from datetime import datetime
import pytest
from hanni.evals.isolation import deny_execution
from hanni.evals.routing import RoutingCase, build_default_host, evaluate_case, load_cases, run_benchmark
from hanni.mcp.host import McpHost
from hanni.tools.base import ToolDefinition, ToolRequest

def test_registry_coverage_does_not_count_forbidden_or_acceptable_mentions():
    host = build_default_host()
    host.registry.register(ToolDefinition('test.uncovered', 'Synthetic untested capability', 0, 0, {}, {}, deny_execution))
    case = RoutingCase('probe', 'probe', 'hello', 'other', 'conversation', mode='fallback', acceptable=('test.uncovered',), forbidden=('test.uncovered',))
    report = run_benchmark(host, [case])
    assert 'test.uncovered' in report.coverage['missing']

def test_evaluation_registry_strips_all_real_handlers():
    host = build_default_host()
    for definition in host.registry.definitions():
        assert definition.handler is deny_execution
        with pytest.raises(AssertionError, match='forbidden'):
            definition.handler({}, None, None)
    with pytest.raises(AssertionError, match='forbidden'):
        host.registry.execute(ToolRequest('system.stats'))

def test_all_registry_capabilities_have_multiple_direct_probes_and_are_reachable_or_blocked():
    host = build_default_host()
    report = run_benchmark(host, load_cases())
    assert report.coverage['total'] == len(host.registry.definitions())
    assert report.coverage['missing'] == []
    assert all((r['number_of_routing_cases'] >= 2 for r in report.coverage['capabilities']))
    assert all((r['reachable'] or r['correctly_blocked'] for r in report.coverage['capabilities']))
    assert report.pass_rate > 85
    stats = report.family_stats()
    for family, minimum in {'diagnostics': 85, 'process_system': 90, 'calendar_read': 90, 'calendar_create': 95, 'mixed_domain': 75, 'slang_typos': 80, 'blocked_writes': 99}.items():
        assert stats[family]['pass_rate'] > minimum

@pytest.mark.parametrize('query,required', [('Please open Discord and play Spotify', {'app.open', 'spotify.play_pause'}), ('Why is this laptop sluggish and what is on my calendar next week?', {'system.performance', 'google_calendar.agenda'}), ('What is the clock time and which app uses the most processor time?', {'time.now', 'process.top_cpu'})])
def test_compound_requests_reserve_room_for_each_domain(query, required):
    host = build_default_host()
    decision = host.route(query, now=datetime(2026, 9, 22, 10))
    assert required <= {t.capability_id for t in decision.tools}
    assert len(decision.tools) <= 8

def test_app_launch_and_playback_wait_for_model_and_only_explicit_allowlist():
    host = build_default_host()
    assert 'app.open' in {t.capability_id for t in host.select_tools('Could you launch Discord?')}
    assert 'spotify.play_pause' in {t.capability_id for t in host.select_tools('Can you play Spotify?')}
    readonly = McpHost(host.registry)
    assert readonly.route('Open Discord').status == 'blocked'
    assert readonly.route('Open Discord').blocked_capabilities == ('app.open',)
    assert host.select_tools('Is Discord open?')[0].capability_id == 'process.find'

def test_incorrect_family_or_subintent_annotations_fail_strict_scoring():
    case = RoutingCase('negative', 'test', 'Which app is eating RAM?', 'process', 'diagnostic', required=('process.top_memory',), acceptable=('system.stats',), expected_families=('calendar',), expected_subintent='network')
    result = evaluate_case(build_default_host(), case)
    assert not result.passed
    assert result.metrics['family'] is False
    assert result.metrics['subintent'] is False

@pytest.mark.parametrize('reference,phrase,day,days', [(datetime(2026, 12, 31), 'tomorrow', '2027-01-01', 1), (datetime(2028, 2, 28), 'tomorrow', '2028-02-29', 1), (datetime(2026, 9, 27), 'this weekend', '2026-09-26', 2), (datetime(2026, 9, 22), 'next week', '2026-09-28', 7)])
def test_local_calendar_boundaries_are_fixed_in_schema(reference, phrase, day, days):
    tools = build_default_host().select_tools('What is on my calendar ' + phrase, now=reference)
    assert tools[0].fixed_arguments == {'start_date': day, 'days': days, 'query': ''}
    function = tools[0].openai_schema()['function']
    assert 'start_date' not in function['parameters']['properties']
    assert day in function['description']
