"""Speech data types for Milestone 2.

Raw audio and ordinary transcripts are deliberately ephemeral.  These objects
are held in memory only by the speech pipeline; persistence belongs to later
memory milestones and must store extracted facts rather than raw perception.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AudioChunk:
    """One PCM16 mono microphone chunk captured at a monotonic timestamp."""

    pcm16: bytes
    sample_rate: int
    channels: int
    captured_at: float

    @property
    def sample_count(self) -> int:
        bytes_per_frame = 2 * self.channels
        return len(self.pcm16) // bytes_per_frame

    @property
    def duration_seconds(self) -> float:
        return self.sample_count / self.sample_rate if self.sample_rate else 0.0


@dataclass(frozen=True, slots=True)
class Transcription:
    """Result returned by the local STT backend before it enters the buffer."""

    text: str
    language: str | None = None
    language_probability: float | None = None


@dataclass(frozen=True, slots=True)
class TranscriptRecord:
    """One ephemeral recognized utterance."""

    text: str
    started_at: float
    ended_at: float
    language: str | None = None
    language_probability: float | None = None
    transcript_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.ended_at - self.started_at)
