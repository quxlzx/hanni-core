from __future__ import annotations
import unittest
from hanni.config.schema import MAX_EPHEMERAL_RETENTION_SECONDS
from hanni.core.events import Event, EventType
from hanni.speech.buffer import AudioBuffer, TranscriptBuffer

class SpeechPrivacyTests(unittest.TestCase):

    def test_speech_buffers_cannot_exceed_privacy_ceiling(self) -> None:
        for cls in (AudioBuffer, TranscriptBuffer):
            with self.subTest(cls=cls.__name__):
                with self.assertRaises(ValueError):
                    cls(MAX_EPHEMERAL_RETENTION_SECONDS + 1)

    def test_transcript_event_can_reference_id_without_raw_window(self) -> None:
        event = Event(EventType.TRANSCRIPT_READY, 'speech.stt', payload={'transcript_id': 'abc123', 'duration_ms': 800})
        payload = event.to_dict()['payload']
        self.assertNotIn('text', payload)
        self.assertNotIn('audio', payload)
