"""Original services in disposable roots, with explicit unsafe leaf fixtures.

No inference, owner configuration, Google credential vault or real OS action is
used by the default executor. Root may supply an admitted genuine session via
``session_factory``. Input actions are contracts, never semantic model answers.
"""
from __future__ import annotations
from contextlib import contextmanager, ExitStack
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid5
DIMENSIONS = ('intent', 'retrieved_context', 'tools', 'arguments', 'authorization', 'execution', 'outcome_verification', 'final_response', 'latency', 'recovery')
REPO = Path(__file__).resolve().parents[2]
NAMESPACE = UUID('40cd3804-84c1-4e35-88ea-c9bbb0e07e59')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def owned(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError('HARNESS_ISOLATION: path escapes disposable root.')
    return path

def substitute(value, root, results):
    if isinstance(value, dict):
        if set(value) == {'$ref'}:
            parts = value['$ref'].split('/')
            current = results[parts[0]]
            for part in parts[1:]:
                current = current[int(part)] if isinstance(current, list) else current[part]
            return deepcopy(current)
        return {key: substitute(child, root, results) for key, child in value.items()}
    if isinstance(value, list):
        return [substitute(child, root, results) for child in value]
    return value.replace('{root}', str(root)) if isinstance(value, str) else value

def fixture_config(root):
    from hanni.config.schema import AppConfig, HanniConfig, Paths, PrivacyConfig, parse_models, parse_permissions
    permissions = parse_permissions({'levels': [{'level': n, 'name': 'fixture' + str(n), 'description': 'Owned development', 'auto_approve_allowed': n < 3} for n in range(4)], 'profiles': {'owner': {'max_auto_approve_level': 2, 'chat_only': False}, 'observer': {'max_auto_approve_level': 0, 'chat_only': False}, 'everyone_else': {'max_auto_approve_level': -1, 'chat_only': True}}})
    models = parse_models({'models': [{'id': 'c10-unavailable-supervisor', 'role': 'supervisor', 'backend': 'llama.cpp', 'model_file': str(root / 'unavailable.gguf'), 'endpoint': 'http://127.0.0.1:1', 'keep_loaded': False}]})
    return AppConfig(HanniConfig(), models, permissions, PrivacyConfig(), Paths(root / 'config', root))

class EmptyVault:

    def get(self, account):
        return None

    def accounts(self):
        return ()

    def get_password(self, service, key):
        return None

class NoInferenceClient:

    def stream_chat(self, *args, **kwargs):
        raise RuntimeError('ACTUAL_INFERENCE_NOT_AUTHORIZED: no synthetic assistant answer.')
        yield

    def complete_with_tools(self, *args, **kwargs):
        raise RuntimeError('ACTUAL_INFERENCE_NOT_AUTHORIZED: no synthetic model tool choice.')

def inventory(registry):
    from hanni.mcp.host import McpHost
    host = McpHost(registry)
    return [{'id': d.name, 'module': d.handler.__module__, 'permission_level': d.permission_level, 'risk_level': d.risk_level, 'side_effect': d.side_effect, 'model_default_eligible': host._allowed(d), 'argument_schema': d.argument_schema(), 'output_schema': dict(d.output_schema), 'source_sha256': digest(sys.modules[d.handler.__module__].__file__)} for d in registry.definitions()]

def file_snapshot(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if not p.is_file():
            continue
        key = p.relative_to(root).as_posix()
        try:
            result[key] = {'sha256': digest(p), 'bytes': p.stat().st_size}
        except PermissionError:
            result[key] = {'sha256': None, 'bytes': p.stat().st_size, 'unreadable': 'PermissionError', 'content_verified': False}
    return result

@contextmanager
def environment(root, *, connection_authorizer=None, config=None):
    from hanni.tools.google_access import GoogleAccess
    from hanni.tools.registry import build_default_registry
    from hanni.dashboard.features import DesktopFeatures
    from hanni.mcp.host import McpHost
    from hanni.reliability.execution import close_service
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if config is not None and Path(config.paths.data_dir).resolve() != root:
        raise ValueError('Provided original configuration must use the exact disposable data directory.')
    state = SimpleNamespace(root=root, config=config or fixture_config(root), calls=[], effects=[], model_call_count=0, registry=None, features=None, lab=None, managers=[], entries=[], fixture_prerequisites=[], session_metadata=None, cleanup={'temporary_storage_scope': str(root), 'original_services_closed': False})
    google_init = GoogleAccess.__init__

    def init(instance, vault=None, transport=None, timezone_name=None):
        google_init(instance, vault=EmptyVault(), transport=transport, timezone_name=timezone_name)

    def denied(*args, **kwargs):
        state.effects.append({'leaf': 'denied_external', 'dispatched': False})
        raise PermissionError('CONTROLLED: external OS/network action is unavailable.')
    original_connect = socket.socket.connect

    def connect(sock, address):
        if connection_authorizer is not None and connection_authorizer(address) is True:
            return original_connect(sock, address)
        return denied(sock, address)
    with ExitStack() as stack:
        stack.enter_context(patch.object(GoogleAccess, '__init__', init))
        stack.enter_context(patch.object(socket.socket, 'connect', connect))
        stack.enter_context(patch.object(subprocess, 'Popen', denied))
        stack.enter_context(patch.object(subprocess, 'run', denied))
        state.registry = build_default_registry(state.config)
        state.features = DesktopFeatures(state.config, registry=state.registry)
        settings = state.config.hanni.mcp
        state.host = McpHost(state.registry, read_only=settings.read_only, max_tools=settings.max_tools_per_turn, allowed_actions=settings.allowed_actions)
        try:
            yield state
        finally:
            if hasattr(state, 'session'):
                from hanni.cli import _close_interactive_session
                _close_interactive_session(state.session, registry=state.registry)
            if hasattr(state, 'workflow_facade'):
                state.workflow_facade.close()
            if hasattr(state, 'mcp_facade'):
                state.mcp_facade.close()
            if hasattr(state, 'controller_telemetry'):
                state.controller_telemetry.close()
            if state.lab is not None:
                state.lab.close()
            for manager in state.managers:
                manager.close()
            from hanni.laya.runtime import stop_advisory
            stop_advisory(state.config)
            close_service(root)
            state.cleanup['original_services_closed'] = True

def _validate_setup(setup, action_ids=()):
    """Validate fixture declarations before any fixture effect, not against answers."""
    if not isinstance(setup, dict):
        raise ValueError('Fixture setup must be an object.')
    known = {'files', 'calendar_cache', 'projects', 'tasks', 'memories', 'mcp_records', 'mcp', 'desktop_records'}
    for key in known - {'files', 'mcp'}:
        if key in setup and (not isinstance(setup[key], list)):
            raise ValueError('Fixture ' + key + ' must be an array.')
    files = setup.get('files', {})
    if not isinstance(files, dict) or any((not isinstance(k, str) or not isinstance(v, str) for k, v in files.items())):
        raise ValueError('File fixtures must map owned relative names to text.')
    bindings = set(action_ids)
    for family in ('projects', 'tasks', 'memories'):
        for index, row in enumerate(setup.get(family, [])):
            if not isinstance(row, dict) and (not (family == 'memories' and isinstance(row, str))):
                raise ValueError('Fixture ' + family + ' records must be objects.')
            default = ('memory' if family == 'memories' else family) + '-seed-' + str(index)
            binding = row.get('bind', default) if isinstance(row, dict) else default
            if not isinstance(binding, str) or not binding or binding in bindings:
                raise ValueError('Fixture bindings must be unique nonempty strings, distinct from action IDs.')
            bindings.add(binding)
    for action in setup.get('desktop_records', []):
        if not isinstance(action, dict) or not isinstance(action.get('id'), str) or (not action['id']):
            raise ValueError('Desktop fixture actions need a nonempty ID.')
        if action['id'] in bindings:
            raise ValueError('Fixture bindings must be unique and distinct from action IDs.')
        bindings.add(action['id'])
    fixture = setup.get('mcp')
    if fixture is not None:
        if not isinstance(fixture, dict) or set(fixture) - {'records', 'configured', 'connection_approved', 'tools_approved'}:
            raise ValueError('Unsupported inert MCP fixture contract; arbitrary providers are not initialized.')
        for key in ('configured', 'connection_approved', 'tools_approved'):
            if key in fixture and type(fixture[key]) is not bool:
                raise ValueError('Inert MCP fixture approval and configuration flags must be exact booleans.')
        if 'records' in fixture and (not isinstance(fixture['records'], list)):
            raise ValueError('Inert MCP fixture records must be an array.')
        if fixture.get('configured') is True:
            names = ['mcp-fixture-add']
            if fixture.get('connection_approved') is True:
                names.append('mcp-fixture-connect')
                if fixture.get('tools_approved') is True:
                    names.append('mcp-fixture-approve')
            if bindings.intersection(names):
                raise ValueError('Fixture bindings must be distinct from original MCP setup IDs.')
    return sorted(set(setup) - known)

def seed(state, setup):
    unsupported = _validate_setup(setup)
    state.fixture_prerequisites = [{'fixture': key, 'status': 'NOT_APPLIED', 'reason': 'This Core adapter has no original-service fixture initializer for this declaration.'} for key in unsupported]
    for relative, contents in setup.get('files', {}).items():
        path = owned(state.root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding='utf-8', newline='\n')
    for row in setup.get('calendar_cache', []):
        state.features.store.save_calendar_cache(row['key'], deepcopy(row['payload']))
    results = {}
    for family, operation in [('projects', 'project.create'), ('tasks', 'task.create')]:
        for index, row in enumerate(setup.get(family, [])):
            ident = family + '-seed-' + str(index)
            args = {k: v for k, v in row.items() if k != 'bind'}
            item = dispatch(state, {'id': ident, 'target': 'desktop', 'name': operation, 'arguments': args}, results, 'setup')
            if item['error']:
                raise ValueError('Original ' + family + ' fixture seed failed.')
            results[row.get('bind', ident)] = item
    if setup.get('memories'):
        store = state.features.memory_store()
        for index, row in enumerate(setup['memories']):
            args = dict(row) if isinstance(row, dict) else {'content': row}
            binding = args.pop('bind', 'memory-seed-' + str(index))
            record, created = store.remember(**substitute(args, state.root, results))
            results[binding] = {'result': record.to_dict(), 'created': created, 'error': None, 'scope': 'Original synthetic fixture persistence, not recalled context'}
    if 'mcp_records' in setup:
        state.mcp_records = deepcopy(setup['mcp_records'])
        state.mcp_calls = []
    if 'mcp' in setup:
        fixture = setup['mcp']
        if not isinstance(fixture, dict) or set(fixture) - {'records', 'configured', 'connection_approved', 'tools_approved'}:
            raise ValueError('Unsupported inert MCP fixture contract; arbitrary providers are not initialized.')
        state.mcp_records = deepcopy(fixture.get('records', []))
        state.mcp_calls = []
        if fixture.get('configured') is True:
            row = dispatch(state, {'id': 'mcp-fixture-add', 'target': 'mcp', 'name': 'add'}, results, 'setup')
            results['mcp-fixture-add'] = row
            if row['error']:
                raise ValueError('Original inert MCP configuration failed.')
            if fixture.get('connection_approved') is True:
                config = row['result']
                row = dispatch(state, {'id': 'mcp-fixture-connect', 'target': 'mcp', 'name': 'connect', 'arguments': {'server_id': config['id'], 'config_hash': config['config_hash'], 'approved': True}}, results, 'setup')
                results['mcp-fixture-connect'] = row
                if row['error']:
                    raise ValueError('Original reviewed inert MCP connection failed.')
                if fixture.get('tools_approved') is True:
                    row = dispatch(state, {'id': 'mcp-fixture-approve', 'target': 'mcp', 'name': 'approve', 'arguments': {'server_id': config['id'], 'tools': row['result']['servers'][0]['tools']}}, results, 'setup')
                    results['mcp-fixture-approve'] = row
                    if row['error']:
                        raise ValueError('Original inert tool approval failed.')
    for action in setup.get('desktop_records', []):
        result = dispatch(state, action, results, 'setup')
        if result['error']:
            raise ValueError('Fixture seed failed: ' + result['error']['type'])
        results[action['id']] = result
    return results

@contextmanager
def platform_dependencies(state, name, arguments, controls):
    """Existing original OS fixture adapters; no handler is substituted."""
    from scripts.campaign2.platform_cases import PlatformCase
    from scripts.campaign2.platform_fixtures import Proxy
    from hanni.tools import system
    from hanni.models.resource_manager import ResourceSnapshot
    definition = state.registry.get(name)
    with ExitStack() as stack:
        if controls.get('fault') == 'ENOSPC':
            import errno
            target = owned(state.root, arguments['path'])
            original_write = Path.write_text

            def full(path, *args, **kwargs):
                if path.resolve() == target:
                    state.effects.append({'leaf': 'Path.write_text', 'fault': 'ENOSPC', 'path': str(target)})
                    raise OSError(errno.ENOSPC, 'Owned controlled disk-full condition')
                return original_write(path, *args, **kwargs)
            stack.enter_context(patch.object(Path, 'write_text', full))
        if name.startswith(('app.', 'ui.', 'browser.', 'service.', 'folder.')):
            fixture = PlatformCase(definition, state.root, arguments, 'MOCK')
            stack.enter_context(fixture.deps(arguments, controlled=True, unavailable=bool(controls.get('unavailable')), noop=bool(controls.get('noop'))))
            import hanni.tools.windows as windows
            stack.enter_context(patch.object(windows, '_shortcut_roots', lambda: ()))
            yield (lambda: deepcopy(fixture.state.calls))
            return
        resources = controls.get('resources', {'cpu_percent': 37.5, 'ram_total_gb': 32, 'ram_used_gb': 20, 'ram_percent': 62.5, 'gpus': ()})
        if name == 'system.stats':
            snap = ResourceSnapshot(**resources)
            stack.enter_context(patch.object(system, 'snapshot_resources', lambda **_: snap))
        if name == 'system.battery':
            battery = None if controls.get('unavailable') else SimpleNamespace(percent=controls.get('percent', 68), power_plugged=controls.get('plugged', False), secsleft=5400)
            stack.enter_context(patch.object(system, 'psutil', Proxy(system.psutil, sensors_battery=lambda: battery)))
        if name in {'process.top_memory', 'process.list'}:
            rows = controls.get('processes', [{'pid': 910001, 'name': 'fixture-editor.exe', 'rss': 3 * 1024 ** 3}, {'pid': 910002, 'name': 'fixture-editor.exe', 'rss': 1024 ** 3}, {'pid': 910003, 'name': 'fixture-renderer.exe', 'rss': 2 * 1024 ** 3}])
            procs = [SimpleNamespace(pid=r['pid'], info={'pid': r['pid'], 'name': r['name'], 'memory_info': SimpleNamespace(rss=r['rss']), 'memory_percent': r['rss'] * 100 / (32 * 1024 ** 3)}) for r in rows]
            stack.enter_context(patch.object(system, 'psutil', Proxy(system.psutil, process_iter=lambda *args: iter(procs), virtual_memory=lambda: SimpleNamespace(total=32 * 1024 ** 3))))
        yield (lambda: [])

def _path_arguments(root, name, arguments):
    if name.startswith(('file.', 'folder.', 'archive.')):
        for key in ('path', 'root', 'source', 'destination', 'left', 'right', 'archive'):
            value = arguments.get(key)
            if isinstance(value, str) and value.strip():
                owned(root, value)

def _entered(registry, callback, state):
    codes = {}
    for definition in registry.definitions():
        codes.setdefault(getattr(definition.handler, '__code__', None), set()).add(definition.name)
    prior = sys.getprofile()

    def profile(frame, event, arg):
        if event == 'call':
            request = frame.f_locals.get('request', frame.f_locals.get('_request'))
            name = getattr(request, 'name', None)
            try:
                bound = registry.get(name) if isinstance(name, str) else None
            except Exception:
                bound = None
            exact = bound is not None and getattr(bound.handler, '__code__', None) is frame.f_code
            if not exact and frame.f_code not in codes:
                return
            state.entries.append({'tool': name if exact else sorted(codes[frame.f_code]), 'module': frame.f_globals.get('__name__'), 'arguments': deepcopy(frame.f_locals.get('args', frame.f_locals.get('arguments', {}))), 'confirmed': getattr(request, 'confirmed', None), 'exact_registered_binding': exact})
    sys.setprofile(profile)
    try:
        return callback()
    finally:
        sys.setprofile(prior)

def _lab(state):
    if state.lab is None:
        from hanni.evals.model_lab import ModelLab
        state.lab = ModelLab(state.config, None, registry=state.registry)
    return state.lab

def _mcp(state):
    """Original manager/gates over an explicitly inert unfamiliar provider."""
    if hasattr(state, 'mcp_manager'):
        return state.mcp_manager
    from hanni.mcp.manager import MCPManager

    class InertRuntime:

        def close(self):
            pass

    class PartsBinConnection:

        def __init__(self, runtime, config, **kwargs):
            self.closed = False
            self.protected_values = ()

        def wait_ready(self):
            pass

        def close(self):
            self.closed = True

        def cancel_tools(self, names):
            pass

        def request(self, operation, name=None, arguments=None, **kwargs):
            if operation == 'list':
                return [{'name': 'parts_bin.inspect', 'description': 'Read synthetic local parts stock for one bin; provenance is fixture provider.', 'inputSchema': {'type': 'object', 'properties': {'bin': {'type': 'string'}}, 'required': ['bin'], 'additionalProperties': False}, 'outputSchema': {'type': 'object', 'properties': {'records': {'type': 'array', 'items': {'type': 'object'}}, 'total': {'type': 'integer'}}, 'required': ['records', 'total'], 'additionalProperties': False}, 'annotations': {'readOnlyHint': True}}]
            if operation != 'call':
                raise ValueError('Unknown inert provider operation.')
            if isinstance(name, dict):
                payload = name
                name, arguments = (payload['name'], payload['arguments'])
                kwargs = {**kwargs, 'admit': payload.get('admit')}
            admit = kwargs.get('admit')
            if admit is not None:
                admit()
            state.mcp_calls.append({'name': name, 'arguments': deepcopy(arguments)})
            records = [row for row in state.mcp_records if row['bin'] == arguments['bin']]
            return {'content': [{'type': 'text', 'text': 'Synthetic provider returned matching stock records.'}], 'structuredContent': {'records': records, 'total': sum((r['quantity'] for r in records))}}
    with patch('hanni.mcp.manager.AsyncRuntime', InertRuntime):
        manager = MCPManager(state.root, state.registry, connection_factory=PartsBinConnection, env={}, vault=EmptyVault())
    manager.campaign_runtime_factory = InertRuntime
    state.mcp_manager = manager
    state.managers.append(manager)
    return manager

def dispatch(state, action, results, case_id):
    from hanni.tools.base import ToolRequest
    arguments = substitute(action.get('arguments', {}), state.root, results)
    target = action['target']
    name = action.get('name', '')
    started = time.perf_counter()
    entry_start = len(state.entries)
    effects = []
    returned = None
    error = None
    try:
        if target == 'registry':
            _path_arguments(state.root, name, arguments)
            with platform_dependencies(state, name, arguments, action.get('controls', {})) as observations:
                request = ToolRequest(name, arguments, actor_profile=action.get('profile', 'owner'), confirmed=action.get('confirmed', False), source='campaign10-contract')
                returned = _entered(state.registry, lambda: state.registry.execute(request).to_dict(), state)
                effects = observations()
        elif target == 'desktop':
            if action.get('profile', 'owner') != 'owner':
                raise NotImplementedError('UNSUPPORTED_INTERFACE_ACTOR: the original desktop mutation interface is owner-bound; no synthetic actor elevation is applied.')
            body = {'id': action.get('request_id') or str(uuid5(NAMESPACE, case_id + ':' + action['id'])), 'operation': name, 'data': arguments, 'confirmed': action.get('confirmed', True)}
            returned = _entered(state.registry, lambda: state.features.mutate(action.get('area', 'productivity'), body), state)
        elif target == 'snapshot':
            returned = state.features.productivity()
        elif target == 'calendar':
            returned = state.features.calendar(arguments)
        elif target == 'discovery':
            returned = state.registry.capabilities.search(arguments['query'], limit=arguments.get('limit', 5))
        elif target == 'capability_schema':
            returned = state.registry.capabilities.get(name)
        elif target == 'stop':
            if action.get('profile', 'owner') != 'owner':
                raise NotImplementedError('UNSUPPORTED_INTERFACE_ACTOR: this original stop control adapter is owner-bound.')
            from hanni.core.identity import Actor
            from hanni.core.shutdown import StopSource
            if name == 'trip':
                state.registry.context.emergency_stop.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner(), reason='Owned acceptance fixture stop')
            elif name == 'clear':
                state.registry.context.emergency_stop.clear(Actor.owner())
            else:
                raise ValueError('Unknown original stop action.')
            returned = {'stopped': state.registry.context.emergency_stop.is_tripped}
        elif target == 'restart':
            from hanni.core.shutdown import EmergencyStop, FileStopStateStore
            state.registry.context.emergency_stop = EmergencyStop(FileStopStateStore.for_data_dir(state.root))
            returned = {'stopped': state.registry.context.emergency_stop.is_tripped, 'scope': 'Original state-store reconstruction; not backend process restart'}
        elif target == 'lab':
            lab = _lab(state)
            if name == 'start':
                returned = lab.start(arguments)
            elif name == 'wait':
                deadline = time.monotonic() + min(30, arguments.get('timeout', 10))
                while lab.thread is not None and lab.thread.is_alive() and (time.monotonic() < deadline):
                    time.sleep(0.01)
                returned = lab.detail(arguments['run_id'])
            elif name == 'detail':
                returned = lab.detail(**arguments)
            elif name == 'export':
                returned = lab.export(**arguments)
            elif name == 'compare':
                returned = lab.compare(arguments['run_ids'])
            elif name == 'preflight':
                returned = lab.preflight(**arguments)
            else:
                raise ValueError('Unsupported original Model Lab action.')
        elif target == 'mcp':
            manager = _mcp(state)
            if name == 'add':
                returned = manager.add({'name': 'C10 inert parts-bin provider', 'transport': 'streamable_http', 'url': 'http://127.0.0.1:49191/mcp', 'allow_local_http': True, 'auto_connect': False})
            elif name == 'connect':
                with patch('hanni.mcp.manager.AsyncRuntime', manager.campaign_runtime_factory):
                    returned = manager.connect(arguments['server_id'], approved=arguments.get('approved', False), expected_config_hash=arguments.get('config_hash'))
            elif name == 'approve':
                tools = [{'original_name': t['original_name'], 'definition_hash': t['definition_hash'], 'classification': 'read_only'} for t in arguments['tools']]
                returned = manager.approve_tools(arguments['server_id'], tools)
            elif name == 'snapshot':
                returned = manager.snapshot()
            elif name == 'disable':
                returned = manager.disable_server(arguments['server_id'])
            elif name == 'reopen':
                manager.close()
                del state.mcp_manager
                returned = _mcp(state).snapshot()
            elif name == 'call':
                returned = _entered(state.registry, lambda: state.registry.execute(ToolRequest(arguments['tool_id'], {'bin': arguments['bin']}, actor_profile=action.get('profile', 'owner'), confirmed=action.get('confirmed', False), source='campaign10-inert-mcp')).to_dict(), state)
            else:
                raise ValueError('Unsupported original MCP manager action.')
        elif target == 'session':
            if not hasattr(state, 'session'):
                from hanni.core.orchestrator import TextSession
                from hanni.tools.session import ToolAwareSession
                state.session = ToolAwareSession(TextSession(NoInferenceClient()), state.registry)
            before_calls = state.model_counter() if hasattr(state, 'model_counter') else state.model_call_count
            try:
                text = _entered(state.registry, lambda: ''.join(state.session.stream_response(arguments['query'], max_tokens=256, temperature=0)), state)
            finally:
                state.model_call_count = state.model_counter() if hasattr(state, 'model_counter') else state.model_call_count
            returned = {'text': text, 'genuine_inference': state.model_call_count > before_calls, 'model_call_count': state.model_call_count - before_calls, 'scope': 'Original controller; actual HTTP count must come from root-owned observer'}
        elif target == 'unsupported':
            raise NotImplementedError('This generic operation belongs to another service adapter: ' + name)
        else:
            raise ValueError('Unsupported input-only contract target.')
    except Exception as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)}
    return {'id': action['id'], 'target': target, 'name': name, 'arguments': arguments, 'result': returned, 'error': error, 'handler_entries': state.entries[entry_start:], 'dependency_observations': effects, 'latency_ms': (time.perf_counter() - started) * 1000}

