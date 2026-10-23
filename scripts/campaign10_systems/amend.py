"""Transparent source-contract correction, never rewrite baseline/oracle files."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

def correction(inputs_path, oracles_path, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    original = [json.loads(line) for line in Path(inputs_path).read_text(encoding='utf8').splitlines() if line.strip()]
    oracle_rows = [json.loads(line) for line in Path(oracles_path).read_text(encoding='utf8').splitlines() if line.strip()]
    rows, changes = ([], [])
    for source in original:
        row = deepcopy(source)
        edits = []
        for step_index, step in enumerate(row['fixtures'].get('steps', [])):
            for criterion_index, criterion in enumerate(step.get('criteria', [])):
                if criterion.get('operator') in {'present', 'nonempty', 'json_valid', 'evidence_report'} and 'expected' not in criterion:
                    criterion['expected'] = None
                    edits.append(f'/fixtures/steps/{step_index}/criteria/{criterion_index}/expected')
        if edits:
            rows.append(row)
            changes.append({'id': row['id'], 'added_null_fields_only': edits})
    ids = {row['id'] for row in rows}

    def save(name, values):
        raw = ''.join((json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in values)).encode()
        (destination / name).write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()
    result = {'tasks': len(rows), 'inputs_sha256': save('inputs.jsonl', rows), 'oracles_sha256': save('oracles.jsonl', [r for r in oracle_rows if r['id'] in ids]), 'changes': changes, 'scope': 'Original planner requires expected:null for presence criteria; schema-only authored input correction.', 'original_inputs_sha256': hashlib.sha256(Path(inputs_path).read_bytes()).hexdigest(), 'original_oracles_sha256': hashlib.sha256(Path(oracles_path).read_bytes()).hexdigest(), 'oracle_semantics_unchanged': True, 'prior_results_preserved': True, 'executed': 0}
    (destination / 'AMENDMENT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8', newline='\n')
    return result
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', required=True)
    parser.add_argument('--oracles', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(correction(args.inputs, args.oracles, args.output), indent=2))
