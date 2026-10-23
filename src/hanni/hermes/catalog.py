"""Single-writer, versioned MCP catalog with conservative client reconciliation."""
from copy import deepcopy
import json
from pathlib import Path
import re
import sqlite3
import threading
import time
from urllib.parse import urlsplit

from .state import Conflict, digest


def entry(name, remote_port, local_port):
    return {'name': name, 'enabled': True, 'deleted': False,
            'endpoints': {'hermes': f'http://127.0.0.1:{remote_port}/mcp',
                          'hanni': f'http://127.0.0.1:{local_port}/mcp'},
            'credential_ref': None, 'owner': 'hanni-hermes', 'definition_hashes': {},
            'approvals': {}, 'connection': 'not_checked'}


SEED = [entry('hanni_capabilities', 8090, 18090), entry('hanni_speech', 8091, 18091),
        entry('hanni_browser', 8931, 8931)]


def connection_hash(item):
    return digest({'name':item['name'],'endpoints':item['endpoints'],'credential_ref':item['credential_ref']})


def validate(item):
    if set(item) != set(SEED[0]) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,63}', item['name']):
        raise ValueError('Invalid catalog entry.')
    if item['owner'] != 'hanni-hermes' or type(item['enabled']) is not bool or type(item['deleted']) is not bool:
        raise ValueError('Invalid catalog ownership/state.')
    if item['connection'] != 'not_checked':
        raise ValueError('Connection health is observational and cannot be supplied during registration.')
    if set(item['endpoints']) != {'hermes', 'hanni'}:
        raise ValueError('Both client mappings are required.')
    for value in item['endpoints'].values():
        parts = urlsplit(value)
        if (parts.scheme != 'http' or parts.hostname != '127.0.0.1' or not parts.port or not 1024<=parts.port<=65535
                or parts.username or parts.password or parts.query or parts.fragment or parts.path != '/mcp'):
            raise ValueError('Shared catalog supports explicitly mapped literal loopback HTTP MCP only.')
    ref = item['credential_ref']
    if ref is not None and not re.fullmatch(r'[A-Z][A-Z0-9_]{0,99}', ref):
        raise ValueError('Credentials must be environment references.')
    if item['definition_hashes'] or item['approvals']:
        raise ValueError('Registration cannot supply tool-definition or execution approvals.')
    return deepcopy(item)


