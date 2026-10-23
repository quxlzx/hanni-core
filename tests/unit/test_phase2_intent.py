"""Deterministic contract/recovery tests, NOT live-model or provider success."""
import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.tools.registry import build_default_registry
from hanni.workflows.intent import propose
from hanni.workflows.planner import WorkflowPlanner
from hanni.workflows.service import WorkflowService
from hanni.workflows.types import WorkflowError
from tests.helpers import write_config_dir

class Client:

    def __init__(self, rows):
        self.rows, self.calls = (rows, 0)

    def chat(self, *args, **kwargs):
        self.calls += 1
        return json.dumps({'summary': 'Perform the requested fixture operations.', 'unsupported_reason': None, 'steps': self.rows})

def tool(name, arguments, inputs=()):
    return {'description': name + ' registered operation', 'kind': 'tool', 'capability_id': name, 'arguments': arguments}

def analysis():
    return {'description': 'Present cited facts.', 'kind': 'analysis', 'capability_id': None, 'arguments': {}}

def artifact(name='report.txt'):
    return {'description': 'Save checked facts.', 'kind': 'artifact', 'capability_id': None, 'arguments': {'name': name}}

@pytest.fixture
def host(tmp_path):
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    return McpHost(build_default_registry(config), read_only=True)

def compile(host, tmp_path, goal, rows):
    return propose(WorkflowPlanner(host, Client(rows)), goal, mode='supervised', artifact_root=tmp_path / 'artifacts')

def test_exact_owner_path_and_controller_owned_refs(host, tmp_path):
    source = tmp_path / 'Owner folder' / 'full notes.txt'
    plan = compile(host, tmp_path, 'Read "' + str(source) + '" and save a report.', [tool('file.read', {'path': str(source)}), analysis(), artifact()])
    assert [s['step_id'] for s in plan['steps']] == ['s01', 's02', 's03']
    assert plan['steps'][2]['arguments']['text'] == {'$ref': {'step_id': 's02', 'path': '/data/text', 'type': 'string'}}
    assert plan['steps'][0]['arguments']['path'] == str(source)

def test_shortened_path_is_rejected(host, tmp_path):
    with pytest.raises(WorkflowError, match='original explicit owner source'):
        compile(host, tmp_path, 'Read "' + str(tmp_path / 'Long owner folder' / 'notes.txt') + '"', [tool('file.read', {'path': str(tmp_path / 'notes.txt')})])

def test_missing_report_cannot_claim_completion(host, tmp_path):
    source = tmp_path / 'notes.txt'
    with pytest.raises(WorkflowError, match='omitted'):
        compile(host, tmp_path, 'Read "' + str(source) + '" and save a report.', [tool('file.read', {'path': str(source)}), analysis()])

@pytest.mark.parametrize('name', ['../escape.txt', 'report.py', '..\\escape.txt', 'C:\\escape.txt'])
def test_artifact_scope_is_bounded(host, tmp_path, name):
    with pytest.raises(WorkflowError):
        compile(host, tmp_path, 'Inspect CPU and RAM and save a report.', [tool('system.stats', {}), analysis(), artifact(name)])

def test_forward_reference_fails_before_any_execution(host, tmp_path):
    with pytest.raises(WorkflowError, match='preceding'):
        compile(host, tmp_path, 'Read files in "' + str(tmp_path) + '"', [tool('file.read', {}, [{'argument': 'path', 'step': 1, 'field': 'unique_path'}])])

def op(service, operation, **data):
    return service.mutate({'id': str(uuid4()), 'operation': operation, 'data': data})

