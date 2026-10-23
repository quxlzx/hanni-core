"""Owned native menus, tray, global shortcut, Mini and local preference actions."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
from scripts.campaign8_native.menus import named_native_control
from scripts.campaign8_native.session import NativeSession

def cancel_original_start_dialog(session):
    import win32con
    import win32gui
    import win32process
    from scripts.campaign8_native.menus import tray_menu
    session.identity.verify()
    selection = tray_menu(session.identity, 'Start Assistant…')
    deadline = time.monotonic() + 5
    dialog = None
    while time.monotonic() < deadline:
        candidates = []

        def observe(hwnd, unused):
            if win32process.GetWindowThreadProcessId(hwnd)[1] == session.identity.pid and win32gui.GetWindowText(hwnd) == 'Start Assistant' and (win32gui.GetClassName(hwnd) == '#32770'):
                candidates.append(hwnd)
        win32gui.EnumWindows(observe, None)
        if len(candidates) == 1:
            dialog = candidates[0]
            break
        time.sleep(0.05)
    if dialog is None:
        raise RuntimeError('Original owned Start Assistant confirmation was unavailable; no affirmative input sent.')
    session.identity.verify()
    negative = win32gui.GetDlgItem(dialog, 7)
    if not negative or win32process.GetWindowThreadProcessId(negative)[1] != session.identity.pid or win32gui.GetWindowText(negative).replace('&', '').lower() != 'no':
        raise RuntimeError('Owned No control was not verified; no dialog input sent.')
    win32gui.SendMessage(negative, 245, 0, 0)
    time.sleep(0.2)
    return {'tray_selection': selection, 'dialog_hwnd': dialog, 'button_hwnd': negative, 'button_id': 7, 'selected': 'No', 'dialog_closed': not win32gui.IsWindow(dialog), 'input_layer': 'Actual original owned confirmation; no affirmative input or assistant launch'}

def keys(window, codes, *, preserve_owned_foreground=False):
    import win32api
    import win32con
    import win32gui
    window.verify()
    import win32process
    if not preserve_owned_foreground:
        win32gui.SetForegroundWindow(window.hwnd)
    foreground = win32gui.GetForegroundWindow()
    if not foreground or win32process.GetWindowThreadProcessId(foreground)[1] != window.process.pid:
        raise RuntimeError('Owned foreground was not established; no keys injected.')
    down = []
    try:
        for code in codes:
            win32api.keybd_event(code, 0, 0, 0)
            down.append(code)
    finally:
        for code in reversed(down):
            win32api.keybd_event(code, 0, win32con.KEYEVENTF_KEYUP, 0)
    window.verify()
    time.sleep(0.25)
    return {'virtual_keys': codes, 'input_layer': 'Actual Windows keys with exact owned foreground HWND guard'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import psutil
    import win32con
    import win32gui
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    assert ready['evidence_class'] == 'CONTROLLED'
    assert psutil.Process(ready['pid']).create_time() == ready['create_time']
    with NativeSession(url=ready['url'], output=args.output) as session:
        session.report['native_control_cases'] = []
        session.report['backend_receipt'] = {k: ready[k] for k in ['url', 'pid', 'create_time', 'scope', 'evidence_class']}

        def action(name, function):
            entry = {'id': name, 'before_main': session.window_state(session.main), 'before_mini': session.window_state(session.mini)}
            try:
                entry['result'] = function()
                entry['executed'] = True
            except Exception as error:
                entry['executed'] = False
                entry['error'] = {'type': type(error).__name__, 'message': str(error)[:600]}
            entry.update(after_main=session.window_state(session.main), after_mini=session.window_state(session.mini))
            session.report['native_control_cases'].append(entry)
            session.check_budget()
            session.save()
            return entry
        action('owned-uia-native-tree', lambda: named_native_control(session.main, '', action='inspect_tree'))
        action('original-application-open-mini', lambda: session.execute({'id': 'menu-open-mini', 'action': 'application_menu', 'name': 'Open HANNI Mini'}))
        action('actual-owned-tray-inventory', lambda: session.execute({'id': 'tray-inventory', 'action': 'tray_menu'}))
        action('actual-owned-tray-open-mini', lambda: session.execute({'id': 'tray-mini', 'action': 'tray_menu', 'name': 'Open HANNI Mini'}))
        action('original-mini-hotkey-status', lambda: session.execute({'id': 'mini-state', 'action': 'mini_bridge', 'method': 'get_state', 'view': 'mini'}))
        action('actual-mini-dismiss', lambda: session.execute({'id': 'mini-dismiss', 'action': 'click', 'role': 'button', 'name': 'Dismiss Mini', 'view': 'mini'}))

        def shortcut():
            state = session.mini_page.evaluate('async()=>await window.pywebview.api.get_state()')
            if state.get('shortcut') != 'Ctrl+Shift+H' or state.get('error'):
                raise RuntimeError('Owned shortcut is not genuinely registered; no global keys sent.')
            return keys(session.main, [win32con.VK_CONTROL, win32con.VK_SHIFT, ord('H')])
        action('actual-registered-global-shortcut', shortcut)
        action('actual-mini-pin', lambda: session.execute({'id': 'mini-pin', 'action': 'click', 'role': 'button', 'name': 'Pin', 'view': 'mini'}))
        action('actual-mini-unpin', lambda: session.execute({'id': 'mini-unpin', 'action': 'click', 'role': 'button', 'name': 'Pinned', 'view': 'mini'}))
        action('actual-mini-expand', lambda: session.execute({'id': 'mini-expand', 'action': 'click', 'role': 'button', 'name': 'Expand', 'view': 'mini'}))
        action('actual-tray-close-to-tray-enable', lambda: session.execute({'id': 'tray-close-enable', 'action': 'tray_menu', 'name': 'Close to tray'}))

        def close_to_tray():
            preferences = json.loads((session.output / 'native-state/window.json').read_text())
            if not preferences['close_to_tray']:
                raise RuntimeError('Actual tray toggle did not enable close-to-tray; leaving HWND alive for cleanup.')
            win32gui.PostMessage(session.main.hwnd, win32con.WM_CLOSE, 0, 0)
            time.sleep(0.3)
            return {'input': 'Owned original WM_CLOSE with persisted close-to-tray true'}
        action('actual-window-close-to-tray', close_to_tray)
        time.sleep(0.3)
        action('actual-tray-restore-hidden-window', lambda: session.execute({'id': 'tray-restore', 'action': 'tray_restore'}))
        action('actual-tray-close-to-tray-disable', lambda: session.execute({'id': 'tray-close-disable', 'action': 'tray_menu', 'name': 'Close to tray'}))
        action('actual-tray-minimize-to-tray-enable', lambda: session.execute({'id': 'tray-minimize-enable', 'action': 'tray_menu', 'name': 'Minimize to tray'}))
        action('actual-window-minimize-to-tray', lambda: session.execute({'id': 'minimize-tray', 'action': 'minimize'}))
        action('actual-tray-restore-minimized-window', lambda: session.execute({'id': 'tray-restore-2', 'action': 'tray_restore'}))
        action('actual-tray-minimize-to-tray-disable', lambda: session.execute({'id': 'tray-minimize-disable', 'action': 'tray_menu', 'name': 'Minimize to tray'}))
        action('actual-start-assistant-confirmation-cancel', lambda: cancel_original_start_dialog(session))
        action('actual-tray-desktop-notifications-enable', lambda: session.execute({'id': 'tray-notifications-enable', 'action': 'tray_menu', 'name': 'Desktop notifications'}))
        action('actual-tray-desktop-notifications-disable', lambda: session.execute({'id': 'tray-notifications-disable', 'action': 'tray_menu', 'name': 'Desktop notifications'}))
        session.report['final_local_preferences'] = json.loads((session.output / 'native-state/window.json').read_text())
        session.report['backend_preserved_at_native_close'] = psutil.Process(ready['pid']).create_time() == ready['create_time']
        from scripts.campaign8_native.menus import tray_menu
        session.report['actual_tray_exit'] = tray_menu(session.identity, 'Exit desktop')
        session.process.wait(timeout=15)
        session.report['actual_tray_exit']['exit_code'] = session.process.returncode
        session.report['actual_tray_exit']['backend_preserved_after_exit'] = psutil.Process(ready['pid']).create_time() == ready['create_time']
        session.report['complete'] = True
if __name__ == '__main__':
    main()
