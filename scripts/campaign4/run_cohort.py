"""Seal/archive/run workflow development evidence without rewriting old raw data."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import statistics
import time
from scripts.campaign4.workflow_harness import run_case, transition_atomicity
REPO = Path(__file__).resolve().parents[2]

def archive(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for source in (REPO / 'src' / 'hanni').rglob('*.py'):
        relative = source.relative_to(REPO / 'src')
        raw = source.read_bytes()
        target = destination / 'src' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        manifest[str(relative).replace('\\', '/')] = hashlib.sha256(raw).hexdigest()
    (destination / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding='utf-8')
    return manifest

def production_manifest():
    import hanni
    location = Path(hanni.__file__).resolve().parent
    helpers = [*sorted((REPO / 'scripts/campaign4').glob('*.py')), REPO / 'scripts/v3_review/service_fixture.py', REPO / 'scripts/v3_review/fixtures.py', REPO / 'tests/helpers.py']
    configuration = sorted((REPO / 'config').glob('*.yaml'))
    return {'package_root': str(location), 'files': {str(source.relative_to(location)).replace('\\', '/'): hashlib.sha256(source.read_bytes()).hexdigest() for source in sorted(location.rglob('*.py'))}, 'controlled_helper_sources': {str(source.relative_to(REPO)).replace('\\', '/'): hashlib.sha256(source.read_bytes()).hexdigest() for source in helpers}, 'configuration_fixture_source_hashes': {str(source.relative_to(REPO)).replace('\\', '/'): hashlib.sha256(source.read_bytes()).hexdigest() for source in configuration}}

def evaluate(receipt, expected):
    """Independent desired-state assertions; executor never receives this oracle."""
    observations = []

    def check(label, observed, wanted):
        observations.append({'check': label, 'observed': observed, 'expected': wanted, 'passed': observed == wanted})
    detail = receipt.get('workflow', {})
    steps = detail.get('steps', [])
    invocations = detail.get('invocations', [])
    controls = receipt.get('controls', [])
    check('harness completed', receipt.get('harness_error'), None)
    check('final stopping state', detail.get('status'), expected['status'])
    mappings = {'invocations': len(invocations), 'verified_steps': sum((s['status'] == 'verified' for s in steps)), 'failed_steps': sum((s['status'] == 'failed' for s in steps)), 'unverified_steps': sum((s['status'] == 'unverified' for s in steps)), 'rejected_controls': sum((c.get('ok') is False for c in controls)), 'planner_calls': len(receipt.get('planner_calls', [])), 'finished_invocations': sum((i['state'] == 'finished' for i in invocations)), 'pending_action_approvals': sum((a['state'] == 'pending' and bool(a.get('step_id')) for a in detail.get('approvals', []))), 'retry_checkpoints': sum((c['kind'] == 'retry_scheduled' for c in detail.get('checkpoints', []))), 'artifact_count': len(detail.get('artifacts', [])), 'reported_verification': detail.get('verification_status')}
    for key, observed in mappings.items():
        if key in expected:
            check(key, observed, expected[key])
    if expected.get('no_duplicate_dispatch'):
        check('unique durable invocation ids', len({i['invocation_id'] for i in invocations}), len(invocations))
        check('write is never automatically replayed', any((i['write'] and i['attempt'] > 1 for i in invocations)), False)
        operations = [row['logical_operation'] for row in receipt.get('effect_ledger', []) if row['actual_effect']]
        check('consequential write effects occur once per logical operation', len(operations), len(set(operations)))
    if expected.get('no_unapproved_write'):
        check('all consequential write entries have original exact authority', any((not row['authorized'] for row in receipt.get('effect_ledger', []))), False)
    if 'max_step_attempts' in expected:
        check('attempt bound', max((s.get('attempts', 0) for s in steps), default=0) <= expected['max_step_attempts'], True)
    if 'invocation_states' in expected:
        check('durable invocation states', [i['state'] for i in invocations], expected['invocation_states'])
    if 'order' in expected:
        check('dispatch order', [i['step_id'] for i in invocations], expected['order'])
    for kind in expected.get('checkpoints', []):
        check('checkpoint: ' + kind, any((c['kind'] == kind for c in detail.get('checkpoints', []))), True)
    files = receipt.get('files', {})
    artifact_files = {name: row for name, row in files.items() if name.startswith('data/workflows/artifacts/')}
    if 'artifact_text' in expected:
        check('actual artifact content', next((row['text'] for row in artifact_files.values()), None), expected['artifact_text'])
    if expected.get('artifact_absent'):
        check('no artifact bytes', len(artifact_files), 0)
    if 'artifact_verified' in expected:
        check('artifact truthful verification', all((row['verified'] for row in detail.get('artifacts', []))) if detail.get('artifacts') else False, expected['artifact_verified'])
    for name, text in expected.get('file_text', {}).items():
        check('actual file: ' + name, files.get(name, {}).get('text'), text)
    for name in expected.get('absent_files', []):
        check('file absent: ' + name, name in files, False)
    if 'effect_count' in expected:
        check('actual isolated effect count', files.get('effect.txt', {}).get('text', '').count('exactly one isolated effect'), expected['effect_count'])
    if expected.get('all_success_controls'):
        check('original reopen/readback', all((c.get('ok') is True for c in controls)), True)
    if expected.get('active_cancel'):
        check('active cancel stays visible until actual return', any((c.get('operation') == 'cancel' and c.get('after_status') in {'running', 'verifying'} for c in controls)), True)
    if expected.get('dependencies_verified'):
        by_id = {s['step_id']: s for s in steps}
        check('dependency receipt verification', all((by_id[d]['status'] == 'verified' for s in steps if s['attempts'] for d in s['dependencies'])), True)
    if 'max_active_upper' in expected or 'max_active_lower' in expected:
        from datetime import datetime
        intervals = [(datetime.fromisoformat(i['started_at'].replace('Z', '+00:00')).timestamp(), datetime.fromisoformat(i['finished_at'].replace('Z', '+00:00')).timestamp()) for i in invocations if i.get('finished_at')]
        points = [(a, 1) for a, b in intervals] + [(b, -1) for a, b in intervals]
        active, maximum = (0, 0)
        for _, delta in sorted(points, key=lambda x: (x[0], x[1])):
            active += delta
            maximum = max(maximum, active)
        if 'max_active_upper' in expected:
            check('observed simultaneous invocation upper bound', maximum <= expected['max_active_upper'], True)
        if 'max_active_lower' in expected:
            check('observed simultaneous invocation lower bound', maximum >= expected['max_active_lower'], True)
    return {'passed': all((row['passed'] for row in observations)), 'observations': observations, 'errors': [row['check'] for row in observations if not row['passed']]}

def metrics(results, oracles):
    by_id = {row['id']: row for row in oracles}
    groups = {'completion': 'completion_eligible', 'recovery': 'recovery_eligible', 'cancel': 'cancel_eligible', 'partial': 'partial_eligible'}
    summary = {'cases': len(results), 'passed': sum((row['evaluation']['passed'] for row in results)), 'harness_errors': sum((bool(row.get('harness_error')) for row in results)), 'scopes': dict(Counter((row['execution_scope'] for row in results))), 'status_counts': dict(Counter((row.get('workflow', {}).get('status', 'NO_RECEIPT') for row in results))), 'semantic_goal_plan_quality': 'NOT_MEASURED_CONTROLLED_CLIENT_CONTRACT_TESTS'}
    for label, field in groups.items():
        eligible = [row for row in results if by_id[row['id']][field]]
        summary[label] = {'eligible': len(eligible), 'whole_case_pass': sum((row['evaluation']['passed'] for row in eligible)), 'status_pass': sum((row.get('workflow', {}).get('status') == by_id[row['id']]['status'] for row in eligible))}
    times = sorted((row['duration_ms'] for row in results))
    summary['duration_ms'] = {'n': len(times), 'p50': statistics.median(times) if times else None, 'p95': times[max(0, int(0.95 * len(times) + 0.999999) - 1)] if times else None, 'scope': 'whole isolated case including setup/cleanup and controlled faults'}
    workflow_times = sorted((row['workflow_observed_duration_ms'] for row in results if 'workflow_observed_duration_ms' in row))
    summary['workflow_observed_duration_ms'] = {'n': len(workflow_times), 'p50': statistics.median(workflow_times) if workflow_times else None, 'p95': workflow_times[max(0, int(0.95 * len(workflow_times) + 0.999999) - 1)] if workflow_times else None, 'scope': 'original scheduler submit through observed stopping outcome; excludes setup and cleanup', 'nonzero_clock_offsets': sum((bool(row.get('clock_offset')) for row in results))}
    effects = [entry for row in results for entry in row.get('effect_ledger', [])]
    summary['write_effects'] = {'entries': len(effects), 'actual_effects': sum((e['actual_effect'] for e in effects)), 'unauthorized_entries': sum((not e['authorized'] for e in effects)), 'unauthorized_effects': sum((e['actual_effect'] and (not e['authorized']) for e in effects))}
    for label, field in groups.items():
        subset_times = sorted((row['workflow_observed_duration_ms'] for row in results if by_id[row['id']][field] and 'workflow_observed_duration_ms' in row))
        summary[label]['workflow_observed_duration_ms'] = {'n': len(subset_times), 'p50': statistics.median(subset_times) if subset_times else None, 'p95': subset_times[max(0, int(0.95 * len(subset_times) + 0.999999) - 1)] if subset_times else None}
    from hanni.workflows.types import TRANSITIONS
    actual_edges = {}
    checkpoint_cases, checkpoint_pass = (0, 0)
    for row in results:
        if row['execution_scope'] != 'native_original_scheduler':
            continue
        previous = None
        checkpoints = row.get('workflow', {}).get('checkpoints', [])
        sequence_ok = all((a['sequence'] < b['sequence'] for a, b in zip(checkpoints, checkpoints[1:])))
        checkpoint_cases += 1
        checkpoint_pass += sequence_ok and bool(checkpoints)
        for checkpoint in checkpoints:
            current = checkpoint.get('status')
            if previous and current != previous:
                actual_edges.setdefault((previous, current), []).append(row['id'])
            previous = current
    summary['native_transition_coverage'] = [{'source': source, 'target': target, 'cases': sorted(set(actual_edges.get((source, target), []))), 'scope': 'observed_original_scheduler_checkpoint_edge' if (source, target) in actual_edges else 'UNREACHED_NATIVE', 'fault_boundary_coverage': 'NOT_INFERRED_FROM_REACHABILITY'} for source, targets in sorted(TRANSITIONS.items()) for target in sorted(targets)]
    summary['checkpoint_sequence_correctness'] = {'eligible_original_scheduler_cases': checkpoint_cases, 'strict_sequence_pass': checkpoint_pass, 'scope': 'persisted sequence monotonicity, not full restart proof'}
    summary['by_category'] = {category: {'cases': sum((row['category'] == category for row in results)), 'passed': sum((row['category'] == category and row['evaluation']['passed'] for row in results))} for category in sorted({row['category'] for row in results})}
    return summary

def run(corpus_path, output, subset=None):
    corpus_path, output = (Path(corpus_path), Path(output))
    output.mkdir(parents=True, exist_ok=False)
    cases = json.loads(corpus_path.read_text(encoding='utf-8'))
    if subset:
        cases = [row for row in cases if row['id'] in subset]
    inputs = [{key: deepcopy(value) for key, value in row.items() if key != 'expected'} for row in cases]
    oracles = [{'id': row['id'], **deepcopy(row['expected'])} for row in cases]
    (output / 'inputs.json').write_text(json.dumps(inputs, indent=2), encoding='utf-8')
    (output / 'oracles.json').write_text(json.dumps(oracles, indent=2), encoding='utf-8')
    source_before = production_manifest()
    (output / 'source-before.json').write_text(json.dumps(source_before, indent=2), encoding='utf-8')
    results = []
    with (output / 'receipts.jsonl').open('x', encoding='utf-8', newline='\n') as stream:
        for case, oracle in zip(inputs, oracles):
            receipt = run_case(case, output / 'fixtures' / case['id'])
            receipt['evaluation'] = evaluate(receipt, oracle)
            stream.write(json.dumps(receipt, ensure_ascii=False) + '\n')
            stream.flush()
            results.append(receipt)
            print(json.dumps({'id': case['id'], 'status': receipt.get('workflow', {}).get('status'), 'pass': receipt['evaluation']['passed'], 'errors': receipt['evaluation']['errors']}), flush=True)
    summary = metrics(results, oracles)
    summary['corpus_sha256'] = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    summary['transitions'] = transition_atomicity(output / 'transition-fixtures')
    source_after = production_manifest()
    (output / 'source-after.json').write_text(json.dumps(source_after, indent=2), encoding='utf-8')
    summary['source_uniform'] = source_before == source_after
    (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive')
    parser.add_argument('--corpus', default='evals/workflows/campaign4_development.json')
    parser.add_argument('--output')
    parser.add_argument('--ids', nargs='*')
    args = parser.parse_args()
    if args.archive:
        print(json.dumps({'archived_files': len(archive(args.archive))}))
    else:
        print(json.dumps(run(args.corpus, args.output, args.ids), indent=2))
