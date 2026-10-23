"""Prospective actual native task field afterproof; separate from prior failures."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .plan import validate_input
from .supplement import button, field, select

def cases():
    inputs, oracles = ([], [])

    def add(key, steps, expected):
        identifier = 'task-fidelity-' + key
        inputs.append({'id': identifier, 'route': 'tasks', 'surface': 'desktop', 'operation': 'local_sequence', 'fixture_id': 'original-task-fidelity-backend', 'window_size': [1280, 800], 'steps': steps, 'readback_paths': ['/api/productivity']})
        oracles.append({'id': identifier, 'check': expected, 'scope': 'Original explicit isolated TaskRecord date/timestamp and status checked after actual frontend actions; no model or owner mutation.'})

    def find(title):
        return [select('Task status', 'all'), field('input[aria-label="Search tasks"]', title)]
    add('all-day-title-status', find('Controlled all-day fidelity') + [{'action': 'click', 'selector': '.task-title'}, field('#workspace-title', 'Controlled all-day revised'), {'action': 'select', 'selector': '#workspace-status', 'value': 'completed'}, button('Save', settle_ms=700)], {'persisted_task': {'title': 'Controlled all-day revised', 'status': 'completed', 'due': '2026-11-03T00:00:00', 'all_day': True}})
    add('all-day-reopen-complete', find('Controlled all-day revised') + [button('Reopen Controlled all-day revised', settle_ms=600), button('Complete Controlled all-day revised', settle_ms=600)], {'persisted_task': {'title': 'Controlled all-day revised', 'status': 'completed', 'due': '2026-11-03T00:00:00', 'all_day': True}, 'both_status_transitions_observed': True})
    add('timed-edit-complete-reopen', find('Controlled timed fidelity') + [{'action': 'click', 'selector': '.task-title'}, field('#workspace-course', 'Timed course revised'), button('Save', settle_ms=600), button('Complete Controlled timed fidelity', settle_ms=600), button('Reopen Controlled timed fidelity', settle_ms=600)], {'persisted_task': {'title': 'Controlled timed fidelity', 'course': 'Timed course revised', 'status': 'open', 'due': '2026-11-03T14:25:00-05:00', 'all_day': False}})
    add('date-changed', find('Controlled editable-date fidelity') + [{'action': 'click', 'selector': '.task-title'}, field('#workspace-due', '2026-11-07'), button('Save', settle_ms=700)], {'persisted_task': {'title': 'Controlled editable-date fidelity', 'due': '2026-11-07T00:00:00', 'all_day': True}})
    add('date-cleared', find('Controlled editable-date fidelity') + [{'action': 'click', 'selector': '.task-title'}, field('#workspace-due', ''), button('Save', settle_ms=700)], {'persisted_task': {'title': 'Controlled editable-date fidelity', 'due': '', 'all_day': False}})
    for row in inputs:
        validate_input(row)
    return (inputs, oracles)

def publish(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Preserve original field failures and all prospective versions.')
    output.mkdir(parents=True)
    inputs, oracles = cases()
    hashes = {}
    for name, value in [('inputs.json', inputs), ('oracles.json', oracles)]:
        wire = json.dumps(value, indent=2) + '\n'
        (output / name).write_text(wire, encoding='utf8', newline='\n')
        hashes[name] = hashlib.sha256(wire.encode()).hexdigest()
    seal = {'cases': len(inputs), 'hashes': hashes, 'execution_attempted': False, 'generations': 0, 'fixture': 'Original-task-fidelity plus finite existing populated original records.'}
    (output / 'SEAL.json').write_text(json.dumps(seal, indent=2) + '\n', encoding='utf8', newline='\n')
    return seal
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output)))
