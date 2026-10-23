from __future__ import annotations
import types
import unittest
from hanni.speech.stt import FasterWhisperTranscriber
from hanni.speech.vad import Utterance

class _Segment:

    def __init__(self, text: str) -> None:
        self.text = text

class _FakeWhisper:

    def __init__(self) -> None:
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append((audio, kwargs))
        return (iter([_Segment(' hello '), _Segment('world')]), types.SimpleNamespace(language='en', language_probability=0.99))

class SttTests(unittest.TestCase):

    def test_transcribes_pcm16_and_joins_segments(self) -> None:
        model = _FakeWhisper()
        stt = FasterWhisperTranscriber(model=model, model_name='fake', device='cpu', compute_type='int8', language='en', beam_size=1)
        utterance = Utterance(b'\x01\x00' * 1600, 1.0, 1.1, 16000, 1)
        result = stt.transcribe(utterance)
        self.assertEqual(result.text, 'hello world')
        self.assertEqual(result.language, 'en')
        self.assertAlmostEqual(result.language_probability or 0, 0.99)
        audio, kwargs = model.calls[0]
        self.assertEqual(audio.dtype.name, 'float32')
        self.assertEqual(kwargs['beam_size'], 1)
        self.assertFalse(kwargs['vad_filter'])

    def test_rejects_non_mono_audio(self) -> None:
        stt = FasterWhisperTranscriber(model=_FakeWhisper())
        with self.assertRaisesRegex(ValueError, 'mono'):
            stt.transcribe(Utterance(b'\x00\x00' * 4, 0.0, 1.0, 16000, 2))
