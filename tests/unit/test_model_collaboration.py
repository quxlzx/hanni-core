"""Bounded comparison tests; synthetic adapters, genuine original routing guards."""
from dataclasses import replace
import json
import threading
import pytest
from hanni.models.collaboration import CollaborationEngine, CollaborationLimits, SpecialistTask
from hanni.models.adaptive import ModelSelectionError, ModelRequest
from hanni.compute import ComputeError
from tests.unit.test_adaptive_model_routing import engine, request

def prove(engine, key):
    engine.record_capability_evidence(key, identity=engine.endpoint_identity(key), capabilities=['text', 'structured_json'], context_tokens=8192, observed_prompt_tokens=7600, retrieval_passed=True, evidence_sha256='e' * 64, metadata={'structured_output_formats': ['json_object']}, environment='synthetic controlled probe')

@pytest.fixture
def collaboration(engine, monkeypatch):
    for key in ('local:supervisor', 'worker:fixture'):
        prove(engine, key)

    def local(self, messages, **options):
        usage = options.get('usage', getattr(self, '_inference_usage', None))
        if usage is not None:
            usage.update(prompt_tokens=20, completion_tokens=4, total_tokens=24)
        return '{"value": 41}'
    monkeypatch.setattr('hanni.models.adaptive._BoundedInferenceClient.chat', local)
    engine.compute.transport.outputs = ['{"value": 42}'] * 10
    return CollaborationEngine(engine, limits=CollaborationLimits(max_participants=2))

def checked(text):
    return {'status': 'VERIFIED' if json.loads(text).get('value') == 42 else 'UNVERIFIED', 'scope': 'independent_synthetic_exact_value', 'checks': {'exact_source_value': json.loads(text).get('value') == 42}}

def run(collaboration, **kwargs):
    return collaboration.run([{'role': 'user', 'content': 'Return the source value as JSON.'}], request=request(task_category='analysis', complexity='complex'), preference='parallel', verify=checked, response_format={'type': 'json_object'}, **kwargs)

def test_parallel_uses_distinct_pinned_original_endpoints_and_external_evidence(collaboration):
    result = run(collaboration, context_refs=[{'source_id': 'fixture', 'sha256': 'a' * 64}])
    assert result['selected_endpoint_id'] == 'worker:fixture'
    assert result['final_verification']['status'] == 'VERIFIED'
    assert [item['endpoint_id'] for item in result['participants']] == ['local:supervisor', 'worker:fixture']
    assert result['generated_tokens'] == 7
    assert result['participants'][0]['tokens']['completion_tokens'] == 4
    assert result['participants'][1]['resource_observations']['ram_available_bytes'] == 8 * 1024 ** 3
    assert result['conflicts'][0]['kind'] == 'different_outputs'
    assert result['context_refs'][0]['source_id'] == 'fixture'
    assert len(result['input_sha256']) == 64
    assert len(collaboration.adaptive.compute.transport.calls) == 1

def test_parallel_really_runs_both_inferences_concurrently(collaboration, monkeypatch):
    barrier = threading.Barrier(2)
    original = collaboration.adaptive.compute.transport.request

    def remote(*args, **kwargs):
        barrier.wait(timeout=2)
        return original(*args, **kwargs)

    def local(*args, **kwargs):
        barrier.wait(timeout=2)
        return '{"value":42}'
    monkeypatch.setattr(collaboration.adaptive.compute.transport, 'request', remote)
    monkeypatch.setattr('hanni.models.adaptive._BoundedInferenceClient.chat', local)
    result = run(collaboration)
    assert all((item['state'] == 'completed' for item in result['participants']))

def test_agreement_without_source_verification_is_never_proof(collaboration, monkeypatch):
    monkeypatch.setattr('hanni.models.adaptive._BoundedInferenceClient.chat', lambda *args, **kwargs: '{"value":42}')
    result = collaboration.run([{'role': 'user', 'content': 'synthetic'}], request=request(), preference='parallel')
    assert all((item['verification']['status'] == 'UNVERIFIED' for item in result['participants']))
    assert result['final_verification']['status'] == 'UNVERIFIED'

def test_failed_secondary_retains_primary_and_does_not_retry_other_models(collaboration):
    collaboration.adaptive.compute.transport.fail = True
    result = run(collaboration)
    assert result['selected_endpoint_id'] == 'local:supervisor'
    assert result['state'] == 'completed' and result['final_verification']['status'] == 'UNVERIFIED'
    assert result['participants'][1]['state'] == 'failed'
    assert len(collaboration.adaptive.compute.transport.calls) == 1

