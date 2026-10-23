"""Persistent owner-managed MCP lifecycle; discovery never invokes tools."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import threading
import uuid

from hanni.logs.redaction import redact_value
from hanni.mcp.security import (CLASSIFICATIONS, MAX_DISCOVERY, MAX_SERVERS,
                                MCPAuthenticationRequired, MCPConfigurationError,
                                definition_hash, json_copy, normalize_config, validate_schema)
from hanni.mcp.store import MCPStore
from hanni.mcp.transport import AsyncRuntime, SDKConnection


def now(): return datetime.now(timezone.utc).isoformat()


class MCPManager:
    def __init__(self, data_dir, registry=None, *, connection_factory=SDKConnection, env=None, vault=None):
        self.store = MCPStore(data_dir)
        self.lock, self.operations = threading.RLock(), threading.RLock()
        self.closed = False
        self.runtime = None
        self.connections, self.pending = {}, {}
        self.retired = []
        self.registries, self.registered = [], {}
        self.adapters, self.stop_listeners = {}, []
        self.notification_generation, self.notification_refresh = {}, set()
        self.connection_factory, self.env, self.vault = connection_factory, env, vault
        self.protected_values = set()
        self.revision = 0
        self.servers = {}
        try: saved = self.store.load()
        except Exception:
            self.store.close()
            raise
        for server in saved:
            try:
                if not isinstance(server['id'], str) or len(server['id']) != 32:
                    raise ValueError()
                int(server['id'], 16)
                server['config'] = normalize_config(server['config'])
                self._protect_config(server['config'])
                self._reject_sensitive(server)
                server['config_hash'] = definition_hash(server['config'])
                server['state'] = 'disconnected' if server['enabled'] else 'disabled'
                server['error'] = ''
                server['tools'] = json_copy(server['tools'], limit=MAX_DISCOVERY)
                for tool in server['tools']:
                    tool['available'] = False
                self.servers[server['id']] = server
            except (KeyError, ValueError, TypeError):
                self.store.close()
                raise MCPConfigurationError('Saved MCP settings are invalid; no server was started.') from None
        if registry is not None: self.attach_registry(registry)

    def _check(self):
        if self.closed: raise MCPConfigurationError('MCP Hub has been closed.')

    def _protect_config(self, config):
        env = os.environ if self.env is None else self.env
        references = list(config['env_refs'].values())
        if config['auth']['type'] == 'bearer_env': references.append(config['auth']['reference'])
        for reference in references:
            value = env.get(reference)
            if isinstance(value, str) and value: self.protected_values.add(value)
        self._reject_sensitive(config)

    def _reject_sensitive(self, value):
        if redact_value(value) != value:
            raise MCPConfigurationError('Sensitive credential content was withheld; use credential references only.')
        def contains(item):
            if isinstance(item, str): return any(secret in item for secret in self.protected_values)
            if isinstance(item, dict): return any(contains(key) or contains(child) for key, child in item.items())
            if isinstance(item, list): return any(contains(child) for child in item)
            return False
        if contains(value):
            raise MCPConfigurationError('Sensitive credential content was withheld; use credential references only.')

    def _server(self, server_id):
        self._check()
        try: return self.servers[server_id]
        except (KeyError, TypeError): raise MCPConfigurationError('MCP server was not found.') from None

    def _save(self, server, operation, details=None, *, discovery=None):
        self.revision += 1
        self.store.save(server, discovery=discovery, audit=(now(), operation, details or {}))

    def _public(self, server):
        result = deepcopy(server)
        result.pop('connection_approval_hash', None)
        result['discovered_count'] = len(result['tools'])
        result['enabled_count'] = sum(bool(tool['enabled']) for tool in result['tools'])
        return redact_value(result)

    def snapshot(self):
        with self.lock:
            if not self.closed:
                for server in self.servers.values():
                    connection = self.connections.get(server['id'])
                    if server['state'] == 'connected' and (not connection or connection.closed):
                        server.update(state='failed', error='Server connection ended. Reconnect to restore availability.')
                        self._unregister_server(server)
                        self._save(server, 'connection_ended')
            return {'available': not self.closed, 'revision': self.revision,
                    'servers': [self._public(server) for server in self.servers.values()]}

    def _new_server(self, config):
        return {'id': uuid.uuid4().hex, 'name': config['name'], 'transport': config['transport'],
                'config': config, 'config_hash': definition_hash(config), 'enabled': False,
                'state': 'disabled', 'error': '', 'last_connected_at': None, 'last_discovery_at': None,
                'definition_revision': 0, 'connection_approval_hash': None, 'tools': []}

    def add(self, config):
        return self.import_configs([config], return_server=True)

    def import_configs(self, configs, *, return_server=False):
        if not isinstance(configs, list) or not 1 <= len(configs) <= MAX_SERVERS:
            raise MCPConfigurationError('Import must contain between 1 and 32 server configurations.')
        normalized = [normalize_config(config) for config in configs]
        with self.operations, self.lock:
            self._check()
            for config in normalized: self._protect_config(config)
            names = [config['name'].casefold() for config in normalized]
            current = {server['name'].casefold() for server in self.servers.values()}
            if len(set(names)) != len(names) or current.intersection(names):
                raise MCPConfigurationError('A server with this name already exists; imports never overwrite settings.')
            if len(self.servers) + len(normalized) > MAX_SERVERS:
                raise MCPConfigurationError('At most 32 MCP servers may be configured.')
            servers = [self._new_server(config) for config in normalized]
            self.store.add_many(servers, now())
            self.servers.update({server['id']: server for server in servers})
            self.revision += 1
            return self._public(servers[0]) if return_server else self.snapshot()

    def update(self, server_id, config, *, expected_config_hash):
        normalized = normalize_config(config)
        with self.operations:
            with self.lock:
                server = self._server(server_id)
                self._protect_config(normalized)
                for registry in self.registries:
                    registry.context.emergency_stop.guard('MCP connection')
                if expected_config_hash != server['config_hash']:
                    raise MCPConfigurationError('Server settings changed; review the current configuration before saving.')
                if any(item['id'] != server_id and item['name'].casefold() == normalized['name'].casefold()
                       for item in self.servers.values()):
                    raise MCPConfigurationError('A server with this name already exists.')
            self.disconnect(server_id)
            with self.lock:
                server = self._server(server_id)
                server.update(config=normalized, config_hash=definition_hash(normalized),
                              name=normalized['name'], transport=normalized['transport'],
                              connection_approval_hash=None, enabled=False, state='disabled', error='')
                for tool in server['tools']:
                    tool.update(enabled=False, available=False, approval=None, classification='unknown')
                self._save(server, 'update')
            return self.snapshot()

    def reconnect_approved(self, server_id, expected_config_hash, *, guard):
        """Startup may reuse exact existing connection consent, never create it."""
        with self.operations:
            guard()
            with self.lock:
                server = self._server(server_id)
                if (not server['enabled'] or server['config_hash'] != expected_config_hash
                        or server['connection_approval_hash'] != expected_config_hash):
                    raise MCPConfigurationError('Startup connection approval is absent or changed.')
            result = self.connect(server_id)
            with self.lock:
                connection = self.connections.get(server_id)
                if self._server(server_id)['state'] != 'connected' or connection is None or connection.closed:
                    raise MCPConfigurationError('Approved MCP connection is unavailable.')
            try:
                guard()
            except (RuntimeError, OSError, ValueError):
                self.disconnect(server_id)
                raise
            return result

    def connect(self, server_id, *, approved=False, expected_config_hash=None):
        with self.operations:
            with self.lock:
                server = self._server(server_id)
                for registry in self.registries:
                    registry.context.emergency_stop.guard('MCP connection')
                config_hash = server['config_hash']
                if approved:
                    if type(approved) is not bool or expected_config_hash != config_hash:
                        raise MCPConfigurationError('Connection approval does not match the current server settings.')
                    server['connection_approval_hash'] = config_hash
                elif server['connection_approval_hash'] != config_hash:
                    raise MCPConfigurationError('Review and approve this server configuration before connecting.')
            self.disconnect(server_id)
            with self.lock:
                server = self._server(server_id)
                server.update(enabled=True, state='connecting', error='')
                self._save(server, 'connect_requested', {'config_hash': config_hash})
                if self.runtime is None: self.runtime = AsyncRuntime()
                connection = self.connection_factory(self.runtime, deepcopy(server['config']),
                    changed=lambda: self._changed(server_id), env=self.env, vault=self.vault)
                self.pending[server_id] = connection
            try:
                connection.wait_ready()
                with self.lock:
                    self.protected_values.update(getattr(connection, 'protected_values', ()))
                tools = connection.request('list')
                with self.lock:
                    server = self._server(server_id)
                    if (server['config_hash'] != config_hash or connection.closed
                            or self.pending.get(server_id) is not connection):
                        raise MCPConfigurationError('Server connection was cancelled or settings changed while connecting.')
                    for registry in self.registries:
                        registry.context.emergency_stop.guard('MCP connection')
                    self.pending.pop(server_id, None)
                    self.connections[server_id] = connection
                    server.update(state='connected', error='', last_connected_at=now())
                    self._apply_discovery(server, tools)
                    self._sync_registry(server)
                return self.snapshot()
            except BaseException as exc:
                connection.close()
                with self.lock:
                    self.pending.pop(server_id, None)
                    if not self.closed:
                        self.connections.pop(server_id, None)
                        server = self.servers[server_id]
                        server['state'] = 'authentication_required' if self._authentication_error(exc) else 'failed'
                        server['error'] = self._safe_error(exc)
                        self._unregister_server(server)
                        self._save(server, 'connect_failed', {'state': server['state']})
                if isinstance(exc, (KeyboardInterrupt, SystemExit)): raise
                return self.snapshot()

    @staticmethod
    def _authentication_error(exc):
        if isinstance(exc, MCPAuthenticationRequired): return True
        return any(MCPManager._authentication_error(child) for child in getattr(exc, 'exceptions', ()))

    @staticmethod
    def _safe_error(exc):
        if MCPManager._authentication_error(exc): return 'Authentication is required. Check the configured credential reference.'
        if isinstance(exc, FileNotFoundError): return 'Server executable or working directory was not found.'
        if isinstance(exc, TimeoutError): return 'Connection or discovery timed out.'
        if isinstance(exc, MCPConfigurationError): return str(exc)
        return 'MCP initialization or discovery failed. Check the executable, endpoint, and server configuration.'

    def reconnect(self, server_id, *, approved=False, expected_config_hash=None):
        return self.connect(server_id, approved=approved, expected_config_hash=expected_config_hash)

    def refresh(self, server_id):
        with self.operations:
            with self.lock:
                server = self._server(server_id)
                connection = self.connections.get(server_id)
                generation = self.notification_generation.get(server_id, 0)
                if not connection or connection.closed or not server['enabled']:
                    raise MCPConfigurationError('Connect this server before refreshing definitions.')
            try:
                tools = connection.request('list')
                with self.lock:
                    server = self._server(server_id)
                    server.update(state='connected', error='')
                    self._apply_discovery(server, tools)
                    self._sync_registry(server)
                    if self.notification_generation.get(server_id, 0) != generation:
                        self._unregister_server(server)
                        server['error'] = 'Tool definitions changed during discovery; waiting for a fresh snapshot.'
            except Exception as exc:
                self.disconnect(server_id)
                with self.lock:
                    server = self._server(server_id)
                    server.update(state='failed', error=self._safe_error(exc))
                    self._save(server, 'refresh_failed')
            return self.snapshot()

    def _apply_discovery(self, server, definitions):
        definitions = json_copy(definitions, limit=MAX_DISCOVERY)
        self._reject_sensitive(definitions)
        if not isinstance(definitions, list) or len(definitions) > 256:
            raise MCPConfigurationError('Invalid tool-list response.')
        previous = {tool['original_name']: tool for tool in server['tools']}
        discovered, seen = [], set()
        for raw in definitions:
            raw = json_copy(raw)
            if not isinstance(raw, dict) or not isinstance(raw.get('name'), str) or not raw['name'] or len(raw['name']) > 256:
                raise MCPConfigurationError('MCP tool name is missing or invalid.')
            name = raw['name']
            if name in seen: raise MCPConfigurationError('MCP tool names must be unique within a server.')
            seen.add(name)
            digest, old = definition_hash(raw), previous.get(name)
            same = old is not None and old['definition_hash'] == digest
            errors = []
            try:
                validate_schema(raw.get('inputSchema'))
                if raw.get('outputSchema') is not None: validate_schema(raw['outputSchema'])
            except MCPConfigurationError as exc: errors.append(str(exc))
            internal = 'mcp.' + server['id'] + '.' + definition_hash(name)[:16]
            tool = {'internal_id': internal, 'original_name': name,
                    'description': raw.get('description') or '', 'input_schema': raw.get('inputSchema'),
                    'output_schema': raw.get('outputSchema'), 'annotations': raw.get('annotations'),
                    'metadata': {key: value for key, value in raw.items() if key not in
                                 {'name', 'description', 'inputSchema', 'outputSchema', 'annotations'}},
                    'valid': not errors, 'validation_errors': errors, 'enabled': bool(same and old['enabled'] and not errors),
                    'available': False, 'classification': old['classification'] if same else 'unknown',
                    'version': old['version'] if same else (old['version'] + 1 if old else 1),
                    'definition_hash': digest, 'approval': deepcopy(old['approval']) if same and not errors else None}
            discovered.append(tool)
        self._unregister_server(server)
        server.update(tools=discovered, last_discovery_at=now(), definition_revision=server['definition_revision'] + 1)
        changed = [tool['original_name'] for tool in discovered if tool['original_name'] in previous
                   and tool['definition_hash'] != previous[tool['original_name']]['definition_hash']]
        if changed: server['error'] = 'Tool definitions changed; affected tools require renewed approval.'
        self._save(server, 'discover', {'added': len(seen - set(previous)), 'removed': len(set(previous) - seen),
                                      'changed': len(changed)}, discovery=definitions)

    def _changed(self, server_id):
        with self.lock:
            if self.closed or server_id not in self.servers: return
            self.notification_generation[server_id] = self.notification_generation.get(server_id, 0) + 1
            self._unregister_server(self.servers[server_id])
            if server_id in self.notification_refresh: return
            self.notification_refresh.add(server_id)
        # Never block the SDK notification receive task on its own tools/list call.
        def refresh():
            completed = False
            try:
                while True:
                    with self.lock:
                        if self.closed or server_id not in self.connections:
                            self.notification_refresh.discard(server_id)
                            completed = True
                            return
                        generation = self.notification_generation.get(server_id, 0)
                    self.refresh(server_id)
                    with self.lock:
                        if self.notification_generation.get(server_id, 0) == generation:
                            self.notification_refresh.discard(server_id)
                            completed = True
                            return
            except Exception: pass
            finally:
                if not completed:
                    with self.lock: self.notification_refresh.discard(server_id)
        threading.Thread(target=refresh, name='HANNI-MCP-refresh', daemon=True).start()

    def disconnect(self, server_id):
        with self.operations:
            with self.lock:
                server = self._server(server_id)
                connection = self.connections.pop(server_id, None)
                self._unregister_server(server)
                server.update(state='disconnected' if server['enabled'] else 'disabled', error='')
                self._save(server, 'disconnect')
            if connection: connection.close()
            return self.snapshot()

    def disable_server(self, server_id):
        with self.operations:
            self.disconnect(server_id)
            with self.lock:
                server = self._server(server_id)
                server.update(enabled=False, state='disabled')
                self._save(server, 'disable_server')
            return self.snapshot()

    def enable_server(self, server_id):
        return self.connect(server_id)

    def remove(self, server_id):
        with self.operations:
            self.disconnect(server_id)
            with self.lock:
                self._server(server_id)
                self.store.remove(server_id, now())
                del self.servers[server_id]
                self.revision += 1
            return self.snapshot()

    def approve_tools(self, server_id, tools):
        if not isinstance(tools, list) or not tools or len(tools) > 256:
            raise MCPConfigurationError('Select between 1 and 256 tools to approve.')
        with self.operations, self.lock:
            server = self._server(server_id)
            connection = self.connections.get(server_id)
            if server['state'] != 'connected' or not server['enabled'] or not connection or connection.closed:
                raise MCPConfigurationError('Connect the server before approving tools.')
            current = {tool['original_name']: tool for tool in server['tools']}
            selected = []
            for approval in tools:
                if not isinstance(approval, dict) or set(approval) != {'original_name', 'definition_hash', 'classification'}:
                    raise MCPConfigurationError('Approval requires an exact tool name, definition hash, and classification.')
                tool = current.get(approval['original_name'])
                if (not tool or not tool['valid'] or tool['definition_hash'] != approval['definition_hash']
                        or approval['classification'] not in CLASSIFICATIONS):
                    raise MCPConfigurationError('Tool definition changed or is invalid; inspect it before approval.')
                selected.append((tool, approval))
            before = deepcopy(server['tools'])
            try:
                for tool, approval in selected:
                    tool.update(enabled=True, classification=approval['classification'],
                                approval={**approval, 'approved_at': now()})
                self._sync_registry(server)
            except Exception:
                self._unregister_server(server)
                server['tools'] = before
                self._sync_registry(server)
                raise
            self._save(server, 'approve_tools', {'count': len(selected)})
            return self.snapshot()

    def disable_tools(self, server_id, names):
        if not isinstance(names, list) or not names or len(names) > 256 or any(not isinstance(name, str) for name in names):
            raise MCPConfigurationError('Select tool names to disable.')
        with self.operations, self.lock:
            server = self._server(server_id)
            if set(names) - {tool['original_name'] for tool in server['tools']}:
                raise MCPConfigurationError('A selected tool was not found.')
            for tool in server['tools']:
                if tool['original_name'] in names: tool.update(enabled=False, available=False)
            self._sync_registry(server)
            connection = self.connections.get(server_id)
            if connection: connection.cancel_tools(names)
            self._save(server, 'disable_tools', {'count': len(names)})
            return self.snapshot()

    def preview_import(self, document):
        document = json_copy(document, limit=262144)
        if not isinstance(document, dict) or not isinstance(document.get('mcpServers'), dict):
            raise MCPConfigurationError('Import a JSON object containing mcpServers.')
        if len(document['mcpServers']) > MAX_SERVERS: raise MCPConfigurationError('Import contains too many servers.')
        candidates, warnings = [], []
        for name, original in document['mcpServers'].items():
            try:
                if not isinstance(original, dict): raise MCPConfigurationError('Server settings must be an object.')
                candidate = dict(original, name=name)
                candidate.setdefault('transport', 'streamable_http' if candidate.get('url') else 'stdio')
                if 'env' in candidate:
                    env = candidate.pop('env')
                    if not isinstance(env, dict): raise MCPConfigurationError('Invalid environment settings.')
                    refs = {}
                    for key, value in env.items():
                        if not isinstance(value, str) or not value.startswith('${') or not value.endswith('}'):
                            raise MCPConfigurationError('Plaintext environment values are not imported; use ${VARIABLE} references.')
                        refs[key] = value[2:-1]
                    candidate['env_refs'] = refs
                    warnings.append('Environment references must exist in the HANNI process before connecting.')
                normalized = normalize_config(candidate)
                if any(server['name'].casefold() == name.casefold() for server in self.servers.values()):
                    warnings.append('An existing server name is present; it cannot be overwritten.')
                candidates.append(normalized)
            except MCPConfigurationError as exc:
                warnings.append('A server configuration was skipped: ' + str(exc))
        return {'candidates': candidates, 'warnings': warnings,
                'preview_hash': definition_hash(candidates)}

    def export_configs(self):
        with self.lock:
            return {'version': 1, 'mcpServers': {server['name']: deepcopy(server['config'])
                    for server in self.servers.values()}}

    def attach_registry(self, registry):
        with self.lock:
            self._check()
            if registry not in self.registries:
                self.registries.append(registry)
                listener = self._stop_changed
                registry.context.emergency_stop.add_listener(listener)
                self.stop_listeners.append((registry.context.emergency_stop, listener))
                for server in self.servers.values(): self._sync_registry(server)

    def _unregister_server(self, server):
        prefix = 'mcp.' + server['id'] + '.'
        for registry in self.registries:
            owned = self.registered.setdefault(registry, {})
            for name in list(owned):
                if name.startswith(prefix):
                    registry.unregister(name, expected=owned.pop(name))
        for tool in server['tools']: tool['available'] = False
        for key in list(self.adapters):
            if key[0].startswith(prefix): del self.adapters[key]

    def _sync_registry(self, server):
        from hanni.mcp.adapter import definition
        from hanni.tools.base import UnknownToolError
        connection = self.connections.get(server['id'])
        eligible = [tool for tool in server['tools'] if server['state'] == 'connected' and server['enabled']
                    and connection and not connection.closed and tool['enabled'] and tool['valid']
                    and tool['approval'] and tool['approval']['definition_hash'] == tool['definition_hash']]
        for registry in self.registries:
            owned = self.registered.setdefault(registry, {})
            for tool in eligible:
                try: existing = registry.get(tool['internal_id'])
                except UnknownToolError: continue
                if existing is not owned.get(tool['internal_id']):
                    raise MCPConfigurationError('Imported capability identifier collides with an unrelated registration.')
        self._unregister_server(server)
        for tool in eligible:
            key = (tool['internal_id'], tool['definition_hash'], tool['classification'])
            if key not in self.adapters: self.adapters[key] = definition(self, server, deepcopy(tool))
            for registry in self.registries:
                registry.register(self.adapters[key])
                self.registered[registry][tool['internal_id']] = registry.get(tool['internal_id'])
            tool['available'] = bool(self.registries)

    def execute_remote(self, server_id, original_name, digest, classification, arguments, context, request):
        from concurrent.futures import CancelledError
        from hanni.tools.base import ToolError, ToolPermissionError, _BACKGROUND_CALL

        def admit():
            with self.lock:
                server = self._server(server_id)
                tool = next((item for item in server['tools'] if item['original_name'] == original_name), None)
                connection = self.connections.get(server_id)
                if (not tool or not tool['enabled'] or not tool['available'] or not tool['valid']
                        or not tool['approval'] or tool['approval']['definition_hash'] != digest
                        or tool['definition_hash'] != digest or tool['classification'] != classification
                        or not server['enabled'] or server['state'] != 'connected'
                        or not connection or connection.closed or request.name != tool['internal_id']):
                    raise ToolPermissionError('MCP capability is disabled, unavailable, or its approved definition changed.')
                registry = next((item for item in self.registries if item.context is context), None)
                if registry is None: raise ToolPermissionError('MCP execution requires an attached original registry context.')
                current = registry.get(tool['internal_id'])
                if current is not self.registered[registry].get(tool['internal_id']):
                    raise ToolPermissionError('MCP registry ownership changed.')
                context.emergency_stop.guard('external MCP tool')
                registry._authorize(current, request, arguments)
                if _BACKGROUND_CALL.get() and not current.background_allowed:
                    raise ToolPermissionError('External MCP tools are foreground-only.')
                # A tool's approved schema/classification never authorizes
                # forwarding an already known credential as ordinary data.
                # This admission is repeated by the SDK immediately before RPC.
                self._reject_sensitive(arguments)
                return connection
        connection = admit()
        correlation = request.correlation_id
        self.store.audit(server_id, now(), 'call_requested', {'capability_id': request.name, 'correlation_id': correlation})
        try:
            raw = connection.request('call', {'name': original_name, 'arguments': deepcopy(dict(arguments)), 'admit': admit})
            admit()  # A disable or definition change during the RPC revokes its result.
            with self.lock: self._reject_sensitive(raw)
            self.store.audit(server_id, now(), 'call_completed', {'capability_id': request.name,
                              'correlation_id': correlation, 'ok': not bool(raw.get('isError'))})
            return raw
        except CancelledError:
            raise ToolError('MCP call was cancelled; check the server before retrying.') from None
        except TimeoutError:
            raise TimeoutError('MCP call timed out; check the server before retrying.') from None
        except (ToolError, MCPConfigurationError): raise
        except Exception:
            raise ToolError('MCP transport failed; check the server before retrying.') from None

    def _stop_changed(self, change, record):
        if change != 'tripped': return
        with self.lock:
            if self.closed: return
            connections = list(self.connections.values()) + list(self.pending.values())
            self.retired.extend(connections)
            self.connections.clear()
            self.pending.clear()
            for server in self.servers.values():
                self._unregister_server(server)
                if server['enabled']:
                    server.update(state='disconnected', error='Emergency stop cancelled MCP connections. Reconnect explicitly after clearing it.')
            self.revision += 1
            for connection in connections: connection.signal_close()
        # The stop callback must not wait for network/process teardown or the
        # management operations lock. SDK shielded cleanup completes separately.
        def cleanup():
            for connection in connections: connection.close()
        threading.Thread(target=cleanup, name='HANNI-MCP-stop', daemon=True).start()

    def close(self):
        with self.lock:
            if self.closed: return
            self.closed = True
            connections = list(self.connections.values()) + list(self.pending.values()) + self.retired
            self.retired = []
            self.connections.clear()
            self.pending.clear()
            for server in self.servers.values(): self._unregister_server(server)
            for stop, listener in self.stop_listeners: stop.remove_listener(listener)
            self.stop_listeners.clear()
        for connection in connections: connection.close()
        if self.runtime: self.runtime.close()
        self.store.close()
