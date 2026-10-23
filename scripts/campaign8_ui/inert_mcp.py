"""One inert initialization dependency; original manager retains all authority."""
from copy import deepcopy
from unittest.mock import patch
NAME = 'Controlled approved inert integration'
COMMAND = 'campaign8-inert-provider-no-launch.exe'
TOOL_NAME = 'controlled_metadata_read'
TOOL = {'name': TOOL_NAME, 'description': 'Synthetic metadata only. The fixture refuses every tool invocation.', 'inputSchema': {'type': 'object', 'properties': {'label': {'type': 'string', 'description': 'Synthetic label; never sent to a provider.'}}, 'required': ['label'], 'additionalProperties': False}, 'outputSchema': {'type': 'object', 'properties': {'label': {'type': 'string'}}, 'required': ['label'], 'additionalProperties': False}, 'annotations': {'readOnlyHint': True}, '_meta': {'fixture': 'controlled synthetic metadata; no external implementation'}}

def configure(backend, *, tool_metadata=False):
    manager = backend.server.mcp.require()
    if tool_metadata:
        manager.attach_registry(backend.registry)

    class InertRuntime:
        """The controlled connection uses no asyncio SDK or socketpair."""

        def close(self):
            pass

    class InertConnection:

        def __init__(self, runtime, config, **kwargs):
            self.allowed = not (config['name'] != NAME or config['command'] != COMMAND or config['transport'] != 'stdio' or config['args'] or config['env_refs'] or config['auto_connect'] or (config['auth']['type'] != 'none'))
            self.closed = False
            backend.calls.append({'dependency': 'inert MCP initialization', 'outcome': 'CONTROLLED_MOCK', 'scope': 'No SDK/process/network/credential access.'})

        def wait_ready(self):
            if self.closed or not self.allowed:
                raise OSError('Only the exact inert campaign initialization fixture exists.')

        def request(self, operation, *args, **kwargs):
            if operation != 'list' or self.closed or (not self.allowed):
                raise OSError('No external tool execution or arbitrary operation exists.')
            backend.calls.append({'dependency': 'inert MCP list', 'outcome': 'CONTROLLED_MOCK'})
            return deepcopy([TOOL]) if tool_metadata else []

        def cancel_tools(self, names):
            if set(names) - {TOOL_NAME} or not tool_metadata:
                raise OSError('Only cancellation of the fixed synthetic metadata tool exists.')
            backend.calls.append({'dependency': 'inert MCP cancel_tools', 'outcome': 'CONTROLLED_MOCK'})

        def close(self):
            self.closed = True
    manager.connection_factory = InertConnection
    server = manager.add({'name': NAME, 'transport': 'stdio', 'command': COMMAND, 'args': [], 'auto_connect': False, 'timeout_seconds': 3})
    with patch('hanni.mcp.manager.AsyncRuntime', InertRuntime):
        manager.connect(server['id'], approved=True, expected_config_hash=server['config_hash'])
    if not tool_metadata:
        manager.disable_server(server['id'])
    return {'server_id': server['id'], 'name': NAME, 'source': 'Original manager.add/connect(approved=True, matching hash)/disable_server', 'scope': 'CONTROLLED initialization leaf only; no live SDK/provider or imported-tool execution.', 'snapshot': deepcopy(manager.snapshot())}
