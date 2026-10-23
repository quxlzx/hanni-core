"""Implementation consent survives runtime warmup, not semantic replacement."""
import sys
from dataclasses import replace
from pathlib import Path
from hanni.config import load_config
from hanni.tools import build_default_registry
from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult
from hanni.workflows.policy import _callable_identity, definition_fingerprint

def test_interning_and_adaptive_execution_do_not_change_code_identity():
    namespace = {}
    exec("def observed(value):\n    return value.get('a_noninterned_observed_constant', 7)\n", namespace)
    observed = namespace['observed']
    before = _callable_identity(observed)
    for constant in observed.__code__.co_consts:
        if isinstance(constant, str):
            sys.intern(constant)
    for _ in range(10000):
        assert observed({}) == 7
    assert _callable_identity(observed) == before
    changed = observed.__code__.replace(co_consts=tuple((8 if c == 7 else c for c in observed.__code__.co_consts)))
    observed.__code__ = changed
    assert _callable_identity(observed) != before

def test_nested_semantic_code_constants_are_restart_and_location_stable():
    code = "def outer():\n    def nested(value):\n        return (value + 2, b'bytes', frozenset({1, 3}))\n    return nested\n"
    first, second = ({}, {})
    exec(compile(code, 'first-location.py', 'exec'), first)
    exec(compile('\n\n' + code, 'second-location.py', 'exec'), second)
    assert _callable_identity(first['outer']) == _callable_identity(second['outer'])

def test_original_task_add_get_complete_keeps_existing_definition_hashes(tmp_path):
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    registry = build_default_registry(config)
    before = {name: definition_fingerprint(registry.get(name)) for name in ('todo.add', 'todo.get', 'todo.complete')}
    try:
        added = registry.execute(ToolRequest('todo.add', {'title': 'Isolated identity evidence', 'due': '2030-06-12T15:00:00-04:00'}, confirmed=True))
        assert added.ok
        key = added.data['id']
        assert added.data['task']['due'] == '2030-06-12T15:00:00-04:00'
        assert registry.execute(ToolRequest('todo.get', {'id': key})).ok
        assert registry.execute(ToolRequest('todo.complete', {'id': key}, confirmed=True)).ok
        assert before == {name: definition_fingerprint(registry.get(name)) for name in before}
    finally:
        registry.context.reliability.close()

def test_stateful_handler_reregistration_still_invalidates_consent(tmp_path):
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    registry = build_default_registry(config)

    def factory(label):

        def handler(arguments, context, request):
            return ToolResult('local.observed', True, label, {})
        return handler
    try:
        registry.register(ToolDefinition('local.observed', 'Observed read', 0, 0, {}, {}, factory('first')))
        old = registry.get('local.observed')
        old_hash = definition_fingerprint(old)
        registry.unregister(old.name, expected=old)
        registry.register(replace(old, handler=factory('second')))
        current = registry.get(old.name)
        assert current.workflow_binding_id != old.workflow_binding_id
        assert definition_fingerprint(current) != old_hash
    finally:
        registry.context.reliability.close()
