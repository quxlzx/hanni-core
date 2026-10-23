"""Generic actual cached-model adapter; no sealed goal, answer or case mapping.

Preparation imports do not start a process. Only final coordinator GO permits
OwnedConfiguredRuntime entry. No download fallback and no production assistant.
"""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time

from hanni.config.loader import load_config
from hanni.models.client import LlamaCppClient
from hanni.models.manager import ModelManager, current, install

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def final_manifest():
    """Hash raw public runtime/config/frontend/package bytes, not private stores."""
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    names = [name for name in tracked if name and (
        name.startswith('src/hanni/') and '/evals/' not in name and name.endswith('.py')
        or name.startswith('config/')
        or name.startswith('frontend/src/')
        or name in {'pyproject.toml', 'frontend/package.json', 'frontend/package-lock.json',
                    'frontend/tsconfig.json', 'frontend/vite.config.ts', 'scripts/build_desktop.ps1'})]
    names.extend(['src/hanni/dashboard/static/app.js', 'src/hanni/dashboard/static/style.css'])
    files = {name: digest(ROOT / name) for name in sorted(set(names)) if (ROOT / name).is_file()}
    exe = ROOT / 'dist/HANNI OS/HANNI OS.exe'
    if exe.is_file():
        files['dist/HANNI OS/HANNI OS.exe'] = digest(exe)
    encoded = json.dumps(files, sort_keys=True, separators=(',', ':')).encode()
    return {'sha256': hashlib.sha256(encoded).hexdigest(), 'files': files,
            'scope': 'Raw tracked production Python excluding evals; tracked config; frontend source/package/lock/build settings; compiled app.js/style.css and portable executable. No credentials, private stores, evaluation inputs or weights.'}


class RecordingActualClient:
    """Delegate untouched original inference; measure full returned JSON latency."""
    def __init__(self, client):
        self.original = client
        self.calls = []

    def chat(self, messages, **kwargs):
        record = {'response_format': kwargs.get('response_format'),
                  'temperature_override': kwargs.get('temperature'),
                  'max_tokens_override': kwargs.get('max_tokens')}
        started = time.perf_counter()
        try:
            result = self.original.chat(messages, **kwargs)
            record.update(ok=True, characters=len(result), returned_json=result)
            return result
        except Exception as error:
            record.update(ok=False, error_class=type(error).__name__)
            raise
        finally:
            record['full_inference_ms'] = (time.perf_counter() - started) * 1000
            self.calls.append(record)


class OwnedConfiguredRuntime:
    """Original ModelManager/start_model/stop_owned with one existing GGUF only."""
    def __init__(self, data_dir, model_file, *, startup_timeout=180):
        supplied = Path(model_file)
        if not supplied.is_file() or supplied.stat().st_size < 1024 * 1024:
            raise RuntimeError('Existing cached GGUF missing; downloads are not permitted.')
        self.model_file = supplied.resolve()
        self.config = load_config(ROOT / 'config', data_dir=Path(data_dir).resolve(), env={})
        with socket.socket() as connection:
            connection.bind(('127.0.0.1', 0))
            port = connection.getsockname()[1]
        self.spec = replace(self.config.models.supervisor, endpoint=f'http://127.0.0.1:{port}/v1')
        self.config = replace(self.config, models=replace(self.config.models, models=(self.spec,)))
        self.manager = ModelManager(self.config, startup_timeout=startup_timeout,
                                    model_files={self.spec.id: str(self.model_file)})
        self.previous_manager = None
        self.client = RecordingActualClient(LlamaCppClient(self.spec, max_attempts=1))
        self.settings = {'configured_model': asdict(self.spec),
                         'endpoint_change': 'Fresh owned loopback port only; no model/context/GPU/config sampling overrides.',
                         'weights_file': str(self.model_file), 'weights_sha256': digest(self.model_file),
                         'client_max_attempts': 1,
                         'workflow_sampling': 'Production planner temperature0/max_tokens3072; production analysis temperature0/max_tokens2048. Configured chat sampling is recorded separately.',
                         'timing': 'Each chat measures complete original response. Startup measured separately. No first-token or independently sensed audible timing.'}

    def __enter__(self):
        self.previous_manager = current()
        if self.previous_manager is not None:
            raise RuntimeError('An existing in-process model manager is present; refuse ownership replacement.')
        started = time.perf_counter()
        try:
            self.manager.start()
            install(self.manager)
            entry = self.manager.ensure_loaded(self.spec.id)
            self.settings['startup_ms'] = (time.perf_counter() - started) * 1000
            self.settings['owned_pid'] = getattr(entry.process, 'pid', None)
            if entry.process is None:
                raise RuntimeError('Fresh isolated model endpoint was externally occupied; no owned proof.')
            self.settings['runtime_command'] = list(entry.command)
            return self
        except BaseException:
            self.manager.close()
            install(self.previous_manager)
            raise

    def __exit__(self, *_):
        entry = self.manager.entries[self.spec.id]
        process = entry.process
        self.manager.close()
        install(self.previous_manager)
        self.settings['owned_closed'] = process is None or process.poll() is not None


def write_freeze_manifest(path):
    Path(path).write_text(json.dumps(final_manifest(), indent=2), encoding='utf-8')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Write a raw public freeze manifest; never start a model.')
    parser.add_argument('--manifest', type=Path, required=True)
    write_freeze_manifest(parser.parse_args().manifest)
