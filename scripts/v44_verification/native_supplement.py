"""Read-only original native inventory and disabled cluster-control review.

No model dispatch, power request, terminal launch, or setting mutation occurs.
Only exact receipt-owned native application cleanup is performed.
"""
import ctypes
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import psutil
import win32con
import win32gui
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.v43_verification.capture_native import capture, wait_window

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    private = (ROOT/'data/v44-verification').resolve()
    session, out = args.session.resolve(), args.output.resolve()
    assert session.is_relative_to(private) and out.is_relative_to(private) and not out.exists()
    ready = json.loads((session/'ready.json').read_text())
    assert psutil.Process(ready['helper_pid']).create_time() == ready['helper_create_time']
    out.mkdir(parents=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    title = 'HANNI OS V4.4 Read-only Supplement'
    process = subprocess.Popen([str(ROOT/'dist/HANNI OS/HANNI OS.exe'), '--url', ready['url'],
        '--attach-only', '--state-dir', str(out/'native-state'), '--debug-port', str(port), '--title', title],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    created = psutil.Process(process.pid).create_time()
    report = {'pid': process.pid, 'create_time': created, 'started_at': time.time(),
              'screenshots': [], 'no_model_dispatch': True, 'no_power_or_terminal_dispatch': True, 'complete': False}
    hwnd = None
    try:
        hwnd = wait_window(title, process.pid)
        with sync_playwright() as playwright:
            for attempt in range(100):
                try:
                    browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{port}', timeout=1000)
                    break
                except Exception:
                    time.sleep(.2)
            page = None
            for attempt in range(100):
                matches = [p for c in browser.contexts for p in c.pages if p.url.startswith(ready['url'])]
                if matches:
                    page = matches[0]
                    break
                browser.new_browser_cdp_session().send('Target.getTargets')
                time.sleep(.1)
            assert page is not None
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 8, 32, 1366, 768, 0)
            page.evaluate("location.hash='models'")
            expect(page.get_by_role('heading', name='Model Intelligence Lab', exact=True)).to_be_visible()
            page.get_by_role('button', name='Overview', exact=True).click()
            page.wait_for_timeout(600)
            report['screenshots'].append(capture(hwnd, process.pid, out/'actual-inventory-native.png'))
            page.evaluate("location.hash='cluster'")
            page.get_by_role('button', name='HANNI node', exact=True).click()
            page.wait_for_timeout(600)
            for name in ('Reboot HANNI', 'Sleep HANNI'):
                assert page.get_by_role('button', name=name, exact=True).is_disabled()
            report['screenshots'].append(capture(hwnd, process.pid, out/'actual-hanni-controls-native.png'))
            cluster = page.request.get(ready['url']+'/api/cluster').json()
            assert all(n.get('metrics') is None for n in cluster['nodes'])
            assert all(not n['power']['actions'][a]['enabled'] for n in cluster['nodes'] for a in ('reboot','sleep'))
            assert all(not n['terminal']['enabled'] for n in cluster['nodes'])
            (out/'actual-cluster-projection.json').write_text(json.dumps(cluster, indent=2), encoding='utf8')
            report['controls_disabled_without_fresh_connection'] = True
            report['complete'] = True
            browser.close()
    except Exception as exc:
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        if process.poll() is None:
            assert psutil.Process(process.pid).create_time() == created
            if hwnd: win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            try: process.wait(15)
            except subprocess.TimeoutExpired:
                assert psutil.Process(process.pid).create_time() == created
                process.terminate(); process.wait(10)
        report['owned_native_process_closed'] = process.poll() is not None
        report['finished_at'] = time.time()
        (out/'results.json').write_text(json.dumps(report, indent=2), encoding='utf8')
        print(json.dumps({'complete': report['complete'], 'owned_native_process_closed': report['owned_native_process_closed']}))

if __name__ == '__main__': main()
