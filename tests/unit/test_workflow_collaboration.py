"""Original V3 workflow, actual local file results, fenced model telemetry."""
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace
from uuid import uuid4
import pytest
from hanni.mcp.host import McpHost
from hanni.tools.registry import build_default_registry
from hanni.workflows.service import WorkflowService
from hanni.workflows.store import WorkflowStore
from hanni.workflows.types import LeaseLost, WorkflowError
from tests.unit.test_adaptive_model_routing import engine
from tests.unit.test_model_collaboration import prove
from tests.unit.test_model_collaboration import grade
from tests.unit.test_workflow_store import Clock

@pytest.fixture
def controller(engine, tmp_path, monkeypatch):
    source = tmp_path / 'observed.txt'
    source.write_text('actual original source', encoding='utf-8')
    second = tmp_path / 'second.txt'
    second.write_text('second original source', encoding='utf-8')
    flags = {'two_sources': False}
    spec = replace(engine.config.models.supervisor, context_length=32768)
    engine.config = replace(engine.config, models=replace(engine.config.models, models=(spec,)))
    engine.local_probe = lambda row: {'status': 'healthy', 'model_id': row['configured_model'], 'context_reported': 32768, 'last_heartbeat': 1000, 'runtime_identity': 'workflow-fixture-local', 'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': 1024 ** 3}
    engine.refresh()
    for key in ('local:supervisor', 'worker:fixture'):
        prove(engine, key)
    engine.record_capability_evidence('local:supervisor', identity=engine.endpoint_identity('local:supervisor'), capabilities=['text', 'structured_json'], context_tokens=32768, observed_prompt_tokens=30000, retrieval_passed=True, evidence_sha256='c' * 64, environment='controlled larger workflow grammar context', metadata={'structured_output_formats': ['json_object', 'json_schema']})
    calls = []

    def local(self, messages, **options):
        data = json.loads(messages[1]['content'])
        usage = options.get('usage', getattr(self, '_inference_usage', None))
        if usage is not None:
            usage.update(prompt_tokens=50, completion_tokens=30, total_tokens=80)
        if 'sources' in data:
            return json.dumps({'observations': [{'operation': 'value', 'sources': [{'step_id': name, 'path': '/data/text', 'json_path': None}], 'value': result['data']['text']} for name, result in data['sources'].items()]})
        calls.append(1)
        if len(calls) % 2:
            plan = {'summary': 'Read actual source and verify its factual observation.', 'unsupported_reason': None, 'steps': [{'step_id': 'read', 'description': 'Read text file ' + str(source), 'kind': 'tool', 'dependencies': [], 'required': True, 'criteria': [{'operator': 'equals', 'path': '/data/text', 'expected': 'actual original source'}]}, {'step_id': 'report', 'description': 'Report the exact source value.', 'kind': 'analysis', 'dependencies': ['read'], 'required': True, 'criteria': [{'operator': 'evidence_report', 'path': '/data/report', 'expected': None}]}]}
            if flags['two_sources']:
                plan['steps'].insert(1, {'step_id': 'read2', 'description': 'Read text file ' + str(second), 'kind': 'tool', 'dependencies': [], 'required': True, 'criteria': [{'operator': 'equals', 'path': '/data/text', 'expected': 'second original source'}]})
                plan['steps'][-1]['dependencies'].append('read2')
            return json.dumps(plan)
        binding = {'unsupported_reason': None, 'steps': [{'step_id': 'read', 'capability_id': 'file.read', 'arguments': {'path': str(source)}}, {'step_id': 'report', 'capability_id': None, 'arguments': {'sources': ['read']}}]}
        if flags['two_sources']:
            binding['steps'].insert(1, {'step_id': 'read2', 'capability_id': 'file.read', 'arguments': {'path': str(second)}})
            binding['steps'][-1]['arguments']['sources'].append('read2')
        return json.dumps(binding)
    monkeypatch.setattr('hanni.models.adaptive._BoundedInferenceClient.chat', local)
    registry = build_default_registry(engine.config)
    host = McpHost(registry, read_only=True)
    client = engine.wrap_client(SimpleNamespace(spec=engine.config.models.supervisor))
    service = WorkflowService(tmp_path)
    service.fixture_flags = flags
    service.fixture_paths = (source, second)
    service.attach(registry, client, host=host, compute_scheduler=engine.compute, resource_probe=lambda: {'allowed': True, 'ram_percent': 20.0})
    service.start()
    yield (service, engine)
    service.close()
    registry.context.reliability.close()

