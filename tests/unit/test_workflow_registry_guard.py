"""A changed definition cannot pass between original host and registry gates."""
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import pytest
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.tools import build_default_registry
from hanni.tools.base import ToolResult
from hanni.workflows.policy import WorkflowAuthority, definition_fingerprint
from hanni.workflows.types import fingerprint

def test_definition_replacement_between_host_and_dispatch_never_enters_handler(tmp_path):
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    registry = build_default_registry(config, data_dir=tmp_path)
    target = tmp_path / 'input.txt'
    target.write_text('Original isolated input', encoding='utf-8')
    host = McpHost(registry)
    definition = registry.get('file.read')
    tool = host._as_tool(definition)
    arguments = dict(host.prepare_call(tool, {'path': str(target)}).arguments)
    authority = WorkflowAuthority('owner', False, 'assisted', tmp_path / 'artifacts', ('file.read',), definition_fingerprint(definition), fingerprint(arguments))
    entered = []

    def changed_handler(args, context, request):
        entered.append(True)
        return ToolResult('file.read', True, 'Unexpected replacement', {'text': 'wrong'})
    api = registry.capabilities
    original_call = api.call

    def replace_at_dispatch(request, *, background=False):
        assert registry.unregister('file.read', expected=definition)
        registry.register(replace(definition, handler=changed_handler))
        return original_call(request, background=background)
    try:
        with patch.object(api, 'call', side_effect=replace_at_dispatch):
            result = host.call(tool, arguments, workflow_authority=authority)
        assert result['ok'] is False
        assert entered == []
        assert 'changed' in result['message'].lower()
    finally:
        registry.context.reliability.close()

def test_original_interactive_call_uses_existing_definition_without_workflow_metadata(tmp_path):
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    registry = build_default_registry(config, data_dir=tmp_path)
    target = tmp_path / 'input.txt'
    target.write_text('Original call remains available', encoding='utf-8')
    host = McpHost(registry)
    try:
        result = host.call(host._as_tool(registry.get('file.read')), {'path': str(target)})
        assert result['ok'] is True
        assert 'Original call remains available' in result['data']['text']
    finally:
        registry.context.reliability.close()

@pytest.mark.parametrize('keyword_capture', [False, True])
def test_changed_default_capture_before_host_validation_never_enters_handler(tmp_path, keyword_capture):
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    registry = build_default_registry(config, data_dir=tmp_path)
    original = registry.get('file.read')
    entered = []

    def factory(label):
        if keyword_capture:

            def handler(args, context, request, *, captured=label, events=entered):
                events.append(captured)
                return ToolResult('file.read', True, 'Captured target', {'text': captured})
        else:

            def handler(args, context, request, captured=label, events=entered):
                events.append(captured)
                return ToolResult('file.read', True, 'Captured target', {'text': captured})
        assert handler.__closure__ is None
        return handler
    registry.unregister('file.read', expected=original)
    registry.register(replace(original, handler=factory('approved-target')))
    approved = registry.get('file.read')
    host = McpHost(registry)
    tool = host._as_tool(approved)
    arguments = dict(host.prepare_call(tool, {'path': str(tmp_path / 'input.txt')}).arguments)
    authority = WorkflowAuthority('owner', False, 'assisted', tmp_path / 'artifacts', ('file.read',), definition_fingerprint(approved), fingerprint(arguments))
    registry.unregister('file.read', expected=approved)
    registry.register(replace(approved, handler=factory('unapproved-target')))
    try:
        result = host.call(tool, arguments, workflow_authority=authority)
        assert result['ok'] is False
        assert entered == []
    finally:
        registry.context.reliability.close()

def test_same_factory_replacement_with_changed_closure_never_enters_handler(tmp_path):
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    registry = build_default_registry(config, data_dir=tmp_path)
    target = tmp_path / 'input.txt'
    target.write_text('Original isolated input', encoding='utf-8')
    original = registry.get('file.read')
    entered = []

    def factory(label):

        def handler(args, context, request):
            entered.append(label)
            return original.handler(args, context, request)
        return handler
    assert registry.unregister('file.read', expected=original)
    registry.register(replace(original, handler=factory('approved')))
    approved = registry.get('file.read')
    host = McpHost(registry)
    tool = host._as_tool(approved)
    arguments = dict(host.prepare_call(tool, {'path': str(target)}).arguments)
    authority = WorkflowAuthority('owner', False, 'assisted', tmp_path / 'artifacts', ('file.read',), definition_fingerprint(approved), fingerprint(arguments))
    original_call = registry.capabilities.call

    def replace_at_dispatch(request, *, background=False):
        assert registry.unregister('file.read', expected=approved)
        registry.register(replace(approved, handler=factory('changed-target')))
        return original_call(request, background=background)
    try:
        with patch.object(registry.capabilities, 'call', side_effect=replace_at_dispatch):
            result = host.call(tool, arguments, workflow_authority=authority)
        assert result['ok'] is False
        assert entered == []
    finally:
        registry.context.reliability.close()

