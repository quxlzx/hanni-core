"""Expose approved dashboard-owned MCP tools to native workers over loopback."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import threading
import time

from hanni.hermes.state import TaskStore, TERMINAL
from hanni.tools.base import ToolRequest


class NativeMCP:
    def __init__(self, hub):
        self.hub = hub
        self.lock = threading.RLock()

    @property
    def available(self):
        return bool(self.hub.root and os.environ.get('HANNI_BRIDGE_URL'))

    def authorized(self, header):
        if not self.available:
            return False
        try:
            token = (self.hub.root / 'bridge.token').read_text().strip()
            return bool(token) and secrets.compare_digest(header or '', 'Bearer ' + token)
        except OSError:
            return False

    def attach(self):
        if self.available and self.hub.controller_registry is None:
            self.hub.attach_controller(self.hub.features.registry, model_tools_enabled=True, observe_first=False)

    def tools(self):
        self.attach()
        self.hub.connection_guard()
        result = []
        for server in self.hub.snapshot()['servers']:
            if server['state'] != 'connected' or not server['enabled']:
                continue
            for tool in server['tools']:
                if not (tool['enabled'] and tool['available'] and tool['valid'] and tool['approval']
                        and tool['approval']['definition_hash'] == tool['definition_hash']):
                    continue
                name = 'mcp_' + server['id'] + '_' + tool['definition_hash'][:16]
                result.append({'name': name, 'target': 'mcp', 'hash': tool['definition_hash'],
                    'schema': {'type': 'function', 'function': {'name': name,
                        'description': (server['name'] + ': ' + tool['original_name'] + '. ' + tool['description'])[:1200],
                        'parameters': tool['input_schema']}},
                    'remote': {'server_id': server['id'], 'name': tool['original_name'],
                               'capability_id': tool['internal_id'], 'classification': tool['classification']}})
        return {'tools': result[:128]}

    def call(self, action_id):
        """Claim a durable execution once; arbitrary browser RPC is never accepted."""
        self.attach()
        with self.lock:
            store = TaskStore(self.hub.root / 'tasks.sqlite3')
            try:
                action = store.action(action_id)
                task = store.get(action['task'])
                if (task.get('key') or '').startswith('cron-'):
                    raise ValueError('These MCP tools are available to foreground tasks only.')
                if action['state'] in {'fulfilled', 'rejected', 'uncertain'}:
                    return action['receipt'] or {'ok': False, 'error': action['state']}
                if (action['state'] != 'dispatching' or task['state'] in TERMINAL
                        or time.time() > action['expires']):
                    raise ValueError('MCP action was not authorized, expired, or its task stopped.')
                from hanni.native.tool_access import reconcile_action
                current_action = reconcile_action(store, action)
                if current_action['state'] == 'rejected':
                    return current_action['receipt']
                current = next((tool for tool in self.tools()['tools'] if tool == action['spec']), None)
                if current is None:
                    raise ValueError('MCP tool was disabled or its approved definition changed.')
                registry = self.hub.controller_registry
                definition = registry.get(current['remote']['capability_id'])
                # The unique row survives HTTP loss and dashboard restarts.
                store.db.execute('CREATE TABLE IF NOT EXISTS native_mcp_calls(id TEXT PRIMARY KEY)')
                store.db.commit()
                with store.transaction():
                    claimed = store.db.execute('INSERT OR IGNORE INTO native_mcp_calls VALUES (?)', (action_id,)).rowcount
                if not claimed:
                    return {'ok': False, 'error': 'MCP execution was already claimed. Review its receipt; no effect was replayed.'}
                try:
                    result = registry.execute(ToolRequest(definition.name, action['arguments'], confirmed=True,
                        source='native-mcp', correlation_id=action_id,
                        expected_definition=definition)).to_dict()
                    # Native evidence packages are bounded independently of SDK results.
                    if len(json.dumps(result)) > 24000:
                        result = {'ok': result['ok'], 'message': result['message'][:12000],
                                  'data': {'truncated': True}, 'approved_by': 'mcp_tool_policy'}
                    else:
                        result['approved_by'] = 'mcp_tool_policy'
                    store.settle(action_id, 'fulfilled', result)
                    return result
                except Exception as exc:
                    from hanni.native.runtime import error_receipt
                    result = error_receipt(exc, dispatched=True)
                    store.settle(action_id, 'uncertain', result)
                    return result
            finally:
                store.close()
