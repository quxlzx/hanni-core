"""Independent framed native review matrix for explicitly selected Phase screens.

This is a verification harness, not a feature implementation. Telemetry and
chat use ReviewFixture and must never be reported as genuine live operation.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
import win32con
import win32gui
from playwright.sync_api import sync_playwright, expect

from capture_native import ROOT, SIZES, frame_capture, wait_window
from fixture import ReviewFixture


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--screen', action='append', required=True,
                        help='HASH=VISIBLE_CSS_SELECTOR, repeated for every primary screen')
    parser.add_argument('--workspace-fixture', action='store_true',
                        help='Seed real isolated Phase workspace records through registry-gated HTTP adapters')
    args = parser.parse_args()
    screens = []
    for item in args.screen:
        route, separator, selector = item.partition('=')
        if not separator or not route or not selector or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in route):
            parser.error('--screen requires a simple route and a visible CSS selector')
        screens.append((route, selector))
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    result = {
        'passed': False, 'visual_score': None,
        'disclosure': 'Actual foreground native executable frames; isolated synthetic telemetry/chat/device fixture. No model, microphone, real SSH, power, terminal, screen capture or provider operation.',
        'dpi': ctypes.windll.user32.GetDpiForSystem(), 'screens': screens,
        'screenshots': [], 'errors': [], 'javascript_errors': [], 'external_requests': [],
        'artifact_sha256': {
            'exe': digest(args.exe.resolve()),
            'app.js': digest(ROOT/'src/hanni/dashboard/static/app.js'),
            'style.css': digest(ROOT/'src/hanni/dashboard/static/style.css'),
        },
    }
    title = 'HANNI OS Independent Phase Review'
    process = None
    factory=ReviewFixture
    if args.workspace_fixture:
        from phase_fixture import PhaseReviewFixture
        factory=PhaseReviewFixture
    with factory() as fixture:
        if args.workspace_fixture:
            result['workspace_fixture_disclosure']=fixture.workspace_seed_disclosure
            result['workspace_seed_operations']=fixture.seeded
            result['disclosure']='Actual foreground native executable frames; real isolated registry-gated workspace records and original MemoryStore with synthetic review content; synthetic telemetry/device/model samples and ChatHub reply transport. Voice inactive/unbound, Google disconnected, screen/vision unavailable. No model, microphone, SSH, power, terminal, screen capture or remote provider operation.'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            debug_port = sock.getsockname()[1]
        log = (args.output/'native-launch.log').open('w', encoding='utf-8')
        try:
            process = subprocess.Popen([
                str(args.exe.resolve()), '--url', fixture.url, '--attach-only',
                '--state-dir', str(args.output/'isolated-native-state'),
                '--debug-port', str(debug_port), '--title', title,
            ], stdout=log, stderr=subprocess.STDOUT)
            hwnd = wait_window(title)
            with sync_playwright() as playwright:
                browser = None
                for _ in range(100):
                    try:
                        browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{debug_port}', timeout=1000)
                        break
                    except Exception:
                        time.sleep(.1)
                if browser is None:
                    raise RuntimeError('Actual native WebView CDP unavailable')
                page = None
                for _ in range(300):
                    pages = [p for context in browser.contexts for p in context.pages]
                    matches = [p for p in pages if p.url.startswith(fixture.url) and '?view=mini' not in p.url]
                    if matches:
                        page = matches[0]
                        break
                    if pages:
                        pages[0].wait_for_timeout(100)
                    else:
                        browser.new_browser_cdp_session().send('Target.getTargets')
                if page is None:
                    frame_capture(hwnd, args.output/'startup-failure-native.png')
                    raise RuntimeError('Actual native main page did not load')
                page.on('pageerror', lambda error: result['javascript_errors'].append(str(error)))
                page.on('request', lambda request: result['external_requests'].append(request.url)
                        if request.url.startswith(('http:', 'https:')) and not request.url.startswith(fixture.url) else None)
                for width, height in SIZES:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetWindowPos(hwnd, 0, 0, 0, width, height, win32con.SWP_NOZORDER)
                    page.wait_for_timeout(250)
                    for route, selector in screens:
                        page.evaluate('(route) => { location.hash = route; }', route)
                        expect(page.locator(selector)).to_be_visible(timeout=20000)
                        page.wait_for_timeout(700)
                        layout = page.evaluate('''() => ({
                            inner_width:innerWidth, inner_height:innerHeight,
                            document_width:document.documentElement.scrollWidth,
                            viewport_width:document.documentElement.clientWidth,
                            active_route:location.hash,
                            body_text:document.body.innerText.slice(0,24000)
                        })''')
                        capture = frame_capture(hwnd, args.output/f'{route}-{width}x{height}-native.png')
                        capture.update(screen=route, layout=layout, dpi=ctypes.windll.user32.GetDpiForWindow(hwnd))
                        result['screenshots'].append(capture)
                        if capture['window_size'] != [width, height]:
                            result['errors'].append(f'{route}: physical size mismatch {capture["window_size"]}')
                        if layout['document_width'] > layout['viewport_width'] + 1:
                            result['errors'].append(f'{route} {width}x{height}: document horizontal overflow')
                if fixture.writes:
                    result['errors'].append(f'Capture unexpectedly invoked write handlers: {fixture.writes}')
                result['passed'] = not (result['errors'] or result['javascript_errors'] or result['external_requests'])
                result['scoring_status'] = 'Screenshots require independent visual inspection; harness success is not visual or feature acceptance.'
        except Exception as error:
            result['errors'].append(f'{type(error).__name__}: {error}')
        finally:
            if process is not None and process.poll() is None:
                # Only the exact launched review process tree is terminated.
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    result['errors'].append('Review executable did not terminate')
            log.close()
            result['passed'] = result['passed'] and not result['errors']
            (args.output/'capture-results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'screenshots':len(result['screenshots']), 'errors':result['errors']}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
