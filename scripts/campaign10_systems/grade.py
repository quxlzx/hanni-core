"""Prospective development-only grading, separate from operation dispatch."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from .author import DIMENSIONS

def pointer(value, path):
    for token in path.strip('/').split('/') if path != '/' else []:
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value

def evaluate(receipt, oracle):
    results = []
    for expected in oracle['checks']:
        try:
            actual = pointer(receipt, expected['path'])
            value, op = (expected['value'], expected['op'])
            passed = actual == value if op == 'eq' else value in actual if op == 'contains' else actual <= value if op == 'le' else actual >= value if op == 'ge' else False
            error = None
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            actual, passed, error = (None, False, type(exc).__name__)
        results.append({**expected, 'actual': actual, 'passed': passed, 'lookup_error': error})
    dimensions = {}
    for name in DIMENSIONS:
        checks = [row for row in results if row['dimension'] == name]
        measured = bool(checks)
        if name == 'final_response':
            dimensions[name] = {'status': 'NOT_MEASURED', 'reason': 'No genuine model final response in this cohort.'}
        else:
            dimensions[name] = {'status': ('PASS' if all((r['passed'] for r in checks)) else 'FAIL') if measured else 'NOT_MEASURED', 'scope': 'original isolated implementation / declared controlled leaves', 'check_paths': [r['path'] for r in checks]}
    passed = all((row['passed'] for row in results))
    return {'id': receipt['id'], 'family': receipt['family'], 'contract_verdict': 'PASS' if passed else 'FAIL', 'evidence_categories': receipt['evidence_categories'], 'dimensions': dimensions, 'checks': results, 'model_task_completion': 'NOT_MEASURED', 'major_subsystem_status': 'NOT_IMPLEMENTED' if receipt.get('real_vision') else 'BLOCKED_PHYSICAL_AUDIO' if receipt.get('physical_audio') else 'CONTROLLED_ONLY', 'harness_error': receipt.get('harness_error'), 'elapsed_seconds': receipt['elapsed_seconds']}

def grade(receipts_path, oracles_path, output):
    receipts_path, oracles_path, output = (Path(receipts_path), Path(oracles_path), Path(output))
    if output.exists():
        raise ValueError('Never replace a prior development outcome.')
    raw = [json.loads(line) for line in receipts_path.read_text(encoding='utf8').splitlines() if line.strip()]
    oracles = {row['id']: row for row in (json.loads(line) for line in oracles_path.read_text(encoding='utf8').splitlines() if line.strip())}
    if set(oracles) != {row['id'] for row in raw}:
        raise ValueError('Receipt and prospective oracle identities differ.')
    rows = [evaluate(row, oracles[row['id']]) for row in raw]
    result = {'tasks': len(rows), 'counts': dict(Counter((row['contract_verdict'] for row in rows))), 'harness_errors': sum((row['harness_error'] is not None for row in rows)), 'families': {name: dict(Counter((row['contract_verdict'] for row in rows if row['family'] == name))) for name in sorted({row['family'] for row in rows})}, 'dimensions': {name: dict(Counter((row['dimensions'][name]['status'] for row in rows))) for name in DIMENSIONS}, 'receipts_sha256': hashlib.sha256(receipts_path.read_bytes()).hexdigest(), 'oracles_sha256': hashlib.sha256(oracles_path.read_bytes()).hexdigest(), 'scope': 'Prospective controlled development contracts, not genuine AI end-to-end quality', 'cases': rows}
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf8', newline='\n')
    return result
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipts', required=True)
    parser.add_argument('--oracles', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = grade(args.receipts, args.oracles, args.output)
    print(json.dumps({key: result[key] for key in ('tasks', 'counts', 'harness_errors', 'dimensions')}))
