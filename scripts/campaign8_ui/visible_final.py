"""Finite safe enabled native declaration gaps; no inference or external effects."""
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button, field, select

def cases():
    inputs, oracles = ([], [])

    def add(key, route, steps, check, *, size=(1280, 800), paths=('/api/productivity',)):
        identifier = 'visible-final-' + key
        row = {'id': identifier, 'route': route, 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-populated-dense', 'window_size': list(size), 'steps': steps, 'readback_paths': list(paths)}
        validate_input(row)
        inputs.append(row)
        oracles.append({'id': identifier, 'check': check, 'scope': 'Original isolated native draft/navigation/details/local persistence only. No model, tool, provider, node power or physical audio activation.'})
    add('prepared-memory-draft', 'home', [button('Check memory usage')], {'route': 'chat', 'actual_prepared_draft': "What's using the most memory on my computer?", 'chat_submission': False})
    add('prepared-calendar-draft', 'home', [button("Today's calendar")], {'route': 'chat', 'actual_prepared_draft': "What's on my calendar today?", 'provider_query_or_chat_submission': False})
    add('compact-navigation', 'settings', [button('Open navigation'), button('Close navigation')], {'actual_sidebar_open_then_closed': True, 'route_unchanged': True}, size=(720, 650))
    add('notifications-sidebar', 'home', [button('Notifications')], {'actual_route': 'notifications'}, paths=('/api/notifications',))
    add('settings-sidebar', 'home', [button('Settings')], {'actual_route': 'settings'})
    add('voice-controls-navigation', 'home', [button('Show voice details'), button('Voice controls')], {'actual_route': 'voice', 'original_voice_controller_unavailable': True}, paths=('/api/voice',))
    add('audio-settings-navigation', 'home', [button('Show voice details'), button('Audio settings')], {'actual_route': 'settings', 'original_audio_section_in_view': True, 'audio_activation': False})
    add('project-task-draft', 'projects', [{'action': 'click', 'selector': '.project-list button', 'index': 0}, button('Add task'), button('Cancel')], {'actual_task_dialog_closed': True, 'tasks_unchanged': True})
    add('project-file-draft', 'projects', [{'action': 'click', 'selector': '.project-list button', 'index': 0}, {'action': 'click', 'selector': '.project-link button.text-link', 'index': 0}], {'actual_route': 'chat', 'draft_contains_actual_owned_artifact_path': True, 'file_tool_execution': False})
    add('planner-deadline-target', 'calendar', [{'action': 'click', 'selector': '.calendar-deadlines button.text-link', 'index': 0}], {'actual_route': 'tasks', 'selected_original_task_id': True, 'task_unchanged': True})
    add('planner-all-tasks', 'calendar', [button('Open all tasks')], {'actual_route': 'tasks', 'tasks_unchanged': True})
    project = [{'action': 'click', 'selector': '.memory-tabs button', 'index': 2}, {'action': 'click', 'selector': '.memory-project-index button', 'index': 0}]
    add('memory-project-sources', 'memory', project + [{'action': 'click', 'selector': '.memory-project-section details summary', 'index': 0}, {'action': 'click', 'selector': '.memory-context-source summary'}], {'actual_original_project_note_and_bounded_context_package_visible': True, 'stored_authoritative_memories_unchanged': True}, paths=('/api/memory/explorer?limit=30', '/api/productivity'))
    add('memory-alias-add-remove', 'memory', project + [button('Add alias'), field('dialog input', 'Controlled final local alias'), button('Save change', settle_ms=700), button('Remove'), button('Save change', settle_ms=700)], {'original_project_alias_added_then_removed': True, 'final_alias_absent': True, 'authoritative_memories_unchanged': True}, paths=('/api/memory/explorer?limit=30', '/api/productivity'))
    workflow = [select('Workflow status', 'completed'), {'action': 'click', 'selector': '.workflow-row', 'index': 0}]
    add('workflow-arguments-details', 'workflows', workflow + [button('Refresh workflow'), {'action': 'click', 'selector': '.workflow-control-reasons summary'}, {'action': 'click', 'selector': '.workflow-step > summary', 'index': 0}, {'action': 'click', 'selector': '.workflow-step details summary', 'index': 0}, {'action': 'click', 'selector': '.workflow-step details summary', 'index': 1}, {'action': 'click', 'selector': '.workflow-artifacts details summary', 'index': 0}], {'actual_original_saved_arguments_and_resolved_arguments_visible': True, 'artifact_receipt_metadata_visible': True, 'no_workflow_execution': True}, paths=('/api/workflows',))
    add('workflow-activity-navigation', 'workflows', workflow + [button('Open execution Activity')], {'actual_route': 'activity', 'no_workflow_execution': True}, paths=('/api/agents', '/api/workflows'))
    add('settings-inspector', 'settings', [{'action': 'click', 'selector': '.settings-section .facts button:not([id])', 'index': 0}, {'action': 'click', 'selector': '.settings-section .facts button:not([id])', 'index': 0}], {'actual_local_context_inspector_toggled_then_restored': True, 'owner_preferences_unchanged': True})
    add('settings-shutdown-cancel', 'settings', [{'action': 'click', 'selector': '#shutdown'}, button('Cancel')], {'actual_shutdown_dialog_closed': True, 'backend_still_alive': True, 'owner_model_unchanged': True})
    return (inputs, oracles)

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Preserve all prospective inputs and original outcomes.')
    inputs, oracles = cases()
    output.mkdir(parents=True)
    hashes = {}
    for name, obj in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(obj, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': len(inputs), 'hashes': hashes, 'execution_attempted': False, 'generation_or_provider_or_tool_execution_authorized': False}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
