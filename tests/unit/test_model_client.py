from __future__ import annotations
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from hanni.config.schema import ModelSpec
from hanni.models.client import LlamaCppClient, ModelProtocolError

def spec(endpoint: str) -> ModelSpec:
    return ModelSpec(id='supervisor', role='supervisor', backend='llama.cpp', model_file='Qwen3-8B-Q4_K_M.gguf', endpoint=endpoint, keep_loaded=True, context_length=8192, api_model='supervisor', hf_repo='Qwen/Qwen3-8B-GGUF', quantization='Q4_K_M', gpu_layers=99, split_mode=None, tensor_split=(), device_name_hints=(), max_tokens=128, temperature=0.6, top_p=0.95, thinking_enabled=False, request_timeout_seconds=3, health_timeout_seconds=1)

class _FakeLlamaHandler(BaseHTTPRequestHandler):
    post_count = 0
    fail_posts = 0
    malformed = False
    last_payload: dict | None = None

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        if self.path != '/v1/health':
            self.send_error(404)
            return
        body = json.dumps({'status': 'ok'}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        type(self).post_count += 1
        length = int(self.headers.get('Content-Length', '0'))
        type(self).last_payload = json.loads(self.rfile.read(length) or b'{}')
        if type(self).post_count <= type(self).fail_posts:
            body = b'{"error":"temporary"}'
            self.send_response(500)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if type(self).last_payload.get('stream') is False:
            body = json.dumps({'choices': [{'message': {'content': 'Done.'}}], 'usage': {'prompt_tokens': 8, 'completion_tokens': 2}}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        if type(self).malformed:
            self.wfile.write(b'data: not-json\n\n')
            return
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n')
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n')
        self.wfile.write(b'data: {"choices":[],"usage":{"prompt_tokens":8,"completion_tokens":2,"total_tokens":10}}\n\n')
        self.wfile.write(b'data: [DONE]\n\n')

class LlamaCppClientTests(unittest.TestCase):

    def setUp(self) -> None:
        _FakeLlamaHandler.post_count = 0
        _FakeLlamaHandler.fail_posts = 0
        _FakeLlamaHandler.malformed = False
        _FakeLlamaHandler.last_payload = None
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), _FakeLlamaHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.client = LlamaCppClient(spec(f'http://{host}:{port}/v1'), max_attempts=2)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_health_uses_llama_v1_health(self) -> None:
        report = self.client.health()
        self.assertTrue(report.ok)
        self.assertEqual(report.state, 'ready')
        self.assertIsNotNone(report.latency_ms)

    def test_streaming_chat_yields_content_and_sends_qwen_settings(self) -> None:
        output = ''.join(self.client.stream_chat([{'role': 'user', 'content': 'hello'}]))
        self.assertEqual(output, 'Hello')
        payload = _FakeLlamaHandler.last_payload
        assert payload is not None
        self.assertTrue(payload['stream'])
        self.assertEqual(payload['model'], 'supervisor')
        self.assertEqual(payload['chat_template_kwargs'], {'enable_thinking': False})
        self.assertEqual(payload['max_tokens'], 128)

    def test_structured_request_enforces_json_and_disables_thinking(self) -> None:
        from dataclasses import replace
        self.client.spec = replace(self.client.spec, thinking_enabled=True)
        self.client.chat([{'role': 'user', 'content': 'decide'}], response_format={'type': 'json_object'})
        payload = _FakeLlamaHandler.last_payload
        self.assertEqual(payload['response_format'], {'type': 'json_object'})
        self.assertEqual(payload['chat_template_kwargs'], {'enable_thinking': False})
        self.assertTrue(self.client.spec.thinking_enabled)

    def test_optional_stream_usage_does_not_change_text(self) -> None:
        usage = {}
        self.assertEqual(self.client.chat([{'role': 'user', 'content': 'hello'}], usage=usage), 'Hello')
        self.assertEqual(usage, {'prompt_tokens': 8, 'completion_tokens': 2, 'total_tokens': 10})
        self.assertEqual(_FakeLlamaHandler.last_payload['stream_options'], {'include_usage': True})

    def test_tool_turn_requests_one_call_at_a_time(self) -> None:
        turn = self.client.complete_with_tools([{'role': 'user', 'content': 'check cpu'}], tools=[])
        self.assertEqual(turn.content, 'Done.')
        self.assertFalse(_FakeLlamaHandler.last_payload['parallel_tool_calls'])

    def test_retry_only_before_visible_output(self) -> None:
        _FakeLlamaHandler.fail_posts = 1
        self.assertEqual(self.client.chat([{'role': 'user', 'content': 'retry'}]), 'Hello')
        self.assertEqual(_FakeLlamaHandler.post_count, 2)

    def test_malformed_stream_is_protocol_error(self) -> None:
        _FakeLlamaHandler.malformed = True
        with self.assertRaises(ModelProtocolError):
            list(self.client.stream_chat([{'role': 'user', 'content': 'bad'}]))
if __name__ == '__main__':
    unittest.main()
