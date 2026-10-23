"""Observes the original controller/registry; never schedules or grants access."""
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import re
import threading
import weakref
from uuid import uuid4

from .context import _task, _step, _source, _attempt, current_request_id, safe_source
from .store import TraceStore

STATES = frozenset({'REQUESTED', 'PLANNED', 'AWAITING_APPROVAL', 'EXECUTING', 'TOOL_COMPLETED',
                   'VERIFYING', 'VERIFIED', 'PARTIALLY_VERIFIED', 'UNVERIFIED', 'REPORTED',
                   'FAILED', 'CANCELLED', 'TIMED_OUT', 'REJECTED'})

def stamp():
    return datetime.now(timezone.utc).isoformat()

def error_class(error):
    name = type(error).__name__
    if name == 'ConfirmationRequired': return 'CONFIRMATION_REQUIRED'
    if name in {'EmergencyStopActive', 'CancelledError', 'GeneratorExit'}: return 'CANCELLED'
    if isinstance(error, TimeoutError): return 'TIMED_OUT'
    if name in {'ToolPermissionError', 'PermissionError'}: return 'PERMISSION_DENIED'
    if name in {'ToolValidationError', 'ValueError', 'TypeError'}: return 'INVALID_ARGUMENTS'
    if name == 'UnknownToolError': return 'UNAVAILABLE_CAPABILITY'
    return 'EXECUTION_FAILED'

def safe_capability(name):
    return name if isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,256}', name) else 'unknown'

