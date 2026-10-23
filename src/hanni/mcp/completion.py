"""Small observable ledger for requested clauses and action outcomes.

This is execution bookkeeping over the deterministic router's existing menu,
not a second planner or a source of new authority.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from hanni.tools.routing_intents import clauses, request_intent


@dataclass
class Subtask:
    request: str
    candidates: frozenset[str]
    kind: str = "read"
    status: str = "pending"
    last_error: str | None = None
    accepted_target: str | None = None
    last_message: str | None = None
    verification_status: str = 'UNVERIFIED'


def _kind(request: str, candidates: frozenset[str]) -> str:
    text = request.casefold()
    if "spotify.play_pause" in candidates and re.search(r"\b(?:play|resume|unpause)\b", text):
        return "spotify_play"
    if "spotify.play_pause" in candidates and re.search(r"\bpause\b", text):
        return "spotify_pause"
    if candidates & {'google_calendar.create', 'google.calendar.create'}:
        return "calendar_create"
    if "spotify.launch" in candidates and re.search(r"\b(?:open|launch|start|fire up)\b", text):
        return "app_open"
    if "app.open" in candidates and re.search(r"\b(?:open|launch|start|fire up)\b", text):
        return "app_open"
    return "read"


def _completes(task: Subtask, capability: str, result: dict) -> bool:
    if capability not in task.candidates or not result.get("ok"):
        return False
    data = result.get("data") or {}
    verification = result.get('verification')
    if verification and verification.get('status') == 'UNVERIFIED':
        return False
    if task.kind == "spotify_play":
        return ((capability == "spotify.play_pause" and data.get("playing") is True)
                or (capability == "spotify.status" and data.get("running") is True
                    and data.get("playing") is True))
    if task.kind == "spotify_pause":
        return capability == "spotify.play_pause" and data.get("playing") is False
    if task.kind == "calendar_create":
        return capability in {'google_calendar.create', 'google.calendar.create'} and data.get("created") is True
    if task.kind == "app_open":
        return ((capability == "app.open" and (data.get("verified") is True
                or data.get("outcome") in {"process_started", "window_detected", "window_focused"}))
                or (capability == "spotify.launch" and data.get("running") is True))
    return True


@dataclass
class CompletionLedger:
    subtasks: list[Subtask] = field(default_factory=list)

    @classmethod
    def from_request(cls, host, query: str, *, history=(), decision=None, now=None):
        parts = clauses(request_intent(query))
        decisions = ([decision] if len(parts) == 1 and decision is not None
                     else [host.route(part, history=history, now=now) for part in parts])
        tasks = []
        for part, routed in zip(parts, decisions):
            if routed.status != "tools" or not routed.tools:
                continue
            names = frozenset(tool.capability_id for tool in routed.tools)
            groups = routed.required_groups or (tuple(names),)
            for group in groups:
                candidates=frozenset(group)
                label=part
                if len(groups)>1:
                    definition=host.registry.get(group[0])
                    label=definition.display_name or definition.name.replace('.',' ').replace('_',' ').title()
                tasks.append(Subtask(label, candidates, _kind(part, candidates)))
        return cls(tasks)

    def observe(self, capability: str, result: dict) -> None:
        for task in self.subtasks:
            if task.status != "pending" or capability not in task.candidates:
                continue
            if result.get("ok"):
                task.last_message = str(result.get("message") or "").strip() or None
                task.verification_status = (result.get('verification') or {}).get('status', 'UNVERIFIED')
            if _completes(task, capability, result):
                task.status = "completed"
            elif (task.kind == "app_open" and capability == "app.open" and result.get("ok")
                  and (result.get("data") or {}).get("outcome") == "accepted"):
                task.status = "accepted"
                task.accepted_target = str((result.get("data") or {}).get("app") or "the app")
            elif not result.get("ok"):
                error = result.get("error") or {}
                task.last_error = str(error.get("code") or "EXECUTION_FAILED")
                if task.last_error in {"DEPENDENCY_MISSING", "AUTH_REQUIRED", "PERMISSION_BLOCKED",
                                       "PERMISSION_DENIED", "UNSUPPORTED", "NOT_FOUND"}:
                    task.status = "failed"

    @property
    def pending(self) -> list[Subtask]:
        return [task for task in self.subtasks if task.status == "pending"]

    @property
    def unresolved_actions(self) -> list[Subtask]:
        return [task for task in self.subtasks if task.kind != "read" and task.status not in {"completed", "accepted"}]

    @property
    def accepted_actions(self) -> list[Subtask]:
        return [task for task in self.subtasks if task.status == "accepted"]

    def reminder(self) -> str:
        return ("The following requested parts still lack successful tool evidence: "
                + "; ".join(task.request for task in self.pending)
                + ". Use exposed tools if available; otherwise say which part could not be verified. "
                "Do not claim an action completed from a launch or failed result alone.")

    def to_dict(self) -> list[dict]:
        return [{"request": task.request, "candidates": sorted(task.candidates),
                 "kind": task.kind, "status": task.status, "last_error": task.last_error,
                 "verification_status": task.verification_status}
                for task in self.subtasks]
