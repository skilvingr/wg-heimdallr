# wg-heimdallr

**Heimdallr** adds two‑factor auth (2FA / MFA) to WireGuard VPNs.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Tests][tests-badge]][tests-url]
[![Publish][publish-badge]][publish-url]

[publish-badge]: https://github.com/skilvingr/wg-heimdallr/actions/workflows/publish.yml/badge.svg
[publish-url]: https://github.com/skilvingr/wg-heimdallr/actions/workflows/publish.yml
[tests-badge]: https://github.com/skilvingr/wg-heimdallr/actions/workflows/tests.yml/badge.svg
[tests-url]: https://github.com/skilvingr/wg-heimdallr/actions/workflows/tests.yml

A companion container that adds **password + TOTP authentication (2FA / MFA)** to any WireGuard setup.  Works with
[linuxserver/wireguard](https://github.com/linuxserver/docker-wireguard),
[wg‑easy](https://github.com/wg-easy/wg-easy),
[wgdashboard](https://github.com/donaldzou/WGDashboard), or a hand‑rolled
WireGuard container — as long as you set `WG_INTERFACE` to match the
tunnel interface name.  No forks.  No image modifications.  Just drop it in.

---

## How it works

1. Peer connects to WireGuard -> all forwarded traffic is dropped by nftables.
2. Any HTTP request is silently redirected to the captive portal.
3. Peer logs in with **password + TOTP** -> IP added to the allowed set.
4. RX byte counters track liveness (client-side keepalive required).
5. If traffic stops -> IP revoked after `IDLE_TIMEOUT` seconds.

---

## Tags

| Tag | Base | Description |
|---|---|---|
| `latest`, `v0.1.0` | `alpine:3.24` | Stable — current Alpine release |
| `edge`, `edge-v0.1.0` | `alpine:edge` | Bleeding edge — Alpine rolling, may break |

---

## Quick start

```yaml
# compose.yml
services:
  wireguard:
    image: lscr.io/linuxserver/wireguard:latest
    container_name: wireguard
    cap_add:
      - NET_ADMIN
      - SYS_MODULE #optional
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Etc/UTC
      - SERVERURL=wireguard.domain.com #optional
      - SERVERPORT=51820 #optional
      - PEERS=1 #optional
      - PEERDNS=auto #optional
      - INTERNAL_SUBNET=10.13.13.0 #optional
      - ALLOWEDIPS=0.0.0.0/0 #optional
      - PERSISTENTKEEPALIVE_PEERS= #optional
      - LOG_CONFS=true #optional
    volumes:
      - /path/to/wireguard/config:/config
      - /lib/modules:/lib/modules #optional
    ports:
      - 51820:51820/udp
    sysctls:
      - net.ipv4.conf.all.src_valid_mark=1
    restart: unless-stopped

  wg-heimdallr:
    image: ghcr.io/skilvingr/wg-heimdallr:latest
    # image: docker.io/skilfingr/wg-heimdallr:latest

    container_name: wg-heimdallr
    cap_add:
      - NET_ADMIN
    network_mode: "container:wireguard"
    volumes:
      - ./heimdallr-config:/config
    environment:
      # ── Core ──────────────────────────────────────────
      - IDLE_TIMEOUT=60
      # - LISTEN_PORT=8080
      # - ALLOW_HTTP=1                   # disable HTTP->HTTPS redirect
      # - FIREWALL_EXCEPTIONS=10.0.0.42,10.0.0.53:53
      # - WG_INTERFACE=wg0               # set to match your tunnel iface
      # - LISTEN_IP=10.0.0.2             # auto-detected from eth0
      # ── Telegram (optional) ──────────────────────────
      # - TELEGRAM_BOT_TOKEN=123:abc
      # - TELEGRAM_CHAT_ID=-100123
      # ── User settings ────────────────────────────────
      # - USERNAME=admin                 # admin or stored if unset
      # - PASSWORD=                      # random or stored if unset
      # - TOTP_SECRET=                   # random or stored if unset
      # ── Advanced ─────────────────────────────────────
      # - POLL_INTERVAL=10               # override auto-derived
      # - SECRETS_FILE=/config/heimdallr_secrets.json
      # - TLS_CERT=/config/certs/auth.pem
      # - TLS_KEY=/config/certs/auth.key
      # - ISSUER=WireGuard VPN
    depends_on:
      - wireguard
    restart: unless-stopped
```

On first start, a random password and TOTP secret are printed
to the logs (or use `USERNAME`, `PASSWORD`, `TOTP_SECRET` to set them
explicitly).  Scan the QR code, log in at
`https://<LISTEN_IP>:<LISTEN_PORT>`, accept the self‑signed certificate.

To change credentials later: update the env vars and restart.
`seed_admin.py` resolves each field as
**env var -> stored -> generated default**.  An empty or unset env var
means "check the stored file; if that's missing too, generate one."

**Peer keepalive** — add `PersistentKeepalive = 5` to every peer
config (client-side). This is how heimdallr knows a peer is still
alive.

---

## Environment variables

All variables and their defaults are documented in [`env_variables`](env_variables).

| Variable | Default | What it does |
|---|---|---|
| `USERNAME` | `admin` | Account name. Empty -> stored (if present) -> `admin`. |
| `PASSWORD` | random | Plain‑text password (hashed before storage). Empty -> stored (if present) -> random. |
| `TOTP_SECRET` | random | Base32 TOTP key. Empty -> stored (if present) -> random. |
| `IDLE_TIMEOUT` | `60` | Seconds before an idle peer is revoked |
| `LISTEN_PORT` | `8080` | Port for the captive portal |
| `LISTEN_IP` | auto | Bridge IP for nftables rules (detected from eth0) |
| `WG_INTERFACE` | `wg0` | WireGuard interface name |
| `ALLOW_HTTP` | unset | Set to `1` to disable the HTTP->HTTPS redirect |
| `FIREWALL_EXCEPTIONS` | unset | Comma‑separated `IP:port` always reachable before login |
| `POLL_INTERVAL` | derived | Override the auto‑derived poll interval |
| `TELEGRAM_BOT_TOKEN` | unset | Telegram bot token for login/revoke notifications |
| `TELEGRAM_CHAT_ID` | unset | Telegram chat ID for notifications |
| `SECRETS_FILE` | `/config/heimdallr_secrets.json` | Path to user credentials |
| `TLS_CERT` | `/config/certs/auth.pem` | Path to TLS certificate |
| `TLS_KEY` | `/config/certs/auth.key` | Path to TLS private key |
| `ISSUER` | `WireGuard VPN` | Name shown in authenticator apps |

---

## Architecture

```
                  Internet
                     │  :51820/udp
                     ▼
┌──────────────────────────────────────┐
│  your WireGuard container            │
│  wg0 · DNS · peer configs            │
└──────────────────────────────────────┘
         │  network_mode: "container:wireguard"
         │  (shared network namespace)
         ▼
┌──────────────────────────────────────┐
│  wg-heimdallr  (companion)            │
│  auth_server :8080  ·  cleanup.py    │
│  nftables  ·  TLS cert               │
└──────────────────────────────────────┘
```

The companion shares the WireGuard container's network namespace.
It sees the same interfaces, adds nftables rules that affect VPN
traffic, and binds the captive portal on the bridge IP.

---

## Android devices

Android phones often stop sending keepalive packets when the screen is
locked — the radio enters power‑save mode regardless of battery optimisation
settings.  To avoid false revocations:

- **Keepalive** — set `PersistentKeepalive = 5` on the client (not the server).
- **Timeout** — keep `IDLE_TIMEOUT` at 60 s or higher.  Even with stalled
  keepalives, WireGuard rekeys every ~120 s, which counts as received traffic.
- **Battery** — disable battery optimisation for the WireGuard app
  (Android Settings -> Apps -> WireGuard -> Battery -> Unrestricted) and enable
  "Always‑on VPN" if available.

---

## Customising templates

The login page, granted page, denied page, stylesheet, and HTML
wrapper live under `/app/heimdallr/default_templates/`.
Override any of them by mounting a volume at the user‑facing path:

```yaml
volumes:
  - ./my-templates:/app/heimdallr/templates
```

The loader checks `templates/` first, then falls back to
`default_templates/`.  Override only the files you need — the rest
use their built‑in versions.

| File | What it controls |
|---|---|
| `style.css` | Colours, spacing, responsive breakpoints |
| `base.html` | Outer `<html>` wrapper (title, style injection) |
| `login.html` | Login form (password + TOTP) |
| `granted.html` | Post‑auth success page |
| `denied.html` | 403 access‑denied page |

All templates use simple `{placeholder}` markers — no template engine
required.

---

## Running tests

```bash
cd docker-wireguard-totp
python3 -m venv venv
source venv/bin/activate
pip install pytest argon2-cffi pyotp
python -m pytest tests/ -v
```

Tests run offline — no WireGuard container needed.  They cover config
derivation, dump parsing, nftables set extraction, secrets I/O, Argon2
verification, and admin seeding.  A GitHub Actions workflow runs them
on every push.

## License

GPL‑3.0.  Gjallarhorn not included.
