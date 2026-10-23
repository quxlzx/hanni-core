"""Contract corrections to generic controlled sources, preserving version 1.

Reads only the predeclared dependency source. No corpus, response, route or
sealed objective is consulted. Dynamic filtering must retain original handlers'
name/PID/opaque-ID semantics, original validation and all authorization gates.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
VERSION_1_SHA256 = '71658a249f98ff09d531a7c307d395dda1fce8409be894e362ed31f318dba2f6'

def build(source):
    result = deepcopy(source)
    result['schema_version'] = 2
    result['scope'] = 'version 2 controlled dependency sources; original contract alignment, not live system/provider evidence or model answers'
    result['predecessor'] = {'path': 'evals/campaign1/fixture-sources.json', 'sha256': VERSION_1_SHA256}
    processes = [{'pid': 4141, 'name': 'FixtureRender.exe', 'memory_gb': 8.0, 'memory_percent': 25.0, 'running_minutes': 60}, {'pid': 4242, 'name': 'FixturePreview.exe', 'memory_gb': 2.0, 'memory_percent': 6.25, 'running_minutes': 15}]
    tasks = [{'id': 'task_fixture_1', 'request_key': 'controlled-task-fixture-1', 'title': 'Review the outline', 'course': '', 'due': '2026-10-12T00:00:00-04:00', 'all_day': 1, 'status': 'open', 'created_at': '2026-10-12T10:15:00-04:00'}]
    result['process_inventory'] = processes
    result['todo_inventory'] = tasks
    tools = result['tools']
    tools['process.top_memory']['data'] = {'processes': [{'name': row['name'], 'rss_mb': row['memory_gb'] * 1024, 'rss_gb': row['memory_gb'], 'memory_percent': row['memory_percent'], 'instances': 1, 'pids': [row['pid']]} for row in processes]}
    tools['process.list']['data'] = {'processes': [{key: row[key] for key in ('pid', 'name', 'memory_percent')} for row in processes]}
    tools['process.find']['data'] = {'query': '', 'processes': [{key: row[key] for key in ('pid', 'name', 'memory_gb', 'running_minutes')} for row in processes], 'running': True, 'count': len(processes)}
    tools['process.inspect']['data'] = {'pid': 4242, 'exists': True}
    tools['process.find']['bindings'] = []
    tools['process.inspect']['bindings'] = []
    for name in ('todo.list', 'todo.due'):
        tools[name]['data'] = {'tasks': deepcopy(tasks), 'count': len(tasks)}
        tools[name]['bindings'] = []
    for name in ('todo.get', 'todo.complete'):
        tools[name]['data'] = {'task': deepcopy(tasks[0]), 'id': tasks[0]['id']}
        tools[name]['bindings'] = []
    result['contract_corrections'] = {'process.top_memory': 'Original rss_mb/rss_gb/memory_percent/instances/pids row fields; no memory_mb substitute.', 'process.list': 'Original PID/name/memory_percent rows, not fabricated resident-memory measurement.', 'process.find': 'Case-insensitive substring filtering of fixed inventory; memory_gb/running_minutes only; no CPU measurement or relabeling.', 'process.inspect': 'Exact requested PID existence in fixed inventory; no other measurements.', 'todo': 'Original opaque string IDs and status records; fixed inventory exact-ID lookup, consistent controlled mutation/readback, unknown ID stays unknown.', 'time.now': 'Original module-local controlled-clock handler must apply kind/timezone/day_offset; process-global clocks remain real.'}
    return result

def main():
    original = ROOT / 'evals/campaign1/fixture-sources.json'
    assert hashlib.sha256(original.read_bytes()).hexdigest() == VERSION_1_SHA256
    destination = ROOT / 'evals/campaign1/fixture-sources-v2.json'
    if destination.exists():
        raise SystemExit('Preserve versioned sources; do not replace an existing version.')
    destination.write_text(json.dumps(build(json.loads(original.read_text(encoding='utf8'))), ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf8')
    print(json.dumps({'path': str(destination.relative_to(ROOT)), 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'predecessor_sha256': VERSION_1_SHA256}))
if __name__ == '__main__':
    main()
