"""Review real native compute controls on an owned isolated HANNI backend.

Only reversible worker enable/concurrency configuration is permitted. Model
startup, node power, SSH terminals, microphone, chat and workflow execution are
never clicked. Screenshots are bounded to this owned native window.
"""
import argparse
import ctypes
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.v36_verification.check_native import frame_capture, wait_window
from playwright.sync_api import sync_playwright, expect
import win32con
import win32gui


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    origin = args.url.rstrip('/')
    parsed = urlsplit(origin)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port:
        raise SystemExit('Choose an explicit owned local preview origin.')
    output = args.output.resolve()
    if ROOT / 'data' not in output.parents:
        raise SystemExit('Keep native artifacts in private ignored data.')
    output.mkdir(parents=True, exist_ok=True)
    record = {'checks': [], 'frames': [], 'errors': [], 'javascript_errors': [],
              'startup_requests': [], 'owner_application_launched': True,
              'source': 'actual portable native HANNI app; authentic isolated backend data'}
    def check(name, passed, detail=None):
        record['checks'].append({'name': name, 'passed': bool(passed), 'detail': detail})
        if not passed:
            record['errors'].append(name)
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1', 0))
        debug = reserve.getsockname()[1]
    title = 'HANNI OS V3.7 Independent Compute Review'
    process = None
    log = (output / 'native-launch.log').open('w', encoding='utf8')
    try:
        process = subprocess.Popen([str(ROOT / 'dist/HANNI OS/HANNI OS.exe'),
            '--url', origin, '--attach-only', '--state-dir', str(output / 'native-state'),
            '--debug-port', str(debug), '--title', title], stdout=log, stderr=subprocess.STDOUT)
        hwnd = wait_window(title)
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0, 1366, 768, 0)
        with sync_playwright() as pw:
            browser = None
            for _ in range(80):
                try:
                    browser = pw.chromium.connect_over_cdp(f'http://127.0.0.1:{debug}', timeout=1000)
                    break
                except Exception:
                    time.sleep(.1)
            if browser is None:
                raise RuntimeError('Owned native CDP unavailable.')
            page = None
            for _ in range(300):
                browser.new_browser_cdp_session().send('Target.getTargets')
                pages = [p for c in browser.contexts for p in c.pages]
                page = next((p for p in pages if p.url.startswith(origin) and 'view=mini' not in p.url), None)
                if page:
                    break
                time.sleep(.1)
            if page is None:
                raise RuntimeError('Owned native backend page unavailable.')
            page.on('pageerror', lambda error: record['javascript_errors'].append(str(error)))
            def forbid_start(route):
                req = route.request
                if req.method != 'GET' and urlsplit(req.url).path in {
                    '/api/shutdown', '/api/cluster/power', '/api/cluster/terminal',
                    '/api/voice', '/api/chat', '/api/workflows', '/api/mcp',
                    '/api/gpu-routing', '/api/audio-devices'}:
                    record['startup_requests'].append('blocked unexpected unsafe operation')
                    route.abort('blockedbyclient')
                    return
                if req.method != 'GET' and urlsplit(req.url).path == '/api/compute':
                    body = req.post_data_json
                    if body.get('operation') != 'configure':
                        record['startup_requests'].append('blocked unexpected startup')
                        route.abort('blockedbyclient')
                        return
                route.continue_()
            page.route('**/api/**', forbid_start)
            expect(page.locator('.main-content')).to_be_visible(timeout=20000)
            def api(path):
                return page.evaluate('''async path=>{const chat=await(await fetch('/api/chat')).json();
                    const response=await fetch(path,{headers:{'X-Hanni-Token':chat.token}});
                    return {status:response.status,data:await response.json()}}''', path)
            def capture(name):
                info = frame_capture(hwnd, output / (name + '.png'))
                info['state'] = name
                record['frames'].append(info)
            page.evaluate('location.hash="models"')
            expect(page.locator('.screen-models')).to_be_visible()
            panel = page.locator('.screen-models .compute-worker').first
            expect(panel).to_be_visible(timeout=10000)
            before = api('/api/compute')['data']
            selected = before['workers'][0]
            initial = selected['enabled']
            record['worker_id'] = selected['worker_id']
            panel.locator('summary').click()
            expect(panel).to_contain_text('Configured context')
            expect(panel).to_contain_text('Server-reported context')
            expect(panel).to_contain_text('Allowed context')
            check('Real worker diagnostics distinguish measured and configured limits', True)
            capture('models-diagnostics')
            button_name = 'Disable worker' if initial else 'Enable worker'
            panel.get_by_role('button', name=button_name, exact=True).click()
            try:
                expect(panel.get_by_role('button', name='Enable worker' if initial else 'Disable worker', exact=True)).to_be_visible(timeout=10000)
                changed = api('/api/compute')['data']
                changed_worker = next(row for row in changed['workers'] if row['worker_id'] == selected['worker_id'])
                check('Native enable control persists actual protected configuration', changed_worker['enabled'] is not initial)
                capture('models-worker-toggled')
            finally:
                current = api('/api/compute')['data']
                current_worker = next(row for row in current['workers'] if row['worker_id'] == selected['worker_id'])
                if current_worker['enabled'] != initial:
                    panel.get_by_role('button', name='Enable worker' if initial else 'Disable worker', exact=True).click()
                    expect(panel.get_by_role('button', name=button_name, exact=True)).to_be_visible(timeout=10000)
                check('Native worker configuration restored', next(row for row in api('/api/compute')['data']['workers']
                    if row['worker_id'] == selected['worker_id'])['enabled'] == initial)
            if len(before['workers']) >= 3:
                all_workers = page.locator('.screen-models .compute-worker')
                expect(all_workers).to_have_count(len(before['workers']))
                check('Actual third registered model worker appears in native Models', True)
                last_worker = all_workers.last
                last_worker.locator('summary').click()
                last_worker.scroll_into_view_if_needed()
                capture('models-third-worker-diagnostics')
            page.evaluate('location.hash="cluster"')
            expect(page.locator('.screen-cluster')).to_be_visible()
            node = page.locator('.screen-cluster [data-node="hanni"]')
            expect(node).to_be_visible(timeout=10000)
            node.click()
            details = page.locator('[data-selected-node="hanni"]')
            expect(details).to_be_visible()
            check('Selecting actual HANNI node reveals original detailed diagnostics', True)
            expect(details.locator('.compute-worker').first).to_be_visible(timeout=10000)
            check('Node diagnostics include the actual registered worker panel', details.locator('.compute-worker').count() >= 1)
            capture('cluster-hanni-details')
            page.evaluate('location.hash="workflows"')
            expect(page.locator('.screen-workflows')).to_be_visible()
            workflows = api('/api/workflows')['data']
            record['workflow_count'] = len(workflows.get('items', []))
            if workflows.get('items'):
                row = page.locator('.workflow-row').first
                if not row.count():
                    row = page.locator('.screen-workflows button', has_text=workflows['items'][0].get('goal',''))
                row.first.click()
                expect(page.get_by_role('region', name='Distributed workflow execution')).to_be_visible(timeout=10000)
                check('Saved actual workflow details contain compute assignment section',
                      page.get_by_role('region', name='Distributed workflow execution').count() >= 1)
                reason = page.get_by_text('Why this worker', exact=True)
                if reason.count():
                    reason.first.click()
                    check('Original worker selection reason can be expanded', True)
                capture('workflows-distributed-detail')
                jobs = page.locator('.compute-job')
                if jobs.count() >= 3:
                    jobs.last.scroll_into_view_if_needed()
                    check('All three actual saved compute assignments remain inspectable', True)
                    capture('workflows-third-assignment')
            else:
                check('Absent workflow history displays an honest empty state',
                      'No saved workflows' in page.locator('.screen-workflows').inner_text())
                capture('workflows-empty')
            check('Native review produced no JavaScript errors', not record['javascript_errors'])
            check('Native review sent no startup requests', not record['startup_requests'])
            browser.close()
    except Exception as error:
        record['errors'].append(type(error).__name__ + ': ' + str(error)[:500])
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(5)
        log.close()
        record['native_closed'] = process is None or process.poll() is not None
        (output / 'results.json').write_text(json.dumps(record, indent=2), encoding='utf8')
    print(json.dumps({'checks':len(record['checks']), 'frames':len(record['frames']), 'errors':record['errors']}))

if __name__ == '__main__':
    main()
