"""Real framed Workflows review, run only after root's exclusive native GO.

Win32 ImageGrab captures actual owned portable-app frames; CDP only drives
controls and records layout. Real private HTTP, WorkflowHub/Service and original
host/registry/file handlers remain authoritative. Two-pass model replies, cached
inactive telemetry, one pre-stat failure and one pre-write barrier are disclosed
fixture seams. All files/stores are isolated. No model/provider/voice/SSH/power
action runs; no private CRUD replies or workflow states are fabricated.
Independent reviewer owns execution and scoring, not this harness's author.
"""
from __future__ import annotations

import argparse
import ctypes
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/desktop_review'))
sys.path.insert(0, str(ROOT))
from capture_native import SIZES, frame_capture, wait_window
from scripts.v3_review.check_browser import WorkflowBrowserFixture, runtime_manifest, wait_state, wait_completed
import psutil
import win32con
import win32gui
import win32process
from playwright.sync_api import expect, sync_playwright


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config_manifest():
    tracked = subprocess.check_output(['git', 'ls-files', '-z', '--', 'config'], cwd=ROOT).decode().split('\0')
    files = {name: digest(ROOT / name) for name in sorted(tracked)
             if name and (ROOT / name).is_file()}
    return {'sha256': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(), 'files': files,
            'scope': 'Tracked public repository config only; ignored provider/credential files are neither read nor hashed.'}


