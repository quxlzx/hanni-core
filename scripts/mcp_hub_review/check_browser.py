"""Headless frontend interactions against the genuine isolated MCP Hub.

No private CRUD, schema responses, registry adapters or permission checks are
mocked. Only the existing fixture telemetry/model client is synthetic. SDK
fixture launches occur exclusively after explicit UI connection approval.
This test does not execute any discovered tool, launch a native window or grade
visual appearance. Run only after the coordinator's backend/frontend freeze.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hub_fixture import HubReviewFixture

MOCK = ROOT / 'tests/fixtures/mcp_hub_mock.py'
spec = importlib.util.spec_from_file_location('frontend_sdk_fixture', MOCK)
mock_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mock_module)


def ledger_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--browser-channel', default='msedge')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = {
        'passed': False, 'checks': [], 'errors': [], 'javascript_errors': [],
        'external_requests': [], 'responsive_layouts': [], 'visual_score': None,
        'artifact_sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in {
            'app.js': ROOT/'src/hanni/dashboard/static/app.js',
            'style.css': ROOT/'src/hanni/dashboard/static/style.css',
        }.items()},
        'disclosure': 'Headless real browser interactions; genuine isolated HTTP/registry-gated '
                      'MCP manager and official-SDK stdio mock. Existing telemetry and model '
                      'client synthetic. No private CRUD mocked. No tools/call, live model, '
                      'provider, microphone, SSH, power control or production data. Manager '
                      'restart checks actual SQLite reload, not a native application restart. '
                      'One actual Add response is deliberately aborted after the real '
                      'backend write to verify UUID retry; no CRUD result is fabricated. '
                      'Debug browser images are not native visual-review evidence.',
    }

    def check(name, condition=True, evidence=None):
        result['checks'].append({'name': name, 'passed': bool(condition), 'evidence': evidence})
        if not condition:
            raise AssertionError(name)

    with HubReviewFixture() as fixture:
        owned = Path(fixture.temporary.name) / 'browser-sdk-fixture'
        owned.mkdir()
        control, ledger = owned/'control.json', owned/'ledger.jsonl'
        control.write_text('{}', encoding='utf-8')
        mock_args = [str(MOCK), '--control', str(control), '--ledger', str(ledger)]

        def snapshot():
            return fixture.request()

        def server(server_id):
            return next(row for row in snapshot()['servers'] if row['id'] == server_id)

        def tool(server_id, name):
            return next(row for row in server(server_id)['tools'] if row['original_name'] == name)

        def no_calls():
            return not any(row['event'] == 'call' for row in ledger_rows(ledger))

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=args.browser_channel, headless=True)
            context = browser.new_context(viewport={'width': 1280, 'height': 800}, accept_downloads=True)
            page = context.new_page()
            page.set_default_timeout(15000)
            page.on('pageerror', lambda error: result['javascript_errors'].append(str(error)))
            page.on('request', lambda request: result['external_requests'].append(request.url)
                    if request.url.startswith(('http:', 'https:')) and not request.url.startswith(fixture.url) else None)
            posted = []
            page.on('request', lambda request: posted.append(request.post_data_json)
                    if request.method == 'POST' and request.url == fixture.url.rstrip('/') + '/api/mcp' else None)

            def heading(text):
                expect(page.get_by_role('heading', name=text, exact=True)).to_be_visible()

            def open_server(name):
                page.locator('.mcp-server-row').filter(has_text=name).click()

            def inspect(name):
                page.locator('.mcp-tool-row').filter(has=page.get_by_role('button', name=re.compile(re.escape(name)))).get_by_role('button').click()
                inspector = page.get_by_role('region', name='Inspect ' + name, exact=True)
                expect(inspector).to_be_visible()
                return inspector

            def all_servers():
                page.get_by_role('button', name=re.compile('All servers')).click()

            def exact_connection_destination(dialog):
                command, arguments = dialog.locator('.mcp-approved-destination').inner_text().split('\n', 1)
                check('Connection review preserves exact executable and original argument values',
                      command == sys.executable and json.loads(arguments) == mock_args)

            def approve_connection(name):
                page.get_by_role('button', name='Test & Discover', exact=True).click()
                dialog = page.get_by_role('dialog', name='Test & Discover ' + name + '?', exact=True)
                exact_connection_destination(dialog)
                dialog.get_by_role('button', name='Approve connection', exact=True).click()
                expect(dialog).not_to_be_visible()
                expect(page.locator('.mcp-detail-heading .mcp-state')).to_have_text('connected', timeout=30000)

            try:
                page.goto(fixture.url + '#settings')
                page.get_by_role('link', name='Integrations', exact=True).click()
                page.get_by_role('button', name='MCP Hub', exact=True).click()
                heading('No MCP servers configured')
                check('Settings Integrations opens genuine empty MCP Hub')
                expect(page.locator('.breadcrumb > span').first).to_have_text('Settings')
                check('MCP Hub breadcrumb identifies Settings integration location')

                page.get_by_role('button', name='Add server', exact=True).click()
                dialog = page.get_by_role('dialog', name='Add MCP server', exact=True)
                expect(dialog.get_by_text('Saved servers require an explicit reconnect after restarting HANNI.', exact=True)).to_be_visible()
                expect(dialog.get_by_role('checkbox', name=re.compile('Reconnect.*HANNI starts'))).to_have_count(0)
                check('Server editor describes explicit restart reconnect without selectable startup promise')
                for index in range(12):
                    page.keyboard.press('Tab')
                    focus = page.evaluate('''() => ({tag:document.activeElement?.tagName,
                        inside:Boolean(document.activeElement?.closest('dialog')),
                        modal:Boolean(document.querySelector('dialog:modal'))})''')
                    # Chromium can briefly move focus to browser chrome (BODY
                    # in the document) before wrapping to the modal. Background
                    # DOM controls must remain inert throughout that transition.
                    blocked_background = page.evaluate('''() => {
                        const outside=document.querySelector('.mcp-header-actions>button');
                        outside.focus();return document.activeElement!==outside;
                    }''')
                    check(f'Modal keeps background inert during Tab cycle {index+1}',
                          focus['modal'] and (focus['inside'] or focus['tag'] == 'BODY') and blocked_background,
                          {**focus, 'background_focus_rejected': blocked_background})
                page.keyboard.press('Escape')
                expect(dialog).not_to_be_visible()
                check('Escape cancels Add without saving or launching', snapshot()['servers'] == [] and not ledger.exists())

                page.get_by_role('button', name='Add server', exact=True).click()
                dialog = page.get_by_role('dialog', name='Add MCP server', exact=True)
                dialog.get_by_label('Server name', exact=True).fill('Browser SDK fixture')
                dialog.get_by_label('Executable', exact=True).fill(sys.executable)
                dialog.get_by_label('Arguments (JSON array)', exact=True).fill('[123]')
                dialog.get_by_role('button', name='Save server', exact=True).click()
                expect(dialog.get_by_role('alert')).to_contain_text('Arguments')
                check('Invalid argument types are rejected before API save', snapshot()['servers'] == [])
                dialog.get_by_label('Arguments (JSON array)', exact=True).fill(json.dumps(mock_args))
                dialog.get_by_label('Timeout (seconds)', exact=True).fill('3')
                fault_used = False

                def abort_first_add_response(route):
                    nonlocal fault_used
                    request = route.request
                    if request.method == 'POST' and request.post_data_json.get('operation') == 'add' and not fault_used:
                        actual = route.fetch()
                        if actual.status != 200:
                            raise AssertionError('Genuine Add did not succeed before response-fault injection')
                        fault_used = True
                        route.abort('failed')
                    else:
                        route.continue_()

                api_url = fixture.url.rstrip('/') + '/api/mcp'
                page.route(api_url, abort_first_add_response)
                dialog.get_by_role('button', name='Save server', exact=True).click()
                expect(dialog.get_by_role('alert')).to_be_visible()
                expect(dialog.get_by_label('Server name', exact=True)).to_have_value('Browser SDK fixture')
                check('Response failure retains draft after real Add was persisted', len(snapshot()['servers']) == 1 and fault_used)
                page.unroute(api_url, abort_first_add_response)
                dialog.get_by_role('button', name='Save server', exact=True).click()
                expect(dialog).not_to_be_visible()
                expect(page.locator('.mcp-server-row')).to_have_count(1)
                add_requests = [body for body in posted if body['operation'] == 'add']
                check('Explicit retry reuses UUID and does not duplicate integration', len(add_requests) == 2 and add_requests[0]['id'] == add_requests[1]['id'] and len(snapshot()['servers']) == 1)
                main_server = snapshot()['servers'][0]
                main_id = main_server['id']
                check('Add saves actual disabled settings without process launch', not main_server['enabled'] and main_server['state'] == 'disabled' and not ledger.exists())
                open_server('Browser SDK fixture')

                page.get_by_role('button', name='Test & Discover', exact=True).click()
                dialog = page.get_by_role('dialog')
                exact_connection_destination(dialog)
                dialog.get_by_role('button', name='Cancel', exact=True).click()
                check('Connection approval cancellation starts no process', not ledger.exists())
                approve_connection('Browser SDK fixture')
                page.get_by_text('Connection settings', exact=True).click()
                expect(page.get_by_text('After restart', exact=True)).to_be_visible()
                expect(page.get_by_text('Explicit reconnect required', exact=True)).to_be_visible()
                check('Connection details accurately require explicit reconnect after restart')
                page.get_by_text('Connection settings', exact=True).click()
                expect(page.locator('.mcp-tool-row')).to_have_count(3)
                check('Actual paginated discovery never executes tools', no_calls() and len([row for row in ledger_rows(ledger) if row['event'] == 'list']) >= 2)
                check('All actual definitions initially await approval', all(not row['enabled'] and not row['available'] and row['approval'] is None for row in server(main_id)['tools']))

                inspector = inspect('mock.echo')
                current_tool = tool(main_id, 'mock.echo')
                expect(inspector.locator('.mcp-tool-description')).to_have_text(current_tool['description'])
                for label, field in [('Input JSON schema', 'input_schema'), ('Output JSON schema', 'output_schema')]:
                    details = inspector.locator('.mcp-raw-schema').filter(has=page.get_by_text(label, exact=True))
                    details.locator('summary').click()
                    check('Inspector preserves actual ' + label, json.loads(details.locator('pre').inner_text()) == current_tool[field])
                    details.locator('summary').click()
                expect(inspector.locator('.mcp-parameters')).to_contain_text('Required')
                check('Inspector retains original description and required parameter')
                inspector.get_by_label('Permission classification', exact=True).select_option('read_only')
                inspector.get_by_role('button', name='Approve & enable', exact=True).click()
                page.get_by_role('dialog').get_by_role('button', name='Cancel', exact=True).click()
                check('Tool approval cancellation leaves adapter unavailable', not tool(main_id, 'mock.echo')['available'])
                inspector.get_by_role('button', name='Approve & enable', exact=True).click()
                page.get_by_role('button', name='Approve tools', exact=True).click()
                expect(inspector.get_by_role('button', name='Disable tool', exact=True)).to_be_enabled()
                approved = tool(main_id, 'mock.echo')
                check('UI exact-definition approval registers genuine controller adapter', approved['available'] and approved['approval']['definition_hash'] == approved['definition_hash'] and approved['internal_id'] in {item.name for item in fixture.registry.definitions()})
                inspector.get_by_role('button', name='Disable tool', exact=True).click()
                expect(inspector.get_by_role('button', name='Disable tool', exact=True)).to_be_disabled()
                check('UI disable removes actual registry availability', not tool(main_id, 'mock.echo')['available'] and approved['internal_id'] not in {item.name for item in fixture.registry.definitions()})

                for name in ('mock.echo', 'mock.get_status'):
                    page.get_by_label('Select ' + name, exact=True).check()
                page.get_by_label('Tool permission classification', exact=True).select_option('read_only')
                page.get_by_role('button', name='Approve selected', exact=True).click()
                expect(page.get_by_role('dialog')).to_contain_text('2 selected tools')
                page.get_by_role('button', name='Approve tools', exact=True).click()
                expect(page.locator('.mcp-tool-actions')).to_contain_text('0 selected')
                check('Batch approval enables only exact selected definitions', tool(main_id, 'mock.echo')['available'] and tool(main_id, 'mock.get_status')['available'] and not tool(main_id, 'mock.create_record')['available'])

                inspector = inspect('mock.echo')
                old_tool = tool(main_id, 'mock.echo')
                inspector.get_by_role('button', name='Review approval', exact=True).click()
                changed_tools = deepcopy(mock_module.TOOLS)
                changed_tools[1]['description'] = 'Updated fixture echo definition requiring fresh owner review.'
                changed_tools[1]['inputSchema']['properties']['context'] = {'type': 'string', 'description': 'New optional fixture context.'}
                control.write_text(json.dumps({'tools': changed_tools}), encoding='utf-8')
                fixture.operation('refresh', {'server_id': main_id})
                expect(page.get_by_role('dialog').get_by_role('alert')).to_contain_text('definition changed', timeout=15000)
                expect(page.get_by_role('button', name='Approve tools', exact=True)).to_be_disabled()
                check('Changed definition blocks already-open stale approval dialog', not tool(main_id, 'mock.echo')['available'] and tool(main_id, 'mock.echo')['definition_hash'] != old_tool['definition_hash'])
                page.get_by_role('dialog').get_by_role('button', name='Cancel', exact=True).click()
                inspector = inspect('mock.echo')
                expect(inspector).to_contain_text(changed_tools[1]['description'])
                expect(inspector.locator('.mcp-tool-meta')).to_contain_text('Version 2')
                check('Definition refresh preserves changed source and resets approval', tool(main_id, 'mock.echo')['approval'] is None and tool(main_id, 'mock.echo')['classification'] == 'unknown')

                malformed = deepcopy(changed_tools)
                malformed[2]['inputSchema'] = {'type': 'unsupported_fixture_type'}
                control.write_text(json.dumps({'tools': malformed}), encoding='utf-8')
                page.get_by_role('button', name='Refresh definitions', exact=True).click()
                expect(page.locator('.mcp-detail-heading .mcp-state')).to_have_text('failed')
                expect(page.locator('.mcp-hub-page > .feature-note[role="status"]')).to_contain_text('Definition refresh attempt finished')
                check('Protocol-malformed listing fails closed without executable cached tools',
                      server(main_id)['state'] == 'failed' and all(not row['available'] for row in server(main_id)['tools']))
                unsupported = deepcopy(changed_tools)
                unsupported[2]['inputSchema']['properties']['title']['pattern'] = '(a+)+$'
                control.write_text(json.dumps({'tools': unsupported}), encoding='utf-8')
                approve_connection('Browser SDK fixture')
                expect(page.locator('.mcp-tool-row[data-tool="mock.create_record"]')).to_contain_text('Invalid definition')
                invalid_inspector = inspect('mock.create_record')
                expect(invalid_inspector.get_by_role('button', name='Approve & enable', exact=True)).to_be_disabled()
                invalid_inspector.get_by_text('Input JSON schema', exact=True).click()
                expect(invalid_inspector.locator('pre').first).to_contain_text('(a+)+$')
                check('Unsupported schema remains inspectable and cannot be approved', not tool(main_id, 'mock.create_record')['valid'])
                page.get_by_label('Search MCP tools', exact=True).fill('no-matching-tool')
                expect(page.get_by_text('No tools match this search.', exact=True)).to_be_visible()
                page.get_by_label('Search MCP tools', exact=True).fill('')
                page.get_by_label('Filter MCP tools', exact=True).select_option('invalid')
                expect(page.locator('.mcp-tool-row')).to_have_count(1)
                page.get_by_label('Filter MCP tools', exact=True).select_option('all')
                check('Tool filters include genuine invalid-definition empty/search states')

                # Explicit approval must bind the config that the user saw.
                page.get_by_role('button', name='Test & Discover', exact=True).click()
                copied = server(main_id)
                replacement = {**copied['config'], 'command': 'nonexistent-hanni-mcp-fixture-executable'}
                fixture.operation('update', {'server_id': main_id, 'config': replacement, 'expected_config_hash': copied['config_hash']})
                expect(page.get_by_role('dialog').get_by_role('alert')).to_contain_text('configuration or tool definition changed')
                expect(page.get_by_role('button', name='Approve connection', exact=True)).to_be_disabled()
                check('Concurrent config change cannot launch unseen executable', no_calls())
                page.get_by_role('dialog').get_by_role('button', name='Cancel', exact=True).click()

                page.get_by_role('button', name='Edit settings', exact=True).click()
                edit = page.get_by_role('dialog')
                edit.get_by_label('Server name', exact=True).fill('Unsent browser draft')
                copied = server(main_id)
                fixture.operation('update', {'server_id': main_id, 'config': {**copied['config'], 'name': 'Concurrent SDK fixture'}, 'expected_config_hash': copied['config_hash']})
                edit.get_by_role('button', name='Save server', exact=True).click()
                expect(edit.get_by_role('alert')).to_be_visible()
                expect(edit.get_by_label('Server name', exact=True)).to_have_value('Unsent browser draft')
                check('Stale config editor fails safely and retains its unsent draft', server(main_id)['name'] == 'Concurrent SDK fixture')
                edit.get_by_role('button', name='Cancel', exact=True).click()
                page.get_by_role('button', name='Refresh status', exact=True).click()
                heading('Concurrent SDK fixture')

                page.get_by_role('button', name='Test & Discover', exact=True).click()
                page.get_by_role('button', name='Approve connection', exact=True).click()
                expect(page.locator('.mcp-detail-heading .mcp-state')).to_have_text('failed', timeout=20000)
                expect(page.locator('.mcp-server-detail > .feature-error')).to_be_visible()
                check('Actual missing-executable failure is reported without false availability', server(main_id)['state'] == 'failed' and all(not row['available'] for row in server(main_id)['tools']))
                page.get_by_role('button', name='Edit settings', exact=True).click()
                edit = page.get_by_role('dialog')
                edit.get_by_label('Executable', exact=True).fill(sys.executable)
                edit.get_by_role('button', name='Save server', exact=True).click()
                expect(edit).not_to_be_visible()
                control.write_text('{}', encoding='utf-8')
                approve_connection('Concurrent SDK fixture')

                # Import preview/commit use the same genuine gated adapter.
                all_servers()
                page.get_by_label('Search MCP servers', exact=True).fill('not-a-server')
                expect(page.get_by_text('No servers match this search.', exact=True)).to_be_visible()
                page.get_by_label('Search MCP servers', exact=True).fill('')
                page.get_by_label('Filter MCP server status', exact=True).select_option('disabled')
                expect(page.get_by_text('No servers match this search.', exact=True)).to_be_visible()
                page.get_by_label('Filter MCP server status', exact=True).select_option('all')
                check('Server filters/search leave actual data intact')
                page.get_by_role('button', name='Import config', exact=True).click()
                dialog = page.get_by_role('dialog', name='Import MCP configuration', exact=True)
                import_document = {'mcpServers': {
                    'Imported SDK fixture': {'command': sys.executable, 'args': mock_args, 'auto_connect': True,
                                            'env': {'FIXTURE_OPTION': '${HANNI_EXISTING_REVIEW_OPTION}'}},
                    'Unsupported SSE': {'transport': 'sse', 'url': 'https://service.invalid/mcp'},
                    'Plaintext excluded': {'command': sys.executable, 'args': mock_args,
                                           'env': {'TOKEN': 'DO_NOT_SAVE_FRONTEND_SECRET'}},
                }}
                before_ledger = ledger_rows(ledger)
                dialog.get_by_label('Configuration JSON', exact=True).fill(json.dumps(import_document))
                dialog.get_by_role('button', name='Preview import', exact=True).click()
                expect(page.locator('.mcp-import-candidate')).to_have_count(1)
                expect(page.locator('.mcp-import-preview')).to_contain_text('skipped')
                check('Import preview launches nothing and exposes validated candidates only', ledger_rows(ledger) == before_ledger and len(snapshot()['servers']) == 1)
                dialog.get_by_role('button', name='Import selected', exact=True).click()
                page.get_by_role('dialog').get_by_role('button', name='Confirm change', exact=True).click()
                expect(page.locator('.mcp-server-row')).to_have_count(2)
                imported = next(row for row in snapshot()['servers'] if row['name'] == 'Imported SDK fixture')
                check('Import persists disabled even with auto-reconnect preference', imported['state'] == 'disabled' and not imported['enabled'] and imported['tools'] == [] and ledger_rows(ledger) == before_ledger)
                page.get_by_role('button', name='Export config', exact=True).click()
                export_dialog = page.get_by_role('dialog', name='Exported MCP configuration', exact=True)
                expect(export_dialog).to_be_visible()
                export_path = Path(export_dialog.get_by_label('Saved export file', exact=True).input_value()).resolve()
                expected_export_root = (fixture.server.mcp.root/'mcp/exports').resolve()
                check('Export saves to server-owned directory without browser download', export_path.parent == expected_export_root and export_path.is_file())
                exported = json.loads(export_path.read_text(encoding='utf-8'))
                check('Export presents exact actual non-secret saved file', json.loads(export_dialog.get_by_label('Exported configuration JSON', exact=True).input_value()) == exported and len(exported['mcpServers']) == 2 and 'DO_NOT_SAVE_FRONTEND_SECRET' not in json.dumps(exported) and imported['name'] in exported['mcpServers'])
                context.grant_permissions(['clipboard-read', 'clipboard-write'], origin=fixture.url.rstrip('/'))
                export_dialog.get_by_role('button', name='Copy JSON', exact=True).click()
                expect(export_dialog.get_by_role('status')).to_have_text('JSON copied.')
                check('Explicit Copy JSON works when browser clipboard permission is granted', json.loads(page.evaluate('navigator.clipboard.readText()')) == exported)
                export_dialog.get_by_role('button', name='Close export', exact=True).click()

                before_conflict = [(row['id'], row['config_hash']) for row in snapshot()['servers']]
                before_ledger = ledger_rows(ledger)
                page.get_by_role('button', name='Import config', exact=True).click()
                dialog = page.get_by_role('dialog', name='Import MCP configuration', exact=True)
                dialog.get_by_label('Configuration JSON', exact=True).fill(json.dumps({'mcpServers': {
                    server(main_id)['name']: {'command': sys.executable, 'args': mock_args},
                }}))
                dialog.get_by_role('button', name='Preview import', exact=True).click()
                expect(page.locator('.mcp-import-preview')).to_contain_text('cannot be overwritten')
                dialog.get_by_role('button', name='Import selected', exact=True).click()
                page.get_by_role('dialog').get_by_role('button', name='Confirm change', exact=True).click()
                expect(page.get_by_role('dialog').get_by_role('alert')).to_be_visible()
                check('Conflicting import fails visibly without overwrite or launch',
                      [(row['id'], row['config_hash']) for row in snapshot()['servers']] == before_conflict and ledger_rows(ledger) == before_ledger)
                page.get_by_role('dialog').get_by_role('button', name='Cancel', exact=True).click()
                page.get_by_role('dialog', name='Import MCP configuration', exact=True).get_by_role('button', name='Cancel', exact=True).click()

                # Genuine persistence restart. The HTTP adapter stays the same;
                # no route or store is patched with fabricated return values.
                before_restart = snapshot()['servers']
                before_ledger = ledger_rows(ledger)
                from hanni.mcp.manager import MCPManager
                fixture.server.mcp.manager.close()
                fixture.server.mcp.manager = MCPManager(fixture.server.mcp.root)
                fixture.server.mcp.manager.attach_registry(fixture.registry)
                reloaded = snapshot()['servers']
                def persistent_identity(rows):
                    # The live manager preserves insertion order while SQLite
                    # loads servers ordered by UUID. Identity is keyed by ID.
                    return {row['id']: {'config': row['config'], 'config_hash': row['config_hash'],
                                       'tools': {item['original_name']: item['definition_hash'] for item in row['tools']}}
                            for row in rows}
                check('Actual manager restart retains stable IDs/configurations/definition hashes',
                      persistent_identity(before_restart) == persistent_identity(reloaded),
                      {'before': persistent_identity(before_restart), 'after': persistent_identity(reloaded)})
                check('Disabled server remains disabled and launches nothing on restart', next(row for row in reloaded if row['id'] == imported['id'])['state'] == 'disabled' and ledger_rows(ledger) == before_ledger)
                check('Legacy imported reconnect metadata persists without enabling startup launch', next(row for row in reloaded if row['id'] == imported['id'])['config']['auto_connect'] is True)
                page.reload()
                expect(page.locator('.mcp-server-row')).to_have_count(2)
                check('Reloaded browser reads actual persisted server settings')

                for width in (512, 600, 640, 720, 800, 900, 1024, 1079, 1280, 1366, 1440, 1920):
                    page.set_viewport_size({'width': width, 'height': 650})
                    page.wait_for_timeout(100)
                    layout = page.evaluate('''() => ({width:innerWidth,height:innerHeight,
                        document:document.documentElement.scrollWidth,
                        viewport:document.documentElement.clientWidth})''')
                    result['responsive_layouts'].append(layout)
                    check(f'Overview has no horizontal document overflow at {width}px', layout['document'] <= layout['viewport'] + 1, layout)
                page.set_viewport_size({'width': 1280, 'height': 800})

                open_server('Concurrent SDK fixture')
                inspect('mock.echo')
                for width in (512, 600, 640, 720, 800, 900, 1024, 1079, 1280, 1366, 1440, 1920):
                    page.set_viewport_size({'width': width, 'height': 650})
                    page.wait_for_timeout(100)
                    layout = page.evaluate('''() => ({width:innerWidth,height:innerHeight,state:'inspector',
                        document:document.documentElement.scrollWidth,
                        viewport:document.documentElement.clientWidth})''')
                    result['responsive_layouts'].append(layout)
                    check(f'Inspector has no horizontal document overflow at {width}px', layout['document'] <= layout['viewport'] + 1, layout)
                page.set_viewport_size({'width': 1280, 'height': 800})

                # Reject a real private GET by changing only the browser's
                # request token. No server response or route is fabricated.
                def reject_private_read(route):
                    if route.request.method == 'GET':
                        headers = route.request.all_headers()
                        headers['x-hanni-token'] = 'invalid-review-token'
                        route.continue_(headers=headers)
                    else:
                        route.continue_()

                page.route(api_url, reject_private_read)
                page.get_by_role('button', name='Refresh status', exact=True).click()
                expect(page.locator('.mcp-hub-page > .feature-error')).to_contain_text('Displayed definitions may be stale')
                expect(page.get_by_role('button', name='Add server', exact=True)).to_be_disabled()
                expect(page.get_by_role('button', name='Test & Discover', exact=True)).to_be_disabled()
                expect(page.get_by_role('region', name='Inspect mock.echo', exact=True)).to_be_visible()
                check('Actual rejected private read retains inspectable stale snapshot and blocks writes')
                page.unroute(api_url, reject_private_read)
                page.get_by_role('button', name='Refresh status', exact=True).click()
                expect(page.get_by_role('button', name='Add server', exact=True)).to_be_enabled()
                check('Authenticated refresh recovers mutation controls')
                all_servers()

                open_server('Imported SDK fixture')
                page.get_by_role('button', name='Remove server', exact=True).click()
                page.keyboard.press('Escape')
                check('Remove Escape cancellation preserves actual integration', len(snapshot()['servers']) == 2)
                page.get_by_role('button', name='Remove server', exact=True).click()
                page.get_by_role('button', name='Remove integration', exact=True).click()
                expect(page.locator('.mcp-server-row')).to_have_count(1)
                check('Confirmed removal deletes only selected integration', len(snapshot()['servers']) == 1 and snapshot()['servers'][0]['id'] == main_id)
                check('No discovered tool execution from frontend management', no_calls())
                check('Every frontend mutation uses authenticated fixed UUID/confirmation body', bool(posted) and all(set(body) == {'id', 'operation', 'data', 'confirmed'} and body['confirmed'] is True and len(body['id']) == 36 for body in posted))
                check('No unrelated node power or SSH terminal operation', not fixture.writes)
                check('No frontend JavaScript errors or external browser requests', not result['javascript_errors'] and not result['external_requests'])
                result['protocol_ledger'] = ledger_rows(ledger)
                result['mutation_operations'] = [body['operation'] for body in posted]
                result['passed'] = True
            except Exception as error:
                result['errors'].append(f'{type(error).__name__}: {error}')
                try:
                    page.screenshot(path=str(output/'failure-browser-debug.png'), full_page=True)
                    (output/'failure-browser-text.txt').write_text(page.locator('body').inner_text(), encoding='utf-8')
                except Exception:
                    pass
            finally:
                context.close()
                browser.close()
                (output/'browser-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'checks': len(result['checks']), 'errors': result['errors'], 'output': str(output)}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
