"""Real original-engine inference with bounded synthetic-only wire evidence.

This is ModelLab-adjacent, not the desktop's fixed-suite API. Caller owns original
engine/config/guard setup. It must not forge capability/context/resource proofs.
No runtimes, monitors, authentication or owner state are started or changed here.
"""
from __future__ import annotations
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from hanni.models.adaptive import ModelRequest, ModelSelectionError
from hanni.models.client import ModelTurn
from scripts.campaign5_benchmark.checkers import grade
RAW_LIMIT = 2 * 1024 * 1024

def request_limits(case):
    """Separate native control bounds from actual generation kwargs."""
    output = case['request'].get('output_tokens', 256)
    limits = dict(case.get('limits', {'max_tokens': output, 'temperature': 0, 'top_p': 1}))
    if set(limits) - {'max_tokens', 'temperature', 'top_p', 'max_fallbacks', 'timeout_seconds'}:
        raise ValueError('Unsupported prospective request limit.')
    fallback = limits.pop('max_fallbacks', None)
    timeout = limits.pop('timeout_seconds', None)
    if fallback is not None and (type(fallback) is not int or fallback < 0):
        raise ValueError('Fallback limit must be a nonnegative integer.')
    if timeout is not None and (type(timeout) not in (int, float) or not math.isfinite(timeout) or (not 0 < timeout <= 600)):
        raise ValueError('Timeout must be a finite positive bounded duration.')
    if type(limits.get('max_tokens')) is not int or limits['max_tokens'] != output or (not 1 <= output <= 512) or (type(limits.get('temperature')) not in (int, float)) or (limits['temperature'] != 0) or (type(limits.get('top_p')) not in (int, float)) or (limits['top_p'] != 1):
        raise ValueError('Prospective bounded settings mismatch.')
    return (limits, fallback, timeout)

class RequestCancellation(threading.Event):
    """Owned deadline cancellation also observes, never sets, caller cancellation."""

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent

    def is_set(self):
        return super().is_set() or bool(self.parent is not None and self.parent.is_set())

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, default=str).encode()).hexdigest()

def reported_metadata(raw):
    """Read reported aliases and finish flags; an alias never proves weights."""
    objects = []
    try:
        objects = [json.loads(raw)]
    except (ValueError, TypeError):
        for line in raw.splitlines():
            if not line.startswith('data:'):
                continue
            try:
                objects.append(json.loads(line[5:].strip()))
            except ValueError:
                pass
    return {'reported_model_aliases': sorted({p['model'] for p in objects if isinstance(p, dict) and isinstance(p.get('model'), str)}), 'finish_reasons': [c['finish_reason'] for p in objects if isinstance(p, dict) for c in p.get('choices', []) if isinstance(c, dict) and c.get('finish_reason') is not None], 'identity_scope': 'Reported response aliases only; runtime/weights proof remains separate original endpoint evidence.'}

class ObservedResponse:

    def __init__(self, response, record):
        self.response, self.record = (response, record)

    def __getattr__(self, name):
        return getattr(self.response, name)

    def __enter__(self):
        self.response.__enter__()
        return self

    def __exit__(self, *args):
        try:
            return self.response.__exit__(*args)
        finally:
            self.record['finished_at'] = time.perf_counter()

    def retain(self, value):
        if not value:
            return value
        if self.record.get('first_response_byte_at') is None:
            self.record['first_response_byte_at'] = time.perf_counter()
        data = value.encode() if isinstance(value, str) else value
        self.record['response_byte_count'] += len(data)
        remaining = RAW_LIMIT - len(self.record['_raw'])
        self.record['_raw'].extend(data[:max(0, remaining)])
        self.record['raw_truncated'] = self.record['response_byte_count'] > RAW_LIMIT
        return value

    def read(self, *args, **kwargs):
        return self.retain(self.response.read(*args, **kwargs))

    def readline(self, *args, **kwargs):
        return self.retain(self.response.readline(*args, **kwargs))

    def __iter__(self):
        for chunk in self.response:
            yield self.retain(chunk)

