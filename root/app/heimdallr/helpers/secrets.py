import json, os

from config import SECRETS_FILE


def load() -> dict:
    """Return the stored secrets dict, or an empty one if missing/empty/corrupt."""
    if not os.path.exists(SECRETS_FILE):
        return {}
    try:
        with open(SECRETS_FILE) as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if data else {}


def save(data: dict):
    """Write {user: {password, totp}} to disk."""
    os.makedirs(os.path.dirname(SECRETS_FILE), exist_ok=True)
    with open(SECRETS_FILE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
