"""Independent exposed controls. Synthetic callbacks are never live model proof."""
from __future__ import annotations
import json
import threading
import pytest
from hanni.compute import ComputeError
from hanni.models.adaptive import ModelSelectionError
from scripts.campaign5_intelligence.controlled import controlled_engine, request
MESSAGES = [{'role': 'user', 'content': 'Return the explicitly synthetic verifier sentinel.'}]
SENTINEL = 'independent synthetic sentinel'

@pytest.mark.parametrize('boundary', [1, 2])
def test_independent_local_callback_cancel(boundary, tmp_path):
    with controlled_engine(tmp_path) as engine:
        cancelled = threading.Event()
        calls = {'admit': 0, 'local': 0}

        def admission():
            calls['admit'] += 1
            if calls['admit'] == boundary:
                cancelled.set()

        def operation(client):
            calls['local'] += 1
            return SENTINEL
        rejected = False
        try:
            engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', admission=admission, cancellation=cancelled, max_fallbacks=0, local_operation=operation)
        except ModelSelectionError:
            rejected = True
        assert calls['local'] == boundary - 1
        assert rejected
        decision = engine.snapshot()['decisions'][0]
        assert decision['status'] == 'cancelled'
        assert not decision['fallbacks']
        assert not engine.snapshot()['endpoints'][0]['profiles']
        assert engine.active.get('local:supervisor', 0) == 0

def test_independent_cancel_inside_local_callback_has_no_health_penalty(tmp_path):
    with controlled_engine(tmp_path) as engine:
        cancelled = threading.Event()

        def operation(client):
            cancelled.set()
            return SENTINEL
        with pytest.raises(ModelSelectionError):
            engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', cancellation=cancelled, max_fallbacks=0, local_operation=operation)
        decision = engine.snapshot()['decisions'][0]
        assert decision['status'] == 'cancelled'
        assert decision['fallbacks'] == []
        assert not engine.snapshot()['endpoints'][0]['profiles']

@pytest.mark.parametrize('field,value', [('status', 'unhealthy'), ('ram_available_bytes', 512 * 1024 ** 2), ('vram_free_bytes', 64 * 1024 ** 2), ('ram_available_bytes', False), ('vram_free_bytes', float('nan'))])
def test_independent_result_rechecks_current_resource_authority(tmp_path, field, value):
    with controlled_engine(tmp_path) as engine:

        def operation(client):
            engine.observations['local:supervisor'][field] = value
            return SENTINEL
        with pytest.raises(ModelSelectionError):
            engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0, local_operation=operation)
        assert engine.active.get('local:supervisor', 0) == 0
        assert engine.snapshot()['decisions'][0]['status'] != 'completed'

@pytest.mark.parametrize('renewed_status', ['healthy', 'unhealthy'])
def test_independent_expired_local_result_requires_original_health_probe(tmp_path, renewed_status):
    with controlled_engine(tmp_path) as engine:
        probes = []
        prior = dict(engine.observations['local:supervisor'])

        def probe(row):
            probes.append(row['endpoint_id'])
            return {**prior, 'status': renewed_status, 'last_heartbeat': engine.clock()}
        engine.local_probe = probe

        def operation(client):
            engine.observations['local:supervisor']['last_heartbeat'] = 850
            return SENTINEL
        if renewed_status == 'healthy':
            assert engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0, local_operation=operation) == SENTINEL
            assert engine.observations['local:supervisor']['last_heartbeat'] == engine.clock()
        else:
            with pytest.raises(ModelSelectionError):
                engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0, local_operation=operation)
        assert probes == ['local:supervisor']

def test_independent_late_queue_restricts_future_dispatch_not_admitted_result(tmp_path):
    with controlled_engine(tmp_path) as engine:

        def operation(client):
            engine.observations['local:supervisor']['queue_depth'] = 17
            return SENTINEL
        assert engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0, local_operation=operation) == SENTINEL
        assert engine.snapshot()['decisions'][0]['status'] == 'completed'
        assert engine.select(request(), allowed_endpoint_ids=('local:supervisor',))['endpoint'] is None

