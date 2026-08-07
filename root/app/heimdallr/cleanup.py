#!/usr/bin/env python3
"""
Rx-byte idle detector — client-side keepalives required.
"""

import json, os, re, subprocess, sys, time

from helpers import nft, session_file
from config import (WG_INTERFACE, POLL_INTERVAL, GRACE_POLLS,
                    TG_TOKEN, TG_CHAT_ID, IDLE_TIMEOUT)

sys.stdout.reconfigure(line_buffering=True)

# ── Persistent state ──────────────────────────────────────────
prev: dict[str, int] = {}
idle: dict[str, int] = {}


# ── WireGuard helpers ─────────────────────────────────────────

def rx_data() -> dict[str, int]:
    """Return {ip: rx_bytes} for every peer in wg dump."""
    try:
        out = subprocess.run(
            ["wg", "show", WG_INTERFACE, "dump"],
            capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return {}

    result = {}
    for line in out.strip().split("\n")[1:]:
        cols = line.split("\t")
        if len(cols) < 7:
            continue
        m = re.search(r'(?:\d+\.){3}\d+', cols[3])   # nft.allowed_ips
        if m:
            result[m.group(0)] = int(cols[5])          # rx
    return result


# ── Telegram (fire-and-forget) ────────────────────────────────

def notify(text: str):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    try:
        subprocess.Popen(
            ["curl", "-s", "--connect-timeout", "5", "--max-time", "10",
             "-X", "POST",
             f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
             "-H", "Content-Type: application/json",
             "-d", json.dumps({"chat_id": TG_CHAT_ID, "text": text,
                               "parse_mode": "HTML"})],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


# ── Revocation ────────────────────────────────────────────────

def revoke(ip: str, reason: str, skip_nft: bool = False):
    """Remove IP from nftables and reset all state.  Returns early
    if the nft command failed (caller should retry next poll)."""

    if not skip_nft:
        if not nft.remove_ip(ip):
            return

    user = session_file.load_sessions().get(ip, "unknown")
    emoji = {"dump": "❌", "frozen": "⏳", "logout": "🚪"}.get(reason, "⚠")
    notify(f"{emoji} <b>VPN session revoked</b>\n"
           f"User: <code>{user}</code>\nIP: <code>{ip}</code> ({reason})")

    prev.pop(ip, None)
    idle.pop(ip, None)
    session_file.remove_session(ip)
    print(f"[cleaner]   revoked {ip} ({reason})")
    return


# ── Main loop ─────────────────────────────────────────────────

def main():
    print(f"[cleaner] cleaner started  poll={POLL_INTERVAL}s  "
          f"grace={GRACE_POLLS}  -> revoke after "
          f"~{POLL_INTERVAL * GRACE_POLLS}s")

    while True:
        time.sleep(POLL_INTERVAL)

        dump    = rx_data()
        allowed = nft.allowed_ips()

        gone = [ip for ip in prev if ip not in allowed]
        for ip in gone:
            # peer not in nft allowed table: manual logout from browser; skip nft deletion
            revoke(ip, "logout", skip_nft=True)

        if not allowed:
            continue

        for ip in sorted(allowed):

            # ── Peer gone from wg dump -> disconnected ─────────
            if ip not in dump:
                revoke(ip, "dump")
                continue

            rx = dump[ip]

            # ── First poll for this IP -> baseline + login ─────
            if ip not in prev:
                prev[ip] = rx
                idle[ip] = 0
                user = session_file.load_sessions().get(ip, "unknown")
                notify(f"🔓 <b>VPN login</b>\n"
                       f"User: <code>{user}</code>\nIP: <code>{ip}</code>")
                print(f"[cleaner]   login  {ip} ({user})")
                continue

            # ── RX changed -> alive ────────────────────────────
            if rx != prev[ip]:
                prev[ip] = rx
                idle[ip] = 0
                continue

            # ── RX frozen ─────────────────────────────────────
            idle[ip] += 1
            if idle[ip] >= GRACE_POLLS:
                revoke(ip, "frozen")
            else:
                print(f"[cleaner]   pending {ip}: frozen {idle[ip]}/{GRACE_POLLS}")


if __name__ == "__main__":
    main()
