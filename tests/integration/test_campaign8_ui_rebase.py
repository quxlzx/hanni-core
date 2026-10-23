"""Source-locator accounting must not invent equivalence after source edits."""
from scripts.campaign8_ui.rebase import controls_with_anchors

def inventory(digest, rows):
    return {'source_hashes': {'a.tsx': digest}, 'modules': [{'file': 'a.tsx', 'controls': rows}]}

def declaration(line, label='Read evidence'):
    return {'id': f'a.tsx:{line}:1', 'line': line, 'component': 'Screen', 'tag': 'button', 'attributes': {'onClick': '{refresh}'}, 'static_child_text': label}

def test_unique_unchanged_declaration_keeps_current_locator_and_historical_anchor():
    current = inventory('new', [declaration(45)])
    old = inventory('old', [declaration(12)])
    rows, audit = controls_with_anchors(current, old)
    assert rows[0]['id'] == 'a.tsx:45:1' and rows[0]['line'] == 45
    assert rows[0]['_mapping_anchor_id'] == 'a.tsx:12:1'
    assert rows[0]['_mapping_anchor_line'] == 12
    assert audit['historical_assets_are_not_current_execution'] is True
    assert '_mapping_anchor_line' not in current['modules'][0]['controls'][0]

def test_changed_label_or_ambiguous_shift_gets_no_historical_line_credit():
    old = inventory('old', [declaration(12)])
    rows, audit = controls_with_anchors(inventory('new', [declaration(45, 'Changed meaning')]), old)
    assert rows[0]['_mapping_anchor_line'] is None and audit['matched'] == []
    rows, audit = controls_with_anchors(inventory('new', [declaration(45), declaration(52)]), old)
    assert all((r['_mapping_anchor_line'] is None for r in rows))
    assert len(audit['excluded']) == 2

def test_byte_identical_file_anchors_repeated_declarations_by_exact_existing_id():
    original = inventory('same', [declaration(12), declaration(30)])
    rows, audit = controls_with_anchors(original, original)
    assert [r['_mapping_anchor_line'] for r in rows] == [12, 30]
    assert all((item['file_bytes_unchanged'] for item in audit['matched']))
