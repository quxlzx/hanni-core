"""Prospective exposed-development correction set; frozen original unchanged.

The original corpus has graph tests whose default goal mentions only its first
source. A source-preserving planner properly refuses additional source paths.
This new separately scored set states the intended original graph objectives
explicitly before execution. It is not an unseen evaluation or score migration.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
INTENDED = ['WFDEV-04-01', 'WFDEV-05-03', 'WFDEV-05-05', 'WFDEV-06-01', 'WFDEV-06-02', 'WFDEV-06-03', 'WFDEV-06-04', 'WFDEV-06-05', 'WFDEV-06-06', 'WFDEV-11-02', 'WFDEV-11-03', 'WFDEV-20-05']

def corpus():
    original_path = Path(__file__).resolve().parents[2] / 'evals/workflows/campaign4_development.json'
    originals = {row['id']: row for row in json.loads(original_path.read_text(encoding='utf-8'))}
    rows = []
    for case_id in INTENDED:
        row = deepcopy(originals[case_id])
        sources = list(dict.fromkeys((step['arguments']['path'] for step in row['steps'] if step['capability_id'] == 'file.read')))
        independent = row['category'] == 'Safe parallel execution' and case_id != 'WFDEV-06-03'
        phrase = 'Read the local text file ' + (' and independently read the local text file ' if independent else ', then read the local text file ').join(sources) + '.'
        if any((step['kind'] == 'artifact' for step in row['steps'])):
            phrase += ' Save the requested report after all its prerequisites are verified.'
        if any((not step['required'] for step in row['steps'])):
            phrase += ' The missing additional source is optional; retain verified work if it is unavailable.'
        row.update(id='WFEX-' + case_id.removeprefix('WFDEV-'), goal=phrase, scenario='Explicit owner objective for exposed original graph: ' + row['scenario'], original_graph_id=case_id, evaluation_class='exposed_development_authoring_correction_new_inputs')
        rows.append(row)
    return rows

def seal(destination):
    raw = json.dumps(corpus(), sort_keys=True, indent=2).encode('utf-8') + b'\n'
    destination = Path(destination)
    if destination.exists() and destination.read_bytes() != raw:
        raise RuntimeError('Explicit-goal supplement is already sealed')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return {'cases': len(corpus()), 'sha256': hashlib.sha256(raw).hexdigest(), 'classification': 'separate exposed development; original120 oracles unchanged'}
if __name__ == '__main__':
    print(json.dumps(seal('evals/workflows/campaign4_explicit_goal_supplement.json'), indent=2))
