"""Silero Voice Activity Detection adapter and utterance assembly."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from hanni.speech.microphone import SpeechDependencyError
from hanni.speech.types import AudioChunk


@dataclass(frozen=True, slots=True)
class VadDecision:
    started: bool = False
    ended: bool = False


class SileroVad:
    """Streaming Silero VAD running locally on CPU.

    The official ``silero-vad`` package is loaded lazily.  Its ONNX model is
    requested so inference stays small and does not compete with the Supervisor
    for GPU VRAM.  The package currently exposes ``VADIterator`` for streaming
    512-sample windows at 16 kHz.
    """

    def __init__(
        self,
        *,
        sample_rate: int = 16_000,
        threshold: float = 0.5,
        min_silence_ms: int = 500,
        speech_pad_ms: int = 100,
        iterator: Any | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_silence_ms = min_silence_ms
        self.speech_pad_ms = speech_pad_ms
        self._iterator = iterator

    def _load(self) -> Any:
        if self._iterator is not None:
            return self._iterator
        try:
            import numpy as np  # noqa: F401 - validates speech stack before torch conversion
            import torch
            from silero_vad import VADIterator, load_silero_vad
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SpeechDependencyError(
                'Silero VAD dependencies are not installed; run `.\\scripts\\setup_speech.ps1`'
            ) from exc
        model = load_silero_vad(onnx=True)
        self._iterator = VADIterator(
            model,
            threshold=self.threshold,
            sampling_rate=self.sample_rate,
            min_silence_duration_ms=self.min_silence_ms,
            speech_pad_ms=self.speech_pad_ms,
        )
        return self._iterator

    def prepare(self):
        self._load()

    def process(self, chunk: AudioChunk) -> VadDecision:
        if chunk.sample_rate != self.sample_rate or chunk.channels != 1:
            raise ValueError(f"Silero VAD expects mono {self.sample_rate} Hz audio")
        try:
            import numpy as np
            import torch
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SpeechDependencyError("numpy/torch are required for Silero VAD") from exc
        audio = np.frombuffer(chunk.pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        tensor = torch.from_numpy(audio)
        event = self._load()(tensor, return_seconds=False)
        if not event:
            return VadDecision()
        return VadDecision(started="start" in event, ended="end" in event)

    def reset(self) -> None:
        iterator = self._iterator
        if iterator is not None and hasattr(iterator, "reset_states"):
            iterator.reset_states()


@dataclass(frozen=True, slots=True)
class Utterance:
    pcm16: bytes
    started_at: float
    ended_at: float
    sample_rate: int
    channels: int

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.ended_at - self.started_at)


class UtteranceSegmenter:
    """Convert VAD start/end events into complete PCM utterances.

    A small pre-roll deque avoids clipping the first syllable because Silero may
    emit the start event after speech begins.
    """

    def __init__(self, *, sample_rate: int, block_samples: int, pre_roll_ms: int = 250, max_utterance_seconds: float = 30.0) -> None:
        self.sample_rate = sample_rate
        self.block_samples = block_samples
        self.max_utterance_seconds = max_utterance_seconds
        blocks_per_second = sample_rate / block_samples
        pre_roll_blocks = max(1, round((pre_roll_ms / 1000.0) * blocks_per_second))
        self._recent: deque[AudioChunk] = deque(maxlen=pre_roll_blocks)
        self._active: list[AudioChunk] | None = None
        self._started_at: float | None = None

    @property
    def active(self) -> bool:
        return self._active is not None

    def feed(self, chunk: AudioChunk, decision: VadDecision) -> Utterance | None:
        # Before activation, recent contains the chunk too so a start event can
        # include it and the preceding few blocks.
        if self._active is None:
            self._recent.append(chunk)
            if not decision.started:
                return None
            self._active = list(self._recent)
            self._started_at = self._active[0].captured_at
        else:
            self._active.append(chunk)

        assert self._active is not None and self._started_at is not None
        duration = (chunk.captured_at + chunk.duration_seconds) - self._started_at
        if decision.ended or duration >= self.max_utterance_seconds:
            return self._finish(chunk.captured_at + chunk.duration_seconds)
        return None

    def flush(self) -> Utterance | None:
        if not self._active:
            return None
        last = self._active[-1]
        return self._finish(last.captured_at + last.duration_seconds)

    def reset(self) -> None:
        self._recent.clear()
        self._active = None
        self._started_at = None

    def _finish(self, ended_at: float) -> Utterance:
        assert self._active is not None and self._started_at is not None
        chunks = self._active
        utterance = Utterance(
            pcm16=b"".join(c.pcm16 for c in chunks),
            started_at=self._started_at,
            ended_at=ended_at,
            sample_rate=chunks[0].sample_rate,
            channels=chunks[0].channels,
        )
        self._active = None
        self._started_at = None
        self._recent.clear()
        return utterance
