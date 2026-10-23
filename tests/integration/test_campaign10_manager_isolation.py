"""Scope guards exercised before actual original implementation entry."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts.campaign10_core.harness import environment, seed
from hanni.tools.base import ToolRequest
from scripts.campaign10_manager.isolation import validate_dispatch

@pytest.mark.parametrize('name,arguments', [('file.search', {'query': 'test', 'root': ''}), ('file.search', {'query': 'test'}), ('file.read', {'path': '{outside}'}), ('file.open', {'path': '{root}/sample.txt'}), ('folder.open', {'path': '{root}'}), ('ui.focus_window', {'title': 'synthetic'}), ('clipboard.read', {}), ('process.stop', {'pid': 123456}), ('archive.zip', {'paths': ['{root}/sample.txt', '{outside}'], 'destination': '{root}/a.zip'})])
def test_denied_before_dispatch(tmp_path, name, arguments):
    root = tmp_path / 'owned'
    outside = tmp_path / 'outside.txt'

    def substitute(value):
        if isinstance(value, str):
            return value.replace('{root}', str(root)).replace('{outside}', str(outside))
        if isinstance(value, list):
            return [substitute(v) for v in value]
        return value
    args = {k: substitute(value) for k, value in arguments.items()}
    with environment(root) as state:
        with pytest.raises((PermissionError, ValueError)):
            validate_dispatch(state, ToolRequest(name, args), root)
        assert not state.entries and (not state.effects)

def test_owned_read_reaches_original_handler(tmp_path):
    with environment(tmp_path) as state:
        target = tmp_path / 'fixture.txt'
        target.write_text('Owned content', encoding='utf8')
        request = ToolRequest('file.read', {'path': str(target)})
        validate_dispatch(state, request, tmp_path)
        actual = state.registry.execute(request)
        assert actual.ok and 'Owned content' in str(actual.data)

def test_local_tool_name_cannot_bypass_module_boundary(tmp_path):

    def provider(*args):
        raise AssertionError('External provider entered')
    provider.__module__ = 'synthetic.untrusted_provider'
    state = SimpleNamespace(config=SimpleNamespace(paths=SimpleNamespace(data_dir=tmp_path)), registry=SimpleNamespace(get=lambda name: SimpleNamespace(handler=provider)))
    with pytest.raises(PermissionError):
        validate_dispatch(state, ToolRequest('file.read', {'path': str(tmp_path / 'a')}), tmp_path)

def test_mismatched_store_root_denied(tmp_path):
    with environment(tmp_path / 'owned') as state:
        with pytest.raises(PermissionError):
            validate_dispatch(state, ToolRequest('hanni.permissions', {}), tmp_path)

def test_only_owned_inert_mcp_binding_can_execute(tmp_path):
    with environment(tmp_path) as state:
        seed(state, {'mcp': {'records': [{'bin': 'R4', 'part': 'washer', 'quantity': 7}], 'configured': True, 'connection_approved': True, 'tools_approved': True}})
        definitions = [d for d in state.registry.definitions() if d.handler.__module__ == 'hanni.mcp.adapter']
        assert len(definitions) == 1
        request = ToolRequest(definitions[0].name, {'bin': 'R4'})
        validate_dispatch(state, request, tmp_path)
        actual = state.registry.execute(request)
        assert actual.ok and actual.data['structured_content']['total'] == 7
        assert len(state.mcp_calls) == 1
        state.managers = []
        with pytest.raises(PermissionError):
            validate_dispatch(state, request, tmp_path)