def normalize_case(case):
    """Input envelope translation only; no expectation or private oracle field."""
    if 'query' in case:
        return deepcopy(case)
    turns = case.get('user_turns', [])
    actions = []
    for index, action in enumerate(case.get('actions', [])):
        operation = action['operation']
        if operation in {'registry.call', 'capability.call'}:
            args = action.get('args', {})
            target = {'target': 'registry', 'name': args.get('name', args.get('id', '')), 'arguments': args.get('arguments', {})}
        elif operation.startswith('productivity.'):
            target = {'target': 'desktop', 'name': operation.removeprefix('productivity.'), 'arguments': action.get('args', {})}
        elif operation == 'calendar.project':
            target = {'target': 'calendar', 'arguments': action.get('args', {})}
        elif operation.startswith(('file.', 'folder.', 'archive.', 'todo.', 'note.', 'app.', 'ui.', 'system.', 'hanni.')):
            target = {'target': 'registry', 'name': operation, 'arguments': action.get('args', {})}
        else:
            target = {'target': 'unsupported', 'name': operation, 'arguments': action.get('args', {})}
        authority = {}
        for key in ('confirmed', 'controls', 'request_id', 'area'):
            if key in action:
                authority[key] = deepcopy(action[key])
        profile = action.get('actor_profile', action.get('profile'))
        if profile is None and turns:
            profile = turns[0].get('actor_profile', 'owner')
        authority['profile'] = profile if profile is not None else 'owner'
        if 'confirmed' not in authority:
            authority['confirmed'] = turns[0].get('confirmed', False) if turns else False
        actions.append({'id': action.get('bind') or action.get('id') or 'step' + str(index + 1), **target, **authority})
    return {'id': case['id'], 'category': case.get('family', 'unclassified'), 'difficulty': case.get('difficulty'), 'query': turns[0]['prompt'] if turns else case.get('description', ''), 'user_turns': deepcopy(turns), 'setup': deepcopy(case.get('fixtures', {})), 'actions': actions, 'limits': deepcopy(case.get('limits', {}))}

