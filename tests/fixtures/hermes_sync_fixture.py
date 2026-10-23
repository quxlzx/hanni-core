"""Temporary MCP catalog fixture. It exposes one read-only probe, no side effects."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

class Handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(405)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length > 32768:
            self.send_error(413)
            return
        message = json.loads(self.rfile.read(length))
        if 'id' not in message:
            self.send_response(202)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        method = message['method']
        if method == 'initialize':
            result = {'protocolVersion': message['params']['protocolVersion'], 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'hanni-sync-fixture', 'version': '1'}}
        elif method == 'tools/list':
            result = {'tools': [{'name': 'fixture_probe', 'description': 'Read-only registration fixture; not a production integration.', 'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}, 'annotations': {'readOnlyHint': True, 'destructiveHint': False}}]}
        elif method == 'tools/call' and message['params']['name'] == 'fixture_probe':
            result = {'content': [{'type': 'text', 'text': 'live fixture probe'}], 'isError': False}
        elif method == 'ping':
            result = {}
        else:
            result = {}
        wire = json.dumps({'jsonrpc': '2.0', 'id': message['id'], 'result': result}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(wire)))
        self.end_headers()
        self.wfile.write(wire)
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
