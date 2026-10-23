"""Input-only original implementation executor for isolated C9 security tests.

Only fixture providers are mocked. Registered handlers, the registry, MCP host,
manager and sessions are original. This module does not consult expected answers.
"""
from __future__ import annotations
from contextlib import contextmanager, ExitStack
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch
REPO = Path(__file__).resolve().parents[2]

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class EmptyVault:

    def get(self, account):
        return None

    def accounts(self):
        return ()

    def get_password(self, service, key):
        return None

def fixture_config(root):
    from hanni.config.schema import AppConfig, HanniConfig, Paths, PrivacyConfig, parse_models, parse_permissions
    permissions = parse_permissions({'levels': [{'level': n, 'name': f'level{n}', 'description': 'Synthetic audit policy', 'auto_approve_allowed': n < 3} for n in range(4)], 'profiles': {'owner': {'max_auto_approve_level': 2, 'chat_only': False}, 'observer': {'max_auto_approve_level': 0, 'chat_only': False}, 'everyone_else': {'max_auto_approve_level': -1, 'chat_only': True}, 'denied': {'max_auto_approve_level': -1, 'chat_only': True}}})
    models = parse_models({'models': [{'id': 'synthetic-supervisor', 'role': 'supervisor', 'backend': 'llama.cpp', 'model_file': str(root / 'NOT_A_MODEL.gguf'), 'endpoint': 'http://127.0.0.1:1', 'keep_loaded': False}]})
    return AppConfig(HanniConfig(), models, permissions, PrivacyConfig(), Paths(root / 'config', root))

@contextmanager
def environment(root):
    from hanni.tools.google_access import GoogleAccess
    from hanni.tools.registry import build_default_registry
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    state = SimpleNamespace(leaf_calls=[], entries=[], registry=None, config=fixture_config(root))
    original_google = GoogleAccess.__init__

    def google_init(instance, vault=None, transport=None, timezone_name=None):
        original_google(instance, vault=EmptyVault(), transport=transport, timezone_name=timezone_name)

    def forbidden(*args, **kwargs):
        state.leaf_calls.append({'leaf': 'forbidden_external', 'dispatched': False})
        raise PermissionError('Campaign fixture forbids OS or network dispatch.')
    with ExitStack() as stack:
        stack.enter_context(patch.object(GoogleAccess, '__init__', google_init))
        stack.enter_context(patch.object(socket.socket, 'connect', forbidden))
        stack.enter_context(patch.object(subprocess, 'Popen', forbidden))
        stack.enter_context(patch.object(subprocess, 'run', forbidden))
        state.registry = build_default_registry(state.config)
        state.registry.context.reliability = None
        yield state

@contextmanager
def entered(handler, state):
    code = getattr(handler, '__code__', None)
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if event == 'call' and frame.f_code is code:
            state.entries.append({'module': handler.__module__, 'function': handler.__name__})
    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(previous)

def invoke(registry, request, state):
    try:
        definition = registry.get(request.name)
        with entered(definition.handler, state):
            return {'returned': registry.execute(request).to_dict(), 'exception': None}
    except Exception as exc:
        return {'returned': None, 'exception': {'type': type(exc).__name__, 'message': str(exc)}}

def model_value(schema):
    if 'enum' in schema:
        return deepcopy(schema['enum'][0])
    kind = schema.get('type', 'string')
    if isinstance(kind, list):
        kind = next((k for k in kind if k != 'null'), 'string')
    if kind == 'object':
        return {k: model_value(schema.get('properties', {}).get(k, {})) for k in schema.get('required', [])}
    if kind == 'array':
        return []
    if kind == 'boolean':
        return False
    if kind in {'integer', 'number'}:
        return schema.get('minimum', 1)
    return 'synthetic' + 'x' * max(0, schema.get('minLength', 1) - 9)

def valid_shape(definition):
    schema = definition.argument_schema()
    return {key: model_value(schema['properties'][key]) for key in schema.get('required', [])}

