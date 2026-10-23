"""Read persisted public-positive timing after checks; never profile handlers."""
from datetime import datetime
import json
from pathlib import Path
import os

POSITIVES = {
    'test_read_typed_reference_artifact_real_bytes_and_gates',
    'test_copy_or_move_read_report_matches_external_bytes',
    'test_artifact_roundtrip_through_original_file_read',
    'test_numeric_analysis_and_saved_report_correct_from_real_json',
    'test_two_real_reads_form_verified_barrier_before_report',
    'test_task_add_original_readback_and_saved_exact_fields',
}
ROWS = []


def pytest_addoption(parser):
    parser.addoption('--v3-timing-output', default=None)


def pytest_sessionstart(session):
    from scripts.v3_review.service_fixture import ServiceFixture
    original = ServiceFixture.close
    def close(fixture):
        name = os.environ.get('PYTEST_CURRENT_TEST', '').split(' (')[0]
        selected = any('::' + identifier in name for identifier in POSITIVES)
        if selected:
            for summary in fixture.service.snapshot():
                detail = fixture.service.detail(summary['workflow_id'])
                start, end = detail['created_at'], detail.get('finished_at')
                elapsed = ((datetime.fromisoformat(end.replace('Z', '+00:00')) -
                            datetime.fromisoformat(start.replace('Z', '+00:00'))).total_seconds() * 1000
                           if end else None)
                ROWS.append({'test': name, 'status': detail['status'],
                             'created_at': start, 'finished_at': end,
                             'submission_to_terminal_ms': elapsed,
                             'steps': len(detail['steps']),
                             'verified_steps': detail['counts']['verified'],
                             'invocations': len(detail['invocations'])})
        return original(fixture)
    ServiceFixture.close = close
    session._v3_original_fixture_close = original


def pytest_sessionfinish(session, exitstatus):
    from scripts.v3_review.service_fixture import ServiceFixture
    ServiceFixture.close = session._v3_original_fixture_close
    output = session.config.getoption('--v3-timing-output')
    if output:
        Path(output).write_text(json.dumps({'exitstatus': exitstatus, 'rows': ROWS,
            'scope': 'Seven explicitly exposed positive core objectives only; genuine original Service persisted wall-clock created_at to verified terminal finished_at; includes scripted planning, automatic test-owner reviews and verification. Not actual inference or human approval latency; no original V2 paired equivalent.'}, indent=2), encoding='utf-8')