@pytest.mark.parametrize('endpoint', ['local:supervisor', 'worker:controlled'])
@pytest.mark.parametrize('field,value', [('ram_available_bytes', -7), ('ram_available_bytes', float('inf')), ('vram_free_bytes', False), ('vram_free_bytes', '4294967296')])
def test_independent_nonfinite_or_nonnumeric_capacity_denies(tmp_path, endpoint, field, value):
    with controlled_engine(tmp_path) as engine:
        if endpoint.startswith('local:'):
            engine.observations[endpoint][field] = value
        else:
            engine.compute.registry.observe('controlled', **{field: value})
        assert engine.select(request(), allowed_endpoint_ids=(endpoint,))['endpoint'] is None
        assert not engine.compute.transport.calls

@pytest.mark.parametrize('withdrawal', ['deployment', 'worker', 'privacy', 'ram_low', 'ram_none', 'ram_bool', 'gpu_none', 'gpu_inf', 'context', 'busy', 'closed'])
def test_independent_context_bootstrap_preserves_original_gates(tmp_path, withdrawal):
    with controlled_engine(tmp_path, prove=False) as engine:
        path = tmp_path / 'compute/deployment.json'
        deployment = json.loads(path.read_text())
        worker = deployment['workers'][0]
        if withdrawal == 'deployment':
            deployment['enabled'] = False
        elif withdrawal == 'worker':
            worker['enabled'] = False
        elif withdrawal == 'privacy':
            worker['allowed_categories'] = ['memory']
        elif withdrawal == 'context':
            worker['context_configured'] = 768
        elif withdrawal.startswith('gpu'):
            worker['startup'] = {'gpu_device': 0}
        path.write_text(json.dumps(deployment), encoding='utf8')
        engine.compute.registry.reload()
        if withdrawal == 'busy':
            engine.compute.registry.active['controlled'] = 1
        elif withdrawal == 'closed':
            engine.compute.closed = True
        prior = engine.compute.transport.resources

        def resources(worker):
            changed = {'ram_available_bytes': 512 * 1024 ** 2} if withdrawal == 'ram_low' else {'ram_available_bytes': None} if withdrawal == 'ram_none' else {'ram_available_bytes': False} if withdrawal == 'ram_bool' else {'vram_free_bytes': None} if withdrawal == 'gpu_none' else {'vram_free_bytes': float('inf')} if withdrawal == 'gpu_inf' else {}
            return {**prior(worker), 'resource_sampled_at': engine.compute.registry.clock(), **changed}
        engine.compute.transport.resources = resources
        rejected = False
        try:
            engine.compute.verify_context('controlled', MESSAGES, target_tokens=1024, expected=SENTINEL, max_output_tokens=32)
        except ComputeError:
            rejected = True
        assert not engine.compute.transport.calls
        assert rejected

