"""Bounded public development proof of the original safe Application menu row.

The reference is the independently viewed owned popup, not a private final oracle.
Never invoke a callback, select another row, or capture another application's pixels.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from desktop.main import request_json
from .development_smoke import backend_link_valid
from .final_runner import ROOT, process_identity, sha, write
VIEWED_POPUP_SHA256 = '132d40c8505b51b104a4d8937fb52434eec755998b3448f7f44b1bb20510db07'

def safe_row_point(capture, identity):
    """Only the identical already-viewed owned 125% popup permits a row click."""
    if capture.get('pid') != identity.get('pid') or capture.get('create_time') != identity.get('create_time') or capture.get('method') != 'Win32 PrintWindow PW_RENDERFULLCONTENT' or (capture.get('desktop_pixel_capture') is not False) or (capture.get('dpi') != 120) or (capture.get('image_size') != [199, 112]) or (capture.get('sha256') != VIEWED_POPUP_SHA256) or (not str(capture.get('window_class', '')).startswith('WindowsForms10.Window.')):
        raise ValueError('Safe row lacks matching owned popup pixels and identity; no click permitted')
    rect = capture.get('window_rect')
    if not isinstance(rect, list) or len(rect) != 4 or (not all((type(n) is int for n in rect))) or ([rect[2] - rect[0], rect[3] - rect[1]] != [199, 112]):
        raise ValueError('Safe row popup rectangle changed; no click permitted')
    return (rect[0] + 100, rect[1] + 14)

def run_menu(session):
    import win32api
    import win32con
    import win32gui
    import win32process
    from scripts.campaign8_native.owned_window import OwnedWindow, capture_owned_window
    from scripts.campaign8_native.native_controls import keys
    session.native('resize', size=[1280, 800])
    session.native('focus')
    session.page.wait_for_timeout(350)
    result = {'before_mini': session.window_state(session.mini), 'popup_observations': []}
    started = time.monotonic()
    strips = []
    origin = win32gui.ClientToScreen(session.main.hwnd, (0, 0))
    width = win32gui.GetClientRect(session.main.hwnd)[2]

    def child(hwnd, unused):
        if win32process.GetWindowThreadProcessId(hwnd)[1] != session.identity.pid:
            return
        rect = win32gui.GetWindowRect(hwnd)
        if win32gui.GetClassName(hwnd).startswith('WindowsForms') and win32gui.IsWindowVisible(hwnd) and (0 <= rect[1] - origin[1] <= 4) and (20 <= rect[3] - rect[1] <= 60) and (rect[2] - rect[0] >= width * 0.8):
            strips.append((hwnd, rect))
    win32gui.EnumChildWindows(session.main.hwnd, child, None)
    if len(strips) != 1:
        raise RuntimeError('Original owned menu strip was not uniquely identified')
    hwnd, rect = strips[0]
    opening = win32gui.ClientToScreen(hwnd, (35, (rect[3] - rect[1]) // 2))
    previous_cursor = win32gui.GetCursorPos()

    def click(point, target):
        target.verify()
        foreground = win32gui.GetForegroundWindow()
        hit = win32gui.WindowFromPoint(point)
        if not foreground or win32process.GetWindowThreadProcessId(foreground)[1] != session.identity.pid or win32process.GetWindowThreadProcessId(hit)[1] != session.identity.pid:
            raise RuntimeError('Cursor input lacks exact owned foreground and hit target')
        win32api.SetCursorPos(point)
        target.verify()
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    click(opening, session.main)
    time.sleep(0.3)
    result['single_original_cursor_open'] = list(opening)
    windows = []

    def observe(hwnd, unused):
        if win32process.GetWindowThreadProcessId(hwnd)[1] == session.identity.pid and win32gui.IsWindowVisible(hwnd) and (hwnd not in [session.main.hwnd, session.mini.hwnd]) and win32gui.GetClassName(hwnd).startswith('WindowsForms10.Window.'):
            windows.append(hwnd)
    win32gui.EnumWindows(observe, None)
    matched = []
    for hwnd in windows:
        popup = OwnedWindow(session.identity, hwnd, win32gui.GetWindowText(hwnd), win32gui.GetClassName(hwnd))
        popup.verify()
        capture = capture_owned_window(popup, session.output / 'screenshots' / f'safe-menu-popup-{hwnd}.png')
        result['popup_observations'].append(capture)
        try:
            point = safe_row_point(capture, {'pid': session.identity.pid, 'create_time': session.identity.create_time})
            matched.append((popup, capture, point))
        except ValueError:
            pass
    if len(matched) != 1 or time.monotonic() - started > 25:
        keys(session.main, [win32con.VK_ESCAPE], preserve_owned_foreground=True)
        result['selection_blocked'] = 'Fresh identical owned popup was not unique within the 30-second menu budget'
    else:
        popup, capture, point = matched[0]
        popup.verify()
        if list(win32gui.GetWindowRect(popup.hwnd)) != capture['window_rect'] or win32gui.WindowFromPoint(point) != popup.hwnd:
            raise RuntimeError('Verified popup moved or first-row hit changed; no selection sent')
        click(point, popup)
        result['safe_first_row_cursor_selection'] = {'point': list(point), 'popup_hwnd': popup.hwnd, 'observed_row': 'Open HANNI Mini', 'reference_pixels_sha256': VIEWED_POPUP_SHA256, 'input_layer': 'Actual Windows cursor on original visible menu; no callback invocation'}
        session.page.wait_for_timeout(600)
    result['after_mini'] = session.window_state(session.mini)
    result['actual_Open_Mini_confirmed'] = not result['before_mini']['visible'] and result['after_mini']['visible']
    result['menu_phase_seconds'] = time.monotonic() - started
    result['main_capture'] = session.capture('safe-menu-main')
    if result['after_mini']['visible']:
        result['mini_capture'] = session.capture('safe-menu-opened-mini', mini=True)
    if win32gui.GetCursorPos() in [opening, matched[0][2] if matched else opening] and win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[1] == session.identity.pid:
        win32api.SetCursorPos(previous_cursor)
    return result

def main():
    from scripts.campaign8_native.session import NativeSession
    import psutil
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--native-out', required=True, type=Path)
    args = parser.parse_args()
    output = args.out.resolve()
    native_out = args.native_out.resolve()
    if output.exists() or native_out.exists() or (not output.is_relative_to(ROOT / 'data/campaign8-verifier')) or (not native_out.is_relative_to(ROOT / 'data/campaign8-native')):
        raise ValueError('Fresh independent campaign-owned outputs required')
    output.mkdir(parents=True)
    backend_root = output / 'backend'
    report = {'scope': 'Public DEVELOPMENT safe Application menu reproduction; no private final access or generation', 'sealed_final_access': False, 'errors': [], 'source_before': {p: sha(ROOT / p) for p in ['desktop/main.py', 'src/hanni/dashboard/static/app.js', 'src/hanni/dashboard/static/style.css']}}
    write(output / 'RESULTS.json', report)
    ready = actual = None
    with (output / 'backend.log').open('w', encoding='utf8') as log:
        process = subprocess.Popen([sys.executable, '-X', 'utf8', '-m', 'scripts.campaign8_ui.backend', '--root', str(backend_root), '--timeout', '180'], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        launcher = process_identity(process.pid)
        try:
            deadline = time.monotonic() + 45
            while not (backend_root / 'READY.json').is_file() and time.monotonic() < deadline and (process.poll() is None):
                time.sleep(0.1)
            ready = json.loads((backend_root / 'READY.json').read_text(encoding='utf8'))
            actual = process_identity(ready['pid'])
            if actual['create_time'] != ready['create_time'] or not backend_link_valid(actual, launcher, psutil.Process(ready['pid']).cmdline(), backend_root):
                raise RuntimeError('Original owned backend provenance mismatch')
            with NativeSession(url=ready['url'], output=native_out, maximum_seconds=120) as session:
                report.update(run_menu(session))
                session.report['complete'] = True
            native = json.loads((native_out / 'RESULTS.json').read_text(encoding='utf8'))
            report.update(native_cleanup=native['owned_native_cleanup'], native_receipt_sha256=sha(native_out / 'RESULTS.json'), javascript_errors=native['javascript_errors'], native_HTTP_mutations=sum((x['method'] != 'GET' for x in native['network'])), source_unchanged=all((sha(ROOT / p) == value for p, value in report['source_before'].items())))
        except Exception as error:
            report['errors'].append({'type': type(error).__name__, 'message': str(error)[:600]})
        finally:
            if process.poll() is None:
                if process_identity(process.pid) != launcher:
                    raise RuntimeError('Refusing cleanup of changed owned launcher')
                if ready and actual:
                    if process_identity(ready['pid']) != actual:
                        raise RuntimeError('Refusing cleanup of changed owned backend')
                    token = request_json(ready['url'], '/api/chat?before=1')['token']
                    request_json(ready['url'], '/api/shutdown', body={}, token=token)
                else:
                    process.terminate()
                process.wait(timeout=25)
            report.update(backend_exit_code=process.returncode, backend_closed=(backend_root / 'CLOSED.json').is_file())
            write(output / 'RESULTS.json', report)
    print(json.dumps({'receipt': str(output / 'RESULTS.json'), 'sha256': sha(output / 'RESULTS.json'), 'confirmed': report.get('actual_Open_Mini_confirmed'), 'errors': report['errors'], 'native_cleanup': report.get('native_cleanup'), 'backend_closed': report['backend_closed']}))
if __name__ == '__main__':
    main()
