"""Time unchanged public original-process recovery boundaries, no model/native.

Uses the existing owned child probe, its actual os._exit(73), original handlers,
real lease expiry and unchanged public safety/outcome oracles. Timed recovery
starts after parent fixture construction and lease wait; it is safe disposition,
not owner-resumed completion. All files/stores belong to fresh temporary roots.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.v3_review.service_fixture import ServiceFixture
from scripts.v3_review.check_browser import runtime_manifest
from scripts.v3_review.measure_performance import distribution
from hanni.workflows.types import WorkflowError, WorkflowLimits

spec = importlib.util.spec_from_file_location('public_original_process_helpers', ROOT / 'tests/integration/test_workflow_service_process_verifier.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 5:
        parser.error('repeats must be 1..5')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = {'passed': False, 'rows': [], 'errors': [], 'disclosure': __doc__,
        'runtime_before': runtime_manifest(), 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        with tempfile.TemporaryDirectory(prefix='hanni-public-recovery-timers-') as temporary:
            for target in ('safe_read', 'write'):
                for stage in ('before_dispatch', 'after_result'):
                    for iteration in range(args.repeats):
                        root = Path(temporary) / f'{target}-{stage}-{iteration}'
                        child = helpers.launch(root, stage, target)
                        fixture = None
                        try:
                            boundary = helpers.wait_file(root / 'boundary.json', child)
                            child.wait(timeout=5)
                            assert child.returncode == 73, child.communicate()
                            died_at = time.perf_counter_ns()
                            expected_effects = int(stage == 'after_result') if target == 'write' else 0
                            if target == 'write':
                                assert len(helpers.write_audit(root)) == expected_effects
                                assert Path(boundary['path']).exists() is bool(expected_effects)
                            time.sleep(1.15)  # Same original real lease-expiry wait, no fake clock.
                            setup_at = time.perf_counter_ns()
                            fixture = ServiceFixture(root / 'run', limits=WorkflowLimits(lease_seconds=1))
                            setup_ms = (time.perf_counter_ns() - setup_at) / 1e6
                            started = time.perf_counter_ns()
                            fixture.start()
                            detail = fixture.detail(boundary['workflow_id'])
                            safe_ms = (time.perf_counter_ns() - started) / 1e6
                            death_to_safe_ms = (time.perf_counter_ns() - died_at) / 1e6
                            row = {'target': target, 'stage': stage, 'iteration': iteration,
                                'start_to_safe_projection_ms': safe_ms, 'fixture_setup_excluded_ms': setup_ms,
                                'death_observed_to_safe_ms': death_to_safe_ms, 'safe_status': detail['status'],
                                'no_automatic_replay': True, 'duplicate_writes': 0, 'owner_resumed': target == 'safe_read'}
                            if target == 'safe_read':
                                assert detail['status'] == 'paused', detail['status']
                                assert detail['steps'][0]['status'] == 'pending'
                                assert detail['invocations'][0]['state'] == 'abandoned'
                                time.sleep(.15)
                                assert fixture.detail(boundary['workflow_id'])['status'] == 'paused'
                                resumed_at = time.perf_counter_ns()
                                fixture.control(boundary['workflow_id'], 'resume')
                                final = fixture.await_state(boundary['workflow_id'], 'completed', 'blocked', timeout=6)
                                row['owner_resume_to_verified_ms'] = (time.perf_counter_ns() - resumed_at) / 1e6
                                assert final['status'] == 'completed', final['status']
                                stat = next(step for step in final['steps'] if step['step_id'] == 'stat')
                                assert stat['attempts'] == 2 and stat['verification']['status'] == 'VERIFIED'
                                assert len(final['invocations']) == 3
                                records = list(map(json.loads, (root / 'run/state/logs/tool_audit.jsonl').read_text().splitlines()))
                                assert sum(record['tool'] == 'file.stat' for record in records) == 1 + int(stage == 'after_result')
                                assert sum(record['tool'] == 'file.read' for record in records) == 1
                                assert helpers.write_audit(root) == []
                            else:
                                assert detail['status'] == 'blocked', detail['status']
                                assert any(item['state'] == 'uncertain' and item['step_id'] == 'save' for item in detail['invocations'])
                                assert next(step for step in detail['steps'] if step['step_id'] == 'read')['status'] == 'verified'
                                for operation in ('resume', 'retry_safe'):
                                    try:
                                        fixture.control(boundary['workflow_id'], operation,
                                            **({'step_id': 'save'} if operation == 'retry_safe' else {}))
                                    except WorkflowError:
                                        pass
                                    else:
                                        raise AssertionError('Uncertain write accepted an unchanged forbidden control.')
                                time.sleep(.15)
                                assert len(helpers.write_audit(root)) == expected_effects
                                assert Path(boundary['path']).exists() is bool(expected_effects)
                                if expected_effects:
                                    assert Path(boundary['path']).read_text() == 'One original fixture effect.'
                            assert fixture.client.calls == []
                            result['rows'].append(row)
                        finally:
                            if fixture:
                                fixture.close()
                            if child.poll() is None:
                                child.kill()  # Exact owned temporary probe only.
                            child.communicate(timeout=5)
        result['passed'] = True
    except BaseException as error:
        result['errors'].append(f'{type(error).__name__}: {error}')
    finally:
        result['runtime_after'] = runtime_manifest()
        result['passed'] = result['passed'] and result['runtime_before']['sha256'] == result['runtime_after']['sha256']
        result['summary'] = {target: distribution([row['start_to_safe_projection_ms'] for row in result['rows'] if row['target'] == target])
                             for target in ('safe_read', 'write')}
        result['owner_resume_summary'] = distribution([row['owner_resume_to_verified_ms'] for row in result['rows'] if row['target'] == 'safe_read'])
        (output / 'recovery-performance.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'cases': len(result['rows']), 'errors': result['errors']}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
