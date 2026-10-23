"""Verification-only timer semantics; no actual inference or sealed inputs."""
from scripts.v3_review.check_public_model import persisted_timing

def test_planning_phase_end_excludes_grant_wait_and_setup():
    detail = {'created_at': '2030-01-01T00:00:00.000Z', 'status': 'completed', 'started_at': '2030-01-01T00:00:20.000Z', 'finished_at': '2030-01-01T00:00:25.123Z', 'checkpoints': [{'kind': 'planning_started', 'created_at': '2030-01-01T00:00:01.000Z'}, {'kind': 'plan_saved', 'created_at': '2030-01-01T00:00:05.000Z'}, {'kind': 'planning_finished', 'created_at': '2030-01-01T00:00:05.123Z'}, {'kind': 'started', 'created_at': '2030-01-01T00:00:20.000Z'}]}
    result = persisted_timing(detail)
    assert result['planning_endpoint_kind'] == 'planning_finished'
    assert result['submitted_to_planning_endpoint_ms'] == 5123
    assert result['active_planning_to_endpoint_ms'] == 4123
    assert result['completed_submission_to_finished_ms'] == 25123
    assert result['completed_started_to_finished_ms'] == 5123

def test_failed_objective_never_becomes_completed_duration():
    detail = {'status': 'blocked', 'created_at': '2030-01-01T00:00:00Z', 'finished_at': '2030-01-01T00:00:03Z', 'started_at': '2030-01-01T00:00:01Z', 'checkpoints': [{'kind': 'planning_started', 'created_at': '2030-01-01T00:00:01Z'}, {'kind': 'planning_blocked', 'created_at': '2030-01-01T00:00:02Z'}]}
    result = persisted_timing(detail)
    assert result['active_planning_to_endpoint_ms'] == 1000
    assert result['completed_submission_to_finished_ms'] is None
    assert result['completed_started_to_finished_ms'] is None
    assert result['completion_duration_status'] == 'NOT MEASURED'

def test_missing_naive_and_rollback_timestamps_are_not_guessed():
    for created in (None, 'invalid', '2030-01-01T00:00:00', '2030-01-01T00:00:10Z'):
        detail = {'status': 'completed', 'created_at': created, 'finished_at': '2030-01-01T00:00:03Z', 'checkpoints': []}
        result = persisted_timing(detail)
        assert result['completed_submission_to_finished_ms'] is None
        assert result['submitted_to_planning_endpoint_ms'] is None
        assert result['completion_duration_status'] == 'NOT MEASURED'
