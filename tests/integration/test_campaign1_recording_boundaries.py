"""Private evaluator seams: source capture and owned filesystem containment."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.campaign1_verification.recording import Recording, hooks, record_into
from scripts.campaign1_verification.fixtures import install_seams
from hanni.models import client
from hanni.config.loader import load_config
from hanni.tools.registry import build_default_registry
from hanni.tools.base import ToolRequest
ROOT = Path(__file__).resolve().parents[2]

class RecordingBoundaries(unittest.TestCase):

    def test_raw_invalid_argument_object_retained_before_original_rejection(self):
        events = []
        r = Recording(events.append)
        raw = json.dumps({'choices': [{'message': {'tool_calls': [{'id': 'bad', 'function': {'name': 'hanni__file__read', 'arguments': 'not-json'}}]}}]})
        with hooks(), record_into(r), r.call('tool_selection', [], {}):
            with self.assertRaises(client.ModelProtocolError):
                client._parse_tool_turn(raw)
        self.assertEqual(r.calls[0]['raw_responses'], [raw])
        self.assertTrue(any((e['kind'] == 'raw_before_tool_parser' for e in events)))

    def test_capture_is_immutable_when_controller_appends_later(self):
        r = Recording(lambda e: None)
        messages = [{'role': 'user', 'content': 'first'}]
        options = {'tools': [{'x': 1}]}
        with r.call('tool_selection', messages, options):
            messages.append({'role': 'tool', 'content': 'later'})
            options['tools'][0]['x'] = 2
        self.assertEqual(len(r.calls[0]['messages']), 1)
        self.assertEqual(r.calls[0]['options']['tools'][0]['x'], 1)

    def test_raw_sse_observed_before_parse_with_usage(self):
        events = []
        r = Recording(events.append)
        usage = {}
        raw = [b'data: {"choices":[{"delta":{"content":"hello"}}]}\n', b'data: {"choices":[],"usage":{"completion_tokens":1,"prompt_tokens":9,"total_tokens":10}}\n', b'data: [DONE]\n']
        with hooks(), record_into(r), r.call('text_generation', [], {}):
            answer = ''.join(client._iter_sse_content(raw, usage=usage))
        self.assertEqual(answer, 'hello')
        self.assertEqual(usage['total_tokens'], 10)
        self.assertEqual(len([e for e in events if e['kind'] == 'raw_before_sse_parser']), 3)

    def test_original_filesystem_rejects_nullable_default_and_foreign_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            state = base / 'state'
            owned = base / 'owned'
            owned.mkdir()
            cfg = load_config(ROOT / 'config', data_dir=state, env={})
            reg = build_default_registry(cfg, data_dir=state)
            source = json.loads((ROOT / 'evals/campaign1/fixture-sources.json').read_text(encoding='utf8'))
            install_seams(reg, {'scope': 'isolated final', 'fixture': {'profile': 'production_config'}}, owned, state, source, lambda e: None)
            for name, args in [('file.search', {}), ('file.search', {'root': None}), ('file.search', {'root': str(base)}), ('file.read', {'path': str(base / 'foreign.txt')})]:
                with self.subTest(name=name, args=args):
                    result = reg.execute(ToolRequest(name, args))
                    self.assertFalse(result.ok)
                    self.assertIn(result.error['code'], {'MISSING_OWNED_FIXTURE_PATH', 'OUTSIDE_OWNED_FIXTURE'})
            (owned / 'actual.txt').write_text('literal owned observation', encoding='utf8')
            result = reg.execute(ToolRequest('file.read', {'path': str(owned / 'actual.txt')}))
            self.assertTrue(result.ok)
            self.assertEqual(result.data['text'], 'literal owned observation')
            from hanni.reliability.execution import close_service
            close_service(state)
if __name__ == '__main__':
    unittest.main()
