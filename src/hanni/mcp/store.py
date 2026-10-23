"""Versioned transactional MCP settings; no credentials or tool arguments."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import threading

from hanni.mcp.security import MCPConfigurationError, MAX_DISCOVERY, MAX_SERVERS, json_copy


class MCPStore:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / 'mcp' / 'hub.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        try:
            self.db = sqlite3.connect(self.path, check_same_thread=False)
            version = self.db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                self.db.close()
                raise MCPConfigurationError('MCP settings require a newer HANNI version.')
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('CREATE TABLE IF NOT EXISTS servers(id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS discovery(id INTEGER PRIMARY KEY, server_id TEXT NOT NULL REFERENCES servers(id) ON DELETE CASCADE, created_at TEXT NOT NULL, payload TEXT NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, server_id TEXT, operation TEXT NOT NULL, details TEXT NOT NULL)')
            self.db.execute('PRAGMA user_version=1')
            self.db.commit()
        except sqlite3.DatabaseError:
            if hasattr(self, 'db'): self.db.close()
            raise MCPConfigurationError('MCP settings could not be read. The existing file has been preserved.') from None

    def load(self):
        with self.lock:
            try:
                rows = self.db.execute('SELECT payload FROM servers ORDER BY id').fetchall()
                if len(rows) > MAX_SERVERS: raise ValueError()
                return [json_copy(json.loads(row[0]), limit=MAX_DISCOVERY + 65536) for row in rows]
            except (ValueError, TypeError, sqlite3.DatabaseError):
                raise MCPConfigurationError('MCP settings are corrupt; no configured server was started.') from None

    def save(self, server, *, discovery=None, audit=None):
        payload = json.dumps(server, ensure_ascii=False, allow_nan=False)
        with self.lock, self.db:
            self.db.execute('INSERT INTO servers(id,payload) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (server['id'], payload))
            if discovery is not None:
                self.db.execute('INSERT INTO discovery(server_id,created_at,payload) VALUES(?,?,?)',
                                (server['id'], server['last_discovery_at'], json.dumps(discovery, ensure_ascii=False)))
                self.db.execute('DELETE FROM discovery WHERE server_id=? AND id NOT IN (SELECT id FROM discovery WHERE server_id=? ORDER BY id DESC LIMIT 8)', (server['id'], server['id']))
            if audit: self._audit(server['id'], *audit)

    def _audit(self, server_id, timestamp, operation, details):
        self.db.execute('INSERT INTO audit(timestamp,server_id,operation,details) VALUES(?,?,?,?)',
                        (timestamp, server_id, operation, json.dumps(details, ensure_ascii=False)))

    def add_many(self, servers, timestamp):
        with self.lock, self.db:
            for server in servers:
                self.db.execute('INSERT INTO servers(id,payload) VALUES(?,?)',
                                (server['id'], json.dumps(server, ensure_ascii=False)))
                self._audit(server['id'], timestamp, 'add', {'transport': server['transport']})

    def audit(self, server_id, timestamp, operation, details):
        with self.lock, self.db: self._audit(server_id, timestamp, operation, details)

    def remove(self, server_id, timestamp):
        with self.lock, self.db:
            self.db.execute('DELETE FROM servers WHERE id=?', (server_id,))
            self._audit(server_id, timestamp, 'remove', {})

    def close(self):
        with self.lock: self.db.close()
