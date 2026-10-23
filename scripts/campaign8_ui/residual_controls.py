"""One prospective audit of viable remaining native declaration gestures.

Uses the existing original-lab-controls fixture, with its finite timing leaf.
No new result/status override, model call, provider dispatch or owner mutation.
"""
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button, field, select

def cases():
    inputs, oracles = ([], [])

    def add(key, route, steps, check, paths=('/api/productivity',)):
        identifier = 'residual-final-' + key
        item = {'id': identifier, 'route': route, 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-lab-controls', 'window_size': [1280, 800], 'steps': steps, 'readback_paths': list(paths)}
        validate_input(item)
        inputs.append(item)
        oracles.append({'id': identifier, 'check': check, 'scope': 'Actual original native gesture and original isolated state only. Controlled evaluation delay is not speed evidence. No model/provider/tool/physical-audio dispatch.'})
    add('planner-refresh', 'planner', [button('Refresh', settle_ms=700)], {'original_calendar_refresh_GET_observed': True, 'provider_unavailable_remains_truthful': True, 'local_tasks_unchanged': True}, ('/api/calendar', '/api/productivity'))
    add('planner-open-calendar', 'planner', [button('Open calendar')], {'actual_route': 'calendar', 'no_provider_write': True}, ('/api/calendar', '/api/productivity'))
    add('inspector-review-settings', 'home', [button('Show inspector'), button('Review settings'), {'action': 'click', 'selector': '.inspector button[aria-label="Hide inspector"]'}], {'actual_route': 'settings', 'original_inspector_closed': True, 'settings_unchanged': True})
    add('palette-close-icon', 'home', [button('Search workspace'), button('Close dialog')], {'original_palette_opened_then_closed': True, 'no_write': True})
    add('palette-escape', 'home', [button('Search workspace'), {'action': 'press', 'selector': 'dialog', 'key': 'Escape'}], {'original_palette_onCancel_closes_dialog': True, 'no_write': True})
    add('palette-capability-draft', 'home', [button('Search workspace'), field('#workspace-search', 'file.stat'), {'action': 'click', 'selector': '.command-results button:has-text("file.stat")'}], {'actual_route': 'chat', 'prepared_draft': 'Tell me about the file.stat capability and what permission it needs.', 'no_prompt_submission_or_tool_execution': True}, ('/api/workspace',))
    add('workflow-output-close', 'workflows', [select('Workflow status', 'completed'), {'action': 'click', 'selector': '.workflow-row', 'index': 0}, button('View output'), button('Close output')], {'original_saved_output_dialog_open_then_closed': True, 'persisted_workflow_unchanged': True}, ('/api/workflows',))
    add('results-cancel-resume', 'models', [button('Benchmark runner'), select('Benchmark suite', 'llm-tools-development'), field('input[aria-label="Output tokens"]', '32'), field('input[aria-label="Tool rounds"]', '1'), select('Benchmark suite', 'routing-development'), field('input[aria-label="Cases"]', '10'), field('input[aria-label="Repetitions"]', '1'), button('Start benchmark', settle_ms=200), button('Cancel after case', settle_ms=1000), button('Inspect results', settle_ms=500), button('Resume checkpoint', settle_ms=3000)], {'cancelled_checkpoint_incomplete_before_resume': True, 'same_original_run_completed_after_Results_Resume': True, 'completed': 10, 'total': 10, 'unique_original_case_ordinals': list(range(10)), 'no_completed_case_reevaluation': True, 'actual_generation_requests': 0, 'tool_dispatches': 0}, ('/api/model-lab',))
    add('history-title-inspect', 'models', [{'action': 'click', 'selector': '.lab-history tbody .lab-row-link', 'index': 0}], {'actual_original_history_run_detail_visible': True, 'detail_ID_matches_clicked_row': True, 'persisted_run_unchanged': True}, ('/api/model-lab',))
    add('history-button-inspect', 'models', [{'action': 'click', 'selector': '.lab-history tbody tr button:has-text("Inspect")', 'index': 0}], {'actual_original_history_run_detail_visible': True, 'detail_ID_matches_clicked_row': True, 'persisted_run_unchanged': True}, ('/api/model-lab',))
    return (inputs, oracles)

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Preserve all prospective inputs and outcomes.')
    inputs, oracles = cases()
    output.mkdir(parents=True)
    hashes = {}
    for name, obj in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(obj, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': len(inputs), 'hashes': hashes, 'execution_attempted': False, 'fixture_id': 'original-lab-controls', 'generation_or_provider_or_tool_execution_authorized': False, 'existing_timing_adapter': '.15 seconds/call, at most204 original evaluations', 'download_scope': 'Browser download buttons remain outside this input corpus until an exact owned-download boundary is available.'}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
