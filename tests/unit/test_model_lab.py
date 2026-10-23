"""Focused protocol/admission, durability, and optional dashboard boundaries."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from uuid import uuid4
import pytest
from hanni.config import load_config
from hanni.dashboard.server import DashboardServer
from hanni.evals import model_lab as module
from hanni.evals.model_lab import ModelLab, digest
from hanni.models.adaptive import AdaptiveModelEngine
from hanni.reliability.execution import close_service
ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture
def lab(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    engine = AdaptiveModelEngine(config, local_probe=lambda row: {'status': 'healthy', 'model_id': config.models.supervisor.api_model, 'last_heartbeat': time.time(), 'context_reported': 16384, 'runtime_identity': 'controlled-unit-runtime', 'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': 3 * 1024 ** 3})
    engine.refresh()
    service = ModelLab(config, engine)
    yield service
    service.close()
    if service.thread:
        service.thread.join(3)
    engine.close()
    close_service(tmp_path)

def settings(**changes):
    return {'suite_id': 'structured-development', 'endpoint_id': 'local:supervisor', 'max_cases': 1, 'repetitions': 1, 'max_tokens': 192, 'max_rounds': 3} | changes

def wait(service, run_id):
    service.thread.join(5)
    assert not service.thread.is_alive()
    return service.detail(run_id)

def test_exact_frozen_long_case_is_rejected_before_any_dispatch(lab, monkeypatch):
    calls = []
    monkeypatch.setattr(lab.engine, 'execute', lambda *args, **kwargs: calls.append(args))
    preflight = lab.preflight('structured-development', 'local:supervisor', 2, 192)
    assert preflight['eligible'] is False
    assert preflight['unsupported_cases'][0]['id'] == 'long'
    assert preflight['unsupported_cases'][0]['required_context_upper_bound'] > 16384
    with pytest.raises(ValueError, match='context admission'):
        lab.start(settings(max_cases=2))
    assert calls == [] and lab.snapshot()['runs'] == []

def test_execution_uses_captured_cases_after_corpus_changes(lab, monkeypatch):
    captured, entered, release = ([], threading.Event(), threading.Event())
    original = module.corpus

    def evaluate(run, case):
        entered.set()
        assert release.wait(3)
        captured.append(deepcopy(case))
        return {'id': case['id'], 'passed': True, 'score': 100, 'expected': case['expected'], 'latency_ms': 1}
    monkeypatch.setattr(lab, '_evaluate', evaluate)
    run = lab.start(settings())
    assert entered.wait(3)
    monkeypatch.setattr(module, 'corpus', lambda _id: [{'id': 'changed', 'expected': {'modified': True}}])
    release.set()
    result = wait(lab, run['id'])
    assert captured == original('structured-development')[:1]
    assert result['run']['selection_sha256'] == digest(captured)
    assert result['cases'][0]['expected'] == {'serial': 8427, 'available': False}

def test_metrics_use_original_v42_percentile_convention_and_real_denominators(lab):
    run_id = str(uuid4())
    for ordinal, latency in enumerate([1, 2, 3, 4, 100]):
        row = {'id': str(ordinal), 'passed': ordinal != 4, 'score': 100 if ordinal != 4 else 0, 'latency_ms': latency, 'verified_task_success': None, 'inference': [{'performance': {'generation_tps': 10}}] if ordinal < 2 else []}
        lab.db.execute('INSERT INTO cases VALUES(?,?,?)', (run_id, ordinal, json.dumps(row)))
    lab.db.commit()
    summary = lab._summary(run_id)
    assert summary['latency_p50_ms'] == 3 and summary['latency_p95_ms'] == 100
    assert summary['latency_samples'] == 5 and summary['pass_rate_percent'] == 80
    assert summary['metric_sample_counts'] == {'generation_tps': 2, 'prompt_tps': 0, 'ttft_ms': 0}
    assert summary['mean_generation_tps'] == 10 and summary['mean_ttft_ms'] is None
    assert summary['verified_task_success_percent'] is None

def test_server_side_history_search_finds_oldest_beyond_first_page(lab, monkeypatch):
    monkeypatch.setattr(lab, '_launch', lambda *args: None)
    template = lab.start(settings())
    for index in range(121):
        row = deepcopy(template)
        row.update(id=str(uuid4()), status='completed', created_at=index, completed=1, suite_name='Oldest needle' if index == 0 else 'Recent fixture')
        lab._save(row)
    first = lab.snapshot()
    assert len(first['runs']) == 100 and first['history_has_more'] is True
    oldest = lab.snapshot({'q': 'Oldest needle'})
    assert oldest['history_count'] == 1 and oldest['runs'][0]['created_at'] == 0
    by_filename = lab.snapshot({'q': lab.config.models.supervisor.model_file})
    assert by_filename['history_count'] == 122
    assert all((r['model']['configured_model_file'] == lab.config.models.supervisor.model_file for r in by_filename['runs']))
    second = lab.snapshot({'offset': '100', 'limit': '100'})
    assert len(second['runs']) == 22 and (not second['history_has_more'])

def test_large_export_has_bounded_pages_and_complete_prefix(lab, monkeypatch):
    monkeypatch.setattr(lab, '_launch', lambda *args: None)
    run = lab.start(settings(repetitions=5))
    run.update(status='completed', completed=20, total=20)
    for ordinal in range(20):
        row = {'id': str(ordinal), 'ordinal': ordinal, 'passed': True, 'score': 100, 'final_answer': 'x' * 500000, 'latency_ms': 1}
        row['evidence_sha256'] = digest(row)
        lab.db.execute('INSERT INTO cases VALUES(?,?,?)', (run['id'], ordinal, json.dumps(row)))
    lab._save(run)
    first = lab.export(run['id'], limit=5)
    assert len(first['results']) == 5 and first['next_offset'] == 5
    rows = first['results']
    while not first['export_complete']:
        first = lab.export(run['id'], offset=first['next_offset'], limit=5)
        rows.extend(first['results'])
    assert [r['ordinal'] for r in rows] == list(range(20))

def test_optional_corrupt_lab_store_preserves_dashboard_startup(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    directory = tmp_path / 'model-lab'
    directory.mkdir()
    evidence = b'controlled corrupt store; retain exact bytes'
    (directory / 'runs.sqlite3').write_bytes(evidence)
    server = DashboardServer(0, SimpleNamespace(config=config, snapshot=lambda: {}), shutdown_event=threading.Event())
    try:
        state = server.model_lab.snapshot()
        assert state['available'] is False and state['controls']['start']['enabled'] is False
        assert server.workflows is not None and server.model_routing is not None and (server.chat is not None)
        assert (directory / 'runs.sqlite3').read_bytes() == evidence
    finally:
        server.server_close()
        server.chat.close()
        server.chat.db.close()
        close_service(tmp_path)

def test_configuration_fingerprint_includes_behavior_but_not_live_load(lab):
    first = digest(lab._configuration('local:supervisor'))
    lab.engine.active['local:supervisor'] = 1
    assert digest(lab._configuration('local:supervisor')) == first
    user = replace(lab.config.hanni.user, timezone='UTC')
    lab.config = replace(lab.config, hanni=replace(lab.config.hanni, user=user))
    assert digest(lab._configuration('local:supervisor')) != first

def test_package_local_scorer_hash_does_not_require_checkout(lab, monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'REPO', tmp_path / 'missing-checkout')
    assert len(module.scorer_digest('structured-development')) == 64
    state = lab.snapshot()
    assert next((s for s in state['suites'] if s['id'] == 'structured-development'))['enabled'] is True
    assert next((s for s in state['suites'] if s['id'] == 'llm-tools-development'))['enabled'] is False

def test_serialized_export_preserves_float_hashes_large_nested_objects_and_current_redaction(lab, monkeypatch):
    monkeypatch.setattr(lab, '_launch', lambda *args: None)
    run = lab.start(settings())
    run.update(status='completed', completed=1)
    assert type(run['configuration']['model']['top_p']) is float
    prose = 'Measured fixture text with spaces. ' * 7000
    row = {'id': 'float-evidence', 'ordinal': 0, 'score': 100.0, 'latency_ms': 1500.0, 'inference': [{'latency_ms': 0.0}], 'expected': {'text': 'quoted "brace { }" / 雪'}, 'actual': {'first': prose, 'second': prose}, 'final_answer': 'new_secret_canary_624834'}
    row = module.redact(row)
    row['evidence_sha256'] = digest(row)
    lab.db.execute('INSERT INTO cases VALUES(?,?,?)', (run['id'], 0, json.dumps(row)))
    lab._save(run)
    from hanni.logs import redaction
    monkeypatch.setattr(redaction, '_registry', {})
    redaction.register_secret('SERIALIZED_EXPORT_TEST', 'new_secret_canary_624834')
    page = lab.export(run['id'], representation='serialized')
    decoded_run = json.loads(page['run_json'])
    decoded_case = json.loads(page['results_json'][0])
    assert len(page['results_json'][0]) > 262144
    assert '"latency_ms":1500.0' in page['results_json'][0]
    assert '"latency_ms":0.0' in page['results_json'][0]
    assert type(decoded_case['latency_ms']) is float
    assert digest(decoded_run['configuration']) == decoded_run['configuration_sha256']
    assert digest({k: v for k, v in decoded_case.items() if k != 'evidence_sha256'}) == decoded_case['evidence_sha256']
    assert decoded_case['actual']['first'] == prose and decoded_case['actual']['second'] == prose
    assert decoded_case['expected']['text'] == 'quoted "brace { }" / 雪'
    assert 'new_secret_canary_624834' not in json.dumps(page)
    assert lab.export(run['id'])['results'][0] == decoded_case
    assert len(json.dumps(page).encode()) < 16 * 1024 ** 2
    with pytest.raises(ValueError, match='representation'):
        lab.export(run['id'], representation='raw')
