"""Actual native workspace interactions against isolated genuine local stores.

No private API routes, CRUD, permission gates or persistence are mocked. The
fixture's system telemetry/device/model samples and chat transport are synthetic.
Run only after the coordinator grants exclusive GUI ownership and build freeze.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import date
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.request
from uuid import uuid4

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
import win32con
import win32gui
from playwright.sync_api import sync_playwright, expect

from capture_native import ROOT, frame_capture, wait_window
from phase_fixture import PhaseReviewFixture


def request(fixture, route, body=None, *, authenticated=True):
    headers = {'Origin': fixture.url.rstrip('/')}
    if authenticated:
        headers['X-Hanni-Token'] = fixture.hub.token
    data = None
    if body is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(body).encode()
    req = urllib.request.Request(fixture.url + route.lstrip('/'), data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def operation(name, data):
    return {'id': str(uuid4()), 'operation': name, 'data': data, 'confirmed': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reminder-boundary', action='store_true',
                        help='Create 100 additional actual gated due tasks and inspect all 101 reminder targets')
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    result = {'passed': False, 'checks': [], 'errors': [], 'frames': [],
              'javascript_errors': [], 'dpi': ctypes.windll.user32.GetDpiForSystem(),
              'disclosure': 'Genuine native window and real isolated registry-gated local workspace/MemoryStore/audit/notification persistence with synthetic review content. Synthetic telemetry/chat/model/device samples. Voice unbound; Google disconnected; vision unavailable. No model, microphone, remote actions or actual provider operations.',
              'artifact_sha256': {label: hashlib.sha256(path.read_bytes()).hexdigest()
                  for label, path in [('exe', args.exe.resolve()),
                                      ('app.js', ROOT/'src/hanni/dashboard/static/app.js'),
                                      ('style.css', ROOT/'src/hanni/dashboard/static/style.css')]}}
    process = None

    def check(name, assertion, evidence=None):
        if not assertion:
            raise AssertionError(name)
        result['checks'].append({'name': name, 'passed': True, 'evidence': evidence})

    with PhaseReviewFixture() as fixture:
        try:
            if args.reminder_boundary:
                for index in range(100):
                    fixture.operation('task.create', {'title':f'Boundary reminder task {index+1:03d}',
                        'course':'Independent notification boundary', 'due':date.today().isoformat(),
                        'priority':'normal', 'project_id':None})
                result['reminder_boundary_disclosure'] = '100 additional real HTTP/registry-gated isolated due tasks plus one seeded due task; no private writes mocked.'
            # Private GET gates are exercised before the native UI reads them.
            for route in ('productivity', 'memory', 'calendar', 'agents', 'awareness', 'voice', 'notifications'):
                status, _ = request(fixture, 'api/' + route, authenticated=False)
                check('Private GET rejects missing token: ' + route, status == 403, status)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                debug_port = sock.getsockname()[1]
            log = (args.output/'native-launch.log').open('w', encoding='utf-8')
            launch_args = [str(args.exe.resolve()), '--url', fixture.url,
                '--attach-only', '--state-dir', str(args.output/'isolated-native-state'),
                '--debug-port', str(debug_port), '--title', 'HANNI OS Workspace Verification']
            process = subprocess.Popen(launch_args,
                stdout=log, stderr=subprocess.STDOUT)
            hwnd = wait_window('HANNI OS Workspace Verification')
            win32gui.SetWindowPos(hwnd, 0, 0, 0, 1440, 900, win32con.SWP_NOZORDER)
            with sync_playwright() as playwright:
                browser = None
                for _ in range(100):
                    try:
                        browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{debug_port}', timeout=1000)
                        break
                    except Exception:
                        time.sleep(.1)
                if browser is None:
                    raise RuntimeError('Native WebView CDP unavailable')
                page = None
                for _ in range(300):
                    pages = [page for context in browser.contexts for page in context.pages]
                    matches = [page for page in pages if page.url.startswith(fixture.url) and '?view=mini' not in page.url]
                    if matches:
                        page = matches[0]
                        break
                    if pages:
                        pages[0].wait_for_timeout(100)
                if page is None:
                    raise RuntimeError('Actual native main page did not load')
                page.on('pageerror', lambda error: result['javascript_errors'].append(str(error)))

                def route(name, heading):
                    page.evaluate('(name) => {location.hash=name}', name)
                    expect(page.get_by_role('heading', name=heading, exact=True)).to_be_visible(timeout=15000)

                def frame(name):
                    page.wait_for_timeout(300)
                    result['frames'].append(frame_capture(hwnd, args.output/(name+'-native.png')))

                def snapshot():
                    status, data = request(fixture, 'api/productivity')
                    check('Workspace snapshot remains authorized', status == 200)
                    return data

                # Create/edit writes originate in the real React UI. Read-only
                # HTTP snapshots independently check the authoritative store.
                route('tasks', 'Tasks')
                page.get_by_role('button', name='New task', exact=True).click()
                dialog = page.get_by_role('dialog', name='New task', exact=True)
                expect(dialog).to_be_visible()
                dialog.get_by_label('Title', exact=True).fill('Native independent task')
                dialog.get_by_label('Course or category', exact=True).fill('Verification')
                dialog.get_by_label('Priority', exact=True).select_option('high')
                frame('task-create-dialog')
                dialog.get_by_role('button', name='Save', exact=True).click()
                expect(dialog).not_to_be_visible()
                row = page.locator('[data-task]').filter(has_text='Native independent task')
                expect(row).to_be_visible()
                tasks = snapshot()['tasks']
                task = next(item for item in tasks if item['title'] == 'Native independent task')
                check('Native task creation persisted once', sum(item['title'] == task['title'] for item in tasks) == 1, task['id'])
                row.locator('.task-title').click()
                dialog = page.get_by_role('dialog', name='Edit task', exact=True)
                expect(dialog).to_be_visible()
                dialog.get_by_label('Title', exact=True).fill('Native edited task')
                dialog.get_by_role('button', name='Save', exact=True).click()
                expect(dialog).not_to_be_visible()
                expect(page.locator('[data-task]').filter(has_text='Native edited task')).to_be_visible()
                updated = next(item for item in snapshot()['tasks'] if item['id'] == task['id'])
                check('Native edit retained stable task identity', updated['title'] == 'Native edited task' and updated['fingerprint'] != task['fingerprint'])

                # Concurrent authoritative edit while the native draft is open.
                page.locator('[data-task]').filter(has_text='Native edited task').locator('.task-title').click()
                dialog = page.get_by_role('dialog', name='Edit task', exact=True)
                dialog.get_by_label('Title', exact=True).fill('Stale native draft')
                concurrent = operation('task.update', {'task_id':updated['id'],
                    'expected_fingerprint':updated['fingerprint'], 'title':'Concurrent saved task',
                    'course':updated['course'], 'due':updated['due'] or None, 'priority':updated['priority'],
                    'project_id':updated['project_id'], 'status':updated['status']})
                status, _ = request(fixture, 'api/productivity', concurrent)
                check('Independent concurrent edit accepted through original gate', status == 200)
                dialog.get_by_role('button', name='Save', exact=True).click()
                expect(dialog.get_by_role('alert')).to_be_visible()
                expect(dialog.get_by_label('Title', exact=True)).to_have_value('Stale native draft')
                current = next(item for item in snapshot()['tasks'] if item['id'] == task['id'])
                check('Stale native edit rejected without overwriting current data', current['title'] == 'Concurrent saved task', dialog.get_by_role('alert').inner_text())
                frame('task-stale-error')
                dialog.get_by_role('button', name='Cancel', exact=True).click()

                # Request-ID dedupe and changed-payload rejection use the actual
                # public local adapter, not an injected response.
                body = operation('task.create', {'title':'Deduplicated request task','course':'Verification',
                    'due':None,'priority':'normal','project_id':None})
                first_status, first = request(fixture, 'api/productivity', body)
                second_status, second = request(fixture, 'api/productivity', body)
                check('Exact UUID retry returns identical result', first_status == second_status == 200 and first == second)
                changed = {**body, 'data':{**body['data'], 'title':'Changed UUID payload'}}
                status, _ = request(fixture, 'api/productivity', changed)
                check('Reused UUID with changed payload rejected', status == 400, status)
                check('UUID retries produced exactly one stored task', sum(item['title'] == 'Deduplicated request task' for item in snapshot()['tasks']) == 1)
                page.get_by_role('button', name='Refresh tasks', exact=True).click()
                disposable = page.locator('[data-task]').filter(has_text='Deduplicated request task')
                expect(disposable).to_be_visible()
                disposable.get_by_role('button', name='Complete Deduplicated request task', exact=True).click()
                expect(disposable).to_have_count(0)
                check('Native completion persists original task status',
                      next(item for item in snapshot()['tasks'] if item['title'] == 'Deduplicated request task')['status'] == 'completed')
                page.get_by_label('Task status', exact=True).select_option('all')
                expect(disposable).to_be_visible()
                disposable.get_by_role('button', name='Reopen Deduplicated request task', exact=True).click()
                expect(disposable.get_by_role('button', name='Complete Deduplicated request task', exact=True)).to_be_visible()
                check('Native reopen persists original task status',
                      next(item for item in snapshot()['tasks'] if item['title'] == 'Deduplicated request task')['status'] == 'open')
                disposable.get_by_role('button', name='Delete Deduplicated request task', exact=True).click()
                dialog = page.get_by_role('dialog', name='Delete Deduplicated request task?', exact=True)
                expect(dialog).to_be_visible()
                frame('task-exact-delete-dialog')
                dialog.get_by_role('button', name='Confirm deletion', exact=True).click()
                expect(dialog).not_to_be_visible()
                expect(disposable).to_have_count(0)
                check('Confirmed native task deletion removes exact selected record',
                      not any(item['title'] == 'Deduplicated request task' for item in snapshot()['tasks']))

                route('projects', 'Projects')
                page.get_by_role('button', name='New project', exact=True).click()
                dialog = page.get_by_role('dialog', name='New project', exact=True)
                dialog.get_by_label('Project name', exact=True).fill('Native independent project')
                dialog.get_by_label('Description', exact=True).fill('Genuine isolated verification record')
                dialog.get_by_role('button', name='Save', exact=True).click()
                expect(dialog).not_to_be_visible()
                page.locator('.project-list').get_by_role('button').filter(has_text='Native independent project').click()
                expect(page.get_by_role('heading', name='Native independent project', exact=True)).to_be_visible()
                project = next(item for item in snapshot()['projects'] if item['name'] == 'Native independent project')
                page.get_by_role('button', name='Add note', exact=True).click()
                dialog = page.get_by_role('dialog', name='New note', exact=True)
                dialog.get_by_label('Title', exact=True).fill('Native independent note')
                dialog.get_by_label('Note', exact=True).fill('Private local note body must not appear in execution audits.')
                dialog.get_by_role('button', name='Save', exact=True).click()
                expect(dialog).not_to_be_visible()
                expect(page.locator('.project-note').filter(has_text='Native independent note')).to_be_visible()
                page.get_by_role('button', name='Add link', exact=True).click()
                dialog = page.get_by_role('dialog', name='New link', exact=True)
                dialog.get_by_label('Link label', exact=True).fill('Native review file reference')
                dialog.get_by_label('Absolute file path', exact=True).fill(str(ROOT/'docs/HANNI_OS.md'))
                dialog.get_by_role('button', name='Save', exact=True).click()
                expect(dialog).not_to_be_visible()
                expect(page.locator('.project-link').filter(has_text='Native review file reference')).to_be_visible()
                stored = snapshot()
                check('Native project, note and file reference persist in real store',
                      any(item['project_id'] == project['id'] and item['title'] == 'Native independent note' for item in stored['notes'])
                      and any(item['project_id'] == project['id'] and item['label'] == 'Native review file reference' for item in stored['links']))
                frame('project-populated-detail')
                page.get_by_role('button', name='Delete project', exact=True).click()
                dialog = page.get_by_role('dialog', name='Delete Native independent project?', exact=True)
                expect(dialog).to_be_visible()
                dialog.get_by_role('button', name='Cancel', exact=True).click()
                check('Cancel native deletion preserves saved project', any(item['id'] == project['id'] for item in snapshot()['projects']))

                # Exact target IDs are observed through native navigation, not
                # merely accepted as a route change.
                route('notifications', 'Notifications')
                if args.reminder_boundary:
                    _, boundary_first = request(fixture, 'api/notifications')
                    _, boundary_repeat = request(fixture, 'api/notifications')
                    first_due = [item for item in boundary_first['items'] if item['category'] == 'reminders']
                    repeat_due = [item for item in boundary_repeat['items'] if item['category'] == 'reminders']
                    check('All 101 real due task reminders ingested beyond first batch', len(first_due) == 101, len(first_due))
                    check('Repeated real notification observation preserves exact 101 reminder identities',
                          {item['id'] for item in first_due} == {item['id'] for item in repeat_due} and len(repeat_due) == 101)
                    page.get_by_label('Notification category', exact=True).select_option('reminders')
                    expect(page.locator('.notification-list article')).to_have_count(101)
                    check('Actual native center renders all 101 reminder records', page.locator('.notification-list article').count() == 101)
                    frame('notifications-101-reminder-boundary')
                    page.get_by_label('Notification category', exact=True).select_option('all')
                due = page.locator('.notification-list article').filter(has_text='Check desktop window layouts')
                expect(due).to_be_visible(timeout=15000)
                due.get_by_role('button', name='Inspect event', exact=True).click()
                expect(page.get_by_role('heading', name='Tasks', exact=True)).to_be_visible()
                inspected = page.locator('[data-task].inspected')
                expect(inspected).to_contain_text('Check desktop window layouts')
                check('Notification Inspect selects exact task record', inspected.count() == 1, inspected.get_attribute('data-task'))
                frame('notification-inspect-task')
                route('notifications', 'Notifications')
                audited = page.locator('.notification-list article').filter(has_text='workspace.note.create completed').first
                expect(audited).to_be_visible()
                audited.get_by_role('button', name='Inspect event', exact=True).click()
                expect(page.get_by_role('heading', name='Activity', exact=True)).to_be_visible()
                expect(page.locator('.execution-record[open]')).to_be_visible()
                check('Audit notification Inspect opens exact recorded execution', page.locator('.execution-record[open]').count() == 1
                      and 'workspace.note.create' in page.locator('.execution-record[open] > summary').inner_text())
                frame('notification-inspect-audit')

                route('memory', 'Memory')
                before_status, before_memory = request(fixture, 'api/memory')
                check('Memory provenance is from original store', before_status == 200 and before_memory['source'] == 'stored-memory')
                page.get_by_role('button', name='Forget record', exact=True).first.click()
                dialog = page.get_by_role('dialog', name='Forget this memory?', exact=True)
                expect(dialog).to_be_visible()
                frame('memory-exact-forget-dialog')
                dialog.get_by_role('button', name='Cancel', exact=True).click()
                _, retained_memory = request(fixture, 'api/memory')
                check('Cancel exact memory deletion retains all records', retained_memory['count'] == before_memory['count'])
                page.get_by_role('button', name='Forget record', exact=True).first.click()
                dialog = page.get_by_role('dialog', name='Forget this memory?', exact=True)
                dialog.get_by_role('button', name='Forget memory', exact=True).click()
                expect(dialog).not_to_be_visible()
                _, after_memory = request(fixture, 'api/memory')
                check('Confirmed native memory forget deletes exactly one original record', after_memory['count'] == before_memory['count'] - 1)

                route('notifications', 'Notifications')
                _, notifications_before = request(fixture, 'api/notifications')
                page.locator('.notification-list article').first.get_by_role('button', name='Mark read', exact=True).click()
                expect(page.get_by_role('button', name='Mark read', exact=True)).to_have_count(
                    sum(not item['read'] and not item['dismissed'] for item in notifications_before['items']) - 1)
                _, notifications_read = request(fixture, 'api/notifications')
                check('Native Mark read persists an additional read record',
                      sum(item['read'] for item in notifications_read['items']) == sum(item['read'] for item in notifications_before['items']) + 1)
                page.locator('.notification-list article').first.get_by_role('button', name='Dismiss', exact=True).click()
                page.wait_for_timeout(300)
                _, notifications_dismissed = request(fixture, 'api/notifications')
                check('Native Dismiss persists exact record in history',
                      sum(item['dismissed'] for item in notifications_dismissed['items']) == sum(item['dismissed'] for item in notifications_read['items']) + 1)
                page.locator('.notification-preferences summary').click()
                # This controlled checkbox updates after its real HTTP write;
                # Playwright uncheck() demands an immediate synchronous state.
                page.get_by_label('tasks', exact=True).click()
                expect(page.get_by_label('tasks', exact=True)).not_to_be_checked()
                _, notifications_preferences = request(fixture, 'api/notifications')
                check('Native category preference persists without approving tools', notifications_preferences['preferences']['categories']['tasks'] is False)
                page.get_by_role('button', name='Clear all', exact=True).click()
                dialog = page.get_by_role('dialog', name='Clear current notifications?', exact=True)
                expect(dialog).to_be_visible()
                frame('notifications-clear-confirmation')
                dialog.get_by_role('button', name='Cancel', exact=True).click()
                _, cancelled = request(fixture, 'api/notifications')
                check('Cancel notification clear preserves history', sum(item['dismissed'] for item in cancelled['items']) == sum(item['dismissed'] for item in notifications_preferences['items']))
                page.get_by_role('button', name='Clear all', exact=True).click()
                dialog = page.get_by_role('dialog', name='Clear current notifications?', exact=True)
                dialog.get_by_role('button', name='Clear notifications', exact=True).click()
                expect(dialog).not_to_be_visible()
                expect(page.locator('.notification-list article')).to_have_count(0)
                _, cleared = request(fixture, 'api/notifications')
                check('Confirmed native clear dismisses history without re-notifying itself', len(cleared['items']) > 0 and all(item['dismissed'] for item in cleared['items']))
                frame('notifications-empty-after-clear')

                route('voice', 'Voice & audio')
                _, voice = request(fixture, 'api/voice')
                check('Unbound voice is truthfully disabled', voice['available'] is False and voice['microphone_active'] is False and voice['input_level'] == 0 and voice['state'] == 'disabled', voice)
                frame('voice-disabled')
                route('screen', 'Screen awareness')
                _, awareness = request(fixture, 'api/awareness')
                check('Missing vision has inactive capture and disabled analyze', awareness['available'] is False and awareness['capture_active'] is False and page.get_by_role('button', name='Analyze current screen').is_disabled(), awareness)
                frame('awareness-unavailable')
                route('calendar', 'Calendar')
                _, calendar = request(fixture, 'api/calendar')
                check('Unconfigured calendar remains disconnected', calendar['connected'] is False, calendar.get('reason'))
                expect(page.locator('.calendar-deadlines')).to_be_visible()
                page.locator('.calendar-deadlines').get_by_role('button', name='Check desktop window layouts', exact=True).click()
                expect(page.locator('[data-task].inspected')).to_contain_text('Check desktop window layouts')
                check('Native local Calendar deadline opens exact task without provider access',
                      page.locator('[data-task].inspected').count() == 1)
                route('calendar', 'Calendar')
                frame('calendar-disconnected')

                route('agents', 'Agents')
                expect(page.locator('.capability-list strong')).to_have_count(6)
                initial_capabilities = page.locator('.capability-list strong').all_inner_texts()
                page.get_by_role('button', name='Next capabilities', exact=True).click()
                next_capabilities = page.locator('.capability-list strong').all_inner_texts()
                check('Native capability pagination displays distinct real registrations',
                      len(next_capabilities) == 6 and next_capabilities != initial_capabilities)
                page.get_by_role('button', name='Previous capabilities', exact=True).click()
                check('Native capability Previous restores first real page',
                      page.locator('.capability-list strong').all_inner_texts() == initial_capabilities)
                check('Native capability region no longer has competing inner scrolling',
                      page.locator('.capability-list').evaluate('(element) => !["auto","scroll"].includes(getComputedStyle(element).overflowY)'))
                frame('agents-real-pagination')

                route('models', 'Models')
                expect(page.locator('.model-entry')).to_have_count(1)
                check('Native model view merges configuration and observation once',
                      page.locator('.model-entry').count() == 1 and 'supervisor · supervisor' not in page.locator('.models-page').inner_text())
                page.get_by_role('button', name='Refresh status', exact=True).click()
                page.locator('.model-connection summary').click()
                expect(page.locator('.model-connection[open]')).to_be_visible()
                check('Native model Connection details exposes actual model identity',
                      'supervisor' in page.locator('.model-connection[open]').inner_text())
                frame('models-real-unified-details')
                page.get_by_role('button', name='Open Mission Control', exact=True).click()
                expect(page.get_by_role('heading', name='Mission Control', exact=True)).to_be_visible()
                check('Native model navigation opens existing Mission Control', page.locator('.screen-mission').is_visible())

                route('activity', 'Activity')
                expect(page.locator('.execution-record').first).to_be_visible(timeout=15000)
                _, agents = request(fixture, 'api/agents')
                encoded = json.dumps(agents)
                check('Recorded workspace audits redact private task content', 'workspace.task.create' in encoded and 'Native independent task' not in encoded and 'Stale native draft' not in encoded)
                check('Recorded workspace audit redacts private note body', 'Private local note body' not in encoded)
                frame('activity-real-redacted-audits')

                # A new actual adapter/store instance performs independent
                # persistent reads. This is a store reopen, not an exe restart.
                from hanni.dashboard.features import DesktopFeatures
                reopened = DesktopFeatures(fixture.config)
                persisted = reopened.productivity()
                check('Fresh adapter reopening same isolated DB preserves saved data', any(item['id'] == task['id'] and item['title'] == 'Concurrent saved task' for item in persisted['tasks']))
                check('Fresh store reopening preserves notification preference/history', reopened.store.notifications()['preferences']['categories']['tasks'] is False
                      and all(item['dismissed'] for item in reopened.store.notifications()['items']))
                check('No fake machine action handlers invoked', not fixture.writes, fixture.writes)

                # Restart the real executable while the isolated original
                # backend/store stays alive, then inspect saved data again.
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                process.wait(timeout=10)
                process = subprocess.Popen(launch_args, stdout=log, stderr=subprocess.STDOUT)
                hwnd = wait_window('HANNI OS Workspace Verification')
                browser = None
                for _ in range(100):
                    try:
                        browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{debug_port}', timeout=1000)
                        break
                    except Exception:
                        time.sleep(.1)
                if browser is None:
                    raise RuntimeError('Restarted actual native WebView unavailable')
                restarted_page = None
                for _ in range(300):
                    pages = [item for context in browser.contexts for item in context.pages]
                    matches = [item for item in pages if item.url.startswith(fixture.url) and '?view=mini' not in item.url]
                    if matches:
                        restarted_page = matches[0]
                        break
                    if pages:
                        pages[0].wait_for_timeout(100)
                if restarted_page is None:
                    raise RuntimeError('Restarted native main page did not load')
                page = restarted_page
                route('tasks', 'Tasks')
                expect(page.locator('[data-task]').filter(has_text='Concurrent saved task')).to_be_visible(timeout=15000)
                check('Actual executable restart reads the same persisted task identity',
                      page.locator('[data-task]').filter(has_text='Concurrent saved task').get_attribute('data-task') == task['id'])
                frame('native-restart-persisted-task')
                page.get_by_role('button', name='New task', exact=True).click()
                dialog = page.get_by_role('dialog', name='New task', exact=True)
                dialog.get_by_label('Title', exact=True).fill('Disconnected retained native draft')
                # Actually stop only this harness-owned temporary HTTP server;
                # no mocked network response or production server is involved.
                fixture.server.shutdown()
                fixture.server.server_close()
                fixture.thread.join(timeout=3)
                dialog.get_by_role('button', name='Save', exact=True).click()
                expect(dialog.get_by_role('alert')).to_be_visible(timeout=15000)
                expect(dialog.get_by_label('Title', exact=True)).to_have_value('Disconnected retained native draft')
                check('Actual disconnected backend preserves native unsaved draft',
                      not any(item['title'] == 'Disconnected retained native draft' for item in fixture.server.features.productivity()['tasks']))
                frame('workspace-actual-backend-disconnected-draft')
                result['passed'] = not result['javascript_errors']
        except Exception as error:
            result['errors'].append(f'{type(error).__name__}: {error}')
        finally:
            if process is not None and process.poll() is None:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    result['errors'].append('Exact review executable failed to exit')
            if 'log' in locals():
                log.close()
            result['passed'] = result['passed'] and not result['errors']
            (args.output/'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'passed':result['passed'], 'checks':len(result['checks']), 'errors':result['errors']}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
