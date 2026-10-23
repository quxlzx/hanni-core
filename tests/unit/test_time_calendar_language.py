from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from unittest.mock import patch
import pytest
from hanni.tools.time_routing import time_read_request
from hanni.tools.timekeep import _now
from hanni.tools.calendar_routing import calendar_read_request, google_write_request
from hanni.tools.base import ToolRequest
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.tools.registry import build_default_registry
from hanni.tools.google_access import GoogleAccess, definitions as google_definitions

@pytest.mark.parametrize('phrase,offset', [("What is tomorrow's date?", 1), ("What's today's date?", 0), ('What day is it?', 0), ('What day will tomorrow be?', 1), ("What was yesterday's date?", -1)])
def test_date_language(phrase, offset):
    request = time_read_request(phrase)
    assert request and request.arguments == {'kind': 'date', 'day_offset': offset}

@pytest.mark.parametrize('phrase', ['What time is my meeting?', 'What time is it and play Spotify?', 'Show the date in this file', 'What is tomorrow like?', 'Set a timer', 'What time is it in Tokyo?'])
def test_other_intents_are_not_silently_reduced_to_local_clock(phrase):
    assert time_read_request(phrase) is None

def test_explicit_zone_is_preserved_only_when_requested():
    assert time_read_request('What time is it?').arguments == {'kind': 'time'}
    assert time_read_request('What time is it in Eastern time zone?').arguments['timezone'] == 'eastern'

def test_tomorrow_is_computed_from_os_clock_across_year_boundary():
    fixed = datetime(2026, 12, 31, 23, 58, tzinfo=timezone.utc)
    with patch('hanni.tools.timekeep.datetime') as clock:
        clock.now.return_value = fixed
        result = _now({'kind': 'date', 'day_offset': 1}, None, ToolRequest('time.now', {}))
    assert result.data['requested_date'] == '2027-01-01'
    assert 'Tomorrow is Friday, January 1, 2027.' == result.message

def test_calendar_default_is_google_only():
    now = date(2026, 12, 31)
    result = calendar_read_request("What's on my calendar tomorrow?", today=now)
    assert result.name == 'google_calendar.agenda'
    assert result.arguments == {'start_date': '2027-01-01', 'days': 1, 'query': ''}
    assert calendar_read_request('Show my Google calendar tomorrow', today=now).name == 'google_calendar.agenda'
    assert calendar_read_request('How about tomorrow?') is None

def test_calendar_write_never_becomes_read_or_implicit_local_change():
    phrase = 'Can you put on my calendar tomorrow at 7am to buy flowers?'
    assert calendar_read_request(phrase) is None
    assert google_write_request(phrase)
    assert google_write_request('Add to my calendar tomorrow at 7am to buy flowers')
    assert calendar_read_request('Show my calendar tomorrow and delete everything') is None

@pytest.mark.parametrize('phrase', ['whats on my calendar for today', 'whats on my calendar 2026-9-15', "What's on my calendar for 2026-09-15?"])
def test_browser_calendar_spelling_and_year_first_dates(phrase):
    request = calendar_read_request(phrase, today=date(2026, 9, 15))
    assert request.name == 'google_calendar.agenda'
    assert request.arguments == {'start_date': '2026-09-15', 'days': 1, 'query': ''}

def test_explicit_date_preserves_google_account_and_followup():
    request = calendar_read_request('show my Google calendar 2027-1-1')
    assert request.name == 'google_calendar.agenda'
    assert request.arguments == {'start_date': '2027-01-01', 'days': 1, 'query': ''}
    history = [{'role': 'user', 'content': 'show my school Google calendar today'}]
    request = calendar_read_request('and 2026-9-15?', history)
    assert request.name == 'google_calendar.agenda'
    assert request.arguments['account'] == 'school'
    assert request.arguments['start_date'] == '2026-09-15'

@pytest.mark.parametrize('phrase', ['whats on my calendar 2026-2-30', 'whats on my calendar 9/15', 'whats on my calendar 2026-9-15 to 2026-9-16', 'whats on my calendar today 2026-9-15', 'whats on my calendar 2026-9-15 at 3', 'show my calendar 2026-9-15 and delete everything', 'show my calendar 2026-9-15\nshow my calendar tomorrow', 'add a meeting on my calendar 2026-9-15'])
def test_dates_do_not_hide_invalid_or_compound_calendar_requests(phrase):
    assert calendar_read_request(phrase) is None

