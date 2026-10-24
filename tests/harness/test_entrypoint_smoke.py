"""Installed Python entry point with actual config/client and controlled HTTP."""
import os
import subprocess
import sys

from tests.helpers import write_config_dir
from .fakes import ModelService


def test_cli_chat_subprocess_uses_fake_provider_without_model_or_devices(tmp_path):
    model = ModelService()
    model.content = 'OFFLINE_HARNESS_OK'
    try:
        config = write_config_dir(tmp_path / 'config', {'models.yaml': {'models': [{
            'id': 'supervisor', 'role': 'supervisor', 'backend': 'llama.cpp', 'model_file': 'fixture.gguf',
            'api_model': 'fixture', 'endpoint': model.endpoint, 'keep_loaded': True, 'context_length': 65536,
            'max_tokens': 128, 'health_timeout_seconds': 1, 'request_timeout_seconds': 3}]}})
        env = {key: value for key, value in os.environ.items() if not key.startswith('HANNI_')}
        command = [sys.executable, '-m', 'hanni.cli', 'chat', 'Say hello without using tools.',
                   '--config-dir', str(config), '--data-dir', str(tmp_path / 'data'),
                   '--env-file', str(tmp_path / 'absent.env'), '--no-file-log']
        result = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        assert 'OFFLINE_HARNESS_OK' in result.stdout
        assert model.requests
    finally:
        model.close()
