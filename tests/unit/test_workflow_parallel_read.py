"""Parallel admission is narrower than the original read/permission policy."""
from dataclasses import replace
import json
import threading
import time
import pytest
from hanni.workflows.policy import is_read, parallel_read_safe
from tests.unit.test_workflow_service import approve_start, install, operation, service

@pytest.mark.parametrize('changes', [{'external_definition_hash': 'approved-external-definition'}, {'name': 'mcp.provider_read'}, {'name': 'unknown_extension.read'}, {'name': 'google.drive.metadata'}])
def test_external_name_hash_provider_and_unknown_reads_remain_reads_but_not_parallel(service, changes):
    definition = replace(service.registry.get('file.read'), **changes)
    assert is_read(definition)
    assert not parallel_read_safe(definition)

class IndependentReadsClient:

    def __init__(self, source):
        self.source, self.calls = (source, 0)

    def chat(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return json.dumps({'summary': 'Read the supplied local file independently twice.', 'unsupported_reason': None, 'steps': [{'step_id': key, 'description': 'Read the text file ' + self.source, 'kind': 'tool', 'dependencies': [], 'required': True, 'criteria': [{'operator': 'equals', 'path': '/data/text', 'expected': 'actual isolated evidence'}]} for key in ('first', 'second')]})
        return json.dumps({'unsupported_reason': None, 'steps': [{'step_id': key, 'capability_id': 'file.read', 'arguments': {'path': self.source}} for key in ('first', 'second')]})

@pytest.mark.parametrize('external', [False, True])
def test_actual_original_reads_overlap_only_when_known_local(service, external):
    original = service.registry.get('file.read')
    first_entered, both_entered, released = (threading.Event(), threading.Event(), threading.Event())
    entries, lock = ([], threading.Lock())

    def observed(arguments, context, request):
        with lock:
            entries.append(request.correlation_id)
            first_entered.set()
            if len(entries) == 2:
                both_entered.set()
        assert released.wait(5)
        return original.handler(arguments, context, request)
    install(service, 'file.read', observed, external_definition_hash='approved-isolated-external' if external else '')
    service.client = IndependentReadsClient(service.client.source)
    key = operation(service, 'goal.submit', {'goal': 'Read the local text file ' + service.client.source, 'mode': 'assisted'})['workflow_id']
    detail = service.wait(key)
    assert detail['status'] == 'awaiting_plan_approval', detail
    approve_start(service, key, detail)
    try:
        assert first_entered.wait(3)
        if external:
            assert not both_entered.wait(0.3)
            assert len(entries) == 1
            assert {worker['kind'] for worker in service.workers.values()} == {'serial_read'}
            detail = service.detail(key)
            assert len(detail['invocations']) == 1
            assert not detail['invocations'][0]['write']
            assert not detail['invocations'][0]['approval_id']
            queued = operation(service, 'goal.submit', {'goal': 'Read the local text file ' + service.client.source, 'mode': 'assisted'})['workflow_id']
            time.sleep(0.15)
            assert service.client.calls == 2
            assert service.detail(queued)['status'] == 'submitted'
            queued_detail = service.detail(queued)
            operation(service, 'cancel', {'workflow_id': queued, 'expected_revision': queued_detail['revision']})
        else:
            assert both_entered.wait(3)
            assert len(entries) == 2
            assert {worker['kind'] for worker in service.workers.values()} == {'read'}
    finally:
        released.set()
    detail = service.wait(key)
    assert len(detail['invocations']) == 2
    assert detail['status'] == ('partially_completed' if external else 'completed')
