"""Fixed, authenticated MCP management operations through existing tool policy.

Configuration/credential references never become audit arguments or a generic
execution API. The live assistant receives adapters in its original registry.
"""
from __future__ import annotations

from contextvars import ContextVar
import json
import os
from pathlib import Path
import sqlite3
import threading
from uuid import uuid4

from hanni.dashboard.features import RequestLedger, request_id
from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult

OPERATIONS = frozenset({
    'add', 'update', 'test_discover', 'refresh', 'reconnect', 'enable_server',
    'disable_server', 'disconnect', 'remove', 'approve_tools', 'disable_tools',
    'import_preview', 'import', 'export',
})
_MANAGEMENT_PAYLOAD = ContextVar('hanni_mcp_management_payload', default=None)


class MCPHub:
    def __init__(self, config, features, *, manager=None):
        self.config, self.features = config, features
        self.root = Path(config.paths.data_dir).resolve() if config else None
        self.manager = manager
        self.ledger = RequestLedger()
        self.lock = threading.RLock()
        self.controller_registry = None
        self.model_tools_enabled = False
        self.observe_first = True
        self.closed = False
        self.error = None
        self.auto_connections = None
        if self.root is not None and self.manager is None:
            try:
                from hanni.mcp.manager import MCPManager
                self.manager = MCPManager(self.root)
            except (OSError, RuntimeError, ValueError, sqlite3.Error):
                self.error = ('MCP storage is unavailable or requires a supported migration. '
                              'Existing data was retained; no server was started.')
        if self.root is not None and self.manager is not None:
            from hanni.mcp.autoconnect import AutoConnections
            self.auto_connections = AutoConnections(self.manager,self.root/'mcp'/'auto-connect.json',self.connection_guard)
            self.auto_connections.start()

    def connection_guard(self):
        if self.closed:
            raise RuntimeError('MCP Hub is closed.')
        registry = self.controller_registry or self.features.registry
        registry.context.emergency_stop.guard('MCP startup connection')
        owner = registry.context.permissions.owner
        if owner.chat_only or owner.max_auto_approve_level < 0:
            raise RuntimeError('Owner profile blocks MCP startup connections.')

    def require(self):
        if self.closed or self.manager is None:
            raise RuntimeError(self.error or 'MCP Hub is unavailable in this session.')
        return self.manager

    def attach_controller(self, registry, *, model_tools_enabled, observe_first, external_tools_enabled=True):
        with self.lock:
            if self.closed:
                return
            if self.manager is not None and external_tools_enabled:
                self.manager.attach_registry(registry)
            self.controller_registry = registry
            self.model_tools_enabled = bool(model_tools_enabled)
            self.observe_first = bool(observe_first)

    def snapshot(self):
        if self.manager is None or self.closed:
            result = {'available': False, 'servers': [], 'revision': 0,
                      'reason': self.error or 'Local MCP configuration is unavailable.'}
        else:
            result = self.manager.snapshot()
        return {**result, 'auto_connections': self.auto_connections.snapshot() if self.auto_connections else None,
                'controller_attached': self.controller_registry is not None,
                'model_tools_enabled': self.model_tools_enabled,
                'observe_first': self.observe_first,
                'policy_reason': (
                    'Start the assistant to use approved tools in its live registry.'
                    if self.controller_registry is None else
                    'Tool calling is disabled in the current assistant configuration.'
                    if not self.model_tools_enabled else
                    'The assistant exposes approved read-only tools. Writes still require execution confirmation.'
                    if self.observe_first else
                    'The existing assistant permission and confirmation policy governs every tool call.')}

    def export_configs(self):
        return self.require().export_configs()

    @staticmethod
    def _keys(data, required):
        if not isinstance(data, dict) or set(data) != set(required):
            raise ValueError('Choose the expected MCP operation fields and refresh before retrying.')

    def _operation(self, operation, data, correlation_id=None):
        manager = self.require()
        if operation == 'add':
            self._keys(data, {'config'})
            return manager.add(data['config'])
        if operation == 'update':
            self._keys(data, {'server_id', 'config', 'expected_config_hash'})
            return manager.update(data['server_id'], data['config'],
                                  expected_config_hash=data['expected_config_hash'])
        if operation in {'test_discover', 'reconnect'}:
            self._keys(data, {'server_id', 'approved', 'expected_config_hash'})
            if data['approved'] is not True:
                raise ValueError('Review and explicitly approve the displayed connection first.')
            action = manager.connect if operation == 'test_discover' else manager.reconnect
            return action(data['server_id'], approved=True,
                          expected_config_hash=data['expected_config_hash'])
        if operation in {'refresh', 'enable_server', 'disable_server', 'disconnect', 'remove'}:
            self._keys(data, {'server_id'})
            if self.auto_connections and operation in {'disable_server','disconnect','remove'}:
                self.auto_connections.pause(data['server_id'])
            return getattr(manager, operation)(data['server_id'])
        if operation == 'approve_tools':
            self._keys(data, {'server_id', 'tools'})
            return manager.approve_tools(data['server_id'], data['tools'])
        if operation == 'disable_tools':
            self._keys(data, {'server_id', 'names'})
            return manager.disable_tools(data['server_id'], data['names'])
        if operation == 'import_preview':
            self._keys(data, {'document'})
            return manager.preview_import(data['document'])
        if operation == 'import':
            self._keys(data, {'configs'})
            # Manager validates the normalized configurations together again;
            # conflicts reject the whole transaction, never overwrite or launch.
            return manager.import_configs(data['configs'])
        if operation == 'export':
            self._keys(data, set())
            return self._save_export(correlation_id)
        raise ValueError('Choose a supported MCP management operation.')

    def _save_export(self, correlation_id):
        # Native HANNI intentionally disables browser downloads. This fixed
        # local export works in its WebView without changing that policy.
        configuration = self.export_configs()
        content = json.dumps(configuration, ensure_ascii=False, allow_nan=False, indent=2)
        directory = (self.root / 'mcp' / 'exports').resolve()
        try:
            directory.relative_to(self.root)
        except ValueError:
            raise ValueError('The MCP export folder must stay inside HANNI data storage.') from None
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f'hanni-mcp-{request_id(correlation_id)}.json'
        if path.exists():
            if path.read_text(encoding='utf-8') != content:
                raise ValueError('This export ID already belongs to a different configuration.')
        else:
            temporary = directory / f'.{uuid4().hex}.tmp'
            try:
                with temporary.open('x', encoding='utf-8', newline='\n') as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        return {'configuration': configuration, 'file': {'name': path.name, 'path': str(path)}}

    def mutate(self, body):
        self.require()
        self._keys(body, {'id', 'operation', 'data', 'confirmed'})
        operation = body['operation']
        if not isinstance(operation, str) or operation not in OPERATIONS:
            raise ValueError('Choose a supported MCP management operation.')
        if body['confirmed'] is not True or not isinstance(body['data'], dict):
            raise ValueError('Explicit confirmation is required for MCP management.')

        def execute():
            # Once live, management shares the exact controller stop/profile
            # context; dashboard-only uses the existing desktop registry.
            registry = self.controller_registry or self.features.registry
            name = 'workspace.mcp.manage'
            with self.lock:
                if name not in {tool.name for tool in registry.definitions()}:
                    def handler(arguments, context, request):
                        payload = _MANAGEMENT_PAYLOAD.get()
                        if payload is None or request.source != 'desktop-mcp-hub':
                            raise ValueError('MCP management is available only through the authenticated Hub.')
                        result = self._operation(arguments['operation'], payload, request.correlation_id)
                        return ToolResult(name, True, 'Explicit MCP management action completed.', {'result': result})
                    registry.register(ToolDefinition(
                        name, 'Explicit owner-approved MCP connection and definition management.',
                        2, 3, {'operation': str}, {'result': 'object'}, handler,
                        side_effect='external_action', background_allowed=False,
                        argument_constraints={'operation': {'required': True, 'nullable': False,
                                                           'enum': sorted(OPERATIONS)}}))
            token = _MANAGEMENT_PAYLOAD.set(body['data'])
            try:
                from hanni.reliability.context import request_scope
                with request_scope(body['id'], 'dashboard'):
                    result = registry.execute(ToolRequest(name, {'operation': operation},
                        confirmed=True, source='desktop-mcp-hub', correlation_id=body['id']))
                return result.data['result']
            finally:
                _MANAGEMENT_PAYLOAD.reset(token)

        return self.ledger.execute(body['id'], body, execute)

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
        from hanni.mcp.runtime import uninstall
        uninstall(self)
        if self.auto_connections is not None:
            self.auto_connections.close()
        if self.manager is not None:
            self.manager.close()