def test_saved_report_actual_contents_and_original_confirmations(host, tmp_path):
    source = tmp_path / 'notes.txt'
    source.write_text('Independent fixture value: 42.', encoding='utf-8')
    client = Client([tool('file.read', {'path': str(source)}), analysis(), artifact()])
    service = WorkflowService(tmp_path / 'controller', planning_contract='intent')
    service.attach(host.registry, client, host=host, resource_probe=lambda: {'allowed': True, 'ram_percent': 20, 'gpu': None})
    service.start()
    try:
        key = op(service, 'goal.submit', goal='Read "' + str(source) + '" and save a report.', mode='supervised')['workflow_id']
        detail = service.wait(key)
        assert detail['status'] == 'awaiting_step_approval', detail
        assert not list(service.artifacts_root.rglob('report.txt'))
        grant = next((a for a in detail['approvals'] if a['kind'] == 'action' and a['state'] == 'pending'))
        op(service, 'approve_step', workflow_id=key, expected_revision=detail['revision'], **{k: grant[k] for k in ('step_id', 'approval_id', 'plan_hash', 'argument_hash', 'definition_hash')})
        detail = service.wait(key)
        assert detail['status'] == 'completed', detail
        saved = detail['steps'][-1]['resolved_arguments']
        actual = json.loads(Path(saved['path']).read_text(encoding='utf-8'))
        assert any((o['value'] == source.read_text() for o in actual['observations']))
        assert len([i for i in detail['invocations'] if i['write']]) == 1
        assert client.calls == 1
    finally:
        service.close()

def test_invalid_proposal_retries_at_most_twice(host, tmp_path):
    client = Client([analysis()])
    service = WorkflowService(tmp_path / 'controller', planning_contract='intent')
    service.attach(host.registry, client, host=host, resource_probe=lambda: {'allowed': True, 'ram_percent': 20, 'gpu': None})
    service.start()
    try:
        key = op(service, 'goal.submit', goal='Inspect current CPU and RAM.', mode='supervised')['workflow_id']
        detail = service.wait(key)
        assert detail['status'] == 'blocked'
        assert client.calls == detail['planning_attempts'] == 2
        assert not detail['invocations']
    finally:
        service.close()

def test_locate_reference_requires_one_actual_match(host, tmp_path):
    root = tmp_path / 'owner'
    root.mkdir()
    rows = [tool('file.locate', {'root': str(root), 'name': 'notes.txt'}), tool('file.read', {})]
    plan = compile(host, tmp_path, 'Locate notes.txt only under "' + str(root) + '" and read it.', rows)
    assert plan['steps'][0]['criteria'] == [{'operator': 'count_equals', 'path': '/data/matches', 'expected': 1}]
    assert plan['steps'][1]['arguments']['path']['$ref']['step_id'] == 's01'

def test_ambiguous_actual_discovery_never_dispatches_the_read(host, tmp_path):
    root = tmp_path / 'owner'
    root.mkdir()
    for folder in ('first', 'second'):
        child = root / folder
        child.mkdir()
        (child / 'notes.txt').write_text(folder)
    client = Client([tool('file.locate', {'root': str(root), 'name': 'notes.txt'}), tool('file.read', {})])
    service = WorkflowService(tmp_path / 'controller', planning_contract='intent')
    service.attach(host.registry, client, host=host, resource_probe=lambda: {'allowed': True, 'ram_percent': 20, 'gpu': None})
    service.start()
    try:
        key = op(service, 'goal.submit', goal='Locate notes.txt only under "' + str(root) + '" and read it.', mode='supervised')['workflow_id']
        detail = service.wait(key)
        assert detail['status'] == 'partially_completed', detail
        assert len(detail['steps'][0]['result']['data']['matches']) == 2
        assert detail['steps'][0]['verification']['status'] == 'UNVERIFIED'
        assert not any((i['capability_id'] == 'file.read' for i in detail['invocations']))
    finally:
        service.close()

