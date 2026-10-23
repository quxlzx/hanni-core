"""Input-only original implementation adapters, no C10 oracle import.

Fixtures below isolate all durable state. Compute transport, planner responses,
and device leaves are explicitly controlled, never substitutes for live models.
"""
from dataclasses import asdict
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import threading
import time
from uuid import uuid4
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
ALIASES = {'memory.search': 'memory.retrieve', 'project.context': 'project.package', 'cluster.status': 'cluster.snapshot', 'screen.status': 'screen.awareness', 'screen.image_admission': 'screen.invalid_image'}

def json_safe(value):
    if hasattr(value, 'to_dict'):
        return json_safe(value.to_dict())
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value

def source_manifest():
    files = list((ROOT / 'src/hanni').rglob('*.py'))
    files += list((ROOT / 'scripts/campaign10_systems').glob('*.py'))
    files += [ROOT / p for p in ('scripts/campaign4/workflow_harness.py', 'scripts/campaign7_voice/controls.py', 'tests/helpers.py')]
    return {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

def original_memory_wrapper(fallback_session, store, *, registry, **options):
    """Root may supply the actual existing controller; this function never calls it.

    No fixed answer or new model client is supplied. Original registered owner
    profile, emergency-stop, privacy, and native fallback limits remain active.
    """
    from hanni.memory.session import MemoryAwareSession
    return MemoryAwareSession(fallback_session, store, registry=registry, **options)

def _observation(receipt, operation, data, error=None):
    receipt['observations'].append({'operation': operation, 'data': json_safe(data), 'error': error})

def audit_replays(detail):
    """Read-only original verifier over durable invocation history.

    Original invocation state is finished, not verified. Only an earlier
    finished result passing the native step verifier proves completion.
    """
    from hanni.workflows.verification import evaluate_step
    steps = {row['step_id']: row for row in detail.get('steps', [])}
    completed, repeated = ({}, [])
    for invocation in sorted(detail.get('invocations', []), key=lambda row: row.get('started_at', '')):
        key = invocation['step_id']
        if key in completed:
            repeated.append({'step_id': key, 'invocation_id': invocation['invocation_id']})
        if invocation.get('state') != 'finished' or key not in steps:
            continue
        result = invocation.get('result') or {}
        evidence = evaluate_step(steps[key], result, completed)
        if evidence['status'] == 'VERIFIED':
            completed[key] = {**steps[key], 'status': 'verified', 'result': result, 'verification': evidence}
    return {'count': len(repeated), 'replayed_invocations': repeated, 'verified_prior_steps': list(completed), 'method': 'original evaluate_step over chronologically finished durable results'}

def _memory(case, root, receipt):
    from hanni.memory.store import MemoryStore
    from hanni.memory.retrieval import ContextAwareRetriever
    from hanni.memory.projects import ProjectContext
    from hanni.dashboard.productivity import ProductivityStore
    fixture = case['fixtures']
    store_path = root / 'memory.sqlite3'
    store = MemoryStore(store_path)
    workspace = ProductivityStore(root / 'workspace')
    projects, records, suggestions = ({}, [], [])

    def mutate(operation, data):
        return workspace.mutate(operation, data, request_id=str(uuid4()))
    for row in fixture.get('projects', []):
        result = mutate('project.create', {key: row[key] for key in ('name', 'description') if key in row})
        projects[row.get('key', row['name'])] = result['project']['id']
    context = ProjectContext(store, workspace)
    for item in fixture.get('memories', []):
        options = {k: v for k, v in item.items() if k not in {'content', 'project'}}
        if item.get('project'):
            options['project_id'] = projects[item['project']]
        record, _ = store.remember(item['content'], **options)
        records.append(record.id)
    for row in fixture.get('notes', []):
        mutate('note.create', {'project_id': projects[row['project']], 'title': row['title'], 'body': row['body']})
    for row in fixture.get('links', []):
        target = row['target'].replace('{root}', str(root).replace('\\', '/'))
        mutate('link.create', {'project_id': projects[row['project']], 'label': row['label'], 'target': target, 'kind': 'file'})
    for row in fixture.get('tasks', []):
        mutate('task.create', {**{k: v for k, v in row.items() if k != 'project'}, 'project_id': projects[row['project']]})
    retriever = ContextAwareRetriever(store, max_tokens=fixture.get('max_tokens', 4000))
    for action in case['actions']:
        operation = ALIASES.get(action['operation'], action['operation'])
        args = action.get('args', {})
        if operation == 'memory.retrieve':
            result = retriever.retrieve(args['query'])
            encoded = result.text
            data = {'contents': [m.record.content for m in result.matches], 'text': encoded, 'bytes': len(encoded.encode()), 'valid_json': not encoded or isinstance(json.loads(encoded), dict), 'metrics': deepcopy(retriever.last_metrics)}
        elif operation == 'memory.correct':
            old = store.get(records[args['index']])
            result = store.correct(old.id, args['content'], expected_updated_at=old.updated_at.isoformat())
            data = result.to_dict()
        elif operation == 'memory.delete':
            old = store.get(records[args['index']])
            data = {'deleted': store.delete(old.id, expected_updated_at=old.updated_at.isoformat())}
        elif operation == 'memory.reopen':
            store = MemoryStore(store_path)
            retriever = ContextAwareRetriever(store, max_tokens=fixture.get('max_tokens', 4000))
            context = ProjectContext(store, workspace)
            data = {'count': store.count(), 'scope': 'same owned SQLite, new original store/retriever instance'}
        elif operation == 'memory.propose':
            proposal = store.propose('add', args['content'], source='owner_statement:controlled-development')
            suggestions.append(proposal.id)
            data = proposal.to_dict()
        elif operation == 'memory.review':
            suggestion = store.get_suggestion(suggestions[args.get('index', -1)])
            data = store.review_suggestion(suggestion.id, args['decision'], expected_updated_at=suggestion.updated_at.isoformat()).to_dict()
        elif operation == 'project.resolve':
            data = context.resolve(args['query'])
            data['resolved_key'] = next((k for k, v in projects.items() if v == data['project_id']), None)
        elif operation == 'project.package':
            package = context.package(projects[args['project']], query=args.get('query', ''))
            data = {'memory_contents': [row['content'] for row in package['memories']], 'decision_count': len(package['decisions']), 'plan_count': len(package['plans']), 'verified_result_count': len(package['verified_results']), 'notes': [row['body'] for row in package['notes']], 'file_count': len(package['files']), 'uncertainties': '\n'.join(package['uncertainties']), 'package': package}
        elif operation in {'project.alias', 'project.remove_alias'}:
            identity = projects[args['project']]
            current = context.project(identity)
            if operation == 'project.alias':
                data = context.add_alias(identity, args['alias'], expected_fingerprint=current['fingerprint'])
            else:
                data = context.remove_link(identity, 'alias', args['alias'], expected_fingerprint=current['fingerprint'])
        elif operation == 'project.workspace':
            result = workspace.snapshot()
            data = {'project_count': len(result['projects']), 'task_count': len(result['tasks']), 'all_day': [r['all_day'] for r in result['tasks']], 'snapshot': result}
        else:
            raise NotImplementedError('Unsupported public memory/project operation: ' + operation)
        _observation(receipt, operation, data)
    receipt.update(memory_count=store.count(), project_count=len(workspace.snapshot()['projects']), tool_dispatches=0, intent_scope='original deterministic retrieval/resolution; no model intent or final synthesis measured')

def _workflow(case, root, receipt):
    from scripts.campaign4.workflow_harness import run_case as native_run
    fixture = {key: deepcopy(value) for key, value in case['fixtures'].items() if key != 'adapter'}
    fixture.update(id=case['id'], category=case['family'], scenario=case['description'])
    raw = native_run(fixture, root / 'workflow')
    receipt['raw_workflow'] = raw
    detail = raw.get('workflow', {})
    steps, invocations = (detail.get('steps', []), detail.get('invocations', []))
    ledger = raw.get('effect_ledger', [])
    writes = [row for row in ledger if row.get('actual_effect')]
    logical = [row.get('logical_operation') for row in writes]
    attempted = [row.get('attempt', 1) for row in invocations]
    verified = [row for row in steps if row.get('status') == 'verified']
    replay_audit = audit_replays(detail)
    reports = [row['text'] for name, row in raw.get('files', {}).items() if name.startswith('data/workflows/artifacts/')]
    receipt.update(status=detail.get('status'), verified_steps=len(verified), invocation_count=len(invocations), unauthorized_effects=sum((not row.get('authorized') for row in writes)), duplicate_effects=len(logical) - len(set(logical)), write_effect_count=len(writes), report_texts=reports, completed_replayed=replay_audit['count'], replay_audit=replay_audit, max_attempt=max(attempted, default=0), uncertain_count=sum((row.get('state') == 'uncertain' for row in invocations)), restart_count=sum((row.get('operation') == 'restart' for row in raw.get('controls', []))), rejected_controls=sum((row.get('error') is not None for row in raw.get('controls', []))), harness_error=raw.get('harness_error'), intent_scope='controlled outline/binding; original planner validation, not genuine goal understanding', recovery_scope='native service detach/reattach, not a Windows/backend process restart')
    receipt['evidence_categories'].append('MOCK_DEPENDENCY')
    _observation(receipt, 'workflow.run', {'status': detail.get('status')})

def _compute(case, root, receipt):
    from hanni.compute import ComputeRegistry, ComputeScheduler
    from hanni.compute.registry import ComputeError
    protected = root / 'compute'
    protected.mkdir()
    deployment = {'version': 1, 'enabled': True, 'nodes': [{'id': 'c10-node'}], 'workers': [{'worker_id': 'c10-worker', 'node_id': 'c10-node', 'remote_port': 19213, 'model_id': 'c10-controlled-model', 'protocol': 'llama_cpp', 'enabled': True, 'context_configured': 2048, 'allowed_categories': ['synthetic'], 'capabilities': ['analysis', 'structured_json'], 'concurrency': 1}], 'policy': {'timeout_seconds': 1, 'max_retries': 0}}
    (protected / 'deployment.json').write_text(json.dumps(deployment), encoding='utf8', newline='\n')
    clock = [1000.0]
    registry = ComputeRegistry(root, clock=lambda: clock[0])
    target_calls, setup_calls = ([], [])
    cancel = threading.Event()

    class ControlledTransport:
        fault = None
        setup = True

        def health(self, worker):
            return {'status': 'healthy', 'model_id': worker['model_id'], 'last_heartbeat': clock[0], 'context_reported': 2048, 'runtime_identity': 'c10-controlled-runtime'}

        def resources(self, worker):
            return {'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': None, 'resource_sampled_at': clock[0]}

        def request(self, worker, method, path, **options):
            entry = {'worker': worker['worker_id'], 'method': method, 'path': path, 'payload': deepcopy(options.get('payload')), 'scope': 'MOCK_DEPENDENCY, no socket/model'}
            (setup_calls if self.setup else target_calls).append(entry)
            if not self.setup and self.fault == 'disconnect':
                raise ComputeError('Controlled worker connection lost.')
            if not self.setup and self.fault == 'cancel_after':
                cancel.set()
            model = 'other-controlled-model' if self.fault == 'wrong_model' else worker['model_id']
            content = '{"probe":"native-controlled"}' if self.setup else '{"scope":"controlled_dependency"}'
            return {'model': model, 'choices': [{'message': {'content': content}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 1024 if self.setup else 80, 'completion_tokens': 12}}

        def close(self):
            pass

        def cancel(self, **options):
            pass
    transport = ControlledTransport()
    scheduler = ComputeScheduler(registry, transport=transport)
    try:
        proof = scheduler.verify_context('c10-worker', [{'role': 'user', 'content': 'Return the synthetic probe marker.'}], target_tokens=1024, max_output_tokens=32, expected={'probe': 'native-controlled'})
        receipt['bootstrap'] = {'scope': 'native API with MOCK usage/retrieval, not hardware context certification', 'proof': proof, 'transport': setup_calls}
        transport.setup = False
        for action in case['actions']:
            operation, args = (action['operation'], action.get('args', {}))
            if operation == 'compute.withdraw':
                registry.observe('c10-worker', **{args['field']: args['value']})
                data = {'field': args['field'], 'withdrawn': True}
            elif operation == 'compute.refresh':
                scheduler.refresh()
                data = {'workers': registry.snapshot()['workers']}
            elif operation == 'compute.chat':
                transport.fault = args.get('fault')
                cancel.clear()
                if transport.fault == 'cancel_before':
                    cancel.set()
                try:
                    content, job = scheduler.chat([{'role': 'user', 'content': args.get('message', 'Synthetic analysis for a controlled service test.')}], workflow_id='wf_c10_' + case['id'].replace('-', '_'), step_id='analysis', invocation_id='inv_' + uuid4().hex, categories=set(args['categories']), cancellation=cancel, max_tokens=64, temperature=0, max_queue_seconds=0.15, max_retries_override=0)
                    data = {'accepted': True, 'content': content, 'job': job, 'worker': job['worker_id']}
                except (ComputeError, RuntimeError) as error:
                    data = {'accepted': False, 'error_type': type(error).__name__, 'error': str(error)}
            else:
                raise NotImplementedError('Unsupported compute operation: ' + operation)
            _observation(receipt, operation, data)
        receipt.update(active_slots=sum(registry.active.values()), pending_jobs=len(scheduler.queued), target_transport_calls=len(target_calls), target_transport=target_calls, compute_snapshot=registry.snapshot(), model_response_quality='NOT_MEASURED_MOCK_RESPONSE')
    finally:
        scheduler.close()
    receipt['evidence_categories'].append('MOCK_DEPENDENCY')

def _cluster(case, root, receipt):
    from hanni.dashboard.cluster import ClusterMonitor, Node
    mode = case['fixtures']['mode']
    now = time.time()
    nodes = [Node('c10-archive', 'Controlled archive node', '', None, '' + '.'.join(('100', '64', '0', '25')) + '', 'fixture', mode == 'maintenance')]
    calls = []

    def probe(node, peer):
        calls.append({'node': node.id, 'scope': 'MOCK_DEPENDENCY connectivity/telemetry'})
        if mode == 'probe_failure':
            raise OSError('Controlled node unavailable.')
        available = mode in {'fresh', 'stale'}
        return {'status': 'online', 'checked_at': now, 'sampled_at': now - (7 if mode == 'stale' else 0) if available else None, 'metrics': {'cpu_percent': 24, 'ram_percent': 42} if available else None, 'availability_source': 'telemetry' if available else 'tailscale', 'tailscale_online': True, 'address': None, 'connection': None, 'os': None, 'message': 'Controlled telemetry.' if available else 'Authentication unavailable; no hardware observed.'}
    monitor = ClusterMonitor(nodes=nodes, probe=probe, tailnet=lambda: {'state': 'running', 'peers': {}})
    try:
        for action in case['actions']:
            operation = ALIASES.get(action['operation'], action['operation'])
            if operation == 'cluster.sample':
                monitor.sample_once()
                data = {'sampled': True}
            elif operation == 'cluster.snapshot':
                snapshot = monitor.snapshot()
                row = snapshot['nodes'][0]
                data = {'status': row['status'], 'metrics_available': row['metrics'] is not None, 'cpu': row['metrics']['cpu_percent'] if row['metrics'] else None, 'history_count': len(row['history']), 'snapshot': snapshot}
            else:
                raise NotImplementedError('Unsupported cluster operation: ' + operation)
            _observation(receipt, operation, data)
    finally:
        monitor.close()
    receipt.update(probe_calls=len(calls), probe_receipts=calls)
    receipt['evidence_categories'].append('MOCK_DEPENDENCY')

def _voice(case, root, receipt):
    adapter = case['fixtures']['adapter']
    if adapter == 'voice_text':
        from hanni.speech.relevance import SpeechRelevanceClassifier
        classifier = SpeechRelevanceClassifier()
        for action in case['actions']:
            if action['operation'] != 'voice_text.classify':
                raise NotImplementedError('Unsupported text classifier operation.')
            result = classifier.classify(action['args']['text'])
            _observation(receipt, action['operation'], asdict(result))
        receipt['evidence_categories'].append('TEXT_ONLY')
        receipt['intent_scope'] = 'original text classifier; no acoustic wake/STT measurement'
    elif adapter == 'voice_stop':
        from hanni.speech.microphone import MicrophoneCapture
        from scripts.campaign7_voice.controls import CaptureBackend
        stop = threading.Event()
        stop.set()
        backend = CaptureBackend()
        rows = list(MicrophoneCapture(backend=backend).chunks(stop_event=stop, max_chunks=1))
        receipt.update(capture_created=backend.created, capture_entered=backend.entered, emitted_chunks=len(rows))
        receipt['evidence_categories'].append('MOCK_DEPENDENCY')
    elif adapter == 'voice_rate':
        from hanni.speech.stt import FasterWhisperTranscriber
        from hanni.speech.vad import Utterance
        from scripts.campaign7_voice.controls import Decoder
        decoder = Decoder()
        transcriber = FasterWhisperTranscriber(model=decoder)
        try:
            transcriber.transcribe(Utterance(pcm16=b'\x01\x00' * 512, sample_rate=22050, channels=1, started_at=0.0, ended_at=0.1))
        except ValueError as error:
            receipt.update(rejected=True, rejection=str(error))
        else:
            receipt['rejected'] = False
        receipt['decoder_calls'] = len(decoder.calls)
        receipt['evidence_categories'].append('MOCK_DEPENDENCY')
    else:
        raise NotImplementedError('Unsupported voice fixture.')
    receipt['physical_audio'] = 'BLOCKED_USER_DEVICE_UNAVAILABLE'

def _screen(case, root, receipt):
    from hanni.config.loader import load_config
    from hanni.dashboard.features import DesktopFeatures
    from hanni.dashboard.productivity import ProductivityStore
    from tests.helpers import write_config_dir
    from hanni.models.adaptive import AdaptiveModelClient, ModelSelectionError
    from types import SimpleNamespace
    config = load_config(write_config_dir(root / 'config'), data_dir=root / 'data', env={})
    workspace = ProductivityStore(root / 'workspace')
    features = DesktopFeatures(config, store=workspace)
    if case['fixtures'].get('project'):
        workspace.mutate('project.create', {'name': case['fixtures']['project']}, request_id=str(uuid4()))
    calls = []
    for action in case['actions']:
        operation = ALIASES.get(action['operation'], action['operation'])
        if operation == 'screen.awareness':
            raw = features.awareness()
            data = {**raw, 'analyze': raw['actions']['analyze']}
        elif operation == 'screen.project':
            data = {'project_count': len(workspace.snapshot()['projects'])}
        elif operation == 'screen.invalid_image':

            def denied(*args, **kwargs):
                calls.append('denied model-engine leaf')
                raise RuntimeError('No network is allowed in this controlled image contract.')
            client = AdaptiveModelClient(SimpleNamespace(spec=config.models.supervisor), SimpleNamespace(execute=denied))
            try:
                list(client.stream_chat([{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AA=='}}]}]))
            except ModelSelectionError as error:
                data = {'rejected': True, 'error_type': type(error).__name__, 'reason': str(error)}
            else:
                data = {'rejected': False}
        else:
            raise NotImplementedError('Unsupported screen operation: ' + operation)
        _observation(receipt, operation, data)
    receipt.update(transport_calls=len(calls), real_vision='NOT_IMPLEMENTED', screen_capture_calls=0)
    receipt['evidence_categories'].append('NOT_IMPLEMENTED')

def run_case(case, root):
    """No expected fields, oracle file, or private case identity enters dispatch."""
    root = Path(root).resolve()
    if root.exists():
        raise ValueError('Each integration task needs a fresh disposable directory.')
    root.mkdir(parents=True)
    started = time.perf_counter()
    receipt = {'id': case['id'], 'family': case['family'], 'observations': [], 'harness_error': None, 'evidence_categories': ['ISOLATED_IMPLEMENTATION'], 'real_model_requests': 0, 'real_provider_requests': 0, 'physical_audio_calls': 0, 'real_remote_calls': 0, 'model_intent': 'NOT_MEASURED', 'model_tool_selection': 'NOT_MEASURED', 'model_final_response': 'NOT_MEASURED'}
    adapters = {'memory': _memory, 'project': _memory, 'workflow': _workflow, 'compute': _compute, 'cluster': _cluster, 'voice_text': _voice, 'voice_stop': _voice, 'voice_rate': _voice, 'screen': _screen}
    try:
        adapter = case['fixtures'].get('adapter')
        if adapter not in adapters:
            raise NotImplementedError('No original public adapter for this explicit fixture. No default plan substituted.')
        adapters[adapter](case, root, receipt)
    except Exception as error:
        receipt['harness_error'] = {'type': type(error).__name__, 'message': str(error)}
    receipt['elapsed_seconds'] = round(time.perf_counter() - started, 6)
    return receipt

def run_cohort(inputs_path, destination):
    inputs_path, destination = (Path(inputs_path).resolve(), Path(destination).resolve())
    if not destination.is_relative_to(ROOT / 'data/campaign10-systems'):
        raise ValueError('Only the campaign-owned evidence directory is allowed.')
    destination.mkdir(parents=True, exist_ok=False)
    inputs = [json.loads(line) for line in inputs_path.read_text(encoding='utf8').splitlines() if line.strip()]
    before = source_manifest()
    for name in before:
        target = destination / 'source-before' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    for row in inputs:
        if row.get('version') != 1 or not str(row['id']).replace('-', '').isalnum():
            raise ValueError('Invalid bounded input identity.')
    with (destination / 'receipts.jsonl').open('w', encoding='utf8', newline='\n') as stream:
        for row in inputs:
            result = run_case(row, destination / 'cases' / row['id'])
            stream.write(json.dumps(result, ensure_ascii=False) + '\n')
            stream.flush()
            (destination / 'PROGRESS.json').write_text(json.dumps({'last': row['id'], 'completed': sum((1 for _ in (destination / 'receipts.jsonl').open(encoding='utf8')))}) + '\n', encoding='utf8', newline='\n')
    after = source_manifest()
    summary = {'tasks': len(inputs), 'inputs_sha256': hashlib.sha256(inputs_path.read_bytes()).hexdigest(), 'source_before': before, 'source_after': after, 'source_unchanged': before == after, 'real_model_requests': 0, 'real_provider_requests': 0, 'raw_receipts': 'receipts.jsonl'}
    (destination / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8', newline='\n')
    return summary
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run_cohort(args.inputs, args.output)
    print(json.dumps({key: result[key] for key in ('tasks', 'source_unchanged', 'real_model_requests')}))
