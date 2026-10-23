"""Prospective exact native JSON viewing checks, with no answer in execution."""
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Preserve original canceled exports and every afterproof.')
    original = Path('data/campaign8-ui/native-policy-retakes-prospective-cycle1')
    setup = json.loads((original / 'SETUP.json').read_text(encoding='utf8'))
    inputs = [{'id': 'native-json-preview-results', 'route': 'models', 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-lab-controls', 'window_size': [1280, 800], 'steps': [button('View JSON', settle_ms=700), button('Select JSON'), button('Close'), button('View JSON', settle_ms=700), button('Close dialog'), button('View JSON', settle_ms=700), {'action': 'press', 'selector': 'dialog', 'key': 'Escape'}], 'readback_paths': ['/api/model-lab']}, {'id': 'native-json-preview-comparison', 'route': 'models', 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-lab-controls', 'window_size': [1280, 800], 'steps': [button('Benchmark runner'), button('Start benchmark', settle_ms=3000), button('Compare'), {'action': 'check', 'selector': '.lab-history input[type="checkbox"]', 'index': 0, 'checked': True}, {'action': 'check', 'selector': '.lab-history input[type="checkbox"]', 'index': 1, 'checked': True}, button('Compare selected runs', settle_ms=700), {'action': 'click', 'selector': '.lab-actions button:has-text("View JSON ")', 'index': 0, 'settle_ms': 700}, button('Select JSON'), button('Close')], 'readback_paths': ['/api/model-lab']}]
    oracles = [{'id': item['id'], 'check': {'original_serialized_export_GET_200': True, 'preview_text_equals_complete_original_serialized_assembly': True, 'server_numeric_spellings_and_redaction_preserved': True, 'selection_start': 0, 'selection_end_equals_full_text_length': True, 'preview_readonly': True, 'dialog_closed': True, 'original_native_download_policy_false_preserved': True, 'browser_download_control_absent_in_native': True, 'actual_generation_requests': 0, 'actual_tool_dispatches': 0, 'owner_files_or_clipboard_untouched': True}, 'scope': 'Actual native JSON viewing/selection/closure, not file delivery, clipboard writes, neural quality or general benchmark speed.'} for item in inputs]
    for item in setup + inputs:
        validate_input(item)
    output.mkdir(parents=True)
    hashes = {}
    for name, obj in [('inputs.json', inputs), ('oracles.json', oracles), ('SETUP.json', setup), ('EXECUTION.json', setup + inputs)]:
        wire = json.dumps(obj, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'targets': 2, 'original_fixture_setup': 1, 'hashes': hashes, 'execution_attempted': False, 'max_original_routing_evaluations': 20, 'native_download_policy_override_authorized': False, 'generation_provider_tool_or_clipboard_action_authorized': False, 'preview_byte_bound': 8 * 1024 * 1024, 'source': 'Approved bounded frontend JSON viewer; original complete serializer and original native download policy retained.'}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
