"""Actual framed MCP Hub review; original server/manager/registry, no CRUD mocks.

Run only after coordinator releases a frozen frontend/native artifact. CDP
drives controls; all screenshots are physical native Windows frame captures.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts/desktop_review'))
import win32con
import win32gui
from playwright.sync_api import sync_playwright, expect
from capture_native import SIZES, frame_capture, wait_window
from hub_fixture import HubReviewFixture


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ledger_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--supplemental-only', action='store_true',
                        help='Capture compact inspector/dialog scroll positions; perform controls at 900x650')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = {'passed': False, 'screenshots': [], 'checks': [], 'errors': [],
              'supplemental_only':args.supplemental_only,
              'javascript_errors': [], 'external_requests': [], 'visual_score': None,
              'artifact_sha256': {label: digest(path) for label, path in {
                  'exe': args.exe.resolve(), 'app.js': ROOT/'src/hanni/dashboard/static/app.js',
                  'style.css': ROOT/'src/hanni/dashboard/static/style.css'}.items()}}
    process = None
    title = 'HANNI OS Independent MCP Hub Review'
    with HubReviewFixture() as fixture:
        result['disclosure'] = fixture.disclosure
        directory = Path(fixture.temporary.name)/'independent-mock'
        directory.mkdir()
        control, ledger = directory/'control.json', directory/'ledger.jsonl'
        control.write_text('{}', encoding='utf-8')
        mock_args = [str(ROOT/'tests/fixtures/mcp_hub_mock.py'), '--control', str(control), '--ledger', str(ledger)]
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            debug_port = sock.getsockname()[1]
        log = (output/'native-launch.log').open('w', encoding='utf-8')
        try:
            process = subprocess.Popen([str(args.exe.resolve()), '--url', fixture.url,
                '--attach-only', '--state-dir', str(output/'isolated-native-state'),
                '--debug-port', str(debug_port), '--title', title], stdout=log, stderr=subprocess.STDOUT)
            hwnd = wait_window(title)
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(hwnd, 0, 0, 0, 1920, 1080, win32con.SWP_NOZORDER)
            with sync_playwright() as playwright:
                browser = None
                for _ in range(100):
                    try:
                        browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{debug_port}', timeout=1000)
                        break
                    except Exception:
                        time.sleep(.1)
                if browser is None:
                    raise AssertionError('Native WebView CDP unavailable')
                page = None
                for _ in range(300):
                    pages = [p for c in browser.contexts for p in c.pages]
                    matches = [p for p in pages
                               if p.url.startswith(fixture.url) and '?view=mini' not in p.url]
                    if matches:
                        page = matches[0]
                        break
                    # Playwright's synchronous dispatcher must process native
                    # navigation events; time.sleep leaves page.url stale.
                    if pages:
                        pages[0].wait_for_timeout(100)
                    else:
                        browser.new_browser_cdp_session().send('Target.getTargets')
                if page is None:
                    result['cdp_targets'] = browser.new_browser_cdp_session().send('Target.getTargets')
                    result['cdp_pages'] = [p.url for c in browser.contexts for p in c.pages]
                    frame_capture(hwnd, output/'startup-failure-native.png')
                    raise AssertionError('Native CDP page selection timed out; inspect target diagnostics and actual frame')
                page.on('pageerror', lambda error: result['javascript_errors'].append(str(error)))
                page.on('request', lambda request: result['external_requests'].append(request.url)
                    if request.url.startswith(('http:', 'https:')) and not request.url.startswith(fixture.url) else None)

                def capture_state(name):
                    supplemental_states = {'add-server','connection-review','connection-settings','tool-inspector','raw-definition',
                                           'tool-approval','import-preview','export-review','remove-confirmation'}
                    if args.supplemental_only and name not in supplemental_states:
                        return
                    sizes = [(1366,768),(900,650)] if args.supplemental_only else SIZES
                    for width, height in sizes:
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetWindowPos(hwnd, 0, 0, 0, width, height, win32con.SWP_NOZORDER)
                        page.wait_for_timeout(450)
                        layout = page.evaluate('''() => ({inner_width:innerWidth,inner_height:innerHeight,
                          document_width:document.documentElement.scrollWidth,
                          viewport_width:document.documentElement.clientWidth,
                          body_text:document.body.innerText.slice(0,32000),active_route:location.hash})''')
                        frame = frame_capture(hwnd, output/f'{name}-{width}x{height}-native.png')
                        frame.update(state=name, layout=layout, dpi=ctypes.windll.user32.GetDpiForWindow(hwnd))
                        result['screenshots'].append(frame)
                        if frame['window_size'] != [width, height]:
                            result['errors'].append(f'{name}: requested size differs from actual frame')
                        if layout['document_width'] > layout['viewport_width']+1:
                            result['errors'].append(f'{name} {width}x{height}: document horizontal overflow')
                        if args.supplemental_only:
                            targets = [('content','.mcp-tool-inspector h3'),('actions','.mcp-inspector-actions')]
                            if name == 'connection-settings':
                                targets = [('restart-facts','.mcp-connection-details dl')]
                            if page.get_by_role('dialog').count():
                                targets = [('bottom','.dialog-actions')]
                            for suffix, selector in targets:
                                target = page.locator(selector).last
                                if not target.count():
                                    continue
                                target.evaluate('(element)=>element.scrollIntoView({block:"start"})')
                                page.wait_for_timeout(180)
                                lower = frame_capture(hwnd, output/f'{name}-{suffix}-{width}x{height}-native.png')
                                lower.update(state=name, scroll_position=suffix,
                                             dpi=ctypes.windll.user32.GetDpiForWindow(hwnd))
                                result['screenshots'].append(lower)
                    if not args.supplemental_only:
                        win32gui.SetWindowPos(hwnd, 0, 0, 0, 1920, 1080, win32con.SWP_NOZORDER)
                        page.wait_for_timeout(150)

                def check(name, condition=True):
                    result['checks'].append({'name': name, 'passed': bool(condition)})
                    if not condition:
                        raise AssertionError(name)

                page.evaluate('location.hash="settings"')
                expect(page.get_by_role('button', name='MCP Hub', exact=True)).to_be_visible(timeout=20000)
                page.get_by_role('button', name='MCP Hub', exact=True).click()
                expect(page.locator('.mcp-hub-page')).to_be_visible()
                expect(page.get_by_role('heading', name='No MCP servers configured')).to_be_visible()
                check('Settings Integrations opens actual empty Hub')
                expect(page.locator('.breadcrumb > span').first).to_have_text('Settings')
                check('Actual native breadcrumb locates MCP Hub in Settings')
                capture_state('empty')

                page.get_by_role('button', name='Add server', exact=True).click()
                dialog = page.get_by_role('dialog', name='Add MCP server', exact=True)
                expect(dialog).to_be_visible()
                expect(dialog.get_by_text('Saved servers require an explicit reconnect after restarting HANNI.', exact=True)).to_be_visible()
                check('Native Add editor has honest restart note and no startup checkbox',
                      dialog.get_by_role('checkbox').count() == 0)
                capture_state('add-server')
                dialog.get_by_label('Server name', exact=True).fill('Independent SDK fixture')
                dialog.get_by_label('Executable', exact=True).fill(sys.executable)
                dialog.get_by_label('Arguments (JSON array)', exact=True).fill(json.dumps(mock_args))
                dialog.get_by_label('Timeout (seconds)', exact=True).fill('3')
                dialog.get_by_role('button', name='Save server', exact=True).click()
                row = page.locator('.mcp-server-row').filter(has_text='Independent SDK fixture')
                expect(row).to_be_visible(timeout=15000)
                saved = fixture.server.mcp.snapshot()['servers'][0]
                check('Add stores disabled config without child launch', saved['enabled'] is False and not ledger.exists())
                row.click()
                page.get_by_text('Connection settings', exact=True).click()
                expect(page.get_by_text('After restart', exact=True)).to_be_visible()
                expect(page.get_by_text('Explicit reconnect required', exact=True)).to_be_visible()
                check('Native connection details accurately require explicit restart reconnect')
                capture_state('connection-settings')
                page.get_by_text('Connection settings', exact=True).click()
                page.get_by_role('button', name='Test & Discover', exact=True).click()
                dialog = page.get_by_role('dialog', name='Test & Discover Independent SDK fixture?', exact=True)
                expect(dialog).to_contain_text(sys.executable)
                capture_state('connection-review')
                page.keyboard.press('Escape')
                check('Cancel connection review launches nothing', not ledger.exists())
                page.get_by_role('button', name='Test & Discover', exact=True).click()
                page.get_by_role('button', name='Approve connection', exact=True).click()
                expect(page.locator('.mcp-tool-row')).to_have_count(3, timeout=20000)
                check('Paginated real discovery does not execute tools',
                      not any(row['event']=='call' for row in ledger_rows(ledger)))
                capture_state('discovered-tools')
                page.locator('.mcp-tool-row[data-tool="mock.echo"] button').click()
                inspector = page.get_by_role('region', name='Inspect mock.echo', exact=True)
                expect(inspector).to_be_visible()
                capture_state('tool-inspector')
                inspector.get_by_text('Input JSON schema', exact=True).click()
                inspector.get_by_text('Output JSON schema', exact=True).click()
                inspector.get_by_text('Original annotations and metadata', exact=True).click()
                expect(inspector.locator('.mcp-raw-schema[open]')).to_have_count(3)
                capture_state('raw-definition')
                for label in ('Input JSON schema', 'Output JSON schema', 'Original annotations and metadata'):
                    inspector.get_by_text(label, exact=True).click()

                # Server and tool enablement are separate actual UI confirmations.
                if page.get_by_role('button', name='Enable server', exact=True).count():
                    page.get_by_role('button', name='Enable server', exact=True).click()
                    page.get_by_role('dialog').get_by_role('button', name='Confirm change', exact=True).click()
                    expect(page.get_by_role('button', name='Disable server', exact=True)).to_be_visible(timeout=15000)
                page.get_by_label('Permission classification', exact=True).select_option('read_only')
                page.get_by_role('button', name='Approve & enable', exact=True).click()
                expect(page.get_by_role('dialog')).to_contain_text('mock.echo')
                capture_state('tool-approval')
                page.get_by_role('button', name='Approve tools', exact=True).click()
                expect(page.get_by_role('button', name='Disable tool', exact=True)).to_be_enabled(timeout=15000)
                enabled = next(tool for tool in fixture.server.mcp.snapshot()['servers'][0]['tools']
                               if tool['original_name']=='mock.echo')
                check('UI approval installs actual enabled registry adapter', enabled['enabled'] and enabled['available'])

                # Use the original CLI-bound controller; only model selection is deterministic.
                decision = fixture.controller.host.route('Use mock.echo to echo the message independent-native-proof')
                offered = next(tool for tool in decision.tools if tool.capability_id==enabled['internal_id'])
                fixture.model_probe.wire_name = offered.wire_name
                fixture.model_probe.arguments = {'message': 'independent-native-proof'}
                answer = ''.join(fixture.controller.stream_response('Use mock.echo to echo the message independent-native-proof'))
                result['controller_probe'] = {'answer': answer, 'menus': fixture.model_probe.menus,
                    'disclosure': 'Original CLI-bound controller/host/session; deterministic model client, real SDK tools/call.'}
                check('Original controller executes original external identity',
                    'independent-native-proof' in answer and
                    any(row.get('event')=='call' and row.get('name')=='mock.echo' for row in ledger_rows(ledger)))
                page.get_by_role('button', name='Disable tool', exact=True).click()
                expect(page.get_by_role('button', name='Disable tool', exact=True)).to_be_disabled(timeout=15000)
                check('Actual UI disable removes availability',
                    not next(tool for tool in fixture.server.mcp.snapshot()['servers'][0]['tools']
                             if tool['original_name']=='mock.echo')['available'])

                page.get_by_role('button', name=re.compile('All servers')).click()
                capture_state('server-overview')
                page.get_by_role('button', name='Export config', exact=True).click()
                export_dialog = page.get_by_role('dialog', name='Exported MCP configuration', exact=True)
                expect(export_dialog).to_be_visible(timeout=15000)
                export_path = Path(export_dialog.get_by_label('Saved export file', exact=True).input_value()).resolve()
                export_path.relative_to(Path(fixture.temporary.name).resolve())
                export_json = export_dialog.get_by_label('Exported configuration JSON', exact=True).input_value()
                check('Native export saves actual owned JSON matching the review dialog', export_path.is_file() and
                    json.loads(export_path.read_text(encoding='utf-8'))==json.loads(export_json)==
                    fixture.server.mcp.export_configs())
                check('Native export exposes readonly JSON and an explicit copy control',
                    export_dialog.get_by_label('Exported configuration JSON', exact=True).get_attribute('readonly') is not None)
                expect(export_dialog.get_by_role('button', name='Copy JSON', exact=True)).to_be_enabled()
                result['export_evidence'] = {'owned_path':str(export_path.relative_to(Path(fixture.temporary.name))),
                    'file_sha256':digest(export_path), 'configuration':json.loads(export_json),
                    'clipboard_disclosure':'Copy button availability checked; OS clipboard was not read or overwritten.'}
                capture_state('export-review')
                export_dialog.get_by_role('button', name='Close export', exact=True).click()
                page.get_by_label('Search MCP servers', exact=True).fill('no-such-independent-server')
                expect(page.get_by_text('No servers match this search.', exact=True)).to_be_visible()
                check('Search has meaningful empty result')
                page.get_by_label('Search MCP servers', exact=True).fill('')
                page.get_by_role('button', name='Import config', exact=True).click()
                dialog = page.get_by_role('dialog', name='Import MCP configuration', exact=True)
                import_document = {'mcpServers': {'Imported preview': {'command': sys.executable,
                                                                     'args': mock_args}}}
                dialog.get_by_label('Configuration JSON', exact=True).fill(json.dumps(import_document))
                before = len(ledger_rows(ledger))
                dialog.get_by_role('button', name='Preview import', exact=True).click()
                expect(page.locator('.mcp-import-preview')).to_be_visible(timeout=15000)
                capture_state('import-preview')
                page.keyboard.press('Escape')
                check('Import preview has no execution or saved config', len(ledger_rows(ledger))==before and
                      len(fixture.server.mcp.snapshot()['servers'])==1)
                page.locator('.mcp-server-row').first.click()
                page.get_by_role('button', name='Remove server', exact=True).click()
                expect(page.get_by_role('dialog', name='Remove Independent SDK fixture?', exact=True)).to_be_visible()
                capture_state('remove-confirmation')
                page.keyboard.press('Escape')
                check('Remove cancellation preserves original config', len(fixture.server.mcp.snapshot()['servers'])==1)
                control.write_text(json.dumps({'list_delay':5}), encoding='utf-8')
                page.get_by_role('button', name='Refresh definitions', exact=True).click()
                expect(page.locator('.mcp-detail-heading .mcp-state')).to_have_text('failed', timeout=20000)
                capture_state('timeout-error')
                check('Actual timed out discovery revokes availability',
                    not any(tool['available'] for tool in fixture.server.mcp.snapshot()['servers'][0]['tools']))
                check('No unrelated cluster/power/terminal writes', not fixture.writes)
                result['protocol_ledger'] = ledger_rows(ledger)
                result['management_requests'] = fixture.management_requests
                result['original_audit'] = ledger_rows(fixture.registry.context.audit.path)
                result['passed'] = not (result['errors'] or result['javascript_errors'] or result['external_requests'])
                result['scoring_status'] = 'Actual PNG pixels require independent inspection and exact five-category /2 rubric; harness PASS is not a visual grade.'
        except Exception as error:
            result['errors'].append(f'{type(error).__name__}: {error}')
            try:
                if 'hwnd' in locals():
                    frame_capture(hwnd, output/'failure-native.png')
            except Exception:
                pass
        finally:
            if process is not None and process.poll() is None:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                process.wait(timeout=10)
            log.close()
            result['passed'] = result['passed'] and not result['errors']
            (output/'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'screenshots':len(result['screenshots']), 'checks':len(result['checks']), 'errors':result['errors']}))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
