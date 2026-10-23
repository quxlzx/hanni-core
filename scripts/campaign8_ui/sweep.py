"""Remaining safe native local controls, sealed before their first execution."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button, field, select

def cases():
    inputs, oracles = ([], [])

    def add(key, route, steps, expectation, paths=('/api/productivity',)):
        inputs.append({'id': 'sweep-' + key, 'route': route, 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-populated-dense-backend', 'window_size': [1280, 800], 'steps': steps, 'readback_paths': list(paths)})
        oracles.append({'id': 'sweep-' + key, 'check': expectation, 'scope': 'Original isolated local controls only; draft values and actual persistent effects checked independently, no external/model dispatch.'})
    add('task-all-fields', 'tasks', [button('New task'), field('#workspace-title', 'Controlled final field task'), field('#workspace-due', '2026-10-12'), field('#workspace-course', 'Synthetic field controls'), {'action': 'select', 'selector': '#workspace-priority', 'value': 'normal'}, {'action': 'select', 'selector': '#workspace-project', 'value': ''}, button('Save')], {'persisted_task': {'title': 'Controlled final field task', 'course': 'Synthetic field controls', 'priority': 'normal', 'project_id': None}})
    add('task-edit-status', 'tasks', [field('input[aria-label="Search tasks"]', 'Controlled final field task'), {'action': 'click', 'selector': '.task-title'}, {'action': 'select', 'selector': '#workspace-status', 'value': 'completed'}, button('Save')], {'persisted_task': {'title': 'Controlled final field task', 'status': 'completed'}})
    add('task-refresh', 'tasks', [button('Refresh tasks')], {'store_unchanged': True})
    add('task-project-filter', 'tasks', [select('Task project', ''), field('input[aria-label="Search tasks"]', '')], {'store_unchanged': True, 'filter_values': {'project': ''}})
    add('workspace-backup', 'tasks', [button('Back up workspace')], {'owned_backup_created': True, 'no_owner_write': True})
    add('project-link-save', 'projects', [button('Add link'), field('#workspace-title', 'Controlled final URL'), {'action': 'select', 'selector': '#workspace-link-kind', 'value': 'url'}, field('#workspace-target', 'https://example.invalid/controlled-ui-only'), button('Save')], {'persisted_link': {'label': 'Controlled final URL', 'kind': 'url', 'target': 'https://example.invalid/controlled-ui-only'}, 'url_never_opened': True})
    add('project-link-delete', 'projects', [button('Remove Controlled final URL link'), button('Confirm deletion')], {'link_absent': 'Controlled final URL'})
    add('project-note-delete', 'projects', [button('Delete note', index=0), button('Confirm deletion')], {'selected_note_removed': True, 'project_retained': 'Controlled QA observatory'})
    memory = ('/api/memory/explorer?limit=30', '/api/memory/suggestions?limit=20')
    add('memory-type-filter', 'memory', [{'action': 'select', 'selector': '.memory-search select', 'index': 1, 'value': 'preference'}, {'action': 'select', 'selector': '.memory-search select', 'index': 1, 'value': ''}], {'filter_values': {'type': ''}, 'store_unchanged': True}, memory)
    add('memory-project-filter', 'memory', [{'action': 'select', 'selector': '.memory-search select', 'index': 0, 'value': ''}], {'filter_values': {'project': ''}, 'store_unchanged': True}, memory)
    add('memory-order', 'memory', [{'action': 'select', 'selector': '.memory-search select', 'index': 2, 'value': 'created'}], {'filter_values': {'sort': 'created'}, 'store_unchanged': True}, memory)
    add('memory-record-pages', 'memory', [button('Next'), button('Previous')], {'pagination_forward_back': True, 'store_unchanged': True}, memory)
    add('memory-review-pages', 'memory', [{'action': 'click', 'selector': '.memory-tabs [role="tab"]', 'index': 1}, button('Next'), button('Previous')], {'review_forward_back': True, 'store_unchanged': True}, memory)
    add('memory-approve', 'memory', [button('Approve'), button('Approve memory')], {'explicit_suggestion_approved': True, 'stored_count_increased_once': True}, memory)
    add('memory-edit-approve', 'memory', [button('Edit & approve'), field('dialog textarea', 'Controlled final edited review statement.'), button('Approve memory')], {'edited_suggestion_approved': True, 'exact_statement_stored': 'Controlled final edited review statement.'}, memory)
    add('memory-dismiss', 'memory', [button('Dismiss'), button('Dismiss suggestion')], {'selected_suggestion_dismissed': True, 'stored_count_unchanged': True}, memory)
    add('memory-review-dialog-fields', 'memory', [button('Suggest from a statement'), field('dialog textarea', 'Controlled uncommitted reusable statement.'), {'action': 'select', 'selector': 'dialog select', 'value': ''}, button('Cancel')], {'dialog_closed': True, 'no_suggestion_write': True}, memory)
    add('memory-history-pages', 'memory', [button('Stored memories', role='tab'), {'action': 'select', 'selector': '.memory-search select', 'index': 2, 'value': 'updated'}, field('.memory-search input', 'Controlled correction history revision 51'), {'action': 'click', 'selector': '.memory-index-row', 'index': 0}, button('Older corrections'), button('Newer corrections'), field('.memory-search input', '')], {'history_forward_back': True, 'store_unchanged': True}, memory)
    add('memory-project-alias', 'memory', [{'action': 'click', 'selector': '.memory-tabs [role="tab"]', 'index': 2}, {'action': 'click', 'selector': '.memory-project-index button', 'index': 0}, button('Add alias'), field('dialog input', 'Controlled UI alias'), button('Save change')], {'alias_persisted': 'Controlled UI alias'}, memory)
    add('memory-link-workflow-cancel', 'memory', [button('Link workflow'), field('dialog input', 'wf_controlled_uncommitted_id'), button('Cancel')], {'dialog_closed': True, 'workflow_associations_unchanged': True}, memory)
    mcp = ('/api/mcp',)
    add('mcp-stdio-fields-cancel', 'mcp', [button('Add server'), field('#mcp-name', 'Controlled cancelled stdio'), field('#mcp-command', 'campaign8-no-launch.exe'), field('#mcp-args', '["--never-launch"]'), field('#mcp-cwd', 'C:\\campaign8-not-opened'), field('#mcp-env', '{"MODE":"CAMPAIGN8_UNUSED_VAR"}'), field('#mcp-timeout', '4'), button('Cancel')], {'server_absent': 'Controlled cancelled stdio', 'draft_values_measured': True, 'no_auth_resolution': True}, mcp)
    add('mcp-http-fields-cancel', 'mcp', [button('Add server'), {'action': 'select', 'selector': '#mcp-transport', 'value': 'streamable_http'}, field('#mcp-name', 'Controlled cancelled HTTP'), field('#mcp-url', 'http://127.0.0.1:49159/mcp'), {'action': 'select', 'selector': '#mcp-auth', 'value': 'bearer_secret'}, field('#mcp-auth-reference', 'campaign8-nonexistent-secret-reference'), {'action': 'click', 'selector': '.mcp-checkbox input'}, button('Cancel')], {'server_absent': 'Controlled cancelled HTTP', 'draft_values_measured': True, 'no_auth_resolution': True}, mcp)
    add('mcp-workspace-navigation', 'mcp', [button('Workspace settings')], {'route': 'settings'}, mcp)
    models = ('/api/model-lab',)
    add('lab-benchmark-fields-only', 'models', [button('Benchmark runner'), select('Benchmark suite', 'llm-tools-development'), field('input[aria-label="Cases"]', '2'), field('input[aria-label="Repetitions"]', '2'), field('input[aria-label="Output tokens"]', '64'), field('input[aria-label="Tool rounds"]', '2'), button('Overview')], {'draft_values_measured': {'Cases': '2', 'Repetitions': '2', 'Output tokens': '64', 'Tool rounds': '2'}, 'no_benchmark_start': True}, models)
    add('lab-history-filters', 'models', [{'action': 'click', 'selector': '.lab-tabs button', 'index': 2}, select('Filter run status', 'completed'), select('Filter benchmark suite', 'structured-development')], {'empty_filtered_history': True, 'no_fake_results': True}, models)
    add('lab-refresh', 'models', [button('Overview'), button('Refresh inventory')], {'original_projection_refreshed': True, 'no_benchmark_start': True}, models)
    add('routing-refresh', 'model-routing', [button('Refresh endpoints')], {'original_projection_refreshed': True}, ('/api/model-routing',))
    add('activity-refresh', 'activity', [button('Refresh activity')], {'original_projection_refreshed': True}, ('/api/agents',))
    add('workflows-refresh', 'workflows', [button('Refresh workflows')], {'original_projection_refreshed': True}, ('/api/workflows',))
    add('notifications-refresh', 'notifications', [button('Refresh notifications')], {'original_projection_refreshed': True}, ('/api/notifications',))
    add('notifications-category-filter', 'notifications', [select('Notification category', 'application'), select('Notification category', 'all')], {'notification_category_reset': True}, ('/api/notifications',))
    add('notifications-clear-cancel', 'notifications', [button('Clear all'), button('Cancel')], {'original_notification_history_retained': True}, ('/api/notifications',))
    for row in inputs:
        validate_input(row)
    return (inputs, oracles)

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Preserve every sealed development version.')
    output.mkdir(parents=True)
    inputs, oracles = cases()
    hashes = {}
    for name, obj in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(obj, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': len(inputs), 'hashes': hashes, 'execution_attempted': False, 'model_generation': False, 'owner_effects': False, 'fixture': 'Original disposable stores, dense synthetic pagination/review seeds; no mock HTTP projections.'}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    print(json.dumps(publish(parser.parse_args().output)))
