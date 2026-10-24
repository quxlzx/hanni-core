"""Original workflow runner over isolated fixtures, with no embedded oracle.

Controlled planner replies test protocol contracts, not model understanding.
Faults attach only to pathlib I/O for declared campaign paths. Registered tool
definitions and handlers, McpHost, planner, scheduler and SQLite store remain
the production implementations. No process, hardware, remote or owner store is
used. Direct-store probes are labeled separately from native scheduler runs.
"""
from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import inspect
import json
from pathlib import Path
import threading
import time
from typing import Any
from unittest.mock import patch
from uuid import uuid4
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.tools import build_default_registry
from hanni.workflows.service import WorkflowService
from hanni.workflows.store import WorkflowStore
from hanni.workflows.types import TRANSITIONS, TERMINAL, WorkflowError, WorkflowLimits, fingerprint
from tests.helpers import write_config_dir

def expand(value: Any, root: Path, artifact_root: Path | None=None) -> Any:
    if isinstance(value, str):
        return value.replace('{root}', str(root)).replace('{artifact_root}', str(artifact_root or root / 'UNBOUND_ARTIFACT'))
    if isinstance(value, list):
        return [expand(item, root, artifact_root) for item in value]
    if isinstance(value, dict):
        return {key: expand(item, root, artifact_root) for key, item in value.items()}
    return value

class FixtureClock:
    """Real advancing time plus explicitly reported bounded fault offsets."""

    def __init__(self):
        self.offset = 0.0

    def wall(self):
        return time.time() + self.offset

    def monotonic(self):
        return time.monotonic() + self.offset

    def advance(self, seconds):
        self.offset += seconds

class ControlledPlannerClient:

    def __init__(self, case, root):
        self.case, self.root = (case, root)
        self.calls = []
        self.responses = []
        self.completed_calls = 0
        self.analysis_calls = 0

    def chat(self, messages, **kwargs):
        self.calls.append({'messages': deepcopy(messages), 'kwargs': deepcopy(kwargs)})
        payload = json.loads(messages[-1]['content'])
        if kwargs.get('response_format', {}).get('json_schema', {}).get('name') == 'hanni_workflow_evidence':
            replies = self.case.get('analysis_replies', [])
            if isinstance(replies, dict):
                reply = replies[payload['description']]
            else:
                reply = replies[self.analysis_calls]
            self.analysis_calls += 1
            response = reply if isinstance(reply, str) else json.dumps(reply)
            self.responses.append({'phase': 'analysis', 'raw': response})
            return response
        artifact_root = Path(payload['artifact_root'])
        index = self.completed_calls % 2
        self.completed_calls += 1
        faults = self.case.get('planner_fault', {})
        if faults.get('phase', 'outline') == ('outline' if index == 0 else 'binding'):
            kind = faults.get('kind')
            if kind == 'malformed_json':
                self.responses.append({'phase': 'outline' if index == 0 else 'binding', 'raw': '{unfinished'})
                return '{unfinished'
            if kind == 'raise_timeout':
                self.responses.append({'phase': 'outline' if index == 0 else 'binding', 'exception': 'TimeoutError'})
                raise TimeoutError('Controlled planner transport timeout')
        steps = expand(self.case.get('steps', []), self.root, artifact_root)
        if index == 0:
            response = {'summary': self.case.get('summary', 'Controlled contract plan.'), 'unsupported_reason': self.case.get('unsupported_reason'), 'steps': [{key: step[key] for key in ('step_id', 'description', 'kind', 'dependencies', 'required', 'criteria')} for step in steps]}
        else:
            response = {'unsupported_reason': None, 'steps': [{'step_id': step['step_id'], 'capability_id': step['capability_id'], 'arguments': step['arguments']} for step in steps]}
        if faults.get('phase', 'outline') == ('outline' if index == 0 else 'binding'):
            kind = faults.get('kind')
            if kind == 'authority':
                response['confirmed'] = True
            elif kind == 'missing_step' and response['steps']:
                response['steps'].pop()
            elif kind == 'extra_step' and response['steps']:
                response['steps'].append(deepcopy(response['steps'][0]))
            elif kind == 'invented_capability' and response['steps']:
                response['steps'][0]['capability_id'] = 'fixture.unregistered_execution'
            elif kind == 'reserved_arguments' and response['steps']:
                response['steps'][0]['arguments']['confirmed'] = True
            elif kind == 'wrong_id' and response['steps']:
                response['steps'][0]['step_id'] = 'undeclared_step'
        raw = json.dumps(response)
        self.responses.append({'phase': 'outline' if index == 0 else 'binding', 'raw': raw})
        return raw

