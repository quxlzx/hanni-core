"""Real native Mini -> existing configured controller -> read-only RAM tool.

Uses the original text launcher, local cached model and isolated temporary data.
No microphone, TTS, provider, node, file write or system-control tool is requested.
Native frames are evidence of integration, not an independent visual grade.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
import psutil
import win32api
import win32con
import win32gui
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts' / 'desktop_review'))
from capture_native import frame_capture, wait_window
from desktop.main import request_json


def free_port():
    with socket.socket() as connection:
        connection.bind(('127.0.0.1', 0))
        return connection.getsockname()[1]


def model_pids():
    return {p.pid for p in psutil.process_iter(['name'])
            if (p.info['name'] or '').lower() == 'llama-server.exe'}


def owns_listener(process, port):
    try:
        tree = {process.pid, *(p.pid for p in psutil.Process(process.pid).children(recursive=True))}
    except psutil.NoSuchProcess:
        return False
    return any(connection.pid in tree and connection.status == psutil.CONN_LISTEN
               and connection.laddr.port == port for connection in psutil.net_connections('tcp'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, default=ROOT / 'dist/HANNI OS/HANNI OS.exe')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/hanni-phase12-review/live-controller')
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    original_models = model_pids()
    result = {'passed': False, 'checks': [], 'original_model_pids': sorted(original_models),
              'exe_sha256': hashlib.sha256(args.exe.read_bytes()).hexdigest(),
              'disclosure': 'Real packaged native Mini, original launcher/text controller, configured local model and actual process-memory tool. Isolated temporary databases; no microphone, TTS or remote/node action. Not a voice or independent visual score.'}
    controller = app = hwnd = mini_hwnd = None
    port, debug_port = free_port(), free_port()
    url, title = f'http://127.0.0.1:{port}', 'HANNI OS Real Controller Check'
    with tempfile.TemporaryDirectory(prefix='hanni-real-controller-') as temporary:
        environment = os.environ.copy()
        environment.update(HANNI_DATA_DIR=temporary, HANNI_CHAT_HISTORY='session',
                           HANNI_LAYA_SHADOW_ENABLED='0')
        with (args.output / 'controller.log').open('w', encoding='utf-8') as log:
            try:
                controller = subprocess.Popen([sys.executable, '-m', 'hanni.dashboard.launcher',
                    '--no-browser', '--text', '--port', str(port), '--data-dir', temporary,
                    '--startup-timeout', '180'], cwd=ROOT, env=environment,
                    stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                result['controller_pid'] = controller.pid
                deadline, snapshot = time.monotonic() + 190, None
                while time.monotonic() < deadline:
                    if controller.poll() is not None:
                        raise RuntimeError('Original controller exited before readiness; see isolated log.')
                    if owns_listener(controller, port):
                        try:
                            snapshot = request_json(url, '/api/chat', timeout=3)
                            if snapshot.get('ready'):
                                break
                        except (OSError, ValueError):
                            pass
                    time.sleep(.25)
                assert snapshot and snapshot.get('ready'), 'Original controller did not become ready.'
                result['checks'].append('Existing configured controller and local model became ready')
                app = subprocess.Popen([str(args.exe.resolve()), '--url', url, '--attach-only',
                    '--state-dir', str(Path(temporary) / 'native'), '--debug-port', str(debug_port),
                    '--title', title], cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
                hwnd, mini_hwnd = wait_window(title), wait_window('HANNI Mini')
                with sync_playwright() as playwright:
                    browser = None
                    for _ in range(100):
                        try:
                            browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{debug_port}', timeout=1000)
                            break
                        except Exception:
                            time.sleep(.1)
                    assert browser, 'Native WebView debug connection unavailable.'
                    browser.new_browser_cdp_session().send('Target.getTargets')
                    page = browser.contexts[0].pages[0]
                    page.wait_for_timeout(1500)
                    pages = [p for context in browser.contexts for p in context.pages]
                    main_page = next(p for p in pages if p.url.startswith(url) and '?view=mini' not in p.url)
                    mini = next(p for p in pages if p.url.startswith(url) and '?view=mini' in p.url)
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    for key in (win32con.VK_CONTROL, win32con.VK_SHIFT, win32con.VK_SPACE):
                        win32api.keybd_event(key, 0, 0, 0)
                    main_page.wait_for_timeout(80)
                    for key in (win32con.VK_SPACE, win32con.VK_SHIFT, win32con.VK_CONTROL):
                        win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
                    mini.wait_for_timeout(250)
                    assert win32gui.IsWindowVisible(mini_hwnd), 'Native Mini did not open.'
                    text = 'What is using the most RAM right now? Show the current top memory processes.'
                    mini.get_by_role('textbox', name='Message HANNI', exact=True).fill(text)
                    mini.get_by_role('button', name='Send', exact=True).click()
                    deadline = time.monotonic() + 150
                    while time.monotonic() < deadline:
                        snapshot = request_json(url, '/api/chat', timeout=4)
                        replies = [m for m in snapshot['messages'] if m['role'] == 'assistant' and m['status'] == 'complete' and m['content'].strip()]
                        if replies:
                            break
                        mini.wait_for_timeout(200)
                    assert replies, 'Existing local controller did not complete the Mini request.'
                    audit = Path(temporary) / 'logs/tool_audit.jsonl'
                    rows = [json.loads(line) for line in audit.read_text(encoding='utf-8').splitlines()]
                    completed = [row['tool'] for row in rows if row.get('ok')]
                    result['completed_tools'] = completed
                    assert 'process.top_memory' in completed, f'No original process-memory tool execution: {completed}'
                    assert all(row['tool'] == 'process.top_memory' for row in rows), 'Unexpected additional tool request; inspect isolated audit.'
                    users = [m for m in snapshot['messages'] if m['role'] == 'user']
                    assert len(users) == 1 and users[0]['content'] == text
                    expect(mini.locator('.mini-message').filter(has_text=replies[-1]['content'])).to_be_visible(timeout=10000)
                    frame_capture(mini_hwnd, args.output / 'mini-real-controller-native.png')
                    mini.get_by_role('button', name='Expand', exact=True).click()
                    expect(main_page.locator('.chat-message.assistant p')).to_contain_text(replies[-1]['content'], timeout=15000)
                    frame_capture(hwnd, args.output / 'conversation-real-controller-native.png')
                    result['checks'].extend(['One native Mini submission through original ChatHub/controller',
                        'Original read-only process.top_memory capability executed with actual OS data',
                        'Real local-model reply rendered in Mini and expanded Conversation'])
                    result['completed_tools'] = completed
                    result['reply_characters'] = len(replies[-1]['content'])
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    app.wait(timeout=30)
                    assert controller.poll() is None, 'Closing attached native app stopped its controller.'
                    result['checks'].append('Attached controller survives native close')
                if owns_listener(controller, port):
                    request_json(url, '/api/shutdown', token=snapshot['token'], body={})
                controller.wait(timeout=45)
                assert model_pids() == original_models, 'Owned-model cleanup changed the external model set.'
                result['checks'].append('Original shutdown cleans owned controller/model and preserves external models')
                result['passed'] = True
            except Exception as error:
                result['error'] = repr(error)
                (args.output / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            finally:
                if app and app.poll() is None:
                    if hwnd and win32gui.IsWindow(hwnd):
                        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                        try: app.wait(timeout=30)
                        except subprocess.TimeoutExpired: pass
                    if app.poll() is None:
                        subprocess.run(['taskkill', '/PID', str(app.pid), '/T', '/F'], capture_output=True)
                if controller and controller.poll() is None:
                    if owns_listener(controller, port):
                        try:
                            current = request_json(url, '/api/chat')
                            request_json(url, '/api/shutdown', token=current['token'], body={})
                            controller.wait(timeout=45)
                        except (OSError, ValueError, subprocess.TimeoutExpired):
                            pass
                    if controller.poll() is None:
                        subprocess.run(['taskkill', '/PID', str(controller.pid), '/T', '/F'], capture_output=True)
                result['final_model_pids'] = sorted(model_pids())
                (args.output / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
