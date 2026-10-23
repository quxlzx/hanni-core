import json
import pytest
from scripts.campaign8_ui.local_final import cases
from scripts.campaign8_ui.plan import validate_input
from scripts.campaign8_ui.upload import upload_fixture
from scripts.campaign8_ui.local_retakes import publish

def test_only_fixed_synthetic_disabled_configuration_enters_file_control():
    fixture = upload_fixture('mcp-disabled-config')
    assert fixture['name'] == 'campaign8-controlled-disabled-mcp.json'
    assert fixture['mimeType'] == 'application/json'
    assert len(fixture['buffer']) < 256 * 1024
    document = json.loads(fixture['buffer'])
    config = document['mcpServers']['Controlled native file integration']
    assert config['auto_connect'] is False and config['env'] == {}
    assert config['args'] == []
    for invalid in ['owner.json', '../owner.json', 'C:\\Users\\user', None]:
        with pytest.raises(ValueError):
            upload_fixture(invalid)

@pytest.mark.parametrize('extra', [{'path': 'C:\\Users\\user'}, {'buffer': 'private'}, {'value': 'private'}, {'name': 'owner.json'}, {'selector': 'input[type="file"]'}, {'fixture_id': 'owner.json'}])
def test_input_only_upload_does_not_grant_path_or_payload_authority(extra):
    step = {'action': 'upload_fixture', 'selector': 'dialog input[type="file"]', 'fixture_id': 'mcp-disabled-config', **extra}
    with pytest.raises(ValueError):
        validate_input({'operation': 'local_sequence', 'steps': [step]})

def test_final_local_cases_exclude_clipboard_provider_and_model_actions():
    inputs, oracles = cases()
    assert len(inputs) == 12 and {r['id'] for r in inputs} == {r['id'] for r in oracles}
    uploads = [s for r in inputs for s in r['steps'] if s['action'] == 'upload_fixture']
    assert len(uploads) == 1
    for row in inputs:
        validate_input(row)
        assert not any((s.get('name') in {'Copy JSON', 'Test & Discover', 'Reconnect', 'Confirm server startup', 'Start benchmark', 'Send'} for s in row['steps']))

def test_exposed_retakes_preserve_original_semantics_and_inputs(tmp_path):
    original = tmp_path / 'original'
    original.mkdir()
    inputs, oracles = cases()
    for name, rows in [('inputs.json', inputs), ('oracles.json', oracles)]:
        (original / name).write_text(json.dumps(rows), encoding='utf8')
    before = {p.name: p.read_bytes() for p in original.iterdir()}
    output = tmp_path / 'retakes'
    seal = publish(original, output)
    assert seal['cases'] == 8 and seal['original_oracle_objects_unchanged'] is True
    actual_oracles = json.loads((output / 'oracles.json').read_text())
    assert all((row in oracles for row in actual_oracles))
    assert {p.name: p.read_bytes() for p in original.iterdir()} == before
    rows = json.loads((output / 'inputs.json').read_text())
    for row in rows:
        validate_input(row)
    imported = next((r for r in rows if r['id'] == 'local-final-mcp-import-confirm'))
    assert [s['action'] for s in imported['steps'][:3]] == ['click', 'upload_fixture', 'click']
