"""Independently reject incomplete or overstated dynamic capability evidence.

The checker never invokes a capability, connects a provider, or opens any
Campaign 1 corpus. Its inventory input must come from a fresh original registry.
Coverage includes documented blocked/inapplicable outcomes, not only passes.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
DIMENSIONS = ('valid_arguments', 'invalid_arguments', 'missing_parameter', 'permission_enforcement', 'dependency_unavailable', 'output_contract', 'natural_language_selection', 'end_to_end')
STATUSES = {'pass', 'fail', 'blocked', 'not_applicable'}
IMPLEMENTATION_MODES = {'live_read', 'isolated_original', 'original_mock_dependency'}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()

def capability_ids(inventory):
    """Include enabled external discovery even when currently unavailable."""
    items = list(inventory.get('builtins', []))
    items += [{'id': tool.get('internal_id'), **tool} for tool in inventory.get('owner_enabled_mcp_tools', [])]
    ids = [item.get('id') for item in items]
    if any((not isinstance(name, str) or not name for name in ids)):
        raise ValueError('Inventory has an invalid capability ID.')
    if len(ids) != len(set(ids)):
        raise ValueError('Inventory has duplicate capability IDs.')
    return {item['id']: item for item in items}

def check_scorecard(scorecard, inventory, *, artifact_root=None):
    """Return violations and honest dimension counts without editing evidence."""
    original = capability_ids(inventory)
    problems = []
    rows = scorecard.get('capabilities', [])
    if not isinstance(rows, list):
        return {'accepted': False, 'violations': ['capabilities must be an array']}
    seen = Counter((row.get('id') for row in rows if isinstance(row, dict)))
    for name, count in seen.items():
        if count != 1:
            problems.append(f'Duplicate scorecard capability: {name}')
    for name in sorted(set(original) - set(seen)):
        problems.append(f'Missing current capability: {name}')
    for name in sorted(set(seen) - set(original), key=str):
        problems.append(f'Not in fresh current inventory: {name}')
    if scorecard.get('inventory_sha256') != inventory.get('inventory_sha256'):
        problems.append('Scorecard inventory hash does not match the fresh inventory.')
    if 'discovered_count' in scorecard and scorecard['discovered_count'] != len(original):
        problems.append('Reported discovered_count is not the dynamic inventory count.')
    if 'discovered_ids' in scorecard and set(scorecard['discovered_ids']) != set(original):
        problems.append('Reported discovered_ids differ from the dynamic inventory.')
    if 'inventory_count' in scorecard and scorecard['inventory_count'] != len(original):
        problems.append('Reported inventory_count differs from the current dynamic inventory.')
    if 'tested_count' in scorecard and scorecard['tested_count'] != len(rows):
        problems.append('Reported tested_count differs from actual scorecard rows.')
    dimensions = {name: Counter() for name in DIMENSIONS}
    implementation_passes = 0
    evidence_modes = Counter()
    for row in rows:
        if not isinstance(row, dict):
            problems.append('Non-object capability row.')
            continue
        name = row.get('id')
        expected = original.get(name)
        if expected:
            for key in ('definition_hash', 'handler_module', 'handler_sha256'):
                if expected.get(key) is not None and row.get(key) != expected[key]:
                    problems.append(f'{name}: current {key} does not match.')
        measured = row.get('dimensions')
        if not isinstance(measured, dict):
            problems.append(f'{name}: dimensions must be an object.')
            continue
        for dimension in DIMENSIONS:
            entry = measured.get(dimension)
            label = f'{name}/{dimension}'
            if not isinstance(entry, dict):
                problems.append(f'{label}: no explicit outcome.')
                dimensions[dimension]['missing'] += 1
                continue
            status, mode = (entry.get('status'), entry.get('mode'))
            if status not in STATUSES:
                problems.append(f'{label}: invalid outcome status.')
            dimensions[dimension][status or 'missing'] += 1
            if not isinstance(mode, str) or not mode:
                problems.append(f'{label}: missing evidence mode.')
            else:
                evidence_modes[mode] += 1
            if status in {'blocked', 'not_applicable'} and (not entry.get('reason')):
                problems.append(f'{label}: blocked/inapplicable outcome has no reason.')
            if status == 'fail' and (not entry.get('receipt')) and (not entry.get('reason')):
                problems.append(f'{label}: failure has no observed receipt or explicit reason.')
            if status == 'pass':
                assertions = entry.get('assertions')
                if not isinstance(assertions, list) or not assertions:
                    problems.append(f'{label}: pass has no assertions.')
                else:
                    for assertion in assertions:
                        if not isinstance(assertion, dict) or not assertion.get('check') or assertion.get('passed') is not True or ('observed' not in assertion) or ('expected' not in assertion):
                            problems.append(f'{label}: pass assertion lacks a successful observed check.')
                if not isinstance(entry.get('receipt'), dict) or not entry['receipt']:
                    problems.append(f'{label}: pass has no actual receipt.')
                if dimension in {'valid_arguments', 'output_contract', 'end_to_end'}:
                    if mode not in IMPLEMENTATION_MODES:
                        problems.append(f'{label}: gate/metadata evidence cannot establish implementation success.')
                    if entry.get('receipt', {}).get('original_handler_entered') is not True:
                        problems.append(f'{label}: no proof the original handler entered.')
                if dimension == 'dependency_unavailable' and mode in IMPLEMENTATION_MODES and (entry.get('receipt', {}).get('original_handler_entered') is not True):
                    problems.append(f'{label}: a pre-handler refusal cannot prove implementation dependency handling.')
                if dimension == 'end_to_end' and mode in IMPLEMENTATION_MODES and (entry.get('receipt', {}).get('original_handler_entered') is True):
                    implementation_passes += 1
                if entry.get('receipt_sha256') and digest(entry.get('receipt')) != entry['receipt_sha256']:
                    problems.append(f'{label}: receipt digest does not match its evidence.')
                if dimension == 'natural_language_selection' and mode == 'retrieval_only':
                    if entry.get('model_evaluation_passed') is True:
                        problems.append(f'{label}: metadata retrieval is not actual model evaluation.')
                if mode in {'original_mock_dependency', 'original_gate', 'retrieval_only'}:
                    if entry.get('live_integration_verified') is True:
                        problems.append(f'{label}: controlled/gate/metadata evidence is not live integration.')
            artifact = entry.get('artifact')
            if artifact and artifact_root is not None:
                target = (Path(artifact_root) / artifact).resolve()
                if target.suffix.casefold() not in {'.json', '.jsonl', '.xml'}:
                    problems.append(f'{label}: unsupported evidence artifact type.')
                elif not target.is_file():
                    problems.append(f'{label}: evidence artifact absent.')
                elif not entry.get('artifact_sha256'):
                    problems.append(f'{label}: artifact is not hash-bound.')
                elif hashlib.sha256(target.read_bytes()).hexdigest() != entry['artifact_sha256']:
                    problems.append(f'{label}: evidence artifact hash mismatch.')
    return {'scope': 'Fresh dynamic inventory and evidence claims; no inference or foreign provider execution.', 'accepted': not problems, 'discovered_count': len(original), 'scorecard_rows': len(rows), 'violations': problems, 'dimension_outcomes': {key: dict(value) for key, value in dimensions.items()}, 'original_implementation_end_to_end_passes': implementation_passes, 'evidence_modes': dict(evidence_modes), 'coverage_is_not_success': True}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--scorecard', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--artifact-root', type=Path)
    args = parser.parse_args()
    result = check_scorecard(json.loads(args.scorecard.read_text(encoding='utf8')), json.loads(args.inventory.read_text(encoding='utf8')), artifact_root=args.artifact_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps({key: value for key, value in result.items() if key != 'violations'}))
    raise SystemExit(0 if result['accepted'] else 1)
if __name__ == '__main__':
    main()
