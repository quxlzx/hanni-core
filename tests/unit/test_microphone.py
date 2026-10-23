from __future__ import annotations
import unittest
from hanni.speech.microphone import MicrophoneCapture, resolve_device

class _FakeStream:

    def __init__(self, *, callback, blocksize, **kwargs):
        self.callback = callback
        self.blocksize = blocksize

    def __enter__(self):
        for value in (1, 2, 3):
            self.callback(bytes([value, 0]) * self.blocksize, self.blocksize, None, None)
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

class _FakeBackend:
    RawInputStream = _FakeStream

class MicrophoneTests(unittest.TestCase):

    def test_resolve_device(self) -> None:
        self.assertIsNone(resolve_device('default'))
        self.assertEqual(resolve_device('7'), 7)
        self.assertEqual(resolve_device('USB Mic'), 'USB Mic')

    def test_capture_yields_pcm_chunks(self) -> None:
        times = iter([1.0, 1.032, 1.064])
        capture = MicrophoneCapture(sample_rate=16000, channels=1, block_samples=512, backend=_FakeBackend(), clock=lambda: next(times))
        chunks = list(capture.chunks(max_chunks=3))
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].sample_count, 512)
        self.assertEqual(chunks[0].captured_at, 1.0)
