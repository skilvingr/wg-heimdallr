"""Shared configuration — imported by the other modules."""

import os
import subprocess

# ── WireGuard ─────────────────────────────────────────────────
WG_INTERFACE = os.environ.get("WG_INTERFACE", "wg0")

# ── nftables ──────────────────────────────────────────────────
NFT_TABLE = "inet vpn"
NFT_SET   = "allowed_clients"

# ── Auth server ───────────────────────────────────────────────
LISTEN_PORT  = int(os.environ.get("LISTEN_PORT", "8080"))
SECRETS_FILE = os.environ.get("SECRETS_FILE", "/config/heimdallr_secrets.json")
ISSUER_NAME  = os.environ.get("ISSUER", "WireGuard VPN")

CERT_FILE = os.environ.get("TLS_CERT", "/config/certs/auth.pem")
KEY_FILE  = os.environ.get("TLS_KEY",  "/config/certs/auth.key")

USERNAME = os.environ.get("USERNAME", "")
PASSWORD = os.environ.get("PASSWORD", "")
TOTP_SECRET = os.environ.get("TOTP_SECRET", "")

FIREWALL_EXCEPTIONS = os.environ.get("FIREWALL_EXCEPTIONS", "")

# ── Bridge IP (the address other containers and VPN clients reach us at) ─
def _detect_ip() -> str:
    """Return the container's eth0 IPv4 address."""
    try:
        out = subprocess.run(
            ["ip", "-4", "-br", "addr", "show", "eth0"],
            capture_output=True, text=True, check=True,
        ).stdout
        # Output: "eth0  UP  10.0.0.2/24 ..."
        import re
        m = re.search(r'(\d+\.){3}\d+', out)
        if m:
            return m.group(0)
    except Exception:
        pass
    return ""

AUTH_IP = os.environ.get("LISTEN_IP") or _detect_ip()

# ── Base URL for HTTPS redirects ──────────────────────────────
# Used when TLS certs exist.  Constructed from the bridge IP
# so the redirect points to an address the client can reach.
BASE_URL = f"https://{AUTH_IP}:{LISTEN_PORT}" if AUTH_IP else ""

# ── Allow plain HTTP? ─────────────────────────────────────────
ALLOW_HTTP = os.environ.get("ALLOW_HTTP", "").lower() in ("1", "true", "yes")

# ── Idle timeout ──────────────────────────────────────────────
IDLE_TIMEOUT = int(os.environ.get("IDLE_TIMEOUT", "60"))

_override = os.environ.get("POLL_INTERVAL")
if _override is not None:
    POLL_INTERVAL = int(_override)
else:
    POLL_INTERVAL = max(5, min(30, IDLE_TIMEOUT // 3))

GRACE_POLLS = max(2, -(-IDLE_TIMEOUT // POLL_INTERVAL))

# ── Telegram ──────────────────────────────────────────────────
TG_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ── Session file ──────────────────────────────────────────────
SESSION_FILE = "/tmp/heimdallr_sessions.json"

