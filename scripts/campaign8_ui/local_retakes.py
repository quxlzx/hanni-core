"""Exposed input-only setup corrections; the original twelve remain immutable."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from .plan import validate_input

def publish(original, output):
    original, output = (Path(original), Path(output))
    if output.exists():
        raise ValueError('Preserve every original and separately sealed retake.')
    inputs = json.loads((original / 'inputs.json').read_text(encoding='utf8'))
    oracles = json.loads((original / 'oracles.json').read_text(encoding='utf8'))
    selected = {'memory-create-proposal', 'memory-consolidate', 'memory-review-index', 'mcp-import-selection', 'mcp-import-confirm', 'mcp-enable-local', 'mcp-disable-local', 'mcp-private-export-select'}
    rows = [copy.deepcopy(row) for row in inputs if row['id'].removeprefix('local-final-') in selected]
    tab = {'action': 'click', 'selector': '.memory-tabs button', 'index': 1}
    setup = [{'action': 'click', 'role': 'button', 'name': 'Import config'}, {'action': 'upload_fixture', 'selector': 'dialog input[type="file"]', 'fixture_id': 'mcp-disabled-config'}, {'action': 'click', 'role': 'button', 'name': 'Preview import'}]
    reasons = {}
    for row in rows:
        key = row['id'].removeprefix('local-final-')
        if key == 'memory-create-proposal':
            row['steps'][0] = copy.deepcopy(tab)
            reasons[row['id']] = 'Exact accessible tab name includes the original pending-count badge; fixed source tab index is explicit.'
        elif key.startswith('memory-'):
            row['steps'].insert(0, copy.deepcopy(tab))
            reasons[row['id']] = 'Each native case navigation remounts the component; explicitly select the original Review queue before its controls.'
        elif key == 'mcp-import-selection':
            row['steps'] = copy.deepcopy(setup) + row['steps'] + [{'action': 'click', 'role': 'button', 'name': 'Cancel'}]
            reasons[row['id']] = 'Reconstruct the actual file-preview dialog in this case; previous case local React dialog state is not retained.'
        elif key == 'mcp-import-confirm':
            row['steps'] = copy.deepcopy(setup) + row['steps']
            reasons[row['id']] = 'Reconstruct preview before original confirmation and commit; no API or force-click substitution.'
        elif key == 'mcp-disable-local':
            row['steps'].insert(0, {'action': 'click', 'selector': '.mcp-server-row', 'index': 0})
            reasons[row['id']] = 'Explicitly select the persisted original server after navigation remount before Disable server.'
        elif key == 'mcp-private-export-select':
            row['steps'].pop(0)
            reasons[row['id']] = 'Navigation starts on server listing; Export config is original listing action, not Back to servers detail action.'
        else:
            reasons[row['id']] = 'Previous import failed at setup; this unchanged enable action now follows a successfully persisted original disabled fixture.'
        validate_input(row)
    oracle_rows = [row for row in oracles if row['id'] in {r['id'] for r in rows}]
    output.mkdir(parents=True)
    hashes = {}
    for name, obj in [('inputs.json', rows), ('oracles.json', oracle_rows)]:
        wire = json.dumps(obj, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': len(rows), 'execution_attempted': False, 'hashes': hashes, 'original_hashes': {name: hashlib.sha256((original / name).read_bytes()).hexdigest() for name in ('inputs.json', 'oracles.json')}, 'reasons': reasons, 'original_oracle_objects_unchanged': True, 'production_changes': False, 'generation_authorized': False, 'provider_execution_authorized': False}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.original, args.output)))