def operation(service, name, data):
    return service.mutate({'id': str(uuid4()), 'operation': name, 'data': data})

@pytest.mark.parametrize('preference', ['parallel', 'review', 'specialists'])
def test_original_workflow_reads_verifies_and_checkpoints_private_single_fallback(controller, preference):
    service, engine = controller
    key = operation(service, 'goal.submit', {'goal': 'Read actual local source and report its exact value.', 'mode': 'assisted', 'collaboration': preference})['workflow_id']
    detail = service.wait(key)
    assert detail['status'] == 'awaiting_plan_approval', (detail.get('error'), [(row['status'], row['reason'], row['required_context_tokens'], row['excluded']) for row in engine.snapshot()['decisions']])
    operation(service, 'approve_plan', {'workflow_id': key, 'expected_revision': detail['revision'], 'plan_hash': detail['plan_hash']})
    detail = service.detail(key)
    operation(service, 'start', {'workflow_id': key, 'expected_revision': detail['revision'], 'plan_hash': detail['plan_hash']})
    detail = service.wait(key)
    assert detail['status'] == 'completed', detail.get('error')
    assert detail['collaboration'] == preference
    assert detail['steps'][0]['verification']['status'] == 'VERIFIED'
    report = detail['steps'][1]
    assert report['verification']['scope'] == 'cited_observations_and_calculations'
    assert report['collaboration']['effective_pattern'] == 'single'
    assert report['collaboration']['participants'][0]['tokens']['completion_tokens'] == 30
    assert report['collaboration']['context_refs'][0]['step_id'] == 'read'
    assert 'selected_output' not in report['collaboration']
    assert report['collaboration']['participants'][0]['output']
    assert engine.compute.transport.calls == []
    assert len(detail['invocations']) == 2
    assert any((row['kind'] == 'collaboration_progress' for row in detail['checkpoints']))
    persisted = WorkflowStore(service.root)
    try:
        assert persisted.steps(key)[1]['collaboration'] == report['collaboration']
    finally:
        persisted.close()

def test_ordinary_auto_workflow_retains_original_dispatch_count_and_no_comparison(controller):
    service, engine = controller
    key = operation(service, 'goal.submit', {'goal': 'Read source and report its value.', 'mode': 'supervised'})['workflow_id']
    detail = service.wait(key)
    assert detail['status'] == 'completed', detail
    assert 'collaboration' not in detail['steps'][1]
    assert engine.compute.transport.calls == []
    assert len(detail['invocations']) == 2

@pytest.mark.parametrize('preference', [[], {}, None, 'model-authorized'])
def test_untrusted_or_unknown_preference_is_rejected(controller, preference):
    service, _ = controller
    with pytest.raises(WorkflowError):
        operation(service, 'goal.submit', {'goal': 'x', 'mode': 'assisted', 'collaboration': preference})

def started_store(tmp_path):
    clock = Clock()
    store = WorkflowStore(tmp_path, clock=clock)
    lease = store.claim(str(uuid4()))
    record = store.create('Original approved analysis', 'assisted', collaboration='parallel')
    step = {'step_id': 'analysis', 'kind': 'analysis', 'description': 'Read checked evidence', 'dependencies': [], 'capability_id': None, 'definition_hash': None, 'arguments': {'sources': []}, 'criteria': []}
    record = store.save_plan(record['workflow_id'], record['revision'], {'steps': [step]}, [step], lease=lease)
    record = store.update(record['workflow_id'], record['revision'], {'status': 'ready'})
    invocation, record = store.begin_invocation(record['workflow_id'], record['revision'], 'analysis', lease=lease, arguments={'sources': []}, definition_hash=None, write=False, retry_safe=False)
    return (store, clock, lease, invocation, record)

