from __future__ import annotations
import unittest
from hanni.speech.buffer import AudioBuffer, EphemeralBuffer, TranscriptBuffer
from hanni.speech.types import AudioChunk, TranscriptRecord

class SpeechBufferTests(unittest.TestCase):

    def test_retention_is_hard_capped_at_two_minutes(self) -> None:
        with self.assertRaisesRegex(ValueError, 'may not exceed 120'):
            EphemeralBuffer(121)

    def test_audio_buffer_expires_old_chunks(self) -> None:
        buf = AudioBuffer(120)
        first = AudioChunk(b'\x00\x00' * 512, 16000, 1, 0.0)
        second = AudioChunk(b'\x01\x00' * 512, 16000, 1, 60.0)
        newest = AudioChunk(b'\x02\x00' * 512, 16000, 1, 121.0)
        buf.append_chunk(first, now=0.0)
        buf.append_chunk(second, now=60.0)
        buf.append_chunk(newest, now=121.0)
        self.assertEqual(buf.values(now=121.0), (second, newest))

    def test_transcript_buffer_expires_old_records(self) -> None:
        buf = TranscriptBuffer(30)
        a = TranscriptRecord('old', 0.0, 1.0)
        b = TranscriptRecord('new', 35.0, 36.0)
        buf.append_record(a, now=1.0)
        buf.append_record(b, now=36.0)
        self.assertEqual(tuple((r.text for r in buf.values(now=36.0))), ('new',))

    def test_audio_chunk_duration(self) -> None:
        chunk = AudioChunk(b'\x00\x00' * 16000, 16000, 1, 5.0)
        self.assertEqual(chunk.sample_count, 16000)
        self.assertAlmostEqual(chunk.duration_seconds, 1.0)
