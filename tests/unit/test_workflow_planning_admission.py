"""Planning rechecks original trust/admission between every model request."""
import pytest
from hanni.core.identity import Actor
from hanni.core.shutdown import StopSource
from tests.unit.test_workflow_service import PlanClient, operation, service

@pytest.mark.parametrize('withdraw', ['stop', 'pause', 'cancel', 'resources'])
def test_second_model_call_is_not_admitted_after_trust_or_resources_change(service, withdraw):
    original = PlanClient(service.client.source)

    class ChangingClient:

        def chat(self, messages, **options):
            text = original.chat(messages, **options)
            if original.calls == 1:
                if withdraw == 'stop':
                    service.registry.context.emergency_stop.trip(source=StopSource.LOCAL_TERMINAL, requested_by=Actor.local('isolated-planning-test'), reason='isolated planning stop')
                elif withdraw == 'resources':
                    service.resource_probe = lambda: {'allowed': False, 'ram_percent': None, 'reason': 'isolated unavailable resource'}
                else:
                    record = service.snapshot()[0]
                    operation(service, withdraw, {'workflow_id': record['workflow_id'], 'expected_revision': record['revision']})
            return text
    service.client = ChangingClient()
    key = operation(service, 'goal.submit', {'goal': 'Read the local text file ' + original.source, 'mode': 'assisted'})['workflow_id']
    detail = service.wait(key)
    assert original.calls == 1
    assert not detail['invocations']
    assert not detail['active_uninterruptible']
    assert detail['status'] == ('cancelled' if withdraw == 'cancel' else 'paused' if withdraw in {'pause', 'stop'} else 'blocked')

def test_unchanged_admission_allows_both_original_model_calls(service):
    client = service.client
    key = operation(service, 'goal.submit', {'goal': 'Read the local text file ' + client.source, 'mode': 'assisted'})['workflow_id']
    detail = service.wait(key)
    assert client.calls == 2
    assert detail['status'] == 'awaiting_plan_approval'
    assert not detail['invocations']
