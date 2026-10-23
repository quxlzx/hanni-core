"""Prospective native input plan; execution never receives the scoring oracle."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .inventory import inventory
OPERATIONS = frozenset({'navigate', 'inspect', 'click_local', 'fill_local', 'select_local', 'open_dialog', 'close_dialog', 'keyboard', 'measure_layout', 'read_projection', 'native_window', 'local_sequence'})

def validate_input(case):
    if not isinstance(case, dict) or set(case) & {'expected', 'oracle', 'checker_inputs'}:
        raise ValueError('Execution accepts prospective inputs without expected answers.')
    if case.get('operation') not in OPERATIONS:
        raise ValueError('Unsupported native audit operation.')
    if case.get('surface', 'desktop') not in {'desktop', 'mini'}:
        raise ValueError('Choose an original desktop surface.')
    if any((key in case for key in ('javascript', 'command', 'shell', 'url', 'pid', 'hwnd'))):
        raise ValueError('Inputs cannot grant arbitrary execution or process authority.')
    if case['operation'] == 'native_window':
        actions = case.get('actions', [case.get('action')])
        allowed = {'resize', 'minimize', 'maximize', 'restore', 'focus', 'pin', 'unpin', 'expand', 'dismiss', 'show', 'hide', 'close'}
        if not isinstance(actions, list) or not actions or any((a not in allowed for a in actions)):
            raise ValueError('Choose a fixed owned-window action.')
    if case['operation'] == 'local_sequence':
        steps = case.get('steps')
        if not isinstance(steps, list) or not 1 <= len(steps) <= 32:
            raise ValueError('Provide a bounded local control sequence.')
        for step in steps:
            if not isinstance(step, dict) or step.get('action') not in {'click', 'fill', 'select', 'check', 'press', 'upload_fixture'}:
                raise ValueError('Only fixed local DOM control actions are supported.')
            if set(step) - {'action', 'role', 'name', 'index', 'selector', 'value', 'key', 'checked', 'settle_ms', 'timeout_ms', 'fixture_id'}:
                raise ValueError('Control steps cannot contain oracles or execution authority.')
            if step['action'] == 'upload_fixture':
                from .upload import upload_fixture
                if step.get('selector') != 'dialog input[type="file"]' or set(step) - {'action', 'selector', 'fixture_id'}:
                    raise ValueError('Only the original scoped MCP file input accepts synthetic upload.')
                upload_fixture(step.get('fixture_id'))
        if any((not isinstance(path, str) or not path.startswith(('/api/productivity', '/api/memory/', '/api/notifications', '/api/workflows', '/api/agents', '/api/cluster', '/api/model-lab', '/api/model-routing', '/api/mcp', '/api/voice', '/api/awareness', '/api/workspace', '/api/calendar', '/api/audio-devices', '/api/gpu-routing')) for path in case.get('readback_paths', []))):
            raise ValueError('Only declared original local audit projections are supported.')
    return case

def prospective_plan():
    source = inventory()
    cases, oracles = ([], [])
    for route in source['routes']:
        for name, dimensions in [('wide', [1280, 800]), ('compact', [960, 700])]:
            identifier = route['route'] + '-' + name
            cases.append({'id': identifier, 'route': route['route'], 'surface': 'desktop', 'operation': 'measure_layout', 'window_size': dimensions, 'scope': 'Actual owned Windows HWND; physical DPI observed, never changed.', 'fixture_id': 'original-empty-backend'})
            oracles.append({'id': identifier, 'checks': ['actual_owned_hwnd', 'original_backend_route', 'main_content_visible', 'no_unintended_root_horizontal_overflow', 'controls_not_clipped_by_window_chrome', 'loaded_font_recorded', 'native_capture_or_blocker'], 'native_required': True})
    extra = [('palette-focus', 'home', 'keyboard', {'key': 'Control+k'}), ('palette-escape', 'home', 'close_dialog', {'key': 'Escape'}), ('palette-no-match', 'home', 'fill_local', {'control': {'role': 'textbox', 'name': 'Search screens, capabilities, or loaded messages'}, 'value': 'synthetic-absent-search-zeta'}), ('task-draft-dialog', 'tasks', 'open_dialog', {'control': {'role': 'button', 'name': 'New task'}}), ('memory-tabs-keys', 'memory', 'keyboard', {'control': {'role': 'tab', 'name': 'Stored memories'}, 'keys': ['ArrowRight', 'Home', 'End']}), ('voice-unavailable', 'voice', 'read_projection', {}), ('screen-unavailable', 'screen', 'read_projection', {}), ('cluster-unconfigured', 'cluster', 'read_projection', {}), ('model-not-loaded', 'models', 'read_projection', {}), ('owned-window-resize', 'home', 'native_window', {'action': 'resize', 'window_size': [960, 700]}), ('owned-window-minimize-restore', 'home', 'native_window', {'actions': ['minimize', 'restore']})]
    for identifier, route, operation, values in extra:
        cases.append({'id': identifier, 'route': route, 'operation': operation, 'fixture_id': 'original-empty-backend', **values})
        oracles.append({'id': identifier, 'checks': ['actual_original_native_outcome', 'no_owner_mutation', 'original_backend_or_local_control_evidence'], 'native_required': True})
    for case in cases:
        validate_input(case)
    return (cases, oracles, source['source_hashes'])

def publish(output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Preserve every prospective plan version.')
    output.mkdir(parents=True)
    cases, oracles, sources = prospective_plan()
    hashes = {}
    for name, value in [('inputs.json', cases), ('oracles.json', oracles)]:
        text = json.dumps(value, indent=2) + '\n'
        (output / name).write_text(text, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(text.encode()).hexdigest()
    seal = {'cases': len(cases), 'inputs_and_oracles_separate': True, 'hashes': hashes, 'source_identity': sources, 'execution_attempted': False, 'scope': 'Development source/interaction plan only; no native pass is implied.'}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)['hashes']))
