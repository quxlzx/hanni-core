"""Original ZIP parsing/writes; no owner paths or model/network requests."""
import pytest
from scripts.campaign9_tools.filesystem_supplement import scenarios, run_case, grade

@pytest.mark.parametrize('case', scenarios(), ids=lambda case: case['id'])
def test_original_filesystem_security_and_fault_contract(tmp_path, case):
    raw = run_case(case, tmp_path)
    assessment = grade(case, raw)
    assert assessment['passed'], assessment['errors']
