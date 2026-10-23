"""Operation words must retain the action/read boundary in the MCP menu."""
from datetime import datetime
import pytest
from hanni.evals.routing import build_default_host

@pytest.mark.parametrize('query', ['end every running python process', 'please end all running tasks', 'flip my laptop to high performance mode', 'switch this computer to power saver mode'])
def test_restricted_actions_never_fall_back_to_read_tools(query):
    decision = build_default_host().route(query)
    assert decision.status == 'blocked'
    assert decision.tools == ()

@pytest.mark.parametrize('query', ['which actions need my consent', 'what can Hanni do without my consent', 'is Hanni allowed to end processes'])
def test_permission_questions_are_read_only(query):
    decision = build_default_host().route(query)
    assert decision.status == 'tools'
    assert decision.tools[0].capability_id == 'hanni.permissions'

@pytest.mark.parametrize('query, expected', [('fire up Discord real quick', 'app.open'), ('bring up the Spotify desktop client', 'spotify.launch')])
def test_launch_phrases_keep_their_existing_capabilities(query, expected):
    decision = build_default_host().route(query)
    assert decision.status == 'tools'
    assert decision.tools[0].capability_id == expected

def test_window_focus_stays_restricted_in_the_default_eval_policy():
    decision = build_default_host().route('bring up the current window')
    assert decision.status == 'blocked'
    assert decision.blocked_capabilities == ('ui.focus_window',)

@pytest.mark.parametrize('query, required', [('tomorrow calendar plus current ram usage', {'google_calendar.agenda', 'system.stats'}), ('free tmr, and how much gpu memory is left', {'google_calendar.agenda', 'gpu.memory'}), ('tmr schedule and whos using most cpu', {'google_calendar.agenda', 'process.top_cpu'}), ('pc crawling rn, also got plans tomorrow', {'system.performance', 'google_calendar.agenda'}), ('next meeting and the biggest ram hog', {'google_calendar.next', 'process.top_memory'})])
def test_casual_mixed_clauses_reserve_both_capability_families(query, required):
    decision = build_default_host().route(query, now=datetime(2026, 9, 22, 13, 30))
    assert required <= {tool.capability_id for tool in decision.tools}

def test_calendar_event_title_is_not_split_into_two_requests():
    decision = build_default_host().route('schedule dinner and a movie tomorrow at 8', now=datetime(2026, 9, 22, 13, 30))
    assert [tool.capability_id for tool in decision.tools] == ['google_calendar.create']
    assert decision.tools[0].fixed_arguments['summary'] == 'dinner and a movie'

def test_low_gpu_memory_is_a_direct_capacity_question():
    decision = build_default_host().route('am I low on GPU mem right now')
    assert decision.tools[0].capability_id == 'gpu.memory'

def test_launch_then_play_uses_both_existing_actions():
    decision = build_default_host().route('get Steam up then start Spotify music')
    assert {'app.open', 'spotify.play_pause'} <= {tool.capability_id for tool in decision.tools}

def test_get_me_up_to_speed_does_not_launch_an_app():
    decision = build_default_host().route('get me up to speed on MCP')
    assert all((tool.capability_id != 'app.open' for tool in decision.tools))