def test_partial_progress_persists_without_completion_and_recovery_never_replays(tmp_path):
    store, clock, lease, invocation, record = started_store(tmp_path)
    progress = {'state': 'running', 'participants': [{'participant_id': 'analysis_1', 'state': 'completed', 'output': 'exact source'}, {'participant_id': 'analysis_2', 'state': 'running', 'output': None}]}
    store.record_collaboration(invocation['invocation_id'], progress, lease=lease)
    key = record['workflow_id']
    assert store.steps(key)[0]['status'] == 'running'
    assert store.get(key)['invocation_count'] == 1
    store.release(lease)
    next_lease = store.claim(str(uuid4()))
    store.recover(next_lease)
    step = store.steps(key)[0]
    assert step['status'] == 'blocked' and step['collaboration']['state'] == 'interrupted'
    assert step['collaboration']['participants'][0]['output'] == 'exact source'
    assert step['collaboration']['participants'][1]['state'] == 'interrupted'
    assert store.history(key)['invocations'][0]['state'] == 'abandoned'
    assert store.history(key)['invocations'][0]['collaboration']['state'] == 'interrupted'
    assert store.history(key)['invocations'][0]['collaboration']['participants'][1]['state'] == 'interrupted'
    with pytest.raises(LeaseLost):
        store.record_collaboration(invocation['invocation_id'], progress, lease=lease)
    assert store.get(key)['invocation_count'] == 1
    store.close()

def test_collaboration_preference_is_immutable_and_progress_cannot_finish_step(tmp_path):
    store, clock, lease, invocation, record = started_store(tmp_path)
    with pytest.raises(WorkflowError):
        store.update(record['workflow_id'], record['revision'], {'collaboration': 'single'})
    store.record_collaboration(invocation['invocation_id'], {'state': 'completed', 'participants': [], 'final_verification': {'status': 'VERIFIED'}}, lease=lease)
    assert store.steps(record['workflow_id'])[0]['status'] == 'running'
    assert store.get(record['workflow_id'])['status'] == 'running'
    store.close()

def test_authoritative_specialist_source_groups_merge_only_independently_checked_reports(controller):
    service, engine = controller
    service.fixture_flags['two_sources'] = True
    secondary = replace(engine.config.models.supervisor, id='fixture-secondary', api_model='fixture-secondary')
    engine.config = replace(engine.config, models=replace(engine.config.models, models=(*engine.config.models.models, secondary)))
    engine.refresh()
    engine.record_capability_evidence('local:fixture-secondary', identity=engine.endpoint_identity('local:fixture-secondary'), capabilities=['text', 'structured_json'], context_tokens=32768, observed_prompt_tokens=30000, retrieval_passed=True, evidence_sha256='f' * 64, environment='controlled synthetic independent endpoint', metadata={'structured_output_formats': ['json_schema', 'json_object']})
    for endpoint in ('local:supervisor', 'local:fixture-secondary'):
        grade(engine, endpoint, 'analysis')
    goal = 'Read text files ' + str(service.fixture_paths[0]) + ' and ' + str(service.fixture_paths[1]) + ' and report their exact values.'
    key = operation(service, 'goal.submit', {'goal': goal, 'mode': 'supervised', 'collaboration': 'specialists'})['workflow_id']
    detail = service.wait(key)
    assert detail['status'] == 'completed', detail.get('error')
    report = detail['steps'][-1]
    assert report['collaboration']['effective_pattern'] == 'specialists'
    assert len(report['collaboration']['participants']) == 2
    assert {item['endpoint_id'] for item in report['collaboration']['participants']} == {'local:supervisor', 'local:fixture-secondary'}
    assert {item['value'] for item in report['result']['data']['report']['observations']} == {'actual original source', 'second original source'}
    assert report['verification']['status'] == 'VERIFIED'
    assert report['verification']['scope'] == 'cited_observations_and_calculations'
    assert len(detail['invocations']) == 3
    assert engine.compute.transport.calls == []
    assert all((item['assignment_evidence']['correctness_sample_count'] == 30 for item in report['collaboration']['participants']))
