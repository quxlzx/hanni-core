"""Separate prospective model-free Lab lifecycle and real frontend shell controls."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button, field, select

def cases():
    inputs, oracles = ([], [])

    def add(key, route, steps, check, *, surface='desktop', size=(1280, 800), paths=('/api/model-lab',)):
        inputs.append({'id': 'lifecycle-' + key, 'route': route, 'surface': surface, 'operation': 'local_sequence', 'fixture_id': 'original-populated-backend', 'window_size': list(size), 'steps': steps, 'readback_paths': list(paths)})
        oracles.append({'id': 'lifecycle-' + key, 'check': check, 'scope': 'Actual original native actions and original isolated stores. Capability retrieval is deterministic, not inference, tool execution, or model quality.'})
    add('retrieval-start-first', 'models', [button('Benchmark runner'), select('Benchmark suite', 'llm-tools-development'), field('input[aria-label="Output tokens"]', '32'), field('input[aria-label="Tool rounds"]', '1'), select('Benchmark suite', 'routing-development'), field('input[aria-label="Cases"]', '2'), field('input[aria-label="Repetitions"]', '1'), button('Start benchmark', settle_ms=3500)], {'new_completed_run': {'suite_id': 'routing-development', 'endpoint_id': None, 'settings': {'max_cases': 2, 'repetitions': 1, 'max_tokens': 32, 'max_rounds': 1}}, 'generation_requests': 0, 'actual_tool_execution': False, 'committed_cases': 2})
    add('retrieval-inspect-first', 'models', [button('Inspect results', settle_ms=500), {'action': 'click', 'selector': '.lab-case-list button', 'index': 0}, {'action': 'click', 'selector': '.lab-case-detail details summary', 'index': 0}], {'original_case_evidence_visible': True, 'real_inference_false': True, 'actual_tool_execution_false': True})
    add('retrieval-transcript', 'models', [{'action': 'click', 'selector': '.lab-case-detail details summary', 'index': 1}], {'original_transcript_expanded': True, 'generation_requests': 0})
    add('retrieval-protocol', 'models', [{'action': 'click', 'selector': '.lab-run-protocol summary'}], {'original_settings_and_fingerprints_visible': True})
    add('retrieval-outcome-filter', 'models', [select('Filter case outcome', 'passed'), select('Filter case outcome', 'failed'), select('Filter case outcome', '')], {'case_filter_reset': True, 'persisted_evidence_unchanged': True})
    add('retrieval-start-second', 'models', [button('Benchmark runner'), button('Start benchmark', settle_ms=3500)], {'second_new_completed_run': True, 'same_protocol_settings': True, 'generation_requests': 0})
    add('retrieval-history-search', 'models', [{'action': 'click', 'selector': '.lab-tabs button', 'index': 2}, field('input[aria-label="Search benchmark history"]', 'Capability retrieval'), select('Filter run status', 'completed'), select('Filter benchmark suite', 'routing-development')], {'two_actual_matching_runs': True, 'no_model_quality_claim': True})
    add('retrieval-compare', 'models', [button('Compare'), {'action': 'click', 'selector': '.lab-history input[type="checkbox"]', 'index': 0}, {'action': 'click', 'selector': '.lab-history input[type="checkbox"]', 'index': 1}, button('Compare selected runs', settle_ms=800)], {'comparable_original_runs': True, 'two_persisted_run_columns': True, 'no_inference_metrics_fabricated': True})
    mini = dict(surface='mini', size=(660, 460), paths=())
    add('mini-pin', 'home', [{'action': 'click', 'selector': '.mini-header button[title="Keep Mini above other windows"]', 'settle_ms': 2200}], {'native_mini_pinned': True, 'frontend_aria_pressed': True}, **mini)
    add('mini-unpin', 'home', [{'action': 'click', 'selector': '.mini-header button[title="Keep Mini above other windows"]', 'settle_ms': 2200}], {'native_mini_pinned': False, 'frontend_aria_pressed': False}, **mini)
    add('mini-shortcut', 'home', [button('Shortcut'), select('Global shortcut', 'Ctrl+Shift+H'), button('Shortcut')], {'preferences_open_then_closed': True, 'original_hotkey_choice': 'Ctrl+Shift+H', 'no_owner_preferences_write': True}, **mini)
    add('mini-capability-draft', 'home', [field('textarea[aria-label="Message HANNI"]', '/file'), {'action': 'click', 'selector': '.mini-capabilities button', 'index': 0}, field('textarea[aria-label="Message HANNI"]', '')], {'original_capability_prepared_draft': True, 'no_chat_submission': True, 'no_tool_dispatch': True}, **mini)
    add('mini-expand', 'home', [button('Expand')], {'native_main_visible': True, 'native_mini_hidden': True}, **mini)
    add('mini-dismiss', 'home', [button('Dismiss Mini')], {'native_mini_hidden': True, 'owner_windows_unchanged': True}, **mini)
    no_write = ('/api/productivity', '/api/voice', '/api/awareness')
    add('shell-skiplink', 'home', [{'action': 'press', 'selector': '.skip-link', 'key': 'Tab'}, {'action': 'press', 'selector': '.skip-link', 'key': 'Enter'}], {'main_content_focused': True}, paths=no_write)
    add('shell-home', 'settings', [button('HANNI home')], {'actual_route': 'home'}, paths=no_write)
    add('shell-navigation-groups', 'home', [{'action': 'click', 'selector': '.area-button', 'index': index} for index in (1, 2, 0)], {'original_group_panels_changed_then_assistant': True}, paths=no_write)
    add('shell-status-details', 'home', [{'action': 'click', 'selector': '.connection'}, {'action': 'click', 'selector': '.connection'}], {'workspace_status_shown_then_closed': True}, paths=no_write)
    add('shell-voice-details', 'home', [button('Show voice details'), button('Pause voice visual'), button('Resume voice visual'), button('Close voice details')], {'details_and_local_visual_changed_then_restored': True, 'voice_controller_not_activated': True}, paths=no_write)
    add('shell-stop-cancel', 'home', [button('Stop HANNI'), button('Cancel')], {'original_shutdown_dialog_closed': True, 'backend_remains_alive': True, 'no_model_stop': True}, paths=no_write)
    add('shell-palette-route', 'home', [button('Search workspace'), field('#workspace-search', 'Notifications'), {'action': 'click', 'selector': '.command-results button', 'index': 0}], {'actual_route': 'notifications'}, paths=('/api/notifications',))
    for case in inputs:
        validate_input(case)
    return (inputs, oracles)

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Preserve all sealed versions and first-run outcomes.')
    output.mkdir(parents=True)
    inputs, oracles = cases()
    hashes = {}
    for name, value in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(value, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': len(inputs), 'hashes': hashes, 'execution_attempted': False, 'generation_requests_authorized': 0, 'actual_tool_execution_authorized': False, 'download_ui_excluded': 'Export JSON creates a download. No owner Downloads write or clipboard use; serialized export API may be read independently.', 'pause_cancel_scope': 'Two deterministic cases may finish before pause/cancel becomes eligible. No transition pass is inferred.'}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
