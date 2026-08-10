"""Shared session file helpers — imported by auth_server.py and cleanup.py."""

import json, os, sys

from config import (SESSION_FILE)

sys.stdout.reconfigure(line_buffering=True)

def load_sessions() -> dict[str, str]:
    try:
        with open(SESSION_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def remove_session(ip: str):
    sessions = load_sessions()
    if ip in sessions:
        del sessions[ip]
        with open(SESSION_FILE, "w") as f:
            json.dump(sessions, f)

def save_session(ip: str, user: str) -> None:
    sessions = {}
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE) as f:
                sessions = json.load(f)
        except Exception:
            pass
    sessions[ip] = user
    with open(SESSION_FILE, "w") as f:
        json.dump(sessions, f)