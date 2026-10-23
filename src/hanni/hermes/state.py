"""Durable task/action receipts. Uncertain dispatches are never replayed."""
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time
from contextlib import contextmanager
from uuid import uuid4

VERSION = 1
TERMINAL = {'completed', 'review_required', 'failed', 'cancelled', 'interrupted', 'uncertain'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


class Conflict(ValueError):
    pass


class TaskStore:
    def __init__(self, path, *, recover=False):
        self.path = Path(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, key TEXT UNIQUE, hash TEXT, payload TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY, task TEXT, payload TEXT)')
        self.db.commit()
        if recover:
            with self.transaction():
                for row in self.db.execute('SELECT id,payload FROM tasks').fetchall():
                    task = json.loads(row[1])
                    if task['state'] not in TERMINAL:
                        task.update(state='interrupted', error='Bridge restarted; side effects were not replayed.')
                        self._save(task)
                for row in self.db.execute('SELECT id,payload FROM actions').fetchall():
                    action = json.loads(row[1])
                    if action['state'] == 'dispatching':
                        action.update(state='uncertain', receipt={'ok': False, 'error': 'Acknowledgment unavailable; do not replay.'})
                        self._action_save(action)

    @contextmanager
    def transaction(self):
        with self.lock:
            nested = self.db.in_transaction
            if not nested:
                self.db.execute('BEGIN IMMEDIATE')
            try:
                yield
                if not nested:
                    self.db.commit()
            except BaseException:
                if not nested:
                    self.db.rollback()
                raise

    def _save(self, task):
        task['updated'] = time.time()
        self.db.execute('UPDATE tasks SET payload=? WHERE id=?', (json.dumps(task), task['id']))

    def _action_save(self, action):
        self.db.execute('UPDATE actions SET payload=? WHERE id=?', (json.dumps(action), action['id']))

    def submit(self, key, payload):
        if not isinstance(key, str) or not 1 <= len(key) <= 128:
            raise ValueError('An idempotency key is required.')
        if set(payload) != {'prompt', 'windows_tools', 'origin', 'context'} or payload['origin'] != 'hanni':
            raise ValueError('Invalid task contract or delegation loop.')
        if not isinstance(payload['prompt'], str) or not 1 <= len(payload['prompt']) <= 8000:
            raise ValueError('Task exceeds prompt limit.')
        if not isinstance(payload['context'],dict):
            raise ValueError('Task context must be a bounded data package.')
        if len(json.dumps(payload)) > 65536 or not isinstance(payload['windows_tools'], list) or len(payload['windows_tools']) > 12:
            raise ValueError('Task context/tool menu exceeds limits.')
        if any(not isinstance(spec, dict) or spec.get('target') != 'windows' for spec in payload['windows_tools']):
            raise ValueError('HANNI can supply only its own Windows capability proposals.')
        h = digest(payload)
        with self.transaction():
            row = self.db.execute('SELECT id,hash FROM tasks WHERE key=?', (key,)).fetchone()
            if row:
                if row[1] != h:
                    raise Conflict('Idempotency key reused for a different task.')
                return self.get(row[0])
            if self.db.execute('SELECT count(*) FROM tasks').fetchone()[0] >= 256:
                raise ValueError('Task retention limit reached; archive explicitly before adding work.')
            task = dict(id=uuid4().hex, state='queued', created=time.time(), updated=time.time(),
                        request=payload, events=[], result=None, error=None)
            self.db.execute('INSERT INTO tasks VALUES(?,?,?,?)', (task['id'], key, h, json.dumps(task)))
            return task

    def get(self, task_id):
        with self.lock:
            row = self.db.execute('SELECT payload FROM tasks WHERE id=?', (task_id,)).fetchone()
            if row is None:
                raise KeyError('Task not found.')
            task = json.loads(row[0])
            task['actions'] = [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM actions WHERE task=?', (task_id,))]
            return task

    def list(self):
        with self.lock:
            return [self.get(row[0]) for row in self.db.execute('SELECT id FROM tasks ORDER BY rowid DESC LIMIT 30').fetchall()]

    def submission(self, key):
        with self.lock:
            row = self.db.execute('SELECT id FROM tasks WHERE key=?', (key,)).fetchone()
            if row is None:
                raise KeyError('Submission not found.')
            return self.get(row[0])

    def queued(self):
        with self.lock:
            return [self.get(row[0]) for row in self.db.execute('SELECT id FROM tasks ORDER BY rowid').fetchall()
                    if self.get(row[0])['state'] == 'queued']

    def event(self, task_id, text, *, state=None, result=None, error=None):
        with self.transaction():
            task = self.get(task_id)
            task.pop('actions')
            if task['state'] in TERMINAL:
                return
            task['events'] = (task['events'] + [{'time': time.time(), 'text': str(text)[:500]}])[-64:]
            if state is not None:
                task['state'] = state
            if result is not None:
                if len(json.dumps(result)) > 65536:
                    raise ValueError('Result exceeds limit.')
                task['result'] = result
            if error is not None:
                task['error'] = str(error)[:500]
            self._save(task)

    def request_action(self, task_id, call_id, spec, arguments):
        if set(spec) != {'name', 'target', 'hash', 'schema', 'remote'} or spec['target'] not in {'windows', 'karina', 'local'}:
            raise ValueError('Invalid scoped capability.')
        if len(json.dumps(arguments)) > 32768:
            raise ValueError('Arguments exceed limit.')
        action_id = digest([task_id, call_id])
        with self.transaction():
            existing = self.db.execute('SELECT payload FROM actions WHERE id=?', (action_id,)).fetchone()
            if existing:
                action = json.loads(existing[0])
                if action['spec'] != spec or action['arguments'] != arguments:
                    raise Conflict('Changed arguments on a repeated call.')
                return action
            task = self.get(task_id)
            if task['state'] in TERMINAL or len(task['actions']) >= 32:
                raise ValueError('Task stopped or action budget exhausted.')
            # Repeated proposals use existing receipts, never duplicate effects.
            for previous in task['actions']:
                trusted_read = spec['target']=='windows' and spec['remote'].get('retry_read') is True
                if previous['spec'] == spec and previous['arguments'] == arguments and not trusted_read:
                    return previous
            action = dict(id=action_id, task=task_id, state='pending', spec=spec,
                          arguments=arguments, created=time.time(), expires=time.time()+300, receipt=None)
            self.db.execute('INSERT INTO actions VALUES(?,?,?)', (action_id, task_id, json.dumps(action)))
            self.event(task_id, 'Waiting for HANNI capability authorization.', state='approval')
            return action

    def action(self, action_id):
        with self.lock:
            row = self.db.execute('SELECT payload FROM actions WHERE id=?', (action_id,)).fetchone()
            if row is None:
                raise KeyError('Action not found.')
            return json.loads(row[0])

    def settle(self, action_id, state, receipt=None):
        if state not in {'dispatching', 'rejected', 'fulfilled', 'uncertain'}:
            raise ValueError('Invalid action transition.')
        with self.transaction():
            action = self.action(action_id)
            task = self.get(action['task'])
            if action['state'] in {'fulfilled', 'rejected', 'uncertain'}:
                if action['state'] == state and action['receipt'] == receipt:
                    return action
                raise Conflict('Action already settled; execution cannot be replayed.')
            reporting_dispatched = action['state'] == 'dispatching' and state in {'fulfilled', 'uncertain'}
            rejecting_expired = action['state'] == 'pending' and state == 'rejected' and task['state'] not in TERMINAL
            if not reporting_dispatched and not rejecting_expired and (task['state'] in TERMINAL or time.time() > action['expires']):
                raise Conflict('Task cancelled or approval expired.')
            if state == 'dispatching' and action['state'] != 'pending':
                raise Conflict('Action already dispatched; do not repeat.')
            if state == 'fulfilled' and action['state'] != 'dispatching':
                raise Conflict('Execution must be claimed before reporting a receipt.')
            action.update(state=state, receipt=receipt)
            self._action_save(action)
            return action

    def cancel(self, task_id):
        self.event(task_id, 'Cancellation requested; completed effects are retained.', state='cancelled')
        return self.get(task_id)

    def close(self):
        self.db.close()
