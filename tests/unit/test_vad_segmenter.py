from __future__ import annotations
import unittest
from hanni.speech.types import AudioChunk
from hanni.speech.vad import UtteranceSegmenter, VadDecision

def chunk(index: int) -> AudioChunk:
    samples = 512
    return AudioChunk(bytes([index % 255, 0]) * samples, 16000, 1, index * (samples / 16000))

class UtteranceSegmenterTests(unittest.TestCase):

    def test_start_end_builds_utterance_with_preroll(self) -> None:
        segmenter = UtteranceSegmenter(sample_rate=16000, block_samples=512, pre_roll_ms=64, max_utterance_seconds=30)
        self.assertIsNone(segmenter.feed(chunk(0), VadDecision()))
        self.assertIsNone(segmenter.feed(chunk(1), VadDecision()))
        self.assertIsNone(segmenter.feed(chunk(2), VadDecision(started=True)))
        self.assertTrue(segmenter.active)
        self.assertIsNone(segmenter.feed(chunk(3), VadDecision()))
        utterance = segmenter.feed(chunk(4), VadDecision(ended=True))
        self.assertIsNotNone(utterance)
        assert utterance is not None
        self.assertGreaterEqual(len(utterance.pcm16), 4 * 512 * 2)
        self.assertFalse(segmenter.active)

    def test_max_duration_forces_finish(self) -> None:
        segmenter = UtteranceSegmenter(sample_rate=16000, block_samples=512, pre_roll_ms=0, max_utterance_seconds=0.05)
        self.assertIsNone(segmenter.feed(chunk(0), VadDecision(started=True)))
        utterance = segmenter.feed(chunk(1), VadDecision())
        self.assertIsNotNone(utterance)

    def test_flush_returns_active_audio(self) -> None:
        segmenter = UtteranceSegmenter(sample_rate=16000, block_samples=512)
        segmenter.feed(chunk(0), VadDecision(started=True))
        utterance = segmenter.flush()
        self.assertIsNotNone(utterance)
        self.assertFalse(segmenter.active)

class _FakeIterator:

    def __init__(self, event):
        self.event = event
        self.calls = 0
        self.reset_called = False

    def __call__(self, tensor, return_seconds=False):
        self.calls += 1
        return self.event

    def reset_states(self):
        self.reset_called = True

class SileroAdapterTests(unittest.TestCase):

    def test_injected_iterator_maps_silero_event(self) -> None:
        import pytest
        pytest.importorskip('torch', reason='Optional torch adapter NOT TESTED without the test-speech extra.')
        from hanni.speech.vad import SileroVad
        iterator = _FakeIterator({'start': 123})
        vad = SileroVad(iterator=iterator)
        decision = vad.process(AudioChunk(b'\x00\x00' * 512, 16000, 1, 0.0))
        self.assertTrue(decision.started)
        self.assertFalse(decision.ended)
        vad.reset()
        self.assertTrue(iterator.reset_called)
