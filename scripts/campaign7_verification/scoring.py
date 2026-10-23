"""Separate exact prospective grading; no input or expected content in exports."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def grade(receipt, oracle):
    expected = oracle['expected']
    observed = receipt.get('observed', {})
    checks = {key: {'observed': observed.get(key), 'expected': value, 'passed': key in observed and observed[key] == value} for key, value in expected.items()}
    return dict(id=receipt['id'], domain=receipt['domain'], category=receipt['category'], passed=bool(checks) and all((x['passed'] for x in checks.values())) and (not receipt.get('harness_error')), checks=checks, harness_error=receipt.get('harness_error'), receipt_sha256=receipt['receipt_sha256'])

def summarize(grades):
    groups = defaultdict(lambda: Counter(total=0, passed=0, failed=0, harness_errors=0))
    for row in grades:
        for key in (f"domain:{row['domain']}", f"category:{row['category']}", 'overall'):
            groups[key]['total'] += 1
            groups[key]['passed' if row['passed'] else 'failed'] += 1
            groups[key]['harness_errors'] += bool(row.get('harness_error'))
    return {key: dict(counts) for key, counts in sorted(groups.items())}

def score_run(run, oracles_path):
    run = Path(run)
    oracles = {row['id']: row for row in json.loads(Path(oracles_path).read_text(encoding='utf-8'))}
    index = json.loads((run / 'CLOSED.json').read_text(encoding='utf-8'))
    grades = []
    for item in index['receipts']:
        path = run / item['path']
        if digest(path) != item['sha256']:
            raise ValueError('Immutable receipt changed')
        receipt = json.loads(path.read_text(encoding='utf-8'))
        receipt['receipt_sha256'] = item['sha256']
        grades.append(grade(receipt, oracles[receipt['id']]))
    if len(grades) != len(oracles) or {row['id'] for row in grades} != set(oracles):
        raise ValueError('Incomplete or duplicated final coverage')
    payload = {'oracle_sha256': digest(oracles_path), 'grades': grades, 'aggregate': summarize(grades)}
    (run / 'GRADES.json').write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    return payload
