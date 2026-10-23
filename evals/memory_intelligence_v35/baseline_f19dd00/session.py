"""Owner-only memory boundary around the existing conversational/tool/agent stack."""

from __future__ import annotations

import re
import sqlite3
import time
from collections.abc import Callable, Iterator
from hanni.memory.facts import extract_fact, project_reference, key_text, absolute_path
from hanni.memory.retrieval import LocalMemoryRetriever
from hanni.memory.store import MemoryConflictError
from hanni.tools.base import ToolRequest, ToolError, ConfirmationRequired, ToolRegistry

from hanni.core.shutdown import EmergencyStop, EmergencyStopActive
from hanni.memory.privacy import SensitiveMemoryError
from hanni.memory.store import MemoryStore

_PREFIX = r"(?:(?:hanni|honey|ani|hani|hanny|hannie)[,\s]+)?"
_REMEMBER_RE = re.compile(rf"^{_PREFIX}remember(?:\s+that)?\s+(.+?)[.!?]*$", re.IGNORECASE)
_DELETE_ALL_RE = re.compile(rf"^{_PREFIX}(?:delete|forget)\s+(?:everything|all)(?:\s+(?:that\s+)?you\s+remember)?\s+about\s+(.+?)[.!?]*$", re.IGNORECASE)
_FORGET_RE = re.compile(rf"^{_PREFIX}forget(?:\s+that)?\s+(.+?)[.!?]*$", re.IGNORECASE)
_QUERY_RE = re.compile(rf"^{_PREFIX}(?:what\s+do\s+you\s+remember\s+about|show\s+(?:me\s+)?(?:my\s+)?memories\s+about)\s+(.+?)[?!.]*$", re.IGNORECASE)
_LIST_RE = re.compile(rf"^{_PREFIX}(?:what\s+do\s+you\s+remember|show\s+(?:me\s+)?(?:my\s+)?memories)[?!.]*$", re.IGNORECASE)


