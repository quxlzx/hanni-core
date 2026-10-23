"""Development regressions for everyday reliability, independent of final holdout."""
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from hanni.tools.calendar_routing import calendar_read_request, calendar_create_request, calendar_write_needs_time
from hanni.tools.google_access import GoogleAccess, calendar_summary
from hanni.tools.language_concepts import conceptual_query, recent_subject
from hanni.tools.storage import _usage
from hanni.tools.files import _search
from hanni.mcp.completion import Subtask, _completes
from hanni.evals.routing import build_default_host

class Vault:

    def get(self, name):
        return {'email': 'owner@example.com', 'calendar_ids': ['primary']} if name == 'personal' else None

def test_calendar_weekday_and_named_date_resolve_without_model_guessing():
    assert calendar_read_request("what's on this Sunday", today=date(2026, 9, 25)).arguments == {'start_date': '2026-09-27', 'days': 1, 'query': ''}
    assert calendar_read_request('can you check my calendar for September 27th', today=date(2026, 9, 25)).arguments['start_date'] == '2026-09-27'

def test_calendar_point_availability_uses_end_exclusive_overlap():

    def transport(account, path, params):
        assert params['timeMin'] == '2026-09-27T00:00:00-04:00'
        assert params['timeMax'] == '2026-09-28T00:00:00-04:00'
        return {'items': [{'id': 'meeting', 'summary': 'Evening meeting', 'start': {'dateTime': '2026-09-27T18:00:00-04:00'}, 'end': {'dateTime': '2026-09-27T23:00:00-04:00'}}]}
    access = GoogleAccess(Vault(), transport, timezone_name='America/New_York')
    for clock, busy in [('18:00', True), ('21:00', True), ('23:00', False)]:
        result = access.agenda({'account': 'personal', 'start_date': '2026-09-27', 'days': 1, 'availability_at': clock})
        assert result['availability']['busy'] is busy
        assert result['event_count'] == 1
        assert result['calendar_id'] == 'primary'
        assert result['resolved_date'] == '2026-09-27'
        assert ('busy' if busy else 'free') in calendar_summary(result)
    interval = access.agenda({'account': 'personal', 'start_date': '2026-09-27', 'days': 1, 'availability_start': '17:00', 'availability_end': '19:00'})
    assert interval['availability']['busy'] is True
    assert 'from 5:00 PM to 7:00 PM' in calendar_summary(interval)

def test_calendar_daypart_write_requests_an_exact_time():
    phrase = 'schedule a two hour reading block tomorrow evening'
    assert calendar_write_needs_time(phrase)
    assert calendar_create_request(phrase, now=datetime(2026, 9, 25, 9), timezone_name='America/New_York') is None
    assert not calendar_write_needs_time('schedule reading tomorrow evening at 7pm')

def test_calendar_interval_arguments_are_resolved_before_tool_selection():
    request = calendar_read_request('am i free from 6pm to 9pm Sunday', today=date(2026, 9, 25))
    assert request.arguments['start_date'] == '2026-09-27'
    assert request.arguments['availability_start'] == '18:00'
    assert request.arguments['availability_end'] == '21:00'

def test_media_subject_survives_short_followups_then_resets():
    history = [{'role': 'user', 'content': 'play spotify'}, {'role': 'user', 'content': 'pause that'}]
    assert recent_subject(history) == 'spotify'
    assert conceptual_query('resume it', history) == 'resume it spotify'
    assert conceptual_query("what's playing", history) == 'spotify status now playing'
    assert recent_subject(history + [{'role': 'user', 'content': 'tell me a joke'}]) is None

def test_drive_presence_comes_from_partition_enumeration(monkeypatch):
    monkeypatch.setattr('hanni.tools.storage.psutil.disk_partitions', lambda all=False: [SimpleNamespace(mountpoint='C:\\', device='C:', fstype='NTFS', opts='rw')])
    monkeypatch.setattr('hanni.tools.storage.psutil.disk_usage', lambda drive: SimpleNamespace(total=100 * 1024 ** 3, used=40 * 1024 ** 3, free=60 * 1024 ** 3, percent=40))
    result = _usage({'drive': 'D'}, None, None)
    assert result.data['present'] is False
    assert 'not among' in result.message

def test_started_process_completes_launch_without_window_claim():
    task = Subtask('open browser', frozenset({'app.open'}), kind='app_open')
    assert _completes(task, 'app.open', {'ok': True, 'data': {'outcome': 'process_started', 'verified': False, 'process_id': 123}})
    assert not _completes(task, 'app.open', {'ok': True, 'data': {'outcome': 'accepted', 'verified': False}})

def test_filename_search_prefers_personal_document_and_skips_dependencies(tmp_path: Path):
    (tmp_path / 'node_modules').mkdir()
    (tmp_path / 'node_modules' / 'resume.txt').write_text('dependency')
    (tmp_path / 'resume.pdf').write_text('personal')
    result = _search({'root': str(tmp_path), 'query': 'resume'}, None, None)
    assert result.data['matches'] == [str(tmp_path / 'resume.pdf')]

def test_file_search_followup_switches_root_and_keeps_search_object():
    host = build_default_host()
    history = [{'role': 'user', 'content': 'find my invoice file in downloads'}]
    decision = host.route('what about documents?', history=history)
    tool = next((tool for tool in decision.tools if tool.capability_id == 'file.search'))
    assert tool.fixed_arguments['root'] == str(Path.home() / 'Documents')

def test_drive_existence_routes_to_measured_disk_inventory():
    host = build_default_host()
    tool = host.route('is there a d drive on this computer').tools[0]
    assert tool.capability_id == 'disk.usage'
    assert tool.fixed_arguments['drive'] == 'D'

def test_calendar_availability_arguments_are_resolver_only():
    host = build_default_host()
    agenda = host.route('show my calendar today').tools[0]
    schema = agenda.openai_schema()['function']['parameters']['properties']
    assert not {'availability_at', 'availability_start', 'availability_end'} & set(schema)
    assert agenda.fixed_arguments['start_date']
