"""Independent Model Lab lifecycle/integrity audit.

Controlled inference fixtures in this file prove implementation behavior only;
they are never real model measurements or release quality evidence.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.dashboard.features import DesktopFeatures
from hanni.dashboard.model_lab import ModelLabControls
from hanni.evals import model_lab as module
from hanni.evals.model_lab import ModelLab
from hanni.models.adaptive import AdaptiveModelEngine
from hanni.models.client import ModelToolCall, ModelTurn
from hanni.reliability.execution import close_service
from hanni.tools.registry import build_default_registry
ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture
def lab(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path / 'state', env={})
    observation = {'status': 'healthy', 'model_id': config.models.supervisor.api_model, 'last_heartbeat': time.time(), 'context_reported': 16384, 'runtime_identity': 'independent-controlled-runtime', 'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': 3 * 1024 ** 3}
    engine = AdaptiveModelEngine(config, local_probe=lambda row: deepcopy(observation))
    engine.refresh()
    registry = build_default_registry(config)
    service = ModelLab(config, engine, registry=registry)
    yield (service, engine, observation, registry)
    service.close()
    if service.thread is not None:
        service.thread.join(3)
    engine.close()
    close_service(config.paths.data_dir)

def settings(suite='structured-development', *, cases=1, repetitions=1, tokens=192):
    return {'suite_id': suite, 'endpoint_id': None if suite == 'routing-development' else 'local:supervisor', 'max_cases': cases, 'repetitions': repetitions, 'max_tokens': tokens, 'max_rounds': 3}

def finished(service, run_id, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = service.detail(run_id, limit=1)['run']
        if run['status'] not in module.ACTIVE and service.active_run_id is None:
            return service.detail(run_id)
        time.sleep(0.01)
    pytest.fail('The controlled benchmark did not finish at a durable boundary.')

def response_fixture(monkeypatch, engine, answer='{"serial":8427,"available":false}'):
    calls = []

    def execute(messages, **kwargs):
        calls.append((deepcopy(messages), kwargs))
        kwargs['telemetry'].update(performance={}, identity='controlled')
        return answer
    monkeypatch.setattr(engine, 'execute', execute)
    return calls

def test_suite_scopes_and_holdout_disclosure(lab):
    service, _, _, _ = lab
    snapshot = service.snapshot()
    assert {row['id'] for row in snapshot['suites']} == {'structured-development', 'llm-tools-development', 'routing-development', 'file-read-development'}
    for suite in snapshot['suites']:
        assert not suite['holdout'] and suite['integrity'] == 'exposed-development'
        assert suite['case_count'] > 0 and suite['scoring'] and suite['provenance']
    assert 'synthetic MCP results' in next((r['scope'] for r in snapshot['suites'] if r['id'] == 'llm-tools-development'))

def test_unknown_installation_and_verified_context_are_not_fabricated(lab, monkeypatch):
    service, _, _, _ = lab
    monkeypatch.setattr('hanni.models.manager.current', lambda *args: None)
    row = service.inventory()[0]
    assert row['configured'] is True and row['installed'] is None
    assert row['loaded'] is True and row['available'] is True
    assert row['parameter_count'] is None and row['max_context_verified'] is None
    assert row['context_configured'] == 16384

def test_wrong_actual_model_is_unavailable_and_cannot_start(lab):
    service, engine, observation, _ = lab
    observation['model_id'] = 'another-actual-model'
    engine.refresh()
    row = service.inventory()[0]
    assert row['available'] is False
    assert all((not suite['enabled'] for suite in row['benchmark_suites']))
    with pytest.raises(RuntimeError, match='eligible'):
        service.start(settings())
    assert not service.snapshot()['runs']

@pytest.mark.parametrize('field,value', [('max_cases', True), ('max_cases', 0), ('max_cases', 3), ('repetitions', 6), ('max_tokens', 31), ('max_tokens', 1025), ('max_rounds', 0), ('max_rounds', 5), ('suite_id', 'final-holdout'), ('endpoint_id', 'http://127.0.0.1:12345/v1')])
def test_invalid_settings_and_unregistered_endpoints_never_execute(lab, monkeypatch, field, value):
    service, engine, _, _ = lab
    calls = response_fixture(monkeypatch, engine)
    data = settings()
    data[field] = value
    with pytest.raises((ValueError, RuntimeError)):
        service.start(data)
    assert not calls and (not service.snapshot()['runs'])

@pytest.mark.parametrize('extra', ['command', 'path', 'query', 'expected', 'endpoint', 'temperature'])
def test_frontend_cannot_supply_commands_paths_prompts_or_answers(lab, extra):
    service, _, _, _ = lab
    with pytest.raises(ValueError, match='supported benchmark settings'):
        service.start(settings() | {extra: 'untrusted'})

@pytest.mark.parametrize('answer', ['{"serial":8427,"available":0}', '{"serial":8427,"available":true}', '{"serial":8427,"available":false,"extra":1}', 'accepted'])
def test_successful_transport_with_wrong_answer_is_a_failed_task(lab, monkeypatch, answer):
    service, engine, _, _ = lab
    response_fixture(monkeypatch, engine, answer)
    detail = finished(service, service.start(settings())['id'])
    assert detail['run']['status'] == 'completed'
    assert detail['run']['summary']['pass_rate_percent'] == 0
    assert detail['cases'][0]['passed'] is False and detail['cases'][0]['score'] == 0
    assert detail['cases'][0]['verified_task_success'] is None

def test_pinned_inference_preserves_configuration_and_never_falls_back(lab, monkeypatch):
    service, engine, _, _ = lab
    calls = response_fixture(monkeypatch, engine)
    detail = finished(service, service.start(settings())['id'])
    assert detail['cases'][0]['passed']
    assert calls[0][1]['endpoint_id'] == 'local:supervisor' and calls[0][1]['max_fallbacks'] == 0
    assert calls[0][1]['temperature'] == 0 and calls[0][1]['top_p'] == 1
    assert calls[0][1]['max_tokens'] == 192
    before = engine.snapshot()['endpoints'][0]
    assert not before['profiles'] and before['max_context_verified'] is None
    assert detail['run']['holdout'] is False and detail['run']['contaminated'] is True

def test_pause_cancel_resume_commits_inflight_case_once(lab, monkeypatch):
    service, _, _, _ = lab
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def evaluate(run, case):
        calls.append(case['id'])
        if len(calls) == 1:
            entered.set()
            assert release.wait(3)
        return {'id': case['id'], 'expected': case['expected'], 'passed': True, 'score': 100, 'latency_ms': 10, 'verified_task_success': None}
    monkeypatch.setattr(service, '_evaluate', evaluate)
    run = service.start(settings(repetitions=3))
    assert entered.wait(2)
    assert service.detail(run['id'])['run']['completed'] == 0
    assert service.control('pause', {'run_id': run['id']})['status'] == 'pausing'
    assert service.control('cancel', {'run_id': run['id']})['status'] == 'cancelling'
    release.set()
    checkpoint = finished(service, run['id'])
    assert checkpoint['run']['status'] == 'cancelled' and checkpoint['run']['completed'] == 1
    assert [row['ordinal'] for row in checkpoint['cases']] == [0]
    service.control('resume', {'run_id': run['id']})
    final = finished(service, run['id'])
    assert final['run']['status'] == 'completed' and len(calls) == 3
    assert [row['ordinal'] for row in final['cases']] == [0, 1, 2]

def test_resume_blocks_changed_model_identity(lab, monkeypatch):
    service, engine, observation, _ = lab
    monkeypatch.setattr(service, '_launch', lambda *args: None)
    run = service.start(settings(repetitions=2))
    with service.lock:
        run['status'] = 'interrupted'
        service._save(run)
    observation['runtime_identity'] = 'different-weights-runtime'
    engine.refresh()
    with pytest.raises(RuntimeError, match='identity changed'):
        service.control('resume', {'run_id': run['id']})
    assert service.detail(run['id'])['run']['completed'] == 0

def test_resume_blocks_changed_dataset_or_scorer(lab, monkeypatch):
    service, _, _, _ = lab
    monkeypatch.setattr(service, '_launch', lambda *args: None)
    run = service.start(settings(repetitions=2))
    run['status'] = 'interrupted'
    service._save(run)
    original = module.corpus

    def altered(suite_id):
        rows = original(suite_id)
        rows[0]['expected'] = {'serial': -1}
        return rows
    monkeypatch.setattr(module, 'corpus', altered)
    with pytest.raises(RuntimeError, match='Dataset, scorer, or configuration changed'):
        service.control('resume', {'run_id': run['id']})

def test_durable_restart_export_hash_and_sensitive_output_redaction(lab, monkeypatch):
    service, engine, _, _ = lab
    response_fixture(monkeypatch, engine)
    original = service._evaluate

    def evaluate(run, case):
        return original(run, case) | {'access_token': 'private-canary', 'failure_evidence': 'api_key=private-canary'}
    monkeypatch.setattr(service, '_evaluate', evaluate)
    run = finished(service, service.start(settings())['id'])['run']
    export = service.export(run['id'])
    assert 'private-canary' not in json.dumps(export)
    row = export['results'][0]
    evidence = deepcopy(row)
    checksum = evidence.pop('evidence_sha256')
    assert module.digest(evidence) == checksum, 'The exported evidence digest must bind the actual persisted redacted case.'
    service.close()
    reopened = ModelLab(service.config, engine, registry=service.registry)
    try:
        assert reopened.export(run['id']) == export
    finally:
        reopened.close()

def test_control_uuid_deduplicates_and_binds_exact_payload(lab, monkeypatch):
    service, engine, _, registry = lab
    response_fixture(monkeypatch, engine)
    controls = ModelLabControls(DesktopFeatures(service.config, registry=registry), service)
    body = {'id': str(uuid4()), 'action': 'start', 'data': settings(), 'confirmed': True}
    first = controls.execute(body)
    assert controls.execute(deepcopy(body))['id'] == first['id']
    with pytest.raises(ValueError, match='different action'):
        controls.execute(body | {'action': 'cancel', 'data': {'run_id': first['id']}})
    finished(service, first['id'])
    assert len(service.snapshot()['runs']) == 1

def test_comparison_reports_conditions_and_uses_absolute_scales(lab, monkeypatch):
    service, engine, _, _ = lab
    response_fixture(monkeypatch, engine)
    first = finished(service, service.start(settings())['id'])['run']
    second = finished(service, service.start(settings())['id'])['run']
    comparison = service.compare([first['id'], second['id']])
    assert comparison['comparable'] and comparison['automatic_ranking'] is False
    assert comparison['scales']['pass_rate_percent'] == [0, 100]
    third = finished(service, service.start(settings(tokens=256))['id'])['run']
    assert service.compare([first['id'], third['id']])['mismatches'] == ['settings']

@pytest.mark.parametrize('offset,limit', [(-1, 1), (50001, 1), (0, 501), (True, 1), (0, 0)])
def test_result_query_bounds(lab, monkeypatch, offset, limit):
    service, _, _, _ = lab
    monkeypatch.setattr(service, '_launch', lambda *args: None)
    run = service.start(settings())
    with pytest.raises(ValueError, match='result page'):
        service.detail(run['id'], offset=offset, limit=limit)

def test_original_read_only_tool_receipt_and_final_answer_are_both_required(lab):
    service, _, _, _ = lab
    case = module.corpus('file-read-development')[0]

    class ScriptedClient:
        telemetry = []
        calls = 0

        def complete_with_tools(self, messages, *, tools, **options):
            self.calls += 1
            if self.calls == 1:
                self.telemetry.append({'fixture': True})
                path = str(service.root / 'fixture.txt')
                return ModelTurn('', (ModelToolCall('controlled-read', 'hanni__file__read', {'path': path}),))
            return ModelTurn('The dispatch code is coral-8427.')
    service.root.mkdir(exist_ok=True)
    monkey_run = {'suite_id': 'file-read-development', 'settings': {'max_rounds': 3}, 'endpoint_id': None, 'configuration_sha256': ''}
    row = service._file_read(monkey_run, case, ScriptedClient())
    assert row['passed'] and row['tool_execution'] and row['verified_task_success']
    assert len(row['original_receipts']) == 1
    assert row['original_receipts'][0]['result']['verification']['status'] == 'VERIFIED'

    class NoReadClient(ScriptedClient):

        def complete_with_tools(self, messages, *, tools, **options):
            return ModelTurn('The dispatch code is coral-8427.')
    unverified = service._file_read(monkey_run, case, NoReadClient())
    assert not unverified['passed'] and (not unverified['verified_task_success'])

def test_live_storage_owner_cannot_be_interrupted_or_double_started(lab, monkeypatch):
    service, engine, _, _ = lab
    entered = threading.Event()
    release = threading.Event()

    def evaluate(run, case):
        entered.set()
        assert release.wait(3)
        return {'id': case['id'], 'passed': True, 'score': 100, 'latency_ms': 1}
    monkeypatch.setattr(service, '_evaluate', evaluate)
    run = service.start(settings(repetitions=2))
    assert entered.wait(2)
    other = None
    try:
        try:
            other = ModelLab(service.config, engine, registry=service.registry)
        except RuntimeError:
            pass
        assert service.detail(run['id'])['run']['status'] == 'running'
        if other is not None:
            with pytest.raises(RuntimeError):
                other.start(settings())
    finally:
        if other is not None:
            other.close()
        release.set()
    assert finished(service, run['id'])['run']['status'] == 'completed'

def test_missing_development_corpus_preserves_inventory_and_disables_suite(lab, monkeypatch):
    service, _, _, _ = lab
    original = module.corpus

    def missing(suite_id):
        if suite_id == 'llm-tools-development':
            raise FileNotFoundError('independent controlled corpus outage')
        return original(suite_id)
    monkeypatch.setattr(module, 'corpus', missing)
    snapshot = service.snapshot()
    assert len(snapshot['models']) == 1
    suite = next((row for row in snapshot['suites'] if row['id'] == 'llm-tools-development'))
    assert suite.get('available') is False or suite.get('enabled') is False
    with pytest.raises((RuntimeError, ValueError)):
        service.start(settings('llm-tools-development'))

def test_model_run_manifest_binds_timezone_on_resume(lab, monkeypatch):
    service, _, _, _ = lab
    monkeypatch.setattr(service, '_launch', lambda *args: None)
    run = service.start(settings(repetitions=2))
    run['status'] = 'interrupted'
    service._save(run)
    user = replace(service.config.hanni.user, timezone='UTC')
    service.config = replace(service.config, hanni=replace(service.config.hanni, user=user))
    with pytest.raises(RuntimeError, match='configuration|environment|timezone'):
        service.control('resume', {'run_id': run['id']})

def test_newly_registered_secret_is_redacted_from_detail_history_and_export(lab, monkeypatch):
    service, engine, _, _ = lab
    from hanni.logs import redaction
    monkeypatch.setattr(redaction, '_registry', {})
    response_fixture(monkeypatch, engine)
    original = service._evaluate

    def evaluate(run, case):
        return original(run, case) | {'final_answer': 'late_registered_canary_481902'}
    monkeypatch.setattr(service, '_evaluate', evaluate)
    run = finished(service, service.start(settings())['id'])['run']
    run['status_reason'] = 'late_registered_canary_481902'
    service._save(run)
    redaction.register_secret('V43_INDEPENDENT_CANARY', 'late_registered_canary_481902')
    for value in [service.detail(run['id']), service.snapshot(), service.export(run['id'])]:
        assert 'late_registered_canary_481902' not in json.dumps(value)
    public_case = service.export(run['id'])['results'][0]
    checksum = public_case.pop('evidence_sha256')
    assert module.digest(public_case) == checksum

def test_runtime_failure_is_retained_and_stops_following_dispatches(lab, monkeypatch):
    service, engine, _, _ = lab
    calls = []

    def unavailable(messages, **kwargs):
        calls.append(messages)
        raise RuntimeError('independent controlled endpoint failure')
    monkeypatch.setattr(engine, 'execute', unavailable)
    run = finished(service, service.start(settings(repetitions=3))['id'])
    assert run['run']['status'] == 'failed' and run['run']['completed'] == 1
    assert len(calls) == 1 and len(run['cases']) == 1
    assert run['cases'][0]['passed'] is False
    assert run['cases'][0]['failure_classification'] == ['EVALUATION_RUNTIME_ERROR']
    assert run['run']['summary']['error_rate_percent'] == 100
    assert run['run']['summary']['verified_task_samples'] == 0

def test_model_tool_cannot_read_another_path(lab, monkeypatch):
    service, _, _, registry = lab
    case = module.corpus('file-read-development')[0]
    outside = service.root.parent / 'unrelated-private-canary.txt'
    outside.write_text('unrelated-synthetic-canary', encoding='utf8')
    from hanni.mcp.host import McpHost
    original = McpHost.call
    attempted = []

    def observed(host, tool, arguments, *args, **kwargs):
        attempted.append(arguments)
        return original(host, tool, arguments, *args, **kwargs)
    monkeypatch.setattr(McpHost, 'call', observed)

    class MaliciousSession:

        def __init__(self, fallback, client, host, **kwargs):
            self.host = host

        def stream_response(self, prompt):
            tool = self.host.route(prompt).tools[0]
            self.host.call(tool, {'path': str(outside)})
            yield 'never'
    monkeypatch.setattr('hanni.mcp.session.McpToolSession', MaliciousSession)
    with pytest.raises(ValueError, match='fixed synthetic fixture'):
        service._file_read({'endpoint_id': None, 'settings': {'max_rounds': 3}}, case, SimpleNamespace(telemetry=[]))
    assert attempted == []

def test_unreachable_remote_model_is_not_reported_unloaded(lab, monkeypatch):
    service, engine, _, _ = lab
    snapshot = engine.snapshot()
    sources = engine._inventory()
    remote = deepcopy(snapshot['endpoints'][0])
    remote.update(endpoint_id='worker:independent-remote', local=False, health='unhealthy', model_id=None, configured_model='configured-remote-27b', label='Independent remote', legacy_default=False, max_context_verified=None, enabled=True)
    worker = {'worker_id': 'independent-remote', 'node_id': 'remote-host', 'model_id': 'configured-remote-27b', 'startup': {'gpu_device': 'P40', 'cache_type_k': 'f16'}}
    source = {key: value for key, value in sources[0].items() if key != 'spec'}
    source.update(endpoint_id=remote['endpoint_id'], local=False, legacy_default=False, worker=worker)
    monkeypatch.setattr(engine, 'snapshot', lambda: snapshot | {'endpoints': snapshot['endpoints'] + [remote]})
    monkeypatch.setattr(engine, '_inventory', lambda: sources + [source])
    row = next((row for row in service.inventory() if row['endpoint_id'] == remote['endpoint_id']))
    assert row['available'] is False and row['installed'] is None
    assert row['loaded'] is None, 'A transport failure is not proof that remote inference weights are unloaded.'
    assert row['configured_gpu'] == 'P40'

def test_original_long_prompt_preflight_rejects_before_model_scoring(lab, monkeypatch):
    service, engine, _, _ = lab
    calls = response_fixture(monkeypatch, engine)
    prompt = module.corpus('structured-development')[1]['prompt']
    assert 'line 0399' in prompt and 'AUTHORITATIVE_CODE=coral-8427' in prompt
    result = service.preflight('structured-development', 'local:supervisor', 2, 192)
    assert result['eligible'] is False
    assert any((row['id'] == 'long' for row in result['unsupported_cases']))
    with pytest.raises(ValueError):
        service.start(settings(cases=2))
    assert not calls and (not service.snapshot()['runs'])

def test_large_export_is_bounded_and_continues_without_omitting_cases(lab, monkeypatch):
    service, _, _, _ = lab

    def evaluate(run, case):
        return {'id': case['id'], 'passed': False, 'score': 0, 'latency_ms': 1, 'disclosure': 'Large synthetic export fixture; no model inference.', 'bounded_failure_evidence': 'Synthetic failure evidence. ' * 9700}
    monkeypatch.setattr(service, '_evaluate', evaluate)
    run = finished(service, service.start(settings('routing-development', cases=35))['id'], timeout=30)
    first = service.export(run['run']['id'])
    assert first['export_complete'] is False and first['next_offset'] == len(first['results'])
    assert 0 < first['next_offset'] < 35
    second = service.export(run['run']['id'], offset=first['next_offset'])
    assert second['export_complete'] is True and second['next_offset'] is None
    assert [case['ordinal'] for case in first['results'] + second['results']] == list(range(35))
