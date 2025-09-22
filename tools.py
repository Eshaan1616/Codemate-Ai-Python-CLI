
import subprocess
import os

def run_shell_command(command: str, description: str = None):
    try:
        is_windows = os.name == 'nt'
        process_result = subprocess.run(command, shell=is_windows, check=True, capture_output=True, text=True)
        return {"stdout": process_result.stdout, "stderr": process_result.stderr, "returncode": process_result.returncode}
    except subprocess.CalledProcessError as e:
        return {"error": str(e), "stderr": e.stderr}
    except FileNotFoundError as e:
        return {"error": str(e)}
