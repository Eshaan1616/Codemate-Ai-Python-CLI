import os
import json
import subprocess
from datetime import datetime
from llama_cpp import Llama
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from validator import is_dangerous, sanitize_and_parse, ValidationError
from audit import create_audit_record, log_audit_record

CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {"MODEL_PATH": "./models/codellama-7b-instruct.Q4_K_M.gguf"}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

config = load_config()
MODEL_PATH = os.environ.get("MODEL_PATH", config.get("MODEL_PATH"))

llm = None
console = Console()

def load_model():
    global llm
    if not os.path.exists(MODEL_PATH):
        console.print(f"[bold red]Error: Model file not found at {MODEL_PATH}[/bold red]")
        console.print("Please download a GGUF model (e.g., codellama-7b-instruct.Q4_K_M.gguf) and place it in the 'models' directory.")
        console.print("You can find instructions in the 'models/README.md' file.")
        return False
    
    console.print(f"Loading model from {MODEL_PATH}...")
    try:
        llm = Llama(model_path=MODEL_PATH, n_ctx=2048, n_gpu_layers=-1, verbose=False)
        console.print("[bold green]Model loaded successfully.[/bold green]")
        return True
    except Exception as e:
        console.print(f"[bold red]Failed to load model: {e}[/bold red]")
        console.print("Ensure you have installed llama-cpp-python with the correct backend for your system (e.g., `pip install llama-cpp-python[cuda]` for GPU support).")
        return False

def interpret_nl(nl_text: str, cwd: str, os_name: str, history: list = []):
    command = ""
    explanation = ""
    confidence = 0.0
    safety_flags = []
    rule_fallback = False
    meta = {"model": "rule-based-v1"}

    if llm is None:
        console.print("[yellow]Model not loaded, falling back to rule-based.[/yellow]")
        rule_fallback = True
    else:
        try:
            history_prompt = "\n".join(history)
            prompt = f"""System: You are a strict translator of English instructions into a command sequence for the '{os_name}' operating system. Only output JSON: {{"command":"...","explanation":"...","confidence":0.0}}.If the instruction is ambiguous, return "AMBIGUOUS" in command and provide explanation.
                {history_prompt}
                User: cwd={cwd}, instruction = "{nl_text}"
                """
            
            output = llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that translates natural language to shell commands."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.1,
            )
            
            model_content = output["choices"][0]["message"]["content"]
            
            try:
                model_json = json.loads(model_content)
                command = model_json.get("command", "")
                explanation = model_json.get("explanation", "")
                confidence = model_json.get("confidence", 0.0)
                rule_fallback = False
                meta = {"model": "llama-cpp-python"}
            except json.JSONDecodeError:
                console.print(f"[bold red]Model output not valid JSON: {model_content}[/bold red]")
                rule_fallback = True
        except Exception as e:
            console.print(f"[bold red]Error calling LLM: {e}, falling back to rule-based.[/bold red]")
            rule_fallback = True

    if is_dangerous(command):
        safety_flags.append("dangerous_command")

    return {
        "command": command,
        "explanation": explanation,
        "confidence": confidence,
        "safety_flags": safety_flags,
        "rule_fallback": rule_fallback,
        "meta": meta
    }

def create_trash_directory():
    trash_dir = os.path.join(os.path.expanduser("~"), ".trash")
    if not os.path.exists(trash_dir):
        os.makedirs(trash_dir)

from tools import run_shell_command

def execute_tool(command, nl_command, result):
    try:
        execution_result = run_shell_command(command=command, description=result['explanation'])
        console.print(Panel(execution_result['stdout'], title="Command Output", border_style="green"))
        if execution_result.get('stderr'):
            console.print(Panel(execution_result['stderr'], title="Error Output", border_style="red"))
    except Exception as e:
        console.print(f"[bold red]Error executing tool: {e}[/bold red]")
        execution_result = {"error": str(e)}
    finally:
        audit_record = create_audit_record(nl_command, result, True, execution_result)
        log_audit_record(audit_record)