class NativeWorkflowFixture(WorkflowBrowserFixture):
    def __enter__(self):
        super().__enter__()
        self.barrier_path = None
        self.write_entered, self.release_write = threading.Event(), threading.Event()

        def bounded_barrier(arguments, _context, _request):
            if self.barrier_path is not None and Path(arguments['path']) == self.barrier_path:
                self.write_entered.set()
                if not self.release_write.wait(30):
                    raise TimeoutError('Controlled pre-write native-close barrier expired.')

        # Original metadata/gates/observer/handler survive; only fixture timing changes.
        definition = self.registry.get('file.write')
        original = definition.handler

        def gated_handler(arguments, context, request):
            bounded_barrier(arguments, context, request)
            return original(arguments, context, request)

        if not self.registry.unregister('file.write', expected=definition):
            raise AssertionError('Original file.write changed during isolated fixture setup.')
        self.registry.register(replace(definition, handler=gated_handler))
        return self

    def mutation(self, operation, data):
        body = {'id': str(uuid4()), 'operation': operation, 'data': data}
        request = urllib.request.Request(self.url.rstrip('/') + '/api/workflows',
            data=json.dumps(body).encode(), headers={'Content-Type': 'application/json',
            'X-Hanni-Token': self.hub.token, 'Origin': self.url.rstrip('/')}, method='POST')
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            # Publish only path, fixed operation, status and bounded safe gate
            # reason. Never include the private token or original goal/arguments.
            raise AssertionError(f'Fixture POST /api/workflows operation={operation} '
                                 f'HTTP{error.code}; exact-Origin=True; token-present=True; '
                                 f'reason={error.read(512).decode("utf-8", errors="replace")}') from error

    def wait_private(self, key, states, timeout=20):
        deadline, last = time.monotonic() + timeout, None
        while time.monotonic() < deadline:
            last = self.request(f'/api/workflows/{key}')['workflow']
            if last['status'] in states:
                return last
            time.sleep(.1)
        raise AssertionError(f'Actual private workflow state timeout: {(last or {}).get("status")}')

    def __exit__(self, *exc):
        self.release_write.set()
        return super().__exit__(*exc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exe', type=Path, default=ROOT / 'dist/HANNI OS/HANNI OS.exe')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    paths = {'exe': args.exe.resolve(), 'app.js': ROOT / 'src/hanni/dashboard/static/app.js',
             'style.css': ROOT / 'src/hanni/dashboard/static/style.css',
             'workflows.tsx': ROOT / 'frontend/src/workflows.tsx',
             'workflow_types.ts': ROOT / 'frontend/src/workflow_types.ts',
             'check_native.py': Path(__file__), 'check_browser.py': Path(__file__).with_name('check_browser.py')}
    result = {'passed': False, 'visual_score': None, 'checks': [], 'screenshots': [],
              'errors': [], 'javascript_errors': [], 'external_requests': [], 'owned_processes': [],
              'artifact_sha256': {name: digest(path) for name, path in paths.items()},
              'runtime_manifest': runtime_manifest(), 'config_manifest': config_manifest(),
              'disclosure': __doc__, 'private_operations': [],
              'controlled_seams': ['Scripted original two-pass planning client', 'Cached synthetic inactive telemetry',
                                   'One OSError before original stat; original metadata/gates unchanged',
                                   'HTTP 503 only after original Host/Origin/token gates',
                                   'Bounded original-write observer barrier for owned-window-close test']}

    def check(name, condition=True, evidence=None):
        result['checks'].append({'name': name, 'passed': bool(condition), 'evidence': evidence})
        if not condition:
            raise AssertionError(name)

    with NativeWorkflowFixture() as fixture, sync_playwright() as playwright:
        session = {'process': None, 'browser': None, 'page': None, 'hwnd': None, 'log': None, 'owned': set()}

        def launch(sequence):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            title = f'HANNI OS Independent Workflows Review {sequence}'
            log = (output / f'native-launch-{sequence}.log').open('w', encoding='utf-8')
            process = subprocess.Popen([str(args.exe.resolve()), '--url', fixture.url, '--attach-only',
                '--state-dir', str(output / f'isolated-native-state-{sequence}'),
                '--debug-port', str(port), '--title', title], stdout=log, stderr=subprocess.STDOUT)
            session.update(process=process, log=log, hwnd=None, browser=None, page=None, owned={process.pid})
            hwnd = wait_window(title)
            owned = {process.pid, *(child.pid for child in psutil.Process(process.pid).children(recursive=True))}
            actual_pid = win32process.GetWindowThreadProcessId(hwnd)[1]
            check('Actual titled native window belongs to the launched process tree', actual_pid in owned,
                  {'sequence': sequence, 'launcher_pid': process.pid, 'window_pid': actual_pid})
            session.update(hwnd=hwnd, owned=owned)
            result['owned_processes'].append({'sequence': sequence, 'launcher_pid': process.pid, 'window_pid': actual_pid})
            check('Actual native window is observed at 125 percent DPI', ctypes.windll.user32.GetDpiForWindow(hwnd) == 120,
                  {'observed_dpi': ctypes.windll.user32.GetDpiForWindow(hwnd)})
            browser = None
            for _ in range(100):
                try:
                    browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{port}', timeout=1000)
                    break
                except Exception:
                    time.sleep(.1)
            if browser is None:
                raise AssertionError('Actual native CDP did not become available.')
            session['browser'] = browser
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
                raise AssertionError('Actual native private-backend page was not found.')
            session['page'] = page
            page.set_default_timeout(20000)
            page.on('pageerror', lambda error: result['javascript_errors'].append(str(error)))
            page.on('request', lambda request: result['external_requests'].append(request.url)
                    if request.url.startswith(('http:', 'https:')) and not request.url.startswith(fixture.url) else None)
            page.on('request', lambda request: result['private_operations'].append({
                'id': request.post_data_json['id'], 'operation': request.post_data_json['operation']})
                if request.method == 'POST' and request.url == fixture.url.rstrip('/') + '/api/workflows' else None)
            win32gui.SetWindowPos(hwnd, 0, 0, 0, 1920, 1080, win32con.SWP_NOZORDER)
            page.evaluate('location.hash="workflows"')
            expect(page.locator('.workflows-page')).to_be_visible(timeout=30000)
            return page

        def close_native(*, required=False):
            process, hwnd = session['process'], session['hwnd']
            if process and process.poll() is None:
                try:
                    if hwnd and win32gui.IsWindow(hwnd):
                        actual_pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                        if actual_pid not in session['owned']:
                            raise AssertionError('Refusing to close an unowned native window.')
                        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    process.wait(timeout=15)
                except Exception:
                    if required:
                        raise
                    # Cleanup only the exact subprocess handle this harness created.
                    process.terminate()
                    process.wait(timeout=10)
            if required:
                check('Closing the exact owned window exits its launched native process',
                      process.poll() is not None and (not hwnd or not win32gui.IsWindow(hwnd)))
            if session['browser']:
                try:
                    session['browser'].close()
                except Exception:
                    pass
            if session['log']:
                session['log'].close()
            session.update(process=None, browser=None, hwnd=None, page=None, log=None)

        def capture(state, *, supplemental=None):
            page, hwnd = session['page'], session['hwnd']
            for width, height in SIZES:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetWindowPos(hwnd, 0, 0, 0, width, height, win32con.SWP_NOZORDER)
                page.wait_for_timeout(250)
                dialog = page.locator('dialog:modal')
                if dialog.count():
                    dialog.evaluate('(e)=>e.scrollTop=0')
                else:
                    page.locator('.main-content').evaluate('(e)=>e.scrollTop=0')
                page.wait_for_timeout(120)
                layout = page.evaluate('({width:innerWidth,height:innerHeight,documentWidth:document.documentElement.scrollWidth})')
                frame = frame_capture(hwnd, output / f'{state}-{width}x{height}-native.png')
                frame.update(state=state, dpi=ctypes.windll.user32.GetDpiForWindow(hwnd), layout=layout,
                             text=page.locator('.main-content').inner_text())
                result['screenshots'].append(frame)
                check(f'{state} actual physical {width}x{height} frame', frame['window_size'] == [width, height])
                check(f'{state} {width}x{height} no document horizontal overflow', layout['documentWidth'] <= layout['width'] + 1)
                if supplemental and width in {1366, 900}:
                    target = page.locator(supplemental).last
                    expect(target).to_be_visible()
                    target.evaluate('(e)=>e.scrollIntoView({block:"start"})')
                    page.wait_for_timeout(150)
                    extra = frame_capture(hwnd, output / f'{state}-supplemental-{width}x{height}-native.png')
                    extra.update(state=state, scroll_target=supplemental, dpi=ctypes.windll.user32.GetDpiForWindow(hwnd))
                    result['screenshots'].append(extra)
            win32gui.SetWindowPos(hwnd, 0, 0, 0, 1920, 1080, win32con.SWP_NOZORDER)
            page.wait_for_timeout(100)

        def submit(goal):
            page = session['page']
            page.get_by_role('button', name='New goal', exact=True).click()
            form = page.get_by_role('dialog', name='New workflow goal', exact=True)
            form.get_by_label('Goal', exact=True).fill(goal)
            form.get_by_role('button', name='Create workflow', exact=True).click()
            expect(form).not_to_be_visible()
            expect(page.get_by_role('button', name='Review plan approval', exact=True)).to_be_enabled(timeout=20000)
            return page.locator('.workflow-detail').get_attribute('data-workflow-id')

        def approve_and_start():
            page = session['page']
            page.get_by_role('button', name='Review plan approval', exact=True).click()
            dialog = page.get_by_role('dialog', name='Approve this workflow plan?', exact=True)
            dialog.get_by_role('button', name='Approve this plan', exact=True).click()
            expect(dialog).not_to_be_visible()
            expect(page.get_by_role('button', name='Start', exact=True)).to_be_enabled(timeout=20000)
            page.get_by_role('button', name='Start', exact=True).click()

        def back():
            session['page'].get_by_role('button', name='Back to workflows', exact=True).click()

        try:
            fixture.workflow_outage = True
            page = launch(1)
            expect(page.get_by_text('Workflow history could not be loaded. Refresh when the connection is available.', exact=True)).to_be_visible()
            check('Actual first-fetch error does not assert empty history', page.get_by_role('heading', name='No saved workflows', exact=True).count() == 0)
            capture('first-fetch-error')
            fixture.workflow_outage = False
            page.get_by_role('button', name='Refresh workflows', exact=True).click()
            expect(page.get_by_role('heading', name='No saved workflows', exact=True)).to_be_visible()
            expect(page.get_by_role('button', name='New goal', exact=True)).to_be_disabled()
            capture('cold-empty')
            fixture.attach()
            page.get_by_role('button', name='Refresh workflows', exact=True).click()
            expect(page.get_by_role('button', name='New goal', exact=True)).to_be_enabled()
            page.get_by_role('button', name='New goal', exact=True).click()
            form = page.get_by_role('dialog', name='New workflow goal', exact=True)
            expect(form.get_by_label('Autonomy mode', exact=True)).to_have_value('assisted')
            capture('goal-form', supplemental='dialog:modal .dialog-actions')
            for _ in range(8):
                page.keyboard.press('Tab')
                check('Native modal keyboard keeps background inert', page.evaluate('''() => {
                    const background=document.querySelector('.screen-heading button'); background.focus();
                    return document.activeElement!==background && Boolean(document.querySelector('dialog:modal'));
                }'''))
            page.keyboard.press('Escape')
            expect(form).not_to_be_visible()
            check('Native Escape grants no goal', not fixture.request()['items'])

            fixture.client.file_check(fixture.source)
            read_id = submit(f'Check whether file {fixture.source} exists and hash its bytes')
            page.get_by_role('button', name='Review plan approval', exact=True).click()
            plan_dialog = page.get_by_role('dialog', name='Approve this workflow plan?', exact=True)
            capture('plan-review', supplemental='dialog:modal .dialog-actions')
            saved = fixture.request(f'/api/workflows/{read_id}')['workflow']
            fixture.mutation('approve_plan', {'workflow_id': read_id, 'expected_revision': saved['revision'], 'plan_hash': saved['plan_hash']})
            expect(plan_dialog.get_by_role('button', name='Approve this plan', exact=True)).to_be_disabled()
            expect(plan_dialog.get_by_role('alert')).to_contain_text('changed or expired')
            capture('changed-plan-review', supplemental='dialog:modal .dialog-actions')
            plan_dialog.get_by_role('button', name='Keep reviewing', exact=True).click()
            expect(page.get_by_role('button', name='Start', exact=True)).to_be_enabled(timeout=20000)
            page.get_by_role('button', name='Start', exact=True).click()
            wait_completed(page, f'/api/workflows/{read_id}', fixture.hub.token)
            expect(page.locator('.workflow-detail > .screen-heading p')).to_contain_text('Completed')
            page.locator('.workflow-step[data-step-id="check"] > summary').click()
            capture('verified-read-step', supplemental='.workflow-step[data-step-id="check"] .workflow-criteria')
            check('Native read evidence verifies actual unchanged fixture bytes', fixture.source.read_bytes() == b'Original fixture content\n')
            back()
            capture('recorded-overview')

            target = Path(fixture.temporary.name) / 'native-approval-target.txt'
            text = 'Explicitly approved native fixture text\n'
            fixture.client.sensitive_write(target, text)
            rejected_id = submit(f'Create a local text file at {target} with the explicitly reviewed fixture text')
            approve_and_start()
            pending = wait_state(page, f'/api/workflows/{rejected_id}', fixture.hub.token, {'awaiting_step_approval'})['workflow']
            expect(page.get_by_role('button', name='Review action', exact=True)).to_be_enabled()
            page.get_by_role('button', name='Review action', exact=True).click()
            action = page.get_by_role('dialog', name='Approve this workflow action?', exact=True)
            check('Native action preview is fully resolved exact original target/text',
                  json.loads(action.locator('.workflow-approval-arguments').inner_text()) == {'path': str(target), 'text': text})
            capture('resolved-action-review', supplemental='dialog:modal .dialog-actions')
            page.keyboard.press('Escape')
            expect(action).not_to_be_visible()
            check('Native action Escape never dispatches the original write', not target.exists() and not pending['invocations'])
            page.get_by_role('button', name='Reject', exact=True).click()
            rejection = page.get_by_role('dialog', name='Reject this action?', exact=True)
            capture('reject-confirmation', supplemental='dialog:modal .dialog-actions')
            rejection.get_by_role('button', name='Reject this action', exact=True).click()
            expect(rejection).not_to_be_visible()
            rejected = fixture.request(f'/api/workflows/{rejected_id}')['workflow']
            check('Actual rejected action persists without creating the file', not target.exists() and any(item['state'] == 'rejected' for item in rejected['approvals']))
            capture('rejected-action')
            back()

            fixture.client.sensitive_write(target, text)
            approved_id = submit(f'Create a local text file at {target} with the explicitly reviewed fixture text')
            approve_and_start()
            approved_pending = wait_state(page, f'/api/workflows/{approved_id}', fixture.hub.token, {'awaiting_step_approval'})['workflow']
            before_write_count = fixture.ledger.entries('file.write')
            expect(page.get_by_role('button', name='Review action', exact=True)).to_be_enabled()
            page.get_by_role('button', name='Review action', exact=True).click()
            approved_dialog = page.get_by_role('dialog', name='Approve this workflow action?', exact=True)
            check('Actual native approval preview still matches the reviewed pending argument binding',
                  json.loads(approved_dialog.locator('.workflow-approval-arguments').inner_text()) == approved_pending['steps'][0]['resolved_arguments'])
            approved_dialog.get_by_role('button', name='Approve this action', exact=True).click()
            expect(approved_dialog).not_to_be_visible()
            approved = wait_completed(page, f'/api/workflows/{approved_id}', fixture.hub.token)['workflow']
            check('Native explicit action approval executes one actual verified isolated write',
                  approved['counts']['verified'] == 1 and target.read_text(encoding='utf-8') == text and
                  fixture.ledger.entries('file.write') == before_write_count + 1)
            check('Native approved write has exactly one durable dispatched invocation', len(approved['invocations']) == 1)
            expect(page.locator('.workflow-detail > .screen-heading p')).to_contain_text('Completed')
            capture('approved-action-outcome')
            back()

            fixture.client.file_check(fixture.source)
            revoke_id = submit(f'Check file {fixture.source} before an explicit review')
            page.get_by_role('button', name='Revoke approval', exact=True).click()
            revoke = page.get_by_role('dialog', name='Revoke this approval?', exact=True)
            capture('revoke-confirmation', supplemental='dialog:modal .dialog-actions')
            revoke.get_by_role('button', name='Revoke this approval', exact=True).click()
            expect(revoke).not_to_be_visible()
            revoked = wait_state(page, f'/api/workflows/{revoke_id}', fixture.hub.token, {'paused'})['workflow']
            check('Actual revoked pending scope admits no original invocation', not revoked['invocations'] and any(item['state'] == 'revoked' for item in revoked['approvals']))
            expect(page.locator('.workflow-detail > .screen-heading p')).to_contain_text('Paused')
            expect(page.locator('.workflow-detail')).not_to_contain_text('The backend will stop at a safe execution boundary.')
            check('Native settled Paused does not falsely claim a pending future stop')
            capture('revoked-scope')
            back()

            fixture.read_failure_path = fixture.source
            fixture.client.file_check(fixture.source)
            retry_id = submit(f'Check file {fixture.source} with explicit safe read recovery')
            approve_and_start()
            failed = wait_state(page, f'/api/workflows/{retry_id}', fixture.hub.token, {'blocked'})['workflow']
            page.locator('.workflow-step[data-step-id="check"] > summary').click()
            expect(page.get_by_role('button', name='Retry this safe failed step', exact=True)).to_be_enabled()
            capture('failed-safe-read', supplemental='.workflow-step[data-step-id="check"] button')
            page.get_by_role('button', name='Retry this safe failed step', exact=True).click()
            retry_dialog = page.get_by_role('dialog', name='Retry this safe step?', exact=True)
            capture('safe-retry-confirmation', supplemental='dialog:modal .dialog-actions')
            retry_dialog.get_by_role('button', name='Retry this safe step', exact=True).click()
            expect(retry_dialog).not_to_be_visible()
            retried = wait_completed(page, f'/api/workflows/{retry_id}', fixture.hub.token)['workflow']
            check('Native explicit safe retry keeps exact original arguments and verifies the second read',
                  len(failed['invocations']) == 1 and len(retried['invocations']) == 2 and retried['counts']['verified'] == 1 and
                  retried['invocations'][0]['argument_hash'] == retried['invocations'][1]['argument_hash'])
            back()

            cancel_target = Path(fixture.temporary.name) / 'native-cancel-target.txt'
            fixture.client.sensitive_write(cancel_target, text)
            cancel_id = submit(f'Create a local text file at {cancel_target} with the explicitly reviewed fixture text')
            approve_and_start()
            wait_state(page, f'/api/workflows/{cancel_id}', fixture.hub.token, {'awaiting_step_approval'})
            page.get_by_role('button', name='Cancel workflow', exact=True).click()
            cancel_dialog = page.get_by_role('dialog', name='Cancel workflow?', exact=True)
            capture('pending-cancel-confirmation', supplemental='dialog:modal .dialog-actions')
            cancel_dialog.get_by_role('button', name='Cancel workflow', exact=True).click()
            expect(cancel_dialog).not_to_be_visible()
            cancelled = wait_state(page, f'/api/workflows/{cancel_id}', fixture.hub.token, {'cancelled'})['workflow']
            check('Native pending cancellation creates no file or invocation', not cancel_target.exists() and not cancelled['invocations'])
            expect(page.locator('.workflow-detail > .screen-heading p')).to_contain_text('Cancelled')
            expect(page.locator('.workflow-detail')).not_to_contain_text('The backend will stop at a safe execution boundary.')
            check('Native settled Cancelled does not falsely claim a pending future stop')
            capture('cancelled-pending-action')
            back()

            # Real managed artifact waits inside an original-handler observer while
            # the exact owned native process closes. The attached backend is separate.
            fixture.client.file_artifact(fixture.source)
            continue_id = submit(f'Read text file {fixture.source} and save its exact text as a managed report')
            prepared = fixture.request(f'/api/workflows/{continue_id}')['workflow']
            fixture.barrier_path = Path(next(step for step in prepared['steps'] if step['step_id'] == 'save')['planned_arguments']['path'])
            check('Native-close barrier is confined to the isolated managed report', fixture.barrier_path.resolve().is_relative_to(Path(fixture.temporary.name).resolve()))
            approve_and_start()
            deadline = time.monotonic() + 10
            while not fixture.write_entered.is_set() and time.monotonic() < deadline:
                page.wait_for_timeout(100)
            check('Actual original managed-write invocation reached the bounded pre-handler review barrier', fixture.write_entered.is_set())
            running = fixture.request(f'/api/workflows/{continue_id}')['workflow']
            check('Native close occurs while real backend invocation is active and noninterruptible', running['active_uninterruptible'] and not fixture.barrier_path.exists())
            expect(page.locator('.workflow-detail')).to_contain_text('An active action cannot be interrupted.')
            check('Actual noninterruptible original invocation keeps its pending-outcome warning')
            result['active_invocation_warning_frame'] = frame_capture(session['hwnd'], output / 'active-original-invocation-warning-native.png')
            close_native(required=True)
            check('Closing the client does not detach the independently owned backend runner', fixture.request()['runner_attached'])
            fixture.release_write.set()
            finished = fixture.wait_private(continue_id, {'completed'})
            artifact = next(item for item in finished['artifacts'] if item['step_id'] == 'save')
            check('Backend completes actual verified file bytes after native window closes',
                  finished['counts']['verified'] == 2 and fixture.barrier_path.read_text(encoding='utf-8') == fixture.source.read_text(encoding='utf-8') and
                  digest(fixture.barrier_path) == artifact['sha256'] and artifact['verified'])
            page = launch(2)
            page.locator(f'.workflow-row[data-workflow-id="{continue_id}"]').click()
            expect(page.get_by_role('button', name='View output', exact=True)).to_be_visible()
            capture('reopened-verified-report')
            page.get_by_role('button', name='View output', exact=True).click()
            output_dialog = page.get_by_role('dialog', name='Output: browser-report.txt', exact=True)
            expect(output_dialog.locator('.workflow-output-text')).to_have_text(artifact['excerpt'])
            capture('saved-report-output', supplemental='dialog:modal .dialog-actions')
            output_dialog.get_by_role('button', name='Close output', exact=True).click()
            back()
            fixture.workflow_outage = True
            page.get_by_role('button', name='Refresh workflows', exact=True).click()
            expect(page.get_by_text('Displayed history may be stale.', exact=False)).to_be_visible()
            expect(page.get_by_role('button', name='New goal', exact=True)).to_be_disabled()
            capture('stale-recorded-history')
            fixture.workflow_outage = False
            fixture.detach()
            page.get_by_role('button', name='Refresh workflows', exact=True).click()
            expect(page.get_by_role('button', name='New goal', exact=True)).to_be_disabled()
            check('Actual detached runner leaves saved history without current execution authority', not fixture.request()['runner_attached'] and page.locator('.workflow-row').count() == 7)
            capture('cold-recorded-history')
            check('No native browser JavaScript errors', not result['javascript_errors'], result['javascript_errors'])
            check('No nonlocal integration browser requests', not result['external_requests'], result['external_requests'])
            check('No fixture remote power, voice, terminal or provider mutation', not fixture.writes)
            result['workflow_ids'] = {'read': read_id, 'rejected': rejected_id, 'approved': approved_id, 'revoked': revoke_id,
                                      'retried': retry_id, 'cancelled': cancel_id, 'continued': continue_id}
            result['passed'] = True
        except BaseException as error:
            result['errors'].append(f'{type(error).__name__}: {error}')
            if session['hwnd'] and win32gui.IsWindow(session['hwnd']):
                try:
                    result['failure_frame'] = frame_capture(session['hwnd'], output / 'failure-native.png')
                except Exception as capture_error:
                    result['errors'].append(f'Failure capture: {type(capture_error).__name__}: {capture_error}')
        finally:
            fixture.release_write.set()
            close_native()
            result['artifact_sha256_after'] = {name: digest(path) for name, path in paths.items()}
            result['runtime_manifest_after'], result['config_manifest_after'] = runtime_manifest(), config_manifest()
            frozen = (result['artifact_sha256'] == result['artifact_sha256_after'] and
                      result['runtime_manifest']['sha256'] == result['runtime_manifest_after']['sha256'] and
                      result['config_manifest']['sha256'] == result['config_manifest_after']['sha256'])
            result['checks'].append({'name': 'Native executable/frontend/runtime/config remain frozen throughout capture', 'passed': frozen})
            if not frozen:
                result['errors'].append('Source or bundle changed during native review.')
            result['passed'] = result['passed'] and frozen and not result['errors']
            (output / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'checks': len(result['checks']),
                      'frames': len(result['screenshots']), 'errors': result['errors'], 'visual_score': None}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
