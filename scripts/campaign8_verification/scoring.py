"""Post-close independent grading; missing evidence cannot become a pass."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

def criterion_result(expected, observed, *, evidence, name=''):
    if not evidence or observed is None:
        return {'status': 'unmeasured', 'passed': False, 'reason': 'Missing independent original evidence'}
    if name.endswith('_max'):
        matched = type(expected) in {int, float} and type(observed) in {int, float} and math.isfinite(expected) and math.isfinite(observed) and (observed <= expected)
    else:
        matched = type(expected) is type(observed) and expected == observed
    return {'status': 'pass' if matched else 'fail', 'passed': matched, 'observed': observed, 'evidence': evidence}

def grade_case(receipt, oracle, review):
    if receipt.get('id') != oracle.get('id') or review.get('id') != receipt.get('id'):
        raise ValueError('Case identity mismatch')
    if not review.get('receipt_sha256') or review.get('independently_reviewed') is not True:
        raise ValueError('Independent review must bind the immutable raw receipt')
    observed = review.get('observed', {})
    evidence = review.get('evidence', {})
    criteria = {key: criterion_result(value, observed.get(key), evidence=evidence.get(key), name=key) for key, value in oracle['expected'].items()}
    return {'id': receipt['id'], 'family': receipt['family'], 'route': receipt['route'], 'surface': receipt['surface'], 'receipt_sha256': review['receipt_sha256'], 'criteria': criteria, 'passed': not receipt.get('error') and bool(criteria) and all((row['passed'] for row in criteria.values())), 'automatic_failure': receipt.get('error'), 'manual_classification': review.get('manual_classification'), 'grade_promotion': False}

def grade_closed(directory, *, oracle_path, oracle_sha256, reviews_path):
    directory = Path(directory)
    closed = json.loads((directory / 'CLOSED.json').read_text(encoding='utf8'))
    if not closed.get('complete') or closed.get('attempted') != closed.get('case_count'):
        raise ValueError('Grading requires complete closed once-only observations')
    if hashlib.sha256(Path(oracle_path).read_bytes()).hexdigest() != oracle_sha256:
        raise ValueError('Frozen private oracle bytes changed')
    oracles = json.loads(Path(oracle_path).read_text(encoding='utf8'))
    reviews = json.loads(Path(reviews_path).read_text(encoding='utf8'))
    by_oracle = {row['id']: row for row in oracles}
    by_review = {row['id']: row for row in reviews}
    ids = [row['id'] for row in closed['cases']]
    if len(ids) != len(set(ids)) or len(by_oracle) != len(oracles) or len(by_review) != len(reviews) or (set(ids) != set(by_oracle)) or (set(ids) != set(by_review)):
        raise ValueError('Complete one-to-one final review coverage required')
    grades = []
    for item in closed['cases']:
        path = directory / 'cases' / (item['id'] + '.json')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item['receipt_sha256'] or digest != by_review[item['id']]['receipt_sha256']:
            raise ValueError('Raw final receipt changed or review binds different bytes')
        grades.append(grade_case(json.loads(path.read_text(encoding='utf8')), by_oracle[item['id']], by_review[item['id']]))
    return grades
