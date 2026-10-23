"""Independently audit public development receipts without opening final inputs."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def audit(path):
    path = path.resolve()
    if not path.is_relative_to((ROOT / 'data/campaign5-development').resolve()):
        raise ValueError('Manager audit accepts only public development collections.')
    metadata = json.loads((path / 'INPUT_METADATA.json').read_text(encoding='utf8'))
    declared = metadata['selected_case_ids']
    summary = json.loads((path / 'SUMMARY.json').read_text(encoding='utf8'))
    arms = json.loads((path / 'ARMS.json').read_text(encoding='utf8'))
    errors = []
    evidence = {}
    total_dispatches = 0
    total_cases = 0
    for label, mode, endpoint in arms:
        file = path / 'arms' / label / 'receipts.jsonl'
        rows = [json.loads(line) for line in file.read_text(encoding='utf8').splitlines()]
        if [row['id'] for row in rows] != declared:
            errors.append(f'{label}: case coverage/order mismatch')
        if len({row['id'] for row in rows}) != len(rows):
            errors.append(f'{label}: duplicate case IDs')
        for row in rows:
            if row['mode'] != mode or row['requested_endpoint_id'] != endpoint:
                errors.append(f'{label}: mode/assignment mismatch')
            actual = row['real_generation_dispatches']
            if not actual and (row['semantic_pass'] is not None or row.get('actual_response') is not None):
                errors.append(f"{label}/{row['id']}: false unexecuted semantic result")
            wire = row.get('raw_http', [])
            observed = sum((call['method'] == 'POST' and call['path'] in {'/v1/chat/completions', '/chat/completions', '/v1/messages'} for call in wire))
            if actual != observed:
                errors.append(f"{label}/{row['id']}: dispatch/wire mismatch")
            if any((call.get('raw_truncated') for call in wire)):
                errors.append(f"{label}/{row['id']}: lost raw provenance")
            if row.get('reference_backed_collaboration'):
                errors.append(f"{label}/{row['id']}: comparison used reference-backed selection")
            if row.get('tool_execution') or row.get('workflow_execution'):
                errors.append(f"{label}/{row['id']}: unauthorized benchmark scope")
        arm_summary = summary['arms'][label]
        dispatches = sum((row['real_generation_dispatches'] for row in rows))
        if arm_summary['tasks'] != len(rows) or arm_summary['actual_http_generation_requests'] != dispatches:
            errors.append(f'{label}: summary denominator mismatch')
        evidence[label] = {'cases': len(rows), 'by_category': dict(Counter((row['category'] for row in rows))), 'classification_counts': dict(Counter((row['classification'] for row in rows))), 'semantic_measured': sum((row['semantic_pass'] is not None for row in rows)), 'actual_generation_dispatches': dispatches, 'receipts_sha256': hashlib.sha256(file.read_bytes()).hexdigest(), 'source_case_settings': 'Prospectively sealed development inputs; no answers in execution.'}
        total_cases += len(rows)
        total_dispatches += dispatches
    if total_dispatches != summary['actual_generation_requests']:
        errors.append('Global dispatch denominator mismatch')
    before = (path / 'SOURCE_BEFORE.json').read_bytes()
    after = (path / 'SOURCE_AFTER.json').read_bytes()
    if before != after or not summary['source_unchanged']:
        errors.append('Source/config/benchmark freeze mismatch')
    result = {'collection': path.relative_to(ROOT).as_posix(), 'errors': errors, 'all_structural_checks_passed': not errors, 'arms': evidence, 'arm_count': len(arms), 'case_attempt_records': total_cases, 'actual_generation_dispatches': total_dispatches, 'scope': 'Manager structural/provenance audit; not model answer grading or private holdout.'}
    (path / 'MANAGER_AUDIT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8', newline='\n')
    if errors:
        raise RuntimeError('; '.join(errors))
    print(json.dumps({key: value for key, value in result.items() if key != 'arms'}), flush=True)
    return result
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('collection', type=Path)
    audit(parser.parse_args().collection)
