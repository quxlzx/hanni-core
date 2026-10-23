"""Public input-only adapter probes; not acceptance-task denominators."""
from pathlib import Path
import argparse
import json
from .harness import run_case, digest, REPO
CASES = [{'id': 'interface-memory', 'query': 'List the synthetic preference.', 'category': 'adapter_contract', 'setup': {'memories': [{'content': 'I prefer concise equipment summaries.'}]}, 'actions': []}, {'id': 'interface-lazy-desktop', 'query': 'Create an owned fixture project.', 'category': 'adapter_contract', 'actions': [{'id': 'create', 'target': 'desktop', 'name': 'project.create', 'arguments': {'name': 'Adapter test project', 'description': 'Synthetic'}}]}, {'id': 'interface-inert-mcp', 'query': 'Inspect synthetic bin A.', 'category': 'adapter_contract', 'setup': {'mcp_records': [{'bin': 'A', 'quantity': 2, 'part': 'gasket'}]}, 'actions': [{'id': 'add', 'target': 'mcp', 'name': 'add'}, {'id': 'connect', 'target': 'mcp', 'name': 'connect', 'arguments': {'server_id': {'$ref': 'add/result/id'}, 'config_hash': {'$ref': 'add/result/config_hash'}, 'approved': True}}, {'id': 'approve', 'target': 'mcp', 'name': 'approve', 'arguments': {'server_id': {'$ref': 'add/result/id'}, 'tools': {'$ref': 'connect/result/servers/0/tools'}}}, {'id': 'call', 'target': 'mcp', 'name': 'call', 'arguments': {'tool_id': {'$ref': 'connect/result/servers/0/tools/0/internal_id'}, 'bin': 'A'}}]}]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    source = digest(REPO / 'scripts/campaign10_core/harness.py')
    (out / 'INPUTS.json').write_text(json.dumps(CASES, indent=2) + '\n', encoding='utf-8', newline='\n')
    for case in CASES:
        try:
            row = run_case(case, out / case['id'])
        except Exception as exc:
            row = {'id': case['id'], 'error': {'type': type(exc).__name__, 'message': str(exc)}}
        (out / (case['id'] + '.json')).write_text(json.dumps(row, indent=2, default=str) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps({'id': case['id'], 'error': row.get('error'), 'actions': {key: {'error': val.get('error'), 'entries': val.get('handler_entries')} for key, val in row.get('actions', {}).items()}}), flush=True)
    (out / 'SOURCE.json').write_text(json.dumps({'harness_before': source, 'harness_after': digest(REPO / 'scripts/campaign10_core/harness.py')}, indent=2) + '\n', encoding='utf-8', newline='\n')
if __name__ == '__main__':
    main()
