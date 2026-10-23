"""Separate native keyboard proof with implicit CDP defaults disabled."""
import hashlib
import json
from pathlib import Path
from .plan import validate_input

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Retain every earlier keyboard/source proof.')
    item = {'id': 'memory-native-policy-four-keys', 'route': 'memory', 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-lab-controls', 'window_size': [900, 650], 'steps': [{'action': 'click', 'role': 'tab', 'name': 'Stored memories'}] + [{'action': 'press', 'selector': '.memory-tabs [role="tab"][tabindex="0"]', 'key': key} for key in ['ArrowRight', 'ArrowLeft', 'Home', 'End']], 'readback_paths': ['/api/memory/explorer?limit=30']}
    validate_input(item)
    oracle = {'id': item['id'], 'check': {'after_keys_selected_and_focused': ['Review queue', 'Stored memories', 'Stored memories', 'Project context'], 'one_tabIndex_zero_after_every_key': True, 'nonactive_tabs_tabIndex_minus_one': True, 'no_key_induced_tablist_or_page_scroll': True, 'original_stored_memories_unchanged': True}, 'scope': 'Actual original owned WebView keyboard/focus/selection and HWND pixels with no_defaults=True. One physical DPI120 monitor; no microphone/audio/model action or unmodified OS-focus claim.'}
    output.mkdir(parents=True)
    hashes = {}
    for name, obj in [('inputs.json', [item]), ('oracles.json', [oracle])]:
        wire = json.dumps(obj, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': 1, 'hashes': hashes, 'execution_attempted': False, 'connector': 'no_defaults=True; no global download/focus/media override', 'generation_or_tool_or_provider_or_physical_audio_authorized': False}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
