"""Transparent placement for pure inference inside authoritative workflows."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import subprocess
import threading
import time
from uuid import uuid4

from .registry import ComputeError
from .transport import InferenceTransport


class _ComputeAdmissionWithdrawn(ComputeError):
    """Protected scope withdrawal is not an endpoint-health failure."""


def context_categories(completed, sources):
    """Categories come from trusted capability provenance, never model labels."""
    categories = {'project'}
    pending = [(source, frozenset()) for source in sources]
    seen = set()
    while pending:
        source, parents = pending.pop()
        if source in parents or source not in completed or len(parents) >= 64:
            raise ComputeError('Context provenance is missing or cyclic; private forwarding is blocked.')
        if source in seen:
            continue
        seen.add(source)
        step = completed[source]
        name = step.get('capability_id') or ''
        dependencies = step.get('dependencies', [])
        if not isinstance(dependencies, list) or step.get('kind') == 'analysis' and not dependencies:
            raise ComputeError('Analysis context requires complete trusted source provenance.')
        pending.extend((dep, parents | {source}) for dep in dependencies)
        if name.startswith(('memory.', 'memory_explorer.')):
            categories.add('memory')
        if name.startswith(('screen.', 'vision.', 'camera.')):
            categories.add('screen')
        if name.startswith(('google_', 'google.', 'email.', 'calendar.', 'clipboard.', 'security.', 'env.', 'mcp.')) or step.get('external_definition_hash'):
            categories.add('sensitive')
    return categories


class ComputeScheduler:
    def __init__(self, registry, *, transport=None, clock=time.monotonic):
        self.registry = registry
        self.transport = transport or InferenceTransport(registry)
        self.clock = clock
        self.condition = threading.Condition(registry.lock)
        self.waiting = []
        self.queued = {}
        self._queue_sequence = 0
        self.inflight = {}
        self.halt = threading.Event()
        self.monitor = None
        self.closed = False
        self.health_failures = {}
        self.health_wake = threading.Event()
        self.health_workers = {}
        self.health_locks = {}
        self.health_generation = 0

    def start_monitor(self):
        with self.condition:
            if self.monitor is None and not self.closed:
                self.monitor = threading.Thread(target=self._monitor, name='hanni-compute-health', daemon=True)
                self.monitor.start()

    def _monitor(self):
        while not self.halt.is_set():
            for worker in self.registry.workers():
                key = worker['worker_id']
                with self.condition:
                    if self.closed:
                        return
                    thread = self.health_workers.get(key)
                    if worker.get('enabled', False) and (thread is None or not thread.is_alive()):
                        thread = threading.Thread(target=self._monitor_worker, args=(key,),
                            name=f'hanni-health-{key}', daemon=True)
                        self.health_workers[key] = thread
                        thread.start()
            self.halt.wait(1)

    def _check_worker(self, worker):
        key = worker['worker_id']
        with self.condition:
            lock = self.health_locks.setdefault(key, threading.Lock())
        with lock:
            if self.halt.is_set():
                return
            try:
                health = self.transport.health(worker)
            except (ComputeError, OSError, subprocess.TimeoutExpired):
                health = {'status': 'unhealthy', 'model_id': None,
                    'last_heartbeat': self.registry.clock(),
                    'error': 'Worker health check could not complete. Retrying automatically.'}
            with self.condition:
                # Do not publish a late observation after shutdown or after the
                # protected worker definition/enablement changed during a check.
                if self.closed or self.registry.worker(key) != worker:
                    return
                self.health_failures[key] = 0 if health['status'] == 'healthy' else self.health_failures.get(key, 0) + 1
                self.registry.observe(key, **health)
                self.condition.notify_all()
            if health['status'] == 'healthy' and not self.halt.is_set():
                self._observe_resources(worker)

    def _monitor_worker(self, key):
        while not self.halt.is_set():
            with self.condition:
                try:
                    worker = self.registry.worker(key)
                except ComputeError:
                    return
                if not worker.get('enabled', False):
                    return
                generation = self.health_generation
            began = self.clock()
            try:
                self._check_worker(worker)
            except ComputeError:
                pass  # A removed/changed protected source has no health authority.
            with self.condition:
                failures = self.health_failures.get(key, 0)
                # Retry disconnected workers automatically, with a bounded
                # backoff. One slow node never delays another worker heartbeat.
                delay = 10 * min(6, 2 ** min(3, max(0, failures-1)))
                deadline = began + delay
                while not self.closed and generation == self.health_generation and self.clock() < deadline:
                    self.condition.wait(min(1, max(.01, deadline-self.clock())))

    def request_refresh(self):
        with self.condition:
            self.health_failures.clear()
            self.health_generation += 1
            self.condition.notify_all()
            self.health_wake.set()

    def _observe_resources(self, worker):
        try:
            observation = self.transport.resources(worker)
        except ComputeError:
            # A failed resource connection must neither kill health discovery
            # nor retain an older capacity reading as current admission proof.
            observation = {'ram_available_bytes': None, 'vram_free_bytes': None,
                'node_hardware': None, 'gpu_measurement': None, 'resource_sampled_at': None,
                'error': 'Worker resource measurements are unavailable.'}
        with self.condition:
            if not self.closed and self.registry.worker(worker['worker_id']) == worker:
                self.registry.observe(worker['worker_id'], **observation)

    def refresh(self):
        self.request_refresh()
        from concurrent.futures import ThreadPoolExecutor
        workers = [worker for worker in self.registry.workers() if worker.get('enabled', False)]
        with ThreadPoolExecutor(max_workers=max(1, min(8, len(workers)))) as pool:
            list(pool.map(self._check_worker, workers))
        with self.condition:
            self.condition.notify_all()
        return self.registry.snapshot()

    def _choices(self, categories, context_tokens, *, interactive=False, excluded=(), capabilities=('analysis',)):
        candidates = []
        for row in self.registry.snapshot()['workers']:
            key = row['worker_id']
            if key in excluded or not row['enabled'] or row['status'] != 'healthy':
                continue
            if not set(categories) <= set(row['allowed_categories']):
                continue
            if not set(capabilities) <= set(row['capabilities']):
                continue
            if not self._resources_admissible(row):
                continue
            if not self._context_admissible(row, context_tokens):
                continue
            capacity = row['concurrency'] - (0 if interactive else row['interactive_reserve'])
            if row['current_jobs'] >= capacity:
                continue
            # Measured latency and load, never parameter count or invented speed.
            latency = row['latency_ms'] if row['latency_ms'] is not None else row['health_latency_ms'] if row['health_latency_ms'] is not None else 10000
            score = row['current_jobs'] * 10000 + latency
            candidates.append((score, key, row))
        return sorted(candidates, key=lambda value: (value[0], value[1]))

    @staticmethod
    def _context_admissible(row, required):
        verified = row.get('max_context_verified')
        return (type(verified) is int and verified >= required
                and all(type(row.get(field)) is not int or row[field] >= required
                        for field in ('context_configured', 'context_reported')))

    def _resources_admissible(self, row):
        """Unknown remote capacity is not a reserve; CPU workers need no GPU."""
        remote = row['node_id'] != 'local'
        if remote:
            sampled = row.get('resource_sampled_at')
            if (type(sampled) not in (int, float) or not math.isfinite(sampled)
                    or not 0 <= self.registry.clock() - sampled <= 30):
                return False
        worker = self.registry.worker(row['worker_id'])
        needs_gpu = bool(row.get('gpu') or row.get('gpu_measurement')
                         or (worker.get('startup') or {}).get('gpu_device') is not None)
        for field, reserve, required in (
                ('ram_available_bytes', 2 * 1024 ** 3, remote),
                ('vram_free_bytes', 256 * 1024 ** 2, remote and needs_gpu)):
            value = row.get(field)
            if value is None:
                if required:
                    return False
            elif type(value) not in (int, float) or not math.isfinite(value) or value < reserve:
                return False
        return True

    def _update(self, job, state, **fields):
        job.update(state=state, updated_at=self.registry.clock(), **fields)
        self.registry.receipt(job)

    def _unblocked_choices(self, ticket, choices):
        """FIFO per compatible worker, preserving interactive class priority.

        A request pinned to a busy worker must not reserve unrelated idle
        workers. Earlier requests keep every slot they could actually use.
        """
        earlier = self.waiting[:self.waiting.index(ticket)]
        result = []
        for choice in choices:
            _, key, row = choice
            blocked = False
            for pending in earlier:
                requirement = self.queued[pending[2]]
                if requirement['cancellation'].is_set() or key in requirement['excluded']:
                    continue
                allowed = requirement['allowed']
                if allowed is not None and key not in allowed:
                    continue
                capacity = row['concurrency'] - (0 if requirement['interactive'] else row['interactive_reserve'])
                if (set(requirement['categories']) <= set(row['allowed_categories'])
                        and set(requirement['capabilities']) <= set(row['capabilities'])
                        and self._context_admissible(row, requirement['context'])
                        and row['current_jobs'] < capacity):
                    blocked = True
                    break
            if not blocked:
                result.append(choice)
        return result

    def chat(self, messages, *, workflow_id, step_id, invocation_id, categories,
             cancellation=None, admission=None, interactive=False, allowed_worker_ids=None,
             max_retries_override=None, max_queue_seconds=None, selection_reason=None, **kwargs):
        if self.closed or not self.registry.enabled:
            raise ComputeError('Distributed inference is disabled.')
        if type(interactive) is not bool:
            raise ComputeError('Inference priority requires a trusted boolean.')
        if not set(categories) or not set(categories) <= {'synthetic', 'project', 'conversation', 'memory', 'screen', 'sensitive'}:
            raise ComputeError('Controller context categories are required.')
        # Credentials may not cross this transport even for a trusted worker.
        from hanni.workflows.types import canonical_json, WorkflowError
        encoded = canonical_json(messages, maximum=262144)
        response_format = kwargs.get('response_format')
        schema_bytes = 0
        if response_format is not None:
            if not isinstance(response_format, dict) or response_format.get('type') not in {'json_object', 'json_schema'}:
                raise ComputeError('Inference requires a supported bounded response format.')
            try:
                schema_bytes = len(canonical_json(response_format, maximum=262144).encode())
            except WorkflowError:
                raise ComputeError('Inference response schema exceeds its bounded safe payload.') from None
        max_tokens = kwargs.get('max_tokens', 2048)
        if type(max_tokens) is not int or not 1 <= max_tokens <= 8192:
            raise ComputeError('Invalid inference output budget.')
        # One UTF-8 byte per token is a conservative upper bound for routing;
        # actual usage remains separately observed. It never advertises capacity.
        required = len(encoded.encode()) + schema_bytes + max_tokens
        policy = self.registry.deployment.get('policy', {})
        timeout = policy.get('timeout_seconds', 30)
        if allowed_worker_ids is not None:
            allowed_worker_ids = frozenset(allowed_worker_ids)
            if not allowed_worker_ids or not allowed_worker_ids <= {row['worker_id'] for row in self.registry.workers()}:
                raise ComputeError('Adaptive placement must reference registered workers.')
        retries = policy.get('max_retries', 1)
        if max_retries_override is not None:
            if type(max_retries_override) is not int or not 0 <= max_retries_override <= retries:
                raise ComputeError('Adaptive retries cannot increase the existing retry policy.')
            retries = max_retries_override
        queue_timeout = timeout
        if max_queue_seconds is not None:
            if type(max_queue_seconds) not in (int, float) or not 0 < max_queue_seconds <= timeout:
                raise ComputeError('Adaptive queue budget cannot exceed the existing timeout policy.')
            queue_timeout = max_queue_seconds
        cancellation = cancellation or threading.Event()
        started = self.clock()
        excluded = set()
        job = {'job_id': 'job_' + uuid4().hex, 'workflow_id': workflow_id, 'step_id': step_id,
            'invocation_id': invocation_id, 'worker_id': None, 'model_id': None,
            'state': 'QUEUED', 'created_at': self.registry.clock(), 'updated_at': self.registry.clock(),
            'timeout_seconds': timeout, 'attempt': 0, 'input_sha256': hashlib.sha256(encoded.encode()).hexdigest(),
            'verification_status': 'PENDING', 'retry_safe': True}
        with self.condition:
            if len(self.waiting) >= policy.get('max_queue', 16):
                raise ComputeError('Compute queue is full; background admission is paused.')
            # FIFO within each class; interactive work has a separately reserved capacity.
            # Windows clocks can return identical timestamps for successive
            # admissions. A monotonic admission sequence preserves true FIFO.
            self._queue_sequence += 1
            ticket = (not interactive, self._queue_sequence, job['job_id'])
            self.waiting.append(ticket)
            self.waiting.sort()
            self.queued[job['job_id']] = {'categories': frozenset(categories), 'context': required,
                'capabilities': ('analysis', 'structured_json') if kwargs.get('response_format') else ('analysis',),
                'interactive': interactive, 'allowed': allowed_worker_ids, 'excluded': excluded,
                'cancellation': cancellation}
            self.registry.receipt(job)
            self.inflight[job['job_id']] = (workflow_id, cancellation)
        try:
            for attempt in range(retries + 1):
                worker = None
                with self.condition:
                    while worker is None:
                        if not self.registry.enabled:
                            self._update(job, 'BLOCKED', error='Protected compute authorization was withdrawn.')
                            raise ComputeError('Distributed inference authorization was withdrawn.')
                        if cancellation.is_set() or self.closed:
                            self._update(job, 'CANCELLED', error='Inference cancellation requested.')
                            raise ComputeError('Distributed inference was cancelled.')
                        if self.clock() - started >= queue_timeout:
                            self._update(job, 'BLOCKED', error='No eligible worker became available within the queue budget.')
                            raise ComputeError('No healthy trusted worker has verified capacity for this inference.')
                        choices = self._choices(categories, required, interactive=interactive, excluded=excluded,
                            capabilities=('analysis', 'structured_json') if kwargs.get('response_format') else ('analysis',))
                        if allowed_worker_ids is not None:
                            choices = [candidate for candidate in choices if candidate[1] in allowed_worker_ids]
                        choices = self._unblocked_choices(ticket, choices)
                        if choices:
                            _, key, row = choices[0]
                            worker = self.registry.worker(key)
                            self.registry.active[key] = self.registry.active.get(key, 0) + 1
                            self.waiting.remove(ticket)
                            self._update(job, 'ASSIGNED', worker_id=key, model_id=row['model_id'], attempt=attempt + 1,
                                queue_ms=(self.clock() - started) * 1000,
                                selection_reason=selection_reason or f'Healthy, trusted for {", ".join(sorted(categories))}; verified context {row["max_context_verified"]} >= conservative requirement {required}; measured load/latency rank.')
                        else:
                            self.condition.wait(.05)
                key = worker['worker_id']
                call_started = self.clock()
                try:
                    if admission:
                        admission()  # Original lease, reviewed scope, stop and budget gates.
                    if cancellation.is_set() or self.closed:
                        raise ComputeError('Distributed inference was cancelled before dispatch.')
                    # Reload protected authorization before fetching a worker;
                    # an older copy must not survive an admission-time revoke.
                    current = next((candidate for candidate in self.registry.workers()
                                    if candidate['worker_id'] == key), None) if self.registry.enabled else None
                    if (current is None or not current.get('enabled', False)
                            or not set(categories) <= set(current.get('allowed_categories', []))
                            or current.get('model_id') != job['model_id']
                            or self.registry._worker_identity(current) != self.registry._worker_identity(worker)
                            or not set(self.queued[job['job_id']]['capabilities']) <= set(current.get('capabilities', ['analysis']))):
                        raise RuntimeError('Protected compute authorization changed before dispatch.')
                    admitted = next((candidate for candidate in self.registry.snapshot()['workers']
                                     if candidate['worker_id'] == key), None)
                    if (admitted is None or admitted['status'] != 'healthy'
                            or admitted['model_id'] != job['model_id']
                            or not self._context_admissible(admitted, required)
                            or not self._resources_admissible(admitted)):
                        raise RuntimeError('Verified worker capacity changed before inference dispatch.')
                    self._update(job, 'RUNNING', started_at=self.registry.clock())
                    payload = {'model': job['model_id'], 'messages': messages, 'stream': False,
                               'temperature': kwargs.get('temperature', 0), 'max_tokens': max_tokens,
                               'chat_template_kwargs': {'enable_thinking': False}}
                    if kwargs.get('response_format') is not None:
                        payload['response_format'] = kwargs['response_format']
                    result = self.transport.request(worker, 'POST', '/v1/chat/completions', payload=payload,
                        timeout=max(.1, timeout - (self.clock() - started)), cancel=cancellation)
                    # A transport may return just as cancellation or a lease
                    # withdrawal occurs. Completion does not restore authority.
                    if cancellation.is_set() or self.closed:
                        raise ComputeError('Distributed inference was cancelled before result admission.')
                    if admission:
                        admission()
                    if cancellation.is_set() or self.closed:
                        raise ComputeError('Distributed inference was cancelled before result admission.')
                    current = next((candidate for candidate in self.registry.workers()
                                    if candidate['worker_id'] == key), None) if self.registry.enabled else None
                    observed = self.registry.observations.get(key, {})
                    if (current is None or not current.get('enabled', False)
                            or not set(categories) <= set(current.get('allowed_categories', []))
                            or self.registry._worker_identity(current) != self.registry._worker_identity(worker)
                            or not set(self.queued[job['job_id']]['capabilities']) <= set(current.get('capabilities', ['analysis']))
                            or observed.get('model_id') != job['model_id']
                            or not self._context_admissible(
                                dict(observed, context_configured=current.get('context_configured')), required)):
                        raise _ComputeAdmissionWithdrawn('Protected inference authorization changed before result admission.')
                    if result.get('model') is not None and result['model'] != job['model_id']:
                        raise ComputeError('Inference response model differs from the admitted registered model.')
                    try:
                        choice = result['choices'][0]
                        content = choice['message']['content']
                        if (not isinstance(content, str) or not content.strip() or len(content.encode()) > 262144
                                or choice.get('finish_reason') not in {'stop', 'eos'}):
                            raise ComputeError('Inference is empty, truncated, or exceeds its result budget.')
                    except (KeyError, IndexError, TypeError):
                        raise ComputeError('Inference endpoint did not return a complete model response.') from None
                    elapsed = (self.clock() - call_started) * 1000
                    usage = result.get('usage') or {}
                    from hanni.models.performance import server_rates
                    performance = server_rates(result)
                    tokens = usage.get('completion_tokens')
                    self.registry.observe(key, latency_ms=elapsed,
                        throughput_tps=tokens / (elapsed / 1000) if type(tokens) is int and elapsed > 0 else None)
                    self._update(job, 'COMPLETED', finished_at=self.registry.clock(), latency_ms=elapsed,
                        output_sha256=hashlib.sha256(content.encode()).hexdigest(),
                        output_ref=f'workflow:{workflow_id}/invocation:{invocation_id}',
                        tokens=usage if isinstance(usage, dict) else None, performance=performance)
                    return content, deepcopy(job)
                except _ComputeAdmissionWithdrawn as exc:
                    self._update(job, 'BLOCKED', error=str(exc))
                    raise
                except ComputeError as exc:
                    excluded.add(key)
                    cancelled = cancellation.is_set() or self.closed
                    if not cancelled:
                        self.registry.observe(key, status='unhealthy', error=str(exc), last_heartbeat=self.registry.clock())
                    self._update(job, 'CANCELLED' if cancelled else 'LOST_CONNECTION', error=str(exc))
                    if cancelled or attempt >= retries:
                        raise
                    with self.condition:
                        self.waiting.append(ticket)
                        self.waiting.sort()
                except Exception:
                    self._update(job, 'BLOCKED', error='Original controller admission was withdrawn before inference dispatch.')
                    raise
                finally:
                    with self.condition:
                        self.registry.active[key] = max(0, self.registry.active.get(key, 0) - 1)
                        self.condition.notify_all()
        finally:
            with self.condition:
                if ticket in self.waiting:
                    self.waiting.remove(ticket)
                self.inflight.pop(job['job_id'], None)
                self.queued.pop(job['job_id'], None)
                self.condition.notify_all()

    def finish(self, job, evidence):
        self._update(job, 'VERIFYING')
        verified = evidence.get('status') == 'VERIFIED'
        self._update(job, 'VERIFIED' if verified else 'FAILED',
            verification_status=evidence.get('status', 'UNVERIFIED'),
            **({'error': 'Original workflow evidence verification rejected the model output.'} if not verified else {}))

    def cancel_workflow(self, workflow_id):
        with self.condition:
            for current, event in self.inflight.values():
                if current == workflow_id:
                    event.set()
                    self.transport.cancel(event=event)
            self.condition.notify_all()

    def verify_context(self, worker_id, messages, *, target_tokens, expected, anthropic=False,
                       max_output_tokens=256, admission=None, cancellation=None):
        """Controlled engineering probe: actual near-limit inference plus retrieval.

        No UI or model can set this measurement. Counted response usage must
        demonstrate >=90% of the target, and exact synthetic retrieval must pass.
        """
        from hanni.workflows.types import canonical_json, WorkflowError
        if type(target_tokens) is not int or not 1 <= target_tokens <= 131072 or type(anthropic) is not bool:
            raise ComputeError('Invalid bounded context-probe target or protocol.')
        if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 512:
            raise ComputeError('Invalid context-probe output budget.')
        try:
            canonical_json(messages, maximum=262144)
            canonical_json(expected, maximum=8192)
        except WorkflowError:
            raise ComputeError('Context probing requires bounded credential-free synthetic data.') from None
        if (not isinstance(messages, (list, tuple)) or not messages or len(messages) > 256
                or any(not isinstance(message, dict) or message.get('role') not in {'system', 'user', 'assistant'}
                       or not isinstance(message.get('content'), str) for message in messages)):
            raise ComputeError('Context probing requires bounded ordinary text messages.')
        cancellation = cancellation or threading.Event()

        def check_admission():
            if self.closed or cancellation.is_set():
                raise _ComputeAdmissionWithdrawn('Context-probe admission was cancelled or closed.')
            if admission:
                admission()
            if self.closed or cancellation.is_set():
                raise _ComputeAdmissionWithdrawn('Context-probe admission was cancelled or closed.')
            if not self.registry.enabled:
                raise _ComputeAdmissionWithdrawn('Distributed context probing is disabled.')
            current = self.registry.worker(worker_id)
            if not current.get('enabled') or 'synthetic' not in current.get('allowed_categories', []):
                raise _ComputeAdmissionWithdrawn('The protected worker does not authorize synthetic context probing.')
            return current

        worker = check_admission()
        binding = self.registry._worker_identity(worker)
        health = self.transport.health(worker)
        self.registry.observe(worker_id, **health)
        self._observe_resources(worker)
        observed = self.registry.observations.get(worker_id, {})
        runtime_binding = {field: observed.get(field) for field in ('runtime_identity', 'runtime_files_identity')}

        def current_row():
            current = check_admission()
            if self.registry._worker_identity(current) != binding:
                raise _ComputeAdmissionWithdrawn('The protected worker identity changed during context probing.')
            observed = self.registry.observations.get(worker_id, {})
            if any(observed.get(field) != value for field, value in runtime_binding.items()):
                raise _ComputeAdmissionWithdrawn('The observed runtime identity changed during context probing.')
            row = next(row for row in self.registry.snapshot()['workers'] if row['worker_id'] == worker_id)
            if (row['status'] != 'healthy' or row['model_id'] != worker.get('model_id')
                    or not self._resources_admissible(row)):
                raise _ComputeAdmissionWithdrawn('Context probing requires fresh exact model health and measured resource reserves.')
            bounds = (row['context_configured'], row['context_reported'])
            if any(type(value) is not int or value < target_tokens + max_output_tokens for value in bounds):
                raise _ComputeAdmissionWithdrawn('Context-probe target exceeds configured or reported allocation.')
            return row

        probe_id = 'context_probe_' + uuid4().hex
        with self.condition:
            row = current_row()
            # Engineering probes fail fast instead of bypassing queued owner
            # work or borrowing the capacity reserved for interactive requests.
            queued_conflict = any(worker_id not in item['excluded'] and not item['cancellation'].is_set()
                and (item['allowed'] is None or worker_id in item['allowed']) for item in self.queued.values())
            if queued_conflict or row['current_jobs'] >= row['concurrency'] - row['interactive_reserve']:
                raise ComputeError('Context probing cannot bypass a busy or queued inference reservation.')
            self.registry.active[worker_id] = self.registry.active.get(worker_id, 0) + 1
            self.inflight[probe_id] = (probe_id, cancellation)
        try:
            current_row()
            result = self.transport.request(worker, 'POST', '/v1/messages' if anthropic else '/v1/chat/completions',
                payload={'model': worker.get('model_id'), 'messages': messages, 'max_tokens': max_output_tokens, 'temperature': 0, 'stream': False,
                         **({'thinking': {'type': 'disabled'}} if anthropic else {'chat_template_kwargs': {'enable_thinking': False}})},
                timeout=600 if anthropic else 300, cancel=cancellation)
            stamp = self.registry.observations.get(worker_id, {}).get('last_heartbeat')
            if type(stamp) not in (int, float) or not math.isfinite(stamp) or not 0 <= self.registry.clock() - stamp <= 30:
                check_admission()
                self.registry.observe(worker_id, **self.transport.health(worker))
                self._observe_resources(worker)
            row = current_row()
            if result.get('model') is not None and result.get('model') != worker.get('model_id'):
                raise ComputeError('Context-probe response names a different registered model.')
            try:
                if anthropic:
                    usage = result['usage']
                    parts = [usage['input_tokens'], usage.get('cache_read_input_tokens', 0), usage.get('cache_creation_input_tokens', 0)]
                    if any(type(value) is not int or value < 0 for value in parts):
                        raise ValueError('Invalid Anthropic token accounting.')
                    count = sum(parts)
                    content = ''.join(part['text'] for part in result['content'] if part.get('type') == 'text')
                    complete = result['stop_reason'] == 'end_turn'
                else:
                    count = result['usage']['prompt_tokens']
                    content = result['choices'][0]['message']['content']
                    complete = result['choices'][0]['finish_reason'] == 'stop'
                retrieved = json.loads(content) == expected if isinstance(expected, (dict, list)) else content.strip() == expected
                passed = (type(count) is int and target_tokens * .9 <= count <= target_tokens and complete and retrieved
                          and count + max_output_tokens <= min(row['context_configured'], row['context_reported']))
            except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                passed, count = False, None
            if passed:
                current_row()
                self.registry.record_context_verified(worker_id, target_tokens=target_tokens, prompt_tokens=count,
                    model_id=health['model_id'], prompt_sha256=hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest(),
                    response_sha256=hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest())
            return {'passed': passed, 'target_tokens': target_tokens, 'observed_prompt_tokens': count,
                    'max_context_verified': self.registry.observations.get(worker_id, {}).get('max_context_verified')}
        finally:
            with self.condition:
                self.registry.active[worker_id] = max(0, self.registry.active.get(worker_id, 0) - 1)
                self.inflight.pop(probe_id, None)
                self.condition.notify_all()

    def close(self):
        with self.condition:
            self.closed = True
            self.halt.set()
            self.health_wake.set()
            for _, event in self.inflight.values():
                event.set()
            self.condition.notify_all()
        self.transport.close()
        if self.monitor is not None:
            self.monitor.join(2)
        deadline = time.monotonic()+2
        for worker in list(self.health_workers.values()):
            worker.join(max(0, deadline-time.monotonic()))
        self.registry.close()
