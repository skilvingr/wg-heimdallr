"""Shared nft helpers — imported by auth_server.py and cleanup.py."""

import re, subprocess, sys

from config import (NFT_SET, NFT_TABLE)

sys.stdout.reconfigure(line_buffering=True)


def remove_ip(ip: str) -> bool:
    """Remove an IP from the nftables allowed set. Returns True on success."""
    result = subprocess.run(
        ["nft", "delete", "element", NFT_TABLE, NFT_SET, f"{{ {ip} }}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"! nft delete failed {ip}: {result.stderr.strip()}")
        return False
    return True

def add_ip(ip: str) -> bool:
    try:
        subprocess.run(
            ["nft", "add", "element", NFT_TABLE, NFT_SET, f"{{ {ip} }}"],
            check=True, capture_output=True, text=True,
        )
        print(f"[auth] GRANTED: {ip}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[auth] ERROR adding {ip}: {e.stderr.strip()}")
        return False


def is_authenticated(ip: str) -> bool:
    try:
        result = subprocess.run(
            ["nft", "list", "set", NFT_TABLE, NFT_SET],
            capture_output=True, text=True,
        )
        return bool(re.search(r'\b' + re.escape(ip) + r'\b', result.stdout))
    except Exception:
        return False

def allowed_ips() -> set[str]:
    """Return IPs currently in the nftables allowed_clients set."""
    try:
        out = subprocess.run(
            ["nft", "list", "set", NFT_TABLE, NFT_SET],
            capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return set()
    return set(re.findall(r'(?:\d+\.){3}\d+', out))