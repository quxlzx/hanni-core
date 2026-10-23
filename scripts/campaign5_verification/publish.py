"""Independent post-run scoring and aggregate publication, never execution input.

Private reference answers remain in ignored storage. Public output includes only
counts, measured costs, failure categories and exact evidence hashes.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from scripts.campaign5_verification.scoring import score, summary
ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / 'data/campaign5-verifier'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=str) + '\n', encoding='utf8', newline='\n')

def wire_objects(raw):
    try:
        parsed = json.loads(raw)
        return [parsed] if isinstance(parsed, dict) else []
    except (ValueError, TypeError):
        result = []
        for line in raw.splitlines():
            if not line.startswith('data:'):
                continue
            value = line[5:].strip()
            if value == '[DONE]':
                continue
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    result.append(parsed)
            except ValueError:
                continue
        return result

def original_response(row):
    """Recover accessible rejected wire output without making it an accepted result.

Identity-withdrawn, cancelled or multi-participant rejected outputs are not
attributed to an intended model answer. All raw original bytes stay private.
"""
    if row.get('actual_response') is not None:
        return (row['actual_response'], 'original_returned_response')
    if row.get('collaboration') or 'CANCELLED' in row.get('classification', ''):
        return (None, 'no_original_selected_output')
    if any((f.get('trigger') == 'model_identity_mismatch' for d in row.get('native_decisions', []) for f in d.get('fallbacks', []))):
        return (None, 'identity_mismatch_not_configured_model_quality')
    wires = [w for w in row.get('raw_http', []) if w.get('path') in {'/v1/chat/completions', '/chat/completions'} and (not w.get('raw_truncated'))]
    if len(wires) != 1:
        return (None, 'missing_or_multiple_unselected_original_responses')
    wire = wires[0]
    if wire.get('status') != 200:
        return (None, 'non_success_http_no_model_answer')
    objects = wire_objects(wire.get('raw_response', ''))
    try:
        requested_model = json.loads(wire['request_body']).get('model')
    except (ValueError, TypeError, KeyError):
        return (None, 'request_identity_unavailable')
    if any((p.get('model') is not None and p['model'] != requested_model for p in objects)):
        return (None, 'identity_mismatch_not_configured_model_quality')
    content = []
    calls = {}
    full_message = None
    finished = False
    for packet in objects:
        for choice in packet.get('choices', []):
            if choice.get('index', 0) != 0:
                continue
            if isinstance(choice.get('message'), dict):
                full_message = choice['message']
            if choice.get('finish_reason') is not None:
                finished = True
            delta = choice.get('delta') or {}
            if isinstance(delta.get('content'), str):
                content.append(delta['content'])
            for call in delta.get('tool_calls') or []:
                index = call.get('index', 0)
                target = calls.setdefault(index, {'id': '', 'function': {'name': '', 'arguments': ''}})
                if call.get('id'):
                    target['id'] = call['id']
                function = call.get('function') or {}
                for field in ('name', 'arguments'):
                    if isinstance(function.get(field), str):
                        target['function'][field] += function[field]
    if full_message is not None:
        return (full_message, 'original_raw_nonstream_rejected_by_controller')
    if finished and (content or calls):
        return ({'content': ''.join(content), 'tool_calls': [calls[i] for i in sorted(calls)]}, 'original_raw_completed_sse_rejected_by_controller')
    return (None, 'incomplete_or_unavailable_raw_model_answer')

def sample(values):
    values = sorted((v for v in values if type(v) in (int, float) and math.isfinite(v) and (v >= 0)))
    return {'n': len(values), 'mean': sum(values) / len(values) if values else None, 'p50': values[math.ceil(len(values) * 0.5) - 1] if values else None, 'p95': values[math.ceil(len(values) * 0.95) - 1] if values else None}

def cost_summary(rows):
    wires = [w for r in rows for w in r.get('raw_http', []) if w.get('path') in {'/v1/chat/completions', '/chat/completions', '/v1/messages'}]
    usages = []
    for wire in wires:
        usage = None
        for packet in wire_objects(wire.get('raw_response', '')):
            candidate = packet.get('usage')
            if isinstance(candidate, dict):
                usage = candidate
        usages.append(usage)
    tokens = {}
    for field in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
        values = [u.get(field) if isinstance(u, dict) else None for u in usages]
        known = [v for v in values if type(v) is int and v >= 0]
        tokens[field] = {'http_requests': len(usages), 'reported': len(known), 'total': sum(known) if known else None, 'complete_reporting': bool(values) and len(known) == len(values)}
    participants = []
    for row in rows:
        if row.get('collaboration'):
            participants.extend(row['collaboration'].get('participants', []))
        elif row.get('telemetry'):
            participants.append(row['telemetry'])
    return {'http_requests': len(wires), 'reported_tokens': tokens, 'request_ms': sample([r.get('total_request_ms') for r in rows if r.get('real_generation_dispatches')]), 'http_latency_ms': sample([w.get('latency_ms') for w in wires]), 'native_text_ttft_ms': sample([p.get('ttft_ms') for p in participants]), 'native_generation_tokens_per_second': sample([p.get('generation_tps') for p in participants]), 'orchestration_outside_wire_span_ms': sample([r.get('orchestration_outside_wire_span_ms') for r in rows]), 'peak_incremental_ram_vram': None, 'scope': 'Actual reported server usage and original telemetry; request latency includes orchestration. Admission headroom is not measured peak resource cost. Missing usage is null.'}

def arm_label(row):
    return 'pinned:' + row['requested_endpoint_id'] if row['mode'] == 'pinned' else row['mode']

def comparisons(grades):
    by_arm = defaultdict(dict)
    for row in grades:
        by_arm[row['arm']][row['id']] = row
    result = {}
    for baseline, base in by_arm.items():
        if not baseline.startswith('pinned:'):
            continue
        for mode in ('adaptive', 'selective'):
            other = by_arm.get(mode, {})
            common = sorted(set(base) & set(other))
            measured = [k for k in common if base[k]['correct'] is not None and other[k]['correct'] is not None]
            wins = sum((base[k]['correct'] is False and other[k]['correct'] is True for k in measured))
            losses = sum((base[k]['correct'] is True and other[k]['correct'] is False for k in measured))
            result[baseline + ' versus ' + mode] = {'paired_planned_or_attempted': len(common), 'paired_observable_actual_responses': len(measured), 'mode_wins': wins, 'mode_losses': losses, 'ties': len(measured) - wins - losses, 'net_correctness_gain': wins - losses if measured else None, 'improvement_established': False, 'population_confidence_interval': None, 'interpretation': 'Purposive task pairs and shared runtimes/caches; cannot claim overall reliability or stronger-baseline benefit from missing models. Independent claim requires applicable frozen DEV-selected stronger baseline and measured costs.'}
    return result

def publish(run):
    run = run.resolve()
    if not run.is_relative_to(PRIVATE.resolve()):
        raise ValueError('Only campaign-owned independent final receipts are eligible.')
    closed = json.loads((run / 'CLOSED.json').read_text(encoding='utf8'))
    if closed.get('status') != 'COMPLETE_ONCE' or digest(run / 'receipts.jsonl') != closed['receipt_sha256']:
        raise ValueError('Whole once-only immutable collection must be closed before scoring.')
    from scripts.campaign5_verification.holdout_runner import validate_seal
    seal = validate_seal()
    cases = {c['id']: c for c in map(json.loads, (PRIVATE / 'holdout/inputs.jsonl').read_text(encoding='utf8').splitlines())}
    oracles = {c['id']: c for c in map(json.loads, (PRIVATE / 'holdout/oracles.jsonl').read_text(encoding='utf8').splitlines())}
    receipts = list(map(json.loads, (run / 'receipts.jsonl').read_text(encoding='utf8').splitlines()))
    if len(receipts) != closed['planned_arms'] or len({(r['id'], arm_label(r)) for r in receipts}) != len(receipts):
        raise ValueError('Missing, repeated or unexpected final receipt.')
    grades = []
    for receipt in receipts:
        case = cases[receipt['id']]
        response, response_scope = original_response(receipt)
        outcome = 'returned' if receipt['classification'] == 'RETURNED' else receipt['classification'].casefold()
        verdict = score(case, oracles[case['id']], response, actual_model_http_requests=receipt['real_generation_dispatches'], outcome=outcome)
        verdict.update(arm=arm_label(receipt), response_scope=response_scope, receipt_sha256=hashlib.sha256(json.dumps(receipt, sort_keys=True, ensure_ascii=False, allow_nan=False, default=str).encode()).hexdigest())
        grades.append(verdict)
    save(run / 'GRADES.json', grades)
    by_arm = {}
    for arm in sorted({g['arm'] for g in grades}):
        rows = [g for g in grades if g['arm'] == arm]
        raw = [r for r in receipts if arm_label(r) == arm]
        by_arm[arm] = summary(rows) | {'by_category': {category: summary([g for g in rows if g['category'] == category]) for category in sorted({g['category'] for g in rows})}, 'costs': cost_summary(raw), 'response_scopes': dict(Counter((g['response_scope'] for g in rows)))}
    aggregate = {'seal_sha256': seal['seal_sha256'], 'cases': 100, 'receipt_sha256': closed['receipt_sha256'], 'grades_sha256': digest(run / 'GRADES.json'), 'source_proof': closed['source_proof'], 'arms': by_arm, 'paired': comparisons(grades), 'acceptance': {'real_independent_model_quality': any((g['correct'] is not None for g in grades)), 'adaptive_superiority_established': False, 'selective_collaboration_superiority_established': False, 'configured_baseline_change_authorized_by_evidence': False, 'overall': 'PARTIAL_OR_BLOCKED; preserve baseline unless independently reviewed applicable paired real-response benefit is established'}, 'no_final_oracle_feedback_to_model_policy': True, 'coding': 'Canonical AST references, no model-authored execution; unannotated equivalent patches may be missed.', 'memory': 'Supplied synthetic evidence only, no production retrieval validation.', 'native_tools': 'Original schemas/native proposals only; no action execution.'}
    save(run / 'SUMMARY.json', aggregate)
    save(ROOT / 'docs/campaign5/FINAL_HOLDOUT.json', aggregate)
    return aggregate
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.run), indent=2))
