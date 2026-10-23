"""Deterministic emergency-stop state for H.A.N.N.I.

Master Spec §28 and V1 plan §13 require a stop path that does not depend on
any LLM. This module is that path's state machine:

* Anyone may trip the stop - stopping is always the safe direction (D-0005).
* Only the authenticated owner or the local machine may clear it.
* Tripping is idempotent and thread-safe; the first record is preserved.
* State is persisted, so a restart while stopped comes back up in Safe Mode
  instead of silently resuming automation. An unreadable state file fails safe.
* Listeners registered by later milestones (TTS cancel, task cancel, automation
  disable) run synchronously on trip/clear; a failing listener never prevents
  the stop from taking effect.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

from hanni.core.events import Event, EventType
from hanni.core.identity import Actor, local_machine_name
from hanni.core.state import RuntimeMode
from hanni.logs import get_logger

EMERGENCY_STOP_FILENAME = "emergency_stop.json"

log = get_logger("core.shutdown")


class StopSource(str, Enum):
    OWNER_VOICE = "owner-voice"  # "Hanni, stop everything." (voice milestones)
    OWNER_TEXT = "owner-text"  # typed into the local text conversation (M1+)
    LOCAL_HOTKEY = "local-hotkey"  # keyboard hotkey (V1 plan §13; later milestone)
    LOCAL_TERMINAL = "local-terminal"  # `hanni stop`
    INTERNAL = "internal"  # watchdog or safety subsystem
    PERSISTED = "persisted"  # restored from disk at startup


@dataclass(frozen=True, slots=True)
class StopRecord:
    tripped_at: datetime
    source: StopSource
    requested_by: str  # Actor label, e.g. "local-machine:LAPTOP"
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tripped_at": self.tripped_at.isoformat(),
            "source": self.source.value,
            "requested_by": self.requested_by,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "StopRecord":
        if not isinstance(data, dict):
            raise ValueError("stop record must be an object")
        tripped_at = datetime.fromisoformat(str(data["tripped_at"]))
        if tripped_at.tzinfo is None:
            raise ValueError("tripped_at must be timezone-aware")
        return cls(
            tripped_at=tripped_at,
            source=StopSource(data["source"]),
            requested_by=str(data["requested_by"]),
            reason=str(data.get("reason", "")),
        )

    def to_event(self, source: str = "core.shutdown", *, correlation_id: str | None = None) -> Event:
        return Event(EventType.EMERGENCY_STOP, source=source, payload=self.to_dict(), correlation_id=correlation_id)


class EmergencyStopActive(RuntimeError):
    """Raised by :meth:`EmergencyStop.guard` while the stop is tripped."""


class NotAuthorizedToClear(PermissionError):
    """Raised when an actor other than the owner or local machine tries to clear the stop."""


class StopStateStore(Protocol):
    def load(self) -> StopRecord | None: ...
    def save(self, record: StopRecord) -> None: ...
    def clear(self) -> None: ...


class MemoryStopStateStore:
    """In-memory store for tests and ephemeral contexts."""

    def __init__(self) -> None:
        self.record: StopRecord | None = None

    def load(self) -> StopRecord | None:
        return self.record

    def save(self, record: StopRecord) -> None:
        self.record = record

    def clear(self) -> None:
        self.record = None


class FileStopStateStore:
    """Persist the stop record as JSON in the data directory (atomic replace; fails safe on corruption)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def for_data_dir(cls, data_dir: Path) -> "FileStopStateStore":
        return cls(Path(data_dir) / EMERGENCY_STOP_FILENAME)

    def load(self) -> StopRecord | None:
        if not self.path.exists():
            return None
        try:
            return StopRecord.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.error("Unreadable emergency-stop state file; failing safe (treating as tripped)", extra={"path": str(self.path), "error": str(exc)})
            return StopRecord(
                tripped_at=datetime.now(timezone.utc),
                source=StopSource.PERSISTED,
                requested_by=Actor.internal("state-store").label,
                reason=f"unreadable state file {self.path.name}; failing safe",
            )

    def save(self, record: StopRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


Listener = Callable[[Literal["tripped", "cleared"], StopRecord | None], None]


class EmergencyStop:
    """Thread-safe emergency-stop state with persistence and listeners."""

    def __init__(self, store: StopStateStore | None = None, *, clock: Callable[[], datetime] | None = None) -> None:
        self._store = store or MemoryStopStateStore()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._listeners: list[Listener] = []
        self._record: StopRecord | None = self._store.load()
        if self._record is not None:
            log.warning("Starting in SAFE MODE: emergency stop is tripped", extra=self._record.to_dict())

    # ---- state -----------------------------------------------------------------------------

    def refresh(self) -> StopRecord | None:
        """Refresh emergency-stop state from the persisted cross-process store."""
        with self._lock:
            persisted = self._store.load()
            if persisted != self._record:
                self._record = persisted
            return self._record

    @property
    def is_tripped(self) -> bool:
        return self.refresh() is not None

    @property
    def record(self) -> StopRecord | None:
        return self.refresh()

    @property
    def mode(self) -> RuntimeMode:
        return RuntimeMode.SAFE_MODE if self.is_tripped else RuntimeMode.NORMAL

    def guard(self, action: str) -> None:
        """Raise if stopped, refreshing persisted state for cross-process control.

        H.A.N.N.I. V1 is a single-PC system, but the CLI emergency-stop command
        can run in a different process from the long-lived voice/tool loop. A
        persisted store is therefore re-read at every execution boundary so a
        terminal `hanni stop` takes effect before the next tool action.
        """
        with self._lock:
            persisted = self._store.load()
            if persisted != self._record:
                self._record = persisted
            record = self._record
        if record is not None:
            raise EmergencyStopActive(f"emergency stop active (tripped {record.tripped_at.isoformat()} via {record.source.value}); refusing: {action}")

    # ---- transitions -----------------------------------------------------------------------

    def trip(self, *, source: StopSource, requested_by: Actor, reason: str = "") -> StopRecord:
        """Enter Safe Mode. Idempotent: if already tripped, the original record is kept and returned."""
        with self._lock:
            if self._record is not None:
                log.info("Emergency stop already tripped; ignoring duplicate", extra={"duplicate_source": source.value, "duplicate_by": requested_by.label})
                return self._record
            record = StopRecord(tripped_at=self._clock(), source=source, requested_by=requested_by.label, reason=reason or "emergency stop")
            self._record = record
            self._store.save(record)
            listeners = list(self._listeners)
        log.critical("EMERGENCY STOP tripped", extra=record.to_dict())
        self._notify(listeners, "tripped", record)
        return record

    def clear(self, actor: Actor) -> None:
        """Leave Safe Mode. Only the owner or the local machine may do this."""
        if not actor.may_clear_emergency_stop:
            log.warning("Refused emergency-stop clear from unauthorized actor", extra={"actor": actor.label})
            raise NotAuthorizedToClear(f"{actor.label} may not clear the emergency stop")
        with self._lock:
            if self._record is None:
                return
            previous = self._record
            self._record = None
            self._store.clear()
            listeners = list(self._listeners)
        log.warning("Emergency stop cleared; resuming normal mode", extra={"cleared_by": actor.label, "was_tripped_at": previous.tripped_at.isoformat()})
        self._notify(listeners, "cleared", None)

    # ---- listeners -------------------------------------------------------------------------

    def add_listener(self, listener: Listener) -> None:
        with self._lock:
            self._listeners.append(listener)

    def remove_listener(self, listener: Listener) -> None:
        with self._lock:
            self._listeners = [l for l in self._listeners if l is not listener]

    @staticmethod
    def _notify(listeners: list[Listener], change: Literal["tripped", "cleared"], record: StopRecord | None) -> None:
        for listener in listeners:
            try:
                listener(change, record)
            except Exception:  # noqa: BLE001 - a broken listener must never block the stop
                log.exception("Emergency-stop listener failed", extra={"change": change})


class LocalStopControls:
    """Terminal-driven emergency stop for the machine this process runs on.

    Authorized by physical/OS access to the machine (Master Spec §28: "the owner
    must explicitly clear safe mode"; D-0005). Used by ``hanni stop|resume|status``;
    the long-running H.A.N.N.I. process (M1+) watches the same state file so a
    terminal stop takes effect immediately.
    """

    def __init__(self, data_dir: Path, *, machine_name: str | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.actor = Actor.local(machine_name or local_machine_name())
        self.stop = EmergencyStop(FileStopStateStore.for_data_dir(self.data_dir))

    def trip(self, reason: str = "terminal emergency stop") -> StopRecord:
        return self.stop.trip(source=StopSource.LOCAL_TERMINAL, requested_by=self.actor, reason=reason)

    def clear(self) -> None:
        self.stop.clear(self.actor)

    @property
    def record(self) -> StopRecord | None:
        return self.stop.record

    @property
    def mode(self) -> RuntimeMode:
        return self.stop.mode
