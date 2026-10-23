"""Prospective original native export limitation proof, never download consent."""
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Preserve every original limitation receipt.')
    inputs = [{'id': 'export-before-detail-native-denial', 'route': 'models', 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-lab-controls', 'window_size': [1280, 800], 'steps': [button('Export JSON', settle_ms=1000)], 'readback_paths': ['/api/model-lab']}, {'id': 'export-before-comparison-native-denial', 'route': 'models', 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-lab-controls', 'window_size': [1280, 800], 'steps': [button('Benchmark runner'), button('Start benchmark', settle_ms=3000), button('Compare'), {'action': 'check', 'selector': '.lab-history input[type="checkbox"]', 'index': 0, 'checked': True}, {'action': 'check', 'selector': '.lab-history input[type="checkbox"]', 'index': 1, 'checked': True}, button('Compare selected runs', settle_ms=700), {'action': 'click', 'selector': '.lab-actions button:has-text("Export ")', 'index': 0, 'settle_ms': 1000}], 'readback_paths': ['/api/model-lab']}]
    oracles = [{'id': item['id'], 'check': {'original_serialized_export_GET_200': True, 'original_native_download_policy_false_preserved': True, 'no_completed_download_claim_without_actual_evidence': True, 'actual_generation_requests': 0, 'actual_tool_dispatches': 0, 'owner_files_or_clipboard_untouched': True}, 'scope': 'Original packaged native export behavior/limitation before any repair. Readonly passive download events only; no CDP allow override, save_as, external file dialog, owner Downloads read or write.'} for item in inputs]
    for item in inputs:
        validate_input(item)
    output.mkdir(parents=True)
    hashes = {}
    for name, value in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(value, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': 2, 'hashes': hashes, 'execution_attempted': False, 'append_after': 'residual-final-prospective-cycle1', 'no_generation_or_provider_or_tool_execution': True, 'native_download_policy_override_authorized': False, 'original_routing_evaluations_budget': 20, 'original_pre_evaluator_delay_seconds_per_call': 0.15}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
