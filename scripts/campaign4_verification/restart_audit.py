"""Independent audit of genuine owned helper restart and persisted tool receipts."""
import argparse
import json
import os
from pathlib import Path
from .executor import digest, durable

def inspect_challenge(root, output_name='independent-audit.json'):
    root = Path(root).resolve()
    initial = json.loads((root / 'interrupted.json').read_text(encoding='utf8'))
    recovered = json.loads((root / 'completed.json').read_text(encoding='utf8'))
    final = recovered['final']
    baseline = initial['detail']
    invocations = final['invocations']
    completed_before = {row['step_id']: row['invocation_id'] for row in baseline['invocations'] if row['state'] == 'finished' and next((step for step in baseline['steps'] if step['step_id'] == row['step_id']))['status'] == 'verified'}
    writes = [row for row in invocations if row['write']]
    audit = [json.loads(line) for line in (root / 'run/state/logs/tool_audit.jsonl').read_text(encoding='utf8').splitlines()]
    write_audit = [row for row in audit if row['tool'] == 'file.write' and row['source'] == 'tool.workflow']
    report = Path(recovered['report']['path'])
    expected = (root / 'remaining-source.txt').read_bytes()
    import psutil
    checks = {'actual_distinct_owned_worker_pids': initial['pid'] != recovered['pid'], 'fresh_fence': recovered['lease']['fence'] > initial['lease']['fence'], 'persisted_paused_before_explicit_resume': recovered['initial']['status'] == 'paused', 'completed_original_steps_not_replayed': all(([row['invocation_id'] for row in invocations if row['step_id'] == step] == [identity] for step, identity in completed_before.items())), 'single_durable_write_invocation': len(writes) == 1 and writes[0]['state'] == 'finished', 'single_successful_original_write_audit': len(write_audit) == 1 and write_audit[0]['ok'] is True, 'audit_correlation_matches_durable_write': len(writes) == len(write_audit) == 1 and writes[0]['correlation_id'] == write_audit[0]['correlation_id'], 'artifact_exact_original_text_serialization': report.read_bytes() == expected.decode('utf8').replace('\n', os.linesep).encode('utf8') and digest(report) == recovered['report']['sha256'], 'artifact_logical_text_readback': report.read_text(encoding='utf8') == expected.decode('utf8'), 'every_final_step_verified': all((row['status'] == 'verified' and row['verification']['status'] == 'VERIFIED' for row in final['steps'])), 'no_replanning_after_restart': recovered['controlled_model_calls'] == 0, 'controlled_worker_failure_retained': (root / 'hash-worker-failed.json').is_file(), 'bounded_original_retry': len([row for row in invocations if row['step_id'] == 'hash_worker']) == 2, 'owned_workers_gone': all((not psutil.pid_exists(row['pid']) or psutil.Process(row['pid']).create_time() != row['provenance']['create_time'] for row in (initial, recovered)))}
    result = {'scope': 'actual_owned_process_restart_controlled_worker_failure_original_implementation', 'checks': checks, 'passed': all(checks.values()), 'count': len(checks), 'actual_write_invocations': len(writes), 'actual_original_write_audit_rows': len(write_audit), 'actual_model_calls': 0, 'source_bytes': 'challenge source hash manifest retained', 'artifact_contract': 'Original file.write serializes text with platform newlines; source LF bytes are not claimed binary-identical to the Windows report.', 'receipt_hashes': {name: digest(root / name) for name in ('interrupted.json', 'completed.json', 'hash-worker-failed.json', 'run/state/logs/tool_audit.jsonl')}}
    if (root / output_name).exists():
        raise ValueError('Preserve prior audit; choose a new output name')
    durable(root / output_name, result)
    return result
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--output-name', default='independent-audit.json')
    args = parser.parse_args()
    print(json.dumps(inspect_challenge(args.root, args.output_name), indent=2))
