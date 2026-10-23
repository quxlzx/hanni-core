"""Academic Calendar requests: route, bounded fetch, match, and follow-up."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import pytest
from hanni.evals.routing import build_default_host
from hanni.mcp.session import McpToolSession
from hanni.tools.calendar_search import academic_search_plan
from hanni.tools.google_access import GoogleAccess, calendar_summary, definitions
ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 25, 5)

class Vault:

    def __init__(self, connected=('personal',)):
        self.connected = connected

    def get(self, account):
        return {'email': f'{account}@example.test', 'calendar_ids': ['primary']} if account in self.connected else None

def host():
    return build_default_host(config_dir=ROOT / 'config', timezone_name='America/New_York')

def event(title, when, *, event_id=None, location=''):
    return {'id': event_id or title, 'summary': title, 'location': location, 'start': {'dateTime': when}, 'end': {'dateTime': when.replace('14:00', '15:15')}}

def test_future_month_week_and_ordinary_day_windows_are_fixed_before_model():
    checks = (('when is my first mid term', '2026-09-25T05:00:00-04:00', '2027-03-24T05:00:00-04:00', 'midterm'), ('when is my first mid term on my google calendar', '2026-09-25T05:00:00-04:00', '2027-03-24T05:00:00-04:00', 'midterm'), ('when are my next mid terms for october', '2026-10-01T00:00:00-04:00', '2026-11-01T00:00:00-04:00', 'midterm'), ('do i have exams next week', '2026-09-28T00:00:00-04:00', '2026-10-05T00:00:00-04:00', 'exam'), ('when is my next exam', '2026-09-25T05:00:00-04:00', '2027-03-24T05:00:00-04:00', 'exam'), ('when is my exam October 6, 2027', '2027-10-06T00:00:00-04:00', '2027-10-07T00:00:00-04:00', 'exam'))
    service = host()
    for phrase, start, end, concept in checks:
        route = service.route(phrase, now=NOW)
        assert route.status == 'tools'
        assert [tool.capability_id for tool in route.tools] == ['google_calendar.agenda']
        args = route.tools[0].fixed_arguments
        assert args['time_min'] == start and args['time_max'] == end
        assert args['academic_concept'] == concept and args['query'] == ''
        schema = route.tools[0].openai_schema()['function']['parameters']['properties']
        assert not {'time_min', 'time_max', 'academic_concept', 'course'} & set(schema)
    ordinary = service.route('what is on my calendar today', now=NOW).tools[0].fixed_arguments
    assert ordinary == {'start_date': '2026-09-25', 'days': 1, 'query': ''}

def test_first_midterm_finds_first_exam_like_event_after_unrelated_agenda_items():
    calls = []
    fixtures = [event(f'Social event {i}', f'2026-09-2{5 + i % 5}T14:00:00-04:00') for i in range(15)]
    fixtures += [event('CMSC330 Exam 1', '2026-10-06T14:00:00-04:00', location='KEY 0106'), event('CMSC320 Midterm Exam I', '2026-10-15T14:00:00-04:00')]

    def transport(account, path, params):
        calls.append((account, dict(params)))
        return {'items': [item for item in fixtures if params['timeMin'] <= item['start']['dateTime'] < params['timeMax']]}
    plan = academic_search_plan('when is my first mid term', now=NOW, timezone_name='America/New_York')
    data = GoogleAccess(Vault(), transport, timezone_name='America/New_York').agenda(plan.request().arguments)
    answer = calendar_summary(data)
    assert len(calls) == 1 and 'q' not in calls[0][1]
    assert data['events_fetched'] == 17 and data['matched_count'] == 2
    assert data['events'][0]['summary'] == 'CMSC330 Exam 1'
    assert 'CMSC330 Exam 1' in answer and 'CMSC320 Midterm Exam I' in answer
    assert 'light stick' not in answer and 'Social event' not in answer
    assert 'KEY 0106' in answer

def test_month_followup_preserves_subject_month_and_updates_only_source():
    previous = 'when are my next mid terms for october'
    history = [{'role': 'user', 'content': previous}, {'role': 'assistant', 'content': 'I could not check that yet.'}]
    route = host().route('its on my personal calendar', history=history, now=NOW)
    args = route.tools[0].fixed_arguments
    assert args['academic_concept'] == 'midterm' and args['account'] == 'personal'
    assert args['time_min'] == '2026-10-01T00:00:00-04:00'
    assert args['time_max'] == '2026-11-01T00:00:00-04:00'
    assert args['followup_context_used'] is True
    assert host().route('its on my personal calendar', now=NOW).tools[0].fixed_arguments.get('academic_concept') is None

def test_numeric_course_shorthand_matches_existing_code_without_inventing_department():
    plan = academic_search_plan('when is my 351 midterm', now=NOW, timezone_name='America/New_York')
    assert plan.course == '351'
    items = [event('CMSC351 Exam 1', '2026-10-06T14:00:00-04:00'), event('MATH240 Exam 1', '2026-10-07T14:00:00-04:00')]
    access = GoogleAccess(Vault(), lambda *args: {'items': items}, timezone_name='America/New_York')
    data = access.agenda(plan.request().arguments)
    assert [item['summary'] for item in data['events']] == ['CMSC351 Exam 1']
    assert 'MATH240' not in calendar_summary(data)
    ambiguous = GoogleAccess(Vault(), lambda *args: {'items': items + [event('MATH351 Midterm', '2026-10-08T14:00:00-04:00')]}, timezone_name='America/New_York').agenda(plan.request().arguments)
    assert ambiguous['ambiguous_course']
    assert 'multiple courses ending in 351' in calendar_summary(ambiguous)

def test_no_match_and_partial_fetch_have_distinct_answers():
    plan = academic_search_plan('what exams do I have in October', now=NOW, timezone_name='America/New_York')
    empty = GoogleAccess(Vault(), lambda *args: {'items': [event('Office hours', '2026-10-06T14:00:00-04:00'), event('Final Project', '2026-10-07T14:00:00-04:00')]}, timezone_name='America/New_York').agenda(plan.request().arguments)
    assert "didn't find an event" in calendar_summary(empty)
    assert 'October 2026' in calendar_summary(empty)

    def paginated(account, path, params):
        return {'items': [], 'nextPageToken': 'more'}
    partial = GoogleAccess(Vault(), paginated, timezone_name='America/New_York').agenda(plan.request().arguments)
    assert partial['truncated']
    assert 'incomplete' in calendar_summary(partial)
    assert "didn't find an event" not in calendar_summary(partial)

def test_calendar_connection_error_is_reported_from_tool_not_fabricated_access_claim():
    plan = academic_search_plan('when is my next exam', now=NOW, timezone_name='America/New_York')
    definition = next((item for item in definitions(GoogleAccess(Vault(()), lambda *args: {})) if item.name == 'google_calendar.agenda'))
    result = definition.handler(plan.request().arguments, None, None)
    assert not result.ok and 'No Google accounts are connected' in result.message

def test_session_uses_calendar_tool_directly_for_academic_search(monkeypatch):
    service = host()
    seen = []

    def call(tool, args):
        seen.append((tool.capability_id, dict(tool.fixed_arguments), dict(args)))
        return {'ok': True, 'message': 'Your first exam-like event is Biology Exam 1 on October 6.', 'data': {'events_fetched': 3, 'academic_candidates': 1, 'exam_candidates': 1}}
    monkeypatch.setattr(service, 'call', call)

    class Fallback:
        history = []

        def record_turn(self, prompt, answer):
            self.history.append({'role': 'user', 'content': prompt})

        def build_messages(self, prompt, system_suffix=''):
            return []

    class NoModel:

        def complete_with_tools(self, *args, **kwargs):
            raise AssertionError('the resolved academic read should run before model generation')
    answer = ''.join(McpToolSession(Fallback(), NoModel(), service).stream_response('when is my first midterm'))
    assert 'Biology Exam 1' in answer
    assert seen[0][0] == 'google_calendar.agenda' and seen[0][2] == {}