def original_session(state, client):
    """Use the actual CLI text factories; wire admission still belongs to root.

    Real clients require the coordinator's already-installed, exact-root engine.
    That prevents the CLI factory from creating a second compute/model owner.
    Only shadow startup is disabled for this isolated acceptance instance.
    """
    from hanni.core.orchestrator import TextSession, system_prompt_for
    from hanni.cli import _wrap_mcp_session, _wrap_memory_session
    from hanni.models.adaptive import AdaptiveModelClient, current
    from hanni.models.client import LlamaCppClient
    from hanni.mcp.runtime import workflow_hub
    if isinstance(client, (LlamaCppClient, AdaptiveModelClient)):
        engine = current(state.config)
        if engine is None or (isinstance(client, AdaptiveModelClient) and client.engine is not engine):
            raise RuntimeError('HARNESS_PREREQUISITE: install the guarded exact-root model engine before the original text factory.')
    text = TextSession(client, system_prompt=system_prompt_for(state.config.hanni.personality))
    if state.config.hanni.memory.enabled:
        owned(state.root, state.config.hanni.memory.database_file)
    wrapped = _wrap_mcp_session(state.config, text, client=client, registry=state.registry)
    state.session = wrapped
    with patch.dict(os.environ, {'HANNI_LAYA_SHADOW_ENABLED': '0'}):
        session = _wrap_memory_session(state.config, wrapped, source='keyboard', registry=state.registry, emergency_stop=state.registry.context.emergency_stop)
    state.session = session
    layers, cursor, seen = ([], session, set())
    while cursor is not None and id(cursor) not in seen:
        seen.add(id(cursor))
        layers.append(type(cursor).__module__ + '.' + type(cursor).__name__)
        cursor = getattr(cursor, 'fallback_session', None)
    workflows = workflow_hub(state.config)
    state.session_metadata = {'factory': 'hanni.cli._wrap_mcp_session -> hanni.cli._wrap_memory_session', 'layers': layers, 'mcp_enabled': state.config.hanni.mcp.enabled, 'mcp_read_only': state.config.hanni.mcp.read_only, 'memory_enabled': state.config.hanni.memory.enabled, 'context_enabled': state.config.hanni.memory.context_enabled, 'legacy_m6_tool_layer_added': False, 'shadow_startup_enabled': False, 'workflow_facade_present': workflows is not None, 'workflow_controller_attached': workflows is not None and workflows.registry is state.registry and workflows.runner_attached, 'command_driver_attached': False, 'compute_scheduler_attached': workflows is not None and workflows.compute is not None, 'scope': 'Original CLI text wrappers; original dashboard/workflow hub is an independently reported prerequisite. Standalone stream_response does not enter the CLI workflow command driver.'}
    if hasattr(state, 'controller_telemetry'):
        sample = state.controller_telemetry.snapshot()
        state.session_metadata['workflow_resource_sampled_at'] = sample.get('sampled_at')
        state.session_metadata['workflow_resource_admission'] = state.workflow_facade._resource_probe()
    return session