@contextmanager
def capture_http(allowed_origins):
    """Observe original stdlib transport; do not alter requests or response values.

    Run in an isolated benchmark process. Only configured origins and POST bodies
    are captured. Request/response headers, authentication and environment omitted.
    """
    import httpx
    original = urllib.request.urlopen
    original_send = httpx.Client.send
    records = []
    lock = threading.Lock()

    def allowed():
        return set(allowed_origins() if callable(allowed_origins) else allowed_origins)

    def observed(request, *args, **kwargs):
        url = getattr(request, 'full_url', str(request))
        parts = urllib.parse.urlsplit(url)
        origin = (parts.scheme, parts.hostname, parts.port)
        if origin not in allowed() or getattr(request, 'method', None) != 'POST' or getattr(request, 'data', None) is None:
            return original(request, *args, **kwargs)
        body = request.data
        if len(body) > 262144:
            raise ValueError('Synthetic inference request body exceeds capture bound.')
        record = {'origin': list(origin), 'path': parts.path, 'method': 'POST', 'request_body': body.decode('utf8', errors='replace'), 'request_sha256': hashlib.sha256(body).hexdigest(), 'started_at': time.perf_counter(), 'finished_at': None, 'first_response_byte_at': None, 'response_byte_count': 0, '_raw': bytearray(), 'raw_truncated': False, 'status': None}
        timeout = kwargs.get('timeout', args[0] if args else None)
        record['original_transport_timeout_seconds'] = timeout if type(timeout) in (int, float) else None
        with lock:
            records.append(record)
        try:
            response = original(request, *args, **kwargs)
            record['status'] = getattr(response, 'status', None)
            return ObservedResponse(response, record)
        except urllib.error.HTTPError as exc:
            record['status'] = exc.code
            read = exc.read

            def traced_read(*a, **k):
                value = read(*a, **k)
                ObservedResponse(exc, record).retain(value)
                record['finished_at'] = time.perf_counter()
                return value
            exc.read = traced_read
            record['error_class'] = type(exc).__name__
            raise
        except Exception as exc:
            record['error_class'] = type(exc).__name__
            record['finished_at'] = time.perf_counter()
            raise

    def observed_send(client, request, *args, **kwargs):
        parts = urllib.parse.urlsplit(str(request.url))
        origin = (parts.scheme, parts.hostname, parts.port)
        if origin not in allowed() or request.method != 'POST':
            return original_send(client, request, *args, **kwargs)
        body = request.content
        if len(body) > 262144:
            raise ValueError('Synthetic inference request body exceeds capture bound.')
        record = {'origin': list(origin), 'path': parts.path, 'method': 'POST', 'request_body': body.decode('utf8', errors='replace'), 'request_sha256': hashlib.sha256(body).hexdigest(), 'started_at': time.perf_counter(), 'finished_at': None, 'first_response_byte_at': None, 'response_byte_count': 0, '_raw': bytearray(), 'raw_truncated': False, 'status': None, 'transport': 'original_compute_httpx'}
        record['original_transport_timeout_seconds'] = {name: value for name, value in request.extensions.get('timeout', {}).items() if type(value) in (int, float)}
        with lock:
            records.append(record)
        try:
            response = original_send(client, request, *args, **kwargs)
            record['status'] = response.status_code
            data = response.content
            ObservedResponse(response, record).retain(data)
            record['finished_at'] = time.perf_counter()
            return response
        except Exception as exc:
            record['error_class'] = type(exc).__name__
            record['finished_at'] = time.perf_counter()
            raise
    urllib.request.urlopen = observed
    httpx.Client.send = observed_send
    try:
        yield records
    finally:
        urllib.request.urlopen = original
        httpx.Client.send = original_send
        for record in records:
            blob = bytes(record.pop('_raw'))
            record['raw_response'] = blob.decode('utf8', errors='replace')
            record['reported_metadata'] = reported_metadata(record['raw_response'])
            record['response_sha256'] = hashlib.sha256(blob).hexdigest()
            record['latency_ms'] = None if record['finished_at'] is None else 1000 * (record['finished_at'] - record['started_at'])
            record['first_response_byte_ms'] = None if record['first_response_byte_at'] is None else 1000 * (record['first_response_byte_at'] - record['started_at'])

def original_origins(engine):
    origins = []
    for row in engine._inventory():
        if 'spec' in row:
            p = urllib.parse.urlsplit(row['spec'].endpoint)
            origins.append((p.scheme, p.hostname, p.port))
        else:
            worker = row['worker']
            if worker.get('local_port'):
                origins.append(('http', '127.0.0.1', worker['local_port']))
            if worker.get('local_url'):
                p = urllib.parse.urlsplit(worker['local_url'])
                origins.append((p.scheme, p.hostname, p.port))
    if engine.compute is not None:
        for entry in getattr(engine.compute.transport, 'tunnels', {}).values():
            p = urllib.parse.urlsplit(entry['url'])
            origins.append((p.scheme, p.hostname, p.port))
    return origins

def actual_answer(value):
    if value is None:
        return None
    if isinstance(value, ModelTurn):
        return {'text': value.content, 'tool_calls': [asdict(c) for c in value.tool_calls], 'usage': dict(value.usage)}
    return {'text': value if isinstance(value, str) else None, 'unexpected_return_type': None if isinstance(value, str) else type(value).__name__}

