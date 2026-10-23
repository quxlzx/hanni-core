from __future__ import annotations
from pathlib import Path
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.tools.registry import build_default_registry
from hanni.tools.capabilities import capability_family
from hanni.tools.sensitive_paths import is_sensitive_path
from tests.helpers import FakeGoogleAccess, write_config_dir

def _host(tmp_path: Path) -> McpHost:
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    registry = build_default_registry(config)
    return McpHost(registry, read_only=True, max_tools=8)

def test_read_only_host_selects_small_bounded_tool_set(tmp_path):
    host = _host(tmp_path)
    tools = host.select_tools('What is using the most CPU on my computer right now?')
    assert 1 <= len(tools) <= 8
    assert any((tool.capability_id in {'process.top_cpu', 'system.stats'} for tool in tools))
    assert all((tool.risk == 'read_only' for tool in tools))

def test_action_request_exposes_no_model_tools(tmp_path):
    host = _host(tmp_path)
    assert host.select_tools('Kill the process using the most CPU') == ()
    assert host.select_tools('Delete this file') == ()

def test_model_mcp_never_exposes_arbitrary_powershell_even_when_actions_allowed(tmp_path, monkeypatch):
    registry = _host(tmp_path).registry
    host = McpHost(registry, read_only=False, allowed_actions=('powershell.run',))
    assert host.select_tools('run this powershell command') == ()
    tool = host._as_tool(registry.get('powershell.run'))
    monkeypatch.setattr('hanni.tools.powershell.subprocess.run', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('executed')))
    result = host.call(tool, {'command': 'Get-Date'})
    assert result['ok'] is False
    assert result['error']['code'] == 'PERMISSION_DENIED'

def test_model_mcp_does_not_read_credential_files(tmp_path):
    host = _host(tmp_path)
    credential = tmp_path / 'client_secret_example.json'
    credential.write_text('SYNTHETIC_PRIVATE_VALUE', encoding='utf-8')
    for name, arguments in (('file.read', {'path': str(credential)}), ('file.head', {'path': str(credential)}), ('file.tail', {'path': str(credential)}), ('file.compare', {'left': str(credential), 'right': str(credential)})):
        tool = host._as_tool(host.registry.get(name))
        result = host.call(tool, arguments)
        assert result['error']['code'] == 'PERMISSION_DENIED'
        assert 'SYNTHETIC_PRIVATE_VALUE' not in str(result)
    assert is_sensitive_path(tmp_path / '.env')
    assert is_sensitive_path(tmp_path / '.ssh' / 'config')
    assert is_sensitive_path(tmp_path / '.ssh')
    assert is_sensitive_path(tmp_path / 'my-passwords.txt')
    assert not is_sensitive_path(tmp_path / 'notes.txt')

def test_model_mcp_filename_tools_do_not_expose_credential_paths(tmp_path):
    host = _host(tmp_path)
    ordinary = tmp_path / 'notes.txt'
    ordinary.write_text('safe', encoding='utf-8')
    secret = tmp_path / 'client_secret_synthetic.json'
    secret.write_text('SYNTHETIC_PRIVATE_VALUE', encoding='utf-8')
    private_dir = tmp_path / '.ssh'
    private_dir.mkdir()
    (private_dir / 'config').write_text('SYNTHETIC_PRIVATE_VALUE', encoding='utf-8')
    for name, args in (('file.search', {'root': str(tmp_path), 'query': ''}), ('file.list_dir', {'path': str(tmp_path)})):
        result = host.call(host._as_tool(host.registry.get(name)), args)
        assert result['ok']
        assert ordinary.name in str(result)
        assert secret.name not in str(result)
        assert '.ssh' not in str(result)
        assert 'SYNTHETIC_PRIVATE_VALUE' not in str(result)
    for name, args in (('file.stat', {'path': str(secret), 'hash': True}), ('file.locate', {'root': str(tmp_path), 'name': secret.name}), ('file.search', {'root': str(private_dir), 'query': ''}), ('file.list_dir', {'path': str(private_dir)})):
        result = host.call(host._as_tool(host.registry.get(name)), args)
        assert result['ok'] is False
        assert result['error']['code'] == 'PERMISSION_DENIED'

def test_model_mcp_grep_skips_secret_files_and_redacts_returned_text(tmp_path):
    host = _host(tmp_path)
    (tmp_path / '.env.local').write_text('private_lookup=SEARCH_NEEDLE', encoding='utf-8')
    grep = host._as_tool(host.registry.get('file.grep'))
    result = host.call(grep, {'root': str(tmp_path), 'query': 'SEARCH_NEEDLE', 'pattern': '*'})
    assert result['ok'] is True
    assert result['data']['matches'] == []
    assert 'private_lookup' not in str(result)
    ordinary = tmp_path / 'notes.txt'
    ordinary.write_text('Authorization: Bearer synthetic-token-12345', encoding='utf-8')
    read = host._as_tool(host.registry.get('file.read'))
    result = host.call(read, {'path': str(ordinary)})
    assert result['ok'] is True
    assert 'synthetic-token-12345' not in str(result)