def attach_dashboard_facades(state, *, telemetry=None):
    """Opt-in original launcher facades, without HTTP/native/model startup.

    The coordinator can start ``state.controller_telemetry.start()`` for genuine
    resource sampling under its GO. Until then original resource admission is
    unknown/refused. No goal, plan, workflow status or resource is synthesized.
    Environment cleanup owns these same-root facades and telemetry.
    """
    from hanni.dashboard.mcp_hub import MCPHub
    from hanni.dashboard.workflows import WorkflowHub
    from hanni.dashboard.server import Telemetry
    from hanni.mcp import runtime
    if hasattr(state, 'mcp_facade'):
        return state.mcp_facade
    if telemetry is not None and (not isinstance(telemetry, Telemetry) or Path(telemetry.config.paths.data_dir).resolve() != state.root):
        raise ValueError('Controller telemetry must be the original class with the exact owned data root.')
    with runtime._lock:
        if runtime._hub is not None:
            raise RuntimeError('HARNESS_PREREQUISITE: an existing controller hub must not be replaced by this fixture.')
        manager = _mcp(state)
        state.controller_telemetry = telemetry if telemetry is not None else Telemetry(state.config)
        state.mcp_facade = MCPHub(state.config, state.features, manager=manager)
        state.workflow_facade = WorkflowHub(state.config, state.features, state.controller_telemetry, compute=None)
        state.mcp_facade.workflows = state.workflow_facade
        state.features.memory_explorer.workflow_reader = state.workflow_facade.detail
        runtime.install(state.mcp_facade)
    return state.mcp_facade

