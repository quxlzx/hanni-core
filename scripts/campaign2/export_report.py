"""Publish compact audit outcomes with hash-bound local raw evidence references."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
DIMENSIONS = ('valid_arguments', 'invalid_arguments', 'missing_parameter', 'permission_enforcement', 'dependency_unavailable', 'output_contract', 'natural_language_selection', 'end_to_end')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n', encoding='utf8')

def relative(path):
    return path.resolve().relative_to(ROOT).as_posix()

def snapshot():
    paths = set((ROOT / 'src').rglob('*.py')) | set((ROOT / 'config').rglob('*.yaml'))
    for folder in ('scripts/campaign2', 'scripts/campaign2_verification'):
        paths.update((ROOT / folder).rglob('*.py'))
    paths.update((ROOT / 'tests/integration').glob('test_campaign2*.py'))
    paths.add(ROOT / 'tests/unit/test_capability_metadata.py')
    return {relative(path): sha(path) for path in sorted(paths)}

def export(raw, models, output):
    scorecard = json.loads((raw / 'SCORECARD.json').read_text(encoding='utf8'))
    inventory = json.loads((raw / 'INVENTORY.json').read_text(encoding='utf8'))
    model_summary = json.loads((models / 'SUMMARY.json').read_text(encoding='utf8'))
    rows = []
    artifacts = {relative(raw / 'SCORECARD.json'): sha(raw / 'SCORECARD.json'), relative(raw / 'INVENTORY.json'): sha(raw / 'INVENTORY.json')}
    table = ['# Per-capability scorecard', '', 'Counts come from the freshly enumerated registry; no expected total is assumed. The raw original-handler receipts are preserved locally under `' + relative(raw) + '`. They are hash-bound here rather than copied into documentation with unrelated live host data.', '', 'P = passed within the stated fixture scope; F = failed; B = blocked; NA = no optional dependency. Missing-parameter checks document optional/default behavior where the original schema does not require a parameter. NL reports retrieval and host-policy behavior. Model selection is an additional, separate column.', '', '| Capability | Valid | Invalid | Missing | Gates | Absent dep. | Contract | NL | E2E | Valid/E2E scope | Model |', '|---|---|---|---|---|---|---|---|---|---|---|---|']
    symbols = {'pass': 'P', 'fail': 'F', 'blocked': 'B', 'not_applicable': 'NA'}
    modes = {'live_read': 'live read', 'isolated_original': 'isolated implementation', 'original_mock_dependency': 'mock leaf dependency'}
    for case in scorecard['capabilities']:
        path = raw / 'receipts' / f"{case['id']}.json"
        artifacts[relative(path)] = sha(path)
        model_path = models / 'receipts' / f"{case['id']}.json"
        model = json.loads(model_path.read_text(encoding='utf8')) if model_path.is_file() else None
        if model:
            artifacts[relative(model_path)] = sha(model_path)
        dimensions = {}
        for dimension in DIMENSIONS:
            measured = case['dimensions'][dimension]
            dimensions[dimension] = {key: measured[key] for key in ('status', 'mode', 'reason') if key in measured}
            dimensions[dimension]['raw_receipt_sha256'] = measured['receipt_sha256']
        row = {'id': case['id'], 'family': case.get('contract', {}).get('family'), 'definition_hash': case.get('definition_hash'), 'handler_sha256': case.get('handler_sha256'), 'host_eligible': case.get('host_eligible'), 'raw_case': relative(path), 'raw_case_sha256': sha(path), 'dimensions': dimensions, 'model_selection': {'status': model['status'], 'actual_model_http_requests': model['actual_model_http_requests'], 'raw_receipt': relative(model_path), 'raw_receipt_sha256': sha(model_path)} if model else {'status': 'blocked', 'reason': 'No actual model-selection receipt was produced.'}}
        rows.append(row)
        cells = [symbols[dimensions[dimension]['status']] for dimension in DIMENSIONS]
        table.append('| `' + case['id'] + '` | ' + ' | '.join(cells) + ' | ' + modes.get(dimensions['valid_arguments']['mode'], dimensions['valid_arguments']['mode']) + ' | ' + symbols[row['model_selection']['status']] + ' |')
    public = {key: value for key, value in scorecard.items() if key != 'capabilities'}
    public.update(format='compact_public_scorecard', evidence_scope='Outcomes and hashes; full implementation assertions and original results remain in referenced local raw receipts.', raw_scorecard=relative(raw / 'SCORECARD.json'), raw_scorecard_sha256=sha(raw / 'SCORECARD.json'), raw_inventory=relative(raw / 'INVENTORY.json'), capabilities=rows, valid_end_to_end_modes=dict(Counter((case['dimensions']['valid_arguments']['mode'] for case in scorecard['capabilities']))))
    save(output / 'INVENTORY.json', inventory)
    save(output / 'SCORECARD.json', public)
    (output / 'SCORECARD.md').write_text('\n'.join(table) + '\n', encoding='utf8')
    save(output / 'RETRIEVAL_FINDINGS.json', {'scope': 'Original metadata retrieval and host policy, not model inference.', 'failures': [{'id': case['id'], **case['dimensions']['natural_language_selection']['receipt']} for case in scorecard['capabilities'] if case['dimensions']['natural_language_selection']['status'] == 'fail']})
    save(output / 'MODEL_SELECTION.json', {**model_summary, 'per_capability': [{'id': row['id'], **row['model_selection']} for row in rows]})
    unknown = models / 'UNKNOWN_TOOL_DEMO.json'
    if unknown.is_file():
        value = json.loads(unknown.read_text(encoding='utf8'))
        artifacts[relative(unknown)] = sha(unknown)
        save(output / 'UNKNOWN_TOOL.json', {key: value[key] for key in ('capability_id', 'original_name', 'schema', 'discovered_by_actual_sdk', 'model_retraining_performed', 'status', 'reason', 'actual_model_http_requests', 'separate_original_registry_call') if key in value} | {'raw_receipt': relative(unknown), 'raw_receipt_sha256': sha(unknown), 'retrieved_menu_ids': [tool['capability_id'] for tool in value['menu']]})
    for path in models.glob('*.json'):
        artifacts[relative(path)] = sha(path)
    save(output / 'EVIDENCE_MANIFEST.json', {'generated_at': datetime.now(timezone.utc).isoformat(), 'scope': 'SHA-256 of preserved local raw matrix and model receipts; public scorecard omits unrelated live host data.', 'artifacts': artifacts})

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--raw', type=Path)
    parser.add_argument('--models', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/campaign2')
    args = parser.parse_args()
    if args.snapshot:
        save(args.snapshot, {'sources': snapshot()})
    if args.raw and args.models:
        export(args.raw, args.models, args.output)
if __name__ == '__main__':
    main()