def test_independent_valid_bootstrap_reserves_and_releases_native_slot(tmp_path):
    with controlled_engine(tmp_path, prove=False) as engine:
        observed_active = []

        def transport(worker, method, path, **kwargs):
            observed_active.append(engine.compute.registry.active.get('controlled', 0))
            return {'model': worker['model_id'], 'choices': [{'message': {'content': SENTINEL}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 950, 'completion_tokens': 6, 'total_tokens': 956}}
        engine.compute.transport.request = transport
        result = engine.compute.verify_context('controlled', MESSAGES, target_tokens=1024, expected=SENTINEL, max_output_tokens=32)
        assert observed_active == [1]
        assert result['passed'] is True
        assert engine.compute.registry.active.get('controlled', 0) == 0
        assert result['max_context_verified'] == 1024

def test_independent_collaboration_late_verifier_cancel_withholds_authority(tmp_path):
    with controlled_engine(tmp_path) as engine:
        cancelled = threading.Event()

        def verify(output):
            cancelled.set()
            return {'status': 'VERIFIED', 'checks': {'controlled_reference': True}}
        result = engine.collaboration.run(MESSAGES, request=request(), preference='single', verify=verify, cancellation=cancelled, local_operation=lambda client: SENTINEL)
        assert result['state'] == 'cancelled'
        assert result['selected_output'] is None
        assert result['selected_endpoint_id'] is None
        assert result['final_verification']['status'] == 'UNVERIFIED'
        assert result['participants'][0]['state'] == 'cancelled'

def test_independent_collaboration_keeps_declared_context_after_assignment(tmp_path):
    with controlled_engine(tmp_path) as engine:
        calls = []

        def progress(state):
            if state['participants'][0]['state'] == 'running':
                engine.observations['local:supervisor']['context_reported'] = 1024
        result = engine.collaboration.run(MESSAGES, request=request(context_tokens=5000), preference='single', on_progress=progress, local_operation=lambda client: calls.append('entered') or SENTINEL)
        assert not calls
        assert result['selected_output'] is None
        assert result['participants'][0]['state'] == 'failed'

def test_independent_healthy_local_completion_control(tmp_path):
    with controlled_engine(tmp_path) as engine:
        assert engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0, local_operation=lambda client: SENTINEL) == SENTINEL
        assert engine.snapshot()['decisions'][0]['status'] == 'completed'
        assert engine.active.get('local:supervisor', 0) == 0

def test_independent_scoring_never_promotes_controlled_or_missing_generation():
    from scripts.campaign5_verification.scoring import score, summary
    case = {'id': 'exposed-score-1', 'category': 'simple_commands', 'checker_id': 'json_exact'}
    oracle = {'id': case['id'], 'checker_id': case['checker_id'], 'checker_inputs': {'expected': {'answer': 7}, 'schema': None}}
    row = score(case, oracle, '{"answer":7}', actual_model_http_requests=0, outcome='blocked')
    assert row['correct'] is None
    assert row['unconditional_task_passed'] is False
    assert summary([row])['semantic_accuracy'] is None

def test_independent_exact_score_distinguishes_bool_and_extra_fields():
    from scripts.campaign5_verification.scoring import score
    case = {'id': 'exposed-score-2', 'category': 'analytical_reasoning', 'checker_id': 'json_exact'}
    oracle = {'id': case['id'], 'checker_id': case['checker_id'], 'checker_inputs': {'expected': {'answer': 1}, 'schema': None}}
    assert score(case, oracle, '{"answer":1}', actual_model_http_requests=1)['correct']
    assert not score(case, oracle, '{"answer":true}', actual_model_http_requests=1)['correct']
    assert not score(case, oracle, '{"answer":1,"unsupported":"yes"}', actual_model_http_requests=1)['correct']
    assert not score(case, oracle, '{"answer":NaN}', actual_model_http_requests=1)['correct']
    assert not score(case, oracle, '{"answer":0,"answer":1}', actual_model_http_requests=1)['correct']
    assert score(case, oracle, {'text': '{"answer":1}'}, actual_model_http_requests=1)['correct']

def test_independent_code_patch_score_never_executes_model_text(tmp_path):
    from scripts.campaign5_verification.scoring import score
    case = {'id': 'exposed-score-3', 'category': 'coding', 'checker_id': 'python_line_ast'}
    oracle = {'id': case['id'], 'checker_id': case['checker_id'], 'checker_inputs': {'references': {'accepted_lines': ['return n + 2']}, 'schema': None}}
    assert score(case, oracle, json.dumps({'line': 'return (n + 2)'}), actual_model_http_requests=1)['correct']
    target = tmp_path / 'score_should_not_write'
    malicious = 'return n + 2\n__import__("pathlib").Path(' + repr(str(target)) + ').write_text("bad")'
    assert not score(case, oracle, json.dumps({'line': malicious}), actual_model_http_requests=1)['correct']
    assert not target.exists()

