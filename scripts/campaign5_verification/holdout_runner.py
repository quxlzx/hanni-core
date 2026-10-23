"""Once-only inputs-only execution of sealed synthetic tasks through original APIs.

This executor hashes oracle bytes for seal integrity but never parses them,
imports author/scoring code, or supplies an answer verifier to inference.
The manager must authorize the whole run after its exact source freeze.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
PRIVATE = ROOT / 'data/campaign5-verifier'
HOLDOUT = PRIVATE / 'holdout'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=str) + '\n', encoding='utf8', newline='\n')

def validate_seal():
    seal = json.loads((HOLDOUT / 'seal.json').read_text(encoding='utf8'))
    entries = seal.get('hashes', seal.get('files', seal.get('sha256', {})))
    checked = {}
    for name in ('author.py', 'inputs.jsonl', 'oracles.jsonl', 'protocol.json', 'query-hashes.json'):
        stem = name.rsplit('.', 1)[0].replace('-', '_')
        expected = entries.get(name) if isinstance(entries, dict) else None
        if isinstance(expected, dict):
            expected = expected.get('sha256')
        expected = expected or seal.get(stem + '_sha256')
        if expected is None:
            raise RuntimeError('Required private seal hash is absent: ' + name)
        observed = digest(HOLDOUT / name)
        if observed != expected:
            raise RuntimeError('Private seal integrity failed: ' + name)
        checked[name] = observed
    return {'seal_sha256': digest(HOLDOUT / 'seal.json'), 'files': checked}

def assert_freeze(freeze, *, verify_archive=False):
    from scripts.campaign5_manager.freeze import paths
    manifest = json.loads((freeze / 'MANIFEST.json').read_text(encoding='utf8'))
    summary = json.loads((freeze / 'SUMMARY.json').read_text(encoding='utf8'))
    if digest(freeze / 'MANIFEST.json') != summary['manifest_sha256']:
        raise RuntimeError('Frozen manifest identity changed.')
    current_names = {p.relative_to(ROOT).as_posix() for p in paths()}
    if current_names != set(manifest):
        raise RuntimeError('Frozen source membership changed.')
    for name, expected in manifest.items():
        if (ROOT / name).is_symlink() or digest(ROOT / name) != expected:
            raise RuntimeError('Frozen source changed: ' + name)
    for name, expected in summary.get('owner_configuration_sha256', {}).items():
        if digest(ROOT / name) != expected:
            raise RuntimeError('Owner protected deployment changed.')
    if verify_archive and digest(freeze / 'source.zip') != summary['archive_sha256']:
        raise RuntimeError('Frozen archive identity changed.')
    return {'manifest_sha256': summary['manifest_sha256'], 'archive_sha256': summary['archive_sha256'], 'files': len(manifest)}

def effective_input(case, mode):
    """Frozen protocol pins baselines; adaptive retains original native policy."""
    if mode not in {'pinned', 'adaptive', 'selective'}:
        raise ValueError('Unknown prospective final mode.')
    copied = deepcopy(case)
    for key in ('expected', 'oracle', 'checker_inputs'):
        if key in copied:
            raise ValueError('Oracles cannot enter execution inputs.')
    original = copied['limits']
    allowed = {'max_tokens', 'temperature', 'top_p', 'max_fallbacks', 'timeout_seconds'}
    if set(original) - allowed or original.get('max_fallbacks') != 0 or original.get('timeout_seconds') != 120:
        raise ValueError('Frozen prospective generation metadata mismatch.')
    copied['limits'] = {k: original[k] for k in ('max_tokens', 'temperature', 'top_p')}
    return (copied, {'sealed_limits': original, 'effective_generation_kwargs': copied['limits'], 'pinned_max_fallbacks': 0 if mode == 'pinned' else None, 'adaptive_fallback_scope': 'Original native configured budget; sealed zero bound applies to pinned baseline only.', 'requested_timeout_seconds': 120, 'timeout_scope': 'Requested metadata ceiling; original client/transport timeout remains authoritative. No unsupported generation kwarg or forced owner-process interruption.'})

def clone_database(profile, target):
    """SQLite original backup preserves every DEV policy/proof/comparison table."""
    target.parent.mkdir(parents=True, exist_ok=False)
    with sqlite3.connect(profile.as_uri() + '?mode=ro&immutable=1', uri=True) as source:
        with sqlite3.connect(target) as destination:
            source.backup(destination)

def validate_profile(profile):
    profile = profile.resolve()
    roots = ((ROOT / 'data/campaign5-manager').resolve(), (ROOT / 'data/campaign5-development').resolve())
    if not any((profile.is_relative_to(p) for p in roots)) or not profile.is_file() or profile.is_symlink():
        raise ValueError('Only a frozen campaign-owned development checkpoint is allowed.')
    for suffix in ('-wal', '-journal'):
        leaf = Path(str(profile) + suffix)
        if leaf.exists() and leaf.stat().st_size:
            raise ValueError('Frozen DEV checkpoint must be closed and checkpointed.')
    with sqlite3.connect(profile.as_uri() + '?mode=ro&immutable=1', uri=True) as source:
        if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Invalid immutable DEV checkpoint.')
        tables = {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'proofs', 'measurements', 'settings', 'decisions', 'identity_sources'} <= tables:
            raise ValueError('Checkpoint does not contain original adaptive state.')
    return (profile, digest(profile))

def execute(output, *, freeze, profile, endpoints, authorization):
    from hanni.compute import ComputeRegistry, ComputeScheduler
    from hanni.config import load_config
    from hanni.models.adaptive import AdaptiveModelEngine
    from scripts.campaign5_benchmark.live import copy_deployment, fresh_residents
    from scripts.campaign5_benchmark.runner import run_case
    output = output.resolve()
    freeze = freeze.resolve()
    if not authorization.strip():
        raise ValueError('Record explicit manager whole-final authorization.')
    if output.exists() or not output.is_relative_to(PRIVATE.resolve()):
        raise ValueError('Choose a fresh owned verifier output directory.')
    proof = assert_freeze(freeze, verify_archive=True)
    seal = validate_seal()
    profile, profile_sha = validate_profile(profile)
    cases = [json.loads(line) for line in (HOLDOUT / 'inputs.jsonl').read_text(encoding='utf8').splitlines()]
    if len(cases) != 100 or len({c['id'] for c in cases}) != 100:
        raise RuntimeError('Whole 100-case sealed corpus is required; subsets are forbidden.')
    if not endpoints or len(endpoints) != len(set(endpoints)):
        raise ValueError('A distinct original configured endpoint baseline list is required.')
    with (HOLDOUT / 'FINAL_GLOBAL_CLAIM.json').open('x', encoding='utf8', newline='\n') as claim:
        json.dump({'created_at': datetime.now(timezone.utc).isoformat(), 'output': str(output), 'manager_authorization': authorization, 'proof': proof, 'seal': seal, 'profile_sha256': profile_sha, 'cases': 100, 'no_retry': True}, claim, indent=2)
        claim.write('\n')
    output.mkdir(parents=True)
    save(output / 'RUN_METADATA.json', {'authorization': authorization, 'proof': proof, 'seal': seal, 'profile_sha256': profile_sha, 'original_endpoints': endpoints, 'case_count': 100, 'order': 'Alternating stable baseline order; adaptive then selective per case.', 'profile_scope': 'Fresh immutable DEV database clone per case AND mode; final telemetry discarded between arms.', 'quality_feedback_to_policy': False, 'private_pycache_prefix': sys.pycache_prefix, 'semantic_oracles_loaded': False, 'tool_execution': False, 'memory_scope': 'Supplied synthetic source records, no production retrieval.'})
    rows = []
    started = time.perf_counter()
    with ExitStack() as stack:
        state = output / 'native-observer-state'
        owner_hashes = copy_deployment(ROOT / 'data/compute', state)
        config = load_config(ROOT / 'config', data_dir=state, env={})
        registry = ComputeRegistry(state)
        stack.callback(registry.close)
        compute = ComputeScheduler(registry)
        stack.callback(compute.close)
        observer = AdaptiveModelEngine(config, compute_scheduler=compute, data_dir=state)
        stack.callback(observer.close)
        available = {r['endpoint_id'] for r in observer._inventory()}
        if set(endpoints) - available:
            raise RuntimeError('Pinned endpoint is not in original configured inventory.')
        save(output / 'NATIVE_INITIAL_DISCOVERY.json', observer.refresh())
        save(output / 'OWNER_COPY_HASHES.json', owner_hashes)
        stream = stack.enter_context((output / 'receipts.jsonl').open('x', encoding='utf8', newline='\n'))
        for index, case in enumerate(cases):
            assert_freeze(freeze)
            validate_seal()
            if digest(profile) != profile_sha:
                raise RuntimeError('Frozen DEV checkpoint changed; remaining tasks NOT_TESTED.')
            baseline_order = sorted(endpoints, reverse=bool(index % 2))
            arms = [('pinned', endpoint) for endpoint in baseline_order] + [('adaptive', None), ('selective', None)]
            for arm_index, (mode, endpoint) in enumerate(arms):
                assert_freeze(freeze)
                if digest(profile) != profile_sha:
                    raise RuntimeError('Frozen DEV checkpoint changed before mode.')
                fresh_residents(observer)
                child_root = output / 'case-states' / f'{index:03d}-{arm_index:02d}'
                clone_database(profile, child_root / 'model-routing/profiles.sqlite3')
                child_config = replace(config, paths=replace(config.paths, data_dir=child_root))
                child = AdaptiveModelEngine(child_config, compute_scheduler=compute, data_dir=child_root)
                child.observations = deepcopy(observer.observations)
                child._file_hash_cache = deepcopy(observer._file_hash_cache)
                execution_input, settings = effective_input(case, mode)
                try:
                    before_policy = child._settings()
                    row = run_case(execution_input, child, mode=mode, endpoint_id=endpoint)
                    row['native_policy_before_final_answer'] = before_policy
                    row['original_timeout_seconds'] = {s.id: s.request_timeout_seconds for s in child_config.models.models}
                    row['case_profile_source_sha256'] = profile_sha
                    row['frozen_input_sha256'] = hashlib.sha256(json.dumps(case, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
                    row['mode_settings_receipt'] = settings
                    row['oracle_used_during_execution'] = False
                finally:
                    child.close()
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, default=str) + '\n')
                stream.flush()
                rows.append(row)
                save(output / 'PROGRESS.json', {'completed_arms': len(rows), 'completed_cases': index + int(arm_index == len(arms) - 1), 'actual_generation_http': sum((r['real_generation_dispatches'] for r in rows)), 'elapsed_seconds': time.perf_counter() - started, 'classification_counts': {name: sum((r['classification'] == name for r in rows)) for name in sorted({r['classification'] for r in rows})}})
        save(output / 'NATIVE_FINAL_OBSERVER.json', observer.snapshot())
    end_proof = assert_freeze(freeze)
    save(output / 'CLOSED.json', {'completed_arms': len(rows), 'planned_arms': 100 * (len(endpoints) + 2), 'cases': 100, 'elapsed_seconds': time.perf_counter() - started, 'actual_generation_http': sum((r['real_generation_dispatches'] for r in rows)), 'receipt_sha256': digest(output / 'receipts.jsonl'), 'source_proof': end_proof, 'profile_unchanged': digest(profile) == profile_sha, 'seal_unchanged': validate_seal() == seal, 'oracle_data_parsed': False, 'owned_engines_transports_stores_closed': True, 'owner_services_started_stopped': 0, 'status': 'COMPLETE_ONCE'})
    return output / 'CLOSED.json'
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--endpoint-id', action='append', required=True)
    parser.add_argument('--authorization', required=True)
    args = parser.parse_args()
    try:
        print(execute(args.output, freeze=args.freeze, profile=args.profile, endpoints=args.endpoint_id, authorization=args.authorization))
    except Exception as exc:
        output = args.output.resolve()
        if output.is_relative_to(PRIVATE.resolve()) and output.exists():
            receipts = output / 'receipts.jsonl'
            rows = [json.loads(line) for line in receipts.read_text(encoding='utf8').splitlines()] if receipts.exists() else []
            save(output / 'ABORTED.json', {'status': 'ABORTED_NO_RETRY', 'error_type': type(exc).__name__, 'completed_arms': len(rows), 'remaining_NOT_TESTED': 100 * (len(args.endpoint_id) + 2) - len(rows), 'receipt_sha256': digest(receipts) if receipts.exists() else None, 'original_exception_retained_in_private_process_log': True, 'scope': 'Original guards/source integrity remain effective; no final retry.'})
        raise
