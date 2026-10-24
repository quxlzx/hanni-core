"""Bounded reconnects for individually approved, pinned MCP configurations."""
import json
from pathlib import Path
import re
import threading
import time


class AutoConnections:
    def __init__(self, manager, policy_file, guard):
        self.manager, self.path, self.guard = manager, Path(policy_file), guard
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.status = {}
        self.retries = {}
        self.thread = None

    def policy(self):
        if not self.path.exists():
            return []
        if self.path.is_symlink() or self.path.stat().st_size > 16384:
            raise ValueError('Invalid MCP startup policy.')
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if set(data) != {'version','servers'} or data['version'] != 1 or not isinstance(data['servers'],list) or len(data['servers']) > 8:
            raise ValueError('Invalid MCP startup policy.')
        seen = set()
        for item in data['servers']:
            if set(item) != {'id','config_hash'} or not re.fullmatch(r'[0-9a-f]{32}',item['id']) or not re.fullmatch(r'[0-9a-f]{64}',item['config_hash']) or item['id'] in seen:
                raise ValueError('Invalid pinned MCP connection.')
            seen.add(item['id'])
        return data['servers']

    def start(self):
        if self.thread is None and self.path.exists():
            self.thread = threading.Thread(target=self.run, name='hanni-mcp-reconnect', daemon=True)
            self.thread.start()

    def tick(self):
        try:
            policy = self.policy()
            self.guard()
            snapshot = {server['id']:server for server in self.manager.snapshot()['servers']}
            current = {}
            for item in policy:
                if self.stop.is_set(): break
                server = snapshot.get(item['id'])
                key = (item['id'],item['config_hash'])
                if not server or not server['enabled'] or server['config_hash'] != item['config_hash']:
                    current[item['id']] = 'blocked: removed, disabled or configuration changed'
                    continue
                if server['state'] == 'connected':
                    self.retries.pop(key,None)
                    current[item['id']] = 'connected'
                    continue
                tries, retry_at = self.retries.get(key,(0,0))
                if tries >= 8:
                    current[item['id']] = 'retry limit reached'
                    continue
                if time.monotonic() < retry_at:
                    current[item['id']] = 'waiting to retry'
                    continue
                try:
                    def still_authorized():
                        self.guard()
                        if self.stop.is_set() or item not in self.policy():
                            raise RuntimeError('Startup connection scope was revoked.')
                    self.manager.reconnect_approved(item['id'],item['config_hash'],guard=still_authorized)
                    self.retries.pop(key,None)
                    current[item['id']] = 'connected'
                except (RuntimeError, OSError, ValueError):
                    self.retries[key] = (tries+1,time.monotonic()+min(60,2**(tries+1)))
                    current[item['id']] = 'unavailable or approval revoked'
            with self.lock:
                self.status = current
        except (RuntimeError, OSError, ValueError, TypeError, KeyError):
            with self.lock:
                self.status = {'policy':'blocked: startup policy or owner permission unavailable'}

    def run(self):
        while not self.stop.is_set():
            self.tick()
            if self.stop.wait(2): break

    def pause(self, server_id):
        # An authenticated owner disconnect must survive the next polling cycle.
        with self.lock:
            entries = self.policy()
            if any(item['id']==server_id for item in entries):
                tmp = self.path.with_suffix('.tmp')
                tmp.write_text(json.dumps({'version':1,'servers':[item for item in entries if item['id']!=server_id]},indent=2),encoding='utf-8')
                tmp.replace(self.path)

    def pin(self, server_id, config_hash):
        """Persist the exact owner-connected configuration selected in the UI."""
        with self.lock:
            entries = [item for item in self.policy() if item['id'] != server_id]
            if len(entries) >= 8:
                raise ValueError('At most eight servers can reconnect automatically. Disable startup reconnect on another server first.')
            entries.append({'id': server_id, 'config_hash': config_hash})
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps({'version': 1, 'servers': entries}, indent=2), encoding='utf-8')
            tmp.replace(self.path)
        self.start()

    def snapshot(self):
        with self.lock:
            return {'enabled':self.path.exists(),'connections':dict(self.status),'max_consecutive_attempts':8}

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)