@dataclass
class LeafFaults:
    root: Path
    definitions: list[dict]
    calls: list[dict] = field(default_factory=list)
    entered: threading.Event = field(default_factory=threading.Event)
    released: threading.Event = field(default_factory=threading.Event)
    counts: dict = field(default_factory=dict)
    effect_ledger: list = field(default_factory=list)
    environment: Any = None
    original_read: Any = Path.read_text
    original_read_bytes: Any = Path.read_bytes
    original_write: Any = Path.write_text

    def matching(self, path, method):
        actual = str(Path(path).resolve())
        return next((fault for fault in self.definitions if fault.get('method', 'read') == method and str(Path(fault['path']).resolve()) == actual), None)

    def invoke(self, method, path, function, args, kwargs):
        fault = self.matching(path, method)
        identity = (method, str(Path(path).resolve()))
        caller = inspect.currentframe().f_back.f_back
        original_entry = caller.f_globals.get('__name__') == 'hanni.tools.files'
        if original_entry and (not Path(path).resolve().is_relative_to(self.root)):
            raise AssertionError('Original handler attempted filesystem I/O outside campaign root')
        ledger = None
        if original_entry and method == 'write':
            from hanni.reliability.context import current_correlation_id
            correlation = current_correlation_id()
            env = self.environment
            detail = env.service.store.get(env.key)
            history = env.service.store.history(env.key)
            invocation = next((item for item in history['invocations'] if item['correlation_id'] == correlation), None)
            scope = detail.get('scope') or {}
            from datetime import datetime
            now = env.clock.wall()

            def unexpired(item):
                return datetime.fromisoformat(item['expires_at'].replace('Z', '+00:00')).timestamp() > now
            reviewed = any((item['approval_id'] == scope.get('approval_id') and item['state'] == 'approved' and (item['plan_hash'] == detail['plan_hash']) and unexpired(item) for item in history['approvals']))
            exact_review = bool(invocation and invocation.get('approval_id') and any((item['approval_id'] == invocation['approval_id'] and item['state'] == 'consumed' and (item['argument_hash'] == invocation['argument_hash']) and (item['definition_hash'] == invocation['definition_hash']) and (item['plan_hash'] == detail['plan_hash']) and unexpired(item) for item in history['approvals'])))
            managed = Path(path).resolve().is_relative_to(env.service._artifact_root(env.key))
            ledger = {'sequence': len(self.effect_ledger) + 1, 'stage': 'handler_entered', 'path': identity[1], 'correlation_id': correlation, 'workflow_id': env.key, 'step_id': invocation.get('step_id') if invocation else None, 'invocation_id': invocation.get('invocation_id') if invocation else None, 'logical_operation': env.key + '/' + invocation['step_id'] if invocation else None, 'reviewed_plan': reviewed, 'managed_artifact': managed, 'consumed_exact_approval': exact_review, 'authority_time': now, 'scope_expires': scope.get('expires'), 'plan_hash': detail['plan_hash'], 'scope_provenance': scope.get('provenance'), 'authorized': bool(invocation and invocation['state'] == 'dispatched' and invocation['write'] and reviewed and (scope.get('actor_profile') == 'owner') and (scope.get('expires', 0) > now) and (scope.get('plan_hash') == detail['plan_hash']) and (scope.get('provenance') == 'owner_plan_review') and (exact_review or (managed and detail['mode'] != 'supervised'))), 'actual_effect': False, 'returned': False, 'error': None}
            self.effect_ledger.append(ledger)
        if not fault:
            result = function(path, *args, **kwargs)
            if ledger is not None:
                ledger.update(actual_effect=True, returned=True, size_bytes=Path(path).stat().st_size, sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
            if original_entry:
                self.calls.append({'method': method, 'path': identity[1], 'fault': None, 'caller_module': 'hanni.tools.files', 'caller_function': caller.f_code.co_name, 'time': time.monotonic()})
            return result
        count = self.counts[identity] = self.counts.get(identity, 0) + 1
        self.calls.append({'method': method, 'path': identity[1], 'call': count, 'caller_module': caller.f_globals.get('__name__'), 'caller_function': caller.f_code.co_name, 'time': time.monotonic(), 'fault': fault.get('kind')})
        kind = fault.get('kind')
        if kind == 'barrier' and count <= fault.get('times', 1):
            self.entered.set()
            if not self.released.wait(8):
                raise TimeoutError('Controlled I/O barrier did not release')
        if count <= fault.get('times', 1):
            if kind == 'timeout_before':
                if ledger is not None:
                    ledger['error'] = 'timeout_before'
                raise TimeoutError('Controlled original filesystem timeout')
            if kind == 'permission_before':
                if ledger is not None:
                    ledger['error'] = 'permission_before'
                raise PermissionError('Controlled original filesystem permission denial')
            if kind == 'noop_write':
                if ledger is not None:
                    ledger['returned'] = True
                return len(args[0])
            if kind == 'corrupt_write':
                result = function(path, 'different persisted bytes', **kwargs)
                if ledger is not None:
                    ledger.update(actual_effect=True, returned=True, size_bytes=Path(path).stat().st_size, sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
                return result
        result = function(path, *args, **kwargs)
        if ledger is not None:
            ledger.update(actual_effect=True, size_bytes=Path(path).stat().st_size, sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
        if count <= fault.get('times', 1) and kind == 'timeout_after':
            if ledger is not None:
                ledger['error'] = 'timeout_after'
            raise TimeoutError('Controlled timeout after actual isolated filesystem operation')
        if ledger is not None:
            ledger['returned'] = True
        return result

    @contextmanager
    def context(self):
        from hanni.tools import files
        original_hash = files._sha256

        def read(path, *args, **kwargs):
            return self.invoke('read', path, self.original_read, args, kwargs)

        def read_bytes(path, *args, **kwargs):
            return self.invoke('read', path, self.original_read_bytes, args, kwargs)

        def write(path, *args, **kwargs):
            return self.invoke('write', path, self.original_write, args, kwargs)

        def hash_file(path):
            return self.invoke('hash', path, original_hash, (), {})
        with patch.object(Path, 'read_text', read), patch.object(Path, 'read_bytes', read_bytes), patch.object(Path, 'write_text', write), patch.object(files, '_sha256', hash_file):
            try:
                yield self
            finally:
                self.released.set()

@dataclass
class Environment:
    root: Path
    case: dict
    clock: FixtureClock
    registry: Any
    host: Any
    client: ControlledPlannerClient
    service: WorkflowService
    faults: LeafFaults
    events: list
    controls: list = field(default_factory=list)
    instances: list = field(default_factory=list)
    executed_controls: set = field(default_factory=set)
    key: str | None = None

    def observer(self, stage, event):
        self.events.append({'stage': stage, 'event': deepcopy(event), 'time': time.monotonic()})
        _perform(self, stage, event)

    def control(self, operation, **extra):
        detail = self.service.detail(self.key)
        data = {'workflow_id': self.key, 'expected_revision': detail['revision']}
        if operation in {'approve_plan', 'start'}:
            data['plan_hash'] = detail['plan_hash']
        if operation in {'approve_step', 'reject'}:
            approval = next((item for item in reversed(detail['approvals']) if item['state'] == 'pending' and item.get('step_id')))
            data.update({field: approval[field] for field in ('step_id', 'approval_id', 'plan_hash', 'argument_hash', 'definition_hash')})
        if operation == 'revoke':
            data['approval_id'] = next((item for item in reversed(detail['approvals']) if item['state'] == 'approved'))['approval_id']
        if operation == 'retry_safe':
            data['step_id'] = extra.pop('step_id')
        if extra.get('stale_revision'):
            data['expected_revision'] -= 1
        if extra.get('alter_binding'):
            data[extra['alter_binding']] = 'changed-binding'
        actor = extra.get('actor_profile', 'owner')
        try:
            result = self.service.mutate({'id': str(uuid4()), 'operation': operation, 'data': data}, actor_profile=actor)
            receipt = {'operation': operation, 'ok': True, 'result': result, 'before_status': detail['status'], 'before_revision': detail['revision']}
        except Exception as exc:
            receipt = {'operation': operation, 'ok': False, 'error_type': type(exc).__name__, 'error': str(exc), 'before_status': detail['status'], 'before_revision': detail['revision']}
        receipt['after_status'] = self.service.store.get(self.key)['status']
        self.controls.append(receipt)
        return receipt

    def restart(self):
        old = self.service
        old.detach()
        self.faults.released.set()
        end = time.monotonic() + 3
        while old.workers and time.monotonic() < end:
            time.sleep(0.02)
        old.store.close()
        self.service = WorkflowService(self.root / 'data', WorkflowLimits(**self.case.get('limits', {})), protected_roots=(self.root / 'config',), clock=self.clock.wall, monotonic=self.clock.monotonic, observer=self.observer)
        self.instances.append(self.service)
        self.service.attach(self.registry, self.client, host=self.host, resource_probe=lambda: {'allowed': True, 'ram_percent': 20, 'gpu': None})
        self.service.start()

@contextmanager
def setup_environment(case, root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    files = case.get('files', [])
    if isinstance(files, dict):
        files = [{'path': name if '{root}' in name else '{root}/' + name, 'text': text} for name, text in files.items()]
    for item in files:
        path = Path(expand(item['path'], root))
        if not path.is_relative_to(root):
            raise ValueError('Fixture file escapes the campaign directory')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['text'], encoding='utf-8')
    config = load_config(write_config_dir(root / 'config'), data_dir=root / 'data', env={})
    registry = build_default_registry(config)
    from scripts.v3_review.service_fixture import EmptyProviderVault
    registry.google_access._vault = EmptyProviderVault()
    host = McpHost(registry, read_only=True)
    host.allowed_actions = tuple(dict.fromkeys((*host.allowed_actions, 'file.write')))
    clock, events = (FixtureClock(), [])
    client = ControlledPlannerClient(case, root)
    service = WorkflowService(root / 'data', WorkflowLimits(**case.get('limits', {})), protected_roots=(root / 'config',), clock=clock.wall, monotonic=clock.monotonic, observer=lambda stage, event: events.append({'stage': stage, 'event': deepcopy(event), 'time': time.monotonic()}))
    service.attach(registry, client, host=host, resource_probe=lambda: {'allowed': True, 'ram_percent': 20, 'gpu': None})
    faults = LeafFaults(root, [])
    environment = Environment(root, case, clock, registry, host, client, service, faults, events)
    faults.environment = environment
    service.observer = service.store.observer = environment.observer
    environment.instances.append(service)
    try:
        service.start()
        yield environment
    finally:
        faults.released.set()
        for instance in environment.instances:
            instance.close()
        end = time.monotonic() + 3
        while any((instance.workers for instance in environment.instances)) and time.monotonic() < end:
            time.sleep(0.02)
        for instance in environment.instances:
            if not instance.workers:
                instance.store.close()
        from hanni.reliability.execution import close_service
        close_service(root / 'data')

def _perform(env, stage, event=None):
    event = event or {}
    event_step = event.get('step_id')
    if not event_step and event.get('invocation_id') and env.key:
        event_step = next((row['step_id'] for row in env.service.store.history(env.key)['invocations'] if row['invocation_id'] == event['invocation_id']), None)
    for index, control in enumerate(env.case.get('controls', [])):
        if control.get('at') != stage:
            continue
        if index in env.executed_controls and (not control.get('repeat', False)):
            continue
        if event and control.get('step_id') and (control['step_id'] != event_step):
            continue
        env.executed_controls.add(index)
        operation = control['operation']
        if operation == 'advance':
            env.clock.advance(control['seconds'])
            env.service.wake.set()
            env.controls.append({'operation': operation, 'seconds': control['seconds'], 'ok': True})
        elif operation == 'release':
            env.faults.released.set()
            env.controls.append({'operation': operation, 'ok': True})
        elif operation == 'detach':
            env.service.detach()
            env.controls.append({'operation': operation, 'ok': True})
        elif operation == 'restart':
            env.restart()
            env.controls.append({'operation': operation, 'ok': True})
        elif operation == 'wait_entered':
            end = time.monotonic() + control.get('timeout', 3)
            while sum((row.get('fault') == 'barrier' for row in env.faults.calls)) < control['count']:
                if time.monotonic() > end:
                    raise TimeoutError('Declared parallel original handlers did not both enter')
                time.sleep(0.01)
            env.controls.append({'operation': operation, 'ok': True, 'count': control['count']})
        else:
            env.control(operation, **{key: value for key, value in control.items() if key not in {'at', 'operation', 'repeat'}})

def _readback(env):
    result = {}
    for path in env.root.rglob('*'):
        if path.is_file() and path.suffix in {'.txt', '.md', '.csv', '.log', '.json'}:
            data = path.read_bytes()
            if len(data) <= 300000:
                result[str(path.relative_to(env.root)).replace('\\', '/')] = {'text': data.decode('utf-8', errors='replace'), 'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    return result

def run_case(case, root):
    """Execute inputs only. Callers keep prospectively sealed oracles separate."""
    started = time.monotonic()
    receipt = {'id': case['id'], 'category': case['category'], 'scenario': case['scenario'], 'execution_scope': 'native_original_scheduler', 'semantic_model_quality': 'BLOCKED_NOT_MEASURED_CONTROLLED_RESPONSES', 'harness_error': None}
    if case.get('runner', 'scheduler') == 'store':
        return run_store_case(case, root)
    env = None
    try:
        with setup_environment(case, root) as env:
            submitted = time.monotonic()
            response = env.service.mutate({'id': str(uuid4()), 'operation': 'goal.submit', 'data': {'goal': expand(case['goal'], env.root), 'mode': case.get('mode', 'assisted')}})
            env.key = response['workflow_id']
            detail = env.service.wait(env.key, timeout=8)
            artifact_root = env.service._artifact_root(env.key)
            env.faults.definitions = expand(case.get('faults', []), env.root, artifact_root)
            if any((not Path(fault['path']).resolve().is_relative_to(env.root) for fault in env.faults.definitions)):
                raise ValueError('Leaf fault path escapes the exact owned campaign root')
            with env.faults.context():
                _perform(env, 'planned')
                detail = env.service.detail(env.key)
                if detail['status'] == 'awaiting_plan_approval' and case.get('auto_approve', True):
                    env.control('approve_plan')
                _perform(env, 'ready')
                detail = env.service.detail(env.key)
                if detail['status'] == 'ready' and case.get('auto_start', True):
                    env.control('start')
                if env.service.detail(env.key)['status'] in {'running', 'verifying', 'retrying'} and any((fault.get('kind') == 'barrier' for fault in env.faults.definitions)):
                    if not env.faults.entered.wait(4):
                        raise TimeoutError('Original handler did not enter the declared I/O barrier')
                    _perform(env, 'active')
                    env.faults.released.set()
                detail = env.service.wait(env.key, timeout=8, predicate=lambda item: item['status'] in TERMINAL | {'blocked', 'awaiting_plan_approval', 'awaiting_step_approval', 'paused'} or (item['status'] == 'ready' and (not env.service._available())))
                if detail['status'] == 'awaiting_step_approval':
                    _perform(env, 'waiting_approval')
                    if env.service.detail(env.key)['status'] not in {'awaiting_step_approval', 'paused', 'cancelled'}:
                        detail = env.service.wait(env.key, timeout=8)
                _perform(env, 'stopped')
                if env.service._available() and env.service.detail(env.key)['status'] in {'running', 'retrying', 'verifying', 'planning'}:
                    detail = env.service.wait(env.key, timeout=8)
                else:
                    detail = env.service.detail(env.key)
            receipt.update(workflow=detail, files=_readback(env), controls=env.controls, planner_calls=env.client.calls, leaf_calls=env.faults.calls, controlled_raw_responses=env.client.responses, observer_events=env.events, clock_offset=env.clock.offset, runner_error=env.service.runner_error, workflow_observed_duration_ms=(time.monotonic() - submitted) * 1000, original_workflow_duration_seconds=detail.get('duration_seconds'), effect_ledger=env.faults.effect_ledger, restart_scope='owned_in_process_original_service' if any((c.get('operation') == 'restart' for c in env.controls)) else None, original_handlers=[{'name': name, 'module': env.registry.get(name).handler.__module__, 'qualified_name': env.registry.get(name).handler.__qualname__} for name in sorted({step.get('capability_id') for step in detail.get('steps', []) if step.get('capability_id')})])
    except Exception as exc:
        receipt['harness_error'] = {'type': type(exc).__name__, 'message': str(exc)}
        if env and env.key:
            try:
                receipt.update(workflow=env.service.detail(env.key), files=_readback(env), controls=env.controls, observer_events=env.events, planner_calls=env.client.calls, leaf_calls=env.faults.calls, controlled_raw_responses=env.client.responses, effect_ledger=env.faults.effect_ledger)
            except Exception as nested:
                receipt['readback_error'] = {'type': type(nested).__name__, 'message': str(nested)}
    receipt['duration_ms'] = (time.monotonic() - started) * 1000
    return receipt

def run_store_case(case, root):
    """Original durable boundary tests; no scheduler/real tool execution claim."""
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    clock = FixtureClock()
    store = WorkflowStore(root / 'data', clock=clock.wall)
    started, actions = (time.monotonic(), [])
    receipt = {'id': case['id'], 'category': case['category'], 'scenario': case['scenario'], 'execution_scope': 'direct_original_store', 'harness_error': None, 'semantic_model_quality': 'BLOCKED_NOT_MEASURED_DIRECT_STORE'}
    try:
        lease = store.claim(str(uuid4()))
        record = store.create(case['goal'], case.get('mode', 'assisted'))
        key = record['workflow_id']
        steps = [{'step_id': 'effect', 'dependencies': [], 'kind': 'tool', 'required': True, 'capability_id': 'fixture.boundary', 'definition_hash': 'isolated-definition', 'arguments': {}, 'criteria': [{'operator': 'present', 'path': '/data/value', 'expected': None}]}]
        record = store.save_plan(key, record['revision'], {'summary': 'Store boundary only', 'steps': steps}, steps, lease=lease)
        record = store.update(key, record['revision'], {'status': 'ready'}, lease=lease)
        probe = case['probe']
        invocation = None
        if probe in {'recover_read', 'recover_write', 'stale_finish', 'uncertain_replay', 'receipt_failure', 'duplicate_finish'}:
            write = probe not in {'recover_read', 'stale_finish', 'duplicate_finish'}
            invocation, record = store.begin_invocation(key, record['revision'], 'effect', lease=lease, arguments={}, definition_hash='isolated-definition', write=write, retry_safe=not write, resource_keys=('campaign-disposable-effect',))
            if case.get('effect', False):
                path = root / 'effect.txt'
                path.write_text('exactly one isolated effect\n', encoding='utf-8')
                actions.append({'operation': 'isolated_fixture_effect', 'path': str(path), 'count': 1})
            if probe in {'recover_read', 'recover_write', 'stale_finish', 'uncertain_replay'}:
                clock.advance(11)
                replacement = store.claim(str(uuid4()))
                store.recover(replacement)
                actions.append({'operation': 'recover', 'ok': True})
                if probe == 'stale_finish':
                    _attempt(actions, 'stale_finish', lambda: store.finish_invocation(invocation['invocation_id'], lease=lease, result={'ok': True, 'data': {'value': 1}}, step_status='verified', verification={'status': 'VERIFIED'}))
                if probe == 'uncertain_replay':
                    current = store.get(key)
                    _attempt(actions, 'uncertain_replay', lambda: store.begin_invocation(key, current['revision'], 'effect', lease=replacement, arguments={}, definition_hash='isolated-definition', write=True))
            elif probe == 'receipt_failure':
                _attempt(actions, 'invalid_receipt', lambda: store.finish_invocation(invocation['invocation_id'], lease=lease, result={'ok': True, 'data': {'value': float('nan')}}, step_status='verified'))
                store.abandon_invocation(invocation['invocation_id'], lease, 'Unretainable fixture receipt')
            else:
                store.finish_invocation(invocation['invocation_id'], lease=lease, result={'ok': True, 'data': {'value': 1}}, step_status='verified', verification={'status': 'VERIFIED'})
                _attempt(actions, 'duplicate_finish', lambda: store.finish_invocation(invocation['invocation_id'], lease=lease, result={'ok': True, 'data': {'value': 2}}, step_status='verified', verification={'status': 'VERIFIED'}))
        elif probe == 'lease_conflict':
            _attempt(actions, probe, lambda: store.claim(str(uuid4())))
        elif probe == 'stale_plan':
            _attempt(actions, probe, lambda: store.update(key, record['revision'] - 1, {'status': 'running'}))
        elif probe == 'idempotency':
            operation_id = str(uuid4())
            one = store.execute_request(operation_id, {'action': 'same'}, {'actor': 'owner'}, lambda: {'effect': 1})
            two = store.execute_request(operation_id, {'action': 'same'}, {'actor': 'owner'}, lambda: {'effect': 2})
            actions.append({'operation': probe, 'ok': one == two, 'first': one, 'second': two})
            _attempt(actions, 'changed_replay', lambda: store.execute_request(operation_id, {'action': 'different'}, {'actor': 'owner'}, lambda: {'effect': 3}))
        elif probe == 'checkpoint_reopen':
            before = store.history(key)
            store.close()
            after = store.history(key)
            actions.append({'operation': probe, 'ok': before == after})
        else:
            raise ValueError('Unknown store probe: ' + probe)
        receipt.update(workflow={**store.get(key), 'steps': store.steps(key), **store.history(key)}, controls=actions, files={path.name: {'text': path.read_text(encoding='utf-8')} for path in root.glob('*.txt')})
    except Exception as exc:
        receipt['harness_error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        store.close()
    receipt['duration_ms'] = (time.monotonic() - started) * 1000
    return receipt

def _attempt(actions, operation, callback):
    try:
        value = callback()
        actions.append({'operation': operation, 'ok': True, 'result': value})
    except Exception as exc:
        actions.append({'operation': operation, 'ok': False, 'error_type': type(exc).__name__, 'error': str(exc)})

def transition_atomicity(root):
    """Enumerate every declared edge dynamically and inject stale CAS at commit.

    A direct-store test of each supported edge is not scheduler reachability.
    The full before/after projection and history prove transactional rejection.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    outcomes = []
    for source, targets in sorted(TRANSITIONS.items()):
        for target in sorted(targets):
            store = WorkflowStore(root / (source + '-' + target))
            try:
                record = store.create('Isolated dynamic transition atomicity', 'assisted')
                queue, visited = ([('submitted', [])], set())
                path = None
                while queue:
                    state, route = queue.pop(0)
                    if state == source:
                        path = route
                        break
                    if state in visited:
                        continue
                    visited.add(state)
                    queue.extend(((edge, route + [edge]) for edge in sorted(TRANSITIONS.get(state, ()))))
                if path is None:
                    outcomes.append({'source': source, 'target': target, 'classification': 'BLOCKED_UNREACHABLE_GRAPH'})
                    continue
                for state in path:
                    record = store.update(record['workflow_id'], record['revision'], {'status': state})
                key = record['workflow_id']
                before = {'record': store.get(key), 'history': store.history(key)}
                rejected = False
                try:
                    store.update(key, record['revision'] - 1, {'status': target}, kind='injected_stale_commit')
                except WorkflowError:
                    rejected = True
                after = {'record': store.get(key), 'history': store.history(key)}
                actual = store.update(key, record['revision'], {'status': target}, kind='actual_edge_commit')
                outcomes.append({'source': source, 'target': target, 'scope': 'direct_original_store_CAS_boundary', 'rejected': rejected, 'before_hash': fingerprint(before), 'after_rejection_hash': fingerprint(after), 'edge_committed_status': actual['status'], 'passed': rejected and before == after and (actual['status'] == target)})
            except Exception as exc:
                outcomes.append({'source': source, 'target': target, 'passed': False, 'harness_error': {'type': type(exc).__name__, 'message': str(exc)}})
            finally:
                store.close()
    return outcomes