def test_changed_source_blocks_report_at_real_dispatch_boundary(host, tmp_path):
    source = tmp_path / 'notes.txt'
    source.write_text('observed version one')
    service = WorkflowService(tmp_path / 'controller', planning_contract='intent')
    service.attach(host.registry, Client([tool('file.read', {'path': str(source)}), analysis(), artifact()]), host=host, resource_probe=lambda: {'allowed': True, 'ram_percent': 20, 'gpu': None})
    service.start()
    try:
        key = op(service, 'goal.submit', goal='Read "' + str(source) + '" and save a report.', mode='supervised')['workflow_id']
        detail = service.wait(key)
        assert detail['status'] == 'awaiting_step_approval'
        source.write_text('changed version two')
        grant = next((a for a in detail['approvals'] if a['kind'] == 'action' and a['state'] == 'pending'))
        op(service, 'approve_step', workflow_id=key, expected_revision=detail['revision'], **{k: grant[k] for k in ('step_id', 'approval_id', 'plan_hash', 'argument_hash', 'definition_hash')})
        detail = service.wait(key)
        assert detail['status'] == 'blocked'
        assert len([i for i in detail['invocations'] if i['write']]) == 1
        assert not list(service.artifacts_root.rglob('report.txt'))
        assert detail['steps'][-1]['result']['ok'] is False
    finally:
        service.close()

def test_replan_preserves_verified_receipt_and_read_retry_budget(host, tmp_path):
    original = host.registry.get('process.top_cpu')
    calls = []

    def failing_once(arguments, context, request):
        calls.append(1)
        if len(calls) == 1:
            from hanni.tools.base import ToolResult
            return ToolResult('process.top_cpu', False, 'Actual fixture failure', {})
        return original.handler(arguments, context, request)
    host.registry.unregister(original.name, expected=original)
    host.registry.register(replace(original, handler=failing_once, retry_safe=True))

    class ReplanningClient(Client):

        def chat(self, *args, **kwargs):
            self.rows = [tool('system.stats', {}), tool('process.top_cpu', {'limit': 3})] if self.calls == 0 else [tool('process.top_cpu', {'limit': 3})]
            return super().chat(*args, **kwargs)
    client = ReplanningClient([])
    service = WorkflowService(tmp_path / 'controller', planning_contract='intent')
    service.attach(host.registry, client, host=host, resource_probe=lambda: {'allowed': True, 'ram_percent': 20, 'gpu': None})
    service.start()
    try:
        key = op(service, 'goal.submit', goal='Inspect CPU and RAM and list processes using most CPU.', mode='supervised')['workflow_id']
        detail = service.wait(key)
        assert detail['status'] == 'completed', detail
        assert client.calls == 2 and len(calls) == 2
        assert len([i for i in detail['invocations'] if i['capability_id'] == 'system.stats']) == 1
        assert any((c['kind'] == 'bounded_read_replan' for c in detail['checkpoints']))
        assert detail['steps'][0]['step_id'] == 's01' and detail['steps'][0]['status'] == 'verified'
    finally:
        service.close()

def test_uncertain_write_acknowledgment_is_not_replanned_or_repeated(host, tmp_path):
    source = tmp_path / 'notes.txt'
    source.write_text('fixture observation')
    original = host.registry.get('file.write')
    calls = []

    def lost_ack(arguments, context, request):
        calls.append(1)
        original.handler(arguments, context, request)
        raise TimeoutError('Fixture lost acknowledgment after actual write')
    host.registry.unregister(original.name, expected=original)
    host.registry.register(replace(original, handler=lost_ack))
    client = Client([tool('file.read', {'path': str(source)}), analysis(), artifact()])
    service = WorkflowService(tmp_path / 'controller', planning_contract='intent')
    service.attach(host.registry, client, host=host, resource_probe=lambda: {'allowed': True, 'ram_percent': 20, 'gpu': None})
    service.start()
    try:
        key = op(service, 'goal.submit', goal='Read "' + str(source) + '" and save a report.', mode='assisted')['workflow_id']
        detail = service.wait(key)
        op(service, 'approve_plan', workflow_id=key, expected_revision=detail['revision'], plan_hash=detail['plan_hash'])
        detail = service.detail(key)
        op(service, 'start', workflow_id=key, expected_revision=detail['revision'], plan_hash=detail['plan_hash'])
        detail = service.wait(key)
        assert detail['status'] == 'blocked' and calls == [1] and (client.calls == 1)
        assert len(list(service.artifacts_root.rglob('report.txt'))) == 1
        with pytest.raises(WorkflowError):
            op(service, 'retry_safe', workflow_id=key, expected_revision=detail['revision'], step_id=detail['steps'][-1]['step_id'])
    finally:
        service.close()
