"""Finite original model-free Lab UI control fixture and prospective cases.

The sole controlled dependency adds bounded wall time before the unchanged
original routing evaluator. It does not replace results, admission or status.
Consequently this fixture is unsuitable for latency/performance comparisons.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch
from .plan import validate_input
from .supplement import button, field, select

def install_delay(backend, stack):
    from hanni.evals import routing
    original = routing.evaluate_case
    calls = []

    def delayed(*args, **kwargs):
        if len(calls) >= 204:
            raise RuntimeError('The finite controlled evaluation budget is exhausted.')
        delay = 0.15
        calls.append({'case_id': getattr(args[1], 'id', None), 'dependency': 'original routing.evaluate_case timing', 'outcome': 'CONTROLLED_DELAY', 'delay_seconds': delay})
        time.sleep(delay)
        return original(*args, **kwargs)
    stack.enter_context(patch.object(routing, 'evaluate_case', delayed))
    backend.lab_control_calls = calls
    return {'scope': 'Original deterministic routing evaluator with finite .15-second pre-call delay; no result/status override, neural inference or tool execution.', 'max_evaluations': 204, 'max_added_delay_seconds': 30.6, 'performance_comparison_eligible': False}

def cases():

    def row(key, steps, check):
        identifier = 'lab-controls-' + key
        return ({'id': identifier, 'route': 'models', 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-lab-controls', 'window_size': [1280, 800], 'steps': steps, 'readback_paths': ['/api/model-lab']}, {'id': identifier, 'check': check, 'scope': 'Original native UI, deterministic routing evaluator and durable Lab SQLite. Timing is deliberately controlled; no model-quality, inference or tool-dispatch claim.'})
    inputs, oracles = ([], [])
    rows = [row('pause-resume-101', [button('Benchmark runner'), select('Benchmark suite', 'llm-tools-development'), field('input[aria-label="Output tokens"]', '32'), field('input[aria-label="Tool rounds"]', '1'), select('Benchmark suite', 'routing-development'), field('input[aria-label="Cases"]', '101'), field('input[aria-label="Repetitions"]', '1'), button('Start benchmark', settle_ms=350), button('Pause after case', settle_ms=1800), button('Resume checkpoint', settle_ms=35000)], {'actual_pause_checkpoint': True, 'same_run_resume': True, 'final_status': 'completed', 'completed': 101, 'total': 101, 'unique_persisted_ordinals': list(range(101)), 'suite_id': 'routing-development', 'endpoint_id': None, 'model_generation_requests': 0, 'actual_tool_execution': False}), row('case-pagination', [button('Inspect results', settle_ms=500), button('Next cases', settle_ms=700), {'action': 'click', 'selector': '.lab-case-list button', 'index': 0}, button('Previous cases', settle_ms=700)], {'page_2_original_case_ordinal': 100, 'page_2_count': 1, 'page_1_original_ordinals': list(range(100)), 'page_1_count': 100, 'original_detail_GET_offsets': [100, 0], 'persisted_run_and_case_payloads_unchanged': True}), row('cancel-after-case', [button('Benchmark runner'), button('Start benchmark', settle_ms=350), button('Cancel after case', settle_ms=1800)], {'new_distinct_run': True, 'final_status': 'cancelled', 'completed_in_range': [1, 100], 'total': 101, 'no_duplicate_committed_ordinal': True, 'current_case': None, 'active_run_id': None, 'original_durable_case_boundary': True, 'model_generation_requests': 0, 'actual_tool_execution': False})]
    for item, oracle in rows:
        validate_input(item)
        inputs.append(item)
        oracles.append(oracle)
    return (inputs, oracles)

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Preserve all previous prospective inputs and outcomes.')
    inputs, oracles = cases()
    output.mkdir(parents=True)
    hashes = {}
    for name, value in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(value, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    from hanni.evals.model_lab import corpus
    bank = corpus('routing-development')
    seal = {'cases': len(inputs), 'hashes': hashes, 'original_routing_bank_size': len(bank), 'execution_attempted': False, 'generation_authorized': False, 'tool_execution_authorized': False, 'max_evaluations': 204, 'max_added_delay_seconds': 30.6, 'performance_comparison_eligible': False}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
