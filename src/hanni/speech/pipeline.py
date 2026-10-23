"""Milestone 2 microphone -> VAD -> local STT pipeline."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable, Iterator

from hanni.config.schema import SpeechConfig
from hanni.speech.buffer import AudioBuffer, TranscriptBuffer
from hanni.speech.microphone import MicrophoneCapture
from hanni.speech.stt import FasterWhisperTranscriber
from hanni.speech.types import AudioChunk, TranscriptRecord
from hanni.speech.vad import SileroVad, UtteranceSegmenter


class SpeechToTextPipeline:
    """Continuously transcribe local microphone utterances.

    Raw chunks and ordinary transcripts live only in the in-memory rolling
    buffers.  No code in this class writes perception data to disk or logs its
    contents.
    """

    def __init__(
        self,
        *,
        speech: SpeechConfig,
        raw_audio_retention_seconds: int,
        transcript_retention_seconds: int,
        microphone: MicrophoneCapture | None = None,
        vad: SileroVad | None = None,
        transcriber: FasterWhisperTranscriber | None = None,
        clock=time.monotonic,
    ) -> None:
        self.speech = speech
        self.clock = clock
        self.audio_buffer = AudioBuffer(raw_audio_retention_seconds)
        self.transcript_buffer = TranscriptBuffer(transcript_retention_seconds)
        self.microphone = microphone or MicrophoneCapture(
            sample_rate=speech.sample_rate,
            channels=speech.channels,
            block_samples=speech.block_samples,
            device=speech.input_device,
            clock=clock,
        )
        self.vad = vad or SileroVad(
            sample_rate=speech.sample_rate,
            threshold=speech.vad.threshold,
            min_silence_ms=speech.vad.min_silence_ms,
            speech_pad_ms=speech.vad.speech_pad_ms,
        )
        self.transcriber = transcriber or FasterWhisperTranscriber(
            model_name=speech.stt.model,
            device=speech.stt.device,
            compute_type=speech.stt.compute_type,
            language=speech.stt.language,
            beam_size=speech.stt.beam_size,
        )
        self.segmenter = UtteranceSegmenter(
            sample_rate=speech.sample_rate,
            block_samples=speech.block_samples,
            pre_roll_ms=speech.vad.pre_roll_ms,
            max_utterance_seconds=speech.vad.max_utterance_seconds,
        )

    def prepare(self):
        """Warm local speech models without opening a microphone or capturing audio."""
        for component in (self.vad, self.transcriber):
            prepare = getattr(component, 'prepare', None)
            if callable(prepare):
                prepare()

    def run(self, *, stop_event: threading.Event | None = None, once: bool = False) -> Iterator[TranscriptRecord]:
        try:
            for chunk in self.microphone.chunks(stop_event=stop_event):
                record = self.process_chunk(chunk)
                if record is not None:
                    yield record
                    if once:
                        return
        finally:
            # Only the owned running lifecycle releases its perception state.
            # Diagnostic process_chunk callers retain their existing buffers.
            self.audio_buffer.clear()
            self.transcript_buffer.clear()
            self.segmenter.reset()
            reset = getattr(self.vad, 'reset', None)
            if callable(reset):
                reset()

    def process_chunk(self, chunk: AudioChunk) -> TranscriptRecord | None:
        now = self.clock()
        self.audio_buffer.append_chunk(chunk, now=now)
        self.transcript_buffer.cleanup(now=now)
        decision = self.vad.process(chunk)
        utterance = self.segmenter.feed(chunk, decision)
        if utterance is None:
            return None
        if not decision.ended:
            # A forced duration bound does not end Silero's speech state.
            # Rearm it so continuing speech can form another bounded segment.
            self.vad.reset()
        transcription = self.transcriber.transcribe(utterance)
        text = transcription.text.strip()
        if not text:
            return None
        record = TranscriptRecord(
            text=text,
            started_at=utterance.started_at,
            ended_at=utterance.ended_at,
            language=transcription.language,
            language_probability=transcription.language_probability,
        )
        self.transcript_buffer.append_record(record, now=now)
        return record


def create_pipeline(config, *, microphone=None, vad=None, transcriber=None, clock=time.monotonic) -> SpeechToTextPipeline:
    if microphone is None:
        from hanni.speech.audio_devices import selected_input
        device = selected_input(config.paths.data_dir)
        if device is not None:
            speech = config.hanni.speech
            microphone = MicrophoneCapture(sample_rate=speech.sample_rate, channels=speech.channels,
                                           block_samples=speech.block_samples, device=device, clock=clock)
    return SpeechToTextPipeline(
        speech=config.hanni.speech,
        raw_audio_retention_seconds=config.privacy.retention.raw_audio_seconds,
        transcript_retention_seconds=config.privacy.retention.transcript_seconds,
        microphone=microphone,
        vad=vad,
        transcriber=transcriber,
        clock=clock,
    )
