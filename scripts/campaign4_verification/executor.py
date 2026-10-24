"""Input-only original workflow execution over strictly owned disposable files.

The planner replies, declared leaf faults and post-commit observer are controlled
protocol seams. Tool definitions, schemas, authority, scheduling, verification
and durable state retain their original implementations. No expected outcome is
read here. Actual subprocess interruption is confined to a parent-owned nonce.
"""
from __future__ import annotations
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from uuid import uuid4
from unittest.mock import patch
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.tools import build_default_registry
from hanni.workflows.service import WorkflowService
from hanni.workflows.store import WorkflowStore
from hanni.workflows.types import TERMINAL, WorkflowLimits
from scripts.campaign4.workflow_harness import expand, setup_environment
ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path(os.environ.get('PYTEST_HANNI_CAMPAIGN4_ROOT', ROOT / 'data/campaign4-verifier')).resolve()

def durable(path, value):
    path = Path(path)
    stage = path.with_name(path.name + '.publishing')
    stage.parent.mkdir(parents=True, exist_ok=True)
    with stage.open('w', encoding='utf8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2, default=str)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(stage, path)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class ProtocolClient:

    def __init__(self, case, root):
        self.case, self.root, self.calls, self.phase = (case, root, [], 0)

    def chat(self, messages, **kwargs):
        payload = json.loads(messages[-1]['content'])
        analysis = kwargs.get('response_format', {}).get('json_schema', {}).get('name') == 'hanni_workflow_evidence'
        if analysis:
            step = next((row for row in self.case['steps'] if row['description'] == payload['description']))
            reply = self.case['analysis_replies'][step['step_id']]
            text = reply if isinstance(reply, str) else json.dumps(reply)
            phase = 'analysis'
        else:
            phase = 'outline' if self.phase == 0 else 'binding'
            self.phase += 1
            steps = expand(self.case['steps'], self.root, Path(payload['artifact_root']))
            fields = ('step_id', 'description', 'kind', 'dependencies', 'required', 'criteria')
            reply = {'summary': 'Controlled original workflow protocol.', 'unsupported_reason': None, 'steps': [{key: row[key] for key in fields} for row in steps]} if phase == 'outline' else {'unsupported_reason': None, 'steps': [{key: row[key] for key in ('step_id', 'capability_id', 'arguments')} for row in steps]}
            for fault in self.case.get('faults', []):
                if fault.get('kind') != 'planner_reply' or fault.get('stage') != phase:
                    continue
                if 'unsupported_reason' in fault:
                    reply['unsupported_reason'] = fault['unsupported_reason']
                reply.update(fault.get('extra_fields', {}))
                if 'replace_capability_id' in fault and reply['steps']:
                    reply['steps'][0]['capability_id'] = fault['replace_capability_id']
                if 'reference_step_id' in fault:

                    def substitute(value):
                        if isinstance(value, dict):
                            if '$ref' in value:
                                value['$ref']['step_id'] = fault['reference_step_id']
                            else:
                                for item in value.values():
                                    substitute(item)
                        elif isinstance(value, list):
                            for item in value:
                                substitute(item)
                    substitute(reply)
            text = json.dumps(reply)
        self.calls.append({'phase': phase, 'messages': deepcopy(messages), 'kwargs': deepcopy(kwargs), 'raw_response': text, 'actual_model_inference': False})
        return text

class Execution:

    def __init__(self, case, env, *, recovering=False, allow_exit=False):
        if 'expected' in case:
            raise ValueError('An oracle cannot enter execution')
        self.case, self.env, self.recovering, self.allow_exit = (case, env, recovering, allow_exit)
        self.events, self.controls, self.handlers, self.effects, self.intervals, self.notifications = ([], [], [], [], [], [])
        self.done, self.fault_counts, self.active, self.frame_rows = (set(), {}, {}, {})
        self.lock = threading.RLock()
        self.barrier = threading.Condition(self.lock)
        self.original_read, self.original_write, self.original_copy = (Path.read_text, Path.write_text, shutil.copy2)
        self.original_read_bytes = Path.read_bytes
        self.original_profile, self.original_thread_profile = (sys.getprofile(), threading.getprofile())
        self.submit_request = None
        self.initial_recovery = self.env.service.detail(self.env.key) if recovering else None
        self.current_phase = 'recover' if recovering else 'initial'
        for row in self.case.get('steps', []):
            capability = row.get('capability_id')
            if capability:
                try:
                    definition = self.env.registry.get(capability)
                    self.frame_rows[definition.handler.__code__] = capability
                except Exception:
                    pass
        if recovering:
            previous = json.loads((env.root / 'interrupted.json').read_text(encoding='utf8'))
            self.done = set(previous['performed_controls'])
            self.controls = previous['controls']
            self.events = previous['observer_events']
            self.handlers = previous['handler_entries']
            self.effects = previous['effect_ledger']
            self.intervals = previous['io_intervals']
            self.notifications = previous.get('notifications', [])
            self.submit_request = previous['submit_request']

    def detail(self):
        return self.env.service.detail(self.env.key)

    def invocation(self, correlation=None, invocation_id=None):
        from hanni.reliability.context import current_correlation_id
        correlation = correlation or current_correlation_id()
        return next((item for item in self.env.service.store.history(self.env.key)['invocations'] if item['invocation_id'] == invocation_id or item['correlation_id'] == correlation), None)

    def profile(self, frame, event, argument):
        if event != 'call' or frame.f_code not in self.frame_rows:
            return
        request = frame.f_locals.get('request')
        with self.lock:
            invocation = self.invocation(getattr(request, 'correlation_id', None))
            definition = self.env.registry.get(self.frame_rows[frame.f_code])
            sensitive = definition.permission_level > 0 or definition.risk_level > 0
            self.handlers.append({'sequence': len(self.handlers) + 1, 'capability_id': self.frame_rows[frame.f_code], 'module': frame.f_globals.get('__name__'), 'function': frame.f_code.co_name, 'invocation_id': invocation.get('invocation_id') if invocation else None, 'step_id': invocation.get('step_id') if invocation else None, 'correlation_id': getattr(request, 'correlation_id', None), 'phase': self.current_phase, 'handler_time_perf_counter': time.perf_counter(), 'sensitive': sensitive, 'actor_profile': getattr(request, 'actor_profile', None), 'confirmed': getattr(request, 'confirmed', None), 'execution_guard_present': callable(getattr(request, 'execution_guard', None)), 'authorized_sensitive_dispatch': bool(not sensitive or (invocation and invocation['state'] == 'dispatched' and invocation['write'] and (getattr(request, 'actor_profile', None) == 'owner') and (getattr(request, 'confirmed', None) is True) and callable(getattr(request, 'execution_guard', None))))})

    def observe(self, stage, event):
        invocation = self.invocation(invocation_id=event.get('invocation_id')) if event.get('invocation_id') else event
        step_id = (invocation or {}).get('step_id')
        self.events.append({'stage': stage, 'step_id': step_id, 'event': deepcopy(event), 'monotonic': time.monotonic(), 'phase': self.current_phase})
        self.perform(stage + ':' + step_id if step_id else stage)

    def notify(self, event):
        key = event['target']['id']
        record = self.env.service.store.get(key)
        steps = self.env.service.store.steps(key)
        self.notifications.append({'event': deepcopy(event), 'original_status_at_emission': record['status'], 'required_step_statuses': {row['step_id']: row['status'] for row in steps if row['required']}, 'delivery_scope': 'original workflow sink observed; physical desktop delivery not tested'})

    def effect_row(self, path, invocation):
        detail = self.detail()
        scope = detail.get('scope') or {}
        approval = next((row for row in detail.get('approvals', []) if row['approval_id'] == scope.get('approval_id')), None)
        now = self.env.clock.wall()
        reviewed = bool(approval and approval['state'] == 'approved' and (approval['plan_hash'] == detail['plan_hash']))
        expires = datetime.fromisoformat(approval['expires_at'].replace('Z', '+00:00')).timestamp() if approval else 0
        exact = next((row for row in detail.get('approvals', []) if invocation and row['approval_id'] == invocation.get('approval_id')), None)
        managed = Path(path).is_relative_to(self.env.service._artifact_root(self.env.key))
        action_authority = bool(exact and exact['state'] == 'consumed' and (exact['argument_hash'] == invocation['argument_hash']) and (exact['definition_hash'] == invocation['definition_hash']))
        row = {'sequence': len(self.effects) + 1, 'effect_id': (invocation or {}).get('invocation_id', 'missing') + ':effect', 'invocation_id': (invocation or {}).get('invocation_id'), 'step_id': (invocation or {}).get('step_id'), 'workflow_id': self.env.key, 'correlation_id': (invocation or {}).get('correlation_id'), 'path': str(path), 'logical_operation': self.env.key + '/' + (invocation or {}).get('step_id', 'missing'), 'managed': managed, 'reviewed_plan': reviewed, 'exact_action_approval': action_authority, 'scope_expires': scope.get('expires'), 'authority_time': now, 'authorized': bool(invocation and invocation['write'] and (invocation['state'] == 'dispatched') and reviewed and (expires > now) and (scope.get('expires', 0) > now) and (scope.get('actor_profile') == 'owner') and (scope.get('plan_hash') == detail['plan_hash']) and (scope.get('provenance') == 'owner_plan_review') and (action_authority or (managed and detail['mode'] != 'supervised'))), 'actual_effect': False, 'returned': False, 'phase': self.current_phase}
        self.effects.append(row)
        return row

    def io(self, method, path, function, args, kwargs):
        caller = inspect.currentframe().f_back.f_back
        if caller.f_globals.get('__name__') != 'hanni.tools.files':
            return function(path, *args, **kwargs)
        actual = Path(path).resolve()
        destination = Path(args[0]).resolve() if method == 'copy' else actual
        if not actual.is_relative_to(self.env.root) or not destination.is_relative_to(self.env.root):
            raise AssertionError('Original handler I/O escaped the exact owned fixture')
        invocation = self.invocation()
        step_id = (invocation or {}).get('step_id')
        kind = 'write' if method in {'write', 'copy'} else 'read'
        with self.lock:
            interval = {'invocation_id': (invocation or {}).get('invocation_id'), 'step_id': step_id, 'kind': kind, 'entered': time.perf_counter(), 'left': None, 'phase': self.current_phase, 'clock': 'perf_counter high resolution'}
            self.intervals.append(interval)
            count_key = (method, step_id)
            count = self.fault_counts[count_key] = self.fault_counts.get(count_key, 0) + 1
            effect = self.effect_row(destination, invocation) if kind == 'write' else None
        fault = next((row for row in self.case.get('faults', []) if row.get('kind') == 'leaf_failure' and row.get('step_id') == step_id and (count <= row.get('times', 1))), None)
        barrier = next((row for row in self.case.get('faults', []) if row.get('kind') == 'barrier' and step_id in row.get('step_ids', [])), None)
        try:
            if barrier:
                self.perform('barrier:' + step_id)
                if barrier.get('release_after_both_enter'):
                    with self.barrier:
                        self.active[step_id] = True
                        self.barrier.notify_all()
                        end = time.monotonic() + 5
                        while not all((self.active.get(key) for key in barrier['step_ids'])):
                            remaining = end - time.monotonic()
                            if remaining <= 0:
                                raise TimeoutError('The original safe reads did not overlap')
                            self.barrier.wait(remaining)
            if fault and fault.get('when', 'before') == 'before':
                error = {'TimeoutError': TimeoutError, 'ConnectionError': ConnectionError, 'PermissionError': PermissionError}[fault['type']]
                raise error('Controlled owned original I/O fault')
            result = function(path, *args, **kwargs)
            if effect:
                effect.update(actual_effect=True, sha256=digest(destination), size_bytes=destination.stat().st_size)
                durable(self.env.root / 'effect-ledger.json', self.effects)
            tamper = next((row for row in self.case.get('faults', []) if row.get('kind') == 'tamper_artifact' and row.get('step_id') == step_id and (row.get('when') == 'before_verification')), None)
            if tamper and kind == 'write':
                self.original_write(destination, tamper['text'], encoding='utf8')
                self.events.append({'stage': 'declared_fixture_tamper', 'step_id': step_id, 'scope': 'fault injection separate from original handler effect'})
            if fault and fault.get('when') == 'after':
                raise TimeoutError('Controlled owned timeout after actual I/O')
            if effect:
                effect['returned'] = True
            return result
        finally:
            interval['left'] = time.perf_counter()

    def perform(self, stage):
        """Consume only declared controls in their authored order, exactly once."""
        for index, row in enumerate(self.case.get('controls', [])):
            if index in self.done:
                continue
            if row['at'] != stage:
                break
            self.done.add(index)
            operation = row['operation']
            detail = self.detail()
            receipt = {'index': index, 'at': stage, 'operation': operation, 'before_status': detail['status'], 'before_revision': detail['revision'], 'phase': self.current_phase, 'control_time_perf_counter': time.perf_counter()}
            try:
                if operation == 'observe_no_dispatch':
                    receipt['observed_invocations'] = [item['invocation_id'] for item in detail['invocations']]
                    receipt['observed_effects'] = sum((item['actual_effect'] for item in self.effects))
                    receipt['no_active_dispatch'] = not any((item['state'] == 'dispatched' for item in detail['invocations']))
                elif operation == 'reopen_store_readback':
                    authoritative = {**self.env.service.store.get(self.env.key), 'steps': self.env.service.store.steps(self.env.key), **self.env.service.store.history(self.env.key)}
                    reopened = WorkflowStore(self.env.root / 'data')
                    try:
                        receipt['durable_detail'] = {**reopened.get(self.env.key), 'steps': reopened.steps(self.env.key), **reopened.history(self.env.key)}
                        receipt['readback_equal'] = all((receipt['durable_detail'][key] == authoritative[key] for key in ('revision', 'status', 'steps', 'checkpoints', 'invocations', 'approvals')))
                    finally:
                        reopened.close()
                elif operation == 'replay_submit_same_id':
                    result = self.env.service.mutate(deepcopy(self.submit_request))
                    receipt['same_workflow'] = result['workflow_id'] == self.env.key
                elif operation == 'detach':
                    self.env.service.detach()
                elif operation == 'release':
                    self.env.faults.released.set()
                elif operation == 'owned_process_exit':
                    if not self.allow_exit:
                        raise ValueError('Actual exit requires a parent-owned subprocess nonce')
                    self.controls.append({**receipt, 'ok': True, 'owned_exit': True})
                    durable(self.env.root / 'interrupted.json', self.receipt())
                    os._exit(83)
                elif operation == 'restart':
                    if self.recovering:
                        receipt['actual_new_process'] = True
                    else:
                        raise ValueError('Process restart cannot be simulated in process')
                else:
                    original_operation = operation.replace('_expect_denial', '')
                    extra = {key: value for key, value in row.items() if key not in {'at', 'operation'}}
                    if extra.pop('tamper_argument_hash', False):
                        extra['alter_binding'] = 'argument_hash'
                    control = self.env.control(original_operation, **extra)
                    receipt.update(control)
                    receipt['operation'] = operation
                    receipt['original_control_operation'] = original_operation
                    if not control['ok']:
                        receipt['expected_denial_control'] = operation.endswith('_expect_denial')
                    receipt['after_status'] = self.detail()['status']
                    self.controls.append(receipt)
                    continue
                receipt['ok'] = True
            except Exception as exc:
                receipt.update(ok=False, error_type=type(exc).__name__, error=str(exc))
            receipt['after_status'] = self.detail()['status']
            self.controls.append(receipt)
            if stage in {'ready', 'paused', 'blocked'} and receipt['after_status'] != stage:
                break

    def receipt(self):
        detail = self.detail()
        definitions = []
        for capability in sorted({row.get('capability_id') for row in self.case.get('steps', []) if row.get('capability_id')}):
            try:
                definition = self.env.registry.get(capability)
                definitions.append({'name': capability, 'retry_safe': definition.retry_safe, 'permission_level': definition.permission_level, 'risk_level': definition.risk_level, 'handler_module': definition.handler.__module__, 'handler_name': definition.handler.__qualname__})
            except Exception as exc:
                definitions.append({'name': capability, 'unavailable': type(exc).__name__})
        files = {}
        for path in self.env.root.rglob('*'):
            if path.is_file() and path.suffix in {'.txt', '.md', '.csv', '.log', '.json'} and (path.stat().st_size <= 300000):
                files[path.relative_to(self.env.root).as_posix()] = {'text': path.read_bytes().decode('utf8', errors='replace'), 'sha256': digest(path), 'size_bytes': path.stat().st_size}
        return {'id': self.case['id'], 'category': self.case['category'], 'scenario': self.case['scenario'], 'execution_scope': 'native_original_scheduler_isolated', 'workflow': detail, 'files': files, 'controls': self.controls, 'performed_controls': sorted(self.done), 'observer_events': self.events, 'handler_entries': self.handlers, 'effect_ledger': self.effects, 'io_intervals': self.intervals, 'planner_calls': self.env.client.calls, 'notifications': self.notifications, 'submit_request': self.submit_request, 'actual_model_calls': 0, 'model_semantic_quality': 'UNMEASURED_CONTROLLED_PROTOCOL_REPLIES', 'runner_error': self.env.service.runner_error, 'original_definitions': definitions, 'lease': deepcopy(self.env.service.lease), 'fixture_resource_admission': 'controlled_private_fixture', 'workflow_count': len(self.env.service.store.list(100)), 'initial_recovery_snapshot': self.initial_recovery, 'harness_error': None}

    def execute(self):
        started = time.monotonic()
        client = ProtocolClient(self.case, self.env.root)
        self.env.client = client
        self.env.service.client = client
        self.env.host.allowed_actions = tuple(dict.fromkeys((*self.env.host.allowed_actions, *self.case.get('allowed_actions', []))))
        if not self.recovering:
            self.env.service.detach()
        else:
            client = self.env.client = self.env.service.client
        if not self.recovering:
            self.env.service.attach(self.env.registry, client, host=self.env.host, resource_probe=lambda: {'allowed': True, 'ram_percent': 20, 'gpu': None}, notification_sink=self.notify)
            self.env.service.start()
        else:
            self.env.service.notification_sink = self.notify
        self.env.service.observer = self.env.service.store.observer = self.observe
        original_finish = self.env.service.store.finish_invocation

        def finished(invocation_id, **kwargs):
            actual = original_finish(invocation_id, **kwargs)
            invocation = self.invocation(invocation_id=invocation_id)
            step = next((row for row in self.env.service.store.steps(self.env.key) if row['step_id'] == invocation['step_id']))
            if step['status'] == 'verified':
                self.events.append({'stage': 'verified_post_commit', 'step_id': step['step_id'], 'invocation_id': invocation_id, 'original_commit_returned': True})
                self.perform('verified:' + step['step_id'])
            return actual
        with ExitStack() as stack:
            stack.enter_context(patch.object(Path, 'read_text', lambda path, *args, **kwargs: self.io('read', path, self.original_read, args, kwargs)))
            stack.enter_context(patch.object(Path, 'read_bytes', lambda path, *args, **kwargs: self.io('read', path, self.original_read_bytes, args, kwargs)))
            stack.enter_context(patch.object(Path, 'write_text', lambda path, *args, **kwargs: self.io('write', path, self.original_write, args, kwargs)))
            stack.enter_context(patch.object(shutil, 'copy2', lambda path, *args, **kwargs: self.io('copy', path, self.original_copy, args, kwargs)))
            stack.enter_context(patch.object(self.env.service.store, 'finish_invocation', finished))
            sys.setprofile(self.profile)
            threading.setprofile(self.profile)
            try:
                if not self.recovering:
                    self.submit_request = {'id': str(uuid4()), 'operation': 'goal.submit', 'data': {'goal': expand(self.case['goal'], self.env.root), 'mode': self.case.get('mode', 'assisted')}}
                    result = self.env.service.mutate(self.submit_request)
                    self.env.key = result['workflow_id']
                    self.env.service.wait(self.env.key, timeout=8)
                    self.perform('planned')
                else:
                    self.perform('stopped')
                fired_faults = set()
                end = time.monotonic() + 13
                while time.monotonic() < end:
                    detail = self.detail()
                    stage = detail['status']
                    for index, fault in enumerate(self.case.get('faults', [])):
                        if index not in fired_faults and fault.get('kind') == 'unregister' and (fault.get('at') == stage):
                            fired_faults.add(index)
                            definition = self.env.registry.get(fault['capability_id'])
                            removed = self.env.registry.unregister(fault['capability_id'], expected=definition)
                            self.events.append({'stage': 'declared_definition_withdrawal', 'removed': removed, 'capability_id': fault['capability_id']})
                    before = len(self.done)
                    self.perform('waiting_approval' if stage == 'awaiting_step_approval' else stage)
                    if self.detail()['status'] != stage or len(self.done) != before:
                        continue
                    live = any((key[0] == self.env.key for key in self.env.service.workers))
                    if stage in TERMINAL | {'blocked', 'paused', 'awaiting_step_approval', 'ready'} and (not live):
                        self.perform('stopped')
                        if self.detail()['status'] == stage:
                            break
                    time.sleep(0.01)
                receipt = self.receipt()
                receipt['pending_controls'] = [dict(index=index, **row) for index, row in enumerate(self.case.get('controls', [])) if index not in self.done]
                receipt['duration_ms'] = (time.monotonic() - started) * 1000
                return receipt
            finally:
                sys.setprofile(self.original_profile)
                threading.setprofile(self.original_thread_profile)

def run_case(case, root):
    started = time.monotonic()
    root = Path(root).resolve()
    if not root.is_relative_to(PRIVATE):
        raise ValueError('Verifier execution must remain inside its private owned directory')
    if any((row.get('operation') == 'owned_process_exit' for row in case.get('controls', []))):
        return run_process_case(case, root)
    with setup_environment(case, root) as environment:
        execution = Execution(case, environment)
        try:
            receipt = execution.execute()
        except Exception as exc:
            receipt = execution.receipt() if environment.key else {'id': case['id'], 'category': case['category'], 'scenario': case['scenario']}
            receipt['harness_error'] = {'type': type(exc).__name__, 'message': str(exc)}
    receipt['native_controller_duration_ms'] = receipt.get('duration_ms')
    receipt['duration_ms'] = (time.monotonic() - started) * 1000
    return receipt

def process_identity(phase, root):
    import psutil
    current = psutil.Process()
    return {'pid': current.pid, 'parent_pid': current.ppid(), 'create_time': current.create_time(), 'executable': current.exe(), 'command': current.cmdline(), 'root': str(root), 'phase': phase}

def child(root, phase, nonce):
    marker = json.loads((root / 'owned-process.json').read_text(encoding='utf8'))
    if marker.get('nonce') != nonce or marker.get('root') != str(root) or (not root.is_relative_to(PRIVATE)):
        raise ValueError('A verified parent-owned nonce is required')
    case = json.loads((root / 'input.json').read_text(encoding='utf8'))
    execution_root = root / 'fixture'
    durable(root / (phase + '-identity.json'), process_identity(phase, root))
    if phase == 'interrupt':
        with setup_environment(case, execution_root) as env:
            receipt = Execution(case, env, allow_exit=True).execute()
            durable(root / 'unexpected-no-interruption.json', receipt)
            raise RuntimeError('Declared owned process boundary was not reached')
    from scripts.campaign4.workflow_harness import Environment, FixtureClock, LeafFaults
    from scripts.v3_review.service_fixture import EmptyProviderVault
    config = load_config(execution_root / 'config', data_dir=execution_root / 'data', env={})
    registry = build_default_registry(config)
    registry.google_access._vault = EmptyProviderVault()
    host = McpHost(registry, read_only=True)
    host.allowed_actions = tuple(dict.fromkeys((*host.allowed_actions, 'file.write', *case.get('allowed_actions', []))))
    clock = FixtureClock()
    service = WorkflowService(execution_root / 'data', WorkflowLimits(**case.get('limits', {})), protected_roots=(execution_root / 'config',))
    client = ProtocolClient(case, execution_root)
    service.attach(registry, client, host=host, resource_probe=lambda: {'allowed': True, 'ram_percent': 20, 'gpu': None})
    env = Environment(execution_root, case, clock, registry, host, client, service, LeafFaults(execution_root, []), [])
    previous = json.loads((execution_root / 'interrupted.json').read_text(encoding='utf8'))
    env.key = previous['workflow']['workflow_id']
    try:
        service.start()
        receipt = Execution(case, env, recovering=True).execute()
        receipt['initial_recovery_status'] = next((row.get('before_status') for row in receipt['controls'] if row.get('phase') == 'recover'), None)
        durable(root / 'receipt.json', receipt)
    finally:
        service.close()
        service.store.close()

def run_process_case(case, root):
    started = time.monotonic()
    root.mkdir(parents=True, exist_ok=False)
    nonce = str(uuid4())
    durable(root / 'owned-process.json', {'nonce': nonce, 'root': str(root), 'owner': 'independent_verifier'})
    durable(root / 'input.json', case)
    children = []
    for phase, expected in (('interrupt', 83), ('recover', 0)):
        command = [sys.executable, '-X', 'utf8', '-m', 'scripts.campaign4_verification.executor', '--child', phase, '--root', str(root), '--nonce', nonce]
        with (root / (phase + '-stdout.log')).open('w', encoding='utf8') as stdout, (root / (phase + '-stderr.log')).open('w', encoding='utf8') as stderr:
            helper = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                status = helper.wait(timeout=25)
            except subprocess.TimeoutExpired:
                import psutil
                identity = json.loads((root / (phase + '-identity.json')).read_text(encoding='utf8'))
                owned = psutil.Process(identity['pid'])
                if (owned.pid == helper.pid or owned.ppid() == helper.pid) and owned.create_time() == identity['create_time'] and (owned.exe() == identity['executable']) and (identity['root'] == str(root)):
                    owned.kill()
                    owned.wait(5)
                if helper.poll() is None:
                    helper.kill()
                helper.wait(5)
                raise RuntimeError('The owned helper exceeded its bounded time')
        identity = json.loads((root / (phase + '-identity.json')).read_text(encoding='utf8'))
        children.append({'launcher_pid': helper.pid, 'exit_code': status, 'identity': identity, 'parent_verified': identity['pid'] == helper.pid or identity['parent_pid'] == helper.pid})
        if status != expected:
            raise RuntimeError('Owned helper ' + phase + ' failed; retained logs: ' + str(root))
        if phase == 'interrupt':
            time.sleep(1.2)
    receipt = json.loads((root / 'receipt.json').read_text(encoding='utf8'))
    receipt['processes'] = children
    receipt['interruption'] = json.loads((root / 'fixture/interrupted.json').read_text(encoding='utf8'))
    receipt['actual_owned_process_restart'] = True
    receipt['owner_processes_changed'] = False
    receipt['recovery_controller_duration_ms'] = receipt.get('duration_ms')
    receipt['duration_ms'] = (time.monotonic() - started) * 1000
    import psutil
    receipt['owned_children_closed'] = all((not psutil.pid_exists(row['identity']['pid']) or psutil.Process(row['identity']['pid']).create_time() != row['identity']['create_time'] for row in children))
    return receipt
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--child', choices=['interrupt', 'recover'], required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--nonce', required=True)
    args = parser.parse_args()
    child(args.root.resolve(), args.child, args.nonce)
