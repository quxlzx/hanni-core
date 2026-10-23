"""Actor identity used by authorization decisions.

Authorization is always decided in code from verified identity, never from an
LLM's claim about who is asking (Master Spec §37). In V1 the owner is whoever
operates this laptop: the microphone, the terminal, and the future hotkey are
all owner-operated, and speaker identification is out of scope (V1 plan §22;
docs/DECISIONS.md D-0010). The Supervisor LLM and other subsystems act as
``internal`` actors with no authority to clear an emergency stop.
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class ActorKind(str, Enum):
    OWNER = "owner"  # the owner, as established by the interface in use (V1: every local interface)
    LOCAL_MACHINE = "local-machine"  # terminal, hotkey, or service on the machine itself
    INTERNAL = "internal"  # H.A.N.N.I. subsystems: the Supervisor LLM, watchdogs, health checks


@dataclass(frozen=True, slots=True)
class Actor:
    kind: ActorKind
    id: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ActorKind):
            raise TypeError(f"Actor.kind must be an ActorKind, got {type(self.kind).__name__}")
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Actor.id must be a non-empty string")

    @property
    def is_owner(self) -> bool:
        return self.kind is ActorKind.OWNER

    @property
    def may_clear_emergency_stop(self) -> bool:
        """Master Spec §28 / V1 plan §13 / D-0005: only the owner or the local machine may clear."""
        return self.kind in (ActorKind.OWNER, ActorKind.LOCAL_MACHINE)

    @property
    def label(self) -> str:
        """Stable ``kind:id`` string for audit records and logs."""
        return f"{self.kind.value}:{self.id}"

    @classmethod
    def owner(cls, owner_id: str = "owner") -> "Actor":
        """The owner acting through an interface, e.g. ``Actor.owner("voice")``."""
        return cls(ActorKind.OWNER, owner_id)

    @classmethod
    def local(cls, machine_name: str = "localhost") -> "Actor":
        return cls(ActorKind.LOCAL_MACHINE, machine_name)

    @classmethod
    def internal(cls, subsystem: str) -> "Actor":
        return cls(ActorKind.INTERNAL, subsystem)


def local_machine_name(env: Mapping[str, str] | None = None) -> str:
    """Label for this machine in logs and reports: ``HANNI_NODE_ID`` if set, else the hostname."""
    env = os.environ if env is None else env
    return (env.get("HANNI_NODE_ID") or "").strip() or platform.node() or "localhost"
