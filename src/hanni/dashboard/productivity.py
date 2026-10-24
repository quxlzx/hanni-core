"""Explicit local workspace records beside the existing TodoStore task table.

The HTTP adapter must invoke mutations through HANNI's authoritative registry.
This module owns persistence only, never tool execution or permission decisions.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PureWindowsPath
import sqlite3
import threading
import time
from uuid import UUID, uuid4

from hanni.dashboard.gateway import safe_value
from hanni.memory.privacy import validate_memory_text
from hanni.tools.todos import TodoStore
from hanni.tools.whenparse import parse_when

SCHEMA_VERSION = 2
CATEGORIES = ('approvals', 'tasks', 'agents', 'cluster', 'models', 'reminders', 'application')


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def _text(value, maximum, *, optional=False):
    if not isinstance(value, str):
        raise ValueError('Text fields must be strings.')
    return '' if optional and not value.strip() else validate_memory_text(value, max_chars=maximum)


def _body(value, maximum):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f'Body must be text of at most {maximum} characters.')
    if value.strip():
        validate_memory_text(value, max_chars=maximum)
    return value.strip()


class ProductivityStore:
    def __init__(self, data_dir):
        self.root = Path(data_dir).resolve()
        self.path = self.root / 'todos.sqlite3'
        self._lock = threading.RLock()
        if self.path.is_symlink() or not self.path.resolve().is_relative_to(self.root):
            raise ValueError('Workspace database must stay inside the configured data directory.')
        existed = self.path.exists()
        version = 0
        if existed:
            with self.connect() as db:
                table = db.execute("SELECT name FROM sqlite_master WHERE name='workspace_meta'").fetchone()
                row = db.execute("SELECT value FROM workspace_meta WHERE key='schema_version'").fetchone() if table else None
                version = int(row['value']) if row else 0
        if version not in {0, 1, SCHEMA_VERSION}:
            raise RuntimeError(f'Unsupported workspace schema {version}; database left unchanged.')
        with TodoStore(self.root).connect():
            pass
        if version == 0:
            if existed:
                self.backup()
            with self.connect() as db:
                db.executescript('''BEGIN IMMEDIATE;
                    CREATE TABLE IF NOT EXISTS workspace_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS workspace_projects (
                        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS workspace_task_meta (
                        task_id TEXT PRIMARY KEY REFERENCES todos(id) ON DELETE CASCADE,
                        priority TEXT NOT NULL, project_id TEXT REFERENCES workspace_projects(id) ON DELETE SET NULL);
                    CREATE TABLE IF NOT EXISTS workspace_notes (
                        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES workspace_projects(id) ON DELETE CASCADE,
                        title TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS workspace_links (
                        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES workspace_projects(id) ON DELETE CASCADE,
                        label TEXT NOT NULL, target TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS workspace_requests (
                        id TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS workspace_notifications (
                        id TEXT PRIMARY KEY, key TEXT UNIQUE NOT NULL, category TEXT NOT NULL, priority TEXT NOT NULL,
                        title TEXT NOT NULL, message TEXT NOT NULL, target TEXT NOT NULL, created_at TEXT NOT NULL,
                        ingested_at REAL NOT NULL, read INTEGER NOT NULL DEFAULT 0, dismissed INTEGER NOT NULL DEFAULT 0);
                    CREATE TABLE IF NOT EXISTS workspace_notification_seen (key TEXT PRIMARY KEY);
                    CREATE TABLE IF NOT EXISTS workspace_preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS workspace_cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, saved_at TEXT NOT NULL);
                    INSERT OR REPLACE INTO workspace_meta VALUES ('schema_version','2');
                    COMMIT;''')
        elif version == 1:
            self.backup()
            with self.connect() as db:
                db.execute('CREATE TABLE IF NOT EXISTS workspace_cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, saved_at TEXT NOT NULL)')
                db.execute("UPDATE workspace_meta SET value='2' WHERE key='schema_version'")

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA secure_delete=ON')
            db.execute('PRAGMA busy_timeout=5000')
            yield db

    @staticmethod
    def _task(db, task_id):
        row = db.execute('''SELECT t.*, COALESCE(m.priority,'normal') AS priority, m.project_id
                            FROM todos t LEFT JOIN workspace_task_meta m ON m.task_id=t.id WHERE t.id=?''', (task_id,)).fetchone()
        if row is None:
            raise ValueError('Task not found. Refresh the workspace.')
        result = dict(row)
        result['all_day'] = bool(result['all_day'])
        result['fingerprint'] = _digest(result)
        return result

    @staticmethod
    def _record(db, table, item_id):
        row = db.execute(f'SELECT * FROM {table} WHERE id=?', (item_id,)).fetchone()
        if row is None:
            raise ValueError('Record not found. Refresh the workspace.')
        result = dict(row)
        result['fingerprint'] = _digest(result)
        return result

    @staticmethod
    def _check(record, data):
        if not isinstance(data.get('expected_fingerprint'), str) or record['fingerprint'] != data['expected_fingerprint']:
            raise ValueError('This record changed in another session. Refresh before editing it.')

    def snapshot(self):
        with self.connect() as db:
            tasks = [self._task(db, row['id']) for row in db.execute('SELECT id FROM todos ORDER BY status,due,id LIMIT 2000').fetchall()]
            projects = [self._record(db, 'workspace_projects', row['id']) for row in db.execute('SELECT id FROM workspace_projects ORDER BY name,id LIMIT 250').fetchall()]
            notes = [self._record(db, 'workspace_notes', row['id']) for row in db.execute('SELECT id FROM workspace_notes ORDER BY updated_at DESC LIMIT 2000').fetchall()]
            links = [dict(row) for row in db.execute('SELECT * FROM workspace_links ORDER BY created_at DESC LIMIT 1000')]
        return {'available': True, 'schema_version': SCHEMA_VERSION, 'tasks': tasks, 'projects': projects,
                'notes': notes, 'links': links, 'reason': None}

    def _request(self, db, operation, data, request_id, callback):
        try:
            request_id = str(UUID(request_id))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('A valid request UUID is required.') from None
        payload_hash = _digest([operation, data])
        old = db.execute('SELECT * FROM workspace_requests WHERE id=?', (request_id,)).fetchone()
        if old:
            if old['payload_hash'] != payload_hash:
                raise ValueError('This request UUID is already bound to different data.')
            return json.loads(old['result'])
        if db.execute('SELECT count(*) FROM workspace_requests').fetchone()[0] >= 50000:
            raise ValueError('Workspace request ledger is full; back up the workspace before maintenance.')
        result = callback()
        db.execute('INSERT INTO workspace_requests VALUES (?,?,?,?)', (request_id, payload_hash, json.dumps(result), _stamp()))
        return result

    def mutate(self, operation, data, request_id):
        if not isinstance(data, dict):
            raise ValueError('Workspace data must be an object.')
        with self._lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            return self._request(db, operation, data, request_id, lambda: self._mutate(db, operation, data))

    def _mutate(self, db, operation, data):
        specs = {
            'task.create': {'title', 'course', 'due', 'priority', 'project_id'},
            'task.update': {'task_id', 'expected_fingerprint', 'title', 'course', 'due', 'priority', 'project_id', 'status'},
            'task.delete': {'task_id', 'expected_fingerprint'},
            'project.create': {'name', 'description'},
            'project.update': {'project_id', 'expected_fingerprint', 'name', 'description'},
            'project.delete': {'project_id', 'expected_fingerprint'},
            'note.create': {'project_id', 'title', 'body'},
            'note.update': {'note_id', 'expected_fingerprint', 'title', 'body'},
            'note.delete': {'note_id', 'expected_fingerprint'},
            'link.create': {'project_id', 'label', 'target', 'kind'},
            'link.delete': {'link_id'}, 'workspace.backup': set(),
        }
        if not isinstance(operation, str) or operation not in specs or set(data) - specs[operation]:
            raise ValueError('Unknown workspace operation or fields.')
        now = _stamp()
        if operation == 'workspace.backup':
            return {'operation': operation, **self.backup()}
        if operation.startswith('task.'):
            old = None
            if operation != 'task.create':
                old = self._task(db, data.get('task_id'))
                self._check(old, data)
            if operation == 'task.delete':
                db.execute('DELETE FROM todos WHERE id=?', (old['id'],))
                return {'operation': operation, 'deleted_id': old['id']}
            title = _text(data.get('title'), 300)
            course = _text(data.get('course', ''), 120, optional=True)
            priority = data.get('priority', 'normal')
            if not isinstance(priority, str) or priority not in {'low', 'normal', 'high'}:
                raise ValueError('Priority must be low, normal or high.')
            project_id = data.get('project_id') or None
            if project_id is not None and not isinstance(project_id, str):
                raise ValueError('Project ID must be a string or null.')
            if project_id:
                self._record(db, 'workspace_projects', project_id)
            raw_due = data.get('due')
            due, all_day = '', True
            if raw_due is not None and raw_due != '':
                if not isinstance(raw_due, str):
                    raise ValueError('Due date must be an ISO date or date-time.')
                try:
                    datetime.fromisoformat(raw_due)
                except ValueError:
                    raise ValueError('Due date must be an ISO date or date-time.') from None
                parsed = parse_when(raw_due, default_minutes=0)
                due, all_day = parsed.start.isoformat(), parsed.all_day
            key = hashlib.sha256(json.dumps([title.casefold(), course.casefold(), due, all_day]).encode()).hexdigest()
            status = 'open' if old is None else data.get('status')
            if not isinstance(status, str) or status not in {'open', 'completed'}:
                raise ValueError('Task status must be open or completed.')
            duplicate = db.execute('SELECT id FROM todos WHERE request_key=?', (key,)).fetchone()
            if duplicate and (old is None or old['id'] != duplicate['id']):
                raise ValueError('An identical task already exists. Edit or reuse that task.')
            item_id = old['id'] if old else uuid4().hex
            if old:
                db.execute('UPDATE todos SET request_key=?,title=?,course=?,due=?,all_day=?,status=? WHERE id=?', (key, title, course, due, int(all_day), status, item_id))
            else:
                if db.execute('SELECT count(*) FROM todos').fetchone()[0] >= 2000:
                    raise ValueError('Workspace supports at most 2000 tasks.')
                db.execute('INSERT INTO todos VALUES (?,?,?,?,?,?,?,?)', (item_id, key, title, course, due, int(all_day), status, now))
            db.execute('INSERT OR REPLACE INTO workspace_task_meta VALUES (?,?,?)', (item_id, priority, project_id))
            return {'operation': operation, 'task': self._task(db, item_id)}
        if operation.startswith(('project.', 'note.')):
            is_project = operation.startswith('project.')
            table = 'workspace_projects' if is_project else 'workspace_notes'
            field = 'project_id' if is_project else 'note_id'
            old = None
            if not operation.endswith('.create'):
                old = self._record(db, table, data.get(field))
                self._check(old, data)
            if operation.endswith('.delete'):
                db.execute(f'DELETE FROM {table} WHERE id=?', (old['id'],))
                return {'operation': operation, 'deleted_id': old['id']}
            title = _text(data.get('name') if is_project else data.get('title'), 200)
            body = _body(data.get('description', '') if is_project else data.get('body', ''), 4000)
            item_id = old['id'] if old else uuid4().hex
            if old:
                db.execute(f'UPDATE {table} SET {"name" if is_project else "title"}=?, {"description" if is_project else "body"}=?, updated_at=? WHERE id=?', (title, body, now, item_id))
            elif is_project:
                if db.execute('SELECT count(*) FROM workspace_projects').fetchone()[0] >= 250:
                    raise ValueError('Workspace supports at most 250 projects.')
                db.execute('INSERT INTO workspace_projects VALUES (?,?,?,?,?)', (item_id, title, body, now, now))
            else:
                self._record(db, 'workspace_projects', data.get('project_id'))
                if db.execute('SELECT count(*) FROM workspace_notes').fetchone()[0] >= 2000:
                    raise ValueError('Workspace supports at most 2000 project notes.')
                db.execute('INSERT INTO workspace_notes VALUES (?,?,?,?,?,?)', (item_id, data['project_id'], title, body, now, now))
            return {'operation': operation, 'project' if is_project else 'note': self._record(db, table, item_id)}
        if operation == 'link.delete':
            old = self._record(db, 'workspace_links', data.get('link_id'))
            db.execute('DELETE FROM workspace_links WHERE id=?', (old['id'],))
            return {'operation': operation, 'deleted_id': old['id']}
        self._record(db, 'workspace_projects', data.get('project_id'))
        label, target = _text(data.get('label'), 200), _body(data.get('target'), 2000)
        if not target or any(ord(character) < 32 for character in target):
            raise ValueError('Link targets must be nonempty and cannot contain control characters.')
        kind = data.get('kind')
        if not isinstance(kind, str) or kind not in {'file', 'conversation'}:
            raise ValueError('Link kind must be file or conversation.')
        if kind == 'file' and not PureWindowsPath(target).is_absolute() and not Path(target).is_absolute():
            raise ValueError('File links require an absolute path; the controller decides access when opened.')
        if kind == 'conversation' and (not target.isascii() or not target.isdigit() or int(target) < 1):
            raise ValueError('Conversation links require a positive message ID.')
        if db.execute('SELECT count(*) FROM workspace_links').fetchone()[0] >= 1000:
            raise ValueError('Workspace supports at most 1000 links.')
        item_id = uuid4().hex
        db.execute('INSERT INTO workspace_links VALUES (?,?,?,?,?,?)', (item_id, data['project_id'], label, target, kind, now))
        return {'operation': operation, 'link': dict(db.execute('SELECT * FROM workspace_links WHERE id=?', (item_id,)).fetchone())}

    def backup(self):
        folder = self.root / 'workspace-backups'
        if folder.is_symlink() or not folder.resolve().is_relative_to(self.root):
            raise ValueError('Backup directory must stay inside the configured data directory.')
        folder.mkdir(parents=True, exist_ok=True)
        name = f'todos-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}.sqlite3'
        with closing(sqlite3.connect(self.path, timeout=10)) as source, closing(sqlite3.connect(folder / name)) as destination:
            source.backup(destination)
            if destination.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity check failed; source database was not changed.')
        return {'backup_file': name, 'created_at': _stamp()}

    def get_calendar_cache(self, key):
        if not isinstance(key, str) or not 1 <= len(key) <= 120:
            raise ValueError('Invalid calendar cache key.')
        with self.connect() as db:
            row = db.execute('SELECT * FROM workspace_cache WHERE key=?', (key,)).fetchone()
            return {'payload': json.loads(row['value']), 'saved_at': row['saved_at']} if row else None

    def save_calendar_cache(self, key, payload):
        if not isinstance(key, str) or not 1 <= len(key) <= 120 or not isinstance(payload, dict):
            raise ValueError('Invalid calendar cache key or payload.')
        serialized = json.dumps(payload)
        if len(serialized) > 2_000_000:
            raise ValueError('Calendar cache payload is too large.')
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO workspace_cache VALUES (?,?,?)', (key, serialized, _stamp()))

    @staticmethod
    def _preferences(db):
        row = db.execute("SELECT value FROM workspace_preferences WHERE key='notifications'").fetchone()
        saved = json.loads(row['value']) if row else {}
        return {'categories': {category: saved.get(category, True) for category in CATEGORIES}}

    def ingest(self, entries):
        """Record real, pre-redacted adapter events with deduplication and rate limits."""
        if not isinstance(entries, list) or len(entries) > 100:
            raise ValueError('Notification ingestion accepts at most 100 real events.')
        with self._lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            preferences = self._preferences(db)['categories']
            for raw in entries:
                entry = safe_value(raw)
                if not isinstance(entry, dict) or set(entry) - {'key', 'category', 'priority', 'title', 'message', 'target', 'created_at'}:
                    raise ValueError('Invalid notification fields.')
                key, category, priority = entry.get('key'), entry.get('category'), entry.get('priority')
                if not isinstance(key, str) or not 1 <= len(key) <= 400 or category not in CATEGORIES or priority not in {'critical', 'action_required', 'informational'}:
                    raise ValueError('Invalid notification identity, category or priority.')
                if db.execute('SELECT 1 FROM workspace_notification_seen WHERE key=?', (key,)).fetchone():
                    continue
                now = time.time()
                recent = db.execute('SELECT count(*) FROM workspace_notifications WHERE category=? AND ingested_at>?', (category, now - 60)).fetchone()[0]
                target = entry.get('target', {})
                if not isinstance(target, dict) or set(target) - {'screen', 'id'} or not isinstance(target.get('screen'), str):
                    raise ValueError('Notification targets must name a screen.')
                title, message = entry.get('title'), entry.get('message')
                if not isinstance(title, str) or not title.strip() or len(title) > 300 or not isinstance(message, str) or len(message) > 2000:
                    raise ValueError('Invalid notification text.')
                created_at = entry.get('created_at') or _stamp()
                try:
                    datetime.fromisoformat(created_at)
                except (ValueError, TypeError):
                    raise ValueError('Notification timestamp must be ISO formatted.') from None
                db.execute('INSERT INTO workspace_notification_seen VALUES (?)', (key,))
                if not preferences[category] or (priority == 'informational' and recent >= 5):
                    continue  # Muted or rate-limited events must not replay later.
                db.execute('INSERT INTO workspace_notifications (id,key,category,priority,title,message,target,created_at,ingested_at) VALUES (?,?,?,?,?,?,?,?,?)', (uuid4().hex, key, category, priority, title, message, json.dumps(target), created_at, now))
            rows = db.execute('SELECT id FROM workspace_notifications ORDER BY ingested_at DESC LIMIT -1 OFFSET 1000').fetchall()
            for row in rows:
                db.execute('DELETE FROM workspace_notifications WHERE id=?', (row['id'],))

    def notifications(self):
        with self.connect() as db:
            items = []
            for row in db.execute('SELECT * FROM workspace_notifications ORDER BY ingested_at DESC LIMIT 1000'):
                item = dict(row)
                item.pop('ingested_at')
                item['target'] = json.loads(item['target'])
                item['read'], item['dismissed'] = bool(item['read']), bool(item['dismissed'])
                items.append(item)
            return {'available': True, 'items': items, 'preferences': self._preferences(db), 'reason': None}

    def notification_mutate(self, operation, data, request_id):
        specs = {'notification.read': {'notification_id'}, 'notification.dismiss': {'notification_id'},
                 'notification.clear': set(), 'notification.preferences': {'categories'}}
        if operation not in specs or not isinstance(data, dict) or set(data) != specs[operation]:
            raise ValueError('Invalid notification operation or fields.')
        def change():
            if operation == 'notification.clear':
                db.execute('UPDATE workspace_notifications SET read=1,dismissed=1')
            elif operation == 'notification.preferences':
                categories = data['categories']
                if not isinstance(categories, dict) or set(categories) - set(CATEGORIES) or any(type(value) is not bool for value in categories.values()):
                    raise ValueError('Notification category preferences must be booleans.')
                current = self._preferences(db)['categories']
                current.update(categories)
                db.execute("INSERT OR REPLACE INTO workspace_preferences VALUES ('notifications',?)", (json.dumps(current),))
            else:
                row = db.execute('SELECT id FROM workspace_notifications WHERE id=?', (data['notification_id'],)).fetchone()
                if row is None:
                    raise ValueError('Notification not found.')
                db.execute('UPDATE workspace_notifications SET read=1' + (',dismissed=1' if operation == 'notification.dismiss' else '') + ' WHERE id=?', (row['id'],))
            return {'operation': operation, 'saved': True}
        with self._lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            return self._request(db, operation, data, request_id, change)