def run_case(case, engine, *, mode='pinned', endpoint_id=None, endpoint_ids=None, admission=None, cancellation=None, collaboration_verifier=None):
    """Execute ONLY input fields. Oracles are supplied solely to separate graders.

    Modes: pinned individual; native adaptive; explicit development parallel;
    native selective auto. Auto uses only caller's frozen development profiles.
    """
    if mode not in {'pinned', 'adaptive', 'parallel_development', 'selective'}:
        raise ValueError('Unknown benchmark mode.')
    if mode == 'pinned' and (not endpoint_id):
        raise ValueError('Pinned arm requires its original endpoint identifier.')
    if collaboration_verifier is not None and mode != 'parallel_development':
        raise ValueError('Reference-backed selection is restricted to explicitly labeled development comparisons.')
    if 'expected' in case or 'checker_inputs' in case or 'oracle' in case:
        raise ValueError('Oracle data is forbidden in execution inputs.')
    if set(case['request'].get('privacy_categories', ())) != {'synthetic'}:
        raise ValueError('Only synthetic benchmark context is allowed.')
    request_options = dict(case['request'])
    request_options['capabilities'] = frozenset(request_options.get('capabilities', ['text']))
    request_options['privacy_categories'] = frozenset({'synthetic'})
    request = ModelRequest(**request_options)
    options, fallback_limit, timeout = request_limits(case)
    if mode in {'selective', 'parallel_development'} and fallback_limit not in (None, 0):
        raise ValueError('Original collaboration participants are pinned with zero fallbacks.')
    if 'response_format' in case:
        options['response_format'] = case['response_format']
    tools = case.get('tools')
    local_operation = None
    if tools is not None:
        from dataclasses import replace
        request = replace(request, capabilities=frozenset(set(request.capabilities) | {'tool_calling'}), tool_calling_format='openai_function', schema_tokens=max(request.schema_tokens, len(json.dumps(tools).encode())))
        local_operation = lambda client: client.complete_with_tools(case['messages'], tools=tools, **options)
    telemetry = {}
    result = None
    error = None
    began = time.perf_counter()
    previous_decisions = {d['decision_id'] for d in engine.snapshot().get('decisions', [])}
    timer = None
    if timeout is not None:
        cancellation = RequestCancellation(cancellation)
        timer = threading.Timer(timeout, cancellation.set)
        timer.daemon = True
        timer.start()
    with capture_http(lambda: original_origins(engine)) as wire:
        try:
            if mode in {'pinned', 'adaptive'}:
                result = engine.execute(case['messages'], request=request, endpoint_id=endpoint_id if mode == 'pinned' else None, max_fallbacks=0 if mode == 'pinned' else fallback_limit, telemetry=telemetry, admission=admission, cancellation=cancellation, local_operation=local_operation, **options)
            else:
                result = engine.collaboration.run(case['messages'], request=request, preference='parallel' if mode == 'parallel_development' else 'auto', endpoint_ids=endpoint_ids, verify=collaboration_verifier, admission=admission, cancellation=cancellation, local_operation=local_operation, **options)
        except Exception as exc:
            error = {'class': type(exc).__name__, 'message': str(exc)[:2000]}
        finally:
            if timer is not None:
                timer.cancel()
    elapsed = 1000 * (time.perf_counter() - began)
    collaboration = result if mode in {'parallel_development', 'selective'} and isinstance(result, dict) else None
    answer = actual_answer(collaboration.get('selected_output') if collaboration else result)
    dispatches = [r for r in wire if r['method'] == 'POST' and r['path'] in {'/v1/chat/completions', '/chat/completions', '/v1/messages'}]
    wire_span = 1000 * (max((r['finished_at'] or r['started_at'] for r in dispatches)) - min((r['started_at'] for r in dispatches))) if dispatches else None
    decision_snapshot = engine.snapshot()
    if cancellation is not None and cancellation.is_set() or (collaboration and collaboration.get('state') == 'cancelled'):
        classification = 'CANCELLED_AFTER_DISPATCH' if dispatches else 'CANCELLED_NO_INFERENCE'
    elif collaboration and collaboration.get('selected_output') is None:
        classification = 'INFERENCE_ERROR' if dispatches else 'COLLABORATION_DECLINED_NO_INFERENCE'
    elif error is None and answer is not None:
        classification = 'RETURNED' if dispatches else 'UNOBSERVED_INFERENCE'
    elif not dispatches:
        classification = 'BLOCKED_NO_INFERENCE' if error and error['class'] in {'ModelSelectionError', 'ModelUnavailableError', '_ModelAdmissionWithdrawn'} else 'HARNESS_OR_ADMISSION_ERROR_NO_INFERENCE'
    else:
        classification = 'INFERENCE_ERROR'
    return {'id': case['id'], 'category': case['category'], 'difficulty': case.get('difficulty'), 'mode': mode, 'requested_endpoint_id': endpoint_id, 'request': case['request'], 'input_sha256': digest(case), 'generation_settings': options, 'classification': classification, 'requested_limits': case.get('limits'), 'effective_fallback_limit': 0 if mode == 'pinned' else fallback_limit, 'requested_deadline_seconds': timeout, 'deadline_scope': 'Original cancellation checks; an in-progress local blocking read remains bounded by its original transport timeout.', 'requested_response_format': case.get('response_format'), 'original_function_definitions': tools, 'real_generation_dispatches': len(dispatches), 'raw_http': wire, 'actual_response': answer, 'error': error, 'telemetry': telemetry, 'collaboration': collaboration, 'endpoint_inventory': decision_snapshot.get('endpoints'), 'native_decisions': [d for d in decision_snapshot.get('decisions', []) if d['decision_id'] not in previous_decisions], 'total_request_ms': elapsed, 'http_critical_span_ms': wire_span, 'orchestration_outside_wire_span_ms': None if wire_span is None else max(0, elapsed - wire_span), 'overhead_scope': 'wall request minus actual first-to-last HTTP envelope; includes scoring only if supplied as original collaboration verifier', 'semantic_pass': None, 'tool_execution': False, 'workflow_execution': False, 'reference_backed_collaboration': collaboration_verifier is not None, 'memory_scope': 'supplied synthetic evidence; production retrieval not measured'}

