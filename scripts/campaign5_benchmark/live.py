"""Owned collection CLI using original live model admission, never a guard bypass.

No service/model is started. Native refresh runs once per arm, with fresh actual
resident health before its 30-second lease expires. Unhealthy worker leases are
not extended. Each final case can clone an immutable DEV profile checkpoint,
while current observed health/resources retain their true original timestamps.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from hanni.compute import ComputeRegistry, ComputeScheduler
from hanni.config import load_config
from hanni.models.adaptive import AdaptiveModelEngine
from scripts.campaign5_benchmark.runner import run_case, score_receipt, summary, request_limits
REPO = Path(__file__).resolve().parents[2]

def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=str) + '\n', encoding='utf8', newline='\n')

def sources():
    files = [*(REPO / 'src/hanni').rglob('*.py'), *(REPO / 'scripts/campaign5_benchmark').glob('*.py'), *(REPO / 'config').rglob('*.yaml')]
    return {p.relative_to(REPO).as_posix(): file_hash(p) for p in sorted(files)}

def request_reservation(engine, mode, case):
    """Reserve the original maximum generation dispatches BEFORE admission."""
    _, fallback, _ = request_limits(case)
    if mode == 'pinned':
        return 1
    if mode == 'adaptive':
        configured = engine._settings()['max_fallbacks']
        if fallback is not None and fallback > configured:
            raise ValueError('Requested fallback limit exceeds original policy.')
        return (configured if fallback is None else fallback) + 1
    if mode == 'selective':
        if fallback not in (None, 0):
            raise ValueError('Collaboration participants are pinned with zero fallbacks.')
        limits = engine.collaboration.limits
        return limits.max_participants * limits.max_rounds
    raise ValueError('Unknown live benchmark mode.')

def copy_deployment(source, target):
    hashes = {}
    for name in ('deployment.json', 'context-measurements.json'):
        original = source / name
        if original.exists():
            if original.is_symlink() or original.stat().st_size > 1048576:
                raise ValueError('Unsafe deployment/context source.')
            value = original.read_bytes()
            hashes[name] = hashlib.sha256(value).hexdigest()
            destination = target / 'compute' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(value)
    return hashes

def fresh_residents(engine):
    """Use the original actual probe without refreshing/retiming bad workers."""
    for row in engine._inventory():
        if 'spec' not in row:
            continue
        previous = engine.observations.get(row['endpoint_id'], {})
        heartbeat = previous.get('last_heartbeat')
        if type(heartbeat) not in (int, float) or not 0 <= time.time() - heartbeat < 20:
            value = engine._probe_local(row)
            if value.get('runtime_identity') is None:
                value = dict(value, runtime_identity=previous.get('runtime_identity'))
            with engine.lock:
                engine.observations[row['endpoint_id']] = value
            engine._sync_identity_sources()

@contextmanager
def final_case_engine(arm_engine, root, config, profile_source):
    """Each case gets frozen quality AND timing state, preventing holdout feedback.

    Observations are exact current native probe dictionaries, not fabricated
    healthy flags/resources. Compute transport/health remains original and arm
    owned. No case evaluation survives into the next case's profile state.
    """
    directory = root / 'model-routing'
    directory.mkdir(parents=True, exist_ok=False)
    target = directory / 'profiles.sqlite3'
    with sqlite3.connect(profile_source.as_uri() + '?mode=ro', uri=True) as source:
        with sqlite3.connect(target) as destination:
            source.backup(destination)
    engine = AdaptiveModelEngine(config, compute_scheduler=arm_engine.compute, data_dir=root)
    engine.observations = deepcopy(arm_engine.observations)
    engine._file_hash_cache = deepcopy(arm_engine._file_hash_cache)
    try:
        yield engine
    finally:
        engine.close()

def collect(output, *, inputs_path, oracles_path=None, max_cases=None, endpoint_ids=None, modes=('adaptive', 'selective'), deployment_source=None, max_http_requests=20, profile_source=None):
    output = output.resolve()
    allowed = [(REPO / 'data/campaign5-development').resolve(), (REPO / 'data/campaign5-verifier').resolve()]
    if output.exists() or not any((output.is_relative_to(p) for p in allowed)):
        raise ValueError('Choose a fresh owned Campaign5 output directory.')
    input_bytes = inputs_path.read_bytes()
    data = json.loads(input_bytes)
    cases = data['cases'][:max_cases] if max_cases is not None else data['cases']
    if not cases or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Unique prospective inputs are required.')
    references = {}
    if oracles_path is not None:
        references = {o['id']: o for o in json.loads(oracles_path.read_text())['oracles']}
        if any((c['id'] not in references for c in cases)):
            raise ValueError('Case/reference IDs do not match.')
    output.mkdir(parents=True)
    before = sources()
    save(output / 'SOURCE_BEFORE.json', before)
    profile_digest = None
    if profile_source is not None:
        profile_source = profile_source.resolve()
        profile_allowed = [(REPO / 'data/campaign5-development').resolve(), (REPO / 'data/campaign5-manager').resolve()]
        if profile_source.is_symlink() or not profile_source.is_file() or (not any((profile_source.is_relative_to(p) for p in profile_allowed))):
            raise ValueError('Final profiles must be an existing immutable campaign-owned DEV checkpoint.')
        wal = Path(str(profile_source) + '-wal')
        if wal.exists() and wal.stat().st_size:
            raise ValueError('Close and checkpoint frozen DEV profiles before final use.')
        profile_digest = file_hash(profile_source)
    save(output / 'INPUT_METADATA.json', {'inputs_sha256': hashlib.sha256(input_bytes).hexdigest(), 'oracles_sha256': file_hash(oracles_path) if oracles_path else None, 'selected_case_ids': [c['id'] for c in cases], 'max_http_requests': max_http_requests, 'scope': 'ModelLab-adjacent native inference; no tool/workflow execution; no production memory retrieval'})
    deployment_source = (deployment_source or REPO / 'data/compute').resolve()
    discovery_state = output / 'inventory-state'
    copy_deployment(deployment_source, discovery_state)
    config = load_config(REPO / 'config', data_dir=discovery_state, env={})
    registry = ComputeRegistry(discovery_state)
    compute = ComputeScheduler(registry)
    inventory_engine = AdaptiveModelEngine(config, compute_scheduler=compute, data_dir=discovery_state)
    try:
        available = [r['endpoint_id'] for r in inventory_engine._inventory()]
    finally:
        inventory_engine.close()
        compute.close()
        registry.close()
    selected = available if endpoint_ids is None else list(endpoint_ids)
    if set(selected) - set(available):
        raise ValueError('Pinned endpoint must exist in the original configured inventory.')
    if set(modes) - {'adaptive', 'selective'}:
        raise ValueError('Choose native adaptive/selective modes.')
    arms = [('pinned-' + key.replace(':', '-'), 'pinned', key) for key in selected] + [(mode, mode, None) for mode in modes]
    save(output / 'ARMS.json', arms)
    global_http = 0
    all_summaries = {}
    completed = []
    shared_file_cache = {}
    for label, mode, key in arms:
        arm_root = output / 'arms' / label
        state = arm_root / 'state'
        if not arm_root.resolve().is_relative_to(output):
            raise ValueError('Unsafe configured endpoint identifier for owned arm path.')
        hashes = copy_deployment(deployment_source, state)
        config = load_config(REPO / 'config', data_dir=state, env={})
        registry = ComputeRegistry(state)
        compute = ComputeScheduler(registry)
        engine = AdaptiveModelEngine(config, compute_scheduler=compute, data_dir=state)
        engine._file_hash_cache = deepcopy(shared_file_cache)
        rows = []
        quarantine = None
        try:
            refreshed = engine.refresh()
            shared_file_cache = deepcopy(engine._file_hash_cache)
            save(arm_root / 'INITIAL_NATIVE_DISCOVERY.json', refreshed)
            save(arm_root / 'OWNER_COPY_HASHES.json', hashes)
            with (arm_root / 'receipts.jsonl').open('x', encoding='utf8', newline='\n') as stream:
                for index, case in enumerate(cases):
                    if sources() != before:
                        quarantine = 'SOURCE_CHANGED_DURING_COLLECTION'
                    if profile_source and file_hash(profile_source) != profile_digest:
                        quarantine = 'FROZEN_DEVELOPMENT_PROFILE_CHANGED'
                    reservation = request_reservation(engine, mode, case)
                    if quarantine or global_http + reservation > max_http_requests:
                        row = {'id': case['id'], 'category': case['category'], 'mode': mode, 'requested_endpoint_id': key, 'classification': 'NOT_EXECUTED_AFTER_QUARANTINE' if quarantine else 'NOT_EXECUTED_REQUEST_BUDGET', 'semantic_pass': None, 'actual_response': None, 'real_generation_dispatches': 0, 'total_request_ms': None, 'reason': quarantine or 'Prospective generation request budget exhausted.'}
                    else:
                        fresh_residents(engine)
                        if profile_source is not None:
                            child_root = arm_root / 'case-states' / f'{index:04d}'
                            child_config = replace(config, paths=replace(config.paths, data_dir=child_root))
                            with final_case_engine(engine, child_root, child_config, profile_source.resolve()) as child:
                                row = run_case(case, child, mode=mode, endpoint_id=key)
                        else:
                            row = run_case(case, engine, mode=mode, endpoint_id=key)
                        global_http += row['real_generation_dispatches']
                        row['reserved_generation_request_budget'] = reservation
                        if row['real_generation_dispatches'] > reservation:
                            quarantine = 'Original execution exceeded its prospectively reserved generation request budget.'
                        if row['classification'] in {'UNOBSERVED_INFERENCE', 'HARNESS_OR_ADMISSION_ERROR_NO_INFERENCE'} or any((h['raw_truncated'] for h in row['raw_http'])):
                            quarantine = 'Unexpected execution error or lost original wire provenance.'
                        if case['id'] in references:
                            verdict = score_receipt(row, references[case['id']])
                            row['semantic_pass'] = verdict['semantic_pass']
                            row['offline_grading'] = verdict
                    rows.append(row)
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, default=str) + '\n')
                    stream.flush()
            all_summaries[label] = summary(rows) | {'quarantine': quarantine, 'original_state_scope': 'fresh frozen profile clone per case' if profile_source else 'isolated development arm only'}
            save(arm_root / 'SUMMARY.json', all_summaries[label])
            save(arm_root / 'FINAL_NATIVE_STATE.json', engine.snapshot())
            completed.append(label)
        finally:
            engine.close()
            compute.close()
            registry.close()
    after = sources()
    save(output / 'SOURCE_AFTER.json', after)
    result = {'arms': all_summaries, 'completed_arm_ids': completed, 'actual_generation_requests': global_http, 'source_unchanged': before == after, 'owner_services_started_or_stopped': 0, 'native_freshness_scope': 'original health once per arm; actual resident probe before lease expiry; unavailable worker timestamps never extended', 'final_profile_source_sha256': profile_digest, 'final_profile_source_unchanged': file_hash(profile_source) == profile_digest if profile_source else None}
    save(output / 'SUMMARY.json', result)
    print(json.dumps(result, indent=2))
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, default=Path('evals/models/campaign5_development.json'))
    parser.add_argument('--oracles', type=Path, default=Path('evals/models/campaign5_development_oracles.json'))
    parser.add_argument('--ungraded', action='store_true')
    parser.add_argument('--max-cases', type=int)
    parser.add_argument('--endpoint-id', action='append')
    parser.add_argument('--mode', action='append', choices=('adaptive', 'selective'))
    parser.add_argument('--deployment-source', type=Path)
    parser.add_argument('--max-http-requests', type=int, default=20)
    parser.add_argument('--frozen-profile-source', type=Path)
    args = parser.parse_args()
    if args.max_cases is not None and args.max_cases < 1 or args.max_http_requests < 1:
        parser.error('Positive case/request bounds are required.')
    collect(args.output, inputs_path=args.inputs.resolve(), oracles_path=None if args.ungraded else args.oracles.resolve(), max_cases=args.max_cases, endpoint_ids=args.endpoint_id, modes=tuple(args.mode or ('adaptive', 'selective')), deployment_source=args.deployment_source, max_http_requests=args.max_http_requests, profile_source=args.frozen_profile_source)
if __name__ == '__main__':
    main()
