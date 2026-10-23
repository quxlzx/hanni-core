"""Independent compact Workflows review. All displayed collaboration is a fixture.

No fixture output is inference or correctness evidence. Original dashboard static
files, private token, local font and browser behavior remain real.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts/desktop_review')]
from phase_fixture import PhaseReviewFixture
from hanni.reliability.execution import close_service
from playwright.sync_api import sync_playwright, expect


def display_fixture():
    now = datetime.now(timezone.utc).isoformat()
    evidence = {'status': 'VERIFIED', 'scope': 'Disclosed display fixture: source checksum matches', 'checks': {'source_match': True}}
    run = {'requested_pattern': 'parallel', 'effective_pattern': 'parallel', 'state': 'completed',
           'reason': 'Display fixture: explicit comparison of synthetic evidence.',
           'participants': [], 'conflicts': [{'kind': 'different_outputs', 'participant_ids': ['analysis_1', 'analysis_2'],
                    'resolution': 'Source receipt resolves this display fixture disagreement.'}],
           'selected_endpoint_id': 'worker:athena-p6000', 'final_verification': evidence,
           'total_latency_ms': 2384, 'generated_tokens': 121, 'output_token_budget': 768, 'max_rounds': 1,
           'input_sha256': 'd'*64, 'context_refs': [{'step_id': 'fixture_source', 'result_sha256': 'e'*64, 'verification_status': 'VERIFIED'}]}
    for i, endpoint, model, latency, verified, text in [
        (1, 'local:supervisor', 'Qwen3.5-4B-Q4_K_M.gguf', 482, False, '{"verified":true,"source":"T1"}'),
        (2, 'worker:athena-p6000', 'Qwen3.8-27B-Q4_K_S.gguf', 2324, True, '{"verified":false,"source":"T2","reason":"checksum_mismatch"}')]:
        run['participants'].append({'participant_id': f'analysis_{i}', 'endpoint_id': endpoint, 'model_id': model,
            'identity': 'display-fixture-identity-'+str(i), 'assigned_task': 'Independent synthetic evidence analysis',
            'state': 'completed', 'latency_ms': latency, 'output_summary': text, 'output': text,
            'verification': evidence if verified else {'status': 'UNVERIFIED', 'scope': 'Disclosed display fixture: unsupported result', 'checks': {'source_match': False}},
            'error': None, 'tokens': {'completion_tokens': 41 if i == 1 else 80}, 'resource_observations': None})
    counts = {'total': 1, 'required': 1, 'verified': 1, 'unverified': 0, 'failed': 0, 'pending': 0, 'running': 0, 'blocked': 0}
    workflow = {'workflow_id': 'display-fixture-comparison', 'goal': 'Display fixture: compare synthetic evidence',
        'mode': 'assisted', 'status': 'completed', 'revision': 4, 'created_at': now, 'updated_at': now,
        'finished_at': now, 'started_at': now, 'counts': counts, 'verification_status': 'VERIFIED',
        'last_checkpoint_at': now, 'summary': 'Synthetic display data only. No inference runs in this review.', 'error': None,
        'controls': {}, 'collaboration': 'parallel', 'plan_hash': 'd'*64, 'plan_version': 1, 'limits': {},
        'steps': [{'step_id': 'analyze', 'description': 'Compare synthetic source receipts', 'kind': 'analysis',
            'capability_id': None, 'definition_hash': None, 'dependencies': [], 'criteria': [], 'arguments': {},
            'planned_arguments': {}, 'resolved_arguments': None, 'permission_level': 0, 'risk_level': 0,
            'side_effect': None, 'status': 'completed', 'started_at': now, 'finished_at': now, 'attempts': 1,
            'verification': evidence, 'error': None, 'controls': {}, 'collaboration': run}],
        'approvals': [], 'checkpoints': [], 'invocations': [], 'artifacts': [],
        'result_summary': 'Synthetic display fixture: source evidence resolved the disagreement.', 'compute_jobs': []}
    return workflow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to((ROOT/'data/v41-verification').resolve()) and not output.exists()
    output.mkdir(parents=True)
    results = {'checks': [], 'javascript_errors': [], 'external_requests': [], 'screenshots': [],
        'headless': True, 'browser': 'Microsoft Edge', 'native_app_reviewed': False,
        'display_fixture': True, 'disclosure': __doc__, 'visual_score': None,
        'artifacts_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
             [ROOT/'src/hanni/dashboard/static/app.js', ROOT/'src/hanni/dashboard/static/style.css', ROOT/'frontend/src/workflow_collaboration.tsx']}}
    workflow = display_fixture()
    fixture = PhaseReviewFixture()
    fixture.__enter__()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.on('pageerror', lambda error: results['javascript_errors'].append(str(error)))
            page.on('request', lambda req: results['external_requests'].append(req.url) if req.url.startswith(('http:', 'https:')) and not req.url.startswith(fixture.url) else None)
            state = {'outage': False}
            def display(route):
                if route.request.method != 'GET':
                    route.continue_(); return
                if state['outage']:
                    route.fulfill(status=503, content_type='application/json', body='{"error":"Controlled screenshot transport outage"}'); return
                if route.request.url.split('?')[0].endswith('/api/workflows'):
                    body = {'available': True, 'reason': None, 'runner_attached': True, 'controller_attached': True,
                            'sampled_at': 1, 'max_goal_chars': 4000, 'items': [workflow],
                            'controls': {'goal.submit': {'enabled': True}}}
                else:
                    body = {'available': True, 'reason': None, 'runner_attached': True, 'controller_attached': True, 'workflow': workflow}
                route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
            page.route('**/api/workflows**', display)
            page.goto(fixture.url+'#workflows', wait_until='domcontentloaded')
            expect(page.locator('.workflow-row')).to_have_count(1)
            page.locator('.workflow-row').click()
            expect(page.get_by_role('heading', name='Model collaboration', exact=True)).to_be_visible()
            expect(page.locator('.collaboration-participant')).to_have_count(2)
            results['checks'].append({'name': 'Existing workflow detail shows participant receipts and source verification', 'passed': True})
            for width, height in [(1440, 900), (900, 650), (640, 700)]:
                page.set_viewport_size({'width': width, 'height': height})
                page.get_by_role('heading', name='Model collaboration', exact=True).scroll_into_view_if_needed()
                name = f'collaboration-{width}x{height}.png'
                page.screenshot(path=str(output/name), full_page=True)
                results['screenshots'].append(name)
                results['checks'].append({'name': f'No document overflow at {width}', 'passed': not page.evaluate('document.documentElement.scrollWidth > innerWidth')})
            page.set_viewport_size({'width': 1440, 'height': 900})
            page.locator('.collaboration-output details').last.locator('summary').click()
            expect(page.locator('.collaboration-output details').last.locator('pre').first).to_be_visible()
            page.screenshot(path=str(output/'collaboration-full-output.png'), full_page=True)
            results['checks'].append({'name': 'Full returned output and model identity can be inspected', 'passed': True})
            # Unknown, failed and pending states are presentation fixtures only.
            unknown = workflow['steps'][0]['collaboration']
            unknown['participants'][1].update(state='failed', error='Display fixture: secondary endpoint unavailable.', output=None,
                output_summary=None, latency_ms=None, tokens=None, verification=None)
            unknown.update(generated_tokens=None, total_latency_ms=None, selected_endpoint_id='local:supervisor',
                           final_verification=unknown['participants'][0]['verification'], conflicts=[])
            page.get_by_role('button', name='Refresh workflow', exact=True).click()
            expect(page.get_by_text('Display fixture: secondary endpoint unavailable.', exact=True)).to_be_visible()
            expect(page.get_by_text('Tokens not measured', exact=True)).to_be_visible()
            page.screenshot(path=str(output/'collaboration-secondary-unavailable.png'), full_page=True)
            results['checks'].append({'name': 'Unknown duration and tokens stay unmeasured; actual failure text visible', 'passed': 'Not measured' in page.locator('.collaboration-participant').last.inner_text()})
            unknown['participants'][1].update(state='running', error=None)
            unknown['state'] = 'running'
            unknown.update(selected_endpoint_id=None, final_verification=None)
            page.get_by_role('button', name='Refresh workflow', exact=True).click()
            expect(page.locator('.collaboration-heading').get_by_text('Parallel · Running', exact=True)).to_be_visible()
            page.screenshot(path=str(output/'collaboration-running.png'), full_page=True)
            results['checks'].append({'name': 'Running state has no invented result or spinner', 'passed': page.locator('.collaboration-participant').last.get_by_text('No output recorded', exact=True).count() == 1})
            state['outage'] = True
            page.get_by_role('button', name='Refresh workflow', exact=True).click()
            expect(page.get_by_text('Displayed workflow may be stale.', exact=False)).to_be_visible()
            page.screenshot(path=str(output/'collaboration-stale-error.png'), full_page=True)
            results['checks'].append({'name': 'Transport error preserves stale disclosure', 'passed': True})
            state['outage'] = False
            workflow['steps'][0]['collaboration'] = None
            page.get_by_role('button', name='Refresh workflow', exact=True).click()
            expect(page.get_by_text('This workflow has no recorded model collaboration.', exact=False)).to_be_visible()
            page.screenshot(path=str(output/'collaboration-empty.png'), full_page=True)
            results['checks'].append({'name': 'No recorded activity has explicit empty state', 'passed': True})
            page.get_by_role('button', name='Back to workflows', exact=True).click()
            page.get_by_role('button', name='New goal', exact=True).click()
            select = page.get_by_label('Model analysis', exact=True)
            expect(select).to_be_visible()
            results['checks'].append({'name': 'Existing workflow goal offers all bounded collaboration preferences', 'passed': set(select.locator('option').evaluate_all('(els)=>els.map(el=>el.value)')) == {'auto', 'single', 'parallel', 'specialists', 'review'}})
            page.screenshot(path=str(output/'collaboration-goal-preferences.png'), full_page=True)
            results['font_family'] = page.locator('body').evaluate('el=>getComputedStyle(el).fontFamily')
            results['checks'].append({'name': 'User Geist font retained', 'passed': 'Geist' in results['font_family']})
            results['checks'].append({'name': 'No browser errors or external network requests', 'passed': not results['javascript_errors'] and not results['external_requests']})
            browser.close()
    finally:
        fixture.server.shutdown(); fixture.server.server_close(); fixture.thread.join(3)
        close_service(fixture.config.paths.data_dir)
        fixture.hub.close(); fixture.hub.db.close(); fixture.temporary.cleanup()
        (output/'results.json').write_text(json.dumps(results, indent=2), encoding='utf8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