def score_receipt(receipt, oracle):
    if receipt['id'] != oracle['id']:
        raise ValueError('Case/oracle identity mismatch.')
    if receipt['classification'] != 'RETURNED' or receipt['actual_response'] is None:
        return {'semantic_pass': None, 'classification': receipt['classification'], 'reason': 'No successfully returned actual model answer.'}
    answer = receipt['actual_response']['text']
    if answer is None:
        return {'semantic_pass': False, 'classification': 'UNSUPPORTED_NATIVE_RESPONSE'}
    verdict = grade(answer, oracle)
    return {'semantic_pass': verdict['passed'], 'classification': 'SCORED_ACTUAL_RESPONSE', 'task_proof': verdict}

def summary(receipts):
    rows = list(receipts)
    inferred = [r for r in rows if r.get('semantic_pass') is not None]
    latencies = sorted((r['total_request_ms'] for r in rows if r['real_generation_dispatches']))
    percentile = lambda q: latencies[min(len(latencies) - 1, math.ceil(q * len(latencies)) - 1)] if latencies else None
    measurements = []
    for row in rows:
        if not row['real_generation_dispatches']:
            continue
        if row.get('collaboration'):
            measurements.extend((p for p in row['collaboration']['participants'] if p.get('state') in {'completed', 'failed'}))
        elif row.get('telemetry'):
            measurements.append(row['telemetry'])

    def sample(values):
        values = [v for v in values if type(v) in (int, float) and math.isfinite(v)]
        return {'sample_count': len(values), 'mean': sum(values) / len(values) if values else None, 'min': min(values) if values else None, 'max': max(values) if values else None}
    token_metrics = {}
    for field in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
        values = [m.get('tokens', {}).get(field) if isinstance(m.get('tokens'), dict) else None for m in measurements]
        known = [v for v in values if type(v) is int and v >= 0]
        token_metrics[field] = {'participant_count': len(values), 'reported_count': len(known), 'total_reported': sum(known) if known else None, 'complete_reporting': bool(values) and len(known) == len(values)}
    resources = {field: sample([(m.get('resource_observations') or {}).get(field) for m in measurements]) for field in ('ram_available_bytes', 'vram_free_bytes', 'current_requests', 'queue_depth')}
    return {'tasks': len(rows), 'semantic_measured': len(inferred), 'semantic_passed': sum((r['semantic_pass'] is True for r in inferred)), 'blocked_or_unmeasured': len(rows) - len(inferred), 'classification_counts': dict(Counter((r['classification'] for r in rows))), 'actual_http_generation_requests': sum((r['real_generation_dispatches'] for r in rows)), 'latency_ms': {'n': len(latencies), 'p50': percentile(0.5), 'p95': percentile(0.95)}, 'reported_tokens': token_metrics, 'resource_observations': resources, 'resource_scope': 'Original admission-time samples, not measured peak memory consumption or incremental resource cost.', 'orchestration_outside_wire_span_ms': sample([r.get('orchestration_outside_wire_span_ms') for r in rows]), 'by_category': {category: {'tasks': sum((r['category'] == category for r in rows)), 'semantic_measured': sum((r['category'] == category and r.get('semantic_pass') is not None for r in rows)), 'semantic_passed': sum((r['category'] == category and r.get('semantic_pass') is True for r in rows))} for category in sorted({r['category'] for r in rows if 'category' in r})}, 'scope': 'Real original model engine only; controlled dependency/fault suite excluded.'}