def test_model_mcp_redacts_errors_before_returning_them(tmp_path, monkeypatch):
    host = _host(tmp_path)
    tool = host._as_tool(host.registry.get('file.read'))

    def fail(_request):
        raise ValueError('Authorization: Bearer synthetic-token-67890')
    monkeypatch.setattr(host.registry, 'execute', fail)
    result = host.call(tool, {'path': str(tmp_path / 'ordinary.txt')})
    assert result['ok'] is False
    assert 'synthetic-token-67890' not in str(result)

def test_read_only_call_executes_through_registry(tmp_path):
    host = _host(tmp_path)
    tools = host.select_tools('Show my CPU and RAM usage')
    tool = next((tool for tool in tools if tool.capability_id == 'system.stats'))
    result = host.call(tool, {})
    assert result['ok'] is True
    assert 'cpu_percent' in result['data']

def test_wire_names_are_function_call_safe(tmp_path):
    host = _host(tmp_path)
    tools = host.select_tools('Show me what is using my CPU')
    assert tools
    for tool in tools:
        assert tool.wire_name.startswith('hanni__')
        assert '.' not in tool.wire_name
        assert len(tool.wire_name) <= 64

def test_natural_calendar_tomorrow_is_fixed_before_model(tmp_path):
    host = McpHost(_host(tmp_path).registry, read_only=True, max_tools=5, allowed_actions=('google_calendar.create',))
    tools = host.select_tools("What's on my calendar tomorrow?")
    agenda = next((tool for tool in tools if tool.capability_id == 'google_calendar.agenda'))
    assert agenda.fixed_arguments['days'] == 1
    assert agenda.fixed_arguments['start_date']
    function = agenda.openai_schema()['function']
    assert 'start_date' not in function['parameters']['properties']
    assert agenda.fixed_arguments['start_date'] in function['description']

def test_only_explicit_calendar_create_is_exposed_as_write(tmp_path):
    registry = _host(tmp_path).registry
    registry.google_access = FakeGoogleAccess()
    host = McpHost(registry, read_only=True, max_tools=5, allowed_actions=('google_calendar.create',))
    tools = host.select_tools('Schedule dentist tomorrow at 3pm')
    assert len(tools) == 1 and tools[0].capability_id == 'google_calendar.create'
    assert tools[0].fixed_arguments['summary'] == 'dentist'
    assert host.select_tools('Delete this file') == ()

def test_calendar_source_and_date_route_do_not_compete_with_local_tools(tmp_path):
    host = McpHost(_host(tmp_path).registry, read_only=True, max_tools=5, allowed_actions=('google_calendar.create',))
    tools = host.select_tools('What do I have tomorrow?')
    assert len(tools) == 1
    assert tools[0].capability_id == 'google_calendar.agenda'
    assert tools[0].fixed_arguments['days'] == 1

def test_google_calendar_is_the_only_registered_calendar_provider(tmp_path):
    host = _host(tmp_path)
    names = {definition.name for definition in host.registry.definitions()}
    assert {'google_calendar.agenda', 'google_calendar.next', 'google_calendar.list', 'google_calendar.create'} <= names
    assert not any((name.startswith('calendar.') for name in names))

def test_family_first_routing_scopes_ram_before_tool_ranking(tmp_path):
    host = _host(tmp_path)
    family = capability_family("what's eating all my ram")
    assert family is not None
    assert family.name == 'computer.memory'
    matches = host.discovery.search("what's eating all my ram", limit=12)
    names = [match.capability.name for match in matches]
    assert 'process.top_memory' in names
    assert all((family.allows(name) for name in names))
    assert not any((name.startswith(('google_calendar.', 'spotify.', 'archive.', 'ui.', 'security.', 'gpu.', 'disk.', 'time.')) for name in names))

def test_family_first_routing_preserves_fallback_when_no_family_is_confident(tmp_path):
    host = _host(tmp_path)
    query = 'show installed programs'
    assert capability_family(query) is None
    names = [match.capability.name for match in host.discovery.search(query, limit=5)]
    assert 'app.list_installed' in names

def test_diagnostic_subintents_classify_common_computer_problems(tmp_path):
    from hanni.tools.capabilities import diagnostic_subintent
    cases = {'why is my pc so slow right now': 'general_slowdown', "what's eating all my ram": 'memory_pressure', 'which process is hammering the cpu': 'cpu_pressure', 'what is using all my vram': 'gpu_vram', 'why is my disk io at 100 percent': 'disk_io', 'why is my internet latency so high': 'network', 'why are my fans so loud and the pc hot': 'thermal_power', 'why did windows blue screen': 'windows_errors', 'why is my qwen model server slow': 'model_runtime'}
    for query, expected in cases.items():
        scope = diagnostic_subintent(query)
        assert scope is not None, query
        assert scope.name == expected, query

