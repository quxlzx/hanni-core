"""Prospective bounded last local-proposal/configuration controls, no provider use."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button, field, select

def cases():
    inputs, oracles = ([], [])

    def add(key, route, steps, expected, paths):
        identifier = 'local-final-' + key
        inputs.append({'id': identifier, 'route': route, 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-populated-dense-backend', 'window_size': [1280, 800], 'steps': steps, 'readback_paths': list(paths)})
        oracles.append({'id': identifier, 'check': expected, 'scope': 'Original isolated local persistence/proposals/imports only; no provider/model execution, owner clipboard, file-picker, or autonomous memory claim.'})
    memory = ('/api/memory/explorer?limit=30', '/api/memory/suggestions?limit=20')
    add('memory-create-proposal', 'memory', [button('Review queue', role='tab'), button('Suggest from a statement'), field('dialog textarea', 'I prefer concise local QA status notes.'), {'action': 'select', 'selector': 'dialog select', 'value': ''}, button('Create suggestion', settle_ms=700)], {'pending_statement': 'I prefer concise local QA status notes.', 'no_implicit_approval': True, 'no_laya_or_model_request': True}, memory)
    add('memory-consolidate', 'memory', [button('Find related records'), {'action': 'select', 'selector': 'dialog select', 'value': ''}, button('Find suggestions', settle_ms=1000)], {'local_relationship_proposals_or_honest_empty_result': True, 'stored_records_unchanged': True, 'no_laya_or_model_request': True}, memory)
    add('memory-review-index', 'memory', [{'action': 'click', 'selector': 'section[aria-label="Pending memory suggestions"] .memory-index-row', 'index': 0}], {'actual_selected_pending_record': True}, memory)
    add('memory-correction-fields-cancel', 'memory', [button('Stored memories', role='tab'), {'action': 'click', 'selector': '.memory-index-row', 'index': 0}, button('Correct memory'), select('Project', ''), select('Statement type', 'historical'), select('Statement type', 'statement'), button('Cancel')], {'explicit_select_values_measured': True, 'no_correction_write': True}, memory)
    add('memory-history-old-row', 'memory', [field('.memory-search input', 'Controlled correction history revision 51'), {'action': 'click', 'selector': '.memory-index-row', 'index': 0}, button('Older corrections'), {'action': 'click', 'selector': '.memory-history details summary', 'index': 0}, button('Newer corrections')], {'original_older_content_visible_before_return': True, 'offset50_then0': True, 'no_record_write': True}, memory)
    mcp = ('/api/mcp',)
    add('mcp-first-server-draft', 'mcp', [button('Add your first server'), button('Cancel')], {'first_server_dialog_cancelled': True, 'no_configuration_commit': True}, mcp)
    add('mcp-file-preview', 'mcp', [button('Import config'), {'action': 'upload_fixture', 'selector': 'dialog input[type="file"]', 'fixture_id': 'mcp-disabled-config'}, button('Preview import')], {'original_file_read_and_valid_preview': True, 'server_not_yet_saved': True, 'no_physical_file_picker_claim': True}, mcp)
    add('mcp-import-selection', 'mcp', [{'action': 'click', 'selector': 'dialog .mcp-import-candidate input[type="checkbox"]'}, {'action': 'click', 'selector': 'dialog .mcp-import-candidate input[type="checkbox"]'}], {'selection_changed_then_restored': True, 'no_configuration_commit': True}, mcp)
    add('mcp-import-confirm', 'mcp', [button('Import selected'), button('Confirm change', settle_ms=700)], {'server_name': 'Controlled native file integration', 'server_enabled': False, 'auto_connect': False, 'tools_empty': True, 'no_provider_process_or_connection': True}, mcp)
    add('mcp-enable-local', 'mcp', [{'action': 'click', 'selector': '.mcp-server-row', 'index': 0}, button('Enable server'), button('Confirm change', settle_ms=600)], {'server_enabled': True, 'auto_connect': False, 'no_provider_process_or_connection': True}, mcp)
    add('mcp-disable-local', 'mcp', [button('Disable server'), button('Confirm change', settle_ms=600)], {'server_enabled': False, 'auto_connect': False, 'no_provider_process_or_connection': True}, mcp)
    add('mcp-private-export-select', 'mcp', [button('Back to servers'), button('Export config'), {'action': 'press', 'selector': '#mcp-export-path', 'key': 'Control+a'}, {'action': 'press', 'selector': '#mcp-export-json', 'key': 'Control+a'}, button('Close export')], {'private_export_under_exact_owned_root': True, 'actual_json_contains_disabled_fixture_config': True, 'credentials_and_approvals_excluded': True, 'owner_clipboard_unchanged': True}, mcp)
    for row in inputs:
        validate_input(row)
    return (inputs, oracles)

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Keep every seal and first result immutable.')
    output.mkdir(parents=True)
    inputs, oracles = cases()
    hashes = {}
    for name, value in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(value, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': len(inputs), 'hashes': hashes, 'execution_attempted': False, 'generation_authorized': False, 'provider_execution_authorized': False, 'uploads': 'Exactly one bounded public synthetic file buffer; no arbitrary file paths or Windows picker acceptance.'}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
