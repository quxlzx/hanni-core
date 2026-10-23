"""Original discovered callback denials remain before every original handler."""
from pathlib import Path
from scripts.campaign2_verification.dynamic_gates import audit

def test_all_discovered_dynamic_callback_denials(tmp_path):
    result = audit(Path(__file__).resolve().parents[2], tmp_path / 'independent-dynamic-gates')
    assert result['callback_count'] > 0
    assert result['passed'] == result['callback_count']
    assert result['original_handler_entries'] == 0