def test_workflow_guard_rechecks_authority_after_waiting_for_mutation_lane(tmp_path, monkeypatch):
    import threading
    from hanni.tools import base
    from hanni.tools.base import ToolPermissionError, ToolRequest
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    registry = build_default_registry(config, data_dir=tmp_path)
    target = tmp_path / 'report.txt'
    waiting = threading.Event()
    original_lane = base._MUTATION_LOCK

    class ObservedLane:

        def __enter__(self):
            waiting.set()
            original_lane.acquire()
            return self

        def __exit__(self, *_):
            original_lane.release()
    monkeypatch.setattr(base, '_MUTATION_LOCK', ObservedLane())
    authority = {'revoked': False}
    errors = []

    def guard():
        if authority['revoked']:
            raise ToolPermissionError('The workflow grant was revoked while waiting.')

    def execute():
        try:
            registry.capabilities.call(ToolRequest('file.write', {'path': str(target), 'text': 'Must never be written'}, confirmed=True, execution_guard=guard))
        except Exception as error:
            errors.append(error)
    worker = threading.Thread(target=execute, daemon=True)
    original_lane.acquire()
    try:
        worker.start()
        assert waiting.wait(5)
        authority['revoked'] = True
    finally:
        original_lane.release()
        worker.join(5)
        registry.context.reliability.close()
    assert not worker.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], ToolPermissionError)
    assert not target.exists()

def test_original_verification_read_cannot_escape_revoked_workflow_guard(tmp_path):
    from hanni.tools.base import ToolPermissionError, ToolRequest
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    registry = build_default_registry(config, data_dir=tmp_path)
    original_write, original_stat = (registry.get('file.write'), registry.get('file.stat'))
    state = {'revoked': False}
    observed = []

    def guard():
        if state['revoked']:
            raise ToolPermissionError('Authority was withdrawn after the write returned.')

    def write(args, context, request):
        result = original_write.handler(args, context, request)
        state['revoked'] = True
        return result

    def stat(args, context, request):
        observed.append('verification-read-entered')
        return original_stat.handler(args, context, request)
    assert registry.unregister('file.write', expected=original_write)
    assert registry.unregister('file.stat', expected=original_stat)
    registry.register(replace(original_write, handler=write))
    registry.register(replace(original_stat, handler=stat))
    target = tmp_path / 'once.txt'
    try:
        result = registry.execute(ToolRequest('file.write', {'path': str(target), 'text': 'Written once'}, confirmed=True, execution_guard=guard))
        assert result.ok is True and target.read_text() == 'Written once'
        assert result.verification['status'] == 'UNVERIFIED'
        assert observed == []
    finally:
        registry.context.reliability.close()

def test_original_verification_read_pins_checked_definition(tmp_path, monkeypatch):
    from hanni.tools.base import ToolRequest
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    registry = build_default_registry(config, data_dir=tmp_path)
    original = registry.get('file.stat')
    entered = []
    execute = registry.execute

    def changed_handler(args, context, request):
        entered.append(True)
        return original.handler(args, context, request)

    def replace_at_verification(request):
        if request.source == 'tool.verification' and request.name == 'file.stat':
            assert registry.unregister('file.stat', expected=original)
            registry.register(replace(original, handler=changed_handler))
        return execute(request)
    monkeypatch.setattr(registry, 'execute', replace_at_verification)
    target = tmp_path / 'once.txt'
    try:
        result = registry.execute(ToolRequest('file.write', {'path': str(target), 'text': 'Written once'}, confirmed=True))
        assert result.ok is True and target.read_text() == 'Written once'
        assert result.verification['status'] == 'UNVERIFIED'
        assert entered == []
    finally:
        registry.context.reliability.close()
