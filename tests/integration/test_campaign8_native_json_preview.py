"""Full source preview preserves original numeric bytes and authority scope."""
from unittest.mock import patch
import pytest
from scripts.campaign8_native.json_preview import measure_json_preview, source_text

def original_page():
    return {'format': 'hanni-model-lab-v1', 'run_json': '{"id":"002adc74-ff5c-422b-bf4b-0164e8a10b03","ratio":0.12345678901234567}', 'results_json': ['{"ordinal":0,"precise":0.1234567890123456789}'], 'export_complete': True, 'next_offset': None}

def test_complete_original_strings_keep_exact_numeric_bytes_and_selection():
    page = original_page()
    text = source_text(page)
    dom = {'controls': [{'tag': 'textarea', 'name': 'Complete benchmark JSON', 'visible': True, 'value': text, 'valueRedacted': False, 'readOnly': True, 'selectionStart': 0, 'selectionEnd': len(text)}]}
    with patch('scripts.campaign8_native.development.authenticated_readback', return_value={'status': 200, 'data': page}) as read:
        actual = measure_json_preview(object(), dom)
    assert actual['entire_text_matches_source']
    assert actual['readOnly']
    assert actual['selectionEnd'] == actual['utf16_length']
    assert '0.1234567890123456789' in text
    assert read.call_args.args[1] == '/api/model-lab/export/002adc74-ff5c-422b-bf4b-0164e8a10b03?representation=serialized'

def test_missing_preview_never_accesses_original_api():
    with patch('scripts.campaign8_native.development.authenticated_readback') as read:
        assert measure_json_preview(object(), {'controls': []}) == {'present': False}
    read.assert_not_called()

def test_invalid_run_identity_never_accesses_original_api():
    dom = {'controls': [{'tag': 'textarea', 'name': 'Complete benchmark JSON', 'visible': True, 'value': '{"run":{"id":"../owner"}}', 'valueRedacted': False}]}
    with patch('scripts.campaign8_native.development.authenticated_readback') as read:
        with pytest.raises(ValueError):
            measure_json_preview(object(), dom)
    read.assert_not_called()

@pytest.mark.parametrize('change', [{'export_complete': False}, {'next_offset': 1}, {'format': 'other'}, {'results_json': [None]}])
def test_partial_or_invalid_source_is_not_certified(change):
    with pytest.raises(ValueError):
        source_text({**original_page(), **change})
