"""Original discovered callback denials remain before every original handler."""
import sys
from pathlib import Path
import pytest
from scripts.campaign2_verification.dynamic_gates import audit

@pytest.mark.skipif(sys.platform != 'win32', reason='The protected-system-path confirmation under audit is defined by Windows system environment roots (WINDIR/ProgramFiles).')
def test_all_discovered_dynamic_callback_denials(tmp_path):
    result = audit(Path(__file__).resolve().parents[2], tmp_path / 'independent-dynamic-gates')
    assert result['callback_count'] > 0
    assert result['passed'] == result['callback_count']
    assert result['original_handler_entries'] == 0