def test_clock_accepts_typed_whats():
    assert time_read_request('whats the local time').name == 'time.now'

def test_calendar_tmr_shorthand_resolves_before_tool_call():
    request = calendar_read_request("what's on my calendar tmr?", today=date(2026, 9, 22))
    assert request.name == 'google_calendar.agenda'
    assert request.arguments == {'start_date': '2026-09-23', 'days': 1, 'query': ''}

def test_google_calendar_create_natural_language_resolves_exact_time():
    from hanni.tools.calendar_routing import calendar_create_request
    now = datetime(2026, 9, 22, 10, 0)
    request = calendar_create_request('Schedule dinner Friday at 8pm for 2 hours', now=now, timezone_name='America/Chicago')
    assert request.name == 'google_calendar.create'
    assert request.arguments['summary'] == 'dinner'
    assert request.arguments['start'].startswith('2026-09-25T20:00:00')
    assert request.arguments['end'].startswith('2026-09-25T22:00:00')

def test_google_calendar_create_accepts_casual_add_and_word_duration():
    from hanni.tools.calendar_routing import calendar_create_request
    now = datetime(2026, 9, 23, 16, 15)
    dinner = calendar_create_request('add dinner tomorrow at 8', now=now, timezone_name='America/Chicago')
    assert dinner.name == 'google_calendar.create'
    assert dinner.arguments['summary'].casefold() == 'dinner'
    assert dinner.arguments['start'].startswith('2026-09-24T20:00:00')
    tasa = calendar_create_request('schedule tasa friday at 7 for two hours', now=now, timezone_name='America/Chicago')
    assert tasa.arguments['end'].startswith('2026-09-25T21:00:00')

def test_tonight_availability_and_two_hour_study_write_are_exact():
    from hanni.tools.calendar_routing import calendar_create_request, calendar_write_needs_time
    today = date(2026, 9, 25)
    assert calendar_read_request('am I free at 9 tonight', today=today).arguments['availability_at'] == '21:00'
    assert calendar_read_request('am I free at 9 this evening', today=today).arguments['availability_at'] == '21:00'
    assert calendar_read_request('am I free at 9 tomorrow', today=today).arguments['availability_at'] == '09:00'
    tonight = calendar_create_request('schedule study session tonight at 9', now=datetime(2026, 9, 25, 5), timezone_name='America/New_York')
    assert tonight.arguments['start'] == '2026-09-25T21:00:00-04:00'
    assert calendar_write_needs_time('add a 2-hour study session tomorrow evening')
    for hour in (17, 18):
        phrase = f'add a 2-hour study session tomorrow at {hour - 12}pm'
        request = calendar_create_request(phrase, now=datetime(2026, 9, 25, 5), timezone_name='America/New_York')
        assert request.arguments['summary'] == 'study session'
        assert request.arguments['start'] == f'2026-09-26T{hour}:00:00-04:00'
        assert request.arguments['end'] == f'2026-09-26T{hour + 2}:00:00-04:00'

def test_google_calendar_create_tmr_and_account_are_natural_language():
    from hanni.tools.calendar_routing import calendar_create_request
    request = calendar_create_request('Add TASA to my school calendar tmr at 7pm', now=datetime(2026, 9, 22, 10, 0), timezone_name='America/Chicago')
    assert request.arguments['account'] == 'school'
    assert request.arguments['summary'] == 'TASA'
    assert request.arguments['start'].startswith('2026-09-23T19:00:00')

def test_google_calendar_create_casual_time_range_is_timed():
    from hanni.tools.calendar_routing import calendar_create_request
    request = calendar_create_request('schedule study session tmr 3 to 5', now=datetime(2026, 9, 23, 16, 15), timezone_name='America/Chicago')
    assert request.arguments['start'].startswith('2026-09-24T15:00:00')
    assert request.arguments['end'].startswith('2026-09-24T17:00:00')

