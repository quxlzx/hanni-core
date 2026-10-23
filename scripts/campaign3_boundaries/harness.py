"""Disposable boundary fixtures. Responses are controlled data, never LAYA quality."""
from __future__ import annotations
import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
TOKEN = 'campaign-three-synthetic-authentication-00000000'

def wait_until(predicate, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())

def advisory_response(payload):
    result = dict(version=1, request_id=payload['request_id'], operation=payload['operation'], uncalibrated=True, memory_mutated=False, latency_ms=0.0)
    if payload['operation'] == 'rank':
        result['rankings'] = [dict(id=row['id'], updated_at=row['updated_at'], relevant=True) for row in payload['candidates']]
    else:
        result['suggestions'] = dict(capture=False, importance=0, sensitive=False)
    return result

@contextmanager
def controlled_http(*, redirect=None, delay=0, mutate=None):
    """Own one loopback listener; record only synthetic body and auth-presence."""
    receipts = []

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *_):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            payload = json.loads(raw) if raw else None
            receipts.append(dict(method=self.command, path=self.path, payload=payload, authorization_present=bool(self.headers.get('Authorization'))))
            if redirect:
                self.send_response(302)
                self.send_header('Location', redirect)
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if delay:
                time.sleep(delay)
            result = advisory_response(payload) if payload and 'operation' in payload else {'shadow_only': True}
            if mutate:
                result = mutate(result)
            body = json.dumps(result).encode('utf-8')
            try:
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
    service = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    service.daemon_threads = True
    thread = threading.Thread(target=service.serve_forever, daemon=True, name='campaign3-owned-http')
    thread.start()
    try:
        yield (f'http://127.0.0.1:{service.server_port}', receipts)
    finally:
        service.shutdown()
        service.server_close()
        thread.join(2)

class BlockingOpener:
    """Precise queue/lifecycle seam; no socket or model is used."""

    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.payloads = []

    def open(self, request, timeout):
        payload = json.loads(request.data)
        self.payloads.append(payload)
        if len(self.payloads) == 1:
            self.started.set()
            assert self.release.wait(3), 'Owned blocking fixture was not released'
        return Response(payload)

class Response:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, _=None):
        return json.dumps(advisory_response(self.payload)).encode('utf-8')