class MemoryAwareSession:
    """Extract only direct owner statements and supply relevant data to existing sessions."""

    def __init__(
        self,
        fallback_session,
        store: MemoryStore,
        *,
        source: str = "conversation",
        search_limit: int = 8,
        emergency_stop: EmergencyStop | None = None,
        registry: ToolRegistry | None = None,
        extraction_enabled: bool = True,
        retrieval_enabled: bool = True,
        max_context_chars: int = 4000,
        min_relevance_score: float = 25,
        clock: Callable[[], float] = time.monotonic,
        shadow_observer=None,
    ) -> None:
        self.fallback_session = fallback_session
        self.store = store
        self.source = source
        self.search_limit = search_limit
        self.emergency_stop = emergency_stop or (registry.context.emergency_stop if registry is not None else None)
        self.registry = registry
        self.extraction_enabled = extraction_enabled
        self.retrieval_enabled = retrieval_enabled
        self.retriever = LocalMemoryRetriever(store, limit=search_limit, max_chars=max_context_chars, min_score=min_relevance_score)
        self._clock = clock
        self._shadow_observer = shadow_observer
        self._pending_project: tuple[str, str, float] | None = None
        self._pending_folder_name: tuple[str, float] | None = None
        self._fingerprint = store.fingerprint()

    def _layers(self):
        layer, seen = self.fallback_session, set()
        while layer is not None and id(layer) not in seen:
            seen.add(id(layer))
            yield layer
            layer = getattr(layer, "fallback_session", None)

    def _invalidate(self) -> None:
        self._pending_project = None
        self._pending_folder_name = None
        for layer in self._layers():
            invalidate = getattr(layer, "invalidate_memory_context", None)
            if invalidate:
                invalidate()
            if hasattr(layer, "_pending_confirmation"):
                layer._pending_confirmation = None
        self._fingerprint = self.store.fingerprint()

    def _cancel_pending_actions(self) -> None:
        # An intercepted memory request changes the subject just as an ordinary
        # delegated request does. Never leave an old destructive confirmation live.
        for layer in self._layers():
            if hasattr(layer, "_pending_confirmation"):
                layer._pending_confirmation = None
            task = getattr(layer, "task", None)
            if task is not None and getattr(task.status, "value", "") == "waiting_confirmation":
                layer.loop.cancel(task, reason="owner changed subject to a memory request")

    def _active_workspace(self) -> str | None:
        for layer in self._layers():
            workspace = getattr(layer, "_active_workspace", None)
            if workspace:
                return str(workspace)
        return None

    def _open_project(self, alias: str, *, confirmed: bool = False, expected_id: str | None = None) -> str:
        records = self.store.by_key('project:' + alias)
        if not records:
            return f"I don't have a remembered location for your {alias} project. Tell me its full folder path."
        if len(records) != 1:
            return f"I have conflicting locations for {alias}. Use 'remember my {alias} project is FULL_PATH' to choose the current one."
        record = records[0]
        if expected_id is not None and record.id + record.updated_at.isoformat() + record.fact_value != expected_id:
            return "The project memory changed. Please ask to open it again."
        if self.registry is None:
            return f"I remember {record.fact_value}, but folder tools aren't available in this session."
        try:
            # Old/imported records get the same privacy gate as new facts.
            from hanni.memory.privacy import validate_memory_text
            validate_memory_text(record.content, max_chars=self.store.max_item_chars)
            observed = self.registry.execute(ToolRequest('file.stat', {'path': record.fact_value}, confirmed=confirmed, source='memory.project'))
            if not observed.ok or not observed.data.get('exists') or observed.data.get('type') != 'folder':
                return f"The remembered folder for {alias} isn't an existing directory. I didn't open anything. Tell me the new full path."
            result = self.registry.execute(ToolRequest('folder.open', {'path': record.fact_value}, confirmed=confirmed, source='memory.project'))
            return (f"Requested File Explorer for {record.fact_value}." if result.ok else f"I couldn't open that project: {result.message}")
        except ConfirmationRequired:
            self._pending_project = (alias, record.id + record.updated_at.isoformat() + record.fact_value, self._clock())
            return f"Opening {record.fact_value} requires your confirmation. Should I open that folder?"
        except EmergencyStopActive:
            return "Safe Mode is active, so I didn't open the project."
        except (ToolError, OSError, ValueError, RuntimeError) as exc:
            return f"I couldn't open that project safely: {exc}"


    def _guard_write(self) -> None:
        if self.emergency_stop is not None:
            self.emergency_stop.guard("durable memory mutation")

    def stream_response(self, prompt: str, **kwargs: object) -> Iterator[str]:
        clean = prompt.strip()
        if not clean:
            return

        # Observation only. This object has no memory writer and its result
        # must never affect retrieval, actions, permissions or responses.
        if self._shadow_observer is not None and not (self.emergency_stop and self.emergency_stop.is_tripped):
            try:
                self._shadow_observer.observe(clean)
            except Exception:
                pass

        try:
            if self.store.fingerprint() != self._fingerprint:
                self._invalidate()
        except (OSError, sqlite3.Error, RuntimeError):
            yield "Durable memory isn't available safely right now. Please retry after checking the local database."
            return

        pending, self._pending_project = self._pending_project, None
        if pending and re.fullmatch(r"(?:yes|confirm|go ahead|do it)[.!]?", clean, re.I):
            if self._clock() - pending[2] >= 120:
                yield "That folder confirmation expired. Please ask to open the project again."
            else:
                yield self._open_project(pending[0], confirmed=True, expected_id=pending[1])
            return

        folder_name, self._pending_folder_name = self._pending_folder_name, None
        if folder_name and self._clock() - folder_name[1] < 120 and absolute_path(clean.strip('"')):
            clean = f"Remember my {folder_name[0]} project is {clean.strip(chr(34))}"

        match = _REMEMBER_RE.match(clean)
        if match:
            content = match.group(1).strip(" .?!")
            this_folder = re.fullmatch(r"(?:this|the current) (?:folder|directory|workspace) is my ([\w .-]{1,60}?) project", content, re.I)
            if this_folder:
                workspace = self._active_workspace()
                if not workspace:
                    self._pending_folder_name = (key_text(this_folder[1]), self._clock())
                    self._cancel_pending_actions()
                    yield "What is the full path of that project folder? I don't have a verified current folder."
                    return
                content = f"my {this_folder[1]} project is {workspace}"
            self._cancel_pending_actions()
            try:
                self._guard_write()
                record, created = self.store.remember(content, source=f"owner_explicit:{self.source}", confidence=1.0)
            except EmergencyStopActive:
                yield "Safe Mode is active, so I didn't change durable memory."
                return
            except SensitiveMemoryError:
                yield "I won't store secrets or instructions that attempt to change runtime safety authority in durable memory."
                return
            except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
                yield f"I couldn't save that memory safely: {exc}"
                return
            self._invalidate()
            verb = "I'll remember" if created else "I updated that memory"
            yield f"{verb}: {record.content}."
            return

        match = _DELETE_ALL_RE.match(clean)
        if match:
            query = match.group(1).strip(" .?!")
            self._cancel_pending_actions()
            candidates = self.store.find_all(query)
            if not candidates:
                yield f"I don't have a durable memory matching {query}."
                return
            try:
                self._guard_write()
                deleted = len(self.store.forget(query, delete_all=True))
            except EmergencyStopActive:
                yield "Safe Mode is active, so I didn't change durable memory."
                return
            except (OSError, sqlite3.Error, RuntimeError) as exc:
                yield f"I couldn't delete those memories safely: {exc}"
                return
            self._invalidate()
            yield f"Deleted and verified {deleted} matching durable memor{'y' if deleted == 1 else 'ies'} about {query}."
            return

        match = _FORGET_RE.match(clean)
        if match:
            query = match.group(1).strip(" .?!")
            self._cancel_pending_actions()
            candidates = self.store.search(query, limit=max(2, self.search_limit))
            if not candidates:
                yield f"I don't have a durable memory matching {query}."
                return
            if len(candidates) > 1 and (candidates[0].score < 80.0 or abs(candidates[0].score - candidates[1].score) < 5.0):
                yield f"I found multiple memories matching {query}. Say 'delete everything you remember about {query}' if you want all of them removed."
                return
            try:
                self._guard_write()
                record = candidates[0].record
                if not self.store.delete(record.id):
                    yield "I couldn't verify that the memory was deleted."
                    return
            except EmergencyStopActive:
                yield "Safe Mode is active, so I didn't change durable memory."
                return
            except (OSError, sqlite3.Error, RuntimeError) as exc:
                yield f"I couldn't delete that memory safely: {exc}"
                return
            self._invalidate()
            yield f"Forgot and verified deletion of: {record.content}."
            return

        match = _QUERY_RE.match(clean)
        if match:
            query = match.group(1).strip(" .?!")
            self._cancel_pending_actions()
            results = self.store.search(query, limit=self.search_limit)
            if not results:
                yield f"I don't have a durable memory about {query}."
                return
            contents = [item.record.content for item in results[:4]]
            yield "I remember: " + "; ".join(contents) + "."
            return

        if _LIST_RE.match(clean):
            self._cancel_pending_actions()
            records = self.store.list(limit=self.search_limit)
            if not records:
                yield "I don't have any durable memories yet."
                return
            yield "My recent durable memories are: " + "; ".join(record.content for record in records) + "."
            return

        alias = project_reference(clean)
        if alias is not None and self.retrieval_enabled:
            self._cancel_pending_actions()
            # 'find/show' only locates; opening requires the owner's open verb.
            if not re.search(r"\bopen\b", clean, re.I):
                records = self.store.by_key('project:' + alias)
                if len(records) == 1:
                    yield f"The remembered location is {records[0].fact_value}; I haven't checked its current state."
                else:
                    yield "I don't have one unambiguous remembered project location. Tell me the full path."
            else:
                yield self._open_project(alias)
            return

        if self.extraction_enabled:
            try:
                owner_text = re.sub(r"^(?:hanni|honey|ani|hani|hanny|hannie)[,\s]+", "", clean, flags=re.I)
                fact = extract_fact(owner_text, max_chars=self.store.max_item_chars)
                if fact:
                    self._cancel_pending_actions()
                    self._guard_write()
                    record, created = self.store.remember(fact.content, source=f'owner_extracted:{self.source}',
                                                          confidence=fact.confidence, memory_type=fact.memory_type)
                    self._invalidate()
                    yield ("I saved this stable fact: " if created else "I already remember: ") + record.content + "."
                    return
            except MemoryConflictError:
                yield "That differs from a remembered fact. Say 'remember that ...' with the current value to replace it."
                return
            except EmergencyStopActive:
                yield "Safe Mode is active, so I didn't save that fact."
                return
            except (SensitiveMemoryError, ValueError):
                pass  # No automatic persistence of secrets, quotes or transient chat.
            except (OSError, sqlite3.Error, RuntimeError):
                yield "I couldn't save that fact safely. Please check the local memory database."
                return
        if self.retrieval_enabled:
            context = self.retriever.retrieve(clean)
            if context.text:
                kwargs['memory_context'] = context.text
        yield from self.fallback_session.stream_response(clean, **kwargs)
