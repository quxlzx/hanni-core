"""Development readback/action discovery through the original host, without calls."""
from dataclasses import replace
import pytest
from hanni.evals.routing import build_default_host

@pytest.fixture
def host(tmp_path, monkeypatch):
    host = build_default_host(data_dir=tmp_path / 'isolated')
    monkeypatch.setattr(host.registry, 'execute', lambda *_a, **_k: (_ for _ in ()).throw(AssertionError('discovery executed a tool')))
    return host

@pytest.mark.parametrize('query', ['Read back one local task by its exact ID.', 'Read saved local task fields by ID', 'Read a specific local task by its exact ID', 'Get the saved fields of this local task by its identifier'])
def test_precise_entity_read_is_not_hidden_by_broad_collection_menu(host, query):
    names = [tool.capability_id for tool in host.select_tools(query)]
    assert 'todo.get' in names
    assert 'todo.add' not in names and 'todo.complete' not in names
    assert len(names) <= host.max_tools

def test_unrelated_namespace_cannot_use_single_shared_object_word(host):
    getter = host.registry.get('todo.get')
    host.registry.register(replace(getter, name='unrelated.readback'))
    names = [tool.capability_id for tool in host.select_tools('Read back one local task by its exact ID.')]
    assert 'todo.get' in names
    assert 'unrelated.readback' not in names
    assert [tool.capability_id for tool in host.select_tools('List my tasks')] == ['todo.list']

@pytest.mark.parametrize('query', ['Create a local text file at C:\\isolated\\approval-target.txt', 'Create a text file C:\\isolated\\report.txt', 'Make a local text file at C:\\isolated\\report.txt', 'Save the supplied text file at C:\\isolated\\report.txt', 'Write the file contents at C:\\isolated\\report.txt'])
def test_explicitly_allowlisted_local_write_uses_original_schema(host, query):
    host.allowed_actions = (*host.allowed_actions, 'file.write')
    tools = host.select_tools(query)
    assert [tool.capability_id for tool in tools] == ['file.write']
    assert tools[0].input_schema == host.registry.get('file.write').argument_schema()
    request = host.prepare_call(tools[0], {'path': 'C:\\isolated\\report.txt', 'text': 'fixture'})
    assert request.actor_profile == 'owner' and request.confirmed is False

@pytest.mark.parametrize('query', ['Do not create a local text file at C:\\isolated\\report.txt', 'Never create a local text file at C:\\isolated\\report.txt', 'I created a local text file at C:\\isolated\\report.txt', 'A local text file exists at C:\\isolated\\report.txt'])
def test_nonrequested_or_negated_creation_never_discovers_write_fallback(host, query):
    host.allowed_actions = (*host.allowed_actions, 'file.write')
    assert 'file.write' not in {tool.capability_id for tool in host.select_tools(query)}

def test_missing_whitelist_and_imported_action_cannot_enter_local_fallback(host):
    query = 'Create a local text file at C:\\isolated\\report.txt'
    assert not host.select_tools(query)
    write = host.registry.get('file.write')
    host.registry.register(replace(write, name='mcp.fixture.write', external_definition_hash='f' * 64, tags=('isolated-server',), aliases=('external_report',)))
    host.allowed_actions = (*host.allowed_actions, 'mcp.fixture.write')
    assert host._retrieval_actions(query) == ()
    assert 'mcp.fixture.write' not in {tool.capability_id for tool in host.select_tools(query)}
