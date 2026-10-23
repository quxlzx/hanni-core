"""Input-only real native development surface sweep and original controls."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from scripts.campaign8_native.session import NativeSession
from scripts.campaign8_native.passive_downloads import observe_downloads
READBACK_PREFIXES = ('/api/workspace', '/api/productivity', '/api/projects', '/api/memory', '/api/workflows', '/api/mcp', '/api/notifications', '/api/awareness', '/api/voice', '/api/cluster', '/api/model-lab', '/api/model-routing', '/api/state', '/api/activity', '/api/calendar', '/api/agents', '/api/chat')
READBACK_EXACT = frozenset({'/api/audio-devices', '/api/gpu-routing'})

def surface_capture(session, identifier, *, mini=False):
    """Record hidden-target state and capture only a currently visible owned HWND."""
    windows = {'main': session.window_state(session.main), 'mini': session.window_state(session.mini)}
    target = 'mini' if mini else 'main'
    captured = target if windows[target]['visible'] else 'main' if windows['main']['visible'] else None
    if captured is None:
        return {'captured': False, 'reason': 'Both exact-owned native windows are hidden.', 'target_surface': target, 'native_windows': windows}
    result = session.capture(identifier, mini=captured == 'mini')
    return {**result, 'captured': True, 'target_surface': target, 'captured_surface': captured, 'target_visible': windows[target]['visible'], 'native_windows': windows}

def authenticated_readback(session, path):
    if not isinstance(path, str) or not (path.split('?', 1)[0] in READBACK_EXACT or any((path.split('?', 1)[0] == prefix or path.split('?', 1)[0].startswith(prefix + '/') for prefix in READBACK_PREFIXES))):
        raise ValueError('Readback must be an approved original local API path.')
    token = session.page.request.get(session.url + '/api/chat').json().get('token')
    if not isinstance(token, str) or not token or len(token) > 512:
        raise RuntimeError('Original disposable chat authority is unavailable.')
    response = session.page.request.get(session.url + path, headers={'X-Hanni-Token': token, 'Origin': session.url})
    data = response.json()

    def clean(value):
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items() if key.lower() not in {'token', 'password', 'secret', 'api_key', 'authorization'}}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value
    return {'path': path, 'status': response.status, 'data': clean(data), 'authority': 'Original ephemeral token; retained in memory only'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prospective-inputs', type=Path)
    parser.add_argument('--native-navigation', action='store_true')
    parser.add_argument('--observe-downloads', action='store_true')
    parser.add_argument('--observe-json-previews', action='store_true')
    args = parser.parse_args()
    import psutil
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    assert ready['evidence_class'] == 'CONTROLLED'
    assert psutil.Process(ready['pid']).create_time() == ready['create_time']
    with NativeSession(url=ready['url'], output=args.output) as session, observe_downloads(session, enabled=args.observe_downloads):
        session.report['backend_receipt'] = {k: ready[k] for k in ['url', 'pid', 'create_time', 'scope', 'evidence_class']}
        session.report['development_cases'] = []
        if args.prospective_inputs:
            inputs = json.loads(args.prospective_inputs.read_text(encoding='utf8'))
            for case in inputs:
                original = case.copy()
                result = {'input': original, 'executed': False, 'scope': 'Original native implementation; no expected outcomes consulted'}
                mini = case.get('surface') == 'mini'
                page = session.mini_page if mini else session.page
                try:
                    if mini:
                        session.execute({'id': case['id'] + '-owned-mini-setup', 'action': 'show', 'view': 'mini'})
                        result['fixture_setup'] = 'Exact-owned Mini shown for original frontend controls; no Mini action pass inferred from setup.'
                    else:
                        session.execute({'id': case['id'] + '-route', 'action': 'route', 'route': case['route']})
                    operation = case['operation']
                    control = case.get('control', {})
                    if operation == 'measure_layout':
                        session.execute({'id': case['id'] + '-size', 'action': 'resize', 'size': case['window_size']})
                    elif operation == 'fill_local':
                        session.page.keyboard.press('Control+k')
                        session.execute({'id': case['id'] + '-fill', 'action': 'fill', **control, 'value': case['value']})
                        result['fixture_setup'] = 'Original Control+k palette opened before fill.'
                    elif operation == 'open_dialog':
                        session.execute({'id': case['id'] + '-open', 'action': 'click', **control})
                    elif operation in {'keyboard', 'close_dialog'}:
                        if control:
                            session.page.get_by_role(control['role'], name=control['name'], exact=True).focus()
                        for key in case.get('keys', [case.get('key')]):
                            session.page.keyboard.press(key)
                            session.page.wait_for_timeout(100)
                            result.setdefault('keyboard_readbacks', []).append({'key': key, 'dom': session.dom()})
                    elif operation == 'read_projection':
                        paths = {'voice': '/api/voice', 'screen': '/api/awareness', 'cluster': '/api/cluster', 'models': '/api/model-lab'}
                        result['backend_readback'] = authenticated_readback(session, paths[case['route']])
                    elif operation == 'local_sequence':
                        if case.get('window_size'):
                            session.execute({'id': case['id'] + '-size', 'action': 'resize', 'size': case['window_size'], 'view': 'mini' if mini else 'main'})
                        result['step_receipts'] = []
                        for index, step in enumerate(case['steps']):
                            if step['action'] not in {'click', 'fill', 'select', 'check', 'press', 'upload_fixture'}:
                                raise ValueError('Local sequence must use original bounded DOM controls.')
                            receipt = session.execute({'id': case['id'] + '-step-' + str(index), **step, 'view': 'mini' if mini else 'main'})
                            if args.observe_json_previews:
                                from scripts.campaign8_native.json_preview import measure_json_preview
                                receipt['json_preview_measurement'] = measure_json_preview(session, receipt['result'])
                            receipt['screenshot'] = surface_capture(session, case['id'] + '-step-' + str(index), mini=mini)
                            result['step_receipts'].append(receipt)
                        result['backend_readbacks'] = [authenticated_readback(session, path) for path in case.get('readback_paths', [])]
                    elif operation == 'native_window':
                        for action in case.get('actions', [case.get('action')]):
                            session.execute({'id': case['id'] + '-' + action, 'action': action, 'size': case.get('window_size')})
                    else:
                        raise ValueError('Unsupported prospective development operation.')
                    result['dom'] = session.dom(mini=mini)
                    result['window'] = session.window_state(session.mini if mini else session.main)
                    result['screenshot'] = surface_capture(session, case['id'], mini=mini)
                    result['executed'] = True
                except Exception as error:
                    result['error'] = {'type': type(error).__name__, 'message': str(error)[:500]}
                    try:
                        result['dom'] = session.dom(mini=mini)
                        result['window'] = session.window_state(session.mini if mini else session.main)
                        result['error_screenshot'] = surface_capture(session, case['id'] + '-error', mini=mini)
                        result['backend_readbacks'] = [authenticated_readback(session, path) for path in case.get('readback_paths', [])]
                    except Exception as measurement_error:
                        result['measurement_error'] = {'type': type(measurement_error).__name__, 'message': str(measurement_error)[:300]}
                session.report['development_cases'].append(result)
                page.keyboard.press('Escape')
                session.save()
        else:
            session.report['visible_navigation_cases'] = []
            for route in session.report['declared_routes']:
                if args.native_navigation:
                    from scripts.campaign8_native.navigation import navigate, reset_capture_scroll
                    session.report['visible_navigation_cases'].append(navigate(session, route))
                    session.report['visible_navigation_cases'][-1]['capture_scroll_setup'] = reset_capture_scroll(session)
                else:
                    session.execute({'id': route + '-route', 'action': 'route', 'route': route})
                session.execute({'id': route + '-fonts', 'action': 'font_identity'})
                for size in [[1366, 860], [900, 650]]:
                    label = route + '-' + 'x'.join(map(str, size))
                    session.execute({'id': label + '-size', 'action': 'resize', 'size': size})
                    session.execute({'id': label + '-inventory', 'action': 'inventory'})
                    session.execute({'id': label, 'action': 'capture'})
            try:
                session.execute({'id': 'actual-application-open-mini', 'action': 'application_menu', 'name': 'Open HANNI Mini'})
                if not session.window_state(session.mini)['visible']:
                    raise RuntimeError('Owned menu input did not produce a visible Mini; no menu-control pass claimed.')
            except Exception as error:
                session.report['application_menu_automation_error'] = {'type': type(error).__name__, 'message': str(error)[:500]}
                session.execute({'id': 'owned-adapter-show-mini', 'action': 'show', 'view': 'mini'})
                session.report['mini_display_input_layer'] = 'Owned native HWND show adapter; original Application menu invocation unavailable.'
            session.execute({'id': 'mini-fonts', 'action': 'font_identity', 'view': 'mini'})
            for size in [[1366, 860], [900, 650]]:
                label = 'mini-' + 'x'.join(map(str, size))
                session.execute({'id': label + '-size', 'action': 'resize', 'size': size, 'view': 'mini'})
                session.execute({'id': label + '-inventory', 'action': 'inventory', 'view': 'mini'})
                session.execute({'id': label, 'action': 'capture', 'view': 'mini'})
        session.report['complete'] = True
if __name__ == '__main__':
    main()
