"""Archive scoped original bytes and run a bounded, machine-readable fault cohort."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[2]
SCOPES = ('src/hanni/workflows', 'src/hanni/memory', 'src/hanni/laya', 'src/hanni/compute', 'src/hanni/models')
TESTS = ('tests/integration/test_campaign9_resilience_memory.py', 'tests/integration/test_campaign9_resilience_workflows.py', 'tests/integration/test_campaign9_resilience_inference.py')
REGRESSIONS = ('tests/unit/test_model_client.py', 'tests/unit/test_memory.py', 'tests/unit/test_memory_context_v35.py', 'tests/unit/test_laya_advisory.py', 'tests/integration/test_memory_context_v35.py', 'tests/integration/test_memory_v35_verifier.py', 'tests/integration/test_laya_v35_advisory_verifier.py', 'tests/integration/test_campaign3_boundaries.py', 'tests/integration/test_campaign3_boundaries_recovery.py', 'tests/integration/test_campaign5_verification.py')

def sources():
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for scope in SCOPES for path in sorted((ROOT / scope).rglob('*.py'))}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--only', choices=('memory', 'workflows', 'inference'))
    parser.add_argument('--regressions', action='store_true')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    expected = ROOT / 'data'
    if not output.is_relative_to(expected) or not output.name or 'campaign9-resilience' not in str(output):
        raise ValueError('Evidence must use the campaign-owned data root.')
    output.mkdir(parents=True, exist_ok=False)
    before = sources()
    for name in before:
        archived = output / 'source-before' / name
        archived.parent.mkdir(parents=True, exist_ok=True)
        archived.write_bytes((ROOT / name).read_bytes())
    if args.regressions and args.only:
        raise ValueError('Regression and family cohorts are distinct.')
    selected = list(REGRESSIONS) if args.regressions else list(TESTS) if args.only is None else [name for name in TESTS if name.endswith(args.only + '.py')]
    for name in selected:
        archived = output / 'test-before' / name
        archived.parent.mkdir(parents=True, exist_ok=True)
        archived.write_bytes((ROOT / name).read_bytes())
    command = [sys.executable, '-X', 'utf8', '-m', 'pytest', *selected, '-q', '-o', 'junit_family=legacy', '--junitxml=' + str(output / 'tests.xml')]
    started = time.perf_counter()
    run = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=240)
    (output / 'stdout.log').write_bytes(run.stdout)
    (output / 'stderr.log').write_bytes(run.stderr)
    after = sources()
    cases = []
    if (output / 'tests.xml').exists():
        for case in ET.parse(output / 'tests.xml').iter('testcase'):
            cases.append({'node': case.get('classname') + '::' + case.get('name'), 'status': 'fail' if case.find('failure') is not None else 'error' if case.find('error') is not None else 'skip' if case.find('skipped') is not None else 'pass', 'seconds': float(case.get('time', 0)), 'observed': [dict(item.attrib) for item in case.findall('./properties/property')]})
    report = {'scope': 'CONTROLLED original APIs; mocked model/remote/fault leaves; no live inference', 'command': command, 'exit_code': run.returncode, 'seconds': time.perf_counter() - started, 'source_before': before, 'source_after': after, 'source_unchanged': before == after, 'test_sources': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in selected}, 'counts': {status: sum((case['status'] == status for case in cases)) for status in ('pass', 'fail', 'error', 'skip')}, 'cases': cases}
    (output / 'RESULTS.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('exit_code', 'seconds', 'source_unchanged', 'counts')}))
    return run.returncode
if __name__ == '__main__':
    raise SystemExit(main())
