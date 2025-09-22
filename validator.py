import re
import os

DANGEROUS_PATTERNS = [
    r'(^|\s)rm\s+-rf\s+/', r'\bshutdown\b', r'\breboot\b', r'>\s*/dev', r'\bchmod\s+0+\b'
]

class ValidationError(Exception):
    pass

def is_dangerous(command_str):
    for pat in DANGEROUS_PATTERNS:
        if re.search(pat, command_str):
            return True
    return False

def is_path_sandboxed(path, sandbox_dir):
    """Checks if a path is within a sandboxed directory."""
    # Resolve the absolute path of the sandbox directory
    sandbox_dir = os.path.abspath(sandbox_dir)
    
    # Resolve the absolute path of the user-provided path
    resolved_path = os.path.abspath(os.path.join(sandbox_dir, path))
    
    # Check if the resolved path is within the sandbox directory
    return os.path.commonpath([resolved_path, sandbox_dir]) == sandbox_dir

def sanitize_and_parse(command_str, cwd):
    """Parses a command string, validates paths, and returns sanitized operations."""
    ops = command_str.split('&&')
    sanitized_ops = []
    
    for op in ops:
        parts = op.strip().split()
        if not parts:
            continue
            
        # Basic path detection: check arguments that don't start with '-'
        for part in parts[1:]:
            if not part.startswith('-') and '/' in part or '\\' in part:
                if not is_path_sandboxed(part, cwd):
                    raise ValidationError(f"Path '{part}' is outside the allowed directory.")
        
        sanitized_ops.append(op.strip())
            
    return sanitized_ops