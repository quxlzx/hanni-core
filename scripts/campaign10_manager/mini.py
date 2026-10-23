"""Fresh original native Mini window pixels, with current isolated backend."""
from pathlib import Path
import argparse
from scripts.campaign10_manager.native_session import NativeSession
from scripts.campaign8_native.development import authenticated_readback
ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bridge', action='store_true')
    parser.add_argument('--cycle')
    parser.add_argument('--owned-window', action='store_true')
    parser.add_argument('--interactions', action='store_true')
    parser.add_argument('--activate-click', action='store_true')
    args = parser.parse_args()
    cycle = args.cycle or ('current-mini-cycle2' if args.bridge else 'current-mini-cycle1')
    with NativeSession(url='http://127.0.0.1:8766', output=ROOT / 'data/campaign10-native' / cycle, maximum_seconds=120, evidence_class='ACTUAL_WINDOWS_CURRENT_BACKEND_ISOLATED_STATE') as session:
        if args.owned_window:
            session.report['mini_open_method'] = 'Owned native HWND show/restore for visual evidence; no original Open Mini control pass inferred'
            session.execute({'id': 'owned-mini-show', 'action': 'show', 'view': 'mini'})
            session.execute({'id': 'owned-mini-restore', 'action': 'restore', 'view': 'mini'})
        elif args.bridge:
            session.report['mini_open_method'] = 'Original native JS bridge show_mini; no primary menu-control pass inferred'
            session.page.evaluate('async()=>await window.pywebview.api.show_mini()')
        else:
            session.execute({'id': 'open-native-mini', 'action': 'application_menu', 'name': 'Open HANNI Mini'})
        session.mini_page.wait_for_timeout(1200)
        session.report['mini_dom'] = session.dom(mini=True)
        session.report['mini_captures'] = []
        for size in ([620, 560], [480, 560]):
            session.execute({'id': 'mini-size-' + str(size[0]), 'action': 'resize', 'view': 'mini', 'size': size})
            session.mini_page.wait_for_timeout(1200)
            session.report['mini_captures'].append({'size': size, 'window': session.window_state(session.mini), 'dom': session.dom(mini=True), 'screenshot': session.capture('mini-' + str(size[0]), mini=True)})
        session.report['mini_fonts'] = session.platform_fonts(mini=True)
        if args.interactions:
            if args.activate_click:
                import win32api, win32con, win32gui, win32process
                session.report['activation_pin'] = session.execute({'id': 'activation-pin', 'action': 'mini_bridge', 'view': 'mini', 'method': 'pin', 'arguments': [True]})
                session.mini_page.wait_for_timeout(300)
                session.mini.verify()
                point = win32gui.ClientToScreen(session.mini.hwnd, (105, 22))
                target = win32gui.WindowFromPoint(point)
                if not target or win32process.GetWindowThreadProcessId(target)[1] != session.identity.pid or win32gui.GetAncestor(target, win32con.GA_ROOT) != session.mini.hwnd:
                    raise RuntimeError('Mini header mouse activation target is not the owned window.')
                before = win32gui.GetCursorPos()
                try:
                    win32api.SetCursorPos(point)
                    session.mini.verify()
                    if win32gui.WindowFromPoint(point) != target:
                        raise RuntimeError('Owned Mini mouse target changed.')
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    session.mini_page.wait_for_timeout(300)
                    session.report['mouse_activation'] = {'point': list(point), 'foreground_matches_mini': win32gui.GetForegroundWindow() == session.mini.hwnd, 'input_layer': 'Actual mouse click on verified owned Mini inert header'}
                finally:
                    if win32gui.GetCursorPos() == point and win32gui.GetForegroundWindow() == session.mini.hwnd:
                        win32api.SetCursorPos(before)
            try:
                session.report['native_focus'] = session.native('focus', mini=True)
            except Exception as exc:
                session.report['native_focus_error'] = {'type': type(exc).__name__, 'message': str(exc)}
            session.report['keyboard_input_layer'] = 'CDP keyboard on actual native Mini document; native focus result recorded separately'
            session.mini_page.locator('[data-mini-input]').focus()
            session.mini_page.keyboard.press('Shift+Tab')
            session.mini_page.wait_for_timeout(400)
            session.report['mini_keyboard'] = {'dom': session.dom(mini=True), 'screenshot': session.capture('mini-keyboard-focus', mini=True)}
            session.report['mini_minimize'] = session.native('minimize', mini=True)
            session.report['mini_restore'] = session.native('restore', mini=True)
            try:
                session.report['restored_native_focus'] = session.native('focus', mini=True)
            except Exception as exc:
                session.report['restored_native_focus_error'] = {'type': type(exc).__name__, 'message': str(exc)}
            session.mini_page.wait_for_timeout(1200)
            session.native('resize', mini=True, size=[621, 560])
            session.mini_page.wait_for_timeout(1200)
            session.report['mini_restored_pixels'] = session.capture('mini-restored', mini=True)
        session.report['bridge_checks'] = []
        for method, arguments in [('get_state', []), ('pin', [True]), ('pin', [False]), ('expand', [])]:
            session.report['bridge_checks'].append(session.execute({'id': 'mini-' + method + '-' + str(arguments), 'action': 'mini_bridge', 'view': 'mini', 'method': method, 'arguments': arguments}))
        session.page.wait_for_timeout(800)
        session.report['after_expand'] = {'main': session.window_state(session.main), 'mini': session.window_state(session.mini), 'dom': session.dom()}
        session.report['readback'] = authenticated_readback(session, '/api/workspace')
        session.report['complete'] = True
        session.save()
if __name__ == '__main__':
    main()
