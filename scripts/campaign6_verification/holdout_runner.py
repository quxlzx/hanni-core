"""Claim and run the entire sealed independent final once after manager freeze."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from scripts.campaign6_verification.executor import run_case, write

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_freeze(directory):
    """Verify exact manager bytes without modifying its proof or owner's files."""
    directory = Path(directory).resolve()
    summary = json.loads((directory / 'SUMMARY.json').read_text())
    manifest = json.loads((directory / 'MANIFEST.json').read_text())
    if sha(directory / 'MANIFEST.json') != summary['manifest_sha256'] or sha(directory / 'source.zip') != summary['archive_sha256']:
        raise RuntimeError('Freeze receipt integrity mismatch')
    for relative, expected in manifest.items():
        path = ROOT / relative
        if path.is_symlink() or not path.is_file() or sha(path) != expected:
            raise RuntimeError('Frozen source/configuration/input mismatch')
    with zipfile.ZipFile(directory / 'source.zip') as archive:
        if set(archive.namelist()) != set(manifest):
            raise RuntimeError('Frozen archive membership mismatch')
        if any((hashlib.sha256(archive.read(name)).hexdigest() != expected for name, expected in manifest.items())):
            raise RuntimeError('Frozen archive member mismatch')
    from scripts.campaign6_manager.freeze import paths
    if {path.relative_to(ROOT).as_posix() for path in paths()} != set(manifest):
        raise RuntimeError('Frozen source membership changed')
    for relative, expected in summary['owner_configuration_sha256'].items():
        if sha(ROOT / relative) != expected:
            raise RuntimeError('Protected owner configuration changed')
    return {'manifest_sha256': summary['manifest_sha256'], 'archive_sha256': summary['archive_sha256'], 'files': len(manifest), 'source_matches': True}

def grade(receipt, oracle):
    if receipt['id'] != oracle['id']:
        raise ValueError('Independent oracle identity mismatch')
    checks = []

    def compare(name, actual, expected):
        checks.append({'check': name, 'passed': actual == expected, 'actual': actual, 'expected': expected})
    expected = oracle['expected']
    jobs = receipt['jobs']
    derived = {'ordered_choices': receipt.get('ordered_choices'), 'successful_requests': len(receipt['results']), 'max_active': receipt['max_active'], 'request_calls': sum((len(calls) for calls in receipt['provider_calls'].values())), 'completed_receipts': sum((job['state'] == 'COMPLETED' for job in jobs)), 'terminal_states': sorted((job['state'] for job in jobs)), 'selected_worker': jobs[0].get('worker_id') if len(jobs) == 1 else None, 'attempt': jobs[0].get('attempt') if len(jobs) == 1 else None, 'waiting_after': receipt['waiting_after'], 'first_observed_queued': receipt['first_observed_queued'], 'second_queue_rejected': receipt['second_queue_rejected'], 'all_reservations_released': receipt['all_reservations_released']}
    for name, value in expected.items():
        compare(name, derived.get(name), value)
    compare('owned_providers_closed', receipt['owned_providers_closed'], True)
    compare('owned_scheduler_closed', receipt['owned_scheduler_closed'], True)
    compare('owned_registry_closed', receipt['owned_registry_closed'], True)
    return {'id': receipt['id'], 'category': receipt['category'], 'passed': all((check['passed'] for check in checks)), 'checks': checks}

def run(output, freeze):
    output = output.resolve()
    private = ROOT / 'data/campaign6-verifier/holdout'
    if output.exists() or not output.is_relative_to((ROOT / 'data/campaign6-verifier').resolve()):
        raise ValueError('Use a fresh verifier-owned directory')
    seal = json.loads((private / 'seal.json').read_text())
    for name, expected in seal['hashes'].items():
        if sha(private / name) != expected:
            raise RuntimeError('Independent private seal changed')
    proof = verify_freeze(freeze)
    cases = json.loads((private / 'inputs.json').read_text())['cases']
    if len(cases) != seal['cases']:
        raise RuntimeError('Independent final membership mismatch')
    claim = private / 'FINAL_CLAIM.json'
    claim_value = {'claimed_at': datetime.now(timezone.utc).isoformat(), 'output': str(output), 'cases': len(cases), 'seal_sha256': sha(private / 'seal.json'), 'freeze': proof}
    with claim.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(claim_value, stream, indent=2)
        stream.write('\n')
    output.mkdir(parents=True)
    write(output / 'START.json', claim_value)
    receipts = []
    completed = False
    try:
        for case in cases:
            verify_freeze(freeze)
            try:
                row = run_case(case, output / case['id'])
            except Exception as exc:
                row = {'id': case['id'], 'category': case['category'], 'harness_error': {'class': type(exc).__name__, 'message': str(exc)}}
            receipts.append(row)
            write(output / 'RAW.json', {'receipts': receipts})
            write(output / 'PROGRESS.json', {'completed': len(receipts), 'planned': len(cases), 'harness_errors': sum(('harness_error' in row for row in receipts))})
            print(json.dumps({'completed': len(receipts), 'planned': len(cases)}), flush=True)
        proof = verify_freeze(freeze)
        completed = True
    finally:
        write(output / 'CLOSED.json', {'completed': completed, 'receipts': len(receipts), 'raw_sha256': sha(output / 'RAW.json') if (output / 'RAW.json').exists() else None, 'freeze': proof, 'no_retries': True})
    oracles = {row['id']: row for row in json.loads((private / 'oracles.json').read_text())['oracles']}
    grades = [{'id': row['id'], 'category': row['category'], 'passed': False, 'harness_error': row['harness_error']} if 'harness_error' in row else grade(row, oracles[row['id']]) for row in receipts]
    write(output / 'GRADES.json', {'grades': grades})
    summary = {'cases': len(grades), 'passed': sum((row['passed'] for row in grades)), 'category_counts': dict(Counter((row['category'] for row in grades))), 'categories_passed': dict(Counter((row['category'] for row in grades if row['passed']))), 'harness_errors': sum(('harness_error' in row for row in grades)), 'actual_model_inference': 0, 'actual_hardware_measurements': 0, 'raw_sha256': sha(output / 'RAW.json'), 'grades_sha256': sha(output / 'GRADES.json'), 'closed_sha256': sha(output / 'CLOSED.json'), 'seal_sha256': sha(private / 'seal.json'), 'freeze': proof, 'scope': 'Original guarded scheduling with controlled loopback providers; no live-model/hardware claims.'}
    write(output / 'SUMMARY.json', summary)
    print(json.dumps(summary), flush=True)
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    args = parser.parse_args()
    run(args.output, args.freeze)
