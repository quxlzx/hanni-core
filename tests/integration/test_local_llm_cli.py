from __future__ import annotations
import contextlib
import io
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock
from hanni.cli import run
from tests.helpers import TempDirTestCase

class _Handler(BaseHTTPRequestHandler):

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        if self.path == '/v1/models':
            body = json.dumps({'data': [{'id': 'supervisor', 'object': 'model'}]}).encode()
        elif self.path == '/props':
            body = json.dumps({'model_path': 'test.gguf', 'build_info': 'controlled-cli-fixture', 'default_generation_settings': {'n_ctx': 8192}}).encode()
        elif self.path in {'/health', '/v1/health'}:
            body = b'{"status":"ok"}'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get('Content-Length', '0'))
        payload = json.loads(self.rfile.read(length))
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        if payload.get('response_format'):
            text = json.dumps({'route': 'chat', 'message': 'M1 ONLINE', 'capability_hints': []})
            self.wfile.write(('data: ' + json.dumps({'choices': [{'delta': {'content': text}}]}) + '\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n')
            return
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"M1 "}}]}\n\n')
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"ONLINE"}}]}\n\n')
        self.wfile.write(b'data: [DONE]\n\n')

class LocalLlmCliTests(TempDirTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        super().tearDown()

    def _invoke(self, *args: str) -> tuple[int, str, str]:
        host, port = self.server.server_address
        cfg = self.config_dir({'models.yaml': {'models': [{'id': 'supervisor', 'role': 'supervisor', 'backend': 'llama.cpp', 'model_file': 'test.gguf', 'api_model': 'supervisor', 'endpoint': f'http://{host}:{port}/v1', 'keep_loaded': True, 'context_length': 8192, 'max_tokens': 32, 'health_timeout_seconds': 1, 'request_timeout_seconds': 3}]}})
        out, err = (io.StringIO(), io.StringIO())
        environment = {k: v for k, v in os.environ.items() if not k.startswith('HANNI_')}
        with mock.patch.dict(os.environ, environment, clear=True), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run([*args, '--config-dir', str(cfg), '--data-dir', str(self.data_dir), '--env-file', str(self.tmp / 'none.env'), '--no-file-log'])
        return (code, out.getvalue(), err.getvalue())

    def test_model_health_command(self) -> None:
        code, out, err = self._invoke('model-health')
        self.assertEqual(code, 0, err)
        self.assertIn('HEALTHY', out)

    def test_one_shot_chat_streams_to_stdout(self) -> None:
        code, out, err = self._invoke('chat', 'hello')
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), 'M1 ONLINE')

    def test_model_info_is_machine_readable(self) -> None:
        code, out, err = self._invoke('model-info', '--json')
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload['id'], 'supervisor')
        self.assertEqual(payload['context_length'], 8192)
        self.assertIsNone(payload['split_mode'])
        self.assertEqual(payload['tensor_split'], [])
        self.assertEqual(payload['device_name_hints'], [])
if __name__ == '__main__':
    unittest.main()