class TaskTrace:
    def __init__(self, service, source):
        self.service = service
        self.record = {'request_id': current_request_id() or str(uuid4()), 'task_id': str(uuid4()),
            'source': safe_source(_source.get() if current_request_id() else source),
            'created_at': stamp(), 'completed_at': None, 'state': 'REQUESTED',
            'execution_status': 'not_requested', 'verification_status': 'UNVERIFIED',
            'selected_capabilities': [], 'candidate_capabilities': [], 'summary': 'Request received.', 'error_class': None,
            'retry_count': 0, 'steps': [], 'events': []}
        self.emit('REQUESTED')

    def emit(self, state, step=None):
        if state not in STATES:
            return
        with self.service.lock:
            timestamp = stamp()
            target = step or self.record
            target['state'] = state
            if len(target['events']) < 160:
                target['events'].append({'state': state, 'timestamp': timestamp})
            if step:
                self.record['state'] = state
            self.service.publish(self.record, state, timestamp)

    def select(self, names):
        self.record['candidate_capabilities'] = list(dict.fromkeys(safe_capability(name) for name in names))[:32]
        self.emit('PLANNED')

    def begin(self, name):
        if len(self.record['steps']) >= 64:
            self.record['truncated_steps'] = True
            self.record['error_class'] = 'TRACE_LIMIT_REACHED'
            return None
        name = safe_capability(name)
        step = {'step_id': str(uuid4()), 'capability_id': name, 'state': 'REQUESTED',
                'started_at': stamp(), 'completed_at': None, 'attempts': 1,
                'approval': 'not_evaluated', 'verification': None, 'error_class': None, 'events': []}
        attempt = _attempt.get()
        if attempt:
            step['attempt_group'], step['attempts'] = attempt
        self.record['steps'].append(step)
        if name not in self.record['selected_capabilities']:
            self.record['selected_capabilities'].append(name)
        self.emit('REQUESTED', step)
        self.emit('PLANNED', step)
        return step

    def authorized(self, step, confirmed):
        if step:
            step['approval'] = 'explicit_confirmation' if confirmed else 'policy_granted'
            self.emit('EXECUTING', step)

    def complete(self, step, result, verification):
        if not step:
            if not result.ok:
                code = (result.error or {}).get('code')
                self.record['error_class'] = 'TIMED_OUT' if code in {'TIMEOUT', 'TIMED_OUT'} else 'EXECUTION_FAILED'
            return
        step['completed_at'] = stamp()
        if result.ok:
            step['verification'] = verification
            self.emit(verification['status'], step)
        else:
            code = (result.error or {}).get('code', 'EXECUTION_FAILED')
            step['error_class'] = code if code in {'TIMEOUT', 'TIMED_OUT', 'CANCELLED', 'PERMISSION_DENIED',
                'AUTH_REQUIRED', 'API_ERROR', 'RATE_LIMITED', 'INVALID_ARGUMENTS', 'UNAVAILABLE_CAPABILITY'} else 'EXECUTION_FAILED'
            self.emit('TIMED_OUT' if code in {'TIMEOUT', 'TIMED_OUT'} else 'FAILED', step)

    def failed(self, step, error):
        if not step:
            self.record['error_class'] = error_class(error)
            return
        code = error_class(error)
        step['error_class'] = code
        step['completed_at'] = stamp()
        if code == 'CONFIRMATION_REQUIRED':
            step['approval'] = 'confirmation_required'
            self.emit('AWAITING_APPROVAL', step)
        state = ('CANCELLED' if code == 'CANCELLED' else 'TIMED_OUT' if code == 'TIMED_OUT'
                 else 'REJECTED' if code in {'CONFIRMATION_REQUIRED', 'PERMISSION_DENIED', 'INVALID_ARGUMENTS', 'UNAVAILABLE_CAPABILITY'} else 'FAILED')
        self.emit(state, step)

    def retry(self):
        self.record['retry_count'] += 1

    def finish(self, *, cancelled=False):
        if self.record.get('waiting_for_approval') and not cancelled:
            self.record['execution_status'] = 'waiting_approval'
            self.record['verification_status'] = 'UNVERIFIED'
            self.record['completed_at'] = None
            self.record['summary'] = 'The existing tool session is waiting for explicit confirmation.'
            self.emit('AWAITING_APPROVAL')
            return
        steps = self.record['steps']
        successes = [step for step in steps if step['verification'] is not None]
        failures = [step for step in steps if step['error_class'] and not step.get('superseded')]
        if self.record['retry_count']:
            failures = [step for index, step in enumerate(steps) if step['error_class'] and not step.get('superseded') and
                        not (step.get('attempt_group') and any(later.get('attempt_group') == step['attempt_group'] and later['verification']
                                for later in steps[index + 1:]))]
        if cancelled:
            self.record['execution_status'] = 'cancelled'
            self.record['error_class'] = 'CANCELLED'
            self.emit('CANCELLED')
        elif self.record['error_class']:
            code = self.record['error_class']
            self.record['execution_status'] = ('cancelled' if code == 'CANCELLED' else 'timed_out' if code == 'TIMED_OUT' else 'partial' if successes else
                'rejected' if code in {'PERMISSION_DENIED', 'CONFIRMATION_REQUIRED', 'INVALID_ARGUMENTS', 'UNAVAILABLE_CAPABILITY'} else 'failed')
        elif failures:
            last = failures[-1]['error_class']
            self.record['execution_status'] = 'partial' if successes else 'timed_out' if last in {'TIMEOUT', 'TIMED_OUT'} else 'rejected' if last in {'PERMISSION_DENIED', 'CONFIRMATION_REQUIRED', 'INVALID_ARGUMENTS'} else 'failed'
            self.record['error_class'] = last
        elif steps:
            self.record['execution_status'] = 'succeeded'
        values = [step['verification']['status'] for step in successes]
        status = ('VERIFIED' if values and all(value == 'VERIFIED' for value in values) and not failures and not self.record['error_class']
                  else 'PARTIALLY_VERIFIED' if any(value in {'VERIFIED', 'PARTIALLY_VERIFIED'} for value in values)
                  else 'UNVERIFIED')
        self.record['verification_status'] = status
        self.record['completed_at'] = stamp()
        self.record['summary'] = {'VERIFIED': 'The recorded evidence checks passed for their stated scopes.',
                                 'PARTIALLY_VERIFIED': 'Some outcomes have evidence; the remaining scope is unconfirmed.',
                                 'UNVERIFIED': 'The requested outcome is not verified.'}[status]
        self.emit('REPORTED')

