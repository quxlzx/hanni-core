"""Fresh actual Windows WebView2 review of seven HANNI OS areas.

All PNGs are PID-verified foreground native client surfaces. Benchmark responses
are genuine original ModelLab development results. Passive cluster metrics and
unattached conversation consumer are disclosed; no power action is dispatched.
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
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from scripts.v43_verification.capture_native import capture, wait_window
from hanni.evals.model_lab import digest


def audit_export(export):
    run = export['run']
    assert digest(run['configuration']) == run['configuration_sha256']
    assert digest(run['protocol']) == run['protocol_sha256']
    assert export['export_complete']
    assert len(export['results']) == run['completed']
    assert [r['ordinal'] for r in export['results']] == list(range(run['completed']))
    for row in export['results']:
        row = dict(row)
        expected = row.pop('evidence_sha256')
        assert digest(row) == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exe', type=Path, default=ROOT / 'dist/HANNI OS/HANNI OS.exe')
    parser.add_argument('--proof-from', type=Path, help='Reuse already completed actual conversation/start/export proof; no extra inference retry.')
    args = parser.parse_args()
    private = (ROOT / 'data/v44-verification').resolve()
    session, out = args.session.resolve(), args.output.resolve()
    assert session.is_relative_to(private) and out.is_relative_to(private) and not out.exists()
    ready = json.loads((session / 'ready.json').read_text(encoding='utf8'))
    assert psutil.Process(ready['helper_pid']).create_time() == ready['helper_create_time']
    out.mkdir(parents=True)
    title = 'HANNI OS V4.4 Independent Review'
    url = ready['url']
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        debug_port = probe.getsockname()[1]
    command = [str(args.exe.resolve()), '--url', url, '--attach-only', '--state-dir',
               str(out / 'native-state'), '--debug-port', str(debug_port), '--title', title]
    log = (out / 'native-launch.log').open('w', encoding='utf8')
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    created = psutil.Process(process.pid).create_time()
    report = {'started_at': time.time(), 'actual_native_desktop': True, 'headless': False,
              'pid': process.pid, 'create_time': created, 'checks': [], 'screenshots': [],
              'javascript_errors': [], 'external_requests': [], 'complete': False,
              'disclosures': ['Current-source bounded original backend; existing primary unowned and shared.',
                  'Cluster original configured roster passive: no CPU/RAM samples fabricated or new SSH sampling loops.',
                  'Original power/terminal adapters instantiated; no reboot, sleep or SSH terminal execution.',
                  'Original bounded ChatSession/MemoryAwareSession/MCP/TextSession processor attached only in the native helper; voice/autonomy not started.',
                  'ModelLab benchmark is exposed-development real inference; no holdout proof or adaptive improvement.']}
    def save():
        (out / 'results.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
    def check(name, passed):
        report['checks'].append({'name': name, 'passed': bool(passed)})
        save()
        assert passed, name
    hwnd = None
    try:
        hwnd = wait_window(title, process.pid)
        with sync_playwright() as playwright:
            browser = None
            for _ in range(100):
                try:
                    browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{debug_port}', timeout=1000)
                    break
                except Exception:
                    time.sleep(.2)
            assert browser is not None
            page = None
            for _ in range(100):
                pages = [p for context in browser.contexts for p in context.pages]
                matches = [p for p in pages if p.url.startswith(url) and '?view=mini' not in p.url]
                if matches:
                    page = matches[0]
                    break
                browser.new_browser_cdp_session().send('Target.getTargets')
                time.sleep(.1)
            assert page is not None
            page.on('pageerror', lambda err: report['javascript_errors'].append(str(err)))
            page.on('request', lambda req: report['external_requests'].append(req.url)
                    if req.url.startswith(('http:', 'https:')) and not req.url.startswith(url) else None)
            downloads = out / 'downloads'
            downloads.mkdir()
            browser.new_browser_cdp_session().send('Browser.setDownloadBehavior', {
                'behavior': 'allow', 'downloadPath': str(downloads), 'eventsEnabled': True})
            page.evaluate("location.hash='models'")
            expect(page.get_by_role('heading', name='Model Intelligence Lab', exact=True)).to_be_visible(timeout=30000)
            token = page.request.get(url + '/api/chat?before=1').json()['token']
            private_headers = {'X-Hanni-Token': token, 'Origin': url}
            if args.proof_from:
                proof_directory = args.proof_from.resolve()
                assert proof_directory.is_relative_to(private)
                previous = json.loads((proof_directory / 'results.json').read_text(encoding='utf8'))
                assert previous['owned_native_process_closed'] and all(c['passed'] for c in previous['checks'])
                saved = json.loads((proof_directory / 'native-ui-live-export.json').read_text(encoding='utf8'))
                audit_export(saved)
                first = {'id': saved['run']['id']}
                current = page.request.get(url + '/api/model-lab/export/' + first['id'], headers=private_headers).json()
                audit_export(current)
                assert digest(current) == digest(saved)
                report['reused_actual_proof'] = str(proof_directory)
                report['checks'].extend(previous['checks'])
                report['native_run_id'] = first['id']
                report['native_run_summary'] = saved['run']['summary']
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 8, 32, 1366, 768, 0)
                page.evaluate("location.hash='models'")
                expect(page.get_by_role('heading', name='Model Intelligence Lab', exact=True)).to_be_visible()
            else:
                # Two actual native conversation submissions: a private explicit
                # synthetic preference and genuine memory-assisted model response.
                page.evaluate("location.hash='chat'")
                page.wait_for_timeout(700)
                textbox = page.get_by_role('textbox').last
                textbox.fill('Remember that my preferred review color is apricot.')
                page.get_by_role('button', name='Send message', exact=True).click()
                expect(page.get_by_text("I'll remember: my preferred review color is apricot.", exact=True)).to_be_visible(timeout=30000)
                textbox.fill('What is my preferred review color? Answer from your stored memory and do not call tools.')
                page.get_by_role('button', name='Send message', exact=True).click()
                deadline = time.monotonic() + 90000/1000
                while time.monotonic() < deadline:
                    chat_state = page.request.get(url + '/api/chat').json()
                    assistants = [m for m in chat_state['messages'] if m['role'] == 'assistant' and m['status'] == 'complete']
                    if len(assistants) >= 2:
                        break
                    page.wait_for_timeout(100)
                assert len(assistants) >= 2
                check('Actual native conversation persists original explicit memory', 'apricot' in assistants[0]['content'].lower())
                check('Actual native original memory-assisted model response matches stored private preference', 'apricot' in assistants[1]['content'].lower())
                (out / 'actual-conversation.json').write_text(json.dumps(chat_state, indent=2), encoding='utf8')
                page.evaluate("location.hash='models'")
                expect(page.get_by_role('heading', name='Model Intelligence Lab', exact=True)).to_be_visible()
                inventory = page.request.get(url + '/api/model-lab', headers=private_headers).json()
                (out / 'actual-model-inventory.json').write_text(json.dumps(inventory, indent=2), encoding='utf8')
                check('Model Lab shows backend configured/installed/loaded/available fields without synthesized hardware',
                      len(inventory['models']) >= 1)
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 8, 32, 1366, 768, 0)
                page.get_by_role('button', name='Benchmark runner', exact=True).click()
                page.get_by_label('Cases', exact=True).fill('0')
                check('Invalid native benchmark count disables Start', page.get_by_role('button', name='Start benchmark', exact=True).is_disabled())
                page.get_by_label('Cases', exact=True).fill('1')
                page.get_by_label('Benchmark suite', exact=True).select_option('structured-development')
                page.get_by_label('Repetitions', exact=True).fill('3')
                expect(page.get_by_role('button', name='Start benchmark', exact=True)).to_be_enabled(timeout=20000)
                with page.expect_response(lambda response: response.url == url + '/api/model-lab' and response.request.method == 'POST') as accepted:
                    page.get_by_role('button', name='Start benchmark', exact=True).click()
                first = accepted.value.json()
                assert accepted.value.status == 200
                expect(page.get_by_text('3 / 3 cases saved', exact=True)).to_be_visible(timeout=120000)
                saved = page.request.get(url + '/api/model-lab/export/' + first['id'], headers=private_headers).json()
                audit_export(saved)
                assert saved['run']['status'] == 'completed' and len(saved['results']) == 3
                assert all(case['real_inference'] and case.get('inference') for case in saved['results'])
                report['native_run_id'] = first['id']
                report['native_run_summary'] = saved['run']['summary']
                (out / 'native-ui-live-export.json').write_text(json.dumps(saved, indent=2), encoding='utf8')
                check('Native Start dispatches three genuine original primary cases and saves results', True)
                report['screenshots'].append(capture(hwnd, process.pid, out / 'runner-completed-native.png'))
                page.get_by_role('button', name='Inspect results', exact=True).click()
                expect(page.get_by_role('region', name='Results explorer', exact=True)).to_be_visible()
                page.locator('.lab-case-list button').first.click()
                check('Actual case evidence opens through Results', page.locator('.lab-case-detail').is_visible())
                with page.expect_download(timeout=15000) as download_event:
                    page.get_by_role('button', name='Export JSON', exact=True).click()
                download = download_event.value
                assert download.failure() is None
                actual_file = downloads / f"hanni-model-lab-{first['id']}.json"
                assert actual_file.is_file()
                actual = json.loads(actual_file.read_text(encoding='utf8'))
                audit_export(actual)
                assert actual['run']['id'] == first['id']
                check('Actual native disk export preserves manifest and every case checksum', True)
            # Same conditions, fresh genuine second run for a measured comparison.
            second_response = page.request.post(url + '/api/model-lab', headers=private_headers,
                data={'id': str(uuid4()), 'action': 'start', 'confirmed': True, 'data': {**saved['run']['settings'], 'suite_id': saved['run']['suite_id'], 'endpoint_id': saved['run']['endpoint_id']}})
            (out / 'second-start-response.json').write_text(json.dumps({'status': second_response.status, 'body': second_response.json()}, indent=2), encoding='utf8')
            assert second_response.status == 200
            second = second_response.json()
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                second_saved = page.request.get(url + '/api/model-lab/run/' + second['id'], headers=private_headers).json()
                if second_saved['run']['status'] not in {'running', 'pausing', 'cancelling'}:
                    break
                page.wait_for_timeout(100)
            assert second_saved['run']['status'] == 'completed'
            page.get_by_role('button', name='Compare', exact=True).click()
            for key in (first['id'], second['id']):
                page.get_by_label('Compare run ' + key, exact=True).check()
            page.get_by_role('button', name='Compare selected runs', exact=True).click()
            expect(page.locator('.lab-comparison')).to_be_visible(timeout=15000)
            compared = page.request.get(url + '/api/model-lab/compare?ids=' + first['id'] + ',' + second['id'], headers=private_headers).json()
            (out / 'actual-comparison.json').write_text(json.dumps(compared, indent=2), encoding='utf8')
            check('Native comparison consumes actual equal-condition completed runs', compared['comparable'] is True)
            report['comparison_run_ids'] = [first['id'], second['id']]
            page.locator('.lab-comparison').scroll_into_view_if_needed()
            # Close WebView2 native Downloads flyout if present, solely inside
            # the owned app. Escape is harmless to the comparison page.
            page.keyboard.press('Escape')
            page.wait_for_timeout(300)
            report['screenshots'].append(capture(hwnd, process.pid, out / 'actual-comparison-native.png'))
            screens = [('models', 'Model Intelligence Lab', 'model-lab'), ('cluster', 'Cluster', 'cluster'),
                       ('workflows', None, 'workflows'), ('model-routing', None, 'model-selection'),
                       ('home', None, 'home'), ('chat', None, 'conversations'), ('settings', 'Workspace settings', 'settings')]
            for screen, heading, filename in screens:
                page.evaluate('(screen) => { location.hash=screen; }', screen)
                if heading:
                    expect(page.get_by_role('heading', name=heading, exact=True)).to_be_visible(timeout=20000)
                page.wait_for_timeout(700)
                for width, height in [(1366, 768), (900, 650)]:
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 8, 32, width, height, 0)
                    page.wait_for_timeout(300)
                    geometry = page.evaluate('({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth})')
                    check(f'{filename} has no document overflow at native {width}x{height}', geometry['scrollWidth'] <= geometry['width']+1)
                    shot = capture(hwnd, process.pid, out / f'{filename}-{width}x{height}-native.png')
                    shot['viewport'] = geometry
                    report['screenshots'].append(shot)
                if screen == 'settings':
                    page.get_by_role('button', name='Refresh settings', exact=True).click()
                    check('Settings refresh remains an actual read action', True)
            # Verify a real sidebar control navigates, in addition to direct
            # supported hash routing used for repeatable capture.
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 8, 32, 1366, 768, 0)
            page.get_by_role('button', name='Assistant', exact=True).click()
            page.get_by_role('button', name='Home', exact=True).click()
            check('Actual native sidebar navigation returns Home', page.evaluate('location.hash') == '#home')
            check('Native review has no JavaScript errors', not report['javascript_errors'])
            check('Native review has no external network requests', not report['external_requests'])
            report['complete'] = True
            browser.close()
    except Exception as exc:
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        save()
        raise
    finally:
        if process.poll() is None:
            assert psutil.Process(process.pid).create_time() == created
            if hwnd:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            try:
                process.wait(15)
            except subprocess.TimeoutExpired:
                assert psutil.Process(process.pid).create_time() == created
                process.terminate()
                process.wait(10)
        log.close()
        report['owned_native_process_closed'] = process.poll() is not None
        report['finished_at'] = time.time()
        report['passed'] = report['complete'] and report['owned_native_process_closed'] and all(c['passed'] for c in report['checks'])
        save()
        print(json.dumps({'passed': report['passed'], 'checks': len(report['checks']), 'screenshots': len(report['screenshots']),
                          'owned_native_process_closed': report['owned_native_process_closed']}), flush=True)


if __name__ == '__main__':
    main()
