"""Archive source and exact controlled workflow boundary receipts before testing."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import pytest
ROOT = Path(__file__).resolve().parents[2]
SOURCES = [*sorted((ROOT / 'src/hanni/workflows').glob('*.py')), ROOT / 'src/hanni/dashboard/workflows.py', ROOT / 'src/hanni/mcp/host.py', ROOT / 'src/hanni/tools/base.py', ROOT / 'src/hanni/tools/files.py', ROOT / 'src/hanni/reliability/verification.py', ROOT / 'src/hanni/compute/registry.py', ROOT / 'src/hanni/compute/scheduler.py', ROOT / 'src/hanni/compute/transport.py', ROOT / 'scripts/v3_review/service_fixture.py', ROOT / 'scripts/v3_review/fixtures.py']

class Receipts:

    def __init__(self):
        self.rows = []

    def pytest_runtest_logreport(self, report):
        if report.when == 'call' or report.failed:
            self.rows.append(dict(nodeid=report.nodeid, phase=report.when, outcome=report.outcome, duration_seconds=report.duration, properties=dict(report.user_properties), failure=str(report.longrepr) if report.failed else None))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--archive-only', action='store_true')
    parser.add_argument('targets', nargs='*')
    args = parser.parse_args()
    directory = Path(args.output).resolve()
    allowed = (ROOT / 'data/campaign4-boundaries').resolve()
    if directory.exists() or not directory.is_relative_to(allowed):
        raise ValueError('Choose a fresh campaign-owned output directory')
    directory.mkdir(parents=True)
    paths = [*SOURCES, *sorted((ROOT / 'scripts/campaign4_boundaries').glob('*.py')), *sorted((ROOT / 'tests/integration').glob('test_campaign4_boundaries*.py'))]
    hashes = {}
    for path in paths:
        name = path.relative_to(ROOT).as_posix()
        content = path.read_bytes()
        hashes[name] = hashlib.sha256(content).hexdigest()
        archived = directory / 'source' / name
        archived.parent.mkdir(parents=True, exist_ok=True)
        archived.write_bytes(content)
    manifest = dict(baseline=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), source_sha256=hashes, scope='original isolated workflow engine; scripted planner contract; owned helper children only', model_quality_claimed=False, owner_processes_touched=False, owner_database_read=False)
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    if args.archive_only:
        print(json.dumps({'archive': str(directory), 'sources': len(hashes)}))
        return 0
    targets = args.targets or [path.relative_to(ROOT).as_posix() for path in sorted((ROOT / 'tests/integration').glob('test_campaign4_boundaries*.py'))]
    plugin = Receipts()
    start = time.perf_counter()
    code = int(pytest.main(['-q', *targets, '-o', 'junit_family=xunit1', '--junitxml=' + str(directory / 'junit.xml')], plugins=[plugin]))
    result = dict(exit_code=code, duration_seconds=time.perf_counter() - start, counts={outcome: sum((row['outcome'] == outcome for row in plugin.rows)) for outcome in ('passed', 'failed', 'skipped')}, changed_sources=[name for name, before in hashes.items() if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != before], receipts=plugin.rows)
    (directory / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'receipts'}))
    return code
if __name__ == '__main__':
    sys.exit(main())
