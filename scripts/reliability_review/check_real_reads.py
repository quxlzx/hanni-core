"""Read-only Windows integration smoke with real original diagnostic handlers.

No model, handler replacements, app launch, provider request or production data
store. Output contains validation metadata, never process names or raw results.
This is hardware integration evidence, not a controlled before/after benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def runtime_manifest():
    files = list((ROOT / 'src/hanni').rglob('*.py'))
    files.extend(path for path in (ROOT / 'config').rglob('*')
                 if path.is_file() and path.suffix in {'.yaml', '.yml', '.json', '.toml'})
    entries = {str(path.relative_to(ROOT)).replace('\\', '/'):
               hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)}
    encoded = json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()
    return {'sha256': hashlib.sha256(encoded).hexdigest(), 'files': entries}


def percentage(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    before = runtime_manifest()
    sys.path.insert(0, str(ROOT / 'src'))
    from hanni.config.loader import load_config
    from hanni.tools.base import ToolRequest
    from hanni.tools.registry import build_default_registry

    rows = []
    with tempfile.TemporaryDirectory(prefix='hanni-real-read-smoke-') as directory:
        config = load_config(ROOT / 'config', data_dir=Path(directory), env={})
        registry = build_default_registry(config)
        try:
            for name, arguments in [('time.now', {'timezone': 'UTC'}),
                                    ('system.stats', {}),
                                    ('process.top_memory', {'limit': 5}),
                                    ('process.top_cpu', {'limit': 5})]:
                result = registry.execute(ToolRequest(name, arguments, source='test'))
                data = result.data
                if name == 'time.now':
                    valid = isinstance(data.get('utc_iso'), str) and type(data.get('epoch')) is int
                elif name == 'system.stats':
                    valid = all(percentage(data.get(key)) for key in ('cpu_percent', 'ram_percent'))
                else:
                    processes = data.get('processes')
                    metric = 'cpu_percent' if name == 'process.top_cpu' else 'rss_mb'
                    valid = isinstance(processes, list) and bool(processes) and all(
                        isinstance(row, dict) and isinstance(row.get('name'), str)
                        and type(row.get(metric)) in (int, float)
                        and math.isfinite(row[metric]) and row[metric] >= 0 for row in processes)
                rows.append({'capability_id': name, 'response_ok': result.ok,
                             'evidence_valid': valid, 'verification': result.verification,
                             'duration_ms': result.duration_ms})
        finally:
            registry.context.reliability.close()
    after = runtime_manifest()
    report = {'passed': before == after and all(row['response_ok'] and row['evidence_valid'] for row in rows),
              'runtime_manifest': before, 'runtime_manifest_after': after,
              'checks': rows, 'source': 'Original default registry and real local handlers.',
              'disclosure': 'Read-only snapshots on current Windows hardware; no controlled values, model, provider, app or user-data changes. Process names and raw results excluded.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'checks': len(rows)}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
