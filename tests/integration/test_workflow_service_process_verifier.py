"""Real owned process death/suspension and original Service lease recovery."""
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import time
import pytest
from hanni.workflows.types import WorkflowError, WorkflowLimits
from scripts.v3_review.service_fixture import ServiceFixture

def wait_file(path, process, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
        if process.poll() is not None:
            raise AssertionError('Owned probe stopped before committing evidence: ' + process.communicate()[1])
        time.sleep(0.02)
    raise AssertionError('Owned probe failed to produce boundary evidence.')

def launch(root, mode, target='write'):
    return subprocess.Popen([sys.executable, '-m', 'scripts.v3_review.service_process_probe', '--root', str(root), '--mode', mode, '--target', target], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def write_audit(root):
    path = root / 'run' / 'state' / 'logs' / 'tool_audit.jsonl'
    return [row for row in map(json.loads, path.read_text(encoding='utf-8').splitlines()) if row['tool'] == 'file.write']

@pytest.mark.parametrize('stage', ['before_dispatch', 'after_result'])
def test_actual_child_safe_read_crash_requires_resume_and_one_bounded_retry(tmp_path, stage):
    child = launch(tmp_path, stage, 'safe_read')
    try:
        boundary = wait_file(tmp_path / 'boundary.json', child)
        child.wait(timeout=5)
        assert child.returncode == 73, child.communicate()
        time.sleep(1.15)
        with ServiceFixture(tmp_path / 'run', limits=WorkflowLimits(lease_seconds=1)) as recovered:
            key = boundary['workflow_id']
            detail = recovered.detail(key)
            assert detail['status'] == 'paused', detail
            assert detail['steps'][0]['status'] == 'pending'
            assert detail['invocations'][0]['state'] == 'abandoned'
            time.sleep(0.15)
            assert recovered.detail(key)['status'] == 'paused', 'Recovery resumed without owner control.'
            recovered.control(key, 'resume')
            final = recovered.await_state(key, 'completed', 'blocked', timeout=6)
            assert final['status'] == 'completed', final
            stat = next((s for s in final['steps'] if s['step_id'] == 'stat'))
            assert stat['attempts'] == 2
            assert stat['verification']['status'] == 'VERIFIED'
            assert len(final['invocations']) == 3
            audit = tmp_path / 'run/state/logs/tool_audit.jsonl'
            rows = list(map(json.loads, audit.read_text(encoding='utf-8').splitlines()))
            assert len([r for r in rows if r['tool'] == 'file.stat']) == 1 + int(stage == 'after_result')
            assert len([r for r in rows if r['tool'] == 'file.read']) == 1
            assert write_audit(tmp_path) == []
            assert recovered.client.calls == []
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)

@pytest.mark.parametrize('stage', ['before_dispatch', 'after_result'])
def test_actual_child_crash_never_replays_uncertain_original_write(tmp_path, stage):
    child = launch(tmp_path, stage)
    try:
        boundary = wait_file(tmp_path / 'boundary.json', child)
        child.wait(timeout=5)
        assert child.returncode == 73, child.communicate()
        output = Path(boundary['path'])
        expected_effects = int(stage == 'after_result')
        assert output.exists() is bool(expected_effects)
        assert len(write_audit(tmp_path)) == expected_effects
        if expected_effects:
            assert output.read_text(encoding='utf-8') == 'One original fixture effect.'
        time.sleep(1.15)
        with ServiceFixture(tmp_path / 'run', limits=WorkflowLimits(lease_seconds=1)) as recovered:
            detail = recovered.detail(boundary['workflow_id'])
            assert detail['status'] == 'blocked', detail
            assert any((row['state'] == 'uncertain' and row['step_id'] == 'save' for row in detail['invocations']))
            assert next((row for row in detail['steps'] if row['step_id'] == 'read'))['status'] == 'verified'
            for operation in ('resume', 'retry_safe'):
                with pytest.raises(WorkflowError):
                    recovered.control(boundary['workflow_id'], operation, **{'step_id': 'save'} if operation == 'retry_safe' else {})
            time.sleep(0.15)
            assert len(write_audit(tmp_path)) == expected_effects
            assert output.exists() is bool(expected_effects)
            assert recovered.client.calls == []
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)

def process_suspend(pid, suspended):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(2048, False, pid)
    assert handle, ctypes.get_last_error()
    try:
        function = getattr(ctypes.WinDLL('ntdll'), 'NtSuspendProcess' if suspended else 'NtResumeProcess')
        function.argtypes = [ctypes.c_void_p]
        function.restype = ctypes.c_long
        assert function(handle) == 0
    finally:
        kernel.CloseHandle(handle)

@pytest.mark.skipif(sys.platform != 'win32', reason='actual Windows owned-process suspension')
def test_two_real_owners_reject_live_collision_and_fence_stale_completion(tmp_path):
    child = launch(tmp_path, 'hold_result')
    suspended = False
    try:
        boundary = wait_file(tmp_path / 'boundary.json', child)
        assert Path(boundary['path']).read_text(encoding='utf-8') == 'One original fixture effect.'
        assert len(write_audit(tmp_path)) == 1
        contender = ServiceFixture(tmp_path / 'run', limits=WorkflowLimits(lease_seconds=1))
        try:
            with pytest.raises(WorkflowError, match='owns the durable lease'):
                contender.start()
        finally:
            contender.close()
        process_suspend(child.pid, True)
        suspended = True
        time.sleep(1.2)
        with ServiceFixture(tmp_path / 'run', limits=WorkflowLimits(lease_seconds=1)) as new_owner:
            detail = new_owner.detail(boundary['workflow_id'])
            assert detail['status'] == 'blocked'
            assert new_owner.service.lease['fence'] > boundary['lease']['fence']
            revision = detail['revision']
            (tmp_path / 'release').touch()
            process_suspend(child.pid, False)
            suspended = False
            late = wait_file(tmp_path / 'stale-completion.json', child)
            child.wait(timeout=5)
            assert child.returncode == 0, child.communicate()
            final = new_owner.detail(boundary['workflow_id'])
            assert final['status'] == late['status'] == 'blocked'
            assert final['revision'] == revision
            assert len(write_audit(tmp_path)) == 1
            assert next((row for row in final['steps'] if row['step_id'] == 'save'))['status'] == 'blocked'
    finally:
        if suspended:
            process_suspend(child.pid, False)
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)
