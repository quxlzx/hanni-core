"""Fixed synthetic upload validation; no file access, picker or native startup."""
import json
import pytest
from scripts.campaign8_native.session import validated_upload
BASE = {'id': 'controlled-upload', 'action': 'upload_fixture', 'fixture_id': 'mcp-disabled-config', 'selector': 'dialog input[type="file"]', 'view': 'main'}

def test_only_frozen_inert_json_bytes_are_returned():
    value = validated_upload(BASE)
    assert value['name'] == 'campaign8-controlled-disabled-mcp.json'
    assert value['mimeType'] == 'application/json'
    assert type(value['buffer']) is bytes
    assert len(value['buffer']) < 256 * 1024
    config = json.loads(value['buffer'])['mcpServers']['Controlled native file integration']
    assert config['auto_connect'] is False
    assert config['command'] == 'campaign8-no-launch.exe'
    assert config['args'] == [] and config['env'] == {}

@pytest.mark.parametrize('change', [{'fixture_id': 'owner-config'}, {'selector': 'input[type="file"]'}, {'view': 'mini'}, {'path': 'C:/private/config.json'}, {'buffer': b'arbitrary supplied bytes'}])
def test_unknown_or_supplied_upload_authority_is_rejected_before_dispatch(change):
    with pytest.raises(ValueError):
        validated_upload({**BASE, **change})