def inventory(state):
    from hanni.mcp.host import McpHost
    host = McpHost(state.registry)
    return [{'id': d.name, 'module': d.handler.__module__, 'permission_level': d.permission_level, 'risk_level': d.risk_level, 'side_effect': d.side_effect, 'default_model_exposed': host._allowed(d), 'argument_schema': d.argument_schema(), 'confirmation_dynamic': d.requires_confirmation_if is not None, 'source_sha256': digest(Path(sys.modules[d.handler.__module__].__file__))} for d in state.registry.definitions()]

def own_path(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Fixture path escapes its owned root.')
    return path

def substitute(value, root):
    if isinstance(value, str):
        return value.replace('{root}', str(root))
    if isinstance(value, dict):
        return {k: substitute(v, root) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, root) for v in value]
    return value

def owned_arguments(name, arguments, root):
    """Fixture isolation only; not evidence of a production permission denial."""
    if not name.startswith(('file.', 'folder.', 'archive.')):
        return
    for key in ('path', 'source', 'destination', 'left', 'right', 'root'):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            path = Path(value).expanduser().resolve()
            if not path.is_relative_to(root):
                raise ValueError('HARNESS_ISOLATION: tool path is outside the disposable root.')

def _synthetic_tool(description='Read the synthetic ledger.'):
    return {'name': 'fixture.observe', 'description': description, 'inputSchema': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'additionalProperties': False}, 'outputSchema': {'type': 'object', 'properties': {'value': {'type': 'string'}}, 'required': ['value'], 'additionalProperties': False}, 'annotations': {'readOnlyHint': True}}

class ControlledConnection:
    """Explicit inert MCP transport leaf; original manager gates are retained."""

    def __init__(self, runtime, config, *, changed=None, env=None, vault=None, state=None, case=None):
        self.config, self.state, self.case = (config, state, case)
        self.closed, self.protected_values = (False, ())

    def wait_ready(self):
        from hanni.mcp.security import resolve_credentials
        child, headers = resolve_credentials(self.config, env=self.case.get('synthetic_env', {}), vault=EmptyVault())
        self.protected_values = tuple(child.values()) + tuple((v.removeprefix('Bearer ') for v in headers.values()))

    def request(self, method, arguments=None):
        if method == 'list':
            return deepcopy(self.case.get('definitions', [_synthetic_tool(self.case.get('description', 'Read the synthetic ledger.'))]))
        arguments['admit']()
        self.state.leaf_calls.append({'leaf': 'mock_mcp_rpc', 'name': arguments['name'], 'dispatched': True, 'mode': 'CONTROLLED_MOCK', 'synthetic_credential_in_arguments': any((value in json.dumps(arguments['arguments']) for value in self.case.get('synthetic_env', {}).values()))})
        action = self.case.get('controls', {}).get('during_call')
        if action:
            self.state.revoke(action)
        fault = self.case.get('controls', {}).get('fault')
        if fault == 'timeout':
            raise TimeoutError('Synthetic MCP timeout.')
        if fault == 'disconnection':
            self.closed = True
            raise ConnectionError('Synthetic MCP disconnect.')
        return deepcopy(self.case.get('result', {'content': [{'type': 'text', 'text': 'Synthetic ledger observation.'}], 'structuredContent': {'value': 'synthetic'}}))

    def signal_close(self):
        self.closed = True

    def close(self):
        self.closed = True

    def cancel_tools(self, names):
        pass

