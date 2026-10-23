"""Opted, read-only context assembly for the original HANNI session.

No inference, tool execution, durable writes or automatic workflow resumption
occur here. Context is rebuilt from live records on every request.
"""
from __future__ import annotations

import re
import sqlite3
import time

from hanni.logs.redaction import secret_registry_revision
from hanni.memory.privacy import validate_memory_record
from hanni.memory.retrieval import ContextAwareRetriever, MemoryContext
from hanni.memory.store import MemorySearchResult


class ProjectSelectionRequired(ValueError):
    def __init__(self, candidates):
        self.candidates = tuple(dict(item) for item in candidates)
        names = ', '.join(str(item['name']) for item in self.candidates[:8])
        super().__init__('Which project should I continue: ' + names + '?')


def needs_project_context(goal: str) -> bool:
    """Only contextual requests can select a project or require clarification."""
    value = goal.casefold()
    return bool(re.search(r'\b(?:project|workspace|continue|resume|pick up)\b', value) or
                re.search(r'\bwhere\b.{0,30}\bleft off\b', value))


class PersonalContextProvider:
    def __init__(self, store, *, project_context=None, limit=8, max_chars=4000,
                 min_score=25, max_tokens=4000, advisory=None):
        self.store = store
        self.project_context = project_context
        self.limit, self.max_chars = limit, max_chars
        self.min_score, self.max_tokens, self.advisory = min_score, max_tokens, advisory
        # Validate the same bounded contract as the underlying retriever.
        self._retriever = ContextAwareRetriever(store, limit=limit, max_chars=max_chars,
                                               min_score=min_score, max_tokens=max_tokens,
                                               advisory=advisory)
        self.last_metrics = {}

    def invalidate(self):
        if self.advisory is not None:
            self.advisory.invalidate()
        self.last_metrics = {}

    def retrieve(self, goal: str) -> MemoryContext:
        started = time.perf_counter()
        privacy_revision = secret_registry_revision()
        project_text = ''
        project_id = None
        project_matches = []
        if self.project_context is not None and needs_project_context(goal):
            resolution = self.project_context.resolve(goal)
            if resolution['status'] == 'ambiguous':
                raise ProjectSelectionRequired(resolution['candidates'])
            if resolution['status'] == 'matched':
                project_id = resolution['project_id']
                package = self.project_context.package(project_id, max_chars=min(12000, self.max_chars),
                                                       max_records=self.limit)
                stale_markers = set()
                current_matches = {}
                for row in package.get('memories', ()):
                    marker = '[' + row['id'] + '; ' + row['source'] + ']:'
                    current = self.store.get(row['id'])
                    try:
                        if current is None or current.to_dict() != row:
                            raise ValueError('Project memory changed')
                        validate_memory_record(current, max_chars=self.store.max_item_chars)
                    except ValueError:
                        stale_markers.add(marker)
                    else:
                        current_matches[marker] = current
                # Keep whole source lines. Never truncate a fact, receipt or ID.
                lines = []
                source_lines = [line for line in package['context_text'].splitlines()
                                if not any(marker in line for marker in stale_markers)]
                if stale_markers:
                    source_lines.append('Uncertainty: A project memory changed or became unavailable; its earlier text was withheld.')
                for line in source_lines:
                    candidate = '\n'.join(lines + [line])
                    if len(candidate) <= self.max_chars and len(candidate.encode('utf-8')) <= self.max_tokens:
                        lines.append(line)
                project_text = '\n'.join(lines)
                for marker, current in current_matches.items():
                    if marker in project_text:
                        # A project association selects a record without claiming
                        # a numeric model relevance score or calibrated confidence.
                        project_matches.append(MemorySearchResult(current, 0.0))
                if secret_registry_revision() != privacy_revision:
                    project_text, project_matches = '', []

        # Both sources share ONE total budget. A project package already includes
        # project memories; any remaining recall is limited to distinct records.
        room_chars = self.max_chars - len(project_text) - (2 if project_text else 0)
        room_tokens = self.max_tokens - len(project_text.encode('utf-8')) - (2 if project_text else 0)
        recalled = MemoryContext('', ())
        remaining_count = self.limit - len(project_matches)
        if room_chars >= 512 and room_tokens >= 128 and remaining_count > 0:
            if not project_text:
                recalled = self._retriever.retrieve(goal)
            else:
                recalled = ContextAwareRetriever(self.store, limit=remaining_count, max_chars=room_chars,
                    min_score=self.min_score, max_tokens=room_tokens, advisory=self.advisory).retrieve(
                        goal, exclude_ids=tuple(match.record.id for match in project_matches))
        text = '\n\n'.join(part for part in (project_text, recalled.text) if part)
        matches = tuple(project_matches) + recalled.matches
        if secret_registry_revision() != privacy_revision:
            text, matches = '', ()
        self.last_metrics = {'context_chars': len(text), 'utf8_token_upper_bound': len(text.encode('utf-8')),
                             'project_id': project_id,
                             'construction_ms': round((time.perf_counter() - started) * 1000, 3),
                             'token_measurement': 'conservative byte bound; not tokenizer measurement'}
        return MemoryContext(text, matches)


def configured_retriever(config, store=None, *, emergency_stop=None):
    """Legacy retrieval remains default; enhanced context needs explicit opt-in."""
    from hanni.memory.retrieval import LocalMemoryRetriever
    from hanni.memory.store import MemoryStore
    settings = config.hanni.memory
    store = store if store is not None else MemoryStore(config.paths.data_dir / settings.database_file,
                                                       max_item_chars=settings.max_item_chars)
    options = dict(limit=settings.search_limit, max_chars=settings.max_context_chars,
                   min_score=settings.min_relevance_score)
    from hanni.laya.runtime import advisory_for_config
    guard = (lambda: not emergency_stop.is_tripped) if emergency_stop is not None else None
    advisory = advisory_for_config(config, admission_guard=guard)
    ranker = advisory if advisory.retrieval_enabled else None
    if not getattr(settings, 'context_enabled', False):
        return LocalMemoryRetriever(store, max_tokens=settings.max_context_tokens, **options)
    from hanni.memory.projects import ProjectContext
    from hanni.mcp.runtime import workflow_hub
    hub = workflow_hub(config)
    try:
        projects = ProjectContext.from_config(config, workflow_reader=hub.detail if hub else None)
    except (OSError, sqlite3.Error, ValueError, RuntimeError):
        # An unavailable optional project view cannot prevent memory/chat startup.
        return ContextAwareRetriever(store, max_tokens=settings.max_context_tokens, advisory=ranker, **options)
    from hanni.memory.grounded import GroundedPersonalContext
    return GroundedPersonalContext(PersonalContextProvider(store, project_context=projects,
                                   max_tokens=settings.max_context_tokens, advisory=ranker, **options),
                                   max_bytes=settings.max_context_tokens)
