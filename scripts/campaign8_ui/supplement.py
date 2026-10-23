"""Prospective populated original-store native controls; no oracle enters execution."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .plan import validate_input

def button(name, **kwargs):
    return {'action': 'click', 'role': 'button', 'name': name, **kwargs}

def field(selector, value):
    return {'action': 'fill', 'selector': selector, 'value': value}

def select(name, value):
    return {'action': 'select', 'role': 'combobox', 'name': name, 'value': value}

def cases():
    inputs, oracles = ([], [])

    def add(identifier, route, steps, check, paths=('/api/productivity',)):
        inputs.append({'id': identifier, 'route': route, 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-populated-backend', 'window_size': [1280, 800], 'steps': steps, 'readback_paths': list(paths)})
        oracles.append({'id': identifier, 'check': check, 'common': ['actual_owned_native_hwnd', 'original_control_action', 'authoritative_original_readback', 'no_owner_effect', 'screenshot_and_focus_evidence']})
    add('task-create-local', 'tasks', [button('New task'), field('#workspace-title', 'Controlled UI new task'), field('#workspace-course', 'Native QA'), {'action': 'select', 'selector': '#workspace-priority', 'value': 'high'}, button('Save')], {'persisted_task': {'title': 'Controlled UI new task', 'priority': 'high', 'status': 'open'}, 'dialog_closed': True})
    add('task-complete-local', 'tasks', [button('Complete Controlled UI new task')], {'persisted_task': {'title': 'Controlled UI new task', 'status': 'completed'}})
    add('task-reopen-local', 'tasks', [select('Task status', 'all'), button('Reopen Controlled UI new task')], {'persisted_task': {'title': 'Controlled UI new task', 'status': 'open'}})
    add('task-edit-local', 'tasks', [field('input[aria-label="Search tasks"]', 'Controlled UI new task'), {'action': 'click', 'selector': '.task-title'}, field('#workspace-title', 'Controlled UI revised task'), {'action': 'select', 'selector': '#workspace-priority', 'value': 'low'}, button('Save'), field('input[aria-label="Search tasks"]', '')], {'persisted_task': {'title': 'Controlled UI revised task', 'priority': 'low'}})
    add('task-cancel-deletion', 'tasks', [button('Delete Controlled UI revised task'), button('Cancel')], {'task_retained': 'Controlled UI revised task', 'no_delete_write': True})
    add('task-delete-local', 'tasks', [button('Delete Controlled UI revised task'), button('Confirm deletion')], {'task_absent': 'Controlled UI revised task'})
    add('task-draft-cancel', 'tasks', [button('New task'), field('#workspace-title', 'Controlled UI cancelled draft'), button('Cancel')], {'task_absent': 'Controlled UI cancelled draft', 'no_create_write': True})
    add('task-no-match-filter', 'tasks', [field('input[aria-label="Search tasks"]', 'absent-native-task-zeta')], {'visible_text': 'No tasks match your filters.', 'no_mutation': True})
    add('task-filter-clear', 'tasks', [field('input[aria-label="Search tasks"]', '')], {'visible_text': 'Controlled QA inspect retained report', 'no_mutation': True})
    add('task-completed-filter', 'tasks', [select('Task status', 'completed')], {'visible_text': 'No tasks in this view.', 'no_mutation': True})
    add('task-all-filter', 'tasks', [select('Task status', 'all')], {'visible_text': 'Controlled QA inspect retained report', 'no_mutation': True})
    add('project-create-local', 'projects', [button('New project'), field('#workspace-title', 'Controlled UI project'), field('#workspace-body', 'Original native project form persisted locally.'), button('Save')], {'persisted_project': {'name': 'Controlled UI project'}, 'dialog_closed': True})
    add('project-select-original', 'projects', [{'action': 'click', 'selector': '.project-list button', 'index': 0}], {'visible_text': 'Controlled QA observatory', 'no_mutation': True})
    add('project-note-create', 'projects', [button('Add note'), field('#workspace-title', 'Controlled UI new note'), field('#workspace-body', 'Synthetic note persisted through original native form.'), button('Save')], {'persisted_note': {'title': 'Controlled UI new note'}})
    add('project-note-open', 'projects', [{'action': 'click', 'selector': '.project-note summary', 'index': 0}], {'note_expanded': True, 'no_mutation': True})
    add('project-note-edit', 'projects', [{'action': 'click', 'selector': '.project-note button', 'index': 0}, field('#workspace-body', 'Controlled note correction retained in original SQLite.'), button('Save')], {'persisted_note_body': 'Controlled note correction retained in original SQLite.'})
    add('project-note-delete-cancel', 'projects', [button('Delete note', index=0), button('Cancel')], {'notes_retained': True, 'no_delete_write': True})
    add('project-link-draft-cancel', 'projects', [button('Add link'), field('#workspace-title', 'Controlled cancelled link'), button('Cancel')], {'link_absent': 'Controlled cancelled link', 'no_create_write': True})
    add('project-link-remove-cancel', 'projects', [button('Remove Controlled QA report link'), button('Cancel')], {'link_retained': 'Controlled QA report', 'artifact_retained': True})
    add('project-link-remove-local', 'projects', [button('Remove Controlled QA report link'), button('Confirm deletion')], {'link_absent': 'Controlled QA report', 'artifact_retained': True})
    add('project-new-select', 'projects', [{'action': 'click', 'selector': '.project-list button', 'index': 1}], {'visible_text': 'Controlled UI project', 'no_mutation': True})
    add('project-edit-local', 'projects', [button('Edit project'), field('#workspace-body', 'Native updated project description.'), button('Save')], {'persisted_project': {'name': 'Controlled UI project', 'description': 'Native updated project description.'}})
    add('project-delete-cancel', 'projects', [button('Delete project'), button('Cancel')], {'project_retained': 'Controlled UI project', 'no_delete_write': True})
    add('project-delete-local', 'projects', [button('Delete project'), button('Confirm deletion')], {'project_absent': 'Controlled UI project', 'original_project_retained': True})
    memory_paths = ('/api/memory/explorer?limit=30', '/api/memory/suggestions?limit=20')
    add('memory-no-match-search', 'memory', [field('.memory-search input', 'absent-native-memory-eta')], {'visible_text': 'No matching memories', 'no_mutation': True}, memory_paths)
    add('memory-search-clear', 'memory', [field('.memory-search input', '')], {'visible_text': 'For the controlled observatory, use concise status notes.', 'no_mutation': True}, memory_paths)
    add('memory-correction-cancel', 'memory', [button('Correct memory'), button('Cancel')], {'memory_content_retained': 'For the controlled observatory, use concise status notes.', 'no_correction_write': True}, memory_paths)
    add('memory-correction-save', 'memory', [button('Correct memory'), field('dialog textarea', 'For the controlled observatory, retain clear short status notes.'), button('Save change')], {'memory_content': 'For the controlled observatory, retain clear short status notes.', 'history_retained': True}, memory_paths)
    add('memory-delete-cancel', 'memory', [button('Delete'), button('Cancel')], {'memory_retained': True, 'no_delete_write': True}, memory_paths)
    add('memory-review-queue', 'memory', [{'action': 'click', 'selector': '.memory-tabs button', 'index': 1}], {'visible_text': 'Controlled observatory reviews happen on Friday.', 'no_mutation': True}, memory_paths)
    add('memory-review-reject-cancel', 'memory', [button('Reject'), button('Cancel')], {'suggestion_pending': True, 'no_review_write': True}, memory_paths)
    add('memory-review-reject-local', 'memory', [button('Reject'), button('Reject suggestion')], {'suggestion_rejected': True, 'no_new_memory': True}, memory_paths)
    add('memory-project-tab', 'memory', [{'action': 'click', 'selector': '.memory-tabs button', 'index': 2}], {'visible_text': 'Controlled QA observatory', 'no_mutation': True}, memory_paths)
    add('memory-stored-tab', 'memory', [button('Stored memories', role='tab')], {'visible_text': 'Saved record', 'no_mutation': True}, memory_paths)
    add('notification-mark-read', 'notifications', [button('Mark read', index=0)], {'notification_read_count_minimum': 1}, ('/api/notifications',))
    add('notification-all-filter', 'notifications', [select('Notification state', 'all')], {'visible_text': 'Controlled QA record available', 'no_mutation': True}, ('/api/notifications',))
    add('notification-dismiss-local', 'notifications', [button('Dismiss', index=0)], {'notification_dismissed_count_minimum': 1}, ('/api/notifications',))
    add('notification-history-filter', 'notifications', [select('Notification state', 'history')], {'notification_history_retained': True, 'no_mutation': True}, ('/api/notifications',))
    add('notification-preferences-open', 'notifications', [{'action': 'click', 'selector': '.notification-preferences summary'}], {'preferences_visible': True, 'no_mutation': True}, ('/api/notifications',))
    add('workflow-completed-filter', 'workflows', [select('Workflow status', 'completed'), {'action': 'click', 'selector': '.workflow-row'}], {'completed_fixture_receipt_matches_store': True, 'not_autonomous_planning_success': True}, ('/api/workflows',))
    add('workflow-output-open', 'workflows', [button('View output')], {'dialog_output_matches_actual_owned_artifact': True, 'no_mutation': True}, ('/api/workflows',))
    add('workflow-output-close', 'workflows', [button('View output'), {'action': 'press', 'selector': 'dialog', 'key': 'Escape'}], {'dialog_closed': True, 'no_mutation': True}, ('/api/workflows',))
    add('workflow-checkpoint-history', 'workflows', [{'action': 'click', 'selector': '.workflow-history summary'}], {'persisted_checkpoints_visible': True, 'no_mutation': True}, ('/api/workflows',))
    add('workflow-no-match-search', 'workflows', [button('Back to workflows'), field('input[aria-label="Search workflows"]', 'absent-native-goal-iota')], {'no_matching_workflows': True, 'no_mutation': True}, ('/api/workflows',))
    add('workflow-filter-reset', 'workflows', [field('input[aria-label="Search workflows"]', ''), select('Workflow status', 'all')], {'pending_approval_blocked_unattached_controller': True, 'no_mutation': True}, ('/api/workflows',))
    add('activity-audit-search', 'activity', [field('input[aria-label="Search activity and capabilities"]', 'workspace.task')], {'original_local_task_audit_visible': True, 'no_mutation': True}, ('/api/agents',))
    add('activity-failed-filter', 'activity', [select('Filter execution status', 'failed')], {'failure_filter_selected': True, 'no_mutation': True}, ('/api/agents',))
    add('cluster-maintenance-filter', 'cluster', [select('Filter node status', 'maintenance')], {'yunjin_repair_visible': True, 'no_node_control_dispatch': True}, ('/api/cluster',))
    add('cluster-name-sort', 'cluster', [select('Filter node status', 'all'), select('Sort nodes', 'name')], {'original_roster_sorted_by_name': True, 'no_node_control_dispatch': True}, ('/api/cluster',))
    for tab in ['Benchmark runner', 'Results', 'Compare', 'Routing insights', 'Overview']:
        action = {'action': 'click', 'selector': '.lab-tabs button', 'index': 2} if tab == 'Results' else button(tab)
        add('model-lab-' + tab.lower().replace(' ', '-'), 'models', [action], {'selected_tab': tab, 'no_model_start_or_inference': True}, ('/api/model-lab',))
    add('settings-integration-nav', 'settings', [{'action': 'click', 'role': 'link', 'name': 'Integrations'}], {'integration_section_reachable': True, 'no_mutation': True}, ('/api/workspace',))
    add('settings-session-nav', 'settings', [{'action': 'click', 'role': 'link', 'name': 'Session'}], {'session_section_reachable': True, 'no_owner_shutdown': True}, ('/api/workspace',))
    add('workspace-search-button', 'home', [button('Search workspace'), field('#workspace-search', 'absent-native-ui-kappa')], {'palette_visible': True, 'empty_search_feedback': True, 'no_mutation': True}, ('/api/workspace',))
    for row in inputs:
        validate_input(row)
    return (inputs, oracles)

def publish(root):
    root = Path(root).resolve()
    if root.exists():
        raise ValueError('Preserve every prospective supplement version.')
    root.mkdir(parents=True)
    inputs, oracles = cases()
    hashes = {}
    for name, value in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(value, indent=2) + '\n'
        (root / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': len(inputs), 'hashes': hashes, 'attempted': False, 'execution_has_no_oracles': True, 'fixture': 'original-populated-backend', 'scope': 'Development local native controls, original isolated stores; no model, audio, power, external provider or owner effects.'}
    (root / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(publish(parser.parse_args().output)))
