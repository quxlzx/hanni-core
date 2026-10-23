"""Independent V3.7 trust-boundary, telemetry and persistence checks.

These controlled loopback servers test the actual adapters, not GPU performance.
Expected invariants were sealed before implementation outputs.
"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest
from hanni.compute.registry import ComputeError, ComputeRegistry, loopback_url
from hanni.compute.transport import InferenceTransport
from hanni.compute.scheduler import ComputeScheduler, context_categories

def deployment(tmp_path, *, url='http://127.0.0.1:54321'):
    root = tmp_path / 'compute'
    root.mkdir()
    raw = {'version': 1, 'enabled': True, 'nodes': [], 'workers': [{'worker_id': 'independent-worker', 'node_id': 'local', 'local_url': url, 'model_id': 'independent-synthetic-model', 'enabled': True, 'context_configured': 131072, 'allowed_categories': ['synthetic'], 'concurrency': 1}], 'policy': {'max_queue': 2, 'timeout_seconds': 2}}
    path = root / 'deployment.json'
    path.write_text(json.dumps(raw), encoding='utf8')
    return (path, ComputeRegistry(tmp_path))

def test_fresh_readonly_registry_does_not_invalidate_an_open_controller_job(tmp_path):
    _, owner = deployment(tmp_path)
    receipt = {'job_id': 'live-owner-job', 'workflow_id': 'live-workflow', 'step_id': 'analysis', 'invocation_id': 'live-invocation', 'worker_id': 'independent-worker', 'state': 'RUNNING', 'verification_status': 'PENDING', 'created_at': 1.0}
    owner.receipt(receipt)
    reader = ComputeRegistry(tmp_path)
    try:
        assert reader.jobs()[0]['state'] == 'RUNNING'
        assert owner.jobs()[0]['state'] == 'RUNNING'
    finally:
        reader.close()
        owner.close()

@pytest.mark.parametrize('field', ['cache_type_k', 'cache_type_v'])
def test_changed_kv_runtime_invalidates_current_and_prior_context_proofs(tmp_path, field):
    path, registry = deployment(tmp_path)
    config = json.loads(path.read_text())
    config['workers'][0]['startup'] = {'context': 8192, 'model_file': 'controlled-synthetic.gguf', 'cache_type_k': 'f16', 'cache_type_v': 'f16'}
    path.write_text(json.dumps(config))
    registry.reload()
    try:
        registry.record_context_verified('independent-worker', target_tokens=8192, prompt_tokens=7697, model_id='independent-synthetic-model', prompt_sha256='a' * 64, response_sha256='b' * 64)
        config['workers'][0]['startup'][field] = 'q8_0'
        path.write_text(json.dumps(config))
        registry.reload()
        assert registry.observations['independent-worker'].get('max_context_verified') is None
        assert registry.prior_verified_context('independent-worker') == 0
    finally:
        registry.close()

def test_compute_parent_alias_cannot_read_or_mutate_foreign_receipts(tmp_path):
    import subprocess
    foreign = tmp_path / 'foreign'
    protected = tmp_path / 'protected'
    foreign.mkdir()
    protected.mkdir()
    owner = ComputeRegistry(foreign)
    owner.receipt({'job_id': 'foreign-live-job', 'workflow_id': 'foreign-workflow', 'state': 'RUNNING', 'verification_status': 'PENDING'})
    owner.close()
    outside = foreign / 'compute'
    database = outside / 'jobs.sqlite3'
    original_bytes = database.read_bytes()
    alias = protected / 'compute'
    try:
        alias.symlink_to(outside, target_is_directory=True)
    except OSError:
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(alias), str(outside)], capture_output=True, text=True)
        if result.returncode:
            pytest.skip('Platform cannot create a controlled directory alias.')
    reader = ComputeRegistry(protected)
    try:
        try:
            view = reader.snapshot()['jobs']
        except ComputeError:
            view = []
        assert view == [], "Protected registry cannot return another directory's receipts."
        assert database.read_bytes() == original_bytes, 'Read-only snapshot cannot mutate a foreign database.'
    finally:
        reader.close()

@contextmanager
def endpoint(responder):
    calls = []

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *_args):
            pass

        def do_GET(self):
            calls.append(self.path)
            status, headers, payload = responder(self.path)
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield (f'http://127.0.0.1:{server.server_port}', calls)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)

def test_removing_protected_deployment_revokes_stale_authorization(tmp_path):
    path, registry = deployment(tmp_path)
    try:
        assert registry.enabled
        path.unlink()
        registry.reload()
        assert not registry.enabled, 'Removed authorization file must not retain an enabled worker deployment.'
        assert registry.workers() == []
    finally:
        registry.close()

def test_reported_and_configured_128k_are_not_verified_capacity(tmp_path):
    _, registry = deployment(tmp_path)
    try:
        registry.observe('independent-worker', status='healthy', context_reported=131072, last_heartbeat=registry.clock())
        worker = registry.snapshot()['workers'][0]
        assert worker['context_configured'] == worker['context_reported'] == 131072
        assert worker['max_context_verified'] is None
        assert worker['queue_depth'] is None
        assert worker['vram_free_bytes'] is None
        assert worker['ram_available_bytes'] is None
        assert worker['throughput_tps'] is None
    finally:
        registry.close()

def test_active_slots_are_not_fabricated_queue_depth(tmp_path):

    def respond(path):
        data = {'/health': {'status': 'ok', 'slots_processing': 3}, '/v1/models': {'data': [{'id': 'independent-synthetic-model'}]}, '/props': {'default_generation_settings': {'n_ctx': 16384}}}[path]
        return (200, {}, data)
    with endpoint(respond) as (url, calls):
        _, registry = deployment(tmp_path, url=url)
        transport = InferenceTransport(registry)
        try:
            result = transport.health(registry.workers()[0])
            assert result['status'] == 'healthy'
            assert result['context_reported'] == 16384
            assert result['queue_depth'] is None, 'Processing slots describe running work, not waiting queue depth.'
            assert calls == ['/health', '/v1/models', '/props']
        finally:
            transport.close()
            registry.close()

def test_model_identity_mismatch_cannot_become_healthy(tmp_path):

    def respond(path):
        return (200, {}, {'status': 'ok'} if path == '/health' else {'data': [{'id': 'different-model'}]})
    with endpoint(respond) as (url, _):
        _, registry = deployment(tmp_path, url=url)
        transport = InferenceTransport(registry)
        try:
            result = transport.health(registry.workers()[0])
            assert result['status'] == 'unhealthy'
            assert result['model_id'] is None
            assert 'differs' in result['error']
        finally:
            transport.close()
            registry.close()

def test_redirect_cannot_escape_worker_trust_boundary(tmp_path):
    with endpoint(lambda _path: (200, {}, {'status': 'ok'})) as (destination, destination_calls):
        with endpoint(lambda _path: (302, {'Location': destination + '/health'}, {})) as (url, _):
            _, registry = deployment(tmp_path, url=url)
            transport = InferenceTransport(registry)
            try:
                with pytest.raises(ComputeError, match='redirect'):
                    transport.request(registry.workers()[0], 'GET', '/health')
                assert destination_calls == []
            finally:
                transport.close()
                registry.close()

@pytest.mark.parametrize('url', ['http://example.com:8080', 'http://' + '.'.join(('10', '42', '0', '33')) + ':8080', 'http://127.0.0.1:8080/admin', 'https://example.invalid/127.0.0.1:8080', 'http://127.0.0.1:8080?target=external'])
def test_nonloopback_or_administrative_urls_are_rejected(url):
    with pytest.raises(ComputeError):
        loopback_url(url)

def test_cancelled_request_never_reaches_endpoint(tmp_path):
    with endpoint(lambda _path: (200, {}, {'status': 'ok'})) as (url, calls):
        _, registry = deployment(tmp_path, url=url)
        transport = InferenceTransport(registry)
        event = threading.Event()
        event.set()
        try:
            with pytest.raises(ComputeError, match='cancel'):
                transport.request(registry.workers()[0], 'GET', '/health', cancel=event)
            assert calls == []
        finally:
            transport.close()
            registry.close()

def test_restart_retains_uncertain_job_identity_and_never_replays(tmp_path):
    _, registry = deployment(tmp_path)
    receipt = {'job_id': 'sealed-job', 'workflow_id': 'sealed-workflow', 'step_id': 'analysis', 'invocation_id': 'sealed-invocation', 'worker_id': 'independent-worker', 'state': 'RUNNING', 'input_sha256': 'a' * 64, 'created_at': 1.0, 'started_at': 2.0, 'verification_status': 'UNVERIFIED', 'retry_safe': True}
    registry.receipt(receipt)
    registry.close()
    reopened = ComputeRegistry(tmp_path)
    try:
        records = reopened.jobs()
        assert len(records) == 1
        recovered = records[0]
        assert recovered['job_id'] == receipt['job_id']
        assert recovered['workflow_id'] == receipt['workflow_id']
        assert recovered['invocation_id'] == receipt['invocation_id']
        assert recovered['started_at'] == 2.0
        assert recovered['state'] == 'LOST_CONNECTION'
        assert recovered['verification_status'] == 'UNVERIFIED'
    finally:
        reopened.close()

def test_compute_receipts_refuse_private_prompt_and_output_text(tmp_path):
    _, registry = deployment(tmp_path)
    try:
        for field in ('prompt', 'messages', 'output_text', 'response'):
            with pytest.raises(ComputeError, match='receipt'):
                registry.receipt({'job_id': 'job', 'workflow_id': 'workflow', field: 'synthetic sensitive text must not be retained'})
        assert registry.jobs() == []
    finally:
        registry.close()

def test_strict_ssh_forwarding_uses_only_loopback_binding(tmp_path):
    _, registry = deployment(tmp_path)
    transport = InferenceTransport(registry)
    try:
        args = transport._ssh({'username': 'fixture'}, '127.0.0.1', forward='127.0.0.1:54321:127.0.0.1:8080')
        assert 'StrictHostKeyChecking=yes' in args
        assert 'BatchMode=yes' in args
        assert 'ConnectionAttempts=1' in args
        assert 'RequestTTY=no' in args
        assert args[args.index('-L') + 1] == '127.0.0.1:54321:127.0.0.1:8080'
    finally:
        transport.close()
        registry.close()

@pytest.mark.parametrize('sensitive_capability,category', [('memory.read', 'memory'), ('screen.snapshot', 'screen'), ('google_calendar.agenda', 'sensitive'), ('google.gmail.thread', 'sensitive'), ('google.docs.read', 'sensitive'), ('google.drive.search', 'sensitive'), ('mcp.independent_provider_lookup', 'sensitive')])
def test_private_categories_survive_multiple_analysis_dependencies(sensitive_capability, category):
    completed = {'original': {'kind': 'tool', 'capability_id': sensitive_capability, 'dependencies': []}, 'first_analysis': {'kind': 'analysis', 'capability_id': None, 'dependencies': ['original']}, 'second_analysis': {'kind': 'analysis', 'capability_id': None, 'dependencies': ['first_analysis']}}
    assert category in context_categories(completed, ['second_analysis']), 'An intermediate analysis must not erase the source data trust category.'

def test_external_definition_hash_cannot_masquerade_as_local_project_source():
    completed = {'read': {'kind': 'tool', 'capability_id': 'file.read', 'external_definition_hash': 'imported-provider-definition', 'dependencies': []}}
    assert 'sensitive' in context_categories(completed, ['read'])

@contextmanager
def inference_endpoint(model_id, *, gate=None, output=None, finish_reason='stop'):
    calls = []
    entered = threading.Event()

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *_args):
            pass

        def do_GET(self):
            data = {'/health': {'status': 'ok'}, '/v1/models': {'data': [{'id': model_id}]}, '/props': {'default_generation_settings': {'n_ctx': 16384}}}[self.path]
            self.respond(data)

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(payload)
            entered.set()
            if gate is not None:
                assert gate.wait(5), 'Independent test did not release the controlled model request.'
            text = output if output is not None else payload['messages'][-1]['content'] + ':' + model_id
            self.respond({'choices': [{'message': {'content': text}, 'finish_reason': finish_reason}], 'usage': {'completion_tokens': 5}})

        def respond(self, data):
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {'url': f'http://127.0.0.1:{server.server_port}', 'calls': calls, 'entered': entered}
    finally:
        if gate is not None:
            gate.set()
        server.shutdown()
        server.server_close()
        thread.join(2)

def scheduler_fixture(tmp_path, endpoints, *, allowed=('synthetic',), retries=0, verified=True):
    root = tmp_path / 'compute'
    root.mkdir(parents=True)
    workers = [{'worker_id': f'worker_{i}', 'node_id': 'local', 'local_url': server['url'], 'model_id': f'synthetic_model_{i}', 'enabled': True, 'allowed_categories': list(allowed), 'capabilities': ['analysis', 'structured_json'], 'concurrency': 1} for i, server in enumerate(endpoints)]
    (root / 'deployment.json').write_text(json.dumps({'version': 1, 'enabled': True, 'nodes': [], 'workers': workers, 'policy': {'max_queue': 2, 'timeout_seconds': 1, 'max_retries': retries}}), encoding='utf8')
    registry = ComputeRegistry(tmp_path)
    scheduler = ComputeScheduler(registry)
    scheduler.refresh()
    if verified:
        for worker in workers:
            registry.observe(worker['worker_id'], max_context_verified=16384)
    return scheduler

def infer(scheduler, marker, **options):
    return scheduler.chat([{'role': 'user', 'content': marker}], workflow_id='independent-workflow', step_id=marker, invocation_id='invocation_' + marker, categories=['synthetic'], max_tokens=32, **options)

def test_independent_requests_overlap_on_distinct_workers_and_keep_association(tmp_path):
    gate = threading.Event()
    with inference_endpoint('synthetic_model_0', gate=gate) as first:
        with inference_endpoint('synthetic_model_1', gate=gate) as second:
            scheduler = scheduler_fixture(tmp_path, [first, second])
            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(infer, scheduler, marker) for marker in ('alpha', 'beta')]
                    try:
                        assert first['entered'].wait(2)
                        assert second['entered'].wait(2), 'Second worker must enter before the first request is released.'
                        assert sum(scheduler.registry.active.values()) == 2
                    finally:
                        gate.set()
                    results = [future.result(timeout=3) for future in futures]
                jobs = [job for _text, job in results]
                assert {job['worker_id'] for job in jobs} == {'worker_0', 'worker_1'}
                assert len({job['job_id'] for job in jobs}) == 2
                for marker, (text, job) in zip(('alpha', 'beta'), results):
                    assert text.startswith(marker + ':')
                    assert job['step_id'] == marker
                    assert job['invocation_id'] == 'invocation_' + marker
                    assert job['state'] == 'COMPLETED'
                    assert job['verification_status'] == 'PENDING'
                assert all((value == 0 for value in scheduler.registry.active.values()))
            finally:
                scheduler.close()

def test_unknown_context_never_receives_model_request(tmp_path):
    with inference_endpoint('synthetic_model_0') as worker:
        scheduler = scheduler_fixture(tmp_path, [worker], verified=False)
        try:
            with pytest.raises(ComputeError, match='verified capacity'):
                infer(scheduler, 'unknown_context')
            assert worker['calls'] == []
            assert scheduler.registry.jobs()[0]['state'] == 'BLOCKED'
        finally:
            scheduler.close()

def test_unapproved_context_categories_never_cross_http_boundary(tmp_path):
    with inference_endpoint('synthetic_model_0') as worker:
        scheduler = scheduler_fixture(tmp_path, [worker], allowed=('project',))
        try:
            with pytest.raises(ComputeError, match='verified capacity'):
                scheduler.chat([{'role': 'user', 'content': 'synthetic private screen content'}], workflow_id='workflow', step_id='step', invocation_id='invocation', categories=['project', 'screen'], max_tokens=32)
            assert worker['calls'] == []
        finally:
            scheduler.close()

@pytest.mark.parametrize('content,finish_reason', [('', 'stop'), ('valid-looking but truncated', 'length')])
def test_http200_incomplete_response_does_not_complete_job(tmp_path, content, finish_reason):
    with inference_endpoint('synthetic_model_0', output=content, finish_reason=finish_reason) as worker:
        scheduler = scheduler_fixture(tmp_path, [worker])
        try:
            with pytest.raises(ComputeError, match='empty|truncated'):
                infer(scheduler, 'incomplete_response')
            job = scheduler.registry.jobs()[0]
            assert job['state'] not in {'COMPLETED', 'VERIFIED'}
            assert job['verification_status'] == 'PENDING'
            assert scheduler.registry.active['worker_0'] == 0
        finally:
            scheduler.close()

def test_controller_admission_denial_prevents_http_dispatch(tmp_path):
    with inference_endpoint('synthetic_model_0') as worker:
        scheduler = scheduler_fixture(tmp_path, [worker])

        def deny():
            raise ComputeError('Original permission and lease gate denied dispatch.')
        try:
            with pytest.raises(ComputeError, match='gate denied'):
                infer(scheduler, 'denied', admission=deny)
            assert worker['calls'] == []
            assert scheduler.registry.active['worker_0'] == 0
        finally:
            scheduler.close()

def test_cancellation_drops_late_model_output_and_releases_reservation(tmp_path):
    gate = threading.Event()
    with inference_endpoint('synthetic_model_0', gate=gate) as worker:
        scheduler = scheduler_fixture(tmp_path, [worker])
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(infer, scheduler, 'cancelled')
                assert worker['entered'].wait(2)
                scheduler.cancel_workflow('independent-workflow')
                gate.set()
                with pytest.raises(ComputeError):
                    future.result(timeout=3)
            job = scheduler.registry.jobs()[0]
            assert job['state'] == 'CANCELLED'
            assert 'output_sha256' not in job
            assert scheduler.registry.active['worker_0'] == 0
        finally:
            scheduler.close()

def test_verified_capacity_cannot_survive_changed_loaded_model(tmp_path):
    _, registry = deployment(tmp_path)
    try:
        registry.observe('independent-worker', model_id='initial-model', context_reported=16384, max_context_verified=16384, last_heartbeat=registry.clock(), status='healthy')
        registry.observe('independent-worker', model_id='replacement-model', context_reported=16384, last_heartbeat=registry.clock(), status='healthy')
        assert registry.snapshot()['workers'][0]['max_context_verified'] is None
    finally:
        registry.close()

@pytest.mark.parametrize('occupancy_status', [0, 255])
def test_existing_or_uncertain_remote_listener_blocks_duplicate_start(tmp_path, monkeypatch, occupancy_status):
    _, registry = deployment(tmp_path)
    transport = InferenceTransport(registry)
    worker = {'worker_id': 'independent-worker', 'node_id': 'fixture-node', 'remote_port': 8080, 'startup': {'authorized': True, 'kind': 'llama_cpp'}}
    calls = []
    monkeypatch.setattr(registry, 'node', lambda _key: {'username': 'fixture'})
    monkeypatch.setattr(transport, '_address', lambda _node: '127.0.0.1')
    monkeypatch.setattr(transport, 'health', lambda _worker: {'status': 'unhealthy'})

    def run(command, **options):
        calls.append((command, options))
        return SimpleNamespace(returncode=occupancy_status)
    monkeypatch.setattr('hanni.compute.transport.subprocess.run', run)
    try:
        with pytest.raises(ComputeError, match='occupied|occupancy'):
            transport.start(worker)
        assert len(calls) == 1
        assert 'connect_ex' in calls[0][0][-1]
        assert 'input' not in calls[0][1], 'No remote launch script may run after occupied or uncertain port.'
        assert transport.owned == {}
    finally:
        transport.close()
        registry.close()

def analysis_report(value=90):
    return {'observations': [{'operation': 'percentage', 'sources': [{'step_id': 'read', 'path': '/data/text', 'json_path': '/passed'}, {'step_id': 'read', 'path': '/data/text', 'json_path': '/total'}], 'value': value}]}

class IndependentParallelPlan:
    """A disclosed planner fixture; remote outputs still face original verification."""

    def __init__(self, source, count):
        self.source, self.count, self.calls = (source, count, 0)

    def chat(self, _messages, **_options):
        self.calls += 1
        if self.calls == 1:
            steps = [{'step_id': 'read', 'description': 'Read supplied JSON from ' + self.source, 'kind': 'tool', 'dependencies': [], 'required': True, 'criteria': [{'operator': 'json_valid', 'path': '/data/text', 'expected': None}]}]
            steps.extend(({'step_id': f'analysis_{i}', 'description': 'Calculate the cited pass percentage.', 'kind': 'analysis', 'dependencies': ['read'], 'required': True, 'criteria': [{'operator': 'evidence_report', 'path': '/data/report', 'expected': None}]} for i in range(self.count)))
            return json.dumps({'summary': 'Independently analyze the supplied benchmark JSON.', 'unsupported_reason': None, 'steps': steps})
        if self.calls == 2:
            steps = [{'step_id': 'read', 'capability_id': 'file.read', 'arguments': {'path': self.source}}]
            steps.extend(({'step_id': f'analysis_{i}', 'capability_id': None, 'arguments': {'sources': ['read']}} for i in range(self.count)))
            return json.dumps({'unsupported_reason': None, 'steps': steps})
        raise AssertionError('A distributed step unexpectedly used the local planner fixture.')
from tests.unit.test_workflow_service import service, operation, approve_start

def test_original_workflow_runs_parallel_remote_steps_and_verifies_exact_cited_values(service, tmp_path):
    Path(service.client.source).write_text('{"passed":9,"total":10}', encoding='utf8')
    service.client = IndependentParallelPlan(service.client.source, 2)
    gate = threading.Event()
    output = json.dumps(analysis_report())
    with inference_endpoint('synthetic_model_0', gate=gate, output=output) as first:
        with inference_endpoint('synthetic_model_1', gate=gate, output=output) as second:
            scheduler = scheduler_fixture(tmp_path / 'independent-compute', [first, second], allowed=('project', 'conversation'))
            service.compute = scheduler
            try:
                key = operation(service, 'goal.submit', {'goal': 'Read JSON from ' + service.client.source + ' and perform two independent checked percentage analyses.', 'mode': 'assisted'})['workflow_id']
                detail = service.wait(key)
                assert detail['status'] == 'awaiting_plan_approval', detail
                assert scheduler.registry.jobs() == []
                approve_start(service, key, detail)
                try:
                    assert first['entered'].wait(3)
                    assert second['entered'].wait(3), 'Both original workflow steps must overlap on independent workers.'
                finally:
                    gate.set()
                final = service.wait(key)
                assert final['status'] == 'completed', final
                assert final['counts']['verified'] == 3
                assert len(final['invocations']) == 3
                jobs = scheduler.registry.jobs(key)
                assert len(jobs) == 2
                assert all((job['state'] == 'VERIFIED' and job['verification_status'] == 'VERIFIED' for job in jobs))
                assert {job['worker_id'] for job in jobs} == {'worker_0', 'worker_1'}
                assert all((job['workflow_id'] == key for job in jobs))
                assert service.client.calls == 2
            finally:
                service.compute = None
                scheduler.close()

@pytest.mark.parametrize('response', [analysis_report(91), {'observations': []}])
def test_original_workflow_rejects_false_or_malformed_remote_claims(service, tmp_path, response):
    Path(service.client.source).write_text('{"passed":9,"total":10}', encoding='utf8')
    service.client = IndependentParallelPlan(service.client.source, 1)
    with inference_endpoint('synthetic_model_0', output=json.dumps(response)) as worker:
        scheduler = scheduler_fixture(tmp_path / 'independent-compute', [worker], allowed=('project', 'conversation'))
        service.compute = scheduler
        try:
            key = operation(service, 'goal.submit', {'goal': 'Read JSON from ' + service.client.source + ' and calculate the checked pass percentage.', 'mode': 'assisted'})['workflow_id']
            detail = service.wait(key)
            assert detail['status'] == 'awaiting_plan_approval', detail
            approve_start(service, key, detail)
            final = service.wait(key)
            assert final['status'] != 'completed'
            assert final['counts']['verified'] == 1, 'Only the actual prerequisite file read may verify.'
            assert len(worker['calls']) == 1
            jobs = scheduler.registry.jobs(key)
            assert len(jobs) == 1
            assert jobs[0]['state'] == 'FAILED'
            assert jobs[0]['verification_status'] != 'VERIFIED'
        finally:
            service.compute = None
            scheduler.close()

def test_project_only_worker_cannot_receive_goal_derived_description(service, tmp_path):
    Path(service.client.source).write_text('{"passed":9,"total":10}', encoding='utf8')

    class LocalAnalysisPlan(IndependentParallelPlan):

        def chat(self, messages, **options):
            if self.calls >= 2:
                self.calls += 1
                return json.dumps(analysis_report())
            return super().chat(messages, **options)
    service.client = LocalAnalysisPlan(service.client.source, 1)
    with inference_endpoint('synthetic_model_0', output=json.dumps(analysis_report())) as worker:
        scheduler = scheduler_fixture(tmp_path / 'independent-compute', [worker], allowed=('project',))
        service.compute = scheduler
        try:
            key = operation(service, 'goal.submit', {'goal': 'Read JSON from ' + service.client.source + ' and summarize for my private rehearsal tomorrow.', 'mode': 'assisted'})['workflow_id']
            detail = service.wait(key)
            assert detail['status'] == 'awaiting_plan_approval'
            approve_start(service, key, detail)
            final = service.wait(key)
            assert final['status'] == 'completed', final
            assert service.client.calls == 3
            assert worker['calls'] == [], 'Project permission must not authorize goal/conversation forwarding.'
            assert scheduler.registry.jobs(key) == []
        finally:
            service.compute = None
            scheduler.close()

def test_safe_reassignment_preserves_first_worker_interruption_and_durable_history(tmp_path):
    with inference_endpoint('synthetic_model_0', output='') as first:
        with inference_endpoint('synthetic_model_1') as second:
            scheduler = scheduler_fixture(tmp_path, [first, second], retries=1)
            scheduler.registry.observe('worker_0', latency_ms=1)
            scheduler.registry.observe('worker_1', latency_ms=100)
            try:
                text, job = infer(scheduler, 'safe_retry')
                assert text == 'safe_retry:synthetic_model_1'
                assert job['attempt'] == 2
                assert len(first['calls']) == len(second['calls']) == 1
                saved = scheduler.registry.jobs()[0]
                interrupted = [event for event in saved['events'] if event['state'] == 'LOST_CONNECTION']
                assert len(interrupted) == 1
                assert interrupted[0]['worker_id'] == 'worker_0'
                assert interrupted[0]['attempt'] == 1
                assert interrupted[0]['error']
                assert any((event['state'] == 'ASSIGNED' and event['worker_id'] == 'worker_1' for event in saved['events']))
                assert all((event['job_id'] == job['job_id'] for event in saved['events']))
                assert all((event['workflow_id'] == job['workflow_id'] for event in saved['events']))
            finally:
                scheduler.close()
            reopened = ComputeRegistry(tmp_path)
            try:
                restored = reopened.jobs()[0]
                assert any((event['state'] == 'LOST_CONNECTION' and event['worker_id'] == 'worker_0' for event in restored['events']))
                assert restored['state'] == 'LOST_CONNECTION', 'Unverified completion still needs original workflow reconciliation.'
            finally:
                reopened.close()
