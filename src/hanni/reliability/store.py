"""Bounded local trace projection and append-only retained lifecycle events.

The caller supplies strictly constructed metadata, never raw model/tool text.
Existing corrupt or unsupported files are preserved and never recreated.
"""
import json
import os
from pathlib import Path
import sqlite3
import threading

class TraceStore:
    def __init__(self, data_dir):
        self.root = Path(data_dir).resolve()
        self.path = self.root / 'logs' / 'execution_traces.sqlite3'
        self.lock = threading.RLock()
        self.db = None

    def _connect(self):
        if self.db is not None:
            return self.db
        if (self.path.is_symlink() or not self.path.resolve().is_relative_to(self.root)
                or not self.path.parent.resolve().is_relative_to(self.root)):
            raise OSError('Trace path is unavailable.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, check_same_thread=False)
        try:
            if db.execute('PRAGMA user_version').fetchone()[0] not in (0, 1):
                raise ValueError('Unsupported trace version.')
            if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Trace integrity check failed.')
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS traces(task_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS trace_events(id INTEGER PRIMARY KEY, task_id TEXT NOT NULL REFERENCES traces(task_id) ON DELETE CASCADE, timestamp TEXT NOT NULL, state TEXT NOT NULL)')
            db.execute('PRAGMA user_version=1')
            db.commit()
            if os.name != 'nt':
                self.path.chmod(0o600)
        except Exception:
            db.close()
            raise
        self.db = db
        return db

    def append(self, record, state, timestamp):
        payload = json.dumps(record, allow_nan=False, separators=(',', ':'))
        if len(payload.encode()) > 131072:
            raise ValueError('Trace record exceeds its bounded size.')
        with self.lock:
            db = self._connect()
            with db:
                db.execute('INSERT INTO traces VALUES(?,?,?) ON CONFLICT(task_id) DO UPDATE SET payload=excluded.payload',
                           (record['task_id'], record['created_at'], payload))
                db.execute('INSERT INTO trace_events(task_id,timestamp,state) VALUES(?,?,?)', (record['task_id'], timestamp, state))
                db.execute('DELETE FROM traces WHERE task_id NOT IN (SELECT task_id FROM traces ORDER BY created_at DESC LIMIT 1000)')
                db.execute('DELETE FROM trace_events WHERE id NOT IN (SELECT id FROM trace_events ORDER BY id DESC LIMIT 50000)')

    def snapshot(self, limit=50):
        with self.lock:
            if self.db is None and not self.path.exists():
                return []  # Metadata-only discovery must not create files.
            db = self._connect()
            return [json.loads(row[0]) for row in db.execute('SELECT payload FROM traces ORDER BY created_at DESC LIMIT ?', (max(1, min(100, int(limit))),))]

    def close(self):
        with self.lock:
            if self.db:
                self.db.close()
                self.db = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