@pytest.mark.parametrize('private', ['project', 'conversation', 'memory', 'screen', 'sensitive'])
def test_private_workflow_context_cannot_relabel_itself_synthetic(collaboration, private):
    result = collaboration.run([{'role': 'user', 'content': 'private source'}], request=ModelRequest(privacy_categories=frozenset({private}), output_tokens=64), preference='parallel')
    assert result['effective_pattern'] == 'single'
    assert collaboration.adaptive.compute.transport.calls == []

def test_cancelled_collaboration_dispatches_no_model(collaboration):
    cancel = threading.Event()
    cancel.set()
    result = run(collaboration, cancellation=cancel)
    assert result['state'] == 'cancelled' and result['selected_output'] is None
    assert all((item['state'] == 'cancelled' for item in result['participants']))
    assert collaboration.adaptive.compute.transport.calls == []

def test_admission_is_rechecked_before_every_dispatch(collaboration):

    def reject():
        raise ComputeError('Original authority withdrawn.')
    result = run(collaboration, admission=reject)
    assert result['selected_output'] is None
    assert collaboration.adaptive.compute.transport.calls == []

def test_persistence_failure_is_not_hidden_as_an_endpoint_failure(collaboration):
    from hanni.workflows.types import LeaseLost

    def invalid_lease(_):
        raise LeaseLost('Original lease superseded.')
    with pytest.raises(LeaseLost):
        run(collaboration, on_progress=invalid_lease)
    assert collaboration.adaptive.compute.transport.calls == []

def test_single_and_auto_default_do_not_dispatch_second_model(collaboration):
    for preference in ('single', 'auto'):
        result = collaboration.run([{'role': 'user', 'content': 'synthetic'}], request=request(), preference=preference)
        assert len(result['participants']) == 1
    assert collaboration.adaptive.compute.transport.calls == []

def test_invalid_format_and_total_token_budget_are_rejected(collaboration):
    with pytest.raises(ModelSelectionError):
        run(collaboration, max_tokens=8193)
    with pytest.raises(ModelSelectionError):
        collaboration.run([{'role': 'user', 'content': 'x'}], request=request(), response_format='invalid')
    with pytest.raises(ModelSelectionError):
        CollaborationLimits(max_participants=10)
    result = run(collaboration, max_tokens=5000)
    assert result['effective_pattern'] == 'single' and result['output_token_budget'] == 5000

def test_model_review_is_advisory_and_cannot_upgrade_original_answer(collaboration):
    collaboration.adaptive.compute.transport.outputs = ['{"assessment":"supported","issues":[]}']
    result = collaboration.run([{'role': 'user', 'content': 'synthetic source value42'}], request=request(), preference='review', verify=checked, response_format={'type': 'json_object'})
    assert result['participants'][1]['review_assessment']['assessment'] == 'supported'
    assert result['participants'][1]['verification']['status'] == 'UNVERIFIED'
    assert result['final_verification']['status'] == 'UNVERIFIED'
    assert result['max_rounds'] == 2

def test_invalid_secondary_review_preserves_original_output(collaboration):
    collaboration.adaptive.compute.transport.outputs = ['{"assessment":"invented","issues":[]}']
    result = collaboration.run([{'role': 'user', 'content': 'synthetic'}], request=request(), preference='review', verify=checked)
    assert result['state'] == 'completed' and result['participants'][1]['state'] == 'failed'
    assert result['selected_endpoint_id'] == 'local:supervisor'

def test_specialist_preference_never_invents_specialist_expertise(collaboration):
    result = collaboration.run([{'role': 'user', 'content': 'synthetic'}], request=request(), preference='specialists')
    assert result['effective_pattern'] == 'parallel'
    assert 'No distinct' in result['reason']

def grade(engine, endpoint, category):
    for index in range(30):
        engine.record_evaluation(endpoint, identity=engine.endpoint_identity(endpoint), task_category=category, correct=True, verified_success=True, latency_ms=5, evidence_sha256='d' * 64, environment='controlled independently graded category', evaluation_id=f'{endpoint}-{category}-{index}')

