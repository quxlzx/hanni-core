import copy
import pytest
from scripts.campaign8_ui.inventory import inventory
from scripts.campaign8_ui.scorecard import build

def test_every_dynamic_source_slot_has_its_own_route_authority_and_concrete_gap():
    source = inventory()
    result = build(source, source_file='fresh-original-inventory.json')
    original = [control for module in source['modules'] for control in module['controls']]
    assert len(result['rows']) == len(original)
    assert {row['id'] for row in result['rows']} == {control['id'] for control in original}
    assert sum(result['outcome_counts'].values()) == len(original)
    assert not result['outcome_counts'].get('PASS', 0)
    assert all((row['source_locator']['line'] > 0 and row['reason'] and row['evidence_references'] and (row['routed_screens'] or row['route_status'] == 'UNRESOLVED_SOURCE_DECLARATION') and row['authority_status'] for row in result['rows']))
    assert result['eligible_functional_fraction'] is None

def test_source_pass_requires_separate_actual_action_and_result_proof():
    source = inventory()
    first = source['modules'][0]['controls'][0]['id']
    row = {'source_slot_ids': [first], 'outcome': 'PASS', 'reason': 'Visible', 'evidence_references': [{'file': 'owned.png'}]}
    with pytest.raises(ValueError, match='actual action and semantic'):
        build(source, source_file='original.json', assessments=[row])

def test_unseen_source_locator_is_not_credited_from_a_similar_name():
    source = inventory()
    with pytest.raises(ValueError, match='Unknown source'):
        build(source, source_file='original.json', assessments=[{'source_slot_ids': ['not-existing:1:1'], 'outcome': 'BLOCKED', 'reason': 'No corresponding declaration', 'evidence_references': [{'file': 'original.json'}]}])

def test_not_implemented_capture_is_separate_from_source_untested_control():
    source = inventory()
    result = build(source, source_file='original.json')
    unsupported = [row for row in result['rows'] if row['outcome'] == 'NOT_IMPLEMENTED']
    assert unsupported and all((row['component'] == 'ScreenAwarenessPage' for row in unsupported))
    assert all((row['semantic_readback'] is None for row in unsupported))
    refresh = next((row for row in result['rows'] if row['component'] == 'ScreenAwarenessPage' and row['declaration']['label'] == 'Refresh status'))
    assert refresh['outcome'] == 'NOT_RUN'
    audio = next((row for row in result['rows'] if row['component'] == 'AudioSettings' and row['attributes'].get('id') == '"audio-apply"'))
    assert audio['outcome'] == 'NOT_RUN'
