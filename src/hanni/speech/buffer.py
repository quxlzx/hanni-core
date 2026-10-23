"""In-memory rolling privacy buffers for raw audio and transcripts."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Generic, TypeVar

from hanni.config.schema import MAX_EPHEMERAL_RETENTION_SECONDS
from hanni.speech.types import AudioChunk, TranscriptRecord

T = TypeVar("T")


@dataclass(slots=True)
class _TimedItem(Generic[T]):
    timestamp: float
    value: T


class EphemeralBuffer(Generic[T]):
    """A bounded-by-time in-memory buffer.

    ``now`` is supplied by callers so tests can use a deterministic monotonic
    clock.  Retention is hard-capped at 120 seconds even if constructed by code
    that did not come through configuration validation.
    """

    def __init__(self, retention_seconds: float) -> None:
        if retention_seconds <= 0:
            raise ValueError("retention_seconds must be > 0")
        if retention_seconds > MAX_EPHEMERAL_RETENTION_SECONDS:
            raise ValueError(f"retention_seconds may not exceed {MAX_EPHEMERAL_RETENTION_SECONDS}")
        self.retention_seconds = float(retention_seconds)
        self._items: deque[_TimedItem[T]] = deque()

    def append(self, value: T, *, timestamp: float, now: float | None = None) -> None:
        self._items.append(_TimedItem(timestamp=float(timestamp), value=value))
        self.cleanup(now=timestamp if now is None else now)

    def cleanup(self, *, now: float) -> int:
        cutoff = float(now) - self.retention_seconds
        removed = 0
        while self._items and self._items[0].timestamp < cutoff:
            self._items.popleft()
            removed += 1
        return removed

    def clear(self) -> None:
        self._items.clear()

    def values(self, *, now: float | None = None) -> tuple[T, ...]:
        if now is not None:
            self.cleanup(now=now)
        return tuple(item.value for item in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        return (item.value for item in self._items)


class AudioBuffer(EphemeralBuffer[AudioChunk]):
    def append_chunk(self, chunk: AudioChunk, *, now: float | None = None) -> None:
        self.append(chunk, timestamp=chunk.captured_at, now=now)


class TranscriptBuffer(EphemeralBuffer[TranscriptRecord]):
    def append_record(self, record: TranscriptRecord, *, now: float | None = None) -> None:
        self.append(record, timestamp=record.ended_at, now=now)
