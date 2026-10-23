"""Review the actual Windows HANNI client against a live bounded lab server.

CDP drives the real WebView2 page. Screenshots come from Windows ImageGrab of
the PID-verified foreground HANNI window, never an entire desktop or fixture PNG.
"""
from __future__ import annotations

import argparse
import ctypes
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

import psutil
import win32api
import win32con
import win32gui
import win32process
from PIL import ImageGrab
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.workflows.verification import parse_evidence_json
from hanni.evals.model_lab import digest


def wait_window(title, pid, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = []
        def collect(hwnd, _):
            if (win32gui.GetWindowText(hwnd) == title
                    and win32process.GetWindowThreadProcessId(hwnd)[1] == pid):
                found.append(hwnd)
        win32gui.EnumWindows(collect, None)
        if found:
            return found[0]
        time.sleep(.2)
    raise RuntimeError('The owned native HANNI window was not created.')


def capture(hwnd, pid, path):
    assert win32process.GetWindowThreadProcessId(hwnd)[1] == pid
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    foreground = win32gui.GetForegroundWindow()
    own_thread = win32api.GetCurrentThreadId()
    other_thread = win32process.GetWindowThreadProcessId(foreground)[0] if foreground else own_thread
    attached = other_thread != own_thread
    try:
        if attached:
            ctypes.windll.user32.AttachThreadInput(own_thread, other_thread, True)
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
    finally:
        if attached:
            ctypes.windll.user32.AttachThreadInput(own_thread, other_thread, False)
    time.sleep(.2)
    assert win32gui.GetForegroundWindow() == hwnd, 'Refusing capture of an occluded application.'
    client = win32gui.GetClientRect(hwnd)
    left, top = win32gui.ClientToScreen(hwnd, (client[0], client[1]))
    right, bottom = win32gui.ClientToScreen(hwnd, (client[2], client[3]))
    rect = (left, top, right, bottom)
    width, height = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
    assert 0 <= rect[0] < rect[2] <= width and 0 <= rect[1] < rect[3] <= height
    ImageGrab.grab(bbox=rect).save(path)
    return {'file': path.name, 'window_rect': list(rect),
            'capture_scope': 'Owned native client surface only; OS frame/shadow excluded to prevent unrelated desktop pixels.',
            'native_window': True, 'pid_verified': True, 'foreground_verified': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--exe', type=Path, default=ROOT / 'dist/HANNI OS/HANNI OS.exe')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--reuse-native-proof', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / 'desktop'))
    from main import validate_url
    url = validate_url(args.url)
    output = args.output.resolve()
    assert output.is_relative_to((ROOT / 'data/v43-verification').resolve()) and not output.exists()
    output.mkdir(parents=True)
    campaign = args.campaign.resolve()
    if args.reuse_native_proof:
        args.reuse_native_proof = args.reuse_native_proof.resolve()
        assert args.reuse_native_proof.is_relative_to((ROOT / 'data/v43-verification').resolve())
    assert campaign.is_relative_to((ROOT / 'data/v43-verification').resolve())
    live = json.loads((campaign / 'results.json').read_text(encoding='utf8'))
    assert live['real_model_campaign'] is True
    actual_runs = live['runs']
    file_run = next(row for row in actual_runs if row['suite_id'] == 'file-read-development')
    structured_runs = [row for row in actual_runs if row['suite_id'] == 'structured-development'][:2]
    title = 'HANNI OS Model Lab Independent Review'
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        debug_port = probe.getsockname()[1]
    command = [str(args.exe.resolve()), '--url', url, '--attach-only',
               '--state-dir', str(output / 'native-state'), '--debug-port', str(debug_port), '--title', title]
    log = (output / 'native-launch.log').open('w', encoding='utf8')
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    created = psutil.Process(process.pid).create_time()
    result = {'native_app_reviewed': False, 'headless': False,
              'disclosure': 'Actual HANNI Windows WebView2 client and original bounded lab server; persisted live run data. Any UI fixture is separately disclosed.',
              'screenshots': [], 'checks': [], 'javascript_errors': [], 'external_requests': [],
              'dpi': ctypes.windll.user32.GetDpiForSystem(),
              'physical_screen': [win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)]}
    hwnd = None
    try:
        hwnd = wait_window(title, process.pid)
        result['native_window_class'] = win32gui.GetClassName(hwnd)
        with sync_playwright() as playwright:
            browser = None
            for _ in range(100):
                try:
                    browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{debug_port}', timeout=1000)
                    break
                except Exception:
                    time.sleep(.2)
            assert browser is not None, 'Owned WebView2 CDP did not become available.'
            page = None
            for _ in range(100):
                pages = [p for context in browser.contexts for p in context.pages]
                matches = [p for p in pages if p.url.startswith(url) and '?view=mini' not in p.url]
                if matches:
                    page = matches[0]
                    break
                if pages:
                    pages[0].wait_for_timeout(100)
                else:
                    browser.new_browser_cdp_session().send('Target.getTargets')
            assert page is not None, 'Owned HANNI document did not connect to the lab server.'
            downloads = output / 'downloads'
            downloads.mkdir()
            browser.new_browser_cdp_session().send('Browser.setDownloadBehavior', {
                'behavior': 'allow', 'downloadPath': str(downloads), 'eventsEnabled': True})
            page.on('pageerror', lambda error: result['javascript_errors'].append(str(error)))
            page.on('request', lambda request: result['external_requests'].append(request.url)
                    if request.url.startswith(('http:', 'https:')) and not request.url.startswith(url) else None)
            page.evaluate("location.hash='models'")
            expect(page.get_by_role('heading', name='Model Intelligence Lab', exact=True)).to_be_visible(timeout=30000)
            page.wait_for_timeout(800)
            result['native_app_reviewed'] = True
            for width, height in [(1440, 900), (1366, 768), (900, 650)]:
                screen_width, screen_height = result['physical_screen']
                if width + 16 > screen_width or height + 48 > screen_height:
                    continue
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 8, 32, width, height, 0)
                page.wait_for_timeout(400)
                geometry = page.evaluate('({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth})')
                result['checks'].append({'name': f'No document overflow at native {width}x{height}',
                                         'passed': geometry['scrollWidth'] <= geometry['width'] + 1})
                item = capture(hwnd, process.pid, output / f'model-lab-{width}x{height}-native.png')
                item['viewport'] = geometry
                result['screenshots'].append(item)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 8, 32, 1366, 768, 0)
            page.wait_for_timeout(350)
            page.get_by_role('button', name='Benchmark runner', exact=True).click()
            expect(page.get_by_label('Benchmark suite', exact=True)).to_be_visible()
            page.get_by_label('Cases', exact=True).fill('0')
            assert page.get_by_role('button', name='Start benchmark', exact=True).is_disabled()
            page.get_by_label('Cases', exact=True).fill('1')
            page.get_by_label('Benchmark suite', exact=True).select_option('structured-development')
            page.get_by_label('Repetitions', exact=True).fill('3')
            expect(page.get_by_role('button', name='Start benchmark', exact=True)).to_be_enabled()
            if args.reuse_native_proof:
                prior = json.loads((args.reuse_native_proof / 'results.json').read_text(encoding='utf8'))
                assert prior['passed'] and prior['native_app_reviewed'] and prior['owned_native_process_closed']
                native_run = {'id': prior['native_ui_run_id']}
                result['reuse_native_start_proof'] = str(args.reuse_native_proof.relative_to(ROOT))
                page.get_by_role('button', name='Results', exact=False).filter(has_text='Results').first.click()
                page.get_by_label('Search benchmark history', exact=True).fill(native_run['id'])
                expect(page.locator('.lab-history tbody tr')).to_have_count(1)
                page.locator('.lab-history tbody tr').get_by_role('button', name='Inspect', exact=True).click()
                expect(page.locator('.lab-case-list button')).to_have_count(3)
                page.get_by_label('Search benchmark history', exact=True).fill('')
                page.get_by_role('button', name='Benchmark runner', exact=True).click()
            else:
                with page.expect_response(lambda response: response.url == url + '/api/model-lab' and response.request.method == 'POST') as accepted:
                    page.get_by_role('button', name='Start benchmark', exact=True).click()
                native_run = accepted.value.json()
                assert accepted.value.status == 200
                expect(page.get_by_text('Benchmark started. Progress reflects committed cases.', exact=True)).to_be_visible(timeout=10000)
            result['native_ui_run_id'] = native_run['id']
            expect(page.get_by_text('3 / 3 cases saved', exact=True)).to_be_visible(timeout=120000)
            session_token = page.request.get(url + '/api/chat?before=1').json()['token']
            saved = page.request.get(url + '/api/model-lab/export/' + native_run['id'], headers={'X-Hanni-Token': session_token}).json()
            (output / 'native-ui-live-export.json').write_text(json.dumps(saved, indent=2), encoding='utf8')
            assert saved['run']['status'] == 'completed' and len(saved['results']) == 3
            for case in saved['results']:
                assert case['real_inference'] is True and case['inference']
                assert parse_evidence_json(case['final_answer']) == {'serial': 8427, 'available': False}
                assert case['passed'] is True
            result['native_ui_run_summary'] = saved['run']['summary']
            result['checks'].append({'name': ('Retained prior native Start proof: ' if args.reuse_native_proof else '') + 'Native Start benchmark runs and persists three genuine primary responses', 'passed': True})
            result['screenshots'].append(capture(hwnd, process.pid, output / 'runner-completed-native.png'))
            page.get_by_role('button', name='Inspect results', exact=True).click()
            expect(page.get_by_role('region', name='Results explorer', exact=True)).to_be_visible()
            result['checks'].append({'name': 'Native runner result navigation', 'passed': True})
            page.get_by_label('Search benchmark history', exact=True).fill(file_run['id'])
            expect(page.locator('.lab-history tbody tr')).to_have_count(1)
            page.locator('.lab-history tbody tr').get_by_role('button', name='Inspect', exact=True).click()
            expect(page.locator('.lab-case-list button')).to_have_count(file_run['completed'])
            page.locator('.lab-case-list button').first.click()
            expect(page.locator('.lab-case-detail')).to_contain_text('coral-8427')
            expect(page.locator('.lab-case-detail')).to_contain_text('Verified task success')
            page.get_by_text('Tool calls and execution receipts', exact=True).click()
            expect(page.locator('.lab-case-detail')).to_contain_text('VERIFIED')
            page.locator('.lab-results').scroll_into_view_if_needed()
            result['screenshots'].append(capture(hwnd, process.pid, output / 'verified-file-results-native.png'))
            result['checks'].append({'name': 'Genuine persisted original VERIFIED file receipt and actual final response visible', 'passed': True})
            page.get_by_label('Filter case outcome', exact=True).select_option('failed')
            expect(page.locator('.lab-case-list button')).to_have_count(0)
            page.get_by_label('Filter case outcome', exact=True).select_option('passed')
            expect(page.locator('.lab-case-list button')).to_have_count(file_run['completed'])
            with page.expect_download(timeout=15000) as downloading:
                page.get_by_role('button', name='Export JSON', exact=True).click()
            download = downloading.value
            result['download_failure'] = download.failure()
            result['download_suggested_filename'] = download.suggested_filename
            actual_download = downloads / f"hanni-model-lab-{file_run['id']}.json"
            assert actual_download.is_file() and actual_download.stat().st_size > 0, 'The original named native export did not complete.'
            downloaded = json.loads(actual_download.read_text(encoding='utf8'))
            assert downloaded['run']['id'] == file_run['id'] and len(downloaded['results']) == file_run['completed']
            assert downloaded['export_complete'] is True
            assert digest(downloaded['run']['configuration']) == downloaded['run']['configuration_sha256'], 'Native exported configuration hash mismatch.'
            assert digest(downloaded['run']['protocol']) == downloaded['run']['protocol_sha256'], 'Native exported protocol hash mismatch.'
            for case in downloaded['results']:
                original = dict(case)
                checksum = original.pop('evidence_sha256')
                assert digest(original) == checksum, 'Native exported case hash mismatch.'
            result['download_case_hashes_verified'] = True
            result['download_configuration_hash_verified'] = True
            result['download_protocol_hash_verified'] = True
            result['download_suggested_filename'] = download.suggested_filename
            capture(hwnd, process.pid, output / 'native-export-confirmation.png')
            assert win32gui.GetForegroundWindow() == hwnd
            win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
            win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)
            # WebView2's native Downloads flyout is outside the DOM. Close its
            # observed upper-right X only inside the exact owned client surface.
            client = win32gui.GetClientRect(hwnd)
            position = win32gui.ClientToScreen(hwnd, (client[2] - 60, 72))
            assert win32process.GetWindowThreadProcessId(hwnd)[1] == process.pid
            assert win32gui.GetForegroundWindow() == hwnd
            win32api.SetCursorPos(position)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            page.wait_for_timeout(250)
            expect(page.get_by_text(f"Complete redacted JSON export prepared: {file_run['completed']} persisted cases.", exact=True)).to_be_visible(timeout=10000)
            result['checks'].append({'name': 'Native history search, case filtering and real export control', 'passed': True})
            page.get_by_label('Search benchmark history', exact=True).fill('no-such-independent-run-94821')
            expect(page.get_by_text('No runs match these filters.', exact=True)).to_be_visible()
            page.get_by_label('Search benchmark history', exact=True).fill('')
            page.get_by_role('button', name='Compare', exact=True).click()
            for run in structured_runs:
                page.get_by_label('Compare run ' + run['id'], exact=True).check()
            page.get_by_role('button', name='Compare selected runs', exact=True).click()
            expect(page.get_by_text('Comparable completed workloads. Model, hardware and backend differences remain visible below.', exact=True)).to_be_visible(timeout=10000)
            page.get_by_role('region', name='Model comparison', exact=True).scroll_into_view_if_needed()
            result['screenshots'].append(capture(hwnd, process.pid, output / 'actual-comparison-native.png'))
            result['checks'].append({'name': 'Native comparison reflects matching persisted actual conditions and explicit units', 'passed': True})
            page.get_by_role('button', name='Routing insights', exact=True).click()
            page.locator('.lab-routing').scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            result['screenshots'].append(capture(hwnd, process.pid, output / 'routing-insights-native.png'))
            result['checks'].append({'name': 'Original adaptive routing insights render alongside explicit separate development scores', 'passed': True})
            page.get_by_role('button', name='Benchmark runner', exact=True).click()
            def outage(route):
                if route.request.method == 'GET':
                    route.fulfill(status=503, content_type='application/json', body='{"error":"Controlled native review connection outage"}')
                else:
                    route.continue_()
            page.route('**/api/model-lab**', outage)
            expect(page.get_by_role('alert')).to_contain_text('Controlled native review connection outage', timeout=10000)
            assert page.get_by_role('button', name='Start benchmark', exact=True).is_disabled()
            result['screenshots'].append(capture(hwnd, process.pid, output / 'disclosed-outage-fixture-native.png'))
            result['checks'].append({'name': 'Disclosed native transport-outage fixture disables new benchmark dispatch', 'passed': True})
            page.unroute('**/api/model-lab**', outage)
            expect(page.get_by_role('alert')).to_have_count(0, timeout=10000)
            result['checks'].append({'name': 'Native API reconnect recovers controls without a page reload', 'passed': True})
            result['visible_text'] = page.locator('body').inner_text()
            result['font_family'] = page.locator('body').evaluate('element=>getComputedStyle(element).fontFamily')
            result['checks'].append({'name': 'Original local Geist typography', 'passed': 'Geist' in result['font_family']})
            result['checks'].append({'name': 'No JavaScript errors', 'passed': not result['javascript_errors']})
            result['checks'].append({'name': 'No external HTTP requests', 'passed': not result['external_requests']})
            result['passed'] = all(check['passed'] for check in result['checks'])
            browser.close()
    except Exception as error:
        result.update(passed=False, blocker=type(error).__name__ + ': ' + str(error))
        import traceback
        result['verifier_error_locations'] = [{'file': Path(frame.filename).name, 'line': frame.lineno}
                                              for frame in traceback.extract_tb(error.__traceback__)]
    finally:
        if hwnd is not None and win32gui.IsWindow(hwnd):
            assert win32process.GetWindowThreadProcessId(hwnd)[1] == process.pid
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            owned = psutil.Process(process.pid)
            assert owned.create_time() == created and title in owned.cmdline()
            process.terminate()
            process.wait(timeout=5)
        result['owned_native_process_closed'] = process.poll() is not None
        log.close()
        (output / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({key: result.get(key) for key in (
        'passed', 'native_app_reviewed', 'blocker', 'owned_native_process_closed', 'checks')}))
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
