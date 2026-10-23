"""Run only Campaign 2 MCP checks and retain fresh machine-readable receipts."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.campaign2.mcp_contracts import CLASSIFICATIONS, QUERIES, VALID, definitions

class Receipts:

    def __init__(self):
        self.tests = {}

    def pytest_runtest_logreport(self, report):
        row = self.tests.setdefault(report.nodeid, {'nodeid': report.nodeid, 'duration_seconds': 0, 'phases': {}})
        row['duration_seconds'] += report.duration
        row['phases'][report.when] = report.outcome
        if report.failed:
            row['failure'] = str(report.longrepr)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    os.environ['CAMPAIGN2_MCP_ARTIFACT_ROOT'] = str(args.out.resolve())
    sources = [ROOT / 'src/hanni/mcp' / name for name in ('adapter.py', 'host.py', 'manager.py', 'security.py', 'transport.py')]
    before = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    inventory = {'scope': 'new_actual_local_sdk_controlled_tools_only', 'count': len(definitions()), 'tools': [{'definition': row, 'owner_classification': CLASSIFICATIONS[row['name']], 'valid_arguments': VALID[row['name']], 'nl_request': QUERIES[row['name']]} for row in definitions()]}
    (args.out / 'inventory.json').write_text(json.dumps(inventory, indent=2), encoding='utf8')
    import pytest
    plugin = Receipts()
    started = time.monotonic()
    status = pytest.main(['-q', str(ROOT / 'tests/integration/test_campaign2_mcp_matrix.py'), str(ROOT / 'tests/integration/test_campaign2_mcp_lifecycle.py'), '--basetemp=' + str(args.out / 'pytest-owned-temp'), '--junitxml=' + str(args.out / 'tests.xml')], plugins=[plugin])
    after = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    inventory['observed_builtin_counts'] = sorted({json.loads(path.read_text(encoding='utf8'))['base_count'] for path in (args.out / 'transport_receipts').glob('*.json')})
    (args.out / 'inventory.json').write_text(json.dumps(inventory, indent=2), encoding='utf8')
    rows = list(plugin.tests.values())
    passed = sum((row['phases'].get('call') == 'passed' and 'failed' not in row['phases'].values() for row in rows))
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'scope': 'actual_sdk_stdio_and_streamable_http; controlled_local_data; no_real_model', 'duration_seconds': time.monotonic() - started, 'exit_code': int(status), 'test_count': len(rows), 'passed': passed, 'failed': sum(('failed' in row['phases'].values() for row in rows)), 'sdk_version': version('mcp'), 'source_hashes_before': before, 'source_hashes_after': after, 'source_unchanged': before == after, 'tests': rows}
    (args.out / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    return int(status)
if __name__ == '__main__':
    raise SystemExit(main())
