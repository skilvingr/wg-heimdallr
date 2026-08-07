#!/usr/bin/env python3
"""
TOTP Captive Portal for WireGuard VPN.
Three-factor auth: WireGuard key -> password -> TOTP.
"""

import html, os, ssl, sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

import template
from helpers import nft, secrets, session_file
from config import (CERT_FILE, KEY_FILE, LISTEN_PORT, SECRETS_FILE, ISSUER_NAME,
                    IDLE_TIMEOUT, BASE_URL, ALLOW_HTTP)


sys.stdout.reconfigure(line_buffering=True)

ph = PasswordHasher()

# ── Request handler ───────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    # ── Helpers ───────────────────────────────────────────────

    def _ensure_https(self) -> bool:
        """If TLS certs exist and this is a plain-HTTP request, redirect
        to HTTPS.  Returns True if a redirect or error was sent."""
        if isinstance(self.connection, ssl.SSLSocket):
            return False
        if ALLOW_HTTP:
            return False
        if BASE_URL:
            self.send_response(302)
            self.send_header("Location", BASE_URL + self.path)
            self.end_headers()
            return True
        self.send_error(500, "Server misconfiguration — contact admin")
        return True

    def _login_error(self, msg: str, user: str = "", password: str = ""):
        self._serve(200, template.base().format(
            title="VPN Auth", style=template.style(),
            body=template.login()
                .replace("{message}", f'<div class="error">{msg}</div>')
                .replace("{user_value}", html.escape(user))
                .replace("{password_value}", html.escape(password))))

    def _serve(self, status: int, html: str, headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(html.encode())


    def do_GET(self):
        if self._ensure_https():
            return
        
        ip = self.client_address[0]

        if nft.is_authenticated(ip):
            self._serve(200, template.base().format(
                title="Granted", style=template.style(),
                body=template.granted().replace("{timeout_seconds}",
                                                str(IDLE_TIMEOUT))))
        else:
            self._serve(200, template.base().format(
                title="VPN Auth", style=template.style(),
                body=template.login()
                    .replace("{message}", "")
                    .replace("{user_value}", "")
                    .replace("{password_value}", "")))


    def do_POST(self):
        if self._ensure_https():
            return

        path   = urlparse(self.path).path
        ip     = self.client_address[0]
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode()
        params = parse_qs(body)

        # ── Login ──────────────────────────────────────────

        if path == "/":
            user     = params.get("user",     [""])[0].strip()
            password = params.get("password", [""])[0]
            token    = params.get("token",    [""])[0].strip()
            data  = secrets.load()

            if not user or user not in data:
                self._login_error("Unknown user", user=user, password=password)
                return
            
            entry = data[user]

            if not entry.get("password"):
                self._login_error("Account has no password.", user=user, password=password)
                return

            try:
                ph.verify(entry["password"], password)
            except VerifyMismatchError:
                self._login_error("Invalid password", user=user, password=password)
                return

            if ph.check_needs_rehash(entry["password"]):
                data[user]["password"] = ph.hash(password)
                secrets.save(data)
                print(f"[auth] rehashed password for {user}")

            if not entry.get("totp"):
                self._login_error("Account has no totp.", user=user, password=password)
                return

            totp = pyotp.TOTP(entry["totp"])
            if not totp.verify(token):
                self._login_error("Invalid TOTP token", user=user, password=password)
                return

            if not nft.add_ip(ip):
                self._login_error("Internal error — contact admin", user=user, password=password)
                return

            session_file.save_session(ip, user)
            self._serve(200, template.base().format(
                title="Granted", style=template.style(),
                body=template.granted().replace("{timeout_seconds}", str(IDLE_TIMEOUT))))

        # ── Logout ────────────────────────────────────────

        elif path == "/logout":
            if not nft.remove_ip(ip):
                return

            session_file.remove_session(ip)
            print(f"[auth] LOGOUT: {ip}")
            self._serve(302, "", {"Location": "/"})

        # ── Fallback ───────────────────────────────────────

        else:
            self._serve(302, "", {"Location": "/"})


class DualStackServer(HTTPServer):
    """Serves HTTP or HTTPS on the same port.

    Peek at the first byte of each new connection:
      - 0x16 (TLS ClientHello) -> wrap with SSL
      - anything else            -> plain HTTP

    If TLS wrapping fails the socket is closed and the error is
    logged; the server keeps running.
    """

    def __init__(self, addr, handler, cert_file, key_file):
        super().__init__(addr, handler)
        self._cert_file = cert_file
        self._key_file = key_file

    def get_request(self):
        sock, addr = super().get_request()
        try:
            first = sock.recv(1, __import__("socket").MSG_PEEK)
            if first and first[0] == 0x16:
                ctx = __import__("ssl").SSLContext(
                    __import__("ssl").PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(self._cert_file, self._key_file)
                sock = ctx.wrap_socket(sock, server_side=True)
        except Exception:
            try:
                sock.close()
            except Exception:
                pass
            raise
        return sock, addr


def main():
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        server = DualStackServer(("0.0.0.0", LISTEN_PORT), Handler,
                                 CERT_FILE, KEY_FILE)
        print(f"[auth] listening on 0.0.0.0:{LISTEN_PORT} (HTTP+HTTPS)")
        print(f"[auth] redirect target: {BASE_URL}")
    else:
        server = HTTPServer(("0.0.0.0", LISTEN_PORT), Handler)
        print(f"[auth] listening on 0.0.0.0:{LISTEN_PORT} (HTTP only)")

    print(f"[auth] secrets: {SECRETS_FILE}  timeout: {IDLE_TIMEOUT}s")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
