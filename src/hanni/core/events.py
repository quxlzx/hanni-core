"""Structured event schema (Master Spec §32; V1 plan §18).

Every event carries an ID, a type, a UTC timestamp, the component that emitted
it, and an optional correlation ID so a request can be traced through logs
across components. Payloads must be JSON-serializable.

Payloads must never contain raw audio, raw transcript windows, or screen frames.
Those are ephemeral two-minute buffers; events may reference them by ID only.
The event bus that routes these arrives with its first consumer (Milestone 1-2).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

SCHEMA_VERSION = 1


class EventType(str, Enum):
    """V1 plan §18, plus SYSTEM_ALERT (Master Spec §32) and EMERGENCY_STOP_CLEARED."""

    VOICE_ACTIVITY_STARTED = "VOICE_ACTIVITY_STARTED"
    VOICE_ACTIVITY_ENDED = "VOICE_ACTIVITY_ENDED"
    TRANSCRIPT_READY = "TRANSCRIPT_READY"
    OWNER_COMMAND = "OWNER_COMMAND"
    SCREEN_CHANGED = "SCREEN_CHANGED"
    ACTIVE_WINDOW_CHANGED = "ACTIVE_WINDOW_CHANGED"
    SYSTEM_ALERT = "SYSTEM_ALERT"
    MODEL_STARTED = "MODEL_STARTED"
    MODEL_FAILED = "MODEL_FAILED"
    TASK_CREATED = "TASK_CREATED"
    TASK_UPDATED = "TASK_UPDATED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TOOL_REQUESTED = "TOOL_REQUESTED"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    TOOL_FAILED = "TOOL_FAILED"
    MEMORY_CREATED = "MEMORY_CREATED"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    EMERGENCY_STOP_CLEARED = "EMERGENCY_STOP_CLEARED"  # not in the spec lists; added so resume is observable
    HANNI_STARTED = "HANNI_STARTED"
    HANNI_STOPPED = "HANNI_STOPPED"


class EventValidationError(ValueError):
    """Raised when an event or its serialized form is malformed."""


def new_event_id() -> str:
    return uuid.uuid4().hex


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Event:
    type: EventType
    source: str  # component that emitted the event, e.g. "core.shutdown" or "speech.stt"
    payload: Mapping[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=new_event_id)
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=utc_now)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.type, EventType):
            raise EventValidationError(f"type must be an EventType, got {type(self.type).__name__}")
        if not isinstance(self.source, str) or not self.source.strip():
            raise EventValidationError("source must be a non-empty component name")
        if not isinstance(self.event_id, str) or not self.event_id:
            raise EventValidationError("event_id must be a non-empty string")
        if self.correlation_id is not None and not isinstance(self.correlation_id, str):
            raise EventValidationError("correlation_id must be a string or None")
        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None:
            raise EventValidationError("timestamp must be a timezone-aware datetime")
        if not isinstance(self.payload, Mapping):
            raise EventValidationError("payload must be a mapping")
        if self.schema_version != SCHEMA_VERSION:
            raise EventValidationError(f"unsupported schema_version {self.schema_version!r}")
        try:
            json.dumps(self.payload)
        except (TypeError, ValueError) as exc:
            raise EventValidationError(f"payload is not JSON-serializable: {exc}") from exc
        # Freeze a private copy so later mutation of the caller's dict cannot alter the event.
        object.__setattr__(self, "payload", dict(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "correlation_id": self.correlation_id,
            "payload": dict(self.payload),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Event":
        if not isinstance(data, Mapping):
            raise EventValidationError("event must be a mapping")
        missing = [k for k in ("event_id", "type", "timestamp", "source") if k not in data]
        if missing:
            raise EventValidationError(f"event is missing required field(s): {', '.join(missing)}")
        try:
            event_type = EventType(data["type"])
        except ValueError as exc:
            raise EventValidationError(f"unknown event type {data['type']!r}") from exc
        raw_ts = data["timestamp"]
        try:
            timestamp = raw_ts if isinstance(raw_ts, datetime) else datetime.fromisoformat(str(raw_ts))
        except ValueError as exc:
            raise EventValidationError(f"invalid timestamp {raw_ts!r}") from exc
        return cls(
            type=event_type,
            source=data["source"],
            payload=data.get("payload") or {},
            event_id=data["event_id"],
            correlation_id=data.get("correlation_id"),
            timestamp=timestamp,
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        )

    @classmethod
    def from_json(cls, text: str) -> "Event":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise EventValidationError(f"invalid event JSON: {exc}") from exc
        return cls.from_dict(data)
