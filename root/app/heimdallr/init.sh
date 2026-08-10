#!/bin/bash
# ============================================================
# init — bootstrap nftables rules for TOTP access control.
# Idempotent — safe to run across container restarts.
# ============================================================
set -e


TABLE="inet vpn"
SET="allowed_clients"
AUTH_PORT="${LISTEN_PORT:-8080}"
IFACE="${WG_INTERFACE:-wg0}"

if [ -z "${WG_INTERFACE}" ]; then
    echo "[init] WG_INTERFACE not set — defaulting to ${IFACE}"
fi

# Auto-detect container's bridge IP, with env-var override
if [ -n "$LISTEN_IP" ]; then
    AUTH_IP="$LISTEN_IP"
else
    AUTH_IP=$(ip -4 -br addr show eth0 | awk '{print $3}' | cut -d/ -f1)
    if [ -z "$AUTH_IP" ]; then
        echo "[init] ERROR: could not detect eth0 IP. Set LISTEN_IP manually."
        exit 1
    fi
fi

echo "[init] Setting up nftables (table=$TABLE, set=$SET, auth=$AUTH_IP:$AUTH_PORT)"

# ── Table ────────────────────────────────────────────────────
nft add table "$TABLE" 2>/dev/null || true

# ── Allowed-clients set ───────────────────────────────────────
nft add set "$TABLE" "$SET" '{ type ipv4_addr; }' 2>/dev/null || true

# ── Wait for IFACE interface to appear ──────────────────────────
while ! ip link show "$IFACE" >/dev/null 2>&1; do
    echo "[init] Waiting for $IFACE interface (this may take a moment)..."
    sleep 2
done
echo "[init] $IFACE is up — proceeding with nftables setup"

# ── Prerouting chain: captive portal DNAT ─────────────────────
if nft list chain "$TABLE" prerouting >/dev/null 2>&1; then
    nft flush chain "$TABLE" prerouting
else
    nft add chain "$TABLE" prerouting \
        '{ type nat hook prerouting priority dstnat; policy accept; }'
fi

nft add rule "$TABLE" prerouting \
    iif "$IFACE" ip saddr != "@$SET" \
    tcp dport { 80, 3000, 5000, 8000, 8080, 9000 } \
    dnat to "$AUTH_IP:$AUTH_PORT"

# ── Forward chain (idempotent) ────────────────────────────────
if nft list chain "$TABLE" forward >/dev/null 2>&1; then
    nft flush chain "$TABLE" forward
else
    nft add chain "$TABLE" forward \
        '{ type filter hook forward priority -1; policy accept; }'
fi

nft add rule "$TABLE" forward \
    iif "$IFACE" ip daddr "$AUTH_IP" tcp dport "$AUTH_PORT" accept
nft add rule "$TABLE" forward \
    iif "$IFACE" ip saddr "@$SET" accept

EXCEPTIONS="${FIREWALL_EXCEPTIONS:-}"
if [ -n "$EXCEPTIONS" ]; then
    echo "[init] Adding firewall exceptions..."
    IFS=',' read -ra ITEMS <<< "$EXCEPTIONS"
    for item in "${ITEMS[@]}"; do
        item=$(echo "$item" | xargs)
        if [[ "$item" == *:* ]]; then
            ip="${item%%:*}"
            port="${item##*:}"
            nft add rule "$TABLE" forward iif "$IFACE" ip daddr "$ip" tcp dport "$port" accept
            echo "[init]   exception: $ip:$port (TCP)"
        else
            nft add rule "$TABLE" forward iif "$IFACE" ip daddr "$item" accept
            echo "[init]   exception: $item (all)"
        fi
    done
fi

nft add rule "$TABLE" forward \
    iif "$IFACE" reject with icmpx type admin-prohibited

# ── NAT postrouting (idempotent) ──────────────────────────────
if nft list chain "$TABLE" postrouting >/dev/null 2>&1; then
    nft flush chain "$TABLE" postrouting
else
    nft add chain "$TABLE" postrouting \
        '{ type nat hook postrouting priority srcnat; }'
fi

nft add rule "$TABLE" postrouting \
    iif "$IFACE" oif eth0 masquerade

# ── Generate self-signed certificate for HTTPS ────────────────
CERT_DIR="/config/certs"
CERT_FILE="$CERT_DIR/auth.pem"
KEY_FILE="$CERT_DIR/auth.key"
REGEN=0

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    REGEN=1
elif ! openssl x509 -checkend 2592000 -noout -in "$CERT_FILE" 2>/dev/null; then
    echo "[init] Certificate expires within 30 days — regenerating"
    REGEN=1
fi

if [ "$REGEN" -eq 1 ]; then
    echo "[init] Generating self-signed TLS certificate for $AUTH_IP"
    mkdir -p "$CERT_DIR"
    openssl req -x509 -newkey rsa:4096 -sha384 -keyout "$KEY_FILE" \
        -out "$CERT_FILE" -days 365 -nodes \
        -subj "/CN=$AUTH_IP" \
        -addext "subjectAltName=IP:$AUTH_IP" \
        -addext "extendedKeyUsage=serverAuth" 2>/dev/null
    chmod 600 "$KEY_FILE"
    chmod 644 "$CERT_FILE"
    echo "[init] TLS certificate created (valid 1 year)"
fi


python3 /app/heimdallr/seed_admin.py

echo "[init] Done"
