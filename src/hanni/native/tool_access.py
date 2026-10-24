"""Owner-selected agent access, re-read at execution boundaries in every worker.

This restricts agent actions; direct application controls are still explicit
owner actions. It never enables a tool, expands its schema, or removes its jail.
"""
from __future__ import annotations

import json
from pathlib import Path
import threading
from uuid import uuid4

MODES = frozenset({'configured', 'read_only', 'ask', 'full'})
READ_TOOLS = frozenset({
    'local_read_file', 'local_read_document', 'local_list_dir', 'local_search_files',
    'system_info', 'web_search', 'web_fetch', 'skill_read', 'memory_search',
    'history_search', 'session_search', 'skill_propose', 'working_state', 'delegate_task',
})


def is_read(spec, arguments):
    if spec.get('target') == 'local':
        name = spec['name']
        return (name in READ_TOOLS
                or name == 'agent_job' and arguments.get('action', 'status') != 'cancel'
                or name == 'scheduled_tasks' and arguments.get('operation') == 'list')
    remote = spec.get('remote') or {}
    return (spec.get('target') == 'mcp' and remote.get('classification') == 'read_only'
            or spec.get('target') == 'windows' and remote.get('retry_read') is True)


class ToolAccess:
    def __init__(self, root):
        self.path = Path(root) / 'tool-access.json'
        self.lock = threading.RLock()

    def snapshot(self):
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
            if (not isinstance(value, dict) or set(value) != {'mode', 'revision'}
                    or not isinstance(value['mode'], str) or value['mode'] not in MODES
                    or not isinstance(value['revision'], str) or not value['revision']):
                raise ValueError('Invalid tool access settings.')
            return {**value, 'error': None}
        except FileNotFoundError:
            return {'mode': 'configured', 'revision': 'default', 'error': None}
        except (OSError, ValueError, UnicodeError):
            return {'mode': 'read_only', 'revision': 'unavailable',
                    'error': 'Tool access settings could not be read. Read-only access is enforced; save a mode to repair them.'}

    def save(self, mode, expected_revision):
        if not isinstance(mode, str) or mode not in MODES:
            raise ValueError('Choose read only, ask before writes, full access, or existing permissions.')
        with self.lock:
            if self.snapshot()['revision'] != expected_revision:
                raise ValueError('Tool access changed. Refresh settings before saving again.')
            from .model_settings import atomic_json
            value = {'mode': mode, 'revision': uuid4().hex}
            atomic_json(self.path, value)
            return {**value, 'error': None}

    def decision(self, spec, arguments):
        mode = self.snapshot()['mode']
        if mode == 'configured':
            return 'configured'
        read = is_read(spec, arguments)
        if mode == 'read_only' and not read:
            return 'blocked'
        return 'auto' if read or mode == 'full' else 'ask'


def denied_receipt():
    return {'ok': False, 'error': 'Read-only tool access blocks this action. Change Tool access in Settings to allow writes.',
            'error_code': 'tool_access_denied', 'effects': 'none', 'retryable': False}


def reconcile_action(store, action, *, auto=False):
    """Recheck waiting/captured actions, including a mode changed mid-task."""
    current = store.action(action['id'])
    if current['state'] in {'fulfilled', 'rejected', 'uncertain'}:
        return current
    decision = ToolAccess(store.path.parent).decision(current['spec'], current['arguments'])
    if decision == 'blocked':
        return store.settle(current['id'], 'rejected', denied_receipt())
    if auto and decision == 'auto' and current['state'] == 'pending':
        return store.settle(current['id'], 'dispatching')
    return current
