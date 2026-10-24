"""Evidence boundaries and actual isolated capability behavior, with no owner state."""
from dataclasses import replace
from pathlib import Path
import subprocess
import pytest
from hanni.config.loader import load_config
from hanni.tools.base import ConfirmationRequired, ToolRequest, ToolResult
from hanni.tools.registry import build_default_registry
from hanni.reliability.execution import close_service
from scripts.campaign2.capability_audit import audit_case, invoke, output_errors
from scripts.campaign2.inventory import capture
ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture
def registry(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path / 'state', env={})
    value = build_default_registry(config)
    yield (value, config)
    close_service(tmp_path / 'state')

def test_inventory_uses_actual_definitions_not_fixed_total(registry):
    value, config = registry
    baseline = capture(value, config)
    original = value.get('calc.evaluate')
    value.register(replace(original, name='audit.additional_computation'))
    fresh = capture(value, config)
    assert fresh['builtin_count'] == baseline['builtin_count'] + 1
    assert {row['id'] for row in fresh['builtins']} == {tool.name for tool in value.definitions()}
    assert fresh['inventory_sha256'] != baseline['inventory_sha256']

def test_denial_receipt_proves_original_handler_never_entered(registry, tmp_path):
    value, _ = registry
    definition = value.get('file.write')
    target = tmp_path / 'must-not-exist.txt'
    result, receipt = invoke(value, definition, {'path': str(target), 'text': 'audit'}, actor_profile='everyone_else')
    assert result is None and receipt['error']['type'] == 'ToolPermissionError'
    assert receipt['handler_identity_retained'] and (not receipt['original_handler_entered'])
    assert not target.exists()

@pytest.mark.parametrize('command', ['Restart-Computer', "& ('Restart'+'-Computer')", "& ('Stop'+'-Computer')", 'Get-Date', '[System.IO.File]::WriteAllText("unused", "unused")'])
def test_arbitrary_powershell_requires_confirmation_before_dispatch(registry, command):
    value, _ = registry
    dispatched = []

    def guard():
        dispatched.append(command)
        raise AssertionError('Unconfirmed code reached dispatch')
    with pytest.raises(ConfirmationRequired):
        value.execute(ToolRequest('powershell.run', {'command': command}, execution_guard=guard))
    assert dispatched == []

def test_confirmed_safe_powershell_uses_original_handler(registry, monkeypatch):
    from types import SimpleNamespace
    from hanni.tools import powershell
    dispatched = []
    def controlled_process(command, **kwargs):
        dispatched.append(command)
        return subprocess.CompletedProcess(command, 0, 'campaign-two-confirmed\n', '')
    monkeypatch.setattr(powershell, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(powershell, 'subprocess', SimpleNamespace(run=controlled_process))
    value, _ = registry
    definition = value.get('powershell.run')
    result, receipt = invoke(value, definition, {'command': "Write-Output 'campaign-two-confirmed'"})
    assert result.ok and result.data['stdout'].strip() == 'campaign-two-confirmed'
    assert receipt['original_handler_entered'] and receipt['handler_identity_retained']
    assert len(dispatched) == 1 and dispatched[0][-1] == "Write-Output 'campaign-two-confirmed'"

@pytest.mark.parametrize('apply', [True, False])
def test_original_formatter_failure_does_not_claim_completion(registry, tmp_path, monkeypatch, apply):
    from hanni.tools import devtools
    value, _ = registry
    specimen = tmp_path / 'malformed.py'
    specimen.write_text('def broken(:\n', encoding='utf8')

    def failed_runner(command, **kwargs):
        specimen.write_text('# partial write\ndef broken(:\n', encoding='utf8')
        return subprocess.CompletedProcess(command, 123, '', 'Cannot parse malformed.py')
    monkeypatch.setattr(devtools.subprocess, 'run', failed_runner)
    result, receipt = invoke(value, value.get('project.format'), {'root': str(tmp_path), 'apply': apply})
    assert not result.ok and result.data['exit_code'] == 123
    assert result.data['requested_apply'] is apply
    assert result.data['applied'] is None if apply else result.data['applied'] is False
    assert 'failed' in result.message.lower() and 'Reformatted' not in result.message
    assert receipt['original_handler_entered'] and specimen.read_text(encoding='utf8').startswith('# partial write')

def test_output_contract_rejects_missing_fields_bool_numbers_and_wrong_name(registry):
    value, _ = registry
    definition = value.get('calc.evaluate')
    assert output_errors(definition, ToolResult('calc.evaluate', True, 'bad', {'value': True, 'formatted': 'true'}))
    assert output_errors(definition, ToolResult('calc.evaluate', True, 'bad', {'value': 1}))
    assert output_errors(definition, ToolResult('invented', True, 'bad', {'value': 1, 'formatted': '1'}))
    assert not output_errors(definition, ToolResult('calc.evaluate', True, 'ok', {'value': 400.0, 'formatted': '400'}))

def test_schema_only_fixture_generator_supports_every_current_output_descriptor(registry):
    from hanni.evals.llm_coverage import fixture_for
    value, _ = registry
    for definition in value.definitions():
        payload = fixture_for(definition)
        assert payload['message'] == 'Synthetic schema probe; no capability was executed.'
        assert not output_errors(definition, ToolResult(payload['name'], payload['ok'], payload['message'], payload['data']))

@pytest.mark.parametrize('name', ['file.write', 'file.copy', 'file.delete', 'archive.unzip', 'note.append', 'todo.complete', 'calc.evaluate', 'unit.convert', 'google.calendar.create', 'google.calendar.delete', 'file.open', 'notify.toast'])
def test_original_implementation_receipt_and_independent_readback(name, tmp_path, registry):
    value, config = registry
    inventory = next((row for row in capture(value, config)['builtins'] if row['id'] == name))
    own = tmp_path / 'actual-case'
    own.mkdir()
    row = audit_case(name, own, inventory)
    assert row['dimensions']['valid_arguments']['status'] == 'pass'
    assert row['dimensions']['output_contract']['status'] == 'pass'
    assert row['dimensions']['end_to_end']['status'] == 'pass'
    receipt = row['dimensions']['end_to_end']['receipt']
    assert receipt['original_handler_entered'] and receipt['handler_identity_retained']
    assert receipt['readback_assertions'] and all((a['passed'] for a in receipt['readback_assertions']))
    if 'google' in name:
        assert row['dimensions']['end_to_end']['mode'] == 'original_mock_dependency'
