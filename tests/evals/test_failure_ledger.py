from pathlib import Path
import pytest
from hanni.evals.failure_ledger import DEFAULT_REPORT, build_ledger

def test_all_saved_development_failures_have_a_review_and_evidence():
    if not Path(DEFAULT_REPORT).is_file():
        pytest.skip('historical local inference report is not included in this checkout')
    ledger = build_ledger()
    assert ledger['count'] == 25
    assert len({row['id'] for row in ledger['failures']}) == 25
    assert all((row['root_cause'] and row['recommended_architectural_layer'] for row in ledger['failures']))
    assert all((row['menu'] is not None and row['expected_evidence']['claims'] is not None for row in ledger['failures']))
