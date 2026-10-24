"""HTTPS loopback gateway for a paired personal Teams tab.

The dashboard remains loopback-only and retains its token/origin protections.
Pairing is owner authorization, not a Teams identity assertion. No Graph scopes,
bot registration, tunnel, or public listener is created here.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import ssl
import threading
import time
from urllib.parse import urlsplit

from hanni.dashboard.server import ASSETS

MAX_BODY = 12 * 1024 * 1024
MAX_RESPONSE = 24 * 1024 * 1024
CSP = ("default-src 'self'; connect-src 'self' https://res.cdn.office.net/teams-js/validDomains/json/validDomains.json; script-src 'self'; style-src 'self'; "
       "font-src 'self' data:; img-src 'self' blob: data:; "
       "frame-ancestors https://teams.microsoft.com https://*.teams.microsoft.com https://*.cloud.microsoft; "
       "base-uri 'none'; form-action 'self'")


def validate_origin(value):
    parts = urlsplit(value)
    try:
        port = parts.port
    except ValueError:
        raise ValueError('Choose a valid HTTPS origin.') from None
    if (parts.scheme != 'https' or parts.hostname != 'localhost' or port is None
            or not 1 <= port <= 65535 or parts.username is not None or parts.password is not None
            or parts.path not in {'', '/'} or parts.query or parts.fragment):
        raise ValueError('Use https://localhost:PORT for this personal, same-PC Teams app.')
    return f'https://localhost:{port}'


def validate_upstream(value):
    parts = urlsplit(value)
    try:
        port = parts.port
    except ValueError:
        raise ValueError('Choose a valid local HANNI port.') from None
    if (parts.scheme != 'http' or parts.hostname not in {'127.0.0.1', 'localhost'}
            or port is None or not 1 <= port <= 65535 or parts.username is not None or parts.password is not None
            or parts.path not in {'', '/'} or parts.query or parts.fragment):
        raise ValueError('Use the local HANNI address: http://127.0.0.1:PORT.')
    return f'http://{parts.hostname}:{port}'


class TeamsServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, origin, upstream, certificate, key):
        self.origin = validate_origin(origin)
        self.upstream = validate_upstream(upstream)
        self.sessions = {}
        self.lock = threading.RLock()
        self.pairing_code = secrets.token_urlsafe(24)
        self.pairing_expires = time.monotonic() + 900
        self.failed_pairings = 0
        super().__init__(('127.0.0.1', urlsplit(self.origin).port), TeamsHandler)
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(certificate, key)
            self.socket = context.wrap_socket(self.socket, server_side=True, do_handshake_on_connect=False)
        except Exception:
            self.server_close()
            raise

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        try:
            connection.do_handshake()
        except Exception:
            connection.close()
            raise
        return connection, address

    def session_valid(self, value):
        if not isinstance(value, str) or not 20 <= len(value) <= 100:
            return False
        key = hashlib.sha256(value.encode()).hexdigest()
        with self.lock:
            return self.sessions.get(key, 0) > time.monotonic()

    def pair(self, code):
        with self.lock:
            if (self.failed_pairings >= 10 or time.monotonic() >= self.pairing_expires
                    or not isinstance(code, str) or not secrets.compare_digest(code, self.pairing_code)):
                self.failed_pairings += 1
                raise ValueError('Pairing code is invalid or expired. Restart START_TEAMS.cmd for a new code.')
            token = secrets.token_urlsafe(32)
            self.sessions[hashlib.sha256(token.encode()).hexdigest()] = time.monotonic() + 12 * 3600
            # One launch code authorizes one tab session. Restart to pair again.
            self.pairing_expires = 0
            return token


class TeamsHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Never log pairing codes, session tokens, paths or personal results.

    def send(self, status, body, content_type='application/json', headers=None):
        if isinstance(body, dict):
            body = json.dumps(body).encode()
        try:
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', CSP)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)
        except (OSError, TimeoutError):
            self.close_connection = True

    def allowed(self, *, write=False):
        if self.headers.get('Host') != urlsplit(self.server.origin).netloc:
            self.send(403, {'error': 'Invalid Teams host.'}); return False
        origin = self.headers.get('Origin')
        if origin and origin != self.server.origin or write and origin != self.server.origin:
            self.send(403, {'error': 'Invalid Teams origin.'}); return False
        if self.headers.get('Sec-Fetch-Site') == 'cross-site' and self.path.startswith('/api/'):
            self.send(403, {'error': 'Cross-site API request denied.'}); return False
        return True

    def authorized(self):
        if not self.server.session_valid(self.headers.get('X-Hanni-Teams-Session')):
            self.send(401, {'error': 'Connect this tab using the pairing code from START_TEAMS.cmd.',
                            'error_code': 'teams_session_expired'})
            return False
        return True

    def read_body(self, limit):
        size = int(self.headers.get('Content-Length', '0'))
        if self.headers.get('Transfer-Encoding') or not 0 < size <= limit:
            raise ValueError('Request is too large or has no valid length.')
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise ValueError('Incomplete request.')
        return raw

    def do_GET(self):
        if not self.allowed(): return
        path = urlsplit(self.path).path
        static = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
                  '/style.css': ('style.css', 'text/css'),
                  '/THIRD_PARTY_NOTICES.txt': ('THIRD_PARTY_NOTICES.txt', 'text/plain')}
        if path in static:
            name, mime = static[path]
            return self.send(200, (ASSETS / name).read_bytes(), mime + '; charset=utf-8')
        if path in {'/teams/privacy', '/teams/terms'}:
            text = ('HANNI is a local personal assistant. Pairing gives this tab access to the HANNI session on this computer. '
                    'Conversations, files and connected services retain their HANNI settings. Your selected inference provider '
                    'receives prompts and document excerpts. This tab requests no Microsoft Graph permissions and does not '
                    'read Teams chats. Do not share pairing codes or use this single-user app as a shared service. '
                    'HANNI is experimental; review actions and results. Closing Teams does not stop HANNI or its scheduled work.')
            return self.send(200, ('<!doctype html><html lang="en"><meta charset="utf-8"><title>HANNI personal Teams app</title><h1>HANNI personal Teams app</h1><p>' + text + '</p></html>').encode(), 'text/html; charset=utf-8')
        if not self.authorized(): return
        if path == '/api/teams/session':
            return self.send(200, {'connected': True})
        return self.proxy('GET')

    def do_POST(self):
        # Close rejected writes without attempting to reuse unread bodies.
        self.close_connection = True
        if not self.allowed(write=True): return
        try:
            if self.path == '/api/teams/pair':
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    return self.send(415, {'error': 'JSON required.'})
                body = json.loads(self.read_body(512))
                if not isinstance(body, dict) or set(body) != {'code'}:
                    raise ValueError('Enter the pairing code shown by START_TEAMS.cmd.')
                return self.send(200, {'session': self.server.pair(body['code']), 'expires_in': 43200})
            if not self.authorized(): return
            if self.path == '/api/teams/logout':
                token = self.headers['X-Hanni-Teams-Session']
                with self.server.lock:
                    self.server.sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)
                return self.send(200, {'connected': False})
            return self.proxy('POST', self.read_body(MAX_BODY))
        except (ValueError, UnicodeError, TimeoutError):
            return self.send(400, {'error': 'Request or pairing code is invalid. Check the launcher and try again.'})

    def proxy(self, method, body=None):
        path = urlsplit(self.path).path
        if (not self.path.startswith('/api/') or self.path.startswith('//')
                or any(part in {'.', '..'} for part in path.split('/'))
                or path.startswith(('/api/native-mcp', '/api/sandbox', '/api/teams/'))):
            return self.send(404, {'error': 'This route is unavailable in Teams.'})
        parts = urlsplit(self.server.upstream)
        connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=140)
        # Fixed upstream and narrow headers: no redirects, proxy variables or
        # caller-supplied Authorization/Host/forwarding headers are honored.
        headers = {'Origin': self.server.upstream}
        for name in ('Content-Type', 'X-Hanni-Token'):
            if self.headers.get(name): headers[name] = self.headers[name]
        try:
            connection.request(method, self.path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                return self.send(502, {'error': 'HANNI response exceeds the Teams limit.'})
            if 300 <= response.status < 400:
                return self.send(502, {'error': 'HANNI redirected unexpectedly. No redirect was followed.'})
            extra = {}
            if response.getheader('Content-Disposition'):
                extra['Content-Disposition'] = response.getheader('Content-Disposition')
            return self.send(response.status, raw, response.getheader('Content-Type') or 'application/json', extra)
        except (OSError, http.client.HTTPException):
            return self.send(502, {'error': 'HANNI is unavailable. Start HANNI on this computer, then reconnect.'})
        finally:
            connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run the paired same-PC HANNI Teams tab.')
    parser.add_argument('--origin', default='https://localhost:8313')
    parser.add_argument('--upstream', default='http://127.0.0.1:8311')
    parser.add_argument('--cert', type=Path, required=True)
    parser.add_argument('--key', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        server = TeamsServer(args.origin, args.upstream, args.cert, args.key)
    except (OSError, ValueError, ssl.SSLError) as exc:
        parser.exit(1, f'Teams could not start: {exc}\nRun SETUP_TEAMS.cmd and check that port 8313 is free.\n')
    print(f'HANNI personal Teams tab: {server.origin}/?host=teams\n'
          f'Pairing code (one use, valid 15 minutes): {server.pairing_code}\n'
          'Keep this launcher open. Stop it with Ctrl+C. HANNI remains independent.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
