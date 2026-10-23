"""Archive original source and exact synthetic boundary test receipts."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
import time
import tempfile
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
OWNED = [f'src/hanni/memory/{name}.py' for name in ('session', 'integration', 'projects', 'privacy', 'facts')]
OWNED += [f'src/hanni/laya/{name}.py' for name in ('advisory', 'runtime', 'client', 'manager')]
OWNED += ['src/hanni/dashboard/memory.py']
DEPENDENCIES = ['src/hanni/memory/store.py', 'src/hanni/memory/retrieval.py', 'src/hanni/laya/intelligence.py', 'src/hanni/dashboard/features.py', 'src/hanni/config/schema.py', 'src/hanni/tools/base.py']

class Receipts:

    def __init__(self):
        self.rows = []

    def pytest_runtest_logreport(self, report):
        if report.when == 'call' or report.failed:
            self.rows.append(dict(nodeid=report.nodeid, phase=report.when, outcome=report.outcome, duration_seconds=report.duration, failure=str(report.longrepr) if report.failed else None))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('targets', nargs='*')
    args = parser.parse_args()
    out = Path(args.output).resolve()
    allowed = (ROOT / 'data' / 'campaign3-boundaries').resolve()
    if not out.is_relative_to(allowed) or out.exists():
        raise ValueError('Choose a fresh campaign-owned evidence directory')
    out.mkdir(parents=True)
    hashes = {}
    for name in OWNED:
        source = ROOT / name
        content = source.read_bytes()
        hashes[name] = hashlib.sha256(content).hexdigest()
        target = out / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    manifest = dict(baseline=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), scope='synthetic disposable SQLite; controlled loopback HTTP; no real LAYA/model/SSH', source_sha256=hashes)
    manifest['dependency_sha256'] = {}
    for name in DEPENDENCIES:
        content = (ROOT / name).read_bytes()
        manifest['dependency_sha256'][name] = hashlib.sha256(content).hexdigest()
        target = out / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    evidence_sources = [*sorted((ROOT / 'scripts' / 'campaign3_boundaries').glob('*.py')), *sorted((ROOT / 'tests' / 'integration').glob('test_campaign3_boundaries*.py'))]
    manifest['test_harness_sha256'] = {}
    for source in evidence_sources:
        name = str(source.relative_to(ROOT)).replace('\\', '/')
        content = source.read_bytes()
        manifest['test_harness_sha256'][name] = hashlib.sha256(content).hexdigest()
        target = out / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    from hanni.config.loader import load_config
    from dataclasses import asdict
    with tempfile.TemporaryDirectory(prefix='campaign3-config-only-') as temp:
        cfg = load_config(ROOT / 'config', data_dir=Path(temp), env={})
        manifest['configured_memory'] = asdict(cfg.hanni.memory)
        manifest['requested_laya'] = {key: value for key, value in asdict(cfg.hanni.laya).items() if key != 'url'}
        manifest['mode_interpretation'] = 'Flags request behavior; ordinary factory keeps quality gate closed'
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    plugin = Receipts()
    started = time.perf_counter()
    targets = args.targets or [str(path.relative_to(ROOT)) for path in sorted((ROOT / 'tests' / 'integration').glob('test_campaign3_boundaries*.py'))]
    exit_code = pytest.main(['-q', *targets, '--junitxml=' + str(out / 'junit.xml')], plugins=[plugin])
    changed = [name for name, before in hashes.items() if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != before]
    dependencies_changed = [name for name, before in manifest['dependency_sha256'].items() if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != before]
    result = dict(exit_code=int(exit_code), duration_seconds=time.perf_counter() - started, counts={status: sum((row['outcome'] == status for row in plugin.rows)) for status in ('passed', 'failed', 'skipped')}, source_changed=changed, dependencies_changed=dependencies_changed, receipts=plugin.rows)
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'receipts'}))
    return int(exit_code)
if __name__ == '__main__':
    sys.exit(main())
