"""Controlled UI edge cases with explicitly disclosed display-only history.

No model inference executes here. Artificial history rows have no response,
score, latency, or quality measurements and cannot serve as live benchmarks.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts/desktop_review')]
from fixture import ReviewFixture
from hanni.reliability.execution import close_service
from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to((ROOT / 'data/v43-verification').resolve()) and not output.exists()
    output.mkdir(parents=True)
    result = {'display_fixture': True, 'real_model_inference': False, 'native_app_reviewed': False,
              'headless': True, 'browser': 'Microsoft Edge', 'disclosure': __doc__,
              'checks': [], 'screenshots': [], 'javascript_errors': []}
    fixture = ReviewFixture()
    fixture.__enter__()
    try:
        service = fixture.server.model_lab
        baseline = service.start({'suite_id': 'routing-development', 'endpoint_id': None,
                                  'max_cases': 1, 'repetitions': 1, 'max_tokens': 192, 'max_rounds': 3})
        while service.active_run_id is not None:
            time.sleep(.01)
        base = service.detail(baseline['id'])['run']
        oldest_id = None
        now = time.time()
        for index in range(121):
            row = deepcopy(base)
            row.update(id=str(uuid4()), suite_name=f'Display historical fixture {index:03d}',
                       created_at=now - 1000 + index, updated_at=now - 1000 + index,
                       completed=0, total=0, summary={},
                       status_reason='Disclosed UI fixture only; no model/response/score/latency measurements.')
            if index == 0:
                oldest_id = row['id']
            service._save(row)
        assert service.snapshot()['history_count'] == 122 and len(service.snapshot()['runs']) == 100
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.on('pageerror', lambda error: result['javascript_errors'].append(str(error)))
            page.goto(fixture.url + '#models', wait_until='domcontentloaded')
            expect(page.get_by_role('heading', name='Model Intelligence Lab', exact=True)).to_be_visible(timeout=15000)
            page.get_by_role('button', name='Results', exact=False).filter(has_text='Results').first.click()
            expect(page.locator('.lab-history tbody tr')).to_have_count(100)
            page.get_by_label('Search benchmark history', exact=True).fill(oldest_id)
            expect(page.locator('.lab-history tbody tr')).to_have_count(1, timeout=15000)
            expect(page.locator('.lab-history tbody tr')).to_contain_text('Display historical fixture 000')
            result['checks'].append({'name': 'UI search reaches the oldest run beyond the100-row snapshot cap', 'passed': True})
            page.get_by_label('Filter run status', exact=True).select_option('failed')
            expect(page.locator('.lab-history tbody tr')).to_have_count(0)
            page.get_by_label('Filter run status', exact=True).select_option('completed')
            expect(page.locator('.lab-history tbody tr')).to_have_count(1, timeout=15000)
            result['checks'].append({'name': 'Server-backed history status filters compose with search', 'passed': True})
            page.get_by_label('Search benchmark history', exact=True).fill('')
            for width, height in [(1440, 900), (900, 650), (640, 700)]:
                page.set_viewport_size({'width': width, 'height': height})
                page.wait_for_timeout(250)
                result['checks'].append({'name': f'No document overflow in disclosed history fixture at{width}',
                                         'passed': page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')})
                file = f'disclosed-history-{width}x{height}-headless.png'
                page.screenshot(path=str(output / file), full_page=True)
                result['screenshots'].append(file)
            result['checks'].append({'name': 'No JavaScript errors in controlled UI cases', 'passed': not result['javascript_errors']})
            result['passed'] = all(check['passed'] for check in result['checks'])
            browser.close()
    except Exception as error:
        result.update(passed=False, blocker=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        fixture.server.shutdown()
        fixture.server.server_close()
        fixture.thread.join(3)
        close_service(fixture.config.paths.data_dir)
        fixture.hub.close()
        fixture.hub.db.close()
        fixture.temporary.cleanup()
        (output / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf8')
        print(json.dumps({key: result.get(key) for key in ('passed', 'checks', 'blocker')}), flush=True)


if __name__ == '__main__':
    main()
