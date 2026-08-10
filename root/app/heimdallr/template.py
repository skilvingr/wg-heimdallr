"""Template loader — reads from disk, falls back to defaults.

Load order (first match wins):
    1. /app/heimdallr/templates/<name>        (user override — mount a volume here)
    2. /app/heimdallr/default_templates/<name> (built‑in, shipped in the image)

No templates are hardcoded in this file — everything lives on disk.
"""

import os

TEMPLATES_DIR = os.environ.get("TEMPLATES_DIR", "/app/heimdallr/templates")
DEFAULTS_DIR = os.path.join(os.path.dirname(__file__), "default_templates")


def _load(name: str) -> str:
    """Return the content of *name*, trying templates/ then default_templates/."""
    for base in (TEMPLATES_DIR, DEFAULTS_DIR):
        path = os.path.join(base, name)
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return f.read()
            except OSError:
                pass
    return ""  # both missing — caller gets an empty string


def style() -> str:
    """Return the CSS."""
    return _load("style.css")


def base() -> str:
    """Return the outer <html> wrapper with {title}, {style}, {body}."""
    return _load("base.html")


def login() -> str:
    """Return the login form card with {user_value}, {password_value}, {message}."""
    return _load("login.html")


def granted() -> str:
    """Return the post‑auth card with {timeout_seconds}."""
    return _load("granted.html")