def test_calendar_owner_zone_is_independent_of_host_timezone():
    from hanni.tools.calendar_routing import calendar_create_request
    instant = datetime(2026, 9, 23, 21, 15, tzinfo=timezone.utc)
    request = calendar_create_request('add dinner tomorrow at 8', now=instant, timezone_name='America/Chicago')
    assert request.arguments['start'] == '2026-09-24T20:00:00-05:00'
    assert request.arguments['end'] == '2026-09-24T21:00:00-05:00'

def test_calendar_owner_zone_uses_dst_and_rejects_invalid_wall_times():
    from hanni.tools.calendar_routing import calendar_create_request
    winter = calendar_create_request('add dinner tomorrow at 8', now=datetime(2026, 12, 1, 16, 0, tzinfo=ZoneInfo('America/Chicago')), timezone_name='America/Chicago')
    assert winter.arguments['start'] == '2026-12-02T20:00:00-06:00'
    spring = calendar_create_request('add meeting tomorrow at 2:30am', now=datetime(2026, 3, 7, 12, 0, tzinfo=ZoneInfo('America/Chicago')), timezone_name='America/Chicago')
    assert spring is None
    fall = calendar_create_request('add meeting tomorrow at 1:30am', now=datetime(2026, 10, 31, 12, 0, tzinfo=ZoneInfo('America/Chicago')), timezone_name='America/Chicago')
    assert fall is None

def test_implicit_agenda_phrase_is_calendar_natural_language():
    request = calendar_read_request('What do I have tomorrow?', today=date(2026, 9, 22))
    assert request.name == 'google_calendar.agenda'
    assert request.arguments == {'start_date': '2026-09-23', 'days': 1, 'query': ''}

@pytest.mark.parametrize('phrase,expected', [('whats on my calendar for tmr', '2026-09-26'), ('whats on my calendar for sunday', '2026-09-27'), ('what on my calendar for monday', '2026-09-28'), ('whats on my calendar for friday', '2026-09-25'), ('what about this friday', '2026-09-25'), ('what about last friday', '2026-09-18'), ('what about saturday', '2026-09-26')])
def test_calendar_day_words_cannot_become_google_text_filters(tmp_path, phrase, expected):

    class Vault:

        def get(self, account):
            return {'email': 'owner@example.com', 'calendar_ids': ['primary']} if account == 'personal' else None
    calls = []

    def transport(account, path, params):
        calls.append(dict(params))
        day = date.fromisoformat(params['timeMin'][:10])
        return {'items': [] if params.get('q') else [{'id': 'event', 'summary': 'Event on requested day', 'start': {'date': day.isoformat()}, 'end': {'date': (day + timedelta(days=1)).isoformat()}}]}
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    registry = build_default_registry(config)
    access = GoogleAccess(Vault(), transport, timezone_name='America/New_York')
    registry._tools['google_calendar.agenda'] = next((definition for definition in google_definitions(access) if definition.name == 'google_calendar.agenda'))
    host = McpHost(registry, timezone_name='America/New_York')
    now = datetime(2026, 9, 25, 5, 18, tzinfo=ZoneInfo('America/New_York'))
    tools = host.route(phrase, now=now).tools
    assert len(tools) == 1 and tools[0].capability_id == 'google_calendar.agenda'
    assert tools[0].fixed_arguments == {'start_date': expected, 'days': 1, 'query': ''}
    assert 'query' not in tools[0].openai_schema()['function']['parameters']['properties']
    result = host.call(tools[0], {'query': 'sunday'})
    assert result['ok'] and result['data']['event_count'] == 1
    assert result['data']['resolved_date'] == expected
    assert calls[0]['timeMin'] == f'{expected}T00:00:00-04:00'
    assert 'q' not in calls[0]

def test_explicit_calendar_event_search_uses_owner_phrase_only():
    request = calendar_read_request('search my calendar for dentist', today=date(2026, 9, 25))
    assert request.name == 'google_calendar.agenda'
    assert request.arguments['query'] == 'dentist'
    dated = calendar_read_request('search my calendar for dentist on sunday', today=date(2026, 9, 25))
    assert dated.arguments['query'] == 'dentist'
    assert dated.arguments['start_date'] == '2026-09-27'
    assert calendar_read_request('search my calendar for sunday', today=date(2026, 9, 25)).arguments['query'] == ''
    assert calendar_read_request('when is my dentist appointment', today=date(2026, 9, 25)).arguments['query'] == 'dentist appointment'
