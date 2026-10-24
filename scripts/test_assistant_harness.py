"""Run offline assistant tests and retain exact commands, results and coverage.

Examples:
  python scripts/test_assistant_harness.py --layer smoke
  python scripts/test_assistant_harness.py --coverage --checks
  python scripts/test_assistant_harness.py --layer harness -- -x
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LAYERS = {
    'all': ['tests'],
    'unit': ['tests/unit', 'tests/test_native_loop.py', 'tests/test_soul_quartet.py',
             'tests/harness/test_protocol_contracts.py', 'tests/harness/test_state_contracts.py', 'tests/harness/test_routing_regressions.py'],
    'integration': ['tests/integration', 'tests/test_native_dashboard_integration.py',
                    'tests/harness/test_command_registry.py', 'tests/harness/test_hermes_contracts.py', 'tests/harness/test_process_ownership.py'],
    'harness': ['tests/harness'],
    'smoke': ['tests/harness/test_entrypoint_smoke.py', 'tests/integration/test_entry_points.py', 'tests/integration/test_local_llm_cli.py'],
}


def junit_summary(path):
    if not path.exists():
        return None
    suites = ET.parse(path).getroot()
    rows = []
    skipped = []
    for case in suites.iter('testcase'):
        failure, error, skip = (case.find(tag) for tag in ('failure', 'error', 'skipped'))
        status = 'failed' if failure is not None else 'error' if error is not None else 'skipped' if skip is not None else 'passed'
        name = case.attrib.get('classname', '') + '::' + case.attrib.get('name', '')
        rows.append({'id': name, 'status': status})
        if skip is not None:
            skipped.append({'id': name, 'reason': skip.attrib.get('message', '')})
    return {'counts': {status: sum(row['status'] == status for row in rows) for status in ('passed', 'failed', 'error', 'skipped')},
            'collected_results': len(rows), 'results': rows, 'skips': skipped,
            'scope': 'JUnit test cases, including separately reported subtests; pytest console counts are also retained in pytest.log.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layer', choices=LAYERS, default='all')
    parser.add_argument('--coverage', action='store_true')
    parser.add_argument('--checks', action='store_true', help='Also type-check/test/build frontend, compile Python and check a wheel.')
    parser.add_argument('--output', type=Path, default=ROOT / '.pytest-work/assistant-harness/final')
    parser.add_argument('pytest_args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PYTEST_HANNI_GUARD_ROOT'] = str(output / 'guard')
    env['PYTEST_HANNI_REPO'] = str(ROOT)
    env['PYTHONPATH'] = os.pathsep.join([str(ROOT / 'tests/support'), str(ROOT / 'src'), str(ROOT)])
    env['PYTHONHASHSEED'] = '0'
    records = []

    def record(name, command):
        item = {'name': name, 'argv': [str(value) for value in command], 'cwd': str(ROOT), 'exit_code': None}
        records.append(item)
        (output / 'commands.json').write_text(json.dumps(records, indent=2) + '\n')
        print('RUN', name, flush=True)
        start = time.monotonic()
        with (output / (name + '.log')).open('w', encoding='utf-8') as log:
            try:
                result = subprocess.run(item['argv'], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
                item['exit_code'] = result.returncode
            except OSError as exc:
                log.write(type(exc).__name__ + ': ' + str(exc))
                item['exit_code'] = 127
        item['seconds'] = round(time.monotonic() - start, 3)
        (output / 'commands.json').write_text(json.dumps(records, indent=2) + '\n')
        print('DONE', name, item['exit_code'], flush=True)
        return item['exit_code']

    extra = args.pytest_args[1:] if args.pytest_args[:1] == ['--'] else args.pytest_args
    pytest_args = ['-m', 'pytest', *LAYERS[args.layer], '-o', 'addopts=', '-o', 'junit_family=legacy', '-q', '--tb=short',
                   '--junitxml=' + str(output / 'pytest.xml'), *extra]
    if args.coverage and importlib.util.find_spec('coverage'):
        record('pytest', [sys.executable, '-m', 'coverage', 'run', '--branch', '--source=src/hanni',
                         '--data-file=' + str(output / '.coverage'), *pytest_args])
        record('coverage-json', [sys.executable, '-m', 'coverage', 'json', '--data-file=' + str(output / '.coverage'),
                                 '-o', str(output / 'coverage.json')])
        record('coverage-report', [sys.executable, '-m', 'coverage', 'report', '--data-file=' + str(output / '.coverage')])
    else:
        if args.coverage:
            print('Coverage unavailable: install the project dev dependencies. Tests still run.', flush=True)
        record('pytest', [sys.executable, *pytest_args])
    if args.checks:
        record('python-compile', [sys.executable, '-m', 'compileall', '-q', 'src/hanni', 'tests'])
        npm, node = shutil.which('npm'), shutil.which('node')
        if npm and node:
            record('frontend-types', [npm, 'run', 'check', '--prefix', 'frontend'])
            files = sorted([*ROOT.glob('frontend/tests/*.test.ts'), *ROOT.glob('frontend/tests/*.test.mjs')])
            record('frontend-tests', [node, '--test', *files])
            record('frontend-build', [npm, 'run', 'build', '--prefix', 'frontend'])
        else:
            records.append({'name': 'frontend-checks', 'exit_code': 127, 'blocker': 'Node/npm unavailable'})
        record('package-build', [sys.executable, '-m', 'build', '--wheel', '--no-isolation', '--outdir', output / 'dist'])
        record('distribution-check', [sys.executable, 'scripts/check_distribution.py', output / 'dist'])
    summary = {'layer': args.layer, 'commands': records, 'tests': junit_summary(output / 'pytest.xml'),
               'coverage_requested': args.coverage, 'coverage_measured': (output / 'coverage.json').exists(),
               'coverage_scope': 'Main pytest process and its Python threads; subprocess statements are not instrumented. No source omissions.',
               'performance_disclosure': 'Durations describe test runs, not real model latency or throughput benchmarks.',
               'boundary_disclosure': 'Controlled local fixtures only. Python network/storage/device guards are test infrastructure, not an OS sandbox for native binaries.'}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'results': summary['tests']['counts'] if summary['tests'] else None,
                      'checks': {r['name']: r['exit_code'] for r in records}, 'evidence': str(output)}, indent=2))
    return 1 if any(row['exit_code'] != 0 for row in records) else 0


if __name__ == '__main__':
    raise SystemExit(main())