def mcp_case(case, state):
    from hanni.mcp.manager import MCPManager
    from hanni.mcp.host import McpHost
    from hanni.tools.base import ToolRequest

    def factory(*args, **kwargs):
        return ControlledConnection(*args, **kwargs, state=state, case=case)

    class NoRuntime:
        """The inert transport does not need an SDK event loop or sockets."""

        def close(self):
            pass
    runtime_patch = patch('hanni.mcp.manager.AsyncRuntime', NoRuntime)
    runtime_patch.start()
    manager = MCPManager(state.config.paths.data_dir, state.registry, connection_factory=factory, env=case.get('synthetic_env', {}), vault=EmptyVault())
    try:
        config = case.get('mcp_config', {'name': 'Synthetic security fixture', 'transport': 'streamable_http', 'url': 'http://127.0.0.1:49191/mcp', 'allow_local_http': True, 'auto_connect': False})
        added = manager.add(config)
        if case['operation'] == 'mcp_connect_denied':
            return manager.connect(added['id'], approved=case.get('approved', False), expected_config_hash=case.get('config_hash'))
        connected = manager.connect(added['id'], approved=True, expected_config_hash=added['config_hash'])['servers'][-1]
        tool = connected['tools'][0]
        approval = {'original_name': tool['original_name'], 'definition_hash': tool['definition_hash'], 'classification': case.get('classification', 'read_only')}
        if case['operation'] == 'mcp_approval_rejected':
            approval['definition_hash'] = '0' * 64
        manager.approve_tools(connected['id'], [approval])
        definition = state.registry.get(tool['internal_id'])
        host = McpHost(state.registry)
        menu = host._as_tool(definition)

        def revoke(action):
            if action == 'disable_tool':
                manager.disable_tools(connected['id'], [tool['original_name']])
            elif action == 'disable_server':
                manager.disable_server(connected['id'])
            elif action == 'stop':
                from hanni.core.shutdown import Actor, StopSource
                state.registry.context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('synthetic-audit'), reason='Synthetic stop.')
        state.revoke = revoke
        before = case.get('controls', {}).get('before_call')
        if before:
            revoke(before)
        if case['operation'] == 'mcp_stale_definition':
            case['definitions'] = [_synthetic_tool('Changed synthetic observation contract.')]
            manager.refresh(connected['id'])
            current = manager.snapshot()['servers'][-1]['tools'][0]
            manager.approve_tools(connected['id'], [{'original_name': current['original_name'], 'definition_hash': current['definition_hash'], 'classification': 'read_only'}])
        if case.get('via', 'host') == 'registry':
            return invoke(state.registry, ToolRequest(tool['internal_id'], case.get('arguments', {}), actor_profile=case.get('actor_profile', 'owner'), confirmed=case.get('confirmed', False)), state)
        return host.call(menu, case.get('arguments', {}))
    finally:
        manager.close()
        runtime_patch.stop()

