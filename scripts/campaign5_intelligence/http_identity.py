"""Owned loopback server returning controlled protocol bytes, not model answers."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

@contextmanager
def identity_endpoint(mode, reported_model):
    calls = []

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *args):
            pass

        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            model = {} if reported_model is None else {'model': reported_model}
            if mode == 'tools':
                body = json.dumps({**model, 'choices': [{'message': {'content': '', 'tool_calls': [{'id': 'controlled_call', 'type': 'function', 'function': {'name': 'controlled_read', 'arguments': '{"key":"controlled"}'}}]}}]}).encode()
                content_type = 'application/json'
            else:
                events = [dict(model, choices=[{'delta': {'content': 'controlled part'}}])]
                if mode == 'late_stream':
                    events = [{'model': 'controlled_expected', 'choices': [{'delta': {'content': 'first part'}}]}, dict(model, choices=[{'delta': {'content': 'second part'}}])]
                body = b''.join((('data: ' + json.dumps(event) + '\n\n').encode() for event in events)) + b'data: [DONE]\n\n'
                content_type = 'text/event-stream'
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield (f'http://127.0.0.1:{server.server_port}/v1', calls)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