def test_independent_native_tool_score_does_not_treat_text_as_function_call():
    from scripts.campaign5_verification.scoring import score
    case = {'id': 'exposed-score-4', 'category': 'tool_selection', 'checker_id': 'native_tool', 'tools': [{'type': 'function', 'function': {'name': 'fixture_measure', 'parameters': {'type': 'object', 'properties': {'limit': {'type': 'integer', 'minimum': 1}}, 'required': ['limit'], 'additionalProperties': False}}}]}
    oracle = {'id': case['id'], 'checker_id': case['checker_id'], 'checker_inputs': {'expected': {'name': 'fixture_measure', 'arguments_subset': {'limit': 3}, 'calls': 1}}}
    actual = {'content': None, 'tool_calls': [{'function': {'name': 'fixture_measure', 'arguments': '{"limit":3}'}}]}
    assert score(case, oracle, actual, actual_model_http_requests=1)['correct']
    serialized = {'text': None, 'tool_calls': [{'name': 'fixture_measure', 'arguments': {'limit': 3}}]}
    assert score(case, oracle, serialized, actual_model_http_requests=1)['correct']
    assert not score(case, oracle, '{"name":"fixture_measure","arguments":{"limit":3}}', actual_model_http_requests=1)['correct']
    actual['tool_calls'][0]['function']['arguments'] = '{"limit":"3"}'
    result = score(case, oracle, actual, actual_model_http_requests=1)
    assert not result['correct']
    assert result['checks']['selected_name_correct']
    assert not result['schema_valid']

@pytest.mark.parametrize('mode', ['chat', 'tools', 'late_stream'])
@pytest.mark.parametrize('reported', ['controlled_expected', None, 'verifier_other_model'])
def test_independent_original_client_checks_present_http_identity(tmp_path, mode, reported):
    from dataclasses import replace
    from hanni.models.client import LlamaCppClient, ModelProtocolError
    from scripts.campaign5_intelligence.http_identity import identity_endpoint
    with controlled_engine(tmp_path) as engine, identity_endpoint(mode, reported) as (endpoint, calls):
        spec = replace(engine.config.models.supervisor, api_model='controlled_expected', endpoint=endpoint, id='independent_protocol_fixture')
        client = LlamaCppClient(spec, max_attempts=2)

        def call():
            if mode == 'tools':
                return client.complete_with_tools(MESSAGES, tools=[{'type': 'function', 'function': {'name': 'controlled_read', 'parameters': {'type': 'object', 'properties': {'key': {'type': 'string'}}, 'required': ['key'], 'additionalProperties': False}}}])
            return client.chat(MESSAGES, max_tokens=32)
        if reported == 'verifier_other_model':
            with pytest.raises(ModelProtocolError):
                call()
        else:
            assert call()
        assert len(calls) == 1