def run_case(case, root):
    """No expected/oracle keys are read. Returns original receipts and effects."""
    from hanni.tools.base import ToolRequest
    from hanni.mcp.host import McpHost
    root = Path(root).resolve()
    with environment(root) as state:
        case = substitute(deepcopy(case), root)
        owned_arguments(case.get('tool_name', ''), case.get('arguments', {}), root)
        owned_arguments(case.get('tool_name', ''), case.get('fixed_arguments', {}), root)
        for proposal in case.get('model_calls', []):
            owned_arguments(proposal['name'].removeprefix('hanni__').replace('__', '.'), proposal.get('arguments', {}), root)
        for item in case.get('synthetic_files', []):
            path = own_path(root, item['name'])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item['text'], encoding='utf-8')
        before = {str(p.relative_to(root)): digest(p) for p in root.rglob('*') if p.is_file()}
        operation = case['operation']
        try:
            if operation in {'mcp_call', 'mcp_connect_denied', 'mcp_approval_rejected', 'mcp_stale_definition'}:
                response = mcp_case(case, state)
            elif operation in {'registry_gate', 'filesystem'}:
                if case.get('controls', {}).get('stop'):
                    from hanni.core.shutdown import Actor, StopSource
                    state.registry.context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('synthetic-audit'), reason='Synthetic stop.')
                guard = None
                if case.get('controls', {}).get('dispatch_guard_change'):

                    def guard():
                        change = case['controls']['dispatch_guard_change']
                        if change == 'stop':
                            from hanni.core.shutdown import Actor, StopSource
                            state.registry.context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('synthetic-guard'), reason='Synthetic last-boundary stop.')
                        elif change == 'permission':
                            permissions = state.registry.context.permissions
                            state.registry.context.permissions = replace(permissions, profiles={**permissions.profiles, 'owner': permissions.profiles['denied']})
                request = ToolRequest(case['tool_name'], case.get('arguments', {}), actor_profile=case.get('actor_profile', 'owner'), confirmed=case.get('confirmed', False), source='campaign9.synthetic', execution_guard=guard)
                response = invoke(state.registry, request, state)
            elif operation in {'host_call', 'host_prepare'}:
                host = McpHost(state.registry, **case.get('host_policy', {}))
                definition = state.registry.get(case['tool_name'])
                with entered(definition.handler, state):
                    menu = host._as_tool(definition, fixed_arguments=case.get('fixed_arguments'))
                    response = host.call(menu, case.get('arguments', {})) if operation == 'host_call' else {'prepared': host.prepare_call(menu, case.get('arguments', {})).name}
            elif operation == 'mcp_endpoint':
                from hanni.mcp.security import endpoint

                def resolver(host, port, **kwargs):
                    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port)) for ip in case.get('dns_answers', [])]
                response = {'endpoint': endpoint(case['url'], allow_local_http=case.get('allow_local_http', False), resolve=case.get('resolve', False), resolver=resolver)}
            elif operation == 'mcp_schema':
                from hanni.mcp.security import validate_schema
                response = {'schema': validate_schema(case['schema'])}
            elif operation == 'confirmation_session':
                from hanni.tools.session import ToolAwareSession
                from hanni.tools import powershell

                class Fallback:

                    def stream_response(self, prompt, **kwargs):
                        yield 'Controlled fallback: no operation requested.'

                def shell_leaf(command, **kwargs):
                    state.leaf_calls.append({'leaf': 'mock_powershell', 'dispatched': True, 'command_sha256': hashlib.sha256(command[-1].encode()).hexdigest(), 'mode': 'CONTROLLED_MOCK'})
                    return SimpleNamespace(returncode=0, stdout='Synthetic shell receipt', stderr='')
                session = ToolAwareSession(Fallback(), state.registry)
                with patch.object(powershell.subprocess, 'run', shell_leaf):
                    first = list(session.stream_response('run powershell command: Write-Output synthetic-fixture'))
                    if case.get('controls', {}).get('revoke_profile'):
                        permissions = state.registry.context.permissions
                        state.registry.context.permissions = replace(permissions, profiles={**permissions.profiles, 'owner': permissions.profiles['denied']})
                    followups = [list(session.stream_response(text)) for text in case.get('followups', [])]
                response = {'first': first, 'followups': followups, 'pending': session._pending_confirmation is not None}
                session.close()
            elif operation == 'controller_turn':
                from hanni.mcp.session import McpToolSession
                from hanni.models.client import ModelTurn, ModelToolCall

                class Fallback:
                    history = ()

                    def build_messages(self, prompt, system_suffix=''):
                        return [{'role': 'system', 'content': system_suffix}, {'role': 'user', 'content': prompt}]

                    def record_turn(self, prompt, answer):
                        pass

                    def stream_response(self, prompt, **kwargs):
                        yield 'Controlled fallback: no tool proposal.'

                class Client:

                    def __init__(self):
                        self.calls = []

                    def complete_with_tools(self, messages, tools, **kwargs):
                        self.calls.append({'messages': deepcopy(messages), 'tools': deepcopy(tools)})
                        index = len(self.calls) - 1
                        if index < len(case.get('model_calls', [])):
                            raw = case['model_calls'][index]
                            return ModelTurn('', (ModelToolCall('synthetic-call-' + str(index), raw['name'], raw.get('arguments', {})),))
                        return ModelTurn('Controlled final fixture response.', ())

                    def chat(self, messages, **kwargs):
                        return 'Controlled bounded fixture response.'
                host = McpHost(state.registry, **case.get('host_policy', {}))
                client = Client()
                session = McpToolSession(Fallback(), client, host, max_rounds=3)
                response = {'answer': list(session.stream_response(case['prompt'])), 'controlled_model_messages': client.calls, 'trace': session.last_trace}
            else:
                raise ValueError('Unsupported input-only operation.')
        except Exception as exc:
            response = {'exception': {'type': type(exc).__name__, 'message': str(exc)}}
        after = {str(p.relative_to(root)): digest(p) for p in root.rglob('*') if p.is_file()}
        return {'id': case['id'], 'operation': operation, 'evidence_class': 'CONTROLLED', 'response': response, 'handler_entries': state.entries, 'leaf_effects': state.leaf_calls, 'files_before': before, 'files_after': after, 'capabilities': inventory(state)}
