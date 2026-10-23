"""Original-policy export/inspector retakes with separately declared setup.

The two export inputs/oracles stay identical. Only the inspector's unnecessary
post-navigation Hide action is removed; its original oracle is retained.
"""
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button, field, select

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Keep the original confounded/export/helper receipts.')
    original_export = Path('data/campaign8-ui/export-before-prospective-cycle1')
    original_residual = Path('data/campaign8-ui/residual-final-prospective-cycle1')
    exports = json.loads((original_export / 'inputs.json').read_text(encoding='utf8'))
    export_oracles = json.loads((original_export / 'oracles.json').read_text(encoding='utf8'))
    originals = json.loads((original_residual / 'inputs.json').read_text(encoding='utf8'))
    inspector = next((r for r in originals if r['id'] == 'residual-final-inspector-review-settings'))
    inspector['steps'] = inspector['steps'][:2]
    inspector_oracle = next((r for r in json.loads((original_residual / 'oracles.json').read_text(encoding='utf8')) if r['id'] == inspector['id']))
    inputs, oracles = (exports + [inspector], export_oracles + [inspector_oracle])
    setup = [{'id': 'policy-retake-original-lab-setup', 'route': 'models', 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-lab-controls', 'window_size': [1280, 800], 'steps': [button('Benchmark runner'), select('Benchmark suite', 'llm-tools-development'), field('input[aria-label="Output tokens"]', '32'), field('input[aria-label="Tool rounds"]', '1'), select('Benchmark suite', 'routing-development'), field('input[aria-label="Cases"]', '10'), field('input[aria-label="Repetitions"]', '1'), button('Start benchmark', settle_ms=3000), button('Inspect results', settle_ms=500)], 'readback_paths': ['/api/model-lab']}]
    for item in setup + inputs:
        validate_input(item)
    output.mkdir(parents=True)
    hashes = {}
    for name, obj in [('inputs.json', inputs), ('oracles.json', oracles), ('SETUP.json', setup), ('EXECUTION.json', setup + inputs)]:
        wire = json.dumps(obj, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'target_retakes': 3, 'separate_original_fixture_setup': 1, 'hashes': hashes, 'execution_attempted': False, 'export_inputs_and_oracle_objects_identical': True, 'inspector_oracle_unchanged': True, 'inspector_source_correction': 'navigate closes the original inspector at CSS width<=1100; stop after successful Review settings instead of clicking an absent Hide.', 'source': [str(original_export), str(original_residual)], 'native_download_policy_override_authorized': False, 'generation_or_provider_or_tool_execution_authorized': False, 'max_original_routing_evaluations': 20, 'setup_scope': 'Actual original run creation and UI result selection, not injected statuses/results or model quality.'}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
