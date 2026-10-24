"""Fixed desktop adapters; tool policy stays with the existing ToolRegistry.

No generic execution endpoint, alternate model router, capture or credential API.
Personal-data projections are served only after the dashboard token check.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid

from hanni.dashboard.gateway import activity_snapshot, safe_value
from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult


PRODUCTIVITY_OPERATIONS = frozenset({
    'task.create', 'task.update', 'task.delete', 'project.create', 'project.update',
    'project.delete', 'note.create', 'note.update', 'note.delete', 'link.create',
    'link.delete', 'workspace.backup',
})
NOTIFICATION_OPERATIONS = frozenset({
    'notification.read', 'notification.dismiss', 'notification.clear',
    'notification.preferences',
})


def request_id(value):
    if not isinstance(value, str):
        raise ValueError('A UUID request ID is required.')
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise ValueError('A UUID request ID is required.') from None


class RequestLedger:
    """Bounded, payload-bound in-session deduplication for fixed control actions."""
    def __init__(self):
        self.lock = threading.RLock()
        self.results = OrderedDict()

    def execute(self, key, payload, action):
        key = request_id(key)
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        with self.lock:
            if key in self.results:
                old_digest, result = self.results[key]
                if old_digest != digest:
                    raise ValueError('This request ID was already used for a different action.')
                return result
            result = action()
            self.results[key] = (digest, result)
            while len(self.results) > 1024:
                self.results.popitem(last=False)
            return result


class DesktopFeatures:
    def __init__(self, config, *, registry=None, store=None):
        self.config = config
        self.root = Path(config.paths.data_dir).resolve() if config else None
        self._registry = registry
        self._store = store
        self._lock = threading.RLock()
        self.ledger = RequestLedger()
        self._observed = {}
        self._alerted_at = {}
        from hanni.dashboard.memory import MemoryExplorer
        self.memory_explorer = MemoryExplorer(self)

    def require(self):
        if self.config is None:
            raise RuntimeError('Local workspace configuration is unavailable in this session.')

    @property
    def store(self):
        self.require()
        with self._lock:
            if self._store is None:
                from hanni.dashboard.productivity import ProductivityStore
                self._store = ProductivityStore(self.root)
            return self._store

    @property
    def registry(self):
        self.require()
        with self._lock:
            if self._registry is None:
                from hanni.tools.registry import build_default_registry
                self._registry = build_default_registry(self.config)
            return self._registry

    def _execute(self, name, payload, *, destructive=False, confirmed=False):
        registry = self.registry
        with self._lock:
            if name not in {item.name for item in registry.definitions()}:
                def run(arguments, context, request):
                    # The registered handler's source is fixed by this adapter.
                    data = self._fixed_handler(name, arguments['payload'])
                    return ToolResult(name, True, 'Local workspace action completed.', {'result': data})
                registry.register(ToolDefinition(name, 'Explicit local desktop record action.',
                    2, 3 if destructive else 2, {'payload': dict}, {'result': 'object'},
                    run, side_effect='destructive' if destructive else 'reversible_write',
                    background_allowed=False))
        from hanni.reliability.context import request_scope
        with request_scope(payload['id'], 'dashboard'):
            result = registry.execute(ToolRequest(name, {'payload': payload},
                confirmed=confirmed, source='desktop-workspace', correlation_id=payload['id']))
        return result.data['result']

    def _fixed_handler(self, name, payload):
        if name.startswith('memory.desktop_'):
            return self.memory_explorer.handle(name.removeprefix('memory.desktop_'), payload['data'], request_id=payload['id'])
        operation = name.removeprefix('workspace.')
        if operation in PRODUCTIVITY_OPERATIONS:
            if operation == 'workspace.backup':
                if payload['data']:
                    raise ValueError('Backup accepts no paths or arguments.')
                return self.store.backup()
            return self.store.mutate(operation, payload['data'], payload['id'])
        if operation in NOTIFICATION_OPERATIONS:
            return self.store.notification_mutate(operation, payload['data'], payload['id'])
        raise ValueError('Unsupported desktop operation.')

    def mutate(self, area, body):
        if area == 'memory':
            return self.memory_explorer.mutate(body)
        self.require()
        if set(body) != {'id', 'operation', 'data', 'confirmed'}:
            raise ValueError('Expected request ID, operation, data and explicit confirmation.')
        if body['confirmed'] is not True or not isinstance(body['data'], dict):
            raise ValueError('Confirm the displayed local record change before applying it.')
        key = request_id(body['id'])
        allowed = PRODUCTIVITY_OPERATIONS if area == 'productivity' else NOTIFICATION_OPERATIONS
        if not isinstance(body['operation'], str) or body['operation'] not in allowed:
            raise ValueError('Unsupported desktop operation.')
        operation = body['operation']
        name = 'workspace.' + operation
        payload = {'id': key, 'data': body['data']}
        return self.ledger.execute(key, body, lambda: self._execute(name, payload,
            destructive=operation.endswith('.delete'), confirmed=True))

    def productivity(self):
        if not self.config:
            return {'available': False, 'tasks': [], 'projects': [], 'notes': [], 'links': [],
                    'reason': 'Local workspace configuration is unavailable.'}
        return self.store.snapshot()

    def memory_store(self):
        self.require()
        settings = self.config.hanni.memory
        if not settings.enabled:
            raise RuntimeError('Durable memory is disabled in HANNI configuration.')
        from hanni.memory.store import MemoryStore
        path = self.root / settings.database_file
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise RuntimeError('Memory storage is outside the authorized data directory.')
        return MemoryStore(path, max_item_chars=settings.max_item_chars)

    def memories(self, query=''):
        if not isinstance(query, str) or len(query) > 500:
            raise ValueError('Use a search query of at most 500 characters.')
        try:
            store = self.memory_store()
        except RuntimeError as exc:
            return {'available': False, 'records': [], 'reason': str(exc)}
        records = [item.record for item in store.search(query, limit=100)] if query.strip() else store.list(limit=100)
        from hanni.memory.privacy import validate_memory_text
        rows = []
        for record in records:
            try:
                validate_memory_text(record.content, max_chars=store.max_item_chars)
            except ValueError:
                continue
            rows.append(safe_value(record.to_dict()))
        return {'available': True, 'records': rows, 'count': store.count(),
                'limit': 100, 'reason': None, 'source': 'stored-memory'}

    def calendar(self, query):
        self.require()
        start = query.get('start_date', date.today().isoformat())
        if date.fromisoformat(start).isoformat() != start:
            raise ValueError('Choose a valid date.')
        days = int(query.get('days', '7'))
        if days not in {1, 7}:
            raise ValueError('Choose a daily or weekly calendar.')
        refresh = query.get('refresh', '0')
        if refresh not in {'0', '1'}:
            raise ValueError('Invalid refresh choice.')
        key = f'{start}:{days}'
        stored = self.store.get_calendar_cache(key)
        cached = stored['payload'] if stored else None
        access = self.registry.google_access
        accounts = safe_value(access.accounts())
        connected = any(row['connected'] for row in accounts)
        result = {'available': connected, 'connected': connected, 'accounts': accounts,
                  'events': cached.get('events', []) if cached else [],
                  'cached_at': cached.get('cached_at') if cached else None,
                  'stale': bool(cached), 'start_date': start, 'days': days,
                  'reason': 'Select Refresh to read authorized calendar events.' if connected else
                            'No connected Google Calendar account. Existing local tasks remain available.'}
        if refresh == '1' and connected:
            response = self.registry.execute(ToolRequest('google_calendar.agenda',
                {'start_date': start, 'days': days, 'limit': 100}, source='desktop-calendar'))
            if response.ok and not response.data.get('errors') and not response.data.get('truncated'):
                events = []
                for event in response.data.get('events', [])[:100]:
                    beginning, ending = event.get('start', {}), event.get('end', {})
                    events.append(safe_value({'id': event.get('id'),
                        'title': event.get('summary') or 'Untitled event',
                        'start': beginning.get('date') or event.get('start_local') or beginning.get('dateTime'),
                        'end': ending.get('date') or ending.get('dateTime'),
                        'all_day': bool(event.get('all_day')), 'calendar': event.get('calendar_id'),
                        'account': event.get('account')}))
                stamp = datetime.now(timezone.utc).isoformat()
                self.store.save_calendar_cache(key, {'events': events, 'cached_at': stamp})
                result.update(events=events, cached_at=stamp, stale=False, reason=None)
            else:
                result.update(reason='Calendar refresh failed or was incomplete. Cached entries may be out of date.',
                              errors=safe_value(response.data.get('errors', [])))
        return result

    def agents(self, chat, contract):
        observed = activity_snapshot(self.root)
        active = []
        seen = set()
        for message in chat['messages']:
            if message['status'] in {'working', 'queued'} and message['turn'] not in seen:
                seen.add(message['turn'])
                active.append({'id': message['turn'], 'status': message['status'],
                               'started_at': message['created'], 'source': 'conversation'})
        return {'available': bool(self.config),
                'agents': [{'id': 'hanni-controller', 'name': 'HANNI', 'kind': 'controller',
                    'status': 'busy' if chat['busy'] else 'ready' if chat['ready'] else 'unavailable',
                    'model': contract['models'][0]['id'] if contract['models'] else None,
                    'capability_count': len(contract['capabilities'])}],
                'capabilities': contract['capabilities'], 'active_tasks': active,
                'executions': observed['events'], 'awaiting_approvals': [],
                'approvals_available': False, 'cancellation_supported': False,
                'reason': 'Observable conversation controller and tool audit. Persistent workflow execution and approvals are inspected in Workflows.',
                'sampled_at': time.time()}

    def awareness(self):
        retention = self.config.privacy.retention.screen_frames_seconds if self.config else None
        return {'available': False, 'capture_active': False, 'enabled': False,
                'context_available': False, 'expires_at': None, 'retention_seconds': retention,
                'reason': 'No background screen capture is active. Use /screen for one explicit capture and local text recognition.',
                'actions': {'enable': False, 'disable': False, 'analyze': False}}

    def notifications(self, *, telemetry, cluster, contract):
        with self._lock:
            return self._notifications(telemetry=telemetry, cluster=cluster, contract=contract)

    def _notifications(self, *, telemetry, cluster, contract):
        self.require()
        entries = []
        from hanni.dashboard.task_notifications import collect
        entries.extend(collect(self.store, self.root))
        now = datetime.now(timezone.utc).isoformat()
        for event in activity_snapshot(self.root)['events']:
            if event['tool'].startswith('workspace.notification.'):
                continue  # Reading/dismissing notifications must never notify itself.
            raw_key = f"{event['timestamp']}:{event['tool']}:{event['status']}"
            category = 'tasks' if event['tool'].startswith(('todo.', 'workspace.task.')) else 'agents'
            entries.append({'key': 'audit:' + hashlib.sha256(raw_key.encode()).hexdigest(),
                'category': category, 'priority': 'critical' if event['status'] == 'failed' else 'informational',
                'title': f"{event['tool']} {'failed' if event['status'] == 'failed' else 'completed'}",
                'message': event['error'] or event['summary'] or 'Recorded tool execution.',
                'target': {'screen': 'activity', 'id': raw_key},
                'created_at': event['timestamp'] or now})
        if telemetry.get('sampled_at') and isinstance(telemetry.get('model_status'), str):
            model = telemetry.get('model_status')
            previous = self._observed.get('model')
            failed = model in {'unavailable', 'unhealthy', 'unreachable', 'error', 'failed'}
            changed = (previous is not None and model != previous) or (previous is None and failed)
            cooled_down = time.monotonic() - self._alerted_at.get('model', float('-inf')) > 60
            if changed and (not failed or cooled_down):
                if failed:
                    self._alerted_at['model'] = time.monotonic()
                entries.append({'key': f'model:{time.time_ns()}', 'category': 'models',
                    'priority': 'critical' if failed else 'informational',
                    'title': 'Model status changed', 'message': str(model), 'target': {'screen': 'models'}})
            self._observed['model'] = model
        for node in cluster.get('nodes', []):
            if node.get('maintenance'):
                continue
            status = node.get('status')
            previous = self._observed.get('node:' + node['id'])
            alert_key = 'node:' + node['id']
            if (previous is not None and previous != status and status in {'offline', 'unreachable'}
                    and time.monotonic() - self._alerted_at.get(alert_key, float('-inf')) > 60):
                self._alerted_at[alert_key] = time.monotonic()
                entries.append({'key': f"node:{node['id']}:{time.time_ns()}",
                    'category': 'cluster', 'priority': 'critical', 'title': f"{node['name']} disconnected",
                    'message': node.get('message') or 'No current connection.',
                    'target': {'screen': 'cluster', 'id': node['id']}})
            self._observed['node:' + node['id']] = status
        # Due reminders are local observations, never new autonomous tool actions.
        for task in self.store.snapshot().get('tasks', []):
            due = task.get('due')
            if due and task.get('status') == 'open' and due[:10] <= date.today().isoformat():
                entries.append({'key': 'due:' + task['id'] + ':' + due, 'category': 'reminders',
                    'priority': 'action_required', 'title': 'Task due', 'message': task['title'],
                    'target': {'screen': 'tasks', 'id': task['id']}})
        with self._lock:
            for offset in range(0, len(entries), 100):
                self.store.ingest(entries[offset:offset + 100])
            return self.store.notifications()
