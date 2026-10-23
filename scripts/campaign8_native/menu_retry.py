"""Exposed safe Application menu input through one owned native window."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from scripts.campaign8_native.native_controls import keys
from scripts.campaign8_native.session import NativeSession

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import psutil
    import win32con
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    if psutil.Process(ready['pid']).create_time() != ready['create_time']:
        raise RuntimeError('Owned backend process identity changed.')
    with NativeSession(url=ready['url'], output=args.output, maximum_seconds=120) as session:
        session.report['backend_receipt'] = {key: ready[key] for key in ['url', 'pid', 'create_time', 'scope', 'evidence_class']}
        session.report['menu_attempts'] = []
        first = {'method': 'Owned actual cursor click; popup foreground retained'}
        try:
            first['input_receipt'] = session.execute({'id': 'cursor-menu-open-mini', 'action': 'application_menu', 'name': 'Open HANNI Mini'})
        except Exception as error:
            first['error'] = {'type': type(error).__name__, 'message': str(error)[:600]}
        first['actual_mini_visible'] = session.window_state(session.mini)['visible']
        session.report['menu_attempts'].append(first)
        if not first['actual_mini_visible']:
            second = {'method': 'Owned foreground actual Alt, Down, Home, Enter keys; safe first menu entry only'}
            try:
                second['keys'] = [keys(session.main, [win32con.VK_MENU]), keys(session.main, [win32con.VK_DOWN], preserve_owned_foreground=True), keys(session.main, [win32con.VK_HOME], preserve_owned_foreground=True), keys(session.main, [win32con.VK_RETURN], preserve_owned_foreground=True)]
            except Exception as error:
                second['error'] = {'type': type(error).__name__, 'message': str(error)[:600]}
            second['actual_mini_visible'] = session.window_state(session.mini)['visible']
            session.report['menu_attempts'].append(second)
        session.report['actual_application_open_mini_confirmed'] = any((item['actual_mini_visible'] for item in session.report['menu_attempts']))
        session.report['main_after'] = session.window_state(session.main)
        session.report['mini_after'] = session.window_state(session.mini)
        session.report['main_capture'] = session.capture('actual-menu-input-main')
        if session.report['mini_after']['visible']:
            session.report['mini_capture'] = session.capture('actual-menu-input-mini', mini=True)
            session.execute({'id': 'menu-mini-dismiss', 'action': 'click', 'view': 'mini', 'role': 'button', 'name': 'Dismiss Mini'})
        session.report['affirmative_assistant_start_input'] = False
        session.report['complete'] = True
    session.report['backend_preserved_after_native_exit'] = psutil.Process(ready['pid']).create_time() == ready['create_time']
    session.save()
if __name__ == '__main__':
    main()
