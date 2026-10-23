"""Original admission and controlled transport tests, not live cluster evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from hanni.compute.registry import ComputeRegistry
from hanni.compute.scheduler import ComputeScheduler
from scripts.campaign6_scheduling.author import CATEGORIES
from scripts.campaign6_scheduling.runner import grade, run_case
REPO = Path(__file__).resolve().parents[2]
INPUTS = REPO / 'evals/compute/campaign6_development.json'
ORACLES = REPO / 'evals/compute/campaign6_development_oracles.json'

def test_prospective_corpus_is_balanced_substantive_and_unchanged():
    cases = json.loads(INPUTS.read_text())['cases']
    oracles = json.loads(ORACLES.read_text())['oracles']
    assert len(cases) >= 50 and all((sum((c['category'] == category for c in cases)) >= 6 for category in CATEGORIES))
    assert len({c['id'] for c in cases}) == len(cases)
    assert {c['id'] for c in cases} == {o['id'] for o in oracles}
    assert len({c['description'] for c in cases}) == len(cases)
    assert all((not set(c) & {'expected', 'oracle', 'checker_inputs'} for c in cases))
    assert hashlib.sha256(INPUTS.read_bytes()).hexdigest() == 'a33e83c0f6b3c7ab4f5b99b85bcf429675889ee3f56726fb6e29f2e193cd7a5b'
    assert hashlib.sha256(ORACLES.read_bytes()).hexdigest() == '771a3a42d20d3104c82e3f698726ae1de8f87c4f9bede25d11727d1f0696bcee'

def test_execution_refuses_oracles_before_touching_storage(tmp_path):
    with pytest.raises(ValueError, match='Oracles'):
        run_case({'expected': True}, tmp_path / 'forbidden')
    assert not (tmp_path / 'forbidden').exists()

@pytest.mark.parametrize('timestamp,expected', [(1000, True), (999.5, True), (970, True), (969.99, False), (None, False), (1000.01, False), (True, False), (False, False), ('1000', False), (float('nan'), False), (float('inf'), False), (-1, False)])
@pytest.mark.parametrize('gpu', [False, True])
def test_original_remote_resource_guard_requires_current_typed_sample(tmp_path, timestamp, expected, gpu):
    root = tmp_path / 'owned'
    (root / 'compute').mkdir(parents=True)
    worker = {'worker_id': 'w', 'node_id': 'controlled_remote', 'enabled': True, 'model_id': 'controlled', 'remote_port': 1, 'concurrency': 1, 'allowed_categories': ['synthetic']}
    if gpu:
        worker['gpu'] = 'controlled-GPU'
    (root / 'compute/deployment.json').write_text(json.dumps({'version': 1, 'enabled': True, 'nodes': [{'id': 'controlled_remote'}], 'workers': [worker], 'policy': {'timeout_seconds': 1, 'max_retries': 0}}))
    registry = ComputeRegistry(root, clock=lambda: 1000)
    engine = ComputeScheduler(registry)
    try:
        row = {'worker_id': 'w', 'node_id': 'controlled_remote', 'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': 1024 ** 3 if gpu else None, 'gpu': 'controlled-GPU' if gpu else None, 'resource_sampled_at': timestamp}
        assert engine._resources_admissible(row) is expected
    finally:
        engine.close()

def test_unknown_local_cpu_resources_preserve_original_compatibility(tmp_path):
    root = tmp_path / 'owned'
    (root / 'compute').mkdir(parents=True)
    worker = {'worker_id': 'w', 'node_id': 'local', 'enabled': True, 'model_id': 'controlled', 'local_url': 'http://127.0.0.1:1', 'allowed_categories': ['synthetic']}
    (root / 'compute/deployment.json').write_text(json.dumps({'version': 1, 'enabled': True, 'nodes': [], 'workers': [worker]}))
    registry = ComputeRegistry(root)
    engine = ComputeScheduler(registry)
    try:
        assert engine._resources_admissible({'worker_id': 'w', 'node_id': 'local', 'ram_available_bytes': None, 'vram_free_bytes': None})
        assert not engine._resources_admissible({'worker_id': 'w', 'node_id': 'local', 'ram_available_bytes': 0, 'vram_free_bytes': None})
    finally:
        engine.close()

@pytest.mark.parametrize('identifier', ['C6DEV-correct_worker_selection-01', 'C6DEV-worker_busy-03', 'C6DEV-parallel_tasks-01', 'C6DEV-queue_saturation-01', 'C6DEV-network_interruption-01', 'C6DEV-supplemental_controls-02', 'C6DEV-result_verification-01', 'C6DEV-insufficient_vram-06', 'C6DEV-context_too_large-02'])
def test_original_selected_guarded_paths_retain_receipts_readback_and_cleanup(tmp_path, identifier):
    cases = {c['id']: c for c in json.loads(INPUTS.read_text())['cases']}
    oracles = {o['id']: o for o in json.loads(ORACLES.read_text())['oracles']}
    receipt = run_case(deepcopy(cases[identifier]), tmp_path / 'case')
    result = grade(receipt, oracles[identifier])
    assert result['passed'], result
    assert receipt['real_model'] is False and receipt['real_cluster'] is False
    for calls in receipt['provider_calls'].values():
        assert all((call['path'] == '/v1/chat/completions' and call['request_sha256'] for call in calls))

@pytest.mark.parametrize('configured,reported,verified,required,expected', [(256, 8192, 8192, 1000, False), (8192, 256, 8192, 1000, False), (8192, 8192, 256, 1000, False), (1024, 1024, 1024, 1024, True), (1024, 1024, 1024, 1025, False), (None, None, 8192, 1000, True), (None, 1024, 8192, 1000, True), (1024, None, 8192, 1000, True), (8192, 8192, True, 1, False)])
def test_known_context_bounds_cannot_be_overridden_by_old_larger_proof(configured, reported, verified, required, expected):
    assert ComputeScheduler._context_admissible({'context_configured': configured, 'context_reported': reported, 'max_context_verified': verified}, required) is expected

@pytest.mark.parametrize('identifier', ['C6SUP-' + str(i).zfill(2) for i in range(1, 11)])
def test_prospective_corrected_controls_are_separate_from_original_scores(tmp_path, identifier):
    cases = {c['id']: c for c in json.loads((REPO / 'evals/compute/campaign6_development_supplement.json').read_text())['cases']}
    refs = {o['id']: o for o in json.loads((REPO / 'evals/compute/campaign6_development_supplement_oracles.json').read_text())['oracles']}
    receipt = run_case(deepcopy(cases[identifier]), tmp_path / 'case')
    verdict = grade(receipt, refs[identifier])
    assert verdict['passed'], verdict

def test_aggregate_keeps_harness_dispatch_and_unknown_cleanup_separate(tmp_path):
    from scripts.campaign6_scheduling.metrics import collect
    scores = [{'id': 'failed-before-receipt', 'category': 'parallel_tasks', 'passed': False, 'harness_error': {'class': 'RuntimeError', 'message': 'Controlled boundary not reached'}, 'provider_calls': {'owned': [{'path': '/v1/chat/completions'}]}, 'maximum_overlap': 1}, {'id': 'failed-before-diagnostics', 'category': 'parallel_tasks', 'passed': False, 'harness_error': {'class': 'ValueError', 'message': 'Invalid fixture'}}]
    (tmp_path / 'progress.json').write_text(json.dumps(scores))
    metrics = collect(tmp_path)
    assert metrics['cases'] == 2 and metrics['strict_pass'] == 0 and (metrics['harness_errors'] == 2)
    assert metrics['controlled_provider_http_posts'] == 1 and metrics['harness_error_http_posts'] == 1
    assert metrics['harness_errors_without_cleanup_diagnostics'] == 2
    assert metrics['dependency_bytes_stable_during_cases'] is None
    assert metrics['model_accuracy'] is None and metrics['real_cluster_model_responses'] == 0
