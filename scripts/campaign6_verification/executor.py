"""Oracle-free independent scheduling executor over original protected APIs.

Loopback providers and resource/context observations are controlled fixtures.
Their replies/usage never establish actual model, hardware or throughput proof.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, ExitStack
from copy import deepcopy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import threading
import time
from hanni.compute import ComputeRegistry, ComputeScheduler
from hanni.compute.transport import InferenceTransport
from hanni.workflows.verification import evaluate_step

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8', newline='\n')

def wait_for(test, seconds=0.15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if test():
            return True
        time.sleep(0.001)
    return bool(test())

class Activity:

    def __init__(self):
        self.lock = threading.Lock()
        self.active = 0
        self.maximum = 0

    def enter(self):
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)

    def leave(self):
        with self.lock:
            self.active -= 1

def controlled_report(value):
    return {'observations': [{'operation': 'percentage', 'sources': [{'step_id': 'source', 'path': '/data/text', 'json_path': '/passed'}, {'step_id': 'source', 'path': '/data/text', 'json_path': '/total'}], 'value': value}]}

@contextmanager
def provider(config, activity, cancel, gate):
    model = 'owned-control-' + config['id']
    state = {'calls': [], 'health': [], 'model': model, 'closed': False}

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *_):
            pass

        def respond(self, value):
            raw = json.dumps(value, allow_nan=False).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            return raw

        def do_GET(self):
            state['health'].append(self.path)
            self.respond({'/health': {'status': 'ok'}, '/v1/models': {'data': [{'id': model}]}, '/props': {'default_generation_settings': {'n_ctx': config['context_reported']}}}[self.path])

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            call = {'request_raw': raw.decode(), 'request_sha256': hashlib.sha256(raw).hexdigest(), 'entered_at': time.monotonic()}
            state['calls'].append(call)
            activity.enter()
            try:
                if gate is not None:
                    if not gate.wait(2):
                        call['fixture_barrier_expired'] = True
                behavior = config['response_behavior']
                if behavior == 'cancel_after_enter':
                    cancel.set()
                if behavior == 'disconnect':
                    self.close_connection = True
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    self.connection.close()
                    call['disconnected'] = True
                    return
                value = 26 if behavior == 'unsupported_claim' else 25
                result = {'model': model, 'choices': [{'message': {'content': json.dumps(controlled_report(value))}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 40, 'completion_tokens': 25, 'total_tokens': 65}}
                call['response_raw'] = self.respond(result).decode()
            finally:
                call['finished_at'] = time.monotonic()
                activity.leave()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    state['url'] = 'http://127.0.0.1:' + str(server.server_port)
    try:
        yield state
    finally:
        if gate is not None:
            gate.set()
        server.shutdown()
        server.server_close()
        thread.join(2)
        state['closed'] = not thread.is_alive()

def source_evidence(root, output):
    """Actual original file read and cited calculation acceptance, no model oracle."""
    from hanni.config import load_config
    from hanni.tools.base import ToolRequest
    from hanni.tools.registry import build_default_registry
    repo = Path(__file__).resolve().parents[2]
    source = root / 'source.json'
    source.write_text('{"passed":3,"total":12}', encoding='utf-8')
    registry = build_default_registry(load_config(repo / 'config'), data_dir=root / 'original-tools')
    read = registry.execute(ToolRequest('file.read', {'path': str(source)}, correlation_id='c6-independent-source-read')).to_dict()
    completed = {'source': {'status': 'verified', 'kind': 'tool', 'capability_id': 'file.read', 'verification': read.get('verification'), 'result': read}}
    step = {'step_id': 'calculation', 'kind': 'analysis', 'dependencies': ['source'], 'arguments': {'sources': ['source']}, 'criteria': [{'path': '/data/report', 'operator': 'evidence_report', 'expected': None}]}
    report = json.loads(output)
    evidence = evaluate_step(step, {'ok': True, 'data': {'report': report}}, completed)
    return {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'original_read': read, 'report': report, 'acceptance': evidence}

def run_case(case, root):
    """Execute only input fields. No expected/oracle/scorer data is accepted."""
    if any((field in case for field in ('expected', 'oracle', 'checker_inputs'))):
        raise ValueError('Execution inputs cannot include oracles')
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    began = time.monotonic()
    activity = Activity()
    cancellation = threading.Event()
    gate = threading.Event() if case['controls'].get('barrier') else None
    providers, results, errors = ({}, {}, {})
    row = {'id': case['id'], 'category': case['category'], 'scope': case['scope'], 'input_sha256': hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest(), 'actual_model': False, 'actual_hardware': False, 'first_observed_queued': False, 'second_queue_rejected': False, 'source_verification': []}
    with ExitStack() as stack:
        nodes, workers = ([], [])
        for config in case['workers']:
            entry = stack.enter_context(provider(config, activity, cancellation, gate))
            providers[config['id']] = entry
            nodes.append({'id': config['node_id']})
            workers.append({'worker_id': config['id'], 'node_id': config['node_id'], 'model_id': entry['model'], 'enabled': config['enabled'], 'protocol': config['protocol'], 'remote_port': 1, 'concurrency': config['concurrency'], 'interactive_reserve': config['interactive_reserve'], 'capabilities': config['capabilities'], 'allowed_categories': config['categories'], 'context_configured': config['context_configured'], 'gpu': config['gpu']})
        write(root / 'compute/deployment.json', {'version': 1, 'enabled': True, 'nodes': nodes, 'workers': workers, 'policy': {**case['policy'], 'fallback_local': False}})
        registry = ComputeRegistry(root)
        transport = InferenceTransport(registry)
        transport.endpoint = lambda worker: providers[worker['worker_id']]['url']
        transport.runtime_files = lambda worker: 'controlled-runtime-files-' + worker['worker_id']
        config_by_id = {config['id']: config for config in case['workers']}

        def resources(worker):
            config = config_by_id[worker['worker_id']]
            return {**deepcopy(config['resources']), 'resource_sampled_at': registry.clock() - config['resource_sample_age_seconds']}
        transport.resources = resources
        engine = ComputeScheduler(registry, transport=transport)
        stack.callback(registry.close)
        stack.callback(engine.close)
        engine.refresh()
        for config in case['workers']:
            key = config['id']
            registry.record_context_verified(key, target_tokens=config['verified_context'], prompt_tokens=max(1, int(0.95 * config['verified_context'])), model_id=providers[key]['model'], prompt_sha256='a' * 64, response_sha256='b' * 64)
            registry.observe(key, status=config['health'], last_heartbeat=registry.clock() - config['heartbeat_age_seconds'], context_reported=config['context_reported'], latency_ms=config['latency_ms'])
            registry.active[key] = config['active_jobs']
        baseline_active = dict(registry.active)
        row['initial'] = registry.snapshot()
        req = case['request']

        def chat(label):
            try:
                text, job = engine.chat(req['messages'], workflow_id='isolated_' + label, step_id=label, invocation_id='invocation_' + label, categories=req['categories'], cancellation=cancellation, max_tokens=req['max_tokens'], interactive=req['interactive'], max_retries_override=req['retry_override'], max_queue_seconds=req['queue_seconds'])
                results[label] = {'text': text, 'job': deepcopy(job)}
                if case['controls'].get('verify_against_source'):
                    check = source_evidence(root, text)
                    row['source_verification'].append(check)
                    engine.finish(job, check['acceptance'])
            except Exception as exc:
                errors[label] = {'type': type(exc).__name__, 'message': str(exc)}
        scenario = case['scenario']
        with ThreadPoolExecutor(max_workers=2) as pool:
            if scenario == 'selection':
                required = req.get('required_context_tokens', len(json.dumps(req['messages']).encode()) + req['max_tokens'])
                row['ordered_choices'] = [value[1] for value in engine._choices(req['categories'], required, interactive=req['interactive'])]
            elif scenario == 'parallel':
                futures = [pool.submit(chat, 'request_' + str(index)) for index in range(case['controls']['parallel_requests'])]
                if gate is not None:
                    row['barrier_reached'] = wait_for(lambda: activity.active == len(futures), seconds=2)
                    gate.set()
                for future in futures:
                    future.result(3)
            elif scenario in {'queue_full', 'queued_release'}:
                first = pool.submit(chat, 'first')
                row['first_observed_queued'] = wait_for(lambda: len(engine.waiting) == 1)
                if scenario == 'queue_full':
                    chat('second')
                    row['second_queue_rejected'] = 'queue is full' in errors.get('second', {}).get('message', '')
                    cancellation.set()
                else:
                    for key in registry.active:
                        registry.active[key] = 0
                        baseline_active[key] = 0
                with engine.condition:
                    engine.condition.notify_all()
                first.result(3)
            elif scenario in {'chat', 'verified_chat'}:
                chat('request')
            else:
                raise ValueError('Unsupported generic scheduling operation')
        row.update(results=results, errors=errors, jobs=registry.jobs(limit=100), final=registry.snapshot(), max_active=activity.maximum, waiting_after=len(engine.waiting), inflight_after=len(engine.inflight), active_reservations=dict(registry.active), preexisting_reservations=baseline_active, all_reservations_released=all((registry.active.get(key, 0) == value for key, value in baseline_active.items())) and (not engine.waiting) and (not engine.inflight), provider_calls={key: deepcopy(value['calls']) for key, value in providers.items()}, provider_health={key: deepcopy(value['health']) for key, value in providers.items()}, duration_ms=(time.monotonic() - began) * 1000)
        write(root / 'receipt-before-cleanup.json', row)
    row.update(owned_providers_closed=all((value['closed'] for value in providers.values())), owned_scheduler_closed=engine.closed, owned_registry_closed=registry.db is None)
    write(root / 'receipt.json', row)
    return row
