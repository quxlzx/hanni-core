"""Runtime OS facts reach the model; Windows command lines keep their quoting."""
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from hanni.core import host_environment as host
from hanni.native import local_tools, worker
from hanni.hermes.state import TaskStore
from tests.test_native_loop import FakeClient


def test_detected_windows_guidance_distinguishes_user_powershell_from_direct_execution(monkeypatch):
    monkeypatch.setattr(host.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(host.platform, 'release', lambda: '11')
    monkeypatch.setattr(host.platform, 'machine', lambda: 'AMD64')
    facts = host.host_facts(workspace=r'C:\workspace', terminal_cwd=r'C:\workspace\sessions\child')
    assert facts['operating_system'] == 'Windows' and facts['os_release'] == '11'
    assert facts['user_command_syntax'] == 'PowerShell'
    prompt = host.host_environment_prompt(workspace=r'C:\workspace')
    assert 'shell=False' in prompt and 'not a PowerShell, cmd.exe, or Bash session' in prompt
    assert 'local_list_dir' in prompt and 'local_python' in prompt
    assert 'inference server' in prompt and 'remote tool' in prompt


def test_actual_linux_worker_is_not_mislabeled_as_windows(monkeypatch):
    monkeypatch.setattr(host.platform, 'system', lambda: 'Linux')
    assert host.host_facts()['user_command_syntax'] == 'POSIX shell'
    assert 'This execution host runs Windows.' not in host.host_environment_prompt()


@pytest.mark.parametrize('context', [{}, {'scheduled_job_id': 'fixture-daily'},
    {'parent_task_id': 'fixture-parent', 'allowed_tools': ['local_list_dir']}])
def test_every_native_task_gets_host_facts_in_system_prompt_not_user_context(tmp_path, monkeypatch, context):
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    context = {**context, 'environment': {'operating_system': 'InventedLinux', 'shell': 'bash'}}
    task = store.submit('environment-test', {'prompt': 'Which OS and terminal should you use?', 'windows_tools': [],
                                           'origin': 'hanni', 'context': context})
    client = FakeClient([{'message': {'content': 'Use the detected execution environment.'}}])
    client.max_tokens = 1200
    monkeypatch.setattr(worker, 'NativeClient', lambda config: client)
    monkeypatch.setattr(worker, 'load_model', lambda: {'context_length': 65536})
    monkeypatch.setattr(worker, 'load_soul', lambda: '')
    monkeypatch.setattr('hanni.native.mcp_client.discover', lambda root: [])
    try:
        worker.run(store.path, task['id'], {'entries': []})
        assert client.calls, store.get(task['id'])
        system = client.calls[0]['messages'][0]
        assert system['role'] == 'system'
        assert 'Detected execution environment (trusted runtime facts)' in system['content']
        assert json.dumps(host.host_facts()['operating_system']) in system['content']
        assert 'InventedLinux' not in system['content']
        expected_cwd = tmp_path / 'workspace'
        if context.get('parent_task_id'): expected_cwd = expected_cwd / 'sessions' / task['id']
        assert json.dumps(str(expected_cwd))[1:-1] in system['content']
        assert store.get(task['id'])['state'] == 'review_required'
    finally: store.close()


@pytest.mark.skipif(os.name != 'nt', reason='Windows command-line parser')
@pytest.mark.parametrize('argv', [
    ['python', '-c', "print('hi')"],
    ['git.exe', 'status', '--', r'C:\folder\notes.txt'],
    ['python', '-c', 'print(\'a "quoted" value\')', 'C:\\folder with spaces\\tail\\', ''],
])
def test_windows_argv_roundtrips_quotes_spaces_and_backslashes(argv):
    assert local_tools._split_command(subprocess.list2cmdline(argv)) == argv


@pytest.mark.skipif(os.name != 'nt', reason='Windows executable dispatch')
@pytest.mark.parametrize('path', [r'folder\notes.txt', r'C:\folder with spaces\report.txt'])
def test_real_windows_python_receives_exact_path(tmp_path, path):
    command = subprocess.list2cmdline(['PYTHON.EXE', '-c', "print(__import__('sys').argv[1])", path])
    result = local_tools.execute_local('local_terminal', {'command': command}, tmp_path)
    assert result['ok'], result
    assert result['data']['stdout'].strip() == path


def test_posix_parser_retains_posix_semantics(monkeypatch):
    monkeypatch.setattr(local_tools, 'os', SimpleNamespace(name='posix'))
    assert local_tools._split_command("python3 -c 'print(42)' 'file name.txt'") == ['python3', '-c', 'print(42)', 'file name.txt']


def test_null_characters_and_shell_composition_remain_blocked():
    assert local_tools._check_command('python\0 -c print(1)')
    for command in ('python -V | findstr Python', 'python -V && whoami', 'powershell -Command Get-ChildItem'):
        assert local_tools._check_command(command)


@pytest.mark.skipif(os.name != 'nt', reason='Windows recovery hints')
def test_linux_or_shell_commands_get_windows_specific_recovery_guidance(tmp_path):
    problem = local_tools._check_command('Get-ChildItem')
    assert 'Windows' in problem and 'local_list_dir' in problem
    with patch.object(local_tools.subprocess, 'run', side_effect=FileNotFoundError):
        result = local_tools.execute_local('local_terminal', {'command': 'ls'}, tmp_path)
    assert result['error_code'] == 'EXECUTABLE_NOT_FOUND'
    assert result['operating_system'] == 'Windows' and 'not PowerShell' in result['hint']


def test_terminal_schema_tells_model_the_actual_host_and_execution_rules():
    tool = next(spec for spec in local_tools.local_tool_specs() if spec['name'] == 'local_terminal')
    description = tool['schema']['function']['description']
    assert host.host_facts()['operating_system'] in description
    assert 'shell=False' in description and 'No PowerShell cmdlets' in description


def test_host_facts_survive_context_compression():
    from hanni.native.compact import compact
    system = {'role': 'system', 'content': host.host_environment_prompt()}
    messages = [system]
    for i in range(20):
        messages.extend([{'role': 'user', 'content': f'Earlier request {i} ' + 'x' * 400},
                         {'role': 'assistant', 'content': 'Earlier observations ' + 'y' * 400}])
    client = FakeClient([{'message': {'content': 'Progress summary. Earlier OS assumptions were unverified.'}}])
    compacted = compact(messages, client, max_tokens=2000, keep_recent=4)
    assert len(compacted) < len(messages)
    assert compacted[0] == system
