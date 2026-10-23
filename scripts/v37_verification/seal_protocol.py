"""Prospectively seal V3.7 independent expectations before worker outputs."""
from pathlib import Path
import hashlib
import json
import random

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/v37-verification/sealed'

CHECKS = [
    ('node_identity', 'Independent strict-key read-only discovery proves actual OS, memory, GPUs and software; unreachable nodes remain blocked.'),
    ('gpu_assignment', 'Independent process/device measurements prove one actual model server per named GPU; configuration is insufficient.'),
    ('model_identity', 'Existing GGUF metadata and loaded server identity agree; no model substitution or download.'),
    ('context_capacity', 'Configured context is separate from maximum empirically verified near-limit successful retrieval; untested limits are null.'),
    ('strata_protocol', 'Existing Strata launcher is inspected unchanged; actual protocol, health and inference are measured only if reachable.'),
    ('strict_ssh', 'Every connection keeps strict host verification, bounded timeouts and existing authenticated identity.'),
    ('no_public_listener', 'Owned serving/forwarding binds loopback or authorized private addresses; independently managed processes are preserved.'),
    ('central_authority', 'Original WorkflowService and owner lease remain authoritative; remote output cannot execute tools or grant permissions.'),
    ('context_placement', 'Requests exceeding verified context or unknown limits cannot be silently placed on an unverified remote worker.'),
    ('health_placement', 'Disabled, unhealthy, stale, or capability-incompatible resources receive no new jobs.'),
    ('capacity_backpressure', 'Worker reservations, concurrency and bounded queues are enforced under simultaneous requests and released after outcomes.'),
    ('privacy_boundary', 'Remote context transmission defaults denied and enforces allowed nodes/categories, project memory and screen restrictions before HTTP.'),
    ('output_validation', 'HTTP 200, empty/malformed output or wrong retrieval answers do not alone constitute verified workflow completion.'),
    ('parallel_execution', 'Independent supported model steps overlap and retain exact workflow/step/job/output associations.'),
    ('recovery', 'Connection loss records uncertainty and history; restart recovers durable state without silently replaying external side effects.'),
    ('cancellation', 'Cancellation withdraws future dispatch and rejects late results, while uncertain still-running remote work is reported honestly.'),
    ('fallback', 'Fallback stays within privacy, context, capability, retry and resource-budget bounds.'),
    ('benchmark_integrity', 'Sequential and concurrent timings use actual endpoints; all requests, failures and unknown measurements are preserved.'),
    ('native_views', 'Actual native Cluster/Models/Workflows at large, small and compact sizes show real/null telemetry, usable safe controls and no JS errors.'),
    ('ui_scores', 'Independent visible pixels score strictly greater than 8.5/10 and template appearance at most 2/10; no visual tooling means blocked.'),
]

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(370091)
    context_cases = []
    for tokens in (8192, 16384, 32768, 65536, 131072):
        context_cases.append({'case_id': f'context-{tokens}', 'target_context_tokens': tokens,
            'minimum_actual_prompt_fraction': .90, 'reserved_generation_tokens': 256,
            'needle_positions': [.12, .51, .89],
            'needles': [{'key': f'ledger_{i}', 'value': f'{rng.getrandbits(72):018x}'} for i in range(3)],
            'answer_rule': 'All three exact key/value pairs, with actual server tokenizer count and nontruncated prompt evidence.',
            'repetitions': 2,
            'stop_rule': 'Do not increase after instability or OOM; configuration-only acceptance is not context verification.'})
    protocol = {'version': 1, 'reviewer': 'independent verifier', 'checks':
        [{'id': key, 'expectation': value} for key, value in CHECKS],
        'context_cases': context_cases,
        'execution_scopes': ['LIVE_PASS', 'ISOLATED_PASS', 'MOCK_PASS', 'FAIL', 'BLOCKED', 'UNSAFE_TO_RUN'],
        'timing_rules': 'Measure monotonic end-to-end latency; separately report scheduler overhead, queue delay, first token and server token rates when actually available.',
        'privacy': 'Use synthetic requests only. Do not persist private prompt text or secrets in public review artifacts.',
        'visual_components': {'hierarchy': 2, 'typography': 2, 'information_density': 2, 'consistency': 2, 'usable_controls': 2},
        'no_retuning': 'Preserve this protocol and expected retrieval values after first outputs. Repairs require separate regression evidence.'}
    destination = OUT / 'protocol.json'
    encoded = (json.dumps(protocol, ensure_ascii=False, indent=2) + '\n').encode()
    if destination.exists() and destination.read_bytes() != encoded:
        raise SystemExit('Refusing to replace sealed independent expectations.')
    destination.write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    (OUT / 'protocol.sha256').write_text(digest + '\n', encoding='utf8')
    print(json.dumps({'checks': len(CHECKS), 'context_cases': len(context_cases), 'sha256': digest}))

if __name__ == '__main__':
    main()