def run_case(case, root, *, session_factory=None, connection_authorizer=None, config=None, model_counter=None, on_prepared_turns=None):
    """No oracle input. Root-owned actual session optional and never manufactured."""
    case = normalize_case(case)
    action_ids = [action['id'] for action in case.get('actions', [])]
    if len(action_ids) != len(set(action_ids)) or any((not isinstance(key, str) or not key for key in action_ids)):
        raise ValueError('Contract action IDs must be unique nonempty strings.')
    _validate_setup(case.get('setup', {}), action_ids)
    started = time.perf_counter()
    results = {}
    with environment(root, connection_authorizer=connection_authorizer, config=config) as state:
        if model_counter is not None:
            state.model_counter = model_counter
        setup_results = seed(state, case.get('setup', {}))
        results.update(setup_results)
        original_inventory = inventory(state.registry)
        query = substitute(case['query'], state.root, results)
        if not isinstance(query, str):
            raise ValueError('The prepared query must be text.')
        turns = deepcopy(case.get('user_turns') or [{'prompt': query, 'actor_profile': 'owner'}])
        for turn in turns:
            turn['prompt'] = substitute(turn['prompt'], state.root, results)
            if not isinstance(turn['prompt'], str):
                raise ValueError('Prepared user turns must be text.')
        if session_factory is not None and on_prepared_turns is not None:
            on_prepared_turns(case['id'], deepcopy(turns))
        route_started = time.perf_counter()
        decision = state.host.route(query)
        route = {'status': decision.status, 'tools': [t.capability_id for t in decision.tools], 'schemas': [t.openapi_schema() if hasattr(t, 'openapi_schema') else t.openai_schema() for t in decision.tools], 'blocked': list(decision.blocked_capabilities), 'latency_ms': (time.perf_counter() - route_started) * 1000, 'scope': 'Original deterministic capability menu; not model understanding or executed plan'}
        before = file_snapshot(state.root)
        snapshot_before = state.features.productivity()
        response = None
        if session_factory is not None:
            state.session = session_factory(state)
            for index, turn in enumerate(turns):
                ident = 'actual_turn_' + str(index + 1)
                if turn.get('actor_profile', 'owner') != 'owner':
                    response = {'id': ident, 'result': None, 'error': {'type': 'UNSUPPORTED_INTERFACE_ACTOR', 'message': 'Original local foreground interface establishes owner identity; no synthetic role elevation applied.'}}
                else:
                    response = dispatch(state, {'id': ident, 'target': 'session', 'arguments': {'query': turn['prompt']}}, results, case['id'])
                response['interface_authority'] = {'actor_profile': turn.get('actor_profile', 'owner'), 'supplied_confirmed': deepcopy(turn.get('confirmed', False)), 'confirmation_applied_to_tools': False, 'scope': 'The original foreground interface derives confirmation from its own pending request flow, not turn metadata.'}
                results[ident] = response
        else:
            for action in case.get('actions', []):
                try:
                    results[action['id']] = dispatch(state, action, results, case['id'])
                except Exception as exc:
                    results[action['id']] = {'id': action['id'], 'result': None, 'error': {'type': 'HARNESS_REFERENCE_ERROR', 'message': str(exc)}}
        after = file_snapshot(state.root)
        snapshot_after = state.features.productivity()
        audit = state.registry.context.audit.tail(limit=500)
        traces = state.registry.context.reliability.store.snapshot(limit=100)
        receipt = {'id': case['id'], 'category': case['category'], 'query': query, 'mode': 'ACTUAL_ORIGINAL_SESSION' if session_factory else 'CONTROLLED_ORIGINAL_CONTRACT', 'dimensions': {key: {'status': 'NOT_MEASURED', 'scope': 'Observed receipt, offline oracle required'} for key in DIMENSIONS}, 'route': route, 'actions': results, 'inventory_before': original_inventory, 'fixture_setup': deepcopy(setup_results), 'fixture_prerequisites': state.fixture_prerequisites, 'prepared_user_turns': turns, 'session_metadata': state.session_metadata, 'inventory_after': inventory(state.registry), 'files_before': before, 'files_after': after, 'workspace_before': snapshot_before, 'workspace_after': snapshot_after, 'audit': audit, 'trace_projection': traces, 'unsafe_leaf_denials': state.effects, 'actual_model_reply': response, 'elapsed_ms': (time.perf_counter() - started) * 1000, 'inert_mcp_provider_calls': getattr(state, 'mcp_calls', []), 'semantic_model_selection_measured': session_factory is not None and state.model_call_count > 0, 'semantic_grading_scope': 'Observed HTTP counts do not establish correct intent, tool selection or grounded responses; independent wire/readback grading is required.', 'actual_generated': state.model_call_count > 0, 'model_call_count': state.model_call_count, 'source_pins': {p: digest(REPO / p) for p in ('src/hanni/tools/base.py', 'src/hanni/tools/session.py', 'src/hanni/mcp/host.py', 'src/hanni/mcp/session.py', 'src/hanni/dashboard/features.py', 'src/hanni/dashboard/productivity.py', 'src/hanni/evals/model_lab.py', 'src/hanni/cli.py', 'src/hanni/mcp/runtime.py', 'src/hanni/memory/integration.py')}, 'cleanup': state.cleanup}
        return receipt
