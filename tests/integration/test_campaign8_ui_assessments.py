import hashlib
import json
import pytest
from scripts.campaign8_ui.assessments import build, candidates, reviewed_groups
from scripts.campaign8_ui.lifecycle import cases
from scripts.campaign8_ui.project_controls import cases as project_cases

def source(duplicate=False):
    row = {'id': 'example.tsx:4:2', 'line': 4, 'column': 2, 'tag': 'button', 'component': 'App', 'attributes': {'aria-label': '"Refresh"'}, 'static_child_text': ''}
    return {'routes': [{'route': 'home'}], 'modules': [{'file': 'example.tsx', 'controls': [row] + ([dict(row, id='example.tsx:8:2', line=8)] if duplicate else [])}]}

def receipt(path, executed=True):
    path.write_text(json.dumps({'development_cases': [{'executed': executed, 'input': {'id': 'local-case', 'route': 'home', 'steps': [{'action': 'click', 'role': 'button', 'name': 'Refresh'}]}}]}), encoding='utf8')

def test_unexecuted_or_failed_review_never_becomes_source_pass(tmp_path):
    raw = tmp_path / 'raw.json'
    receipt(raw, executed=False)
    assert build(source(), [(str(raw), 'review.json', [{'id': 'local-case', 'status': 'PASS'}])])[0] == []
    receipt(raw, executed=True)
    assert build(source(), [(str(raw), 'review.json', [{'id': 'local-case', 'status': 'FAIL'}])])[0] == []

def test_ambiguous_same_named_original_declarations_remain_unmatched(tmp_path):
    raw = tmp_path / 'raw.json'
    receipt(raw)
    assessments, unmatched = build(source(duplicate=True), [(str(raw), 'review.json', [{'id': 'local-case', 'status': 'PASS', 'observed_scope': 'Only one actual native occurrence.'}])])
    assert assessments == []
    assert len(unmatched[0]['candidate_ids']) == 2

def test_unique_credit_retains_individual_action_and_readback_not_visibility(tmp_path):
    raw = tmp_path / 'raw.json'
    receipt(raw)
    rows, unknown = build(source(), [(str(raw), 'review.json', [{'id': 'local-case', 'status': 'PASS', 'observed_scope': 'Original service refresh observed.'}])])
    assert unknown == [] and len(rows) == 1
    assert rows[0]['action_evidence'][0]['step'] == 0
    assert rows[0]['readback_evidence'][0]['case_id'] == 'local-case'
    assert 'not all' in rows[0]['coverage_scope']

def test_changed_original_receipt_invalidates_public_review_binding(tmp_path):
    raw = tmp_path / 'raw.json'
    receipt(raw)
    review = tmp_path / 'review.json'
    review.write_text(json.dumps({'raw': {'path': str(raw), 'sha256': hashlib.sha256(raw.read_bytes()).hexdigest()}, 'case_grades': []}), encoding='utf8')
    assert reviewed_groups([review])
    raw.write_text('{}', encoding='utf8')
    with pytest.raises(ValueError, match='changed'):
        reviewed_groups([review])

def test_native_lifecycle_has_only_the_model_free_suite_and_no_exports_or_sends():
    inputs, oracles = cases()
    assert {r['id'] for r in inputs} == {r['id'] for r in oracles}
    start = [r for r in inputs if any((s.get('name') == 'Start benchmark' for s in r['steps']))]
    assert len(start) == 2
    assert any((s.get('value') == 'routing-development' for s in start[0]['steps']))
    assert not any((s.get('name') in {'Send', 'Export JSON', 'Test & Discover', 'Reconnect'} for r in inputs for s in r['steps']))
    mini = [r for r in inputs if r['surface'] == 'mini']
    assert len(mini) == 6 and all((r['operation'] == 'local_sequence' for r in mini))

def test_new_project_case_uses_implemented_kinds_preserves_url_oracle_scope():
    inputs, oracles = project_cases()
    assert len(inputs) == 3 and all((r['steps'][0]['selector'] == '.project-list button' for r in inputs))
    assert {s['value'] for r in inputs for s in r['steps'] if s.get('selector') == '#workspace-link-kind'} == {'file', 'conversation'}
    assert all(('no URL' in r['scope'] for r in oracles))

def test_new_json_view_controls_match_their_distinct_original_run_handlers():
    controls = [dict(source()['modules'][0]['controls'][0], component='ModelLabPage', id=f'model_lab.tsx:{line}:1', line=line, attributes={'onClick': handler}, static_child_text='View JSON') for line, handler in [(100, '{() => viewRunJson(detail.run)}'), (200, '{() => viewRunJson(r)}')]]
    assert [r['line'] for r in candidates(controls, {'action': 'click', 'role': 'button', 'name': 'View JSON'}, 'models', ['models'])] == [100]
    assert [r['line'] for r in candidates(controls, {'action': 'click', 'selector': '.lab-actions button:has-text("View JSON ")'}, 'models', ['models'])] == [200]

def test_preview_escape_requires_actual_preceding_view_not_arbitrary_dialog():
    row = dict(source()['modules'][0]['controls'][0], component='FeatureDialog', tag='dialog')
    press = {'action': 'press', 'selector': 'dialog', 'key': 'Escape'}
    assert candidates([row], press, 'models', ['models']) == []
    assert candidates([row], press, 'models', ['models'], preceding=[{'action': 'click', 'name': 'View JSON'}]) == [row]
