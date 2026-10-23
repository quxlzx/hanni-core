from __future__ import annotations
import unittest
from hanni.core.events import EventType
from hanni.speech.attention import AttentiveTextBridge, SpeechAttentionRouter
from hanni.speech.relevance import SpeechRelevanceClassifier
from hanni.speech.types import TranscriptRecord

class FakeSession:

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def stream_response(self, prompt: str, **kwargs: object):
        self.prompts.append(prompt)
        yield 'response'

def record(text: str, *, transcript_id: str='transcript-1') -> TranscriptRecord:
    return TranscriptRecord(text=text, started_at=1.0, ended_at=2.0, transcript_id=transcript_id)

class AttentionRouterTests(unittest.TestCase):

    def test_owner_command_event_references_transcript_without_copying_text(self) -> None:
        router = SpeechAttentionRouter(SpeechRelevanceClassifier())
        routed = router.route(record('Hanni, hello'))
        self.assertIsNotNone(routed.event)
        assert routed.event is not None
        self.assertEqual(routed.event.type, EventType.OWNER_COMMAND)
        self.assertEqual(routed.event.payload['transcript_id'], 'transcript-1')
        self.assertNotIn('text', routed.event.payload)
        self.assertNotIn('Hanni', routed.event.to_json())

    def test_background_speech_never_calls_supervisor(self) -> None:
        session = FakeSession()
        bridge = AttentiveTextBridge(SpeechAttentionRouter(SpeechRelevanceClassifier()), session)
        routed, response = bridge.handle(record("I think I'll play Valorant later."))
        self.assertFalse(routed.decision.relevant)
        self.assertEqual(list(response), [])
        self.assertEqual(session.prompts, [])

    def test_wake_command_is_forwarded_without_wake_prefix(self) -> None:
        session = FakeSession()
        bridge = AttentiveTextBridge(SpeechAttentionRouter(SpeechRelevanceClassifier()), session)
        routed, response = bridge.handle(record('Ani, explain this.'))
        self.assertTrue(routed.decision.relevant)
        self.assertEqual(list(response), ['response'])
        self.assertEqual(session.prompts, ['explain this'])

    def test_follow_up_uses_same_engagement_state(self) -> None:
        classifier = SpeechRelevanceClassifier(engagement_seconds=60)
        session = FakeSession()
        bridge = AttentiveTextBridge(SpeechAttentionRouter(classifier), session)
        _, first = bridge.handle(record('Hanni, hello', transcript_id='a'))
        list(first)
        routed, second = bridge.handle(record('What next?', transcript_id='b'))
        list(second)
        self.assertTrue(routed.decision.follow_up)
        self.assertEqual(session.prompts[-1], 'What next?')

    def test_filler_during_engagement_never_calls_supervisor(self) -> None:
        classifier = SpeechRelevanceClassifier()
        session = FakeSession()
        bridge = AttentiveTextBridge(SpeechAttentionRouter(classifier), session)
        _, first = bridge.handle(record('Hanni, hello', transcript_id='a'))
        list(first)
        routed, filler = bridge.handle(record('umm', transcript_id='b'))
        self.assertTrue(routed.decision.filler_ignored)
        self.assertEqual(list(filler), [])
        self.assertEqual(session.prompts, ['hello'])
if __name__ == '__main__':
    unittest.main()
