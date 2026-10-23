"""Additional prospective primary controls, without external execution authority."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button, field, select

def cases():
    inputs, oracles = ([], [])

    def add(identifier, route, steps, check, paths):
        inputs.append({'id': identifier, 'route': route, 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-populated-backend', 'window_size': [1280, 800], 'steps': steps, 'readback_paths': list(paths)})
        oracles.append({'id': identifier, 'check': check, 'common': ['actual_owned_hwnd', 'original_native_control_action', 'original_authoritative_readback', 'no_owner_mutation', 'no_model_or_external_provider_dispatch']})
    mcp = ('/api/mcp',)
    add('primary-mcp-editor-close', 'mcp', [button('Add server'), field('#mcp-name', 'Cancelled local draft'), button('Close dialog')], {'dialog_closed': True, 'server_absent': 'Cancelled local draft', 'no_mutation': True}, mcp)
    add('primary-mcp-stdio-save', 'mcp', [button('Add server'), field('#mcp-name', 'Controlled native integration'), field('#mcp-command', 'campaign8-no-launch.exe'), field('#mcp-args', '[]'), field('#mcp-env', '{}'), field('#mcp-timeout', '2'), button('Save server')], {'server_config': {'name': 'Controlled native integration', 'command': 'campaign8-no-launch.exe', 'args': [], 'timeout_seconds': 2}, 'never_connected': True}, mcp)
    add('primary-mcp-search-no-match', 'mcp', [field('input[aria-label="Search MCP servers"]', 'absent-native-integration-theta')], {'visible_text': 'No servers match this search.', 'no_mutation': True}, mcp)
    add('primary-mcp-search-reset', 'mcp', [field('input[aria-label="Search MCP servers"]', '')], {'visible_text': 'Controlled native integration', 'no_mutation': True}, mcp)
    add('primary-mcp-detail-settings', 'mcp', [{'action': 'click', 'selector': '.mcp-server-row'}, {'action': 'click', 'selector': '.mcp-connection-details summary'}], {'connection_settings_visible': True, 'no_mutation': True}, mcp)
    add('primary-mcp-edit-save', 'mcp', [button('Edit settings'), field('#mcp-name', 'Controlled revised integration'), button('Save server')], {'server_config': {'name': 'Controlled revised integration'}, 'never_connected': True}, mcp)
    add('primary-mcp-remove-cancel', 'mcp', [button('Remove server'), button('Cancel')], {'server_retained': 'Controlled revised integration', 'no_delete_write': True}, mcp)
    add('primary-mcp-remove-confirm', 'mcp', [button('Remove server'), button('Remove integration')], {'server_absent': 'Controlled revised integration', 'no_external_effect': True}, mcp)
    add('primary-mcp-http-draft-cancel', 'mcp', [button('Add server'), {'action': 'select', 'selector': '#mcp-transport', 'value': 'streamable_http'}, field('#mcp-name', 'Cancelled HTTP draft'), field('#mcp-url', 'http://127.0.0.1:49159/mcp'), {'action': 'select', 'selector': '#mcp-auth', 'value': 'bearer_env'}, field('#mcp-auth-reference', 'CAMPAIGN8_UNUSED_REFERENCE'), button('Cancel')], {'server_absent': 'Cancelled HTTP draft', 'no_mutation': True, 'no_auth_resolution': True}, mcp)
    add('primary-mcp-import-invalid', 'mcp', [button('Import config'), field('.mcp-import-json', 'not valid JSON'), button('Preview import')], {'error_feedback_visible': True, 'no_mutation': True}, mcp)
    add('primary-mcp-import-preview', 'mcp', [button('Import config'), field('.mcp-import-json', json.dumps({'mcpServers': {'Controlled preview only': {'command': 'campaign8-no-launch.exe', 'args': []}}})), button('Preview import')], {'preview_visible': True, 'no_configuration_commit': True, 'no_external_effect': True}, mcp)
    add('primary-mcp-status-filter', 'mcp', [select('Filter MCP server status', 'disabled'), select('Filter MCP server status', 'all'), button('Refresh status')], {'filter_reset': True, 'no_configuration_commit': True}, mcp)
    routing = ('/api/model-routing',)
    add('primary-routing-fast-save', 'model-routing', [select('Selection policy', 'fast'), button('Apply policy')], {'persisted_policy': 'fast', 'no_inference': True}, routing)
    add('primary-routing-quality-save', 'model-routing', [select('Selection policy', 'quality'), button('Apply policy')], {'persisted_policy': 'quality', 'no_inference': True}, routing)
    add('primary-routing-manual-draft', 'model-routing', [select('Selection policy', 'manual')], {'preferred_endpoint_control_visible': True, 'persisted_policy': 'quality', 'no_inference': True}, routing)
    add('primary-routing-balanced-restore', 'model-routing', [select('Selection policy', 'balanced'), button('Apply policy')], {'persisted_policy': 'balanced', 'no_inference': True}, routing)
    add('primary-routing-capability-details', 'model-routing', [{'action': 'click', 'selector': '.routing-endpoint summary', 'index': 0}], {'endpoint_limits_expanded': True, 'no_mutation': True}, routing)
    models = ('/api/model-lab',)
    for identifier, name in [('name', 'Model / endpoint'), ('availability', 'Available'), ('context', 'Verified context')]:
        add('primary-model-sort-' + identifier, 'models', [button(name)], {'sort_heading_activated': name, 'model_inventory_unchanged': True, 'no_inference': True}, models)
    add('primary-model-endpoint-select', 'models', [{'action': 'click', 'selector': '.lab-row-link', 'index': 0}], {'endpoint_detail_visible': True, 'original_identity_truth': True, 'no_mutation': True}, models)
    add('primary-model-results-filter', 'models', [{'action': 'click', 'selector': '.lab-tabs button', 'index': 2}, field('input[aria-label="Search benchmark history"]', 'absent-native-benchmark-lambda')], {'empty_history_visible': True, 'no_fake_results': True, 'no_mutation': True}, models)
    add('primary-model-compare-empty', 'models', [button('Compare')], {'no_measured_comparison_claim': True, 'no_mutation': True}, models)
    memory = ('/api/memory/explorer?limit=30', '/api/memory/projects')
    add('primary-memory-refresh', 'memory', [button('Refresh')], {'original_store_projection_current': True, 'no_mutation': True}, memory)
    add('primary-memory-mode-details', 'memory', [{'action': 'click', 'selector': '.memory-mode-details summary'}], {'mode_details_visible': True, 'keyword_vs_semantic_truth': True, 'no_mutation': True}, memory)
    add('primary-memory-consolidate-cancel', 'memory', [{'action': 'click', 'selector': '.memory-tabs [role="tab"]', 'index': 1}, button('Find related records'), button('Cancel')], {'dialog_closed': True, 'no_consolidation_write': True}, memory)
    add('primary-memory-analyze-cancel', 'memory', [button('Suggest from a statement'), field('dialog textarea', 'Synthetic uncommitted preview preference.'), button('Cancel')], {'dialog_closed': True, 'no_suggestion_write': True}, memory)
    settings = ('/api/workspace',)
    add('primary-settings-refresh', 'settings', [button('Refresh settings')], {'original_config_projection_current': True, 'no_owner_config_write': True}, settings)
    add('primary-settings-motion-toggle', 'settings', [{'action': 'click', 'selector': '#motion'}], {'local_motion_toggle': True, 'no_backend_write': True}, settings)
    add('primary-settings-motion-restore', 'settings', [{'action': 'click', 'selector': '#motion'}], {'local_motion_restored': True, 'no_backend_write': True}, settings)
    for name in ['Audio', 'Model routing', 'Permissions']:
        add('primary-settings-section-' + name.lower().replace(' ', '-'), 'settings', [{'action': 'click', 'role': 'link', 'name': name}], {'section_reached': name, 'no_owner_config_write': True}, settings)
    notifications = ('/api/notifications',)
    add('primary-notification-preference-disable', 'notifications', [{'action': 'click', 'selector': '.notification-preferences summary'}, {'action': 'check', 'selector': '.notification-preferences input', 'index': 0, 'checked': False}], {'original_local_category_preference': False, 'no_external_notification': True}, notifications)
    add('primary-notification-preference-restore', 'notifications', [{'action': 'check', 'selector': '.notification-preferences input', 'index': 0, 'checked': True}], {'original_local_category_preference': True, 'no_external_notification': True}, notifications)
    calendar = ('/api/calendar?start_date=2026-10-10&days=7', '/api/productivity')
    add('primary-calendar-range-daily', 'calendar', [select('Calendar range', '1')], {'daily_local_range': True, 'no_connected_provider': True, 'no_mutation': True}, calendar)
    add('primary-calendar-range-weekly', 'calendar', [select('Calendar range', '7'), field('input[aria-label="Calendar start date"]', '2026-10-10')], {'weekly_local_range': True, 'deadline_grounded': True, 'no_connected_provider': True}, calendar)
    add('primary-calendar-refresh-empty-vault', 'calendar', [button('Refresh calendar')], {'not_connected': True, 'no_provider_dispatch': True, 'local_deadlines_unchanged': True}, calendar)
    add('primary-workspace-inspector-open', 'home', [button('Show inspector')], {'inspector_visible': True, 'no_backend_write': True}, settings)
    add('primary-workspace-inspector-close', 'home', [button('Hide inspector')], {'inspector_closed': True, 'no_backend_write': True}, settings)
    for row in inputs:
        validate_input(row)
    return (inputs, oracles)

def publish(root):
    root = Path(root)
    if root.exists():
        raise ValueError('Preserve prospective inputs and all previous checkpoints.')
    root.mkdir(parents=True)
    inputs, oracles = cases()
    hashes = {}
    for name, value in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(value, indent=2) + '\n'
        (root / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    result = {'cases': len(inputs), 'hashes': hashes, 'attempted': False, 'scope': 'Original isolated native local primary controls; config CRUD never starts/connects MCP or models, no physical audio, no owner configuration/clipboard writes.'}
    (root / 'SEAL.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8', newline='\n')
    return result
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(publish(parser.parse_args().output)))
