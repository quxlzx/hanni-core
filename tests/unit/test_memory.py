from __future__ import annotations
from hanni.core.identity import Actor
from hanni.core.shutdown import EmergencyStop, MemoryStopStateStore, StopSource
from hanni.memory import MemoryAwareSession, MemoryStore, SensitiveMemoryError
from tests.helpers import TempDirTestCase

class _Fallback:

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def stream_response(self, prompt: str, **kwargs: object):
        self.prompts.append(prompt)
        yield 'fallback'

class MemoryStoreTests(TempDirTestCase):

    def store(self) -> MemoryStore:
        return MemoryStore(self.data_dir / 'memory.sqlite3', max_item_chars=1200)

    def test_memory_persists_across_store_reopen(self) -> None:
        store = self.store()
        record, created = store.remember('my preferred code editor is VS Code', source='owner_explicit:test')
        self.assertTrue(created)
        reopened = self.store()
        self.assertEqual(reopened.get(record.id).content, 'my preferred code editor is VS Code')
        self.assertEqual(reopened.count(), 1)

    def test_remember_deduplicates_exact_memory(self) -> None:
        store = self.store()
        first, created = store.remember('I prefer VS Code')
        second, created_again = store.remember('  I   prefer   VS Code  ')
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.id, second.id)
        self.assertEqual(store.count(), 1)

    def test_search_matches_subject_phrase(self) -> None:
        store = self.store()
        store.remember('my preferred code editor is VS Code')
        store.remember('my favorite drink is tea')
        results = store.search('preferred code editor')
        self.assertTrue(results)
        self.assertEqual(results[0].record.content, 'my preferred code editor is VS Code')

    def test_delete_is_verified_and_not_searchable(self) -> None:
        store = self.store()
        record, _ = store.remember('my HANNI project is C:\\Users\\user\\hanni')
        self.assertTrue(store.delete(record.id))
        self.assertIsNone(store.get(record.id))
        self.assertEqual(store.search('HANNI project'), ())

    def test_sensitive_credentials_are_rejected(self) -> None:
        store = self.store()
        for text in ('my password is hunter2-example', 'my 2FA code is 123456', 'my API key is abcdefghijklmnopqrstuvwxyz123456', 'my credit card number is 4111111111111111'):
            with self.subTest(text=text), self.assertRaises(SensitiveMemoryError):
                store.remember(text)
        self.assertEqual(store.count(), 0)

    def test_record_contains_source_confidence_and_timestamps(self) -> None:
        record, _ = self.store().remember('I prefer short spoken answers', source='owner_explicit:keyboard', confidence=1.0)
        self.assertEqual(record.source, 'owner_explicit:keyboard')
        self.assertEqual(record.confidence, 1.0)
        self.assertIsNotNone(record.created_at.tzinfo)
        self.assertIsNotNone(record.updated_at.tzinfo)
        self.assertEqual(record.memory_type, 'preference')

class MemoryAwareSessionTests(TempDirTestCase):

    def make_session(self, *, stopped: bool=False):
        store = MemoryStore(self.data_dir / 'memory.sqlite3')
        fallback = _Fallback()
        emergency = EmergencyStop(MemoryStopStateStore())
        if stopped:
            emergency.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner('test'), reason='test')
        session = MemoryAwareSession(fallback, store, source='keyboard', emergency_stop=emergency)
        return (session, store, fallback, emergency)

    def test_explicit_remember_query_forget_without_model(self) -> None:
        session, store, fallback, _ = self.make_session()
        reply = ''.join(session.stream_response('Remember that my preferred code editor is VS Code.'))
        self.assertIn('remember', reply.lower())
        self.assertEqual(fallback.prompts, [])
        self.assertEqual(store.count(), 1)
        reply = ''.join(session.stream_response('What do you remember about my preferred code editor?'))
        self.assertIn('VS Code', reply)
        self.assertEqual(fallback.prompts, [])
        reply = ''.join(session.stream_response('Forget my preferred code editor.'))
        self.assertIn('Forgot', reply)
        self.assertEqual(store.count(), 0)
        self.assertEqual(fallback.prompts, [])

    def test_delete_everything_removes_all_matches(self) -> None:
        session, store, _, _ = self.make_session()
        store.remember('my HANNI project path is C:\\A')
        store.remember('my HANNI project uses VS Code')
        reply = ''.join(session.stream_response('Delete everything you remember about my HANNI project'))
        self.assertIn('Deleted and verified 2', reply)
        self.assertEqual(store.search('HANNI project'), ())

    def test_sensitive_remember_is_refused(self) -> None:
        session, store, fallback, _ = self.make_session()
        reply = ''.join(session.stream_response('Remember that my password is secret-example-123'))
        self.assertIn("won't store", reply)
        self.assertEqual(store.count(), 0)
        self.assertEqual(fallback.prompts, [])

    def test_safe_mode_blocks_memory_mutation_but_not_read(self) -> None:
        session, store, _, emergency = self.make_session()
        store.remember('I prefer VS Code')
        emergency.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner('test'), reason='test')
        read_reply = ''.join(session.stream_response('What do you remember about VS Code?'))
        self.assertIn('VS Code', read_reply)
        write_reply = ''.join(session.stream_response('Remember that I prefer Python'))
        self.assertIn('Safe Mode', write_reply)
        forget_reply = ''.join(session.stream_response('Forget VS Code'))
        self.assertIn('Safe Mode', forget_reply)
        self.assertEqual(store.count(), 1)

    def test_non_memory_prompt_delegates_unchanged(self) -> None:
        session, _, fallback, _ = self.make_session()
        reply = ''.join(session.stream_response('Explain virtual environments'))
        self.assertEqual(reply, 'fallback')
        self.assertEqual(fallback.prompts, ['Explain virtual environments'])