class Catalog:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS catalog(singleton INTEGER PRIMARY KEY, payload TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS catalog_operations(key TEXT PRIMARY KEY, hash TEXT, result TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS catalog_observations(name TEXT PRIMARY KEY,payload TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS connection_approvals(name TEXT PRIMARY KEY,hash TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS sync_status(client TEXT PRIMARY KEY,payload TEXT)')
        self.db.execute('INSERT OR IGNORE INTO catalog VALUES(1,?)',
                        (json.dumps({'version': 1, 'revision': 0, 'entries': [], 'activation': 'pending'}),))
        self.db.commit()

    def snapshot(self):
        with self.lock:
            result = json.loads(self.db.execute('SELECT payload FROM catalog WHERE singleton=1').fetchone()[0])
            result['observations'] = {row[0]:json.loads(row[1]) for row in self.db.execute('SELECT name,payload FROM catalog_observations')}
            result['connection_approvals'] = dict(self.db.execute('SELECT name,hash FROM connection_approvals'))
            result['sync_status'] = {row[0]:json.loads(row[1]) for row in self.db.execute('SELECT client,payload FROM sync_status')}
            return result

    def record_sync(self, client, status):
        with self.lock,self.db:
            self.db.execute('INSERT INTO sync_status VALUES(?,?) ON CONFLICT(client) DO UPDATE SET payload=excluded.payload',
                            (client,json.dumps({**status,'checked_at':time.time()})))

    def approve_connection(self, name, expected_hash, *, approve):
        with self.lock,self.db:
            item = next((entry for entry in self.snapshot()['entries'] if entry['name']==name),None)
            if item is None or item['deleted'] or connection_hash(item)!=expected_hash:
                raise Conflict('Connection settings changed; review the current mapping.')
            if approve:
                self.db.execute('INSERT INTO connection_approvals VALUES(?,?) ON CONFLICT(name) DO UPDATE SET hash=excluded.hash', (name,expected_hash))
            else:
                self.db.execute('DELETE FROM connection_approvals WHERE name=?',(name,))
        return self.snapshot()

    def observe(self, name, definitions, error=None):
        if name not in {entry['name'] for entry in self.snapshot()['entries']}:
            raise ValueError('Observation is outside catalog ownership.')
        payload = {'checked_at':time.time(),'state':'schema_discovered' if error is None else 'unavailable',
                   'definition_hashes':{raw['name']:digest(raw) for raw in definitions},
                   'execution_approval':'none', 'error':error}
        with self.lock,self.db:
            self.db.execute('INSERT INTO catalog_observations VALUES(?,?) ON CONFLICT(name) DO UPDATE SET payload=excluded.payload', (name,json.dumps(payload)))

    def change(self, expected_revision, entries, key):
        if not isinstance(key, str) or not 1 <= len(key) <= 128 or type(expected_revision) is not int:
            raise ValueError('Catalog revision and operation ID are required.')
        if not isinstance(entries, list) or len(entries) > 32:
            raise ValueError('At most 32 managed entries are permitted.')
        normalized = [validate(item) for item in entries]
        if len({item['name'].casefold() for item in normalized}) != len(normalized):
            raise ValueError('Duplicate catalog names.')
        for client in ['hanni', 'hermes']:
            active = [item['endpoints'][client] for item in normalized if item['enabled'] and not item['deleted']]
            if len(active) != len(set(active)):
                raise ValueError('Two servers cannot own the same mapped endpoint.')
        fingerprint = digest([expected_revision, normalized])
        with self.lock, self.db:
            old = self.db.execute('SELECT hash,result FROM catalog_operations WHERE key=?', (key,)).fetchone()
            if old:
                if old[0] != fingerprint:
                    raise Conflict('Catalog operation ID reused.')
                return json.loads(old[1])
            current = self.snapshot()
            if expected_revision != current['revision']:
                raise Conflict('Catalog changed; refresh and review conflicts before saving.')
            result = {'version': 1, 'revision': current['revision']+1, 'entries': normalized, 'activation': 'pending'}
            self.db.execute('UPDATE catalog SET payload=? WHERE singleton=1', (json.dumps(result),))
            self.db.execute('INSERT INTO catalog_operations VALUES(?,?,?)', (key, fingerprint, json.dumps(result)))
            self.db.execute('DELETE FROM catalog_operations WHERE rowid NOT IN (SELECT rowid FROM catalog_operations ORDER BY rowid DESC LIMIT 256)')
            return result


def reconcile_hermes(catalog, config_path, ownership_path, *, adopt_seed=False):
    """Preserve unrelated YAML values, back up bytes, CAS before atomic replacement.

    Disk registration is NOT active gateway registration. No restarts here.
    """
    import os
    try:
        from hermes_yaml import roundtrip_yaml
        yaml_editor = roundtrip_yaml()
        from io import StringIO
        def load_yaml(value):
            return yaml_editor.load(value)
        def dump_yaml(value):
            stream = StringIO()
            yaml_editor.dump(value, stream)
            return stream.getvalue()
    except ImportError:
        import yaml
        load_yaml = yaml.safe_load
        dump_yaml = lambda value: yaml.safe_dump(value, sort_keys=False, allow_unicode=True)
    path, owned_path = Path(config_path), Path(ownership_path)
    original = path.read_bytes()
    config = load_yaml(original)
    if not isinstance(config, dict):
        raise ValueError('Hermes configuration must be a mapping.')
    owned = json.loads(owned_path.read_text()) if owned_path.exists() else {}
    servers = deepcopy(config.get('mcp_servers', {}))
    if not isinstance(servers, dict):
        raise ValueError('Invalid top-level Hermes MCP settings.')
    desired = {item['name']: item for item in catalog['entries']}
    next_owned = {}
    for name, item in desired.items():
        current = servers.get(name)
        managed_hash = owned.get(name)
        expected_seed = next((seed for seed in SEED if seed['name'] == name), None)
        adopting = bool(adopt_seed and expected_seed and current and current.get('url') == expected_seed['endpoints']['hermes'])
        if current is not None and managed_hash is None and not adopting:
            raise Conflict('Existing Hermes entry is owned by another source: '+name)
        if current is not None and managed_hash and digest(current) != managed_hash:
            raise Conflict('Hermes entry changed outside the shared catalog: '+name)
        if item['deleted'] or not item['enabled']:
            servers.pop(name, None)
            continue
        updated = deepcopy(current) if current is not None else {}
        if current is None:
            # Installed Hermes native filter: an explicit empty whitelist loads
            # no executable tools. Task-adapter approvals remain separate.
            updated['tools'] = {'include': []}
        updated['url'] = item['endpoints']['hermes']
        if item['credential_ref']:
            # Installed Hermes source resolves ${VAR} through its profile secret scope.
            headers = deepcopy(updated.get('headers', {}))
            headers['Authorization'] = 'Bearer ${'+item['credential_ref']+'}'
            updated['headers'] = headers
        elif (updated.get('headers') or {}).get('Authorization', '').startswith('Bearer ${'):
            updated['headers'].pop('Authorization')
        servers[name] = updated
        next_owned[name] = digest(updated)
    for name in owned.keys() - desired.keys():
        if name in servers and digest(servers[name]) != owned[name]:
            raise Conflict('Externally changed entry cannot be removed: '+name)
        servers.pop(name, None)
    config['mcp_servers'] = servers
    content = dump_yaml(config).encode()
    backup = path.with_name(path.name+'.hanni-'+digest(original.hex())[:16]+'.bak')
    if not backup.exists():
        backup.write_bytes(original)
        os.chmod(backup, 0o600)
    if path.read_bytes() != original:
        raise Conflict('Hermes configuration changed during reconciliation.')
    # Journal ownership before YAML. A crash produces a visible conflict, never destructive replay.
    owned_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_owned = owned_path.with_suffix('.tmp')
    tmp_owned.write_text(json.dumps(next_owned))
    os.chmod(tmp_owned, 0o600)
    tmp = path.with_name(path.name+'.hanni.tmp')
    with tmp.open('xb') as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(tmp, path.stat().st_mode & 0o777)
    os.replace(tmp_owned, owned_path)
    os.replace(tmp, path)
    return {'registration': 'saved', 'activation': 'pending', 'backup': str(backup),
            'reason': 'Gateway activation requires a verified idle graceful lifecycle; no automatic restart.'}


def reconcile_hanni(catalog, manager, owned):
    """Registration only; exact-hash connection/tool approvals stay in MCPManager."""
    current = manager.snapshot()['servers']
    by_name = {item['name'].casefold(): item for item in current}
    desired_names = {item['name'] for item in catalog['entries']}
    for name in list(owned):
        if name not in desired_names:
            existing = next((s for s in current if s['id'] == owned[name]['id']), None)
            if existing:
                if existing['config_hash'] != owned[name]['hash']:
                    raise Conflict('HANNI managed entry changed outside catalog.')
                manager.remove(existing['id'])
            owned.pop(name)
    by_name = {server['name'].casefold():server for server in manager.snapshot()['servers']}
    for item in catalog['entries']:
        name = item['name']
        existing = by_name.get(name.casefold())
        known = owned.get(name)
        if existing and (not known or known['id'] != existing['id'] or known['hash'] != existing['config_hash']):
            raise Conflict('Existing HANNI entry is not owned by this catalog: '+name)
        if item['deleted']:
            if existing:
                manager.remove(existing['id'])
            owned.pop(name, None)
            continue
        ref = item['credential_ref']
        config = {'name': name, 'transport': 'streamable_http', 'url': item['endpoints']['hanni'],
                  'allow_local_http': True, 'timeout_seconds': 30,
                  'auth': {'type': 'bearer_env' if ref else 'none', 'reference': ref}, 'auto_connect': False}
        from hanni.mcp.security import normalize_config, definition_hash
        config = normalize_config(config)
        if existing is None:
            existing = manager.add(config)
        elif existing['config_hash'] != definition_hash(config):
            manager.update(existing['id'], config, expected_config_hash=existing['config_hash'])
            existing = next(s for s in manager.snapshot()['servers'] if s['id'] == existing['id'])
        if not item['enabled']:
            manager.disable_server(existing['id'])
        elif known and known.get('desired_enabled') is False and catalog.get('connection_approvals',{}).get(name)==connection_hash(item):
            # Apply a separately approved owner's pending enable transition,
            # never an unconditional reconnect of saved servers on startup.
            manager.enable_server(existing['id'])
        owned[name] = {'id': existing['id'], 'hash': existing['config_hash'], 'revision': catalog['revision'],
                       'desired_enabled':item['enabled']}
    return owned
