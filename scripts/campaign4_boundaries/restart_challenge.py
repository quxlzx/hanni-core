"""Run two real owned workflow helper processes with durable before/after evidence."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
from scripts.campaign4_boundaries.restart_worker import durable_json
from scripts.campaign4_boundaries.run import ROOT, SOURCES

def run_challenge(directory, scenario='safe_checkpoint'):
    root = Path(directory).resolve()
    if root.exists():
        raise ValueError('Choose a fresh owned challenge directory')
    root.mkdir(parents=True)
    (root / 'completed-source.txt').write_bytes(b'Initial controlled source evidence: aperture 7 mm.\n')
    (root / 'remaining-source.txt').write_bytes(b'Campaign 4 controlled source report\nObserved calibration rows: 7, 9, 12.\n')
    durable_json(root / 'challenge-owner.json', dict(kind='campaign4_owned_helper', root=str(root), owner_id=str(uuid4())))
    paths = [*SOURCES, *sorted((ROOT / 'scripts/campaign4_boundaries').glob('*.py'))]
    before = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    for path in paths:
        target = root / 'source' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    children = []
    started = time.perf_counter()
    for phase, expected in [('interrupt', 83), ('recover', 0)]:
        command = [sys.executable, '-X', 'utf8', '-m', 'scripts.campaign4_boundaries.restart_worker', '--root', str(root), '--phase', phase, '--scenario', scenario]
        with (root / (phase + '-stdout.log')).open('w', encoding='utf-8') as stdout, (root / (phase + '-stderr.log')).open('w', encoding='utf-8') as stderr:
            child = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            children.append(dict(pid=child.pid, phase=phase, command=command))
            try:
                code = child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                import psutil
                startup = root / (phase + '-worker-start.json')
                if startup.is_file():
                    owned = json.loads(startup.read_text(encoding='utf-8'))
                    try:
                        worker = psutil.Process(owned['pid'])
                        if owned['root'] == str(root) and owned['phase'] == phase and (worker.pid == child.pid or worker.ppid() == child.pid) and (worker.create_time() == owned['create_time']) and (worker.exe() == owned['executable']):
                            worker.kill()
                            worker.wait(timeout=5)
                    except psutil.NoSuchProcess:
                        pass
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)
                raise AssertionError('The owned workflow helper exceeded its bounded challenge time')
            children[-1]['exit_code'] = code
        if code != expected:
            raise AssertionError('Owned ' + phase + ' helper failed: ' + (root / (phase + '-stderr.log')).read_text(encoding='utf-8'))
        if phase == 'interrupt':
            time.sleep(1.15)
    interrupted = json.loads((root / 'interrupted.json').read_text(encoding='utf-8'))
    completed = json.loads((root / 'completed.json').read_text(encoding='utf-8'))
    assert interrupted['pid'] != completed['pid']
    for payload, child in zip((interrupted, completed), children):
        worker = payload['provenance']
        assert worker['pid'] == payload['pid']
        assert worker['pid'] == child['pid'] or worker['parent_pid'] == child['pid']
        child['worker_provenance'] = worker
        child['launcher_or_direct_parent_verified'] = True
    audit = root / 'run/state/logs/tool_audit.jsonl'
    rows = [json.loads(line) for line in audit.read_text(encoding='utf-8').splitlines()]
    changed = [name for name, value in before.items() if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != value]
    result = dict(status='passed', duration_seconds=time.perf_counter() - started, scope='actual original workflow-owned helper restart; controlled planner and original local file implementations', scenario=scenario, boundary_expectation='verified_completion' if scenario == 'safe_checkpoint' else 'blocked_without_write_replay', owner_processes_touched=False, model_quality_claimed=False, children=children, steps=completed['final']['counts'], workflow_status=completed['final']['status'], original_checkpoint_count=len(interrupted['detail']['checkpoints']), final_checkpoint_count=len(completed['final']['checkpoints']), invocations=len(completed['final']['invocations']), completed_first_step_invocations=1, resumed_explicitly=scenario == 'safe_checkpoint', report=completed['report'], original_source_sha256=before, changed_sources=changed, audit_rows=len(rows), receipts_sha256={name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ('interrupted.json', 'completed.json', 'run/state/logs/tool_audit.jsonl', 'interrupt-worker-start.json', 'recover-worker-start.json')})
    if scenario == 'safe_checkpoint':
        result['receipts_sha256']['hash-worker-failed.json'] = hashlib.sha256((root / 'hash-worker-failed.json').read_bytes()).hexdigest()
    assert not changed
    durable_json(root / 'results.json', result)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--scenario', choices=('safe_checkpoint', 'ambiguous_before', 'ambiguous_after'), default='safe_checkpoint')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if not output.is_relative_to((ROOT / 'data/campaign4-boundaries').resolve()):
        raise ValueError('CLI evidence must stay inside the campaign-owned directory')
    result = run_challenge(output, args.scenario)
    print(json.dumps({key: result[key] for key in ('status', 'duration_seconds', 'steps', 'invocations', 'changed_sources')}))
if __name__ == '__main__':
    main()
