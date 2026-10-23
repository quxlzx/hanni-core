"""Separate prospective corrections; never change the original 79-case score."""
from copy import deepcopy
import json
from pathlib import Path
from scripts.campaign6_scheduling.author import seal

def build():
    cases = {c['id']: c for c in json.loads(Path('evals/compute/campaign6_development.json').read_text())['cases']}
    refs = {o['id']: o for o in json.loads(Path('evals/compute/campaign6_development_oracles.json').read_text())['oracles']}
    chosen = ['C6DEV-parallel_tasks-06', 'C6DEV-queue_saturation-04', 'C6DEV-queue_saturation-05', *['C6DEV-safe_reassignment-' + str(i).zfill(2) for i in range(1, 5)], 'C6DEV-result_verification-02', 'C6DEV-result_verification-04', 'C6DEV-result_verification-05']
    inputs = []
    oracles = []
    for index, source in enumerate(chosen):
        case = deepcopy(cases[source])
        oracle = deepcopy(refs[source])
        case['id'] = oracle['id'] = 'C6SUP-' + str(index + 1).zfill(2)
        case['original_case_id'] = source
        case['description'] = 'Separate corrected control: ' + case['description']
        if index == 0:
            case['start_background_first'] = True
            reason = 'Explicit occupying background entry before reserved interactive admission, rather than a thread-order race.'
        elif index < 7:
            case['policy_timeout_seconds'] = 3
            case['request']['queue_seconds'] = 2.5
            reason = 'Prospective total queue/runtime budget accommodates real controlled HTTP startup and retry dispatch; original .15-second expectations remain failures.'
        else:
            oracle['expected']['workflow_status'] = 'partially_completed'
            reason = 'Original source read verified but analysis rejected; exact partial status and no report write are the intended original contract.'
        case['supplement_scope'] = reason
        inputs.append(case)
        oracles.append(oracle)
    return ({'version': 1, 'cases': inputs}, {'version': 1, 'oracles': oracles})
if __name__ == '__main__':
    inputs, oracles = build()
    print(json.dumps({'cases': len(inputs['cases']), 'inputs_sha256': seal('evals/compute/campaign6_development_supplement.json', inputs), 'oracles_sha256': seal('evals/compute/campaign6_development_supplement_oracles.json', oracles)}, indent=2))