class ReliabilityService:
    def __init__(self, data_dir=None):
        self.lock = threading.RLock()
        self.store = TraceStore(data_dir) if data_dir is not None else None
        self.live = OrderedDict()
        self.pending_owners = weakref.WeakValueDictionary()
        self.error = False

    def publish(self, record, state, timestamp):
        with self.lock:
            self.live[record['task_id']] = deepcopy(record)
            self.live.move_to_end(record['task_id'])
            while len(self.live) > 128:
                self.live.popitem(last=False)
            if self.store and not self.error:
                try:
                    self.store.append(record, state, timestamp)
                except Exception:
                    self.error = True  # Observer failure cannot reexecute actions.

    @contextmanager
    def task(self, source='local'):
        existing = _task.get()
        if existing:
            yield existing
            return
        trace = TaskTrace(self, source)
        token = _task.set(trace)
        cancelled = False
        try:
            yield trace
        except BaseException as exc:
            cancelled = error_class(exc) == 'CANCELLED'
            if not cancelled:
                trace.record['error_class'] = error_class(exc)
            raise
        finally:
            trace.finish(cancelled=cancelled)
            _task.reset(token)

    def snapshot(self, limit=50):
        with self.lock:
            rows = []
            if self.store and not self.error:
                try:
                    rows = self.store.snapshot(limit)
                except Exception:
                    self.error = True
            merged = {row['task_id']: row for row in rows}
            merged.update(self.live)
            records = sorted(merged.values(), key=lambda row: row['created_at'], reverse=True)[:max(1, min(100, int(limit)))]
            records = deepcopy(records)
            for record in records:
                if record.get('waiting_for_approval'):
                    owner = self.pending_owners.get(record['task_id'])
                    active = owner is not None and owner._pending_confirmation is not None and owner._pending_trace_id == record['task_id']
                    record['approval_active'] = active
                    if not active:
                        record['execution_status'] = 'approval_unavailable'
                        record['summary'] = 'Historical confirmation request; the originating tool session is unavailable.'
            return {'available': not self.error, 'tasks': deepcopy(records),
                    'reason': 'Execution trace storage is unavailable; the existing file was preserved.' if self.error else None}

    @contextmanager
    def resume_task(self, task_id):
        with self.lock:
            saved = self.live.get(task_id)
        if saved is None:
            with self.task('tool') as trace:
                yield trace
            return
        trace = TaskTrace.__new__(TaskTrace)
        trace.service, trace.record = self, deepcopy(saved)
        trace.record['waiting_for_approval'] = False
        trace.record['error_class'] = None
        for step in trace.record['steps']:
            if step['error_class'] == 'CONFIRMATION_REQUIRED':
                step['superseded'] = True
        token = _task.set(trace)
        try:
            yield trace
        finally:
            trace.finish()
            _task.reset(token)

    def cancel_pending(self, task_id):
        with self.resume_task(task_id) as trace:
            trace.record['waiting_for_approval'] = False
            trace.record['execution_status'] = 'cancelled'
            trace.record['error_class'] = 'CANCELLED'
            trace.emit('CANCELLED')

    def close(self):
        self.pending_owners.clear()
        if self.store:
            self.store.close()

_services = weakref.WeakValueDictionary()
_services_lock = threading.Lock()
def get_service(data_dir):
    from pathlib import Path
    key = str(Path(data_dir).resolve())
    with _services_lock:
        service = _services.get(key)
        if service is None:
            service = ReliabilityService(data_dir)
            _services[key] = service
        return service

def close_service(data_dir):
    from pathlib import Path
    key = str(Path(data_dir).resolve())
    with _services_lock:
        service = _services.pop(key, None)
    if service:
        service.close()

def safe_read_retry(definition, result):
    code = (result.get('error') or {}).get('code')
    return (definition.retry_safe is True and definition.retry_attempts > 0
            and (definition.side_effect == 'read' or (definition.side_effect is None and definition.risk_level == 0))
            and definition.permission_level == 0
            and definition.risk_level <= 1 and not definition.external_definition_hash
            and not definition.name.startswith('mcp.') and not result.get('ok')
            and (result.get('error') or {}).get('retryable') is True
            and code in {'TIMEOUT', 'TIMED_OUT', 'NETWORK_ERROR', 'API_ERROR', 'RATE_LIMITED'})
