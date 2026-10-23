"""Independent Edge screenshot/control review; rich display is explicitly synthetic."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts/desktop_review')]
from phase_fixture import PhaseReviewFixture
from hanni.reliability.execution import close_service
from playwright.sync_api import sync_playwright, expect


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to((ROOT / 'data/v40-verification').resolve()) and not output.exists()
    output.mkdir(parents=True)
    result = {'headless': True, 'browser': 'Microsoft Edge', 'native_app_reviewed': False,
              'display_fixture': True, 'policy_post_mocked': False,
              'disclosure': 'Rich rows use saved synthetic benchmark telemetry; actual token/Origin-gated policy POST changes only isolated local review settings.',
              'checks': [], 'javascript_errors': [], 'frames': []}
    fixture = PhaseReviewFixture()
    fixture.__enter__()
    try:
        rich = json.loads((ROOT / 'data/v40-verification/published-20261009-b/snapshot.json').read_text())
        # Presentation-only sample history, marked explicitly; never used as inference/correctness evidence.
        rich['decisions'] = [
            {'decision_id': 'display-fixture-routing', 'created_at': 1791587000, 'task_category': 'analysis',
             'policy': 'balanced', 'endpoint_id': 'worker:athena-p6000', 'model_id': 'Qwen3.8-27B-Q4_K_S.gguf',
             'reason': 'Display fixture: verified synthetic input; measured capacity and bounded load.',
             'status': 'completed', 'privacy_categories': ['synthetic'], 'required_context_tokens': 700,
             'excluded': [], 'fallbacks': [{'from_endpoint_id': 'local:supervisor',
                 'to_endpoint_id': 'worker:athena-p6000', 'trigger': 'verification_failed'}], 'latency_ms': 2029}
        ]
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900}, device_scale_factor=1)
            page.on('pageerror', lambda error: result['javascript_errors'].append(str(error)))
            def display(route):
                if route.request.method != 'GET':
                    route.continue_()
                    return
                data = deepcopy(rich)
                actual = fixture.server.model_routing.snapshot()
                data['policy'] = actual['policy']
                data['manual_endpoint_id'] = actual['manual_endpoint_id']
                route.fulfill(status=200, content_type='application/json', body=json.dumps(data))
            page.route('**/api/model-routing', display)
            page.goto(fixture.url + '#model-routing', wait_until='domcontentloaded')
            expect(page.get_by_role('heading', name='Model routing', exact=True)).to_be_visible(timeout=20000)
            expect(page.get_by_text('Qwen3.8-27B-Q4_K_S.gguf', exact=False).first).to_be_visible()
            for width, height in [(1440, 900), (900, 650), (640, 700)]:
                page.set_viewport_size({'width': width, 'height': height})
                page.screenshot(path=str(output / f'routing-{width}x{height}.png'), full_page=True)
                overflow = page.evaluate('document.documentElement.scrollWidth > innerWidth')
                result['checks'].append({'name': f'No document overflow at {width}', 'passed': not overflow})
                result['frames'].append(f'routing-{width}x{height}.png')
            page.set_viewport_size({'width': 1440, 'height': 900})
            page.locator('.routing-endpoint-details').first.locator('summary').click()
            page.screenshot(path=str(output / 'routing-capability-details.png'), full_page=True)
            page.locator('.routing-policy-controls select').first.select_option('fast')
            page.get_by_role('button', name='Apply policy', exact=True).click()
            expect(page.get_by_text('Routing policy saved.', exact=False)).to_be_visible()
            result['checks'].append({'name': 'Real isolated API persisted Fast policy',
                'passed': fixture.server.model_routing.snapshot()['policy'] == 'fast'})
            page.locator('.routing-policy-controls select').first.select_option('manual')
            page.locator('.routing-policy-controls select').nth(1).select_option('local:supervisor')
            page.get_by_role('button', name='Apply policy', exact=True).click()
            expect(page.get_by_text('Routing policy saved.', exact=False)).to_be_visible()
            result['checks'].append({'name': 'Real isolated API persisted primary manual override',
                'passed': fixture.server.model_routing.snapshot()['manual_endpoint_id'] == 'local:supervisor'})
            page.screenshot(path=str(output / 'routing-policy-manual.png'), full_page=True)
            # Error state is a disclosed UI transport fixture, not an actual server outage benchmark.
            page.unroute('**/api/model-routing', display)
            page.route('**/api/model-routing', lambda route: route.fulfill(status=503, content_type='application/json', body='{"error":"Controlled preview unavailable"}') if route.request.method == 'GET' else route.continue_())
            page.reload(wait_until='domcontentloaded')
            expect(page.get_by_role('alert')).to_be_visible()
            page.screenshot(path=str(output / 'routing-error.png'), full_page=True)
            result['checks'].append({'name': 'Error state offers retry', 'passed': page.get_by_role('button', name='Retry', exact=False).count() > 0})
            page.unroute('**/api/model-routing')
            page.route('**/api/model-routing', display)
            page.get_by_role('button', name='Retry loading', exact=True).click()
            expect(page.get_by_text('Qwen3.8-27B-Q4_K_S.gguf', exact=False).first).to_be_visible()
            result['checks'].append({'name': 'Retry recovers endpoint display', 'passed': page.get_by_role('alert').count() == 0})
            page.screenshot(path=str(output / 'routing-recovered.png'), full_page=True)
            page.unroute('**/api/model-routing', display)
            empty = {**rich, 'endpoints': [], 'decisions': [], 'available': True}
            page.route('**/api/model-routing', lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps(empty)) if route.request.method == 'GET' else route.continue_())
            page.reload(wait_until='domcontentloaded')
            page.screenshot(path=str(output / 'routing-empty.png'), full_page=True)
            result['checks'].append({'name': 'Empty state exists', 'passed': page.get_by_text('No inference endpoints', exact=False).count() > 0})
            font = page.locator('body').evaluate('el=>getComputedStyle(el).fontFamily')
            result['font_family'] = font
            result['checks'].append({'name': 'User Geist font retained', 'passed': 'Geist' in font})
            browser.close()
    finally:
        fixture.server.shutdown()
        fixture.server.server_close()
        fixture.thread.join(3)
        close_service(fixture.config.paths.data_dir)
        fixture.hub.close()
        fixture.hub.db.close()
        fixture.temporary.cleanup()
        (output / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
