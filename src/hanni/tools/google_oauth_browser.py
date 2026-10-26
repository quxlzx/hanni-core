"""Cancellable desktop OAuth using the official library's public PKCE APIs."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import secrets
import socket
import time
from urllib.parse import parse_qs, urlsplit
import webbrowser

from hanni.tools.google_identity import GoogleAccessError, verified_scopes


class BrowserGoogleFlow:
    def __init__(self, config, scopes, cancel, *, flow=None, open_browser=None):
        if flow is None:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_config(config, scopes, autogenerate_code_verifier=True)
        self.flow, self.cancel = flow, cancel
        self.open_browser = open_browser or webbrowser.open
        session = getattr(flow, 'oauth2session', None)
        if session is not None:
            session.register_compliance_hook('access_token_response', self._token_response)

    def _token_response(self, response):
        """Normalize only equivalent grants before oauthlib's exact comparison."""
        payload = response.json()
        if isinstance(payload, dict) and 'scope' in payload and 'error' not in payload:
            requested = self.flow.oauth2session.scope
            verified_scopes(payload['scope'], requested)
            # Keep oauthlib's checks enabled. Only equivalent spelling, OpenID
            # metadata and redundant narrower grants have been accepted above.
            payload['scope'] = ' '.join(requested)
            response._content = json.dumps(payload).encode('utf-8')
            response.headers['Content-Length'] = str(len(response._content))
        return response

    def run_local_server(self, *, host, port, timeout_seconds, **options):
        if host != '127.0.0.1' or port != 0:
            raise ValueError('Google sign-in requires a private loopback callback.')
        captured = {}
        expected = {}

        class Server(HTTPServer):
            allow_reuse_address = False

            def server_bind(self):
                if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                super().server_bind()

            def get_request(self):
                connection, address = super().get_request()
                connection.settimeout(2)
                return connection, address

        class Callback(BaseHTTPRequestHandler):
            def log_message(self, *_): pass

            def do_GET(self):
                query = parse_qs(urlsplit(self.path).query)
                valid = (len(self.path) <= 8192 and urlsplit(self.path).path == '/'
                         and self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'
                         and len(query.get('state', [])) == 1
                         and secrets.compare_digest(query['state'][0].encode(), expected['state'].encode())
                         and (len(query.get('code', [])) == 1 or len(query.get('error', [])) == 1))
                if valid:
                    captured.update(query)
                message = ('Return to HANNI. Your Google authorization is being verified.' if valid
                           else 'This callback was not accepted. Return to the Google sign-in you started in HANNI.')
                raw = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>HANNI Google sign-in</title><p>' + message + '</p></html>').encode()
                self.send_response(200 if valid else 400)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(raw)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(raw)

        with Server((host, port), Callback) as server:
            self.flow.redirect_uri = f'http://127.0.0.1:{server.server_port}/'
            for key in ('open_browser', 'authorization_prompt_message', 'success_message'):
                options.pop(key, None)
            auth_url, state = self.flow.authorization_url(**options)
            expected['state'] = state
            parts = urlsplit(auth_url)
            if parts.scheme != 'https' or parts.hostname != 'accounts.google.com' or parts.username is not None:
                raise ValueError('Unexpected Google authorization origin.')
            if self.cancel.is_set(): raise InterruptedError('Google sign-in cancelled.')
            if not self.open_browser(auth_url, new=1, autoraise=True):
                raise RuntimeError('The system browser could not be opened.')
            server.timeout = .25
            deadline = time.monotonic() + min(180, timeout_seconds)
            while not captured and time.monotonic() < deadline and not self.cancel.is_set():
                server.handle_request()
        if self.cancel.is_set(): raise InterruptedError('Google sign-in cancelled.')
        if not captured: raise TimeoutError('Google sign-in timed out.')
        if 'error' in captured: raise GoogleAccessError('Google sign-in was declined.', 'access_denied')
        self.flow.fetch_token(code=captured['code'][0], timeout=20)
        if self.cancel.is_set(): raise InterruptedError('Google sign-in cancelled.')
        return self.flow.credentials
