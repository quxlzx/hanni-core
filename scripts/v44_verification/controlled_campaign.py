"""V4.4 predefined, isolated fixture campaign. No live inference or proof upgrades.

The request classes, conditions, independent eligibility oracle, and recovery
objective are written before execution. Scripted inference isolates original
router/queue/collaboration behavior; it cannot measure model intelligence.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from hanni.compute import ComputeError, ComputeRegistry, ComputeScheduler
from hanni.models.adaptive import ModelRequest, ModelSelectionError
from hanni.models.client import ModelUnavailableError
from hanni.models.collaboration import CollaborationEngine, CollaborationLimits
from hanni.models.performance import percentile
from tests.unit.test_adaptive_model_routing import engine as engine_fixture, prove

SEED = 4409  # No randomized outputs or benchmark-answer adaptation.
CLASSES = [
    {'id': 'simple', 'task_category': 'conversation', 'complexity': 'simple'},
    {'id': 'complex', 'task_category': 'analysis', 'complexity': 'complex'},
    {'id': 'tool', 'task_category': 'tool_selection', 'capabilities': ['tool_calling']},
    {'id': 'multi_step', 'task_category': 'planning', 'complexity': 'complex'},
    {'id': 'long_context', 'task_category': 'long_context', 'context_tokens': 9000},
    {'id': 'memory', 'task_category': 'memory'},
    {'id': 'ambiguous', 'task_category': 'conversation'},
    {'id': 'specialized_vision', 'task_category': 'analysis', 'capabilities': ['vision']},
    {'id': 'no_tools', 'task_category': 'conversation', 'complexity': 'simple'},
]
PRIVACY = ['synthetic', 'project', 'conversation', 'memory', 'screen', 'sensitive']
COLLAB = [
    ('correct_agreement', '{"value":42}', '{"value":42}', 'VERIFIED', False),
    ('incorrect_agreement', '{"value":41}', '{"value":41}', 'FAILED', False),
    ('disagreement', '{"value":41}', '{"value":42}', 'VERIFIED', False),
    ('incomplete', '{"missing":true}', '{"value":42}', 'VERIFIED', False),
    ('conflicting_interpretations', '{"value":42}', '{"value":43}', 'VERIFIED', False),
    ('missing_evidence', '{"value":42}', '{"value":42}', 'UNVERIFIED', False),
    ('secondary_failure', '{"value":41}', '{"value":42}', 'FAILED', True),
]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf8')


@contextmanager
def engine_at(path):
    path.mkdir()
    fixture = engine_fixture.__wrapped__(path)
    engine = next(fixture)
    try:
        for key in ('local:supervisor', 'worker:fixture'):
            prove(engine, key, ('text', 'structured_json', 'tool_calling')
                  if key.startswith('local:') else ('text', 'structured_json'))
        yield engine
    finally:
        fixture.close()


def timing_stats(records, field='elapsed_ms'):
    values = [row[field] for row in records if row.get(field) is not None]
    return {'sample_count': len(values), 'p50_ms': percentile(values, .5),
            'p95_ms': percentile(values, .95), 'method': 'nearest_rank',
            'scope': 'scripted original Python control path, not GPU/model/network performance'}


def routing_campaign(root):
    records = []
    with engine_at(root / 'routing-state') as engine:
        for policy in ('balanced', 'fast', 'quality', 'manual'):
            engine.configure(policy=policy, manual_endpoint_id='worker:fixture' if policy == 'manual' else None)
            for category in PRIVACY:
                for local_only in (False, True):
                    for specification in CLASSES:
                        requirements = {key: value for key, value in specification.items() if key != 'id'}
                        requirements['capabilities'] = frozenset(requirements.get('capabilities', ['text']))
                        request = ModelRequest(**requirements, local_only=local_only,
                            privacy_categories=frozenset({category}), output_tokens=64)
                        # Independent declarative fixture oracle, not router internals.
                        local_ok = ('vision' not in request.capabilities
                            and request.context_tokens + 64 <= 8192)
                        remote_ok = (local_ok and category == 'synthetic' and not local_only
                            and 'tool_calling' not in request.capabilities)
                        allowed = (['worker:fixture'] if remote_ok else []) if policy == 'manual' else (
                            (['local:supervisor'] if local_ok else []) + (['worker:fixture'] if remote_ok else []))
                        began = time.perf_counter()
                        result = engine.select(request)
                        endpoint = result['endpoint']['endpoint_id'] if result['endpoint'] else None
                        valid = endpoint in allowed if allowed else endpoint is None
                        records.append({'case_id': f'{policy}:{category}:{local_only}:{specification["id"]}',
                            'class': specification['id'], 'policy': policy, 'privacy': category,
                            'local_only': local_only, 'expected_eligible': allowed, 'selected': endpoint,
                            'valid': valid, 'elapsed_ms': (time.perf_counter()-began)*1000,
                            'excluded': result['excluded']})
        return {'scope': 'controlled eligibility; no model/tool dispatch',
            'case_count': len(records), 'valid_count': sum(row['valid'] for row in records),
            'records': records, 'timing': timing_stats(records),
            'configuration': {'synthetic_runtime_identity': True, 'verified_capacity_fixture': 8192,
                'output_tokens': 64, 'remote_categories': ['synthetic'],
                'endpoint_identity_hashes': {key: engine.endpoint_identity(key)
                    for key in ('local:supervisor', 'worker:fixture')}}}


def paired_recovery_campaign(root):
    records = []
    for outage in (False, True):
        for privacy in ('synthetic', 'memory', 'sensitive'):
            pair = []
            for mode in ('fixed', 'adaptive'):
                path = root / f'paired-{outage}-{privacy}-{mode}'
                with engine_at(path) as engine:
                    def local(*args, **kwargs):
                        if outage:
                            raise ModelUnavailableError('Scripted V4.4 primary outage.')
                        return 'valid'
                    telemetry = {}
                    began = time.perf_counter()
                    error = None
                    value = None
                    with patch('hanni.models.adaptive._BoundedInferenceClient.chat', local):
                        try:
                            value = engine.execute([{'role': 'user', 'content': 'Synthetic recovery probe.'}],
                                request=ModelRequest(privacy_categories=frozenset({privacy}), output_tokens=64),
                                endpoint_id='local:supervisor' if mode == 'fixed' else None,
                                max_fallbacks=0 if mode == 'fixed' else None,
                                validator=lambda text: text == 'valid', telemetry=telemetry)
                        except ModelSelectionError as exc:
                            error = type(exc).__name__
                    row = {'case_id': f'outage={outage}:privacy={privacy}', 'mode': mode,
                        'primary_outage': outage, 'privacy': privacy, 'success': value == 'valid',
                        'elapsed_ms': (time.perf_counter()-began)*1000, 'error': error,
                        'selected': telemetry.get('endpoint_id'),
                        'remote_dispatch_count': len(engine.compute.transport.calls),
                        'decisions': engine.snapshot()['decisions']}
                    pair.append(row)
            records.extend(pair)
    modes = {}
    for mode in ('fixed', 'adaptive'):
        rows = [row for row in records if row['mode'] == mode]
        successes = sum(row['success'] for row in rows)
        modes[mode] = {'successes': successes, 'cases': len(rows),
            'confidence_interval': None,
            'confidence_interval_reason': 'Exhaustive predetermined fixture conditions, not a statistical sample.',
            'timing': timing_stats(rows)}
    unauthorized = sum(row['remote_dispatch_count'] for row in records if row['privacy'] != 'synthetic')
    objective = (modes['adaptive']['successes'] > modes['fixed']['successes'] and unauthorized == 0)
    return {'scope': 'scripted controller recovery, NOT intelligence or live throughput',
        'objective': 'Improve available authorized completion under primary outage without private forwarding.',
        'paired_conditions': 6, 'inference_attempt_conditions': len(records), 'modes': modes,
        'unauthorized_remote_dispatches': unauthorized, 'objective_passed': objective, 'records': records}


def collaboration_campaign(root):
    records = []
    for name, primary, secondary, expected, fail in COLLAB:
        with engine_at(root / ('collab-' + name)) as engine:
            engine.compute.transport.outputs = [secondary]
            engine.compute.transport.fail = fail
            collab = CollaborationEngine(engine, limits=CollaborationLimits(max_participants=2))
            def local(client, messages, **options):
                usage = options.get('usage', getattr(client, '_inference_usage', None))
                if usage is not None:
                    usage.update(prompt_tokens=20, completion_tokens=4, total_tokens=24)
                return primary
            def verify(text):
                passed = json.loads(text).get('value') == 42
                return {'status': 'VERIFIED' if passed else 'FAILED',
                    'scope': 'fixed synthetic source observation', 'checks': {'exact_source': passed}}
            began = time.perf_counter()
            with patch('hanni.models.adaptive._BoundedInferenceClient.chat', local):
                result = collab.run([{'role': 'user', 'content': 'Synthetic source value is 42.'}],
                    request=ModelRequest(task_category='analysis', complexity='complex',
                        privacy_categories=frozenset({'synthetic'}), output_tokens=64),
                    preference='parallel', verify=None if name == 'missing_evidence' else verify,
                    context_refs=[{'source_id': 'fixture', 'sha256': digest({'value': 42})}])
            proof_ok = result['final_verification']['status'] == expected
            if name in {'disagreement', 'incomplete', 'conflicting_interpretations'}:
                proof_ok = proof_ok and json.loads(result['selected_output']).get('value') == 42 and bool(result['conflicts'])
            records.append({'case_id': name, 'expected_verification': expected,
                'invariant_passed': proof_ok, 'elapsed_ms': (time.perf_counter()-began)*1000,
                'remote_dispatch_count': len(engine.compute.transport.calls),
                'model_response_accuracy': None if name == 'missing_evidence' else json.loads(result['selected_output']).get('value') == 42,
                'result': result})
    return {'scope': 'scripted response/evidence guard evaluation; no live model quality',
        'cases': len(records), 'invariants_passed': sum(row['invariant_passed'] for row in records),
        'externally_verified_outputs': sum(row['result']['final_verification']['status'] == 'VERIFIED' for row in records),
        'timing': timing_stats(records), 'records': records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = (ROOT / 'data' / 'v44-engineering').resolve()
    if not output.is_relative_to(allowed) or output.exists():
        raise SystemExit('Output must be a new directory under data/v44-engineering.')
    output.mkdir(parents=True)
    manifest = {'scope': 'isolated development fixtures; NOT final holdout, live model quality, or hardware speed',
        'seed': SEED, 'evaluation_date_utc': datetime.now(timezone.utc).isoformat(),
        'python': platform.python_version(), 'os': platform.system(), 'classes': CLASSES,
        'routing_policies': ['balanced', 'fast', 'quality', 'manual'], 'privacy': PRIVACY,
        'routing_expected_cases': 432, 'paired_recovery_expected_conditions': 6,
        'paired_recovery_objective': 'More available authorized completed fixture tasks than fixed primary when primary fails; zero private remote dispatch.',
        'paired_recovery_conditions': {'outage': [False, True], 'privacy': ['synthetic', 'memory', 'sensitive'],
            'identical_messages': True, 'same_output_budget': 64, 'fallback_budget': {'fixed': 0, 'adaptive': 2}},
        'collaboration_cases': COLLAB, 'schema_version': 1,
        'source_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [Path(__file__), ROOT/'src/hanni/models/adaptive.py',
                ROOT/'src/hanni/models/collaboration.py', ROOT/'src/hanni/compute/scheduler.py']}}
    manifest['manifest_sha256'] = digest(manifest)
    write(output/'manifest.json', manifest)  # Frozen before the first test/dispatch.
    results = {'manifest_sha256': manifest['manifest_sha256'], 'routing': routing_campaign(output),
        'paired_recovery': paired_recovery_campaign(output), 'collaboration': collaboration_campaign(output)}
    write(output/'results.json', results)
    passed = (results['routing']['valid_count'] == 432
        and results['paired_recovery']['objective_passed']
        and results['collaboration']['invariants_passed'] == 7)
    print(json.dumps({'scope': manifest['scope'], 'routing_valid': results['routing']['valid_count'],
        'routing_total': 432, 'paired_recovery': results['paired_recovery']['modes'],
        'collaboration_invariants': results['collaboration']['invariants_passed'], 'passed': passed}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
