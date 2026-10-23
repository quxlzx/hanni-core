from __future__ import annotations
import unittest
from hanni.config.loader import load_config
from hanni.speech.pipeline import SpeechToTextPipeline
from hanni.speech.types import AudioChunk, Transcription
from hanni.speech.vad import VadDecision
from tests.helpers import TempDirTestCase

class _FakeVad:

    def __init__(self, decisions):
        self.decisions = iter(decisions)

    def process(self, chunk):
        return next(self.decisions)

class _FakeTranscriber:

    def __init__(self, text='testing one two'):
        self.text = text
        self.calls = 0

    def transcribe(self, utterance):
        self.calls += 1
        return Transcription(self.text, 'en', 0.98)

class SpeechPipelineTests(TempDirTestCase):

    def test_process_chunk_yields_transcript_after_vad_end(self) -> None:
        cfg = load_config(self.config_dir(), data_dir=self.data_dir, env={})
        now = [0.0]
        clock = lambda: now[0]
        vad = _FakeVad([VadDecision(), VadDecision(started=True), VadDecision(), VadDecision(ended=True)])
        stt = _FakeTranscriber()
        pipeline = SpeechToTextPipeline(speech=cfg.hanni.speech, raw_audio_retention_seconds=cfg.privacy.retention.raw_audio_seconds, transcript_retention_seconds=cfg.privacy.retention.transcript_seconds, microphone=object(), vad=vad, transcriber=stt, clock=clock)
        result = None
        for i in range(4):
            now[0] = i * 0.032
            chunk = AudioChunk(b'\x00\x00' * 512, 16000, 1, now[0])
            result = pipeline.process_chunk(chunk)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.text, 'testing one two')
        self.assertEqual(stt.calls, 1)
        self.assertEqual(len(pipeline.transcript_buffer), 1)
        self.assertEqual(len(pipeline.audio_buffer), 4)

    def test_empty_stt_result_is_not_buffered(self) -> None:
        cfg = load_config(self.config_dir(), data_dir=self.data_dir, env={})
        vad = _FakeVad([VadDecision(started=True), VadDecision(ended=True)])
        pipeline = SpeechToTextPipeline(speech=cfg.hanni.speech, raw_audio_retention_seconds=120, transcript_retention_seconds=120, microphone=object(), vad=vad, transcriber=_FakeTranscriber('   '), clock=lambda: 0.1)
        self.assertIsNone(pipeline.process_chunk(AudioChunk(b'\x00\x00' * 512, 16000, 1, 0.0)))
        self.assertIsNone(pipeline.process_chunk(AudioChunk(b'\x00\x00' * 512, 16000, 1, 0.032)))
        self.assertEqual(len(pipeline.transcript_buffer), 0)
