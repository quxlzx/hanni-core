"""Input-only original scheduling execution with isolated controlled providers."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
from hanni.compute.registry import ComputeRegistry, ComputeError, validate_deployment
from hanni.compute.scheduler import ComputeScheduler
from hanni.compute.transport import InferenceTransport
from scripts.campaign6_scheduling.providers import Activity, endpoint

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=str) + '\n', encoding='utf8', newline='\n')

def dependencies():
    values = {}
    for name, module in list(sys.modules.items()):
        file = getattr(module, '__file__', None)
        if file and file.endswith('.py') and (name.startswith('hanni.') or name.startswith('scripts.campaign4_boundaries') or name.startswith('tests.integration.test_workflow')):
            path = Path(file).resolve()
            values[name] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return values

def await_condition(test, seconds=2):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if test():
            return True
        time.sleep(0.002)
    return bool(test())

def run_case(case, root, *, diagnostics=None):
    if any((key in case for key in ('expected', 'oracle', 'checker_inputs'))):
        raise ValueError('Oracles are forbidden in execution inputs.')
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    before = dependencies()
    activity = Activity()
    providers = []
    results = {}
    errors = {}
    queue_seen = False
    if diagnostics is not None:
        diagnostics.update(providers=providers, activity=activity, results=results, errors=errors)
    operation = case['scenario']
    main_before_release = False
    workflow_record = None
    writes = None
    context_result = None
    prior_state = None
    deployment = dict(version=1, enabled=True, nodes=[], workers=[], policy=dict(max_queue=case.get('queue_limit', 16), timeout_seconds=case.get('policy_timeout_seconds', 1), max_retries=case.get('retry_policy', 0), fallback_local=False))
    cancellation = threading.Event()
    control = case.get('control')
    registry = None
    engine = None
    with ExitStack() as stack:
        for config in deepcopy(case['workers']):
            provider = stack.enter_context(endpoint(config, activity, workflow=operation == 'workflow_verification'))
            providers.append(provider)
            node = config.get('node_id', 'local')
            if node != 'local' and node not in {r['id'] for r in deployment['nodes']}:
                deployment['nodes'].append({'id': node})
            worker = dict(worker_id=config['id'], node_id=node, model_id=provider['model'], enabled=config.get('enabled', True), concurrency=config.get('concurrency', 1), interactive_reserve=config.get('interactive_reserve', 0), capabilities=config.get('capabilities', ['analysis']), allowed_categories=config.get('categories', ['synthetic']), context_configured=config.get('context_configured', 32768), protocol=config.get('protocol', 'openai'))
            if node == 'local':
                worker['local_url'] = provider['url']
            else:
                worker['remote_port'] = 1
            if config.get('gpu'):
                worker['gpu'] = config['gpu']
            if config.get('gpu_device') is not None:
                worker['startup'] = {'authorized': False, 'gpu_device': config['gpu_device']}
            deployment['workers'].append(worker)
        save(root / 'compute/deployment.json', deployment)
        registry = ComputeRegistry(root)
        transport = InferenceTransport(registry)
        provider_by_id = {p['id']: p for p in providers}
        transport.endpoint = lambda worker: provider_by_id[worker['worker_id']]['url']
        transport.runtime_files = lambda worker: 'controlled-files-' + worker['worker_id']

        def resources(worker):
            config = provider_by_id[worker['worker_id']]['config']
            sample = deepcopy(config.get('resources', {}))
            sample['resource_sampled_at'] = registry.clock() - config.get('resource_sample_age_seconds', 0)
            if config.get('gpu_measurement') is not None:
                sample['gpu_measurement'] = deepcopy(config['gpu_measurement'])
            return sample
        transport.resources = resources
        engine = ComputeScheduler(registry, transport=transport)
        if diagnostics is not None:
            diagnostics.update(registry=registry, engine=engine)
        stack.callback(engine.close)
        engine.refresh()
        for index, provider in enumerate(providers):
            config = provider['config']
            key = provider['id']
            verified = config.get('verified_context', 32768)
            if verified is not None:
                marker = ('Controlled context fixture for ' + key).encode()
                registry.record_context_verified(key, target_tokens=verified, prompt_tokens=max(1, int(0.95 * verified)), model_id=provider['model'], prompt_sha256=hashlib.sha256(marker).hexdigest(), response_sha256=hashlib.sha256(marker + b' response').hexdigest())
            update = {'latency_ms': config.get('latency_ms', 1 + index * 100)}
            if config.get('health'):
                update['status'] = config['health']
            if 'heartbeat_age_seconds' in config:
                update['last_heartbeat'] = registry.clock() - config['heartbeat_age_seconds']
            registry.observe(key, **update)
        initial = registry.snapshot()

        def mutate(kind):
            if kind in {'cancel_before', 'cancel_running', 'cancel_queued'}:
                cancellation.set()
                return
            worker = registry.worker(case['workers'][0]['id'])
            if kind == 'resources_down':
                registry.observe(worker['worker_id'], ram_available_bytes=0)
                return
            if kind == 'runtime_after':
                registry.observe(worker['worker_id'], runtime_identity='controlled-changed-runtime')
                return
            if kind in {'revoke_worker', 'revoke_after'}:
                worker['enabled'] = False
            elif kind == 'revoke_categories':
                worker['allowed_categories'] = []
            elif kind == 'change_model':
                worker['model_id'] = 'controlled-replaced-model'
            else:
                return
            candidate = deepcopy(registry.deployment)
            candidate['workers'] = [worker if w['worker_id'] == worker['worker_id'] else w for w in candidate['workers']]
            save(root / 'compute/deployment.json', validate_deployment(candidate))
            registry.reload()
        admission_count = 0

        def admission():
            nonlocal admission_count
            admission_count += 1
            if admission_count == 1 and control in {'revoke_worker', 'revoke_categories', 'change_model', 'resources_down'}:
                mutate(control)

        def chat(label='main', override=None):
            req = deepcopy(case['request'])
            req.update(override or {})
            messages = deepcopy(req['messages'])
            messages[-1]['content'] = 'label=' + label + '\n' + messages[-1]['content']
            kwargs = {key: req[key] for key in ('max_tokens', 'response_format', 'interactive', 'allowed_worker_ids') if key in req}
            if 'retry_override' in req:
                kwargs['max_retries_override'] = req['retry_override']
            if 'queue_seconds' in req:
                kwargs['max_queue_seconds'] = req['queue_seconds']
            try:
                value, job = engine.chat(messages, workflow_id='workflow_' + label, step_id=label, invocation_id='invocation_' + label, categories=req['categories'], cancellation=cancellation if label == 'main' else None, admission=admission if label == 'main' else None, **kwargs)
                results[label] = {'text': value, 'job': job}
            except Exception as exc:
                errors[label] = {'class': type(exc).__name__, 'message': str(exc)}
        if control == 'cancel_before':
            mutate(control)
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = []
            gate = threading.Event()

            def gate_providers(labels=None):
                for provider in providers:
                    provider['gate'] = gate
                    provider['gated_labels'] = labels
            if operation in {'background_queue', 'queue_saturation', 'ordered_queue'}:
                backgrounds = case.get('background', [{'worker_id': providers[0]['id'], 'label': 'background'}])
                gate_providers({row['label'] for row in backgrounds})
                for background in backgrounds:
                    futures.append(pool.submit(chat, background['label'], {'allowed_worker_ids': [background['worker_id']], 'queue_seconds': 1, 'interactive': background.get('interactive', False)}))
                if not await_condition(lambda: len(activity.entries) >= len(backgrounds)):
                    raise RuntimeError('Controlled occupying calls did not enter.')
                for i in range(case.get('queued_count', 0)):
                    futures.append(pool.submit(chat, 'queued' + str(i), {'queue_seconds': 1, 'interactive': False}))
                    if not await_condition(lambda: len(engine.waiting) >= i + 1):
                        raise RuntimeError('Controlled queued admission did not persist.')
                main = pool.submit(chat)
                futures.append(main)
                if operation == 'queue_saturation':
                    main.result(2)
                elif case.get('release') == 'after_main_entered':
                    if not await_condition(lambda: any((e['label'] == 'main' for e in activity.entries))):
                        raise RuntimeError('Main did not use its independent reserved slot.')
                    main_before_release = True
                else:

                    def main_waiting():
                        return any((job['step_id'] == 'main' and job['job_id'] in engine.queued and any((ticket[2] == job['job_id'] for ticket in engine.waiting)) for job in registry.jobs()))
                    queue_seen = await_condition(lambda: main_waiting() or main.done()) and main_waiting()
                    if control == 'cancel_queued':
                        mutate(control)
                    if case.get('release') == 'after_main_finished' or control == 'cancel_queued':
                        main.result(2)
                gate.set()
                for future in futures:
                    future.result(3)
            elif operation == 'parallel':
                gate_providers()
                interactive = case.get('interactive_index')
                indices = list(range(case['batch']))
                if case.get('start_background_first'):
                    indices = [i for i in indices if i != interactive] + [interactive]
                for position, i in enumerate(indices):
                    if position and case.get('start_background_first') and (i == interactive):
                        if not await_condition(lambda: bool(activity.entries)):
                            raise RuntimeError('Controlled background-first admission did not enter.')
                    futures.append(pool.submit(chat, 'parallel' + str(i), {'interactive': i == interactive, 'queue_seconds': case['request'].get('queue_seconds', 1)}))
                if not await_condition(lambda: len(activity.entries) >= case['release_after_entries']):
                    raise RuntimeError('Requested controlled overlap did not enter.')
                gate.set()
                for future in futures:
                    future.result(3)
            elif operation == 'timeout':
                gate_providers()
                future = pool.submit(chat)
                if not await_condition(lambda: bool(activity.entries)):
                    raise RuntimeError('Timeout fixture never entered.')
                future.result(3)
                gate.set()
            elif operation == 'workflow_verification':
                from scripts.campaign4_boundaries.compute_fixture import analysis_client
                from scripts.campaign4_boundaries.harness import ServiceFixture, reviewed_start
                source = root / 'source.json'
                source.write_text('{"passed":4,"total":10}', encoding='utf8')
                with ServiceFixture(root / 'workflow', client=analysis_client(source)) as box:
                    box.service.compute = engine
                    box.observe('file.write')
                    key = box.submit('Read the JSON file ' + str(source) + ', calculate the percentage and save a checked report.')
                    reviewed_start(box, key)
                    workflow_record = box.await_state(key, 'completed', 'blocked', 'partially_completed')
                    writes = box.ledger.entries('file.write')
                    box.service.compute = None
            elif operation == 'context_probe':
                try:
                    context_result = engine.verify_context(providers[0]['id'], [{'role': 'user', 'content': 'Synthetic marker=fixture; return marker JSON.'}], target_tokens=case['target_tokens'], expected={'marker': 'fixture'}, anthropic=True, max_output_tokens=16)
                except Exception as exc:
                    errors['main'] = {'class': type(exc).__name__, 'message': str(exc)}
            elif operation in {'reconnect', 'scheduler_restart'}:
                chat('prior')
                prior_job = registry.jobs('workflow_prior')[0]
                if operation == 'reconnect':
                    providers[0]['behavior'] = 'complete'
                    engine.refresh()
                else:
                    engine.close()
                    registry = ComputeRegistry(root)
                    transport = InferenceTransport(registry)
                    transport.endpoint = lambda worker: provider_by_id[worker['worker_id']]['url']
                    transport.resources = resources
                    transport.runtime_files = lambda worker: 'controlled-files-' + worker['worker_id']
                    engine = ComputeScheduler(registry, transport=transport)
                    stack.callback(engine.close)
                    engine.refresh()
                prior_state = registry.jobs('workflow_prior')[0]['state']
                chat()
                if prior_job['job_id'] != registry.jobs('workflow_prior')[0]['job_id']:
                    raise RuntimeError('Original prior job identity was lost.')
            elif control in {'cancel_running', 'revoke_after', 'runtime_after'}:
                gate_providers()
                future = pool.submit(chat)
                if not await_condition(lambda: bool(activity.entries)):
                    raise RuntimeError('Controlled dispatch did not enter.')
                if control == 'cancel_running':
                    engine.cancel_workflow('workflow_main')
                else:
                    mutate(control)
                gate.set()
                future.result(3)
            else:
                chat()
        jobs = registry.jobs(limit=100)
        final = registry.snapshot()
        main_job = next((j for j in jobs if j['step_id'] == 'main'), None)
        if workflow_record and jobs:
            main_job = jobs[0]
        row = {'id': case['id'], 'category': case['category'], 'scenario': operation, 'input_sha256': hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest(), 'scope': 'Original scheduler/registry/HTTP transport with controlled loopback endpoint/resource leaves; no live model, GPU or cluster proof.', 'real_model': False, 'real_cluster': False, 'results': results, 'errors': errors, 'jobs': jobs, 'initial': initial, 'final': final, 'main_job': main_job, 'queue_seen': queue_seen, 'main_before_release': main_before_release, 'prior_state': prior_state, 'workflow': workflow_record, 'writes': writes, 'context_result': context_result, 'activity': deepcopy(activity.entries), 'maximum_overlap': activity.maximum, 'active_reservations': dict(registry.active), 'waiting_tickets': len(engine.waiting), 'inflight_count': len(engine.inflight), 'provider_calls': {p['id']: deepcopy(p['calls']) for p in providers}, 'source_before': before, 'source_after': dependencies()}
        save(root / 'receipt-before-cleanup.json', row)
    row['owned_provider_closed'] = all((p['closed'] for p in providers))
    row['owned_scheduler_closed'] = engine.closed
    await_condition(lambda: activity.active == 0)
    row['active_provider_handlers_after_cleanup'] = activity.active
    row['provider_calls_after_cleanup'] = {p['id']: deepcopy(p['calls']) for p in providers}
    save(root / 'receipt.json', row)
    return row

def grade(row, oracle):
    if row['id'] != oracle['id']:
        raise ValueError('Receipt/oracle identity mismatch.')
    expected = oracle['expected']
    checks = []

    def check(name, actual, wanted):
        checks.append({'check': name, 'passed': actual == wanted, 'observed': actual, 'expected': wanted})
    if 'error' in expected:
        check('main_error', bool(row['errors'].get('main')), expected['error'])
    elif row['scenario'] not in {'queue_saturation', 'workflow_verification', 'context_probe'}:
        check('main_error', bool(row['errors'].get('main')), False)
    if 'worker_id' in expected:
        check('selected_worker', (row['main_job'] or {}).get('worker_id'), expected['worker_id'])
    if 'dispatches' in expected:
        check('original_http_dispatches', {key: len(calls) for key, calls in row['provider_calls'].items()}, expected['dispatches'])
    if 'main_state' in expected:
        check('main_job_state', (row['main_job'] or {}).get('state'), expected['main_state'])
    if 'main_attempt' in expected:
        check('bounded_attempts', (row['main_job'] or {}).get('attempt'), expected['main_attempt'])
    if 'job_count' in expected:
        check('durable_job_count', len(row['jobs']), expected['job_count'])
    if 'maximum_overlap' in expected:
        check('actual_http_overlap', row['maximum_overlap'], expected['maximum_overlap'])
    if 'queue_seen' in expected:
        check('actual_queued_ticket', row['queue_seen'], expected['queue_seen'])
    if 'main_before_release' in expected:
        check('independent_capacity_used_before_release', row['main_before_release'], expected['main_before_release'])
    if 'request_order' in expected:
        check('original_dispatch_order', [item['label'] for item in row['activity']], expected['request_order'])
    if 'queue_rejected' in expected:
        check('queue_saturation_rejected', 'queue is full' in (row['errors'].get('main') or {}).get('message', ''), expected['queue_rejected'])
    if 'completed_results' in expected:
        check('returned_deliveries', len(row['results']), expected['completed_results'])
    if 'workflow_status' in expected:
        check('source_verified_workflow_status', (row['workflow'] or {}).get('status'), expected['workflow_status'])
    if 'writes' in expected:
        check('actual_original_artifact_write_entries', row['writes'], expected['writes'])
    if 'prior_state' in expected:
        check('interrupted_prior_preserved', row['prior_state'], expected['prior_state'])
    if 'context_passed' in expected:
        check('original_context_verification', (row['context_result'] or {}).get('passed'), expected['context_passed'])
    if expected.get('all_released'):
        check('active_reservations_released', sum(row['active_reservations'].values()), 0)
        check('queue_drained', row['waiting_tickets'], 0)
        check('inflight_drained', row['inflight_count'], 0)
        check('owned_providers_closed', row['owned_provider_closed'], True)
        check('owned_scheduler_closed', row['owned_scheduler_closed'], True)
        check('owned_provider_handlers_finished', row['active_provider_handlers_after_cleanup'], 0)
    return {'passed': all((c['passed'] for c in checks)), 'checks': checks}

def run(output, inputs, oracles):
    output = Path(output).resolve()
    cases = json.loads(Path(inputs).read_text())['cases']
    refs = {r['id']: r for r in json.loads(Path(oracles).read_text())['oracles']}
    if output.exists():
        raise ValueError('Never overwrite prior campaign evidence.')
    output.mkdir(parents=True)
    rows = []
    for case in cases:
        trace = {}
        try:
            row = run_case(case, output / case['id'], diagnostics=trace)
            verdict = grade(row, refs[case['id']])
            rows.append({'id': case['id'], 'category': case['category'], **verdict})
        except Exception as exc:
            failure = {'id': case['id'], 'category': case['category'], 'passed': False, 'harness_error': {'class': type(exc).__name__, 'message': str(exc)}}
            if 'activity' in trace:
                failure['controlled_dispatch_trace'] = deepcopy(trace['activity'].entries)
                failure['maximum_overlap'] = trace['activity'].maximum
                failure['provider_calls'] = {p['id']: deepcopy(p['calls']) for p in trace['providers']}
                failure['owned_providers_closed'] = all((p['closed'] for p in trace['providers']))
                failure['results'] = deepcopy(trace['results'])
                failure['errors'] = deepcopy(trace['errors'])
                engine = trace.get('engine')
                failure['cleanup_state'] = {'closed': engine.closed, 'active': dict(engine.registry.active), 'waiting': len(engine.waiting), 'inflight': len(engine.inflight)} if engine else None
            save(output / case['id'] / 'harness-error.json', failure)
            rows.append(failure)
        save(output / 'progress.json', rows)
    value = {'cases': len(rows), 'passed': sum((r['passed'] for r in rows)), 'failures': [r for r in rows if not r['passed']], 'scope': 'Controlled original implementation checks only; live cluster inference unavailable/not claimed.'}
    save(output / 'summary.json', value)
    print(json.dumps(value, indent=2))
    return value
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, default=Path('evals/compute/campaign6_development.json'))
    parser.add_argument('--oracles', type=Path, default=Path('evals/compute/campaign6_development_oracles.json'))
    args = parser.parse_args()
    run(args.output, args.inputs, args.oracles)
