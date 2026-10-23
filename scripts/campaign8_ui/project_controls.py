"""New supported Project controls; original unsupported URL oracle stays intact."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button, field

def cases():
    prefix = [{'action': 'click', 'selector': '.project-list button', 'index': 0}]
    inputs, oracles = ([], [])
    for key, steps, expected in [('file-link-save', prefix + [button('Add link'), field('#workspace-title', 'Controlled supported file link'), {'action': 'select', 'selector': '#workspace-link-kind', 'value': 'conversation'}, {'action': 'select', 'selector': '#workspace-link-kind', 'value': 'file'}, field('#workspace-target', 'C:\\campaign8-not-opened\\controlled-file.txt'), button('Save', settle_ms=800)], {'persisted_link': {'label': 'Controlled supported file link', 'kind': 'file', 'target': 'C:\\campaign8-not-opened\\controlled-file.txt'}, 'target_never_opened': True}), ('file-link-delete', prefix + [button('Remove Controlled supported file link link'), button('Confirm deletion', settle_ms=800)], {'link_absent': 'Controlled supported file link', 'original_seed_link_retained': True}), ('note-delete', prefix + [{'action': 'click', 'selector': '.project-note summary', 'index': 0}, button('Delete note', index=0), button('Confirm deletion', settle_ms=800)], {'original_selected_note_absent': True, 'original_project_retained': 'Controlled QA observatory'})]:
        identifier = 'supported-project-' + key
        inputs.append({'id': identifier, 'route': 'projects', 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-populated-backend', 'window_size': [1280, 800], 'steps': steps, 'readback_paths': ['/api/productivity']})
        oracles.append({'id': identifier, 'check': expected, 'scope': 'Actual supported original file/conversation link fields and original local note deletion; no URL link support or actual target access is inferred.'})
    for row in inputs:
        validate_input(row)
    return (inputs, oracles)

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Preserve prior prospective inputs and original errors.')
    output.mkdir(parents=True)
    inputs, oracles = cases()
    hashes = {}
    for name, value in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(value, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': len(inputs), 'hashes': hashes, 'execution_attempted': False, 'original_errors_and_oracles_preserved': True, 'amendment': 'Explicit project selection and note disclosure; new file-link expectation because the original URL expectation is unsupported, not a regraded URL pass.'}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
