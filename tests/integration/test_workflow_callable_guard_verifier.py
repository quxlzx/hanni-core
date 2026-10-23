"""Independent callable replacement boundaries through original workflow host.

These are exposed development checks, not sealed planning inputs. Real local
handlers are wrapped only to record forbidden entry. No replacement executor.
"""
from dataclasses import replace
from pathlib import Path
import threading
import pytest
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.tools import base
from hanni.tools.registry import build_default_registry
from hanni.workflows.policy import WorkflowAuthority, definition_fingerprint
from hanni.workflows.types import fingerprint

@pytest.fixture
def registry(tmp_path):
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path / 'state', env={})
    current = build_default_registry(config)
    try:
        yield current
    finally:
        current.context.reliability.close()

def install(registry, old, handler):
    assert registry.unregister(old.name, expected=old)
    registry.register(replace(old, handler=handler))
    return registry.get(old.name)

def approve(host, definition, arguments, artifact_root):
    tool = host._as_tool(definition)
    prepared = dict(host.prepare_call(tool, arguments, artifact_root=artifact_root).arguments)
    authority = WorkflowAuthority('owner', True, 'assisted', artifact_root, (definition.name,), definition_fingerprint(definition), fingerprint(prepared))
    return (tool, prepared, authority)

@pytest.mark.parametrize('style', ['closure', 'bound_instance'])
def test_replacement_before_host_validation_never_enters_changed_callable(registry, tmp_path, style):
    original = registry.get('file.read')
    entered = []

    def factory(label):

        def handler(arguments, context, request):
            entered.append(label)
            return original.handler(arguments, context, request)
        return handler

    class Bound:

        def __init__(self, label):
            self.label = label

        def handler(self, arguments, context, request):
            entered.append(self.label)
            return original.handler(arguments, context, request)
    first = factory('approved') if style == 'closure' else Bound('approved').handler
    second = factory('changed') if style == 'closure' else Bound('changed').handler
    approved = install(registry, original, first)
    target = tmp_path / 'input.txt'
    target.write_text('Isolated original file; no external action.', encoding='utf-8')
    host = McpHost(registry)
    tool, arguments, authority = approve(host, approved, {'path': str(target)}, tmp_path / 'artifacts')
    install(registry, approved, second)
    result = host.call(tool, arguments, workflow_authority=authority)
    assert result['ok'] is False
    assert entered == [], 'Old consent must not authorize a different captured closure or instance.'

def test_replacement_while_waiting_for_original_mutation_lane_is_denied(registry, tmp_path, monkeypatch):
    original = registry.get('file.write')
    entered = []

    def factory(label):

        def handler(arguments, context, request):
            entered.append(label)
            return original.handler(arguments, context, request)
        return handler
    approved = install(registry, original, factory('approved'))
    root = tmp_path / 'artifacts'
    root.mkdir()
    target = root / 'report.txt'
    host = McpHost(registry)
    tool, arguments, authority = approve(host, approved, {'path': str(target), 'text': 'Never written by stale authority.'}, root)
    waiting = threading.Event()
    actual_lock = base._MUTATION_LOCK

    class ObservedLane:

        def __enter__(self):
            waiting.set()
            actual_lock.acquire()
            return self

        def __exit__(self, *_):
            actual_lock.release()
    monkeypatch.setattr(base, '_MUTATION_LOCK', ObservedLane())
    results = []
    actual_lock.acquire()
    worker = threading.Thread(target=lambda: results.append(host.call(tool, arguments, workflow_authority=authority)), daemon=True)
    try:
        worker.start()
        assert waiting.wait(5), 'The request did not reach the original mutation lane.'
        install(registry, approved, factory('changed'))
    finally:
        actual_lock.release()
        worker.join(5)
    assert not worker.is_alive()
    assert len(results) == 1 and results[0]['ok'] is False
    assert entered == []
    assert not target.exists()
