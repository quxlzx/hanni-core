"""Oracle-free publication from closed private evidence; no execution or edits."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def publish(output):
    summary = json.loads((output / 'SUMMARY.json').read_text())
    raw = json.loads((output / 'RAW.json').read_text())['receipts']
    grades = json.loads((output / 'GRADES.json').read_text())['grades']
    for name, key in (('RAW.json', 'raw_sha256'), ('GRADES.json', 'grades_sha256'), ('CLOSED.json', 'closed_sha256')):
        if hashlib.sha256((output / name).read_bytes()).hexdigest() != summary[key]:
            raise RuntimeError('Closed independent receipt mismatch')
    failures = []
    for row in grades:
        if not row['passed']:
            failures.append({'id': row['id'], 'category': row['category'], 'failed_checks': [check['check'] for check in row.get('checks', []) if not check['passed']], 'harness_error': 'harness_error' in row})
    summary.update(failures=failures, private_evidence=output.relative_to(ROOT).as_posix(), controlled_http_requests=sum((len(calls) for row in raw for calls in row.get('provider_calls', {}).values())), owned_cleanup_complete=all((row.get('owned_providers_closed') and row.get('owned_scheduler_closed') and row.get('owned_registry_closed') for row in raw)), all_owned_reservations_released=all((row.get('all_reservations_released') for row in raw)), quality_speed_tokens_peak_vram=None)
    target = ROOT / 'docs/campaign6/FINAL_HOLDOUT.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'cases': summary['cases'], 'passed': summary['passed'], 'published_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}))
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    publish(parser.parse_args().output.resolve())
