import pytest
from scripts.campaign8_ui.coverage import reconcile

def fixture():
    source = {'modules': [{'controls': [{'id': 'screen.tsx:1:1', 'attributes': {}, 'static_child_text': 'Local action'}]}]}
    native = {'complete': True, 'owned_native_cleanup': True, 'actions': [{'id': 'route-fonts', 'input': {'action': 'font_identity'}, 'result': {'controls': []}}, {'id': 'home-wide-inventory', 'input': {'action': 'inventory'}, 'result': {'url': 'http://127.0.0.1:1/#home', 'controls': [{'index': 0, 'name': 'Local action', 'visible': True, 'enabled': True}, {'index': 1, 'name': 'Unavailable action', 'visible': True, 'enabled': False}]}}]}
    return (source, native)

def test_observation_never_promotes_controls_to_pass():
    data = reconcile(*fixture(), evidence_file='owned-native-results.json')
    assert data['counts'] == {'source': {'NOT_RUN': 1}, 'native': {'NOT_RUN': 1, 'BLOCKED': 1}}
    assert len(data['native_instances']) == 2
    assert data['static_slots'][0]['native_candidates'] == ['home-wide-inventory:0']

def test_passing_assessment_requires_actual_action_and_readback():
    with pytest.raises(ValueError, match='action and semantic'):
        reconcile(*fixture(), evidence_file='owned-native-results.json', assessments=[{'outcome': 'PASS', 'reason': 'Visible', 'evidence_file': 'screenshot.png', 'source_slot_ids': ['screen.tsx:1:1']}])

def test_unknown_assessment_target_is_never_silently_counted():
    with pytest.raises(ValueError, match='unknown'):
        reconcile(*fixture(), evidence_file='owned-native-results.json', assessments=[{'outcome': 'BLOCKED', 'reason': 'No controller', 'evidence_file': 'owned.json', 'source_slot_ids': ['not-a-slot']}])
