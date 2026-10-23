from pathlib import Path
from scripts.campaign2_verification.provider_types import run

def test_original_security_provider_values_do_not_invent_boolean_certainty(tmp_path):
    report = run(Path(__file__).resolve().parents[2], tmp_path / 'provider-types')
    assert report['passed'] == report['cases']
    assert all((row['original_handler_identity_retained'] for row in report['rows']))
