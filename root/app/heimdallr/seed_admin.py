#!/usr/bin/env python3
"""
Runs at startup.  Manages the single-user account.

Three env vars control credentials:
  USERNAME     – account name             (default: admin)
  PASSWORD     – plain-text password      (default: auto-generated)
  TOTP_SECRET  – base32 TOTP key          (default: auto-generated)

Rules on every start:
  • Stored secrets exist and have valid values -> compare with env
  • If any explicitly-set env var differs from stored -> update file
  • If nothing changed -> skip
  • Stored secrets missing or incomplete -> create/update from env
    or generate any missing fields

Generated passwords and TOTP secrets are printed to the log
once.  Values supplied via env vars are never logged.
"""

import secrets as _sec, string, subprocess, sys
import pyotp
from argon2 import PasswordHasher

from helpers import secrets
from config import (AUTH_IP, USERNAME, PASSWORD, TOTP_SECRET, ISSUER_NAME,
                    LISTEN_PORT, SECRETS_FILE)

sys.stdout.reconfigure(line_buffering=True)

ph = PasswordHasher()


# ── Helpers ───────────────────────────────────────────────────

def generate_password(length: int = 16) -> str:
    lowers = string.ascii_lowercase
    uppers = string.ascii_uppercase
    digits = string.digits
    symbols = string.punctuation
    all_chars = lowers + uppers + digits + symbols

    chars = [
        _sec.choice(lowers),
        _sec.choice(uppers),
        _sec.choice(digits),
        _sec.choice(symbols),
    ]
    chars += [_sec.choice(all_chars) for _ in range(length - 4)]
    _sec.SystemRandom().shuffle(chars)
    return "".join(chars)


def print_qr(uri: str) -> None:
    """Print a QR code to the terminal using qrencode (ANSI UTF-8)."""
    try:
        subprocess.run(["qrencode", "-t", "ansiutf8", uri], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"  (qrencode not available — use this URI instead)")
        print(f"  {uri}")

# ── Main ──────────────────────────────────────────────────────

def main():
    stored = secrets.load()
    key = next(iter(stored)) if stored else None

    # ── Resolve credentials: env var -> stored -> default ──────
    user = USERNAME
    if not user and stored:
        user = key
    if not user:
        user = "admin"

    pw = PASSWORD
    pw_generated = False
    if not pw and stored:
        pw = stored[key]["password"]            # keep stored hash (can't recover plaintext)
    if not pw:
        pw = generate_password()
        pw_generated = True

    totp = TOTP_SECRET
    totp_generated = False
    if not totp and stored:
        totp = stored[key]["totp"]
    if not totp:
        totp = pyotp.random_base32()
        totp_generated = True

    # ── Stored exists and is valid -> compare with resolved ────
    if stored and stored[key]["password"] and stored[key]["totp"]:
        user_changed = key != user

        pw_changed = False
        if PASSWORD:
            try:
                ph.verify(stored[key]["password"], PASSWORD)
            except Exception:
                pw_changed = True

        totp_changed = bool(TOTP_SECRET) and TOTP_SECRET != stored[key]["totp"]

        if not user_changed and not pw_changed and not totp_changed:
            print("[seed] credentials match — nothing to update")
            return

    # ── Write ─────────────────────────────────────────────────
    pw_hash = pw
    pw_is_hash = not PASSWORD and stored and pw == stored[key]["password"]
    if pw_is_hash:
        pass                       # already a hash, write as-is
    else:
        pw_hash = ph.hash(pw)

    data = {user: {"password": pw_hash, "totp": totp}}
    secrets.save(data)

    # ── Print banner ──────────────────────────────────────────
    gateway = AUTH_IP or "<your-gateway-ip>"
    print()
    print("=" * 60)
    if stored:
        print("  ACCOUNT UPDATED")
    else:
        print("  ACCOUNT CREATED")
    print("=" * 60)
    print(f"  Username:    {user}")
    if pw_generated:
        print(f"  Generated new password:    {pw}")
    else:
        print(f"  Using password from env" if PASSWORD else "  Using stored password")
    print()
    if totp_generated:
        uri = pyotp.TOTP(totp).provisioning_uri(user, issuer_name=ISSUER_NAME)
        print("  Generated new TOTP code. Scan this QR with your authenticator app:")
        print()
        print_qr(uri)
    else:
        print("  Using TOTP from env" if TOTP_SECRET else "  Using stored TOTP")
    print()
    print(f"  Bookmark:    https://{gateway}:{LISTEN_PORT}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
