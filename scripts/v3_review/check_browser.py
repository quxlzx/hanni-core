"""Real headless Workflows interactions; no private CRUD replies are fabricated.

Uses the isolated original DashboardServer, WorkflowHub, WorkflowService,
McpHost and ToolRegistry. Scripted two-pass planning replies, synthetic cached
RAM telemetry and one browser-only expiry clock are disclosed seams. File observation, a managed artifact and explicitly approved private test-file writes use original
file.stat/read/write handlers against isolated files. The fixture-only original
host action whitelist permits file.write; read_only stays true, and the original
registry's owner/risk/confirmation gates remain unchanged. No production policy
is changed. No live model/provider/app/voice/SSH
or remote power operation runs. Browser images are debugging evidence only,
not independent native visual acceptance. Run only after root's freeze/GO.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/desktop_review'))
sys.path.insert(0, str(ROOT))
from fixture import ReviewFixture
from scripts.v3_review.service_fixture import EmptyProviderVault
from scripts.v3_review.fixtures import HandlerLedger
from hanni.mcp.host import McpHost
from hanni.reliability.execution import close_service


def runtime_manifest():
    files = {str(path.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted((ROOT / 'src/hanni').rglob('*.py'))
             if 'evals' not in path.relative_to(ROOT / 'src/hanni').parts}
    encoded = json.dumps(files, sort_keys=True, separators=(',', ':')).encode()
    return {'sha256': hashlib.sha256(encoded).hexdigest(), 'files': files,
            'scope': 'Production Python runtime only; no evaluation, holdout, model weights or private stores.'}


def wait_state(page, path, token, states, *, timeout=20):
    """Await each genuine private response; async wait_for_function predicates do not poll."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = page.evaluate("""async ({path,token}) => {
            const response = await fetch(path,{headers:{'X-Hanni-Token':token}});
            if (!response.ok) throw new Error(`Actual workflow read failed: HTTP ${response.status}`);
            return await response.json();
        }""", {'path': path, 'token': token})
        if last.get('workflow', {}).get('status') in states:
            return last
        page.wait_for_timeout(250)
    workflow = (last or {}).get('workflow') or {}
    raise AssertionError(f'Actual workflow did not reach {sorted(states)} within {timeout}s: '
                         f'status={workflow.get("status")}, counts={workflow.get("counts")}, '
                         f'error={workflow.get("error")}')


def wait_completed(page, path, token, *, timeout=20):
    return wait_state(page, path, token, {'completed'}, timeout=timeout)


class QueuePlanClient:
    """Scripted planning through the original client interface, not an executor."""
    def __init__(self):
        self.replies = []
        self.calls = 0

    def file_check(self, path):
        self.replies = [
            {'summary': 'Check this isolated file and record its existence.',
             'unsupported_reason': None, 'steps': [{
                 'step_id': 'check', 'description': f'Check whether file {path} exists and hash its bytes',
                 'kind': 'tool', 'dependencies': [], 'required': True,
                 'criteria': [{'operator': 'equals', 'path': '/data/exists', 'expected': True}]}]},
            {'unsupported_reason': None, 'steps': [{'step_id': 'check', 'capability_id': 'file.stat',
                                                    'arguments': {'path': str(path), 'hash': True}}]},
        ]

    def chat(self, messages, **kwargs):
        if not self.replies:
            raise AssertionError('The controlled client received an unexpected inference request')
        self.calls += 1
        response = self.replies.pop(0)
        if callable(response):
            response = response(messages, kwargs)
        return json.dumps(response)

    def file_artifact(self, path):
        self.replies = [
            {'summary': 'Read the isolated file and save its exact text as a managed report.', 'unsupported_reason': None,
             'steps': [
                 {'step_id': 'read', 'description': f'Read text file {path}', 'kind': 'tool', 'dependencies': [],
                  'required': True, 'criteria': [{'operator': 'equals', 'path': '/data/text', 'expected': 'Original fixture content\n'}]},
                 {'step_id': 'save', 'description': 'Save the verified source text as a managed workflow report', 'kind': 'artifact',
                  'dependencies': ['read'], 'required': True,
                  'criteria': [{'operator': 'equals', 'path': '/data/chars', 'expected': len('Original fixture content\n')}]},
             ]},
            lambda messages, kwargs: {'unsupported_reason': None, 'steps': [
                {'step_id': 'read', 'capability_id': 'file.read', 'arguments': {'path': str(path)}},
                {'step_id': 'save', 'capability_id': 'file.write', 'arguments': {
                    'path': str(Path(json.loads(messages[-1]['content'])['artifact_root']) / 'browser-report.txt'),
                    'text': {'$ref': {'step_id': 'read', 'path': '/data/text', 'type': 'string'}},
                }},
            ]},
        ]

    def sensitive_write(self, path, text):
        self.replies = [
            {'summary': 'Create the exact isolated text file after explicit action review.', 'unsupported_reason': None,
             'steps': [{'step_id': 'write', 'description': f'Create a local text file at {path}', 'kind': 'tool', 'dependencies': [],
                        'required': True, 'criteria': [{'operator': 'equals', 'path': '/data/chars', 'expected': len(text)}]}]},
            {'unsupported_reason': None, 'steps': [{'step_id': 'write', 'capability_id': 'file.write',
                                                    'arguments': {'path': str(path), 'text': text}}]},
        ]


class WorkflowBrowserFixture(ReviewFixture):
    def __enter__(self):
        super().__enter__()
        try:
            self.sample['activity'] = {'input_level': 0, 'speaking': False, 'microphone_active': False}
            self.registry = self.server.features.registry
            self.registry.google_access._vault = EmptyProviderVault()
            self.ledger = HandlerLedger()
            self.ledger.observe(self.registry, 'file.write')
            self.read_failure_path = None

            def controlled_read_failure(arguments, _context, _request):
                if self.read_failure_path is not None and Path(arguments['path']) == self.read_failure_path:
                    self.read_failure_path = None
                    raise OSError('Controlled fixture read failure before original stat.')

            self.ledger.observe(self.registry, 'file.stat', before=controlled_read_failure)
            self.host = McpHost(self.registry, read_only=True, allowed_actions=('file.write',))
            self.client = QueuePlanClient()
            self.source = Path(self.temporary.name) / 'browser-source.txt'
            self.source.write_bytes(b'Original fixture content\n')
            self.workflow_outage = False
            self.server.workflows.require()  # Actual cold history, no attached executor.
            fixture = self
            original_handler = self.server.RequestHandlerClass

            class AvailabilityHandler(original_handler):
                def do_GET(self):
                    if self.path.split('?', 1)[0].startswith('/api/workflows') and fixture.workflow_outage:
                        if not self._allowed():
                            return
                        if self.headers.get('X-Hanni-Token') != fixture.hub.token:
                            return self._send(403, b'{"error":"Dashboard token required"}')
                        return self._send(503, b'{"error":"Controlled workflow endpoint unavailable"}')
                    return super().do_GET()

            self.server.RequestHandlerClass = AvailabilityHandler
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def attach(self):
        self.server.workflows.attach_controller(self.registry, self.client, self.host)
        if not self.server.workflows.runner_attached:
            raise AssertionError('The actual workflow runner did not attach')

    def detach(self):
        self.server.workflows.detach_controller(self.registry)

    def request(self, route='/api/workflows', *, token=True):
        headers = {'X-Hanni-Token': self.hub.token} if token else {}
        request = urllib.request.Request(self.url.rstrip('/') + route, headers=headers)
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)

    def __exit__(self, *exc):
        server = getattr(self, 'server', None)
        if server is not None:
            server.workflows.close()
        if getattr(self, 'config', None) is not None:
            close_service(self.config.paths.data_dir)
        return super().__exit__(*exc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--browser-channel', default='msedge')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = {'passed': False, 'checks': [], 'errors': [], 'javascript_errors': [],
              'external_requests': [], 'visual_score': None, 'disclosure': __doc__,
              'runtime_manifest': runtime_manifest(),
              'artifact_sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in {
                  'app.js': ROOT / 'src/hanni/dashboard/static/app.js',
                  'style.css': ROOT / 'src/hanni/dashboard/static/style.css',
                  'workflow_types.ts': ROOT / 'frontend/src/workflow_types.ts',
                  'workflows.tsx': ROOT / 'frontend/src/workflows.tsx',
                  'check_browser.py': Path(__file__),
              }.items()}}

    def check(name, condition=True, evidence=None):
        result['checks'].append({'name': name, 'passed': bool(condition), 'evidence': evidence})
        if not condition:
            raise AssertionError(name)

    with WorkflowBrowserFixture() as fixture:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=args.browser_channel, headless=True)
            context = browser.new_context(viewport={'width': 1280, 'height': 800})
            page = context.new_page()
            page.set_default_timeout(15000)
            page.on('pageerror', lambda error: result['javascript_errors'].append(str(error)))
            context.on('request', lambda request: result['external_requests'].append(request.url)
                    if request.url.startswith(('http:', 'https:')) and not request.url.startswith(fixture.url) else None)
            posted = []
            api_url = fixture.url.rstrip('/') + '/api/workflows'
            context.on('request', lambda request: posted.append(request.post_data_json)
                    if request.method == 'POST' and request.url == api_url else None)
            try:
                try:
                    fixture.request(token=False)
                except urllib.error.HTTPError as error:
                    check('Workflow history requires original private token', error.code == 403)
                else:
                    check('Workflow history requires original private token', False)

                fixture.workflow_outage = True
                page.goto(fixture.url + '#workflows')
                expect(page.get_by_text('Workflow history could not be loaded. Refresh when the connection is available.', exact=True)).to_be_visible()
                expect(page.get_by_role('heading', name='No saved workflows', exact=True)).to_have_count(0)
                expect(page.get_by_role('button', name='New goal', exact=True)).to_be_disabled()
                check('First-fetch failure is an error with disabled creation, not a false empty state')

                fixture.workflow_outage = False
                page.get_by_role('button', name='Refresh workflows', exact=True).click()
                expect(page.get_by_role('heading', name='No saved workflows', exact=True)).to_be_visible()
                expect(page.get_by_role('button', name='New goal', exact=True)).to_be_disabled()
                check('Actual unattached backend exposes empty saved history without fake execution')

                fixture.attach()
                page.get_by_role('button', name='Refresh workflows', exact=True).click()
                expect(page.get_by_role('button', name='New goal', exact=True)).to_be_enabled()
                page.get_by_role('button', name='New goal', exact=True).click()
                dialog = page.get_by_role('dialog', name='New workflow goal', exact=True)
                expect(dialog.get_by_label('Autonomy mode', exact=True)).to_have_value('assisted')
                expect(dialog.get_by_label('Goal', exact=True)).to_have_attribute('maxlength', str(fixture.config.hanni.workflows.max_goal_chars))
                for index in range(8):
                    page.keyboard.press('Tab')
                    blocked = page.evaluate("""() => { const button = document.querySelector('.screen-heading button'); button.focus(); return document.activeElement !== button && Boolean(document.querySelector('dialog:modal')); }""")
                    check(f'Goal dialog keeps background inert during keyboard cycle {index + 1}', blocked)
                page.keyboard.press('Escape')
                expect(dialog).not_to_be_visible()
                check('Escape cancels the goal form without a private mutation', not posted and fixture.request()['items'] == [])

                fixture.client.file_check(fixture.source)
                goal = f'Check whether file {fixture.source} exists and hash its bytes'
                page.get_by_role('button', name='New goal', exact=True).click()
                dialog = page.get_by_role('dialog', name='New workflow goal', exact=True)
                dialog.get_by_label('Goal', exact=True).fill(goal)
                fault_used = False

                def abort_first_submission(route):
                    nonlocal fault_used
                    if route.request.method == 'POST' and route.request.post_data_json['operation'] == 'goal.submit' and not fault_used:
                        response = route.fetch()
                        if response.status != 200:
                            raise AssertionError('The genuine goal submission did not succeed before fault injection')
                        fault_used = True
                        route.abort('failed')
                    else:
                        route.continue_()

                page.route(api_url, abort_first_submission)
                dialog.get_by_role('button', name='Create workflow', exact=True).evaluate('(button) => { button.click(); button.click(); }')
                expect(dialog.get_by_role('alert')).to_be_visible()
                check('Two rapid goal-button activations dispatch one pending submission', len([row for row in posted if row['operation'] == 'goal.submit']) == 1)
                check('Ambiguous response keeps draft after actual durable submission', fault_used and len(fixture.request()['items']) == 1)
                page.unroute(api_url, abort_first_submission)
                dialog.get_by_role('button', name='Create workflow', exact=True).click()
                expect(dialog).not_to_be_visible()
                expect(page.locator('.workflow-detail')).to_be_visible()
                submissions = [row for row in posted if row['operation'] == 'goal.submit']
                check('Identical explicit retry reuses UUID without creating duplicate workflow',
                      len(submissions) == 2 and submissions[0]['id'] == submissions[1]['id'] and len(fixture.request()['items']) == 1)
                workflow_id = fixture.request()['items'][0]['workflow_id']
                expect(page.get_by_role('button', name='Review plan approval', exact=True)).to_be_enabled(timeout=20000)
                check('Two original client planning passes produce an approval-bound persisted plan', fixture.client.calls == 2)
                awaiting = fixture.request(f'/api/workflows/{workflow_id}')['workflow']
                page.wait_for_function("""async ({id,token}) => { const response=await fetch('/api/notifications',{headers:{'X-Hanni-Token':token}}); const body=await response.json(); return body.items?.some(item=>item.target?.screen==='workflows' && item.target?.id===id); }""",
                                       arg={'id': workflow_id, 'token': fixture.hub.token}, timeout=10000, polling=250)
                events = fixture.request('/api/notifications')['items']
                notification = next((event for event in events if event['target'].get('screen') == 'workflows' and event['target'].get('id') == workflow_id), None)
                check('The real workflow service emits an existing-store notification targeting its exact workflow', notification is not None)
                page.goto(fixture.url + '#notifications')
                item = page.locator('.notification-group-item').filter(has=page.get_by_text(notification['title'], exact=True))
                item.get_by_role('button', name='Inspect event', exact=True).click()
                expect(page.locator('.workflow-detail')).to_have_attribute('data-workflow-id', workflow_id)
                check('Notification Inspect opens its own exact workflow and consumes the one-shot target',
                      page.evaluate("sessionStorage.getItem('hanni-inspect-target')") is None)
                after_inspect = fixture.request(f'/api/workflows/{workflow_id}')['workflow']
                check('Reading an approval notification grants no approval and executes no step',
                      after_inspect['status'] == awaiting['status'] == 'awaiting_plan_approval' and
                      after_inspect['revision'] == awaiting['revision'] and not after_inspect['invocations'])

                expiry_context = browser.new_context(viewport={'width': 1280, 'height': 800})
                expiry_context.on('request', lambda request: posted.append(request.post_data_json)
                                  if request.method == 'POST' and request.url == api_url else None)
                expiry_context.on('request', lambda request: result['external_requests'].append(request.url)
                                  if request.url.startswith(('http:', 'https:')) and not request.url.startswith(fixture.url) else None)
                try:
                    expiry_page = expiry_context.new_page()
                    expiry_page.set_default_timeout(15000)
                    expiry_page.on('pageerror', lambda error: result['javascript_errors'].append(str(error)))
                    expiry_page.goto(fixture.url + '#workflows')
                    expiry_page.locator(f'.workflow-row[data-workflow-id="{workflow_id}"]').click()
                    expiry_page.get_by_role('button', name='Review plan approval', exact=True).click()
                    expiry_review = expiry_page.get_by_role('dialog', name='Approve this workflow plan?', exact=True)
                    plan_record = next(record for record in awaiting['approvals'] if record['kind'] == 'plan' and record['state'] == 'pending')
                    future = datetime.fromisoformat(plan_record['expires_at'].replace('Z', '+00:00')).timestamp() + 1
                    # Playwright Clock is context-wide. Its dedicated context
                    # cannot change the main browser clock or actual backend.
                    expiry_page.clock.set_system_time(datetime.fromtimestamp(future, timezone.utc))
                    confirmation = expiry_review.get_by_role('button', name='Approve this plan', exact=True)
                    if confirmation.is_enabled():
                        confirmation.click()
                    expect(confirmation).to_be_disabled()
                    expect(expiry_review.get_by_role('alert')).to_contain_text('expired')
                    check('Click-time client expiry check blocks a stale timer window without an approval POST',
                          not any(row['operation'] == 'approve_plan' for row in posted) and
                          fixture.request(f'/api/workflows/{workflow_id}')['workflow']['revision'] == awaiting['revision'])
                    main_clock = page.evaluate('Date.now()') / 1000
                    check('Dedicated browser expiry context leaves the main clock before the real approval expiry', main_clock < future - 1,
                          {'main_epoch_seconds': main_clock, 'expiry_context_future_seconds': future})
                finally:
                    expiry_context.close()
                page.get_by_role('button', name='Review plan approval', exact=True).click()
                review = page.get_by_role('dialog', name='Approve this workflow plan?', exact=True)
                expect(review.get_by_role('heading', name='Planned arguments', exact=True)).to_be_visible()
                inspected = [json.loads(value) for value in review.locator('.workflow-review-plan pre').all_text_contents()]
                check('Plan review preserves exact original planned path/hash arguments and completion criteria',
                      {'path': str(fixture.source), 'hash': True} in inspected and
                      [{'operator': 'equals', 'path': '/data/exists', 'expected': True}] in inspected)
                fixture.workflow_outage = True
                expect(review.get_by_role('button', name='Approve this plan', exact=True)).to_be_disabled()
                expect(review.get_by_role('status')).to_contain_text('Confirmation is disabled')
                check('A genuine private-read outage disables and explains confirmation inside the open modal',
                      not any(row['operation'] == 'approve_plan' for row in posted))
                fixture.workflow_outage = False
                expect(review.get_by_role('button', name='Approve this plan', exact=True)).to_be_enabled()
                other = context.new_page()
                other.set_default_timeout(15000)
                other.on('pageerror', lambda error: result['javascript_errors'].append(str(error)))
                other.goto(fixture.url + '#workflows')
                other.locator(f'.workflow-row[data-workflow-id="{workflow_id}"]').click()
                other.get_by_role('button', name='Review plan approval', exact=True).click()
                other_review = other.get_by_role('dialog', name='Approve this workflow plan?', exact=True)
                other_review.get_by_role('button', name='Approve this plan', exact=True).click()
                expect(other_review).not_to_be_visible()
                expect(review.get_by_role('button', name='Approve this plan', exact=True)).to_be_disabled()
                expect(review.get_by_role('alert')).to_contain_text('changed or expired')
                check('A real approval in another window invalidates the captured review without rebinding it')
                review.get_by_role('button', name='Keep reviewing', exact=True).click()
                expect(review).not_to_be_visible()
                start = other.get_by_role('button', name='Start', exact=True)
                if start.count() and start.is_enabled():
                    start.click()
                wait_completed(page, f'/api/workflows/{workflow_id}', fixture.hub.token)
                completed = fixture.request(f'/api/workflows/{workflow_id}')['workflow']
                check('Original file handler plus actual acceptance evidence completes the read workflow',
                      completed['status'] == 'completed' and completed['counts']['verified'] == 1 and
                      completed['steps'][0]['verification']['status'] == 'VERIFIED' and fixture.source.read_bytes() == b'Original fixture content\n',
                      {'status': completed['status'], 'counts': completed['counts'],
                       'step_status': completed['steps'][0]['status'],
                       'verification': completed['steps'][0]['verification'],
                       'source_sha256': hashlib.sha256(fixture.source.read_bytes()).hexdigest(),
                       'source_hex': fixture.source.read_bytes().hex(),
                       'invocations': completed['invocations']})
                other.close()
                expect(page.get_by_text('Elapsed since start:', exact=False)).to_be_visible()
                page.get_by_text('Checkpoints and tool activity', exact=True).click()
                expect(page.get_by_role('heading', name='Tool invocations', exact=True)).to_be_visible()
                check('Detail exposes actual checkpoint and original capability invocation history', bool(completed['checkpoints']) and bool(completed['invocations']))
                page.get_by_role('button', name='Back to workflows', exact=True).click()
                expect(page.locator('.workflow-row')).to_have_count(1)
                page.get_by_label('Workflow status', exact=True).select_option('completed')
                expect(page.locator('.workflow-row')).to_have_count(1)
                page.get_by_label('Search workflows', exact=True).fill('No such fixture goal')
                expect(page.get_by_role('heading', name='No workflows match this view', exact=True)).to_be_visible()
                page.get_by_label('Search workflows', exact=True).fill('')
                check('Actual terminal-state filtering and local search preserve recorded history')

                fixture.client.file_artifact(fixture.source)
                page.get_by_role('button', name='New goal', exact=True).click()
                artifact_form = page.get_by_role('dialog', name='New workflow goal', exact=True)
                artifact_form.get_by_label('Goal', exact=True).fill(f'Read text file {fixture.source} and save its exact text as a managed report')
                artifact_form.get_by_role('button', name='Create workflow', exact=True).click()
                expect(artifact_form).not_to_be_visible()
                expect(page.get_by_role('button', name='Review plan approval', exact=True)).to_be_enabled(timeout=20000)
                artifact_id = page.locator('.workflow-detail').get_attribute('data-workflow-id')
                page.get_by_role('button', name='Review plan approval', exact=True).click()
                artifact_review = page.get_by_role('dialog', name='Approve this workflow plan?', exact=True)
                planned = [json.loads(value) for value in artifact_review.locator('.workflow-review-plan pre').all_text_contents()]
                check('Managed artifact review preserves the typed prerequisite reference as planned input',
                      any(isinstance(value, dict) and value.get('text') == {'$ref': {'step_id': 'read', 'path': '/data/text', 'type': 'string'}} for value in planned))
                artifact_review.get_by_role('button', name='Approve this plan', exact=True).click()
                expect(artifact_review).not_to_be_visible()
                if page.get_by_role('button', name='Start', exact=True).is_enabled():
                    page.get_by_role('button', name='Start', exact=True).click()
                wait_completed(page, f'/api/workflows/{artifact_id}', fixture.hub.token)
                artifact_workflow = fixture.request(f'/api/workflows/{artifact_id}')['workflow']
                saved_step = next(step for step in artifact_workflow['steps'] if step['step_id'] == 'save')
                artifact_path = Path(saved_step['resolved_arguments']['path']).resolve()
                check('Artifact readback is confined to the actual isolated fixture root', artifact_path.is_relative_to(Path(fixture.temporary.name).resolve()))
                artifact = next(record for record in artifact_workflow['artifacts'] if record['step_id'] == 'save')
                check('Actual original write stores resolved prerequisite text and the real byte digest',
                      artifact_workflow['counts']['verified'] == 2 and artifact_path.read_text(encoding='utf-8') == fixture.source.read_text(encoding='utf-8') and
                      hashlib.sha256(artifact_path.read_bytes()).hexdigest() == artifact['sha256'] and artifact['verified'] is True)
                expect(page.get_by_role('button', name='View output', exact=True)).to_be_visible()
                before_output = len(artifact_workflow['invocations'])
                page.get_by_role('button', name='View output', exact=True).click()
                output_dialog = page.get_by_role('dialog', name='Output: browser-report.txt', exact=True)
                expect(output_dialog.locator('.workflow-output-text')).to_have_text(artifact['excerpt'])
                output_dialog.get_by_role('button', name='Close output', exact=True).click()
                check('View output renders the actual saved excerpt without another tool invocation',
                      len(fixture.request(f'/api/workflows/{artifact_id}')['workflow']['invocations']) == before_output)
                page.get_by_role('button', name='Back to workflows', exact=True).click()
                page.get_by_label('Workflow status', exact=True).select_option('completed')
                expect(page.locator('.workflow-row')).to_have_count(2)

                target = Path(fixture.temporary.name) / 'approval-target.txt'
                target_text = 'Explicitly approved fixture report\n'

                def sensitive_goal():
                    fixture.client.sensitive_write(target, target_text)
                    page.get_by_role('button', name='New goal', exact=True).click()
                    form = page.get_by_role('dialog', name='New workflow goal', exact=True)
                    form.get_by_label('Goal', exact=True).fill(f'Create a local text file at {target} with the explicitly reviewed fixture text')
                    form.get_by_role('button', name='Create workflow', exact=True).click()
                    expect(form).not_to_be_visible()
                    expect(page.get_by_role('button', name='Review plan approval', exact=True)).to_be_enabled(timeout=20000)
                    key = page.locator('.workflow-detail').get_attribute('data-workflow-id')
                    page.get_by_role('button', name='Review plan approval', exact=True).click()
                    modal = page.get_by_role('dialog', name='Approve this workflow plan?', exact=True)
                    modal.get_by_role('button', name='Approve this plan', exact=True).click()
                    expect(modal).not_to_be_visible()
                    if page.get_by_role('button', name='Start', exact=True).is_enabled():
                        page.get_by_role('button', name='Start', exact=True).click()
                    expect(page.get_by_role('button', name='Review action', exact=True)).to_be_enabled(timeout=20000)
                    return key, fixture.request(f'/api/workflows/{key}')['workflow']

                write_count = fixture.ledger.entries('file.write')
                rejected_id, pending_action = sensitive_goal()
                check('A sensitive personal-file write waits for exact action approval despite approved plan and allowed fixture profile',
                      pending_action['status'] == 'awaiting_step_approval' and not target.exists() and fixture.ledger.entries('file.write') == write_count)
                page.get_by_role('button', name='Review action', exact=True).click()
                action_dialog = page.get_by_role('dialog', name='Approve this workflow action?', exact=True)
                exact_arguments = json.loads(action_dialog.locator('.workflow-approval-arguments').inner_text())
                check('Sensitive approval displays actual fully resolved target/text and authoritative risk',
                      exact_arguments == {'path': str(target), 'text': target_text} and pending_action['steps'][0]['risk_level'] == 2)
                page.keyboard.press('Escape')
                expect(action_dialog).not_to_be_visible()
                check('Escape closes action review without granting approval or dispatching a handler',
                      fixture.ledger.entries('file.write') == write_count and not target.exists())
                page.get_by_role('button', name='Reject', exact=True).click()
                rejection = page.get_by_role('dialog', name='Reject this action?', exact=True)
                rejection.get_by_role('button', name='Reject this action', exact=True).click()
                expect(rejection).not_to_be_visible()
                rejected = fixture.request(f'/api/workflows/{rejected_id}')['workflow']
                check('Real action rejection persists and performs no side effect',
                      any(record['step_id'] == 'write' and record['state'] == 'rejected' for record in rejected['approvals']) and
                      not target.exists() and fixture.ledger.entries('file.write') == write_count)
                page.get_by_role('button', name='Back to workflows', exact=True).click()

                approved_id, pending_action = sensitive_goal()
                pending_record = next(record for record in pending_action['approvals'] if record['step_id'] == 'write' and record['state'] == 'pending')
                page.get_by_role('button', name='Review action', exact=True).click()
                approved_review = page.get_by_role('dialog', name='Approve this workflow action?', exact=True)
                approval_fault_used = False

                def abort_approved_action_response(route):
                    nonlocal approval_fault_used
                    if route.request.method == 'POST' and route.request.post_data_json['operation'] == 'approve_step' and not approval_fault_used:
                        actual = route.fetch()
                        if actual.status != 200:
                            raise AssertionError('The genuine action approval failed before response-fault injection')
                        approval_fault_used = True
                        route.abort('failed')
                    else:
                        route.continue_()

                page.route(api_url, abort_approved_action_response)
                approved_review.get_by_role('button', name='Approve this action', exact=True).click()
                expect(approved_review.get_by_role('alert').filter(has_text='identical retry')).to_be_visible()
                page.unroute(api_url, abort_approved_action_response)
                wait_completed(page, f'/api/workflows/{approved_id}', fixture.hub.token)
                expect(approved_review.get_by_role('button', name='Approve this action', exact=True)).to_be_disabled()
                approved = fixture.request(f'/api/workflows/{approved_id}')['workflow']
                approved_post = next(row for row in posted if row['operation'] == 'approve_step' and row['data']['workflow_id'] == approved_id)
                binding = {field: pending_record[field] for field in ('approval_id', 'step_id', 'plan_hash', 'argument_hash', 'definition_hash')}
                check('Actual approval POST preserves the exact reviewed record and revision without sending replacement arguments',
                      approved_post['data'] == {'workflow_id': approved_id, 'expected_revision': pending_action['revision'], **binding})
                check('Lost approval response reconciles actual completion without replaying the sensitive write',
                      approval_fault_used and approved['counts']['verified'] == 1 and fixture.ledger.entries('file.write') == write_count + 1 and
                      target.read_text(encoding='utf-8') == target_text and
                      len([row for row in posted if row['operation'] == 'approve_step' and row['data']['workflow_id'] == approved_id]) == 1)
                approved_review.get_by_role('button', name='Keep reviewing', exact=True).click()
                page.get_by_role('button', name='Back to workflows', exact=True).click()
                page.get_by_label('Workflow status', exact=True).select_option('completed')
                expect(page.locator('.workflow-row')).to_have_count(3)

                # Actual pending plan revocation; inspecting/cancelling the modal must not grant authority.
                fixture.client.file_check(fixture.source)
                page.get_by_role('button', name='New goal', exact=True).click()
                revoke_form = page.get_by_role('dialog', name='New workflow goal', exact=True)
                revoke_form.get_by_label('Goal', exact=True).fill(f'Check file {fixture.source} before an explicit review')
                revoke_form.get_by_role('button', name='Create workflow', exact=True).click()
                expect(revoke_form).not_to_be_visible()
                expect(page.get_by_role('button', name='Review plan approval', exact=True)).to_be_enabled(timeout=20000)
                revoke_id = page.locator('.workflow-detail').get_attribute('data-workflow-id')
                revoke_before = fixture.request(f'/api/workflows/{revoke_id}')['workflow']
                revoke_record = next(item for item in revoke_before['approvals'] if item['kind'] == 'plan' and item['state'] == 'pending')
                page.locator(f'[data-approval-id="{revoke_record["approval_id"]}"]').get_by_role('button', name='Revoke approval', exact=True).click()
                revoke_modal = page.get_by_role('dialog', name='Revoke this approval?', exact=True)
                expect(revoke_modal).to_contain_text('Completed work is not undone')
                page.keyboard.press('Escape')
                expect(revoke_modal).not_to_be_visible()
                check('Escape from approval revocation changes no actual grant or workflow revision',
                      fixture.request(f'/api/workflows/{revoke_id}')['workflow']['revision'] == revoke_before['revision'])
                page.locator(f'[data-approval-id="{revoke_record["approval_id"]}"]').get_by_role('button', name='Revoke approval', exact=True).click()
                page.get_by_role('dialog', name='Revoke this approval?', exact=True).get_by_role('button', name='Revoke this approval', exact=True).click()
                revoked = wait_state(page, f'/api/workflows/{revoke_id}', fixture.hub.token, {'paused'})['workflow']
                check('Actual pending plan revocation persists its exact ID and admits no handler',
                      any(item['approval_id'] == revoke_record['approval_id'] and item['state'] == 'revoked' for item in revoked['approvals']) and
                      not revoked['invocations'] and revoked['pause_requested'])
                expect(page.locator('.workflow-detail > .screen-heading p')).to_contain_text('Paused')
                expect(page.locator('.workflow-detail').get_by_text('Pause requested.', exact=False)).to_have_count(0)
                expect(page.locator('.workflow-detail').get_by_text('The backend will stop at a safe execution boundary.', exact=False)).to_have_count(0)
                check('A settled revoked workflow displays Paused without a false pending pause notice')
                page.get_by_role('button', name='Back to workflows', exact=True).click()

                # The original stat handler observes one controlled pre-handler failure;
                # explicit safe retry keeps the same exact prepared arguments and original gates.
                fixture.read_failure_path = fixture.source
                fixture.client.file_check(fixture.source)
                page.get_by_role('button', name='New goal', exact=True).click()
                retry_form = page.get_by_role('dialog', name='New workflow goal', exact=True)
                retry_form.get_by_label('Goal', exact=True).fill(f'Check file {fixture.source} with explicit safe read recovery')
                retry_form.get_by_role('button', name='Create workflow', exact=True).click()
                expect(retry_form).not_to_be_visible()
                expect(page.get_by_role('button', name='Review plan approval', exact=True)).to_be_enabled(timeout=20000)
                retry_id = page.locator('.workflow-detail').get_attribute('data-workflow-id')
                page.get_by_role('button', name='Review plan approval', exact=True).click()
                page.get_by_role('dialog', name='Approve this workflow plan?', exact=True).get_by_role('button', name='Approve this plan', exact=True).click()
                expect(page.get_by_role('dialog', name='Approve this workflow plan?', exact=True)).not_to_be_visible()
                if page.get_by_role('button', name='Start', exact=True).is_enabled():
                    page.get_by_role('button', name='Start', exact=True).click()
                retry_before = wait_state(page, f'/api/workflows/{retry_id}', fixture.hub.token, {'blocked'})['workflow']
                page.locator('.workflow-step[data-step-id="check"] > summary').click()
                expect(page.get_by_role('button', name='Retry this safe failed step', exact=True)).to_be_enabled(timeout=20000)
                check('A genuine failed opted-in builtin read exposes only its server-authorized safe retry',
                      retry_before['steps'][0]['status'] == 'failed' and len(retry_before['invocations']) == 1 and
                      not retry_before['invocations'][0]['write'] and retry_before['invocations'][0]['retry_safe'])
                page.get_by_role('button', name='Retry this safe failed step', exact=True).click()
                retry_modal = page.get_by_role('dialog', name='Retry this safe step?', exact=True)
                expect(retry_modal).to_contain_text('Uncertain side effects are not replayed')
                retry_modal.get_by_role('button', name='Retry this safe step', exact=True).click()
                expect(retry_modal).not_to_be_visible()
                wait_completed(page, f'/api/workflows/{retry_id}', fixture.hub.token)
                retried = fixture.request(f'/api/workflows/{retry_id}')['workflow']
                retry_post = next(row for row in posted if row['operation'] == 'retry_safe' and row['data']['workflow_id'] == retry_id)
                check('Explicit safe retry performs a second original read with unchanged captured arguments and verified outcome',
                      retry_post['data'] == {'workflow_id': retry_id, 'expected_revision': retry_before['revision'], 'step_id': 'check'} and
                      len(retried['invocations']) == 2 and
                      retried['invocations'][0]['argument_hash'] == retried['invocations'][1]['argument_hash'] and
                      retried['counts']['verified'] == 1 and fixture.source.read_bytes() == b'Original fixture content\n')
                page.get_by_role('button', name='Back to workflows', exact=True).click()

                # Cancel a still-unapproved sensitive action. No production handler is interrupted or launched.
                target = Path(fixture.temporary.name) / 'cancel-target.txt'
                cancel_write_count = fixture.ledger.entries('file.write')
                cancel_id, cancel_before = sensitive_goal()
                page.get_by_role('button', name='Cancel workflow', exact=True).click()
                cancel_modal = page.get_by_role('dialog', name='Cancel workflow?', exact=True)
                expect(cancel_modal).to_contain_text('A noninterruptible action may continue')
                cancel_modal.get_by_role('button', name='Cancel workflow', exact=True).click()
                expect(cancel_modal).not_to_be_visible()
                cancelled = wait_state(page, f'/api/workflows/{cancel_id}', fixture.hub.token, {'cancelled'})['workflow']
                check('Pending sensitive-action cancellation persists without granting or replaying the action',
                      cancel_before['status'] == 'awaiting_step_approval' and cancelled['cancel_requested'] and
                      not target.exists() and fixture.ledger.entries('file.write') == cancel_write_count and
                      not cancelled['invocations'])
                expect(page.locator('.workflow-detail > .screen-heading p')).to_contain_text('Cancelled')
                expect(page.locator('.workflow-detail').get_by_text('Cancellation requested.', exact=False)).to_have_count(0)
                expect(page.locator('.workflow-detail').get_by_text('The backend will stop at a safe execution boundary.', exact=False)).to_have_count(0)
                check('A settled cancelled workflow displays Cancelled without a false pending cancellation notice')
                page.get_by_role('button', name='Back to workflows', exact=True).click()
                page.get_by_label('Workflow status', exact=True).select_option('completed')
                expect(page.locator('.workflow-row')).to_have_count(4)

                fixture.workflow_outage = True
                page.get_by_role('button', name='Refresh workflows', exact=True).click()
                expect(page.get_by_text('Displayed history may be stale.', exact=False)).to_be_visible()
                expect(page.locator('.workflow-row')).to_have_count(4)
                expect(page.get_by_role('button', name='New goal', exact=True)).to_be_disabled()
                check('A genuine private endpoint outage retains known history and disables mutations')
                fixture.workflow_outage = False
                fixture.detach()
                page.get_by_role('button', name='Refresh workflows', exact=True).click()
                expect(page.get_by_role('button', name='New goal', exact=True)).to_be_disabled()
                expect(page.locator('.workflow-row')).to_have_count(4)
                check('Actual runner detachment retains history without implying work continues', not fixture.request()['runner_attached'])

                for width in [760, 800, 900, 1000, 1079, 1200, 1280, 1366, 1440, 1600, 1920, 2560]:
                    page.set_viewport_size({'width': width, 'height': 650 if width < 1280 else 900})
                    overflow = page.evaluate('document.documentElement.scrollWidth > innerWidth')
                    check(f'Overview has no horizontal page overflow at CSS width {width}', not overflow)
                check('No unexpected browser JavaScript errors', not result['javascript_errors'], result['javascript_errors'])
                check('No browser requests to nonlocal integrations', not result['external_requests'], result['external_requests'])
                check('No remote power, terminal, audio or provider mutation', not fixture.writes)
                check('Production runtime remains frozen throughout the browser cycle', runtime_manifest()['sha256'] == result['runtime_manifest']['sha256'])
                result['workflow_id'] = workflow_id
                result['artifact_workflow_id'] = artifact_id
                result['rejected_workflow_id'] = rejected_id
                result['approved_workflow_id'] = approved_id
                result['revoked_workflow_id'] = revoke_id
                result['retried_workflow_id'] = retry_id
                result['cancelled_workflow_id'] = cancel_id
                result['passed'] = True
            except BaseException as error:
                result['errors'].append(f'{type(error).__name__}: {error}')
                page.screenshot(path=str(output / 'browser-debug-failure.png'), full_page=True)
            finally:
                result['private_operations'] = [{'id': row['id'], 'operation': row['operation']} for row in posted]
                (output / 'browser-review.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
                context.close()
                browser.close()
    print(json.dumps({'passed': result['passed'], 'checks': len(result['checks']), 'errors': result['errors'], 'output': str(output)}))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
