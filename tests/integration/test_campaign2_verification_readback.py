"""Independent source-bound no-op, empty-source and absent-sensor repair checks."""
from pathlib import Path
from scripts.campaign2_verification.platform_readback import run

def test_current_original_handlers_do_not_claim_unobserved_state(tmp_path):
    results = run(Path(__file__).resolve().parents[2], tmp_path / 'current-readback')
    assert results['passed'] == results['cases']
    assert all((row['original_handler_identity_retained'] for row in results['rows']))
