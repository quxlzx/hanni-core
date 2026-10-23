"""Prospective final safe enabled controls, original services and bounded leaves."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button, field, select

def cases():
    inputs, oracles = ([], [])

    def add(key, route, steps, expected, paths):
        identifier = 'safe-gap-' + key
        inputs.append({'id': identifier, 'route': route, 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-safe-gaps-backend', 'window_size': [1280, 800], 'steps': steps, 'readback_paths': list(paths)})
        oracles.append({'id': identifier, 'check': expected, 'scope': 'Original disposable backend/actual native controls; inert MCP initialization is an explicit mocked leaf, never live provider/model/audio/owner effects.'})
    agents = ('/api/agents',)
    add('activity-filter', 'activity', [field('input[aria-label="Search activity and capabilities"]', 'absent-safe-control'), select('Filter execution status', 'failed'), select('Filter execution status', 'all'), field('input[aria-label="Search activity and capabilities"]', '')], {'empty_filter_then_actual_data_return': True, 'no_execution_dispatched': True}, agents)
    add('capability-pagination', 'agents', [button('Next capabilities'), button('Previous capabilities')], {'original_capability_next_previous_rows': True, 'no_registry_execution': True}, agents)
    add('activity-details', 'activity', [{'action': 'click', 'selector': '.execution-record > summary', 'index': 0}, button('Technical details', role='button')], {'original_audit_record_fields_visible': True, 'no_execution_dispatched': True}, agents)
    inputs[-1]['steps'][-1] = {'action': 'click', 'selector': '.execution-record details summary', 'index': 0}
    add('trace-filter-refresh', 'activity', [field('input[aria-label="Search execution traces"]', 'absent-safe-trace'), select('Filter task execution outcome', 'failed'), select('Filter task execution outcome', 'all'), field('input[aria-label="Search execution traces"]', ''), button('Refresh task traces')], {'actual_filter_values_then_original_refreshed_projection': True, 'no_tool_execution': True}, agents)
    add('cluster-filter', 'cluster', [field('input[placeholder="Search name or address"]', 'absent-safe-node'), button('Clear filters')], {'zero_matches_then_original_nodes': True, 'no_node_write': True}, ('/api/cluster',))
    add('cluster-details', 'cluster', [{'action': 'click', 'selector': '.cluster-node', 'index': 0}, {'action': 'click', 'role': 'button', 'name': 'Refresh workers'}, {'action': 'click', 'selector': '.cluster-connection summary', 'index': 0}, {'action': 'click', 'selector': '.cluster-back'}], {'actual_node_details_ssh_text_original_worker_refresh_and_back': True, 'no_ssh_power_or_process': True}, ('/api/cluster',))
    memory = ('/api/memory/explorer?limit=30', '/api/memory/suggestions?limit=20')
    add('modal-memory-project', 'memory', [button('Stored memories', role='tab'), {'action': 'click', 'selector': '.memory-index-row', 'index': 0}, button('Correct memory'), {'action': 'select', 'selector': 'dialog select', 'index': 0, 'value': ''}, {'action': 'select', 'selector': 'dialog select', 'index': 1, 'value': 'historical'}, button('Cancel')], {'actual_modal_project_unassigned_and_statement_historical': True, 'no_memory_correction': True}, memory)
    add('positive-local-proposal', 'memory', [{'action': 'click', 'selector': '.memory-tabs button', 'index': 1}, button('Suggest from a statement'), field('dialog textarea', 'I prefer concise spoken responses.'), {'action': 'select', 'selector': 'dialog select', 'value': ''}, button('Create suggestion', settle_ms=700)], {'pending_statement': 'I prefer concise spoken responses.', 'pending_increment': 1, 'source': 'owner_requested:local_rules', 'source_ref_prefix': 'desktop-review-request:', 'authoritative_memory_unchanged': True, 'no_model_or_laya': True}, memory)
    mcp = ('/api/mcp',)
    reset = [button('Workspace settings'), button('MCP Hub'), {'action': 'click', 'selector': '.mcp-server-row', 'index': 0}]
    add('approved-inert-enable', 'mcp', reset + [button('Enable server'), button('Confirm change', settle_ms=600)], {'server_name': 'Controlled approved inert integration', 'enabled': True, 'state': 'connected', 'original_matching_hash_approval': True, 'transport_mock_only': True, 'no_process_network_or_tool_call': True}, mcp)
    add('approved-inert-disable', 'mcp', reset + [button('Disable server'), button('Confirm change', settle_ms=600)], {'server_name': 'Controlled approved inert integration', 'enabled': False, 'state': 'disabled', 'original_matching_hash_approval': True, 'transport_mock_only': True, 'no_process_network_or_tool_call': True}, mcp)
    add('mcp-empty-tool-filters', 'mcp', reset + [field('input[aria-label="Search MCP tools"]', 'absent-inert-tool'), select('Filter MCP tools', 'review'), select('Filter MCP tools', 'all'), field('input[aria-label="Search MCP tools"]', ''), {'action': 'click', 'selector': '.mcp-connection-details summary'}, button('‹ All servers')], {'actual_empty_tools_filter_values_and_connection_details': True, 'no_provider_dispatch': True}, mcp)
    add('home-cluster-navigation', 'home', [button('Inspect cluster')], {'route': 'cluster'}, ('/api/cluster',))
    add('home-conversation-navigation', 'home', [button('Open conversation')], {'route': 'chat', 'no_generation': True}, ('/api/productivity',))
    add('home-mission-navigation', 'home', [button('Inspect')], {'route': 'mission'}, ('/api/productivity',))
    add('mission-cluster-navigation', 'mission', [button('View cluster')], {'route': 'cluster'}, ('/api/cluster',))
    add('notification-inspect', 'notifications', [{'action': 'click', 'selector': '.notification-group-item:has-text("Controlled QA record available") button:has-text("Inspect event")'}], {'route': 'projects', 'original_notification_read_and_target_retained': True}, ('/api/notifications', '/api/productivity'))
    add('notification-clear', 'notifications', [button('Clear all'), button('Clear notifications', settle_ms=700)], {'original_notifications_all_dismissed': True, 'no_provider_write': True}, ('/api/notifications',))
    add('settings-read-only-details', 'settings', [{'action': 'click', 'selector': '.allowed-actions summary'}, button('Refresh devices'), button('Refresh GPUs')], {'original_allowed_action_details_and_device_gpu_refresh': True, 'no_device_or_model_apply': True}, ('/api/voice', '/api/model-lab'))
    for row in inputs:
        validate_input(row)
    return (inputs, oracles)

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Preserve prospective seals and raw outcomes.')
    inputs, oracles = cases()
    output.mkdir(parents=True)
    hashes = {}
    for name, obj in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(obj, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': len(inputs), 'hashes': hashes, 'execution_attempted': False, 'model_generation': False, 'live_provider': False, 'mcp_scope': 'Actual manager and config-hash approval, explicitly inert mocked initialization/runtime leaf only.'}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
