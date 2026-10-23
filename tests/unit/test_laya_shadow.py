"""Laya shadow contract tests; no model, network, or training data required."""
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from http.client import HTTPConnection
import json
import time
import urllib.request
from urllib.error import HTTPError
from hanni.laya.audit import PrivateAudit
from hanni.laya.client import ShadowClient
from hanni.laya.engine import ShadowEngine
from hanni.laya.manager import LayaShadowManager, enabled
from hanni.laya.server import MAX_BYTES, make_handler
from hanni.memory.session import MemoryAwareSession
from hanni.memory.store import MemoryStore
TOKEN = 'A' * 48

class FakePredictor:

    def __init__(self):
        self.calls = []

    def predict(self, text, questions):
        self.calls.append((text, set(questions)))
        return {'answers': {k: {'choice': 'add'} if k == 'relation' else {'score': 2.0} if k == 'importance' else {'noul': 0.9} for k in questions}}

def test_rejected_incomplete_and_oversize_posts_stay_bounded_and_do_not_evaluate(tmp_path):
    predictor = FakePredictor()
    audit = PrivateAudit(tmp_path / 'private' / 'decisions.jsonl')
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(ShadowEngine(predictor), audit, TOKEN))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for declared_length in (32, MAX_BYTES + 1):
            connection = HTTPConnection('127.0.0.1', server.server_port, timeout=2)
            started = time.monotonic()
            try:
                connection.request('POST', '/v1/shadow/evaluate', headers={'Content-Length': str(declared_length)})
                response = connection.getresponse()
                assert response.status == 401
                assert json.loads(response.read()) == {'error': 'unauthorized'}
                assert time.monotonic() - started < 2
            finally:
                connection.close()
        assert predictor.calls == []
        assert not audit.path.exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

class ShadowContractTests(unittest.TestCase):

    def test_server_is_read_only_and_never_returns_prediction(self):
        with tempfile.TemporaryDirectory() as d:
            predictor = FakePredictor()
            audit = PrivateAudit(Path(d) / 'private' / 'decisions.jsonl')
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(ShadowEngine(predictor), audit, TOKEN))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f'http://127.0.0.1:{server.server_port}/v1/shadow/evaluate'
            try:
                body = json.dumps({'utterance': 'I have 32GB RAM'}).encode()
                req = urllib.request.Request(url, body, headers={'Authorization': 'Bearer ' + TOKEN})
                with urllib.request.urlopen(req, timeout=3) as res:
                    response = json.load(res)
                self.assertTrue(response['shadow_only'])
                self.assertEqual(set(response), {'accepted', 'shadow_only', 'request_id'})
                saved = audit.path.read_text()
                self.assertNotIn('32GB', saved)
                self.assertIn('"memory_mutated":false', saved)
                self.assertEqual(len(predictor.calls), 1)
                with self.assertRaises(HTTPError) as error:
                    urllib.request.urlopen(urllib.request.Request(url, body), timeout=3)
                self.assertEqual(error.exception.code, 401)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_disabled_by_default_and_remote_requires_extra_consent(self):
        self.assertFalse(enabled({}))
        m = LayaShadowManager({'HANNI_LAYA_SHADOW_ENABLED': '1', 'HANNI_LAYA_TRANSPORT': 'remote-ssh'})
        m.start()
        self.assertIsNone(m._worker)
        self.assertIn('consent', m.status)

    def test_invalid_port_rejected(self):
        with self.assertRaises(ValueError):
            LayaShadowManager({'HANNI_LAYA_LOCAL_PORT': '10'})

    def test_private_utterances_are_not_forwarded(self):
        m = LayaShadowManager({})

        class FakeClient:

            def __init__(self):
                self.calls = []

            def observe(self, **kw):
                self.calls.append(kw)
                return True

            def close(self):
                pass
        m._client = FakeClient()
        self.assertFalse(m.observe('Here is my password: abc'))
        self.assertFalse(m.observe('Set this API key'))
        self.assertTrue(m.observe('I prefer concise responses'))
        self.assertEqual(len(m._client.calls), 1)
        m.close()

    def test_memory_session_invokes_observer_without_using_its_answer(self):

        class Observer:

            def __init__(self):
                self.observed = []

            def observe(self, text):
                self.observed.append(text)
                return 'supersede'

        class Fallback:

            def stream_response(self, prompt, **kwargs):
                yield 'normal response'
        with tempfile.TemporaryDirectory() as d:
            store = MemoryStore(Path(d) / 'private.sqlite3')
            observer = Observer()
            session = MemoryAwareSession(Fallback(), store, extraction_enabled=False, retrieval_enabled=False, shadow_observer=observer)
            result = ''.join(session.stream_response('What is 2+2?'))
            self.assertEqual(result, 'normal response')
            self.assertEqual(observer.observed, ['What is 2+2?'])
            self.assertEqual(store.list(), ())

    def test_failing_observer_does_not_change_response(self):

        class Broken:

            def observe(self, text):
                raise RuntimeError('offline')

        class Fallback:

            def stream_response(self, prompt, **kwargs):
                yield 'still works'
        with tempfile.TemporaryDirectory() as d:
            session = MemoryAwareSession(Fallback(), MemoryStore(Path(d) / 'mem.sqlite3'), extraction_enabled=False, retrieval_enabled=False, shadow_observer=Broken())
            self.assertEqual(''.join(session.stream_response('hi')), 'still works')
if __name__ == '__main__':
    unittest.main()

def test_safe_mode_suppresses_shadow_observation(tmp_path):
    from hanni.core.shutdown import EmergencyStop, MemoryStopStateStore, StopSource
    from hanni.core.identity import Actor

    class Observer:

        def __init__(self):
            self.calls = []

        def observe(self, text):
            self.calls.append(text)

    class Fallback:

        def stream_response(self, prompt, **kwargs):
            yield 'normal fallback'
    stop = EmergencyStop(MemoryStopStateStore())
    stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('test'), reason='test')
    obs = Observer()
    sess = MemoryAwareSession(Fallback(), MemoryStore(tmp_path / 'safe.sqlite3'), extraction_enabled=False, retrieval_enabled=False, emergency_stop=stop, shadow_observer=obs)
    assert ''.join(sess.stream_response('hello')) == 'normal fallback'
    assert obs.calls == []
