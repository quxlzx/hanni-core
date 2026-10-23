"""A native dispatch receipt is not sufficient to prove application behavior."""
from scripts.campaign8_ui.grading import grade

def receipt(*, executed=True, title='actual title'):
    return {'input': {'id': 'synthetic', 'route': 'tasks'}, 'executed': executed, 'dom': {'dialogs': []}, 'backend_readbacks': [{'path': '/api/productivity', 'status': 200, 'data': {'tasks': [{'title': title, 'status': 'open'}]}}]}

def test_dispatch_does_not_turn_unknown_measurement_into_pass():
    result = grade(receipt(), {'id': 'synthetic', 'check': {'note_expanded': True}})
    assert result['outcome'] == 'UNVERIFIED'
    assert result['assertions'][0]['passed'] is None

def test_original_persisted_result_is_checked_against_independent_expectation():
    result = grade(receipt(), {'id': 'synthetic', 'check': {'persisted_task': {'title': 'different expected title'}}})
    assert result['outcome'] == 'FAIL'

def test_final_persisted_effect_does_not_erase_failed_caller_attempt():
    result = grade(receipt(executed=False), {'id': 'synthetic', 'check': {'persisted_task': {'title': 'actual title'}}})
    assert result['outcome'] == 'EXECUTION_ERROR'
    assert result['assertions'][0]['passed'] is True

def test_real_dialog_and_original_persisted_fields_can_pass():
    result = grade(receipt(), {'id': 'synthetic', 'check': {'persisted_task': {'title': 'actual title', 'status': 'open'}, 'dialog_closed': True}})
    assert result['outcome'] == 'PASS'
