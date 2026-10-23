"""Versioned original UI remount setup; three original oracles unchanged."""
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button

def publish(original, output):
    original, output = (Path(original), Path(output))
    if output.exists():
        raise ValueError('Preserve earlier inputs, errors and oracles.')
    inputs = json.loads((original / 'inputs.json').read_text(encoding='utf8'))[1:]
    oracles = json.loads((original / 'oracles.json').read_text(encoding='utf8'))[1:]
    for row in inputs:
        row['steps'] = [button('Workspace settings'), button('MCP Hub')] + row['steps']
        validate_input(row)
    output.mkdir(parents=True)
    hashes = {}
    for name, obj in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(obj, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': len(inputs), 'hashes': hashes, 'execution_attempted': False, 'original': original.as_posix(), 'original_errors_preserved': True, 'change': 'Actual original Workspace settings then MCP Hub route navigation remounts the selected-detail state before the unchanged server-row step.', 'semantic_oracles_unchanged': True, 'generation_or_tool_invocation_authorized': False}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.original, args.output)))