@pytest.mark.parametrize('withdrawal', ['runtime', 'files', 'cancel', 'privacy'])
def test_independent_bootstrap_never_publishes_old_proof_after_withdrawal(tmp_path, withdrawal):
    with controlled_engine(tmp_path, prove=False) as engine:
        cancelled = threading.Event()
        dispatched = []

        def transport(worker, method, path, **kwargs):
            dispatched.append(kwargs)
            assert kwargs.get('cancel') is cancelled
            if withdrawal == 'runtime':
                engine.compute.registry.observe('controlled', runtime_identity='changed-verifier-runtime')
            elif withdrawal == 'files':
                engine.compute.registry.observe('controlled', runtime_files_identity={'owned_marker': 'replacement'})
            elif withdrawal == 'cancel':
                cancelled.set()
            elif withdrawal == 'privacy':
                file = tmp_path / 'compute/deployment.json'
                document = json.loads(file.read_text())
                document['workers'][0]['allowed_categories'] = ['project']
                file.write_text(json.dumps(document), encoding='utf8')
            return {'model': worker['model_id'], 'choices': [{'message': {'content': SENTINEL}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 940, 'completion_tokens': 6}}
        engine.compute.transport.request = transport
        with pytest.raises(ComputeError):
            engine.compute.verify_context('controlled', MESSAGES, target_tokens=1024, expected=SENTINEL, max_output_tokens=32, cancellation=cancelled)
        assert len(dispatched) == 1
        assert not engine.compute.registry.observations['controlled'].get('max_context_verified')
        assert engine.compute.registry.active.get('controlled', 0) == 0

def test_independent_closed_adaptive_does_not_reach_remote_dispatch(tmp_path):
    with controlled_engine(tmp_path) as engine:
        engine.compute.registry.record_context_verified('controlled', target_tokens=8192, prompt_tokens=7500, model_id='controlled.gguf', prompt_sha256='d' * 64, response_sha256='e' * 64)

        def admission():
            engine.closed = True
        with pytest.raises(ModelSelectionError):
            engine.execute(MESSAGES, request=request(), endpoint_id='worker:controlled', admission=admission, max_fallbacks=0)
        assert not engine.compute.transport.calls
        assert engine.compute.registry.active.get('controlled', 0) == 0
        engine.closed = False

def test_independent_http_identity_error_is_not_configured_model_incorrectness(tmp_path):
    from dataclasses import replace
    from scripts.campaign5_intelligence.http_identity import identity_endpoint
    with controlled_engine(tmp_path) as engine, identity_endpoint('late_stream', 'verifier_replacement') as (endpoint, calls):
        spec = replace(engine.config.models.supervisor, api_model='controlled_expected', endpoint=endpoint)
        engine.config = replace(engine.config, models=replace(engine.config.models, models=(spec,)))
        engine.observations['local:supervisor']['model_id'] = 'controlled_expected'
        engine.record_capability_evidence('local:supervisor', identity=engine.endpoint_identity('local:supervisor'), capabilities=['text'], context_tokens=8192, observed_prompt_tokens=7600, retrieval_passed=True, evidence_sha256='f' * 64, environment='independent owned HTTP protocol fixture; no real inference')
        with pytest.raises(ModelSelectionError):
            engine.execute(MESSAGES, request=request(), endpoint_id='local:supervisor', max_fallbacks=0)
        assert len(calls) == 1
        profile = engine.snapshot()['endpoints'][0]['profiles']['conversation']
        assert profile['error_count'] == 1
        assert profile['correctness_sample_count'] == 0
        assert profile['accuracy'] is None
        assert engine.snapshot()['decisions'][0]['fallbacks'][0]['trigger'] == 'model_identity_mismatch'

@pytest.mark.parametrize('mode', ['pinned', 'adaptive', 'selective'])
def test_independent_final_adapter_preserves_input_and_native_mode_scope(mode):
    from copy import deepcopy
    from scripts.campaign5_verification.holdout_runner import effective_input
    case = {'id': 'exposed-adapter', 'limits': {'max_tokens': 256, 'temperature': 0, 'top_p': 1, 'max_fallbacks': 0, 'timeout_seconds': 120}}
    original = deepcopy(case)
    actual, receipt = effective_input(case, mode)
    assert case == original
    assert actual['limits'] == {'max_tokens': 256, 'temperature': 0, 'top_p': 1}
    assert receipt['sealed_limits'] == case['limits']
    assert receipt['pinned_max_fallbacks'] == (0 if mode == 'pinned' else None)
    case['oracle'] = {'answer': 'controlled'}
    with pytest.raises(ValueError):
        effective_input(case, mode)

def test_independent_final_profile_clones_include_comparison_state_without_feedback(tmp_path):
    import sqlite3
    from scripts.campaign5_verification.holdout_runner import clone_database
    source = (tmp_path / 'dev.sqlite3').resolve()
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE measurements(id TEXT, correct INTEGER)')
        db.execute('INSERT INTO measurements VALUES("dev-fixed",1)')
        db.execute('CREATE TABLE collaboration_comparisons(id TEXT,payload TEXT)')
        db.execute('INSERT INTO collaboration_comparisons VALUES("paired-dev","controlled-record")')
    first = tmp_path / 'mode1/profile.sqlite3'
    clone_database(source, first)
    with sqlite3.connect(first) as db:
        assert db.execute('SELECT payload FROM collaboration_comparisons').fetchone()[0] == 'controlled-record'
        db.execute('INSERT INTO measurements VALUES("final-unscored",0)')
    second = tmp_path / 'mode2/profile.sqlite3'
    clone_database(source, second)
    with sqlite3.connect(second) as db:
        assert db.execute('SELECT COUNT(*) FROM measurements').fetchone()[0] == 1
    with sqlite3.connect(source) as db:
        assert db.execute('SELECT COUNT(*) FROM measurements').fetchone()[0] == 1

def test_independent_raw_rejected_tool_response_retains_invalid_arguments_for_score():
    from scripts.campaign5_verification.publish import original_response
    response = {'choices': [{'message': {'content': None, 'tool_calls': [{'function': {'name': 'fixture_read', 'arguments': '{bad-json'}}]}}], 'model': 'controlled_expected'}
    row = {'classification': 'INFERENCE_ERROR', 'raw_http': [{'path': '/v1/chat/completions', 'status': 200, 'request_body': '{"model":"controlled_expected"}', 'raw_response': json.dumps(response)}]}
    actual, scope = original_response(row)
    assert actual['tool_calls'][0]['function']['arguments'] == '{bad-json'
    assert scope == 'original_raw_nonstream_rejected_by_controller'
    row['raw_http'][0]['raw_response'] = json.dumps(dict(response, model='other_fixture'))
    assert original_response(row)[0] is None

def test_independent_paired_summary_does_not_claim_benefit_from_missing_models():
    from scripts.campaign5_verification.publish import comparisons
    grades = [{'id': 'exposed-1', 'arm': 'pinned:original', 'correct': None}, {'id': 'exposed-1', 'arm': 'adaptive', 'correct': True}]
    result = comparisons(grades)['pinned:original versus adaptive']
    assert result['paired_planned_or_attempted'] == 1
    assert result['paired_observable_actual_responses'] == 0
    assert result['net_correctness_gain'] is None
    assert not result['improvement_established']

def test_independent_final_freeze_rejects_source_change_and_added_dependency(tmp_path, monkeypatch):
    from scripts.campaign5_verification import holdout_runner
    from scripts.campaign5_manager import freeze as manager_freeze
    root = tmp_path / 'controlled-repo'
    source = root / 'source'
    source.mkdir(parents=True)
    leaf = source / 'original.py'
    leaf.write_text('controlled = 1\n')
    freeze = root / 'proof'
    freeze.mkdir()
    monkeypatch.setattr(holdout_runner, 'ROOT', root)
    monkeypatch.setattr(manager_freeze, 'paths', lambda: sorted(source.glob('*.py')))
    holdout_runner.save(freeze / 'MANIFEST.json', {'source/original.py': holdout_runner.digest(leaf)})
    holdout_runner.save(freeze / 'SUMMARY.json', {'manifest_sha256': holdout_runner.digest(freeze / 'MANIFEST.json'), 'archive_sha256': 'controlled_archive_not_used', 'owner_configuration_sha256': {}})
    assert holdout_runner.assert_freeze(freeze)['files'] == 1
    leaf.write_text('controlled = 2\n')
    with pytest.raises(RuntimeError, match='Frozen source changed'):
        holdout_runner.assert_freeze(freeze)
    leaf.write_text('controlled = 1\n')
    (source / 'unexpected.py').write_text('extra = 1\n')
    with pytest.raises(RuntimeError, match='membership changed'):
        holdout_runner.assert_freeze(freeze)

def test_independent_final_profile_refuses_owner_or_foreign_database(tmp_path):
    from scripts.campaign5_verification.holdout_runner import validate_profile
    with pytest.raises(ValueError, match='campaign-owned'):
        validate_profile(tmp_path / 'foreign.sqlite3')
