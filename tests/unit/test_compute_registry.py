"""Durable context proofs, resource admission and controller-only controls."""
from copy import deepcopy
import json
import threading
from types import SimpleNamespace
from uuid import uuid4
import pytest
from hanni.compute import ComputeError, ComputeRegistry, ComputeScheduler
from hanni.dashboard.compute import ComputeControls

def registry(tmp_path):
    root = tmp_path / 'compute'
    root.mkdir()
    worker = {'worker_id': 'fixture', 'node_id': 'local', 'local_url': 'http://127.0.0.1:43210', 'model_id': 'fixture-model', 'enabled': True, 'capabilities': ['analysis', 'structured_json'], 'allowed_categories': ['synthetic'], 'concurrency': 1, 'context_configured': 8192}
    raw = {'version': 1, 'enabled': True, 'nodes': [], 'workers': [worker], 'policy': {}}
    (root / 'deployment.json').write_text(json.dumps(raw), encoding='utf8')
    return (ComputeRegistry(tmp_path), raw)

def prove(registry):
    registry.record_context_verified('fixture', target_tokens=8192, prompt_tokens=7500, model_id='fixture-model', prompt_sha256='a' * 64, response_sha256='b' * 64)

def test_context_receipt_survives_restart_but_does_not_invent_health(tmp_path):
    first, _ = registry(tmp_path)
    prove(first)
    first.close()
    next_registry = ComputeRegistry(tmp_path)
    row = next_registry.snapshot()['workers'][0]
    assert row['max_context_verified'] == 8192
    assert row['status'] == 'unknown'
    assert row['last_heartbeat'] is None
    next_registry.close()

def test_prior_stage_proof_authorizes_growth_without_advertising_new_capacity(tmp_path):
    first, raw = registry(tmp_path)
    prove(first)
    first.close()
    raw['workers'][0]['context_configured'] = 16384
    (tmp_path / 'compute/deployment.json').write_text(json.dumps(raw))
    next_registry = ComputeRegistry(tmp_path)
    assert next_registry.prior_verified_context('fixture') == 8192
    assert next_registry.snapshot()['workers'][0]['max_context_verified'] is None
    next_registry.close()

@pytest.mark.parametrize('change', ['model_id', 'local_url', 'gpu'])
def test_previous_context_proof_cannot_authorize_a_different_model_or_device(tmp_path, change):
    first, raw = registry(tmp_path)
    prove(first)
    first.close()
    raw['workers'][0][change] = {'model_id': 'different', 'local_url': 'http://127.0.0.1:43211', 'gpu': 'different-device'}[change]
    (tmp_path / 'compute/deployment.json').write_text(json.dumps(raw))
    next_registry = ComputeRegistry(tmp_path)
    assert next_registry.prior_verified_context('fixture') == 0
    assert next_registry.snapshot()['workers'][0]['max_context_verified'] is None
    next_registry.close()

def test_declared_large_context_and_short_prompt_never_create_a_proof(tmp_path):
    first, _ = registry(tmp_path)
    with pytest.raises(ComputeError):
        first.record_context_verified('fixture', target_tokens=131072, prompt_tokens=128, model_id='fixture-model', prompt_sha256='a' * 64, response_sha256='b' * 64)
    assert not (tmp_path / 'compute/context-measurements.json').exists()
    first.close()

def test_context_sharing_and_known_memory_pressure_gate_placement(tmp_path):
    first, _ = registry(tmp_path)
    prove(first)
    first.observe('fixture', status='healthy', last_heartbeat=first.clock(), ram_available_bytes=1024)
    scheduler = ComputeScheduler(first)
    assert scheduler._choices({'synthetic'}, 128) == []
    first.observe('fixture', ram_available_bytes=8 * 1024 ** 3)
    assert scheduler._choices({'project'}, 128) == []
    assert len(scheduler._choices({'synthetic'}, 128)) == 1
    scheduler.close()

def test_shutdown_blocks_controls_before_accessing_the_original_registry(tmp_path):
    first, _ = registry(tmp_path)
    scheduler = ComputeScheduler(first)
    stop = threading.Event()
    stop.set()

    class Features:

        @property
        def registry(self):
            raise AssertionError('A stopped dashboard must not reach execution authority.')
    controls = ComputeControls(Features(), scheduler, stop)
    with pytest.raises(RuntimeError, match='shutting down'):
        controls.execute({'id': str(uuid4()), 'worker_id': 'fixture', 'operation': 'configure', 'data': {'enabled': True}, 'confirmed': False})
    scheduler.close()

@pytest.mark.parametrize('cached,passed', [(7690, True), (0, False), (-1, False), (True, False)])
def test_anthropic_context_verification_counts_cached_input_and_rejects_invalid_usage(tmp_path, cached, passed):
    first, deployment = registry(tmp_path)
    deployment['workers'][0]['context_configured'] = 8448
    (tmp_path / 'compute/deployment.json').write_text(json.dumps(deployment), encoding='utf8')
    first.reload()
    response = {'usage': {'input_tokens': 7, 'cache_read_input_tokens': cached}, 'content': [{'type': 'text', 'text': '{"ledger": "alpha"}'}], 'stop_reason': 'end_turn'}
    transport = SimpleNamespace(health=lambda _worker: {'status': 'healthy', 'model_id': 'fixture-model', 'last_heartbeat': first.clock(), 'context_reported': 8448}, resources=lambda _worker: {'ram_available_bytes': None, 'vram_free_bytes': None}, request=lambda *_args, **_kwargs: response, close=lambda: None)
    scheduler = ComputeScheduler(first, transport=transport)
    try:
        result = scheduler.verify_context('fixture', [{'role': 'user', 'content': 'sealed synthetic ledger'}], target_tokens=8192, expected={'ledger': 'alpha'}, anthropic=True)
        assert result['passed'] is passed
        proof = tmp_path / 'compute/context-measurements.json'
        assert proof.exists() is passed
        if passed:
            assert result['observed_prompt_tokens'] == 7697
            assert json.loads(proof.read_text())['measurements']['fixture']['observed_prompt_tokens'] == 7697
    finally:
        scheduler.close()
