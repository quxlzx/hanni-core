import pytest
from scripts.campaign8_ui.plan import validate_input
from scripts.campaign8_ui.supplement import cases

def test_populated_sequences_keep_oracles_separate_and_unsafe_actions_absent():
    inputs, expected = cases()
    assert {r['id'] for r in inputs} == {r['id'] for r in expected}
    assert len({r['id'] for r in inputs}) == len(inputs)
    assert all((r['operation'] == 'local_sequence' for r in inputs))
    assert all((not {'check', 'common', 'expected'} & r.keys() for r in inputs))
    assert all((step['action'] in {'click', 'fill', 'select', 'check', 'press'} for case in inputs for step in case['steps']))
    for row in inputs:
        validate_input(row)

@pytest.mark.parametrize('steps', [[], [{'action': 'post', 'url': '/api/cluster/power'}], [{'action': 'click', 'javascript': 'arbitrary'}]])
def test_sequence_contract_rejects_generic_authority_or_unbounded_empty_actions(steps):
    with pytest.raises(ValueError):
        validate_input({'operation': 'local_sequence', 'steps': steps})

def test_sequence_readback_never_opens_generic_owner_or_unknown_endpoint():
    with pytest.raises(ValueError):
        validate_input({'operation': 'local_sequence', 'steps': [{'action': 'click', 'role': 'button', 'name': 'Local'}], 'readback_paths': ['http://owner.invalid/api/chat']})
