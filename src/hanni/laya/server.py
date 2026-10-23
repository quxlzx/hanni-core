"""Loopback-only bearer-authenticated HTTP service. Run behind SSH port forward."""
import argparse
import hmac
import json
import os
import secrets
import stat
import uuid
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .audit import PrivateAudit
from .engine import InputError, ShadowEngine

MAX_BYTES = 16_384


def default_token_path():
    return Path.home() / '.config/hanni/laya-shadow.token'


def get_token(path):
    path = Path(path).expanduser()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    if not path.exists():
        # Exclusively create; never print token to terminal or logs.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, (secrets.token_urlsafe(32) + '\n').encode())
        finally:
            os.close(fd)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Unsafe token path')
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    token = path.read_text(encoding='utf-8').strip()
    if len(token) < 32:
        raise ValueError('Token must be at least 32 characters')
    return token


def make_handler(engine, audit, token, *, advisory_engine=None, advisory_enabled=False):
    if advisory_engine is not None:
        advisory_engine.shadow.lock = engine.lock
    advisory_slots = threading.BoundedSemaphore(2)
    class Handler(BaseHTTPRequestHandler):
        server_version = 'HanniLayaShadow/0.1'
        sys_version = ''

        def log_message(self, fmt, *args):
            # Never log URLs/headers/body; prevent incidental disclosure.
            return

        def _reply(self, status, obj):
            body = json.dumps(obj, separators=(',', ':')).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self):
            expected = 'Bearer ' + token
            provided = self.headers.get('Authorization', '')
            return hmac.compare_digest(expected.encode(), provided.encode())

        def _discard_small_body(self):
            # Closing a Windows socket with unread POST data can discard the
            # denial response. Drain only a bounded declared body, never parse
            # rejected input, and bound the wait for incomplete requests.
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if 0 < size <= MAX_BYTES and not self.headers.get('Transfer-Encoding'):
                    self.connection.settimeout(.5)
                    self.rfile.read(size)
            except (ValueError, OSError):
                pass

        def do_GET(self):
            if not self._authorized():
                self._reply(401, {'error': 'unauthorized'})
            elif self.path == '/v1/shadow/health':
                self._reply(200, {'healthy': True, 'shadow_only': True})
            elif self.path == '/v1/advisory/health':
                self._reply(200, {'healthy': bool(advisory_enabled and advisory_engine is not None),
                                  'advisory_enabled': bool(advisory_enabled), 'contract_version': 1,
                                  'memory_write_authority': False})
            else:
                self._reply(404, {'error': 'not_found'})

        def do_POST(self):
            if not self._authorized():
                self._discard_small_body()
                self._reply(401, {'error': 'unauthorized'})
                return
            if self.path == '/v1/advisory/evaluate':
                if not advisory_enabled or advisory_engine is None:
                    self._discard_small_body()
                    self._reply(403, {'error': 'advisory_disabled'})
                    return
                if not advisory_slots.acquire(blocking=False):
                    self._discard_small_body()
                    self._reply(503, {'error': 'advisory_busy'})
                    return
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if self.headers.get('Transfer-Encoding') or not 1 <= size <= MAX_BYTES:
                        self._reply(413, {'error': 'invalid_size'})
                        return
                    self.connection.settimeout(2.)
                    payload = json.loads(self.rfile.read(size).decode('utf-8'))
                    result = advisory_engine.evaluate(payload)
                    # Private diagnostics contain only typed score metadata and
                    # identifiers, never input or candidate memory text.
                    audit.write(result['request_id'], {key: value for key, value in result.items()
                                                       if key in {'operation', 'suggestions', 'rankings', 'uncalibrated'}}, result['latency_ms'])
                    self._reply(200, result)
                except (ValueError, UnicodeError, OSError):
                    self._reply(400, {'error': 'invalid_request'})
                except Exception:
                    self._reply(500, {'error': 'advisory_unavailable'})
                finally:
                    advisory_slots.release()
                return
            if self.path != '/v1/shadow/evaluate':
                self._discard_small_body()
                self._reply(404, {'error': 'not_found'})
                return
            try:
                raw_len = self.headers.get('Content-Length', '')
                size = int(raw_len)
                if size < 1 or size > MAX_BYTES:
                    self._reply(413, {'error': 'invalid_size'})
                    return
                raw = self.rfile.read(size)
                payload = json.loads(raw.decode('utf-8'))
                decisions, ms = engine.evaluate(payload)
                req_id = str(uuid.uuid4())
                audit.write(req_id, decisions, ms)
                # Responses deliberately omit predictions, preventing the
                # shadow client from accidentally controlling HANNI behavior.
                self._reply(200, {'accepted': True, 'shadow_only': True, 'request_id': req_id})
            except (ValueError, UnicodeError, InputError, json.JSONDecodeError):
                self._reply(400, {'error': 'invalid_request'})
            except Exception:
                # No user input or stack traces in server outputs.
                self._reply(500, {'error': 'shadow_unavailable'})
    return Handler


def main():
    ap = argparse.ArgumentParser(description='HANNI Laya shadow service (localhost only)')
    ap.add_argument('--model', required=True, help='Existing locally trained Laya checkpoint')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--token-file', default=str(default_token_path()))
    ap.add_argument('--audit-file', default=None)
    ap.add_argument('--enable-advisory', action='store_true', help='Explicitly enable versioned untrusted advisory output; requires separate HANNI client gates')
    args = ap.parse_args()
    token = get_token(args.token_file)
    import laya
    predictor = laya.load(str(Path(args.model).expanduser()))
    engine = ShadowEngine(predictor)
    from .advisory import AdvisoryEngine
    advisory_engine = AdvisoryEngine(predictor) if args.enable_advisory else None
    # Both contracts share serialization around the one installed model.
    if advisory_engine is not None:
        advisory_engine.shadow = engine
    audit = PrivateAudit(args.audit_file)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(engine, audit, token,
                                                                  advisory_engine=advisory_engine, advisory_enabled=args.enable_advisory))
    print(f'Shadow mode listening on 127.0.0.1:{server.server_port}; model loaded; no memory write path', flush=True)
    print('Advisory endpoint: ' + ('enabled at /v1/advisory/evaluate (untrusted suggestions; no write authority)'
                                  if args.enable_advisory else 'disabled; legacy shadow acknowledgements only'), flush=True)
    print(f'Auth token stored at {Path(args.token_file).expanduser()}', flush=True)
    print(f'Private decisions log at {audit.path}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
