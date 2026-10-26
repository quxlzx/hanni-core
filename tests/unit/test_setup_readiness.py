"""One-command setup prepares a model and repairs per-user login shortcuts."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.test_stick import firstboot
from tests.unit.test_bundled_llama_runtime import builder

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('configure_local_install', ROOT / 'scripts/configure_local_install.py')
setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)


def gguf(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as stream:
        stream.write(b'GGUF\x03\0\0\0' + b'\0' * 16); stream.seek(1024**2); stream.write(b'\0')


def test_first_setup_downloads_small_starter_and_saves_64k_configuration(tmp_path):
    calls = []
    def download(command, **kwargs):
        calls.append(command); gguf(tmp_path / 'models' / setup.STARTER)
    result = setup.configure(tmp_path, run=download)
    assert result['model'] == setup.STARTER and not result['selection_retained']
    assert '--skip-binaries' in calls[0] and calls[0][calls[0].index('--tier') + 1] == '2b'
    selected = json.loads((tmp_path / 'state/model-selection.json').read_text())
    assert selected == {'source': 'local', 'local_model': setup.STARTER, 'context': 65536}
    assert setup.configure(tmp_path, run=lambda *a, **kw: pytest.fail('Do not redownload an installed model'))['selection_retained']


def test_existing_api_and_custom_model_selection_are_retained(tmp_path):
    state = tmp_path / 'state'; state.mkdir()
    path = state / 'model-selection.json'
    selected = {'source': 'api', 'endpoint': 'https://example.test/v1', 'api_model': 'work-model', 'context': 65536}
    path.write_text(json.dumps(selected))
    assert setup.configure(tmp_path, offline=True)['source'] == 'api'
    assert json.loads(path.read_text()) == selected
    selected = {'source': 'local', 'local_model': 'my-approved-model.gguf', 'context': 131072}
    path.write_text(json.dumps(selected)); gguf(tmp_path / 'models' / selected['local_model'])
    assert setup.configure(tmp_path, offline=True)['selection_retained']
    assert json.loads(path.read_text()) == selected


def test_offline_missing_or_incomplete_model_is_not_reported_ready(tmp_path):
    with pytest.raises(RuntimeError, match='Offline'): setup.configure(tmp_path, offline=True)
    target = tmp_path / 'models' / setup.STARTER; target.parent.mkdir(); target.write_bytes(b'incomplete')
    with pytest.raises(RuntimeError, match='incomplete'): setup.configure(tmp_path)
    assert target.read_bytes() == b'incomplete'


@pytest.mark.skipif(os.name != 'nt', reason='Windows runtime verification')
def test_missing_gpu_driver_does_not_fail_a_working_cpu_install():
    def run(command, **kwargs):
        return SimpleNamespace(returncode=1 if 'windows-vulkan' in str(command[0]) else 0)
    with patch.object(builder.subprocess, 'run', side_effect=run):
        result = builder.verify(Path('runtime'))
    assert result['cpu_ready'] and not result['gpu_runtime_ready'] and result['warnings']


@pytest.mark.skipif(os.name != 'nt', reason='Windows runtime verification')
def test_blocked_cpu_runtime_has_an_actionable_managed_laptop_error():
    with patch.object(builder.subprocess, 'run', side_effect=PermissionError('Access denied')):
        with pytest.raises(RuntimeError, match='managed work laptop'): builder.verify(Path('runtime'))


def test_picker_checks_server_execution_not_only_benchmark(tmp_path, monkeypatch):
    monkeypatch.setattr(firstboot, 'STICK', tmp_path)
    monkeypatch.delenv('HANNI_LLAMA_RUNTIME_DIR', raising=False)
    folder = tmp_path / 'binaries' / ('windows-x86_64' if os.name == 'nt' else 'linux-x86_64')
    folder.mkdir(parents=True)
    for name in ('llama-bench', 'llama-server'): (folder / name).write_bytes(b'fixture')
    def run(command, **kwargs): return SimpleNamespace(returncode=0xC0000135 if 'llama-server' in str(command[0]) else 0)
    with patch.object(firstboot.subprocess, 'run', side_effect=run):
        assert firstboot.pick_binary(firstboot.Facts()) is None
    assert 'llama-server' in ';'.join(firstboot._binary_probe_errors)


@pytest.mark.skipif(os.name != 'nt', reason='Windows automatic runtime repair')
def test_first_launch_repairs_missing_runtime_once(tmp_path, monkeypatch):
    monkeypatch.setattr(firstboot, 'CORE', tmp_path)
    helper = tmp_path / 'scripts/prepare_llama_runtime.py'; helper.parent.mkdir(); helper.write_text('fixture')
    with patch.object(firstboot, 'pick_binary', side_effect=[None, tmp_path / 'runtime']), \
         patch.object(firstboot.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
        assert firstboot.ensure_binary(firstboot.Facts()) == tmp_path / 'runtime'
    assert run.call_count == 1 and '--verify' in run.call_args.args[0]


def test_wait_requires_a_ready_assistant_not_only_an_open_dashboard(monkeypatch):
    states = iter([{'present': True, 'ready': False}, {'present': True, 'ready': True}])
    monkeypatch.setattr(setup, 'local_status', lambda: next(states))
    with patch.object(setup.time, 'sleep') as sleep:
        setup.wait_for_assistant(timeout=2)
    assert sleep.call_count == 1


def test_open_disconnected_desktop_repair_keeps_exact_desktop_lifetime(tmp_path, monkeypatch):
    import psutil
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'profile'))
    desktop = SimpleNamespace(pid=12345, info={'pid': 12345, 'exe': str(tmp_path / 'dist/HANNI OS/HANNI OS.exe')},
                              children=lambda **kwargs: [], is_running=lambda: True)
    monkeypatch.setattr(psutil, 'process_iter', lambda *args: [desktop])
    states = iter([{'present': False, 'ready': False}, {'present': True, 'ready': True}])
    monkeypatch.setattr(setup, 'local_status', lambda: next(states))
    with patch.object(setup.subprocess, 'Popen', return_value=SimpleNamespace(poll=lambda: None)) as popen:
        setup.repair_open_desktop(tmp_path, timeout=2)
    command = popen.call_args.args[0]
    assert command[command.index('--desktop-owner-pid') + 1] == '12345'
    assert '--ready-file' in command and '--no-browser' in command
    assert popen.call_args.kwargs['cwd'] == tmp_path
