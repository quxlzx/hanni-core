"""Native context bootstrap must retain deployment, privacy and resource gates."""
import json
import pytest
from hanni.compute import ComputeError
from scripts.campaign5_intelligence.controlled import controlled_engine, MESSAGES

@pytest.mark.parametrize('withdrawal', ['disabled', 'worker_disabled', 'privacy', 'ram', 'ram_unknown', 'ram_invalid', 'vram', 'vram_unknown', 'vram_invalid', 'context_configured', 'context_reported', 'closed', 'busy'])
def test_context_bootstrap_never_dispatches_without_original_authority(tmp_path, withdrawal):
    with controlled_engine(tmp_path, prove=False) as engine:
        path = tmp_path / 'compute/deployment.json'
        deployment = json.loads(path.read_text())
        if withdrawal == 'disabled':
            deployment['enabled'] = False
        elif withdrawal == 'worker_disabled':
            deployment['workers'][0]['enabled'] = False
        elif withdrawal == 'privacy':
            deployment['workers'][0]['allowed_categories'] = ['project']
        elif withdrawal.startswith('vram'):
            deployment['workers'][0]['gpu'] = 'controlled GPU'
        elif withdrawal == 'context_configured':
            deployment['workers'][0]['context_configured'] = 256
        path.write_text(json.dumps(deployment), encoding='utf8')
        engine.compute.registry.reload()
        if withdrawal == 'closed':
            engine.compute.closed = True
        elif withdrawal == 'busy':
            engine.compute.registry.active['controlled'] = 1
        if withdrawal == 'context_reported':
            original_health = engine.compute.transport.health
            engine.compute.transport.health = lambda worker: {**original_health(worker), 'context_reported': 256}
        original = engine.compute.transport.resources

        def resources(worker):
            return {**original(worker), **({'ram_available_bytes': 1024} if withdrawal == 'ram' else {'ram_available_bytes': None} if withdrawal == 'ram_unknown' else {'ram_available_bytes': float('nan')} if withdrawal == 'ram_invalid' else {'vram_free_bytes': 1024} if withdrawal == 'vram' else {'vram_free_bytes': None} if withdrawal == 'vram_unknown' else {'vram_free_bytes': False} if withdrawal == 'vram_invalid' else {})}
        engine.compute.transport.resources = resources
        with pytest.raises(ComputeError):
            engine.compute.verify_context('controlled', MESSAGES, target_tokens=512, expected='controlled source value', max_output_tokens=64)
        assert engine.compute.transport.calls == []
