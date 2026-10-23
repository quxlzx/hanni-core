"""Pin implementation imports when comparing native analysis fault probes."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import os
ROOT = Path(__file__).resolve().parents[2]

class Receipts:

    def __init__(self):
        self.rows = []

    def pytest_runtest_logreport(self, report):
        if report.when == 'call' or report.failed:
            self.rows.append({'nodeid': report.nodeid, 'phase': report.when, 'outcome': report.outcome, 'duration_seconds': report.duration, 'failure': str(report.longrepr) if report.failed else None})

def run(output, implementation):
    output, implementation = (output.resolve(), implementation.resolve())
    if output.exists() or not output.is_relative_to((ROOT / 'data/campaign4-manager').resolve()):
        raise ValueError('Choose a fresh owned manager directory')
    if implementation not in {(ROOT / 'src').resolve(), (ROOT / 'data/campaign4-manager/original-source/extracted/src').resolve()}:
        raise ValueError('Use only current or archived original campaign source')
    output.mkdir(parents=True)
    sys.path[:0] = [str(implementation), str(ROOT)]
    import hanni.workflows.service as service
    engine_path = Path(service.__file__).resolve()
    if engine_path != implementation / 'hanni/workflows/service.py':
        raise RuntimeError('The requested original/candidate engine was not imported')
    test = ROOT / 'tests/integration/test_campaign4_manager_analysis.py'
    blob = test.read_bytes()
    (output / 'prospective-test-source.py').write_bytes(blob)
    source = {p.relative_to(implementation).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((implementation / 'hanni').rglob('*.py'))}
    prepared = {'test_source_sha256': hashlib.sha256(blob).hexdigest(), 'cases': 10, 'engine_path': str(engine_path), 'source_before': source, 'scope': 'Original native local analysis with controlled model; real owned file implementations.'}
    (output / 'PREPARED.json').write_text(json.dumps(prepared, indent=2) + '\n', encoding='utf8', newline='\n')
    os.environ['HANNI_CAMPAIGN4_ANALYSIS_EVIDENCE'] = str(output / 'raw')
    import pytest
    plugin = Receipts()
    started = time.perf_counter()
    command = ['tests/integration/test_campaign4_manager_analysis.py', '-q', '-o', 'pythonpath=' + str(implementation), '--junitxml=' + str(output / 'junit.xml')]
    code = int(pytest.main(command, plugins=[plugin]))
    after = {p.relative_to(implementation).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((implementation / 'hanni').rglob('*.py'))}
    receipt = {'exit_code': code, 'command': command, 'duration_seconds': time.perf_counter() - started, 'counts': {state: sum((row['outcome'] == state for row in plugin.rows)) for state in ('passed', 'failed', 'skipped')}, 'source_unchanged': source == after, 'source_after': after, 'receipts': plugin.rows}
    (output / 'RESULTS.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({key: value for key, value in receipt.items() if key not in {'receipts', 'source_after'}}))
    return code
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--implementation', type=Path, default=ROOT / 'src')
    args = parser.parse_args()
    raise SystemExit(run(args.output, args.implementation))
