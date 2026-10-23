"""Development engine checks using genuine original registry and isolated files."""
import json
from dataclasses import replace
from pathlib import Path
import threading
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.tools.registry import build_default_registry
from hanni.workflows import WorkflowService
from hanni.workflows.types import WorkflowError
from tests.helpers import write_config_dir

class PlanClient:

    def __init__(self, source):
        self.source = str(source)
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return json.dumps({'summary': 'Read the explicitly requested local text.', 'unsupported_reason': None, 'steps': [{'step_id': 'read', 'description': 'Read the text file ' + self.source, 'kind': 'tool', 'dependencies': [], 'required': True, 'criteria': [{'operator': 'equals', 'path': '/data/text', 'expected': 'actual isolated evidence'}]}]})
        return json.dumps({'unsupported_reason': None, 'steps': [{'step_id': 'read', 'capability_id': 'file.read', 'arguments': {'path': self.source}}]})

@pytest.fixture
def service(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('actual isolated evidence', encoding='utf-8')
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    registry = build_default_registry(config)
    host = McpHost(registry, read_only=True)
    service = WorkflowService(tmp_path / 'data', protected_roots=(tmp_path / 'config',))
    service.attach(registry, PlanClient(source), host=host, resource_probe=lambda: {'allowed': True, 'ram_percent': 20.0, 'gpu': None})
    service.start()
    yield service
    service.close()

def operation(service, name, data, request_id=None):
    return service.mutate({'id': request_id or str(uuid4()), 'operation': name, 'data': data})

def submit(service):
    key = operation(service, 'goal.submit', {'goal': 'Read the local text file ' + service.client.source, 'mode': 'assisted'})['workflow_id']
    detail = service.wait(key)
    assert detail['status'] == 'awaiting_plan_approval', detail
    return (key, detail)

def test_real_plan_review_start_and_original_read_completion(service):
    key, detail = submit(service)
    assert not detail['controls']['start']['enabled']
    assert service.client.calls == 2
    operation(service, 'approve_plan', {'workflow_id': key, 'expected_revision': detail['revision'], 'plan_hash': detail['plan_hash']})
    detail = service.detail(key)
    assert detail['status'] == 'ready'
    assert detail['controls']['start']['enabled']
    operation(service, 'start', {'workflow_id': key, 'expected_revision': detail['revision'], 'plan_hash': detail['plan_hash']})
    detail = service.wait(key)
    assert detail['status'] == 'completed', detail
    assert detail['counts']['verified'] == 1
    assert detail['steps'][0]['result']['data']['text'] == 'actual isolated evidence'
    assert detail['steps'][0]['verification']['status'] == 'VERIFIED'
    assert len(detail['invocations']) == 1
    assert detail['invocations'][0]['state'] == 'finished'

def test_goal_request_replay_is_durable_without_second_workflow(service):
    request_id = str(uuid4())
    data = {'goal': 'Read the local text file ' + service.client.source, 'mode': 'assisted'}
    first = operation(service, 'goal.submit', data, request_id)
    assert operation(service, 'goal.submit', data, request_id) == first
    assert len(service.snapshot()) == 1
    with pytest.raises(WorkflowError):
        operation(service, 'goal.submit', dict(data, goal='different objective'), request_id)

def test_stale_plan_review_and_cold_controller_never_admit(service):
    key, detail = submit(service)
    operation(service, 'pause', {'workflow_id': key, 'expected_revision': detail['revision']})
    with pytest.raises(WorkflowError):
        operation(service, 'approve_plan', {'workflow_id': key, 'expected_revision': detail['revision'], 'plan_hash': detail['plan_hash']})
    service.detach()
    assert not service.detail(key)['controls']['cancel']['enabled']
    assert not service.detail(key)['invocations']

def approve_start(service, key, detail):
    operation(service, 'approve_plan', {'workflow_id': key, 'expected_revision': detail['revision'], 'plan_hash': detail['plan_hash']})
    detail = service.detail(key)
    operation(service, 'start', {'workflow_id': key, 'expected_revision': detail['revision'], 'plan_hash': detail['plan_hash']})

def install(service, name, handler, **changes):
    original = service.registry.get(name)
    service.registry.unregister(name, expected=original)
    service.registry.register(replace(original, handler=handler, **changes))
    return original

def test_cancel_waits_for_real_synchronous_handler_return(service):
    entered, released = (threading.Event(), threading.Event())
    original = service.registry.get('file.read')

    def slow(arguments, context, request):
        entered.set()
        assert released.wait(5)
        return original.handler(arguments, context, request)
    install(service, 'file.read', slow)
    key, detail = submit(service)
    approve_start(service, key, detail)
    assert entered.wait(3)
    detail = service.detail(key)
    operation(service, 'cancel', {'workflow_id': key, 'expected_revision': detail['revision']})
    detail = service.detail(key)
    assert detail['cancel_requested'] and detail['active_uninterruptible']
    assert detail['status'] == 'running'
    released.set()
    detail = service.wait(key)
    assert detail['status'] == 'cancelled'
    assert not detail['active_uninterruptible']
    assert len(detail['invocations']) == 1

def test_safe_read_timeout_retries_once_with_durable_backoff(service):
    attempts = []
    original = service.registry.get('file.read')

    def transient(arguments, context, request):
        attempts.append(1)
        if len(attempts) == 1:
            raise TimeoutError('isolated transient read')
        return original.handler(arguments, context, request)
    install(service, 'file.read', transient, retry_safe=True)
    key, detail = submit(service)
    approve_start(service, key, detail)
    detail = service.wait(key)
    assert detail['status'] == 'completed', detail
    assert len(attempts) == len(detail['invocations']) == 2
    assert detail['steps'][0]['attempts'] == 2
    assert any((item['kind'] == 'retry_scheduled' for item in detail['checkpoints']))
    times = [item['started_at'] for item in detail['invocations']]
    from hanni.workflows.service import _epoch
    assert _epoch(times[1]) - _epoch(times[0]) >= 2

def test_revoked_plan_never_dispatches_read(service):
    key, detail = submit(service)
    operation(service, 'approve_plan', {'workflow_id': key, 'expected_revision': detail['revision'], 'plan_hash': detail['plan_hash']})
    detail = service.detail(key)
    approval = next((item for item in detail['approvals'] if item['kind'] == 'plan'))
    operation(service, 'revoke', {'workflow_id': key, 'expected_revision': detail['revision'], 'approval_id': approval['approval_id']})
    detail = service.detail(key)
    assert detail['status'] == 'paused'
    assert not detail['invocations']
    operation(service, 'resume', {'workflow_id': key, 'expected_revision': detail['revision']})
    detail = service.detail(key)
    assert detail['status'] == 'awaiting_plan_approval' and detail['scope'] is None
    assert not detail['invocations']
    assert any((item['kind'] == 'plan' and item['state'] == 'pending' and (item['approval_id'] != approval['approval_id']) for item in detail['approvals']))

def test_changed_stateful_handler_invalidates_review(service):
    key, detail = submit(service)
    original = service.registry.get('file.read')

    def changed(arguments, context, request):
        return original.handler(arguments, context, request)
    install(service, 'file.read', changed)
    with pytest.raises(WorkflowError):
        operation(service, 'approve_plan', {'workflow_id': key, 'expected_revision': detail['revision'], 'plan_hash': detail['plan_hash']})
    assert not service.detail(key)['invocations']

class ArtifactClient:
    """Shared deterministic planner seam; actual file handlers remain original."""

    def __init__(self, source, *, personal_path=None):
        self.source, self.personal_path, self.calls = (str(source), personal_path, 0)

    def chat(self, messages, **kwargs):
        self.calls += 1
        data = json.loads(messages[1]['content'])
        if self.calls == 1:
            return json.dumps({'summary': 'Read the supplied text and preserve its actual contents.', 'unsupported_reason': None, 'steps': [{'step_id': 'read', 'description': 'Read text file ' + self.source, 'kind': 'tool', 'dependencies': [], 'required': True, 'criteria': [{'operator': 'equals', 'path': '/data/text', 'expected': 'actual isolated evidence'}]}, {'step_id': 'save', 'description': 'Save the verified supplied text as a report.', 'kind': 'artifact', 'dependencies': ['read'], 'required': True, 'criteria': [{'operator': 'present', 'path': '/data/path', 'expected': None}]}]})
        self.destination = str(self.personal_path or Path(data['artifact_root']) / 'report.txt')
        return json.dumps({'unsupported_reason': None, 'steps': [{'step_id': 'read', 'capability_id': 'file.read', 'arguments': {'path': self.source}}, {'step_id': 'save', 'capability_id': 'file.write', 'arguments': {'path': self.destination, 'text': {'$ref': {'step_id': 'read', 'path': '/data/text', 'type': 'string'}}}}]})

def artifact_submit(service, *, personal_path=None):
    service.client = ArtifactClient(service.client.source, personal_path=personal_path)
    key = operation(service, 'goal.submit', {'goal': 'Read the text file ' + service.client.source + ' and save its verified contents.', 'mode': 'assisted'})['workflow_id']
    detail = service.wait(key)
    assert detail['status'] == 'awaiting_plan_approval', detail
    approve_start(service, key, detail)
    return key

def test_real_typed_reference_artifact_write_with_independent_readback(service):
    key = artifact_submit(service)
    detail = service.wait(key)
    assert detail['status'] == 'completed', detail
    assert Path(service.client.destination).read_text(encoding='utf-8') == 'actual isolated evidence'
    assert detail['counts']['verified'] == 2
    assert len(detail['invocations']) == 2
    assert detail['steps'][1]['resolved_arguments']['text'] == 'actual isolated evidence'
    assert detail['artifacts'][0]['verified'] is True

def test_shared_artifact_budget_refuses_original_write_handler(service):
    service.limits = replace(service.limits, max_artifact_bytes=10)
    key = artifact_submit(service)
    detail = service.wait(key)
    assert detail['status'] == 'blocked'
    assert not Path(service.client.destination).exists()
    assert len(detail['invocations']) == 1

def test_sensitive_personal_write_requires_exact_rejectable_action_review(service, tmp_path):
    service.host.allowed_actions = tuple((*service.host.allowed_actions, 'file.write'))
    destination = tmp_path / 'explicit-personal-report.txt'
    key = artifact_submit(service, personal_path=destination)
    detail = service.wait(key)
    assert detail['status'] == 'awaiting_step_approval', detail
    assert not destination.exists()
    step = next((item for item in detail['steps'] if item['step_id'] == 'save'))
    approval = next((item for item in detail['approvals'] if item['kind'] == 'action'))
    assert step['resolved_arguments']['text'] == 'actual isolated evidence'
    operation(service, 'reject', {'workflow_id': key, 'expected_revision': detail['revision'], 'step_id': 'save', 'approval_id': approval['approval_id'], 'plan_hash': approval['plan_hash'], 'argument_hash': approval['argument_hash'], 'definition_hash': approval['definition_hash']})
    assert service.detail(key)['status'] == 'blocked'
    assert not destination.exists()

def test_missing_resource_probe_never_starts_planning(service):
    service.resource_probe = None
    key = operation(service, 'goal.submit', {'goal': 'Read ' + service.client.source, 'mode': 'assisted'})['workflow_id']
    with pytest.raises(TimeoutError):
        service.wait(key, timeout=0.15)
    assert service.client.calls == 0
    assert service.detail(key)['status'] == 'submitted'

@pytest.mark.parametrize('mode', ['assisted', 'background'])
def test_assisted_and_background_modes_wait_for_explicit_plan_review(service, mode):
    key = operation(service, 'goal.submit', {'goal': 'Read text file ' + service.client.source, 'mode': mode})['workflow_id']
    detail = service.wait(key)
    assert detail['status'] == 'awaiting_plan_approval'
    assert not detail['invocations'] and detail.get('scope') is None

def test_supervised_owner_submission_automatically_executes_only_known_reads(service):
    key = operation(service, 'goal.submit', {'goal': 'Read text file ' + service.client.source, 'mode': 'supervised'})['workflow_id']
    detail = service.wait(key)
    assert detail['status'] == 'completed', detail
    assert detail['scope']['provenance'] == 'owner_supervised_submission'
    assert detail['scope']['capabilities'] == ['file.read']
    assert len(detail['invocations']) == 1

def test_supervised_artifact_always_waits_for_exact_sensitive_action_review(service):
    service.client = ArtifactClient(service.client.source)
    key = operation(service, 'goal.submit', {'goal': 'Read the text file ' + service.client.source + ' and save its contents.', 'mode': 'supervised'})['workflow_id']
    detail = service.wait(key)
    assert detail['status'] == 'awaiting_step_approval', detail
    assert len(detail['invocations']) == 1
    assert not Path(service.client.destination).exists()
    assert 'file.write' not in detail['scope']['capabilities']
    approval = next((item for item in detail['approvals'] if item['kind'] == 'action'))
    operation(service, 'approve_step', {'workflow_id': key, 'expected_revision': detail['revision'], 'step_id': 'save', 'approval_id': approval['approval_id'], 'plan_hash': approval['plan_hash'], 'argument_hash': approval['argument_hash'], 'definition_hash': approval['definition_hash']})
    detail = service.wait(key)
    assert detail['status'] == 'completed', detail
    assert Path(service.client.destination).read_text() == 'actual isolated evidence'

def test_clearing_emergency_stop_does_not_resume_queued_work(service):
    from hanni.core.identity import Actor
    from hanni.core.shutdown import StopSource
    service.resource_probe = None
    key = operation(service, 'goal.submit', {'goal': 'Read text file ' + service.client.source, 'mode': 'assisted'})['workflow_id']
    stop = service.registry.context.emergency_stop
    stop.trip(source=StopSource.LOCAL_TERMINAL, requested_by=Actor.local('isolated-test'))
    detail = service.detail(key)
    assert detail['status'] == 'paused' and detail['pause_requested']
    stop.clear(Actor.local('isolated-test'))
    service.resource_probe = lambda: {'allowed': True, 'ram_percent': 20.0, 'gpu': None}
    with pytest.raises(TimeoutError):
        service.wait(key, timeout=0.2, predicate=lambda item: item['status'] == 'awaiting_plan_approval')
    assert service.client.calls == 0
    operation(service, 'resume', {'workflow_id': key, 'expected_revision': detail['revision']})
    assert service.wait(key)['status'] == 'awaiting_plan_approval'
