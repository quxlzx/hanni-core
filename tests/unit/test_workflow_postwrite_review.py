from copy import deepcopy
from scripts.v3_review.check_public_postwrite import evaluate

def row():
    path = 'C:\\owned\\artifacts\\report.txt'
    return {'independent_artifacts': [{'path': path}], 'final_detail': {'steps': [{'step_id': 'save', 'kind': 'artifact', 'resolved_arguments': {'path': path}, 'finished_at': '2026-10-09T10:00:00+00:00'}, {'step_id': 'check', 'kind': 'tool', 'capability_id': 'file.read', 'dependencies': ['save'], 'resolved_arguments': {'path': path}, 'started_at': '2026-10-09T10:00:01+00:00', 'status': 'verified', 'result': {'name': 'file.read', 'ok': True, 'verification': {'status': 'VERIFIED'}, 'data': {'path': path, 'text': 'source\r\n', 'truncated': False}}}]}}

def test_explicit_postwrite_read_of_actual_artifact_matches_original_text():
    assert evaluate(row(), 'source\n')['passed']

def test_reading_original_source_again_does_not_prove_saved_artifact_read():
    value = row()
    read = value['final_detail']['steps'][1]
    read['resolved_arguments']['path'] = 'C:\\owned\\inputs\\source.txt'
    read['result']['data']['path'] = 'C:\\owned\\inputs\\source.txt'
    assert not evaluate(value, 'source\n')['passed']

def test_write_receipt_or_reviewers_readback_is_not_explicit_workflow_read():
    value = row()
    value['final_detail']['steps'].pop()
    assert not evaluate(value, 'source\n')['passed']

def test_truncated_wrong_text_or_earlier_read_fails():
    for change in ('text', 'truncated', 'time'):
        value = deepcopy(row())
        read = value['final_detail']['steps'][1]
        if change == 'time':
            read['started_at'] = '2026-10-09T09:00:00+00:00'
        else:
            read['result']['data'][change] = 'wrong' if change == 'text' else True
        assert not evaluate(value, 'source\n')['passed']
