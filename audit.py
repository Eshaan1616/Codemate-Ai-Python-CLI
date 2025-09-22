import json
import os
from datetime import datetime

AUDIT_LOG_FILE = "audit_log.jsonl"

def log_audit_record(record):
    """Appends an audit record to the audit log file."""
    with open(AUDIT_LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")

def create_audit_record(nl_input, result, approved, execution_result):
    """Creates an audit record dictionary."""
    return {
        "id": os.urandom(8).hex(),
        "timestamp": datetime.utcnow().isoformat(),
        "user": os.getlogin(),
        "nl_input": nl_input,
        "chosen_command": result["command"],
        "explanation": result["explanation"],
        "confidence": result["confidence"],
        "safety_flags": result["safety_flags"],
        "rule_fallback": result["rule_fallback"],
        "model_meta": result["meta"],
        "approved": approved,
        "execution_result": execution_result,
    }

