"""Unchanged public V4.4 assertions, with a distinct C9 bootstrap fixture.

Aliases retain every original function body, assertion and parametrization.
Neither original module nor its protected source bytes are changed.
"""
import json
import pytest
from scripts.campaign9_resilience.cross_boundary import bootstrapped_audit_engine
from tests.integration import test_v44_independent_security as original

@pytest.fixture(name='audit_engine')
def c9_audit_engine(tmp_path, record_property):
    with bootstrapped_audit_engine(tmp_path, lambda receipt: record_property('controlled_bootstrap', json.dumps(receipt))) as value:
        yield value
for original_name, original_function in vars(original).items():
    if original_name.startswith('test_') and callable(original_function):
        globals()['test_c9_bootstrapped_' + original_name[5:]] = original_function

def test_c9_bootstrap_reaches_unchanged_native_admission(audit_engine):
    _, compute, calls, _ = audit_engine
    choices = compute._choices({'synthetic'}, 512)
    assert len(choices) == 1
    assert choices[0][1] == 'remote-fixture'
    assert not calls and (not compute.inflight) and (not any(compute.registry.active.values()))

def test_c9_bootstrap_keeps_original_transport_response_and_usage(audit_engine):
    _, compute, calls, response = audit_engine
    text, job = compute.chat([{'role': 'user', 'content': 'Controlled post-setup positive.'}], workflow_id='c9_cross_positive', step_id='reason', invocation_id='positive', categories={'synthetic'}, max_tokens=32, max_queue_seconds=0.1, max_retries_override=0)
    assert text == '{"ok":true}' and job['state'] == 'COMPLETED'
    assert response['usage'] == {'completion_tokens': 5}
    assert len(calls) == 1
    assert not compute.inflight and (not any(compute.registry.active.values()))
