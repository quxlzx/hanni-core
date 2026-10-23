"""New prospective eligibility/parallel cases; original120 oracles unchanged."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from scripts.campaign4.development_corpus import base, criterion, read

def corpus():
    content = 'isolated evidence'
    stat = {'step_id': 'inspect', 'description': 'Check file properties and SHA-256 hash of {root}/input.txt', 'kind': 'tool', 'capability_id': 'file.stat', 'dependencies': [], 'required': True, 'criteria': [criterion('equals', '/data/sha256', hashlib.sha256(content.encode()).hexdigest())], 'arguments': {'path': '{root}/input.txt', 'hash': True}}
    cases = []
    configurations = [('retry_once', 'completed', {'kind': 'timeout_before', 'times': 1}, [], {'invocations': 2, 'retry_checkpoints': 1}), ('retry_exhausted', 'blocked', {'kind': 'timeout_before', 'times': 9}, [], {'invocations': 2, 'max_step_attempts': 2}), ('recover_paused', 'paused', {'kind': 'barrier', 'times': 1}, [{'at': 'active', 'operation': 'restart'}], {'invocations': 1, 'recovery_eligible': True, 'invocation_states': ['abandoned']}), ('recover_resume', 'completed', {'kind': 'barrier', 'times': 1}, [{'at': 'active', 'operation': 'restart'}, {'at': 'stopped', 'operation': 'resume'}], {'invocations': 2, 'recovery_eligible': True, 'max_step_attempts': 2})]
    for index, (name, status, fault, controls, expected) in enumerate(configurations, 1):
        row = base('Bounded retries' if index <= 2 else 'Recovery after restart', index, 'Actual original retry-safe file.stat hash: ' + name, steps=[deepcopy(stat)], status=status, goal='Check file properties and SHA-256 hash of {root}/input.txt.', faults=[{**fault, 'method': 'hash', 'path': '{root}/input.txt'}], controls=controls, expected=expected)
        row['id'] = 'WFSUP-STAT-' + str(index)
        cases.append(row)
    row = base('Safe parallel execution', 1, 'Two original read handlers demonstrably overlap before release.', steps=[read(), read('second', 'second.txt', text='second evidence')], files=[{'path': '{root}/input.txt', 'text': content}, {'path': '{root}/second.txt', 'text': 'second evidence'}], goal='Read local files {root}/input.txt and {root}/second.txt independently.', faults=[{'kind': 'barrier', 'method': 'read', 'path': path} for path in ['{root}/input.txt', '{root}/second.txt']], controls=[{'at': 'active', 'operation': 'wait_entered', 'count': 2}], expected={'verified_steps': 2, 'max_active_lower': 2, 'max_active_upper': 2})
    row['id'] = 'WFSUP-PARALLEL-1'
    cases.append(row)
    return cases

def seal(destination):
    raw = json.dumps(corpus(), indent=2, sort_keys=True).encode() + b'\n'
    destination = Path(destination)
    if destination.exists() and destination.read_bytes() != raw:
        raise ValueError('Supplement already frozen')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return {'cases': len(corpus()), 'sha256': hashlib.sha256(raw).hexdigest()}
if __name__ == '__main__':
    print(json.dumps(seal('evals/workflows/campaign4_supplemental.json'), indent=2))
