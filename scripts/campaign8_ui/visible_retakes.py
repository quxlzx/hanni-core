"""Two input-only original UI-state corrections; original oracles untouched."""
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button

def publish(original, output):
    original, output = (Path(original), Path(output))
    if output.exists():
        raise ValueError('Retain original prospective corpus and errors.')
    selected = {'visible-final-workflow-activity-navigation', 'visible-final-settings-inspector'}
    inputs = [r for r in json.loads((original / 'inputs.json').read_text(encoding='utf8')) if r['id'] in selected]
    oracles = [r for r in json.loads((original / 'oracles.json').read_text(encoding='utf8')) if r['id'] in selected]
    for row in inputs:
        if row['id'] == 'visible-final-workflow-activity-navigation':
            row['steps'] = [button('HANNI home'), {'action': 'click', 'selector': '.area-button', 'index': 1}, button('Workflows')] + row['steps']
        else:
            row['steps'][1] = {'action': 'click', 'selector': '.inspector button[aria-label="Hide inspector"]'}
        validate_input(row)
    output.mkdir(parents=True)
    hashes = {}
    for name, obj in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(obj, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': len(inputs), 'hashes': hashes, 'execution_attempted': False, 'original': original.as_posix(), 'original_errors_preserved': True, 'semantic_oracles_unchanged': True, 'changes': 'Actual Home→Workspace group→Workflows navigation remounts list; original owned inspector Hide closes the obstructing aside rather than clicking covered background.', 'generation_or_tool_or_provider_authorized': False}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.original, args.output)))