def main():
    create_trash_directory()
    if not load_model():
        console.print("[bold red]Exiting due to model loading failure.[/bold red]")
        return

    console.print(Panel("""[bold cyan]Welcome to the Enhanced CLI![/bold cyan]
Type your natural language command or 'exit' to quit.""", title="Enhanced CLI", border_style="green"))
    history = []
    while True:
        try:
            nl_command = console.input("[bold green]>[/bold green] ")
            if nl_command.lower() in ["exit", "quit"]:
                console.print("[bold cyan]Exiting...[/bold cyan]")
                break

            current_working_directory = os.getcwd()

            if "and then" in nl_command.lower():
                commands = nl_command.lower().split("and then")
                for cmd in commands:
                    result = interpret_nl(cmd, current_working_directory, os.name, history)
                    if result["command"] and result["confidence"] > 0.8:
                        execute_tool(result['command'], cmd, result)
                        history.append(f"User: {cmd}")
                        history.append(f"Assistant: {result['command']}")
                    else:
                        console.print(f"[yellow]Could not interpret the command: {cmd}[/yellow]")
                continue

            result = interpret_nl(nl_command, current_working_directory, os.name, history)
            if result and result.get("command"):
                history.append(f"User: {nl_command}")
                history.append(f"Assistant: {result['command']}")
            
            try:
                sanitized_ops = sanitize_and_parse(result['command'], current_working_directory)
                result['command'] = " && ".join(sanitized_ops)
            except ValidationError as e:
                console.print(f"[bold red]Validation Error: {e}[/bold red]")
                continue

            if result['command'] == "AMBIGUOUS":
                console.print(f"[yellow]The command is ambiguous. {result['explanation']}[/yellow]")
                nl_command = console.input("[bold green]Please provide more details: [/bold green] ")
                continue

            if result['confidence'] < 0.8:
                console.print("[yellow]Could not interpret the command with high confidence. Here are some options:[/yellow]")
                options = [
                    result['command'],
                    "Search for files",
                    "Create a new file",
                    "Read a file",
                    "Write to a file"
                ]
                table = Table(title="Command Options")
                table.add_column("Number", style="cyan")
                table.add_column("Option", style="magenta")
                for i, option in enumerate(options):
                    table.add_row(str(i+1), option)
                console.print(table)
                selection = console.input("Select an option (or press enter to cancel): ")
                if selection.isdigit() and 1 <= int(selection) <= len(options):
                    selected_option = options[int(selection)-1]
                    if selected_option == result['command']:
                        nl_command = result['command']
                    else:
                        nl_command = selected_option
                    result = interpret_nl(nl_command, current_working_directory, os.name, history)
                else:
                    console.print("[yellow]Command not executed.[/yellow]")
                    continue

            table = Table(title="Command Interpretation")
            table.add_column("Attribute", style="cyan")
            table.add_column("Value", style="magenta")
            table.add_row("Command", Syntax(result['command'], "bash", theme="monokai", line_numbers=True))
            table.add_row("Explanation", result['explanation'])
            table.add_row("Confidence", f"{result['confidence']:.2f}")
            table.add_row("Model", result['meta']['model'])
            console.print(table)

            if "dangerous_command" in result["safety_flags"]:
                console.print(Panel(f"[bold yellow]Warning:[/bold yellow] The command is considered potentially dangerous.", title="Security Alert", border_style="yellow"))
            
            confirm = console.input("Run this command? (y/n): ")
            if confirm.lower() == 'y':
                if result['command'].strip().startswith("rm "):
                    parts = result['command'].strip().split()
                    if len(parts) > 1:
                        file_to_move = parts[1]
                        trash_dir = os.path.join(os.path.expanduser("~"), ".trash")
                        try:
                            if os.path.exists(file_to_move):
                                trashed_file_name = os.path.basename(file_to_move)
                                trashed_file_path = os.path.join(trash_dir, trashed_file_name)
                                os.rename(file_to_move, trashed_file_path)
                                execution_result = {"action": "trashed", "file": file_to_move, "destination": trashed_file_path}
                                console.print(f"Moved '{file_to_move}' to '{trashed_file_path}'.")
                            else:
                                execution_result = {"error": f"File not found: {file_to_move}"}
                                console.print(f"[red]Error: File not found - {file_to_move}[/red]")
                        except Exception as e:
                            execution_result = {"error": str(e)}
                            console.print(f"[red]Error moving file to trash: {e}[/red]")
                        finally:
                            audit_record = create_audit_record(nl_command, result, True, execution_result)
                            log_audit_record(audit_record)
                    else:
                        console.print("[red]Invalid rm command, no file specified.[/red]")
                else:
                    execute_tool(result['command'], nl_command, result)
            else:
                audit_record = create_audit_record(nl_command, result, False, None)
                log_audit_record(audit_record)
                console.print("[yellow]Command not executed.[/yellow]")

        except KeyboardInterrupt:
            console.print("\n[bold cyan]Exiting...[/bold cyan]")
            break
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")

if __name__ == "__main__":
    main()