def test_diagnostic_subintent_scopes_memory_retrieval(tmp_path):
    from hanni.tools.capabilities import diagnostic_subintent
    host = _host(tmp_path)
    query = "what's eating all my ram"
    scope = diagnostic_subintent(query)
    assert scope is not None and scope.name == 'memory_pressure'
    names = [match.capability.name for match in host.discovery.search(query, limit=12)]
    assert 'process.top_memory' in names
    assert all((scope.allows(name) for name in names))
    assert 'gpu.memory' not in names
    assert 'disk.largest_files' not in names

def test_diagnostic_subintent_scopes_gpu_and_windows_errors(tmp_path):
    from hanni.tools.capabilities import diagnostic_subintent
    host = _host(tmp_path)
    gpu_query = 'what is using all my vram'
    gpu_scope = diagnostic_subintent(gpu_query)
    gpu_names = [match.capability.name for match in host.discovery.search(gpu_query, limit=12)]
    assert gpu_scope is not None and gpu_scope.name == 'gpu_vram'
    assert 'gpu.memory' in gpu_names or 'gpu.top_processes' in gpu_names
    assert all((gpu_scope.allows(name) for name in gpu_names))
    assert 'process.top_memory' not in gpu_names
    error_query = 'why did windows blue screen'
    error_scope = diagnostic_subintent(error_query)
    error_names = [match.capability.name for match in host.discovery.search(error_query, limit=12)]
    assert error_scope is not None and error_scope.name == 'windows_errors'
    assert 'system.event_errors' in error_names
    assert all((error_scope.allows(name) for name in error_names))

def test_diagnostic_subintent_is_scope_only_not_tool_execution(tmp_path):
    from hanni.tools.capabilities import diagnostic_subintent
    host = _host(tmp_path)
    scope = diagnostic_subintent('why is my pc so slow')
    assert scope is not None and scope.name == 'general_slowdown'
    matches = host.discovery.search('why is my pc so slow', limit=8)
    assert matches
    assert all((scope.allows(match.capability.name) for match in matches))

def test_dynamic_tool_budget_keeps_specific_memory_question_small(tmp_path):
    from hanni.tools.capabilities import diagnostic_tool_budget
    host = McpHost(_host(tmp_path).registry, read_only=True, max_tools=8)
    query = 'what process is using the most ram'
    assert diagnostic_tool_budget(query, ceiling=8) == 2
    assert [tool.capability_id for tool in host.select_tools(query)] == ['process.top_memory', 'system.stats']

def test_general_slowdown_uses_curated_six_tool_bundle(tmp_path):
    from hanni.tools.capabilities import diagnostic_subintent, diagnostic_tool_budget
    host = McpHost(_host(tmp_path).registry, read_only=True, max_tools=8)
    query = 'why is my pc so slow right now'
    scope = diagnostic_subintent(query)
    assert scope is not None and scope.name == 'general_slowdown'
    assert diagnostic_tool_budget(query, ceiling=8) == 6
    assert [tool.capability_id for tool in host.select_tools(query)] == ['system.performance', 'system.stats', 'process.top_cpu', 'process.top_memory', 'process.top_disk_io', 'gpu.top_processes']

def test_diagnostic_bundles_are_retrieval_only_and_do_not_execute(tmp_path, monkeypatch):
    host = McpHost(_host(tmp_path).registry, read_only=True, max_tools=8)
    calls = []

    def fail_execute(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError('retrieval must not execute capabilities')
    monkeypatch.setattr(host.registry, 'execute', fail_execute)
    tools = host.select_tools('why is my pc so slow right now')
    assert len(tools) == 6
    assert calls == []

def test_negative_signal_plain_ram_boosts_process_memory_and_suppresses_gpu(tmp_path):
    host = _host(tmp_path)
    matches = host.discovery.search("what's eating all my ram right now", limit=8)
    names = [match.capability.name for match in matches]
    assert names[0] == 'process.top_memory'
    assert 'gpu.memory' not in names
    assert not any((name.startswith('gpu.') for name in names))

def test_negative_signal_vram_keeps_gpu_memory_tools(tmp_path):
    host = _host(tmp_path)
    matches = host.discovery.search('what is eating all my vram right now', limit=8)
    names = [match.capability.name for match in matches]
    assert 'gpu.top_processes' in names
    assert 'gpu.memory' in names
    assert 'process.top_memory' not in names

def test_negative_signal_right_now_is_not_a_clock_request(tmp_path):
    host = _host(tmp_path)
    names = [match.capability.name for match in host.discovery.search('show installed programs right now', limit=8)]
    assert 'app.list_installed' in names
    assert 'time.now' not in names

def test_negative_signal_windows_performance_is_not_ui_window_intent(tmp_path):
    host = _host(tmp_path)
    names = [match.capability.name for match in host.discovery.search('why does Windows feel so slow right now', limit=8)]
    assert 'system.performance' in names
    assert not any((name.startswith('ui.') for name in names))
