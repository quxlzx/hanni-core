"""Additional gate contracts only; no real model request is sent by these tests."""
import pytest
from scripts.campaign8_ui.streaming import resource_gate, StreamingAdmissionError, streaming_config

@pytest.mark.parametrize('sample', [{'available_ram_bytes': 3072 * 1024 ** 2 - 1, 'used_percent': 80}, {'available_ram_bytes': True, 'used_percent': 80}, {'available_ram_bytes': 4000 * 1024 ** 2, 'used_percent': 90}, {'available_ram_bytes': 4000 * 1024 ** 2, 'used_percent': float('nan')}, {'available_ram_bytes': 4000 * 1024 ** 2, 'used_percent': None}])
def test_additional_streaming_gate_rejects_unknown_pressure_and_below_reserve(sample):
    with pytest.raises(StreamingAdmissionError):
        resource_gate(sample)

def test_gate_boundary_acceptance_does_not_replace_original_model_or_admission(tmp_path):
    resource_gate({'available_ram_bytes': 3072 * 1024 ** 2, 'used_percent': 89.9})
    config = streaming_config(tmp_path)
    assert config.paths.data_dir.resolve() == tmp_path.resolve()
    assert len(config.models.models) == 1
    assert config.models.supervisor.endpoint == 'http://127.0.0.1:8080/v1'
    assert config.models.supervisor.model_file == 'Qwen3.5-4B-Q4_K_M.gguf'
    assert config.models.supervisor.max_tokens == 64
    assert config.models.supervisor.request_timeout_seconds == 30
    assert config.models.ram_reserve_mb == 3072
    assert config.models.critical_ram_percent == 90
    assert config.hanni.mcp.enabled and config.hanni.memory.enabled
