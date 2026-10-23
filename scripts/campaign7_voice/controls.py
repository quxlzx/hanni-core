"""Exposed development leaf fixtures for original voice components only."""
from __future__ import annotations
from types import SimpleNamespace
from hanni.config.schema import SpeechConfig
from hanni.speech.pipeline import SpeechToTextPipeline
from hanni.speech.types import AudioChunk, Transcription

class CaptureBackend:
    """Records controlled stream lifecycle; never calls PortAudio."""

    def __init__(self, *, stop_on_enter=None, fail_open=False, values=(1, 2, 3)):
        self.stop_on_enter, self.fail_open, self.values = (stop_on_enter, fail_open, values)
        self.created = self.entered = self.exited = 0

    def RawInputStream(self, **kwargs):
        self.created += 1
        if self.fail_open:
            raise OSError('Controlled device unavailable')
        owner = self

        class Stream:

            def __enter__(self):
                owner.entered += 1
                if owner.stop_on_enter is not None:
                    owner.stop_on_enter.set()
                for value in owner.values:
                    kwargs['callback'](value.to_bytes(2, 'little', signed=True) * kwargs['blocksize'], kwargs['blocksize'], None, None)
                return self

            def __exit__(self, *args):
                owner.exited += 1
        return Stream()

class Decoder:
    """Controlled decoder output, not a model or expected acoustic transcript."""

    def __init__(self, *, text='controlled transcript', error=None):
        self.text, self.error, self.calls = (text, error, [])

    def transcribe(self, audio, **kwargs):
        self.calls.append({'samples': len(audio), 'options': kwargs})
        if self.error is not None:
            raise self.error
        return (iter([SimpleNamespace(text=self.text)]), SimpleNamespace(language='en', language_probability=0.99))

def chunk(index, *, sample_rate=16000, samples=512):
    return AudioChunk(b'\x01\x00' * samples, sample_rate, 1, index * samples / sample_rate)

def pipeline(vad, *, transcriber=None, clock=lambda: 1.0, speech=None):
    return SpeechToTextPipeline(speech=speech or SpeechConfig(), raw_audio_retention_seconds=120, transcript_retention_seconds=120, microphone=object(), vad=vad, transcriber=transcriber or SimpleNamespace(transcribe=lambda utterance: Transcription('controlled transcript')), clock=clock)
