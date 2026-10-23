"""C9-only preparation for unchanged public V4.4 assertions.

The legacy fixture already has a direct context record, but predates mandatory
remote resource timestamps. Every new stamp belongs to a newly returned MOCK
resource sample. Native verify_context uses mocked token/retrieval accounting;
it is never a hardware context certificate or an actual model request.
"""
from contextlib import contextmanager
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from scripts.campaign9_resilience.run import ROOT, sources
LEGACY_TEST = 'tests/integration/test_v44_independent_security.py'
LEGACY_FIXTURE = 'tests/integration/test_adaptive_v40_verifier.py'
SUPPLEMENT = 'tests/integration/test_campaign9_resilience_cross_boundary.py'

@contextmanager
def bootstrapped_audit_engine(root, record):
    """Preserve original fixture/response, with separately recorded mock setup."""
    from tests.integration import test_adaptive_v40_verifier as legacy
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError('Controlled bootstrap requires a fresh disposable root.')
    fixture = legacy.audit_engine.__wrapped__(root)
    engine, compute, calls, response = next(fixture)
    transport = compute.transport
    original_resources, original_request = (transport.resources, transport.request)
    try:
        compute.registry.observe('remote-fixture', resource_sampled_at=None)
        original_row = compute.registry.snapshot()['workers'][0]
        assert compute._context_admissible(original_row, 512)
        assert original_row.get('resource_sampled_at') is None
        assert not compute._resources_admissible(original_row)
        assert not calls

        def measured_resources(worker):
            sample = dict(original_resources(worker))
            sample.setdefault('resource_sampled_at', compute.registry.clock())
            return sample

        def context_result(worker, method, path, **options):
            result = original_request(worker, method, path, **options)
            result['usage'] = {'prompt_tokens': 1024, 'completion_tokens': 5, 'total_tokens': 1029}
            return result
        transport.resources = measured_resources
        transport.request = context_result
        try:
            proof = compute.verify_context('remote-fixture', [{'role': 'user', 'content': 'Controlled bootstrap result is {"ok":true}.'}], target_tokens=1024, expected={'ok': True}, max_output_tokens=32)
        finally:
            transport.request = original_request
        assert proof['passed'], 'Original synthetic context-bootstrap gates did not pass.'
        assert len(calls) == 1
        assert not compute.inflight and (not any(compute.registry.active.values()))
        assert response['usage'] == {'completion_tokens': 5}
        row = compute.registry.snapshot()['workers'][0]
        assert compute._resources_admissible(row)
        record({'scope': 'CONTROLLED_MOCK setup, not live inference/context certification', 'injected_fault': 'missing resource timestamp before controlled bootstrap', 'original_context_verified': original_row['max_context_verified'], 'original_resource_sampled_at': original_row.get('resource_sampled_at'), 'mock_resource_sampled_at': row['resource_sampled_at'], 'native_bootstrap': proof, 'setup_transport_entries': len(calls), 'setup_reservation_released': True, 'original_response_unchanged': True})
        calls.clear()
        yield (engine, compute, calls, response)
    finally:
        transport.request = original_request
        transport.resources = original_resources
        engine.close()
        compute.close()
        fixture.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if not output.is_relative_to(ROOT / 'data/campaign9-resilience'):
        raise ValueError('Use only the campaign-owned evidence directory.')
    output.mkdir(parents=True, exist_ok=False)
    before = sources()
    tracked = {**before, **{name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (LEGACY_TEST, LEGACY_FIXTURE, SUPPLEMENT, 'scripts/campaign9_resilience/cross_boundary.py')}}
    for name in tracked:
        target = output / 'source-before' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    command = [sys.executable, '-X', 'utf8', '-m', 'pytest', SUPPLEMENT, '-q', '-o', 'junit_family=legacy', '--junitxml=' + str(output / 'tests.xml')]
    started = time.perf_counter()
    run = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120)
    (output / 'stdout.log').write_bytes(run.stdout)
    (output / 'stderr.log').write_bytes(run.stderr)
    cases = []
    for case in ET.parse(output / 'tests.xml').iter('testcase'):
        cases.append({'node': case.get('classname') + '::' + case.get('name'), 'status': 'fail' if case.find('failure') is not None else 'error' if case.find('error') is not None else 'skip' if case.find('skipped') is not None else 'pass', 'observed': [dict(item.attrib) for item in case.findall('./properties/property')]})
    after = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in tracked}
    report = {'scope': 'C9 supplemental original V4.4 assertions; controlled resource timestamp/native mocked-token bootstrap', 'original_failed_cohort_preserved': 'data/campaign9-manager/development/CROSS_BOUNDARY_REGRESSIONS.xml', 'diagnosis': 'data/campaign9-resilience/cross-boundary-before-corrected/DIAGNOSIS.json', 'command': command, 'exit_code': run.returncode, 'seconds': time.perf_counter() - started, 'source_before': tracked, 'source_after': after, 'source_unchanged': tracked == after, 'counts': {status: sum((c['status'] == status for c in cases)) for status in ('pass', 'fail', 'error', 'skip')}, 'cases': cases, 'real_model_calls': 0, 'real_remote_provider_calls': 0, 'denominator': 'Separate fixture-adapted supplement; unchanged original failure count is not regraded.'}
    (output / 'RESULTS.json').write_bytes((json.dumps(report, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({key: report[key] for key in ('exit_code', 'seconds', 'source_unchanged', 'counts')}))
    return run.returncode
if __name__ == '__main__':
    raise SystemExit(main())