def test_distinct_specialist_tasks_require_measured_category_proof(collaboration):
    tasks = [SpecialistTask('facts', 'Check supplied source facts', ({'role': 'user', 'content': 'fact task'},), request(task_category='analysis'), checked), SpecialistTask('code', 'Check supplied coding result', ({'role': 'user', 'content': 'coding task'},), request(task_category='coding'), checked)]
    with pytest.raises(ModelSelectionError):
        collaboration.run_specialists(tasks, request=request())
    assert collaboration.adaptive.compute.transport.calls == []
    grade(collaboration.adaptive, 'local:supervisor', 'analysis')
    grade(collaboration.adaptive, 'worker:fixture', 'coding')
    result = collaboration.run_specialists(tasks, request=request())
    assert result['effective_pattern'] == 'specialists'
    assert [item['assigned_task'] for item in result['participants']] == ['Check supplied source facts', 'Check supplied coding result']
    assert [item['task_id'] for item in result['outcomes']] == ['facts', 'code']
    assert result['final_verification']['status'] == 'UNVERIFIED'

def test_specialist_subrequest_cannot_remove_private_aggregate_context(collaboration):
    grade(collaboration.adaptive, 'local:supervisor', 'analysis')
    grade(collaboration.adaptive, 'worker:fixture', 'analysis')
    tasks = [SpecialistTask('a', 'Check a', ({'role': 'user', 'content': 'a'},), request(task_category='analysis'), checked), SpecialistTask('b', 'Check b', ({'role': 'user', 'content': 'b'},), request(task_category='analysis'), checked)]
    with pytest.raises(ModelSelectionError):
        collaboration.run_specialists(tasks, request=ModelRequest())
    assert collaboration.adaptive.compute.transport.calls == []

def test_paired_policy_requires_identity_bound_benefit_and_rejects_losing_classes(collaboration):
    req = request(task_category='analysis', complexity='complex')
    assert collaboration.policy(req)['enabled'] is False
    for index in range(5):
        collaboration.record_comparison(task_category='analysis', single_correct=False, multi_correct=True, single_latency_ms=100, multi_latency_ms=150, evidence_sha256='a' * 64, evaluation_id=f'pair-{index}')
    assert collaboration.policy(req)['enabled'] is True
    assert collaboration.policy(replace(req, complexity='simple'))['enabled'] is False
    collaboration.adaptive.compute.registry.observe('fixture', runtime_identity='changed')
    assert collaboration.policy(req)['enabled'] is False
    for index in range(5):
        collaboration.record_comparison(task_category='analysis', single_correct=True, multi_correct=False, single_latency_ms=100, multi_latency_ms=150, evidence_sha256='b' * 64, evaluation_id=f'loss-{index}')
    assert collaboration.policy(req)['enabled'] is False

def test_comparison_replay_is_idempotent_and_cannot_change_proof(collaboration):
    options = dict(task_category='analysis', single_correct=True, multi_correct=True, single_latency_ms=100, multi_latency_ms=150, evidence_sha256='a' * 64, evaluation_id='same')
    collaboration.record_comparison(**options)
    collaboration.record_comparison(**options)
    assert collaboration.policy(request(task_category='analysis', complexity='complex'))['sample_count'] == 1
    with pytest.raises(ModelSelectionError):
        collaboration.record_comparison(**dict(options, multi_correct=False))

@pytest.mark.parametrize('oversize', ['output', 'evidence'])
def test_oversized_secondary_serialized_envelope_preserves_primary(collaboration, oversize):
    if oversize == 'output':
        collaboration.adaptive.compute.transport.outputs = [json.dumps({'value': 42, 'padding': '\x01' * 2000})]
        verify = checked
    else:

        def verify(text):
            return {**checked(text), 'reason': 'x' * 4000 if json.loads(text)['value'] == 42 else 'Primary evidence preserved.'}
    result = collaboration.run([{'role': 'user', 'content': 'synthetic'}], request=request(), preference='parallel', verify=verify, retained_output_bytes=2048, retained_participant_bytes=3072)
    assert result['participants'][0]['state'] == 'completed'
    assert result['participants'][0]['output'] == '{"value": 41}'
    assert result['participants'][1]['state'] == 'failed'
    assert result['participants'][1]['output'] is None
    assert result['participants'][1]['tokens']['completion_tokens'] == 3
    assert result['selected_endpoint_id'] == 'local:supervisor'

def test_review_provenance_identifies_actual_wrapped_input(collaboration):
    collaboration.adaptive.compute.transport.outputs = ['{"assessment":"uncertain","issues":["Draft lacks proof"]}']
    result = collaboration.run([{'role': 'user', 'content': 'synthetic'}], request=request(), preference='review')
    first, second = result['participants']
    assert first['input_sha256'] != second['input_sha256']
    assert second['context_refs'][-1]['participant_id'] == first['participant_id']
    assert result['final_verification']['status'] == 'UNVERIFIED'
