from pathlib import Path
from scripts.campaign2_verification.powershell_gate import run

def test_arbitrary_shell_always_requires_confirmation_but_trusted_confirmed_gate_still_admits(tmp_path):
    report = run(Path(__file__).resolve().parents[2], tmp_path / 'shell-gate')
    assert report['permission_level'] == report['risk_level'] == 3
    assert report['passed'] == report['cases']
    assert all((not row['original_handler_entered'] for row in report['rows']))
