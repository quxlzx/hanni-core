"""Actual result metadata and real PowerShell error classification regressions."""
from pathlib import Path
import os
import sys
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/v36_engineering'))
from fixtures import GoogleProvider, GoogleVault
from hanni.config.loader import load_config
from hanni.tools import build_default_registry
from hanni.tools.base import ToolRequest

@pytest.fixture
def registry(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    value = build_default_registry(config)
    provider = GoogleProvider()
    value.google_access._vault = GoogleVault()
    value.google_access.transport = provider
    yield (value, provider)
    value.context.reliability.close()

def assert_contract(definition, result):
    assert result.ok, result.message
    types = {'string': str, 'object': dict, 'array': list, 'boolean': bool, 'integer': int, 'number': (int, float)}
    for name, kind in definition.output_schema.items():
        assert name in result.data, (definition.name, name, result.data)
        assert isinstance(result.data[name], types[kind]), (definition.name, name, kind, type(result.data[name]))

def test_unavailable_audio_readback_does_not_invent_unmuted_state(registry, monkeypatch):
    from hanni.tools import media
    value, _ = registry
    monkeypatch.setattr(media, '_endpoint_volume', lambda: None)
    monkeypatch.setattr(media, 'require_windows', lambda _: None)
    monkeypatch.setattr(media, 'run_powershell_json', lambda *a, **k: [{'Name': 'Synthetic endpoint', 'Status': 'OK'}])
    result = value.execute(ToolRequest('audio.status'))
    assert result.ok and result.data['muted'] is None
    assert result.data['percent'] == -1 and result.data['precise'] is False
    assert 'unknown' in result.message
    assert value.get('audio.status').output_schema['muted'] == 'boolean|null'

def test_content_search_distinguishes_content_query_from_filename_filter(registry, tmp_path):
    value, _ = registry
    (tmp_path / 'sample.txt').write_text('A cobalt lighthouse appears.\n', encoding='utf-8')
    normal = value.execute(ToolRequest('file.grep', {'root': str(tmp_path), 'query': 'cobalt lighthouse'}))
    assert normal.data['match_count'] == 1 and normal.data['search_performed'] is True
    assert normal.data['scanned_files'] == 1 and normal.data['pattern'] == ''
    filtered = value.execute(ToolRequest('file.grep', {'root': str(tmp_path), 'query': 'cobalt lighthouse', 'pattern': 'cobalt lighthouse'}))
    assert filtered.data['scanned_files'] == 0 and filtered.data['search_performed'] is False
    assert 'No files were searched' in filtered.message and 'unknown' in filtered.message
    assert_contract(value.get('file.grep'), filtered)
    schema = value.get('file.grep').argument_schema()
    assert schema['properties']['pattern']['default'] == ''
    assert 'filename' in schema['properties']['pattern']['description']

def test_file_metadata_reports_actual_byte_count_and_full_hash(registry, tmp_path):
    import hashlib
    value, _ = registry
    content = 'é\n52 bytes is not assumed'.encode('utf-8')
    path = tmp_path / 'bytes.txt'
    path.write_bytes(content)
    measured = value.execute(ToolRequest('file.stat', {'path': str(path), 'hash': True}))
    assert measured.data['size_bytes'] == len(content) == path.stat().st_size
    assert measured.data['sha256'] == hashlib.sha256(content).hexdigest()
    assert value.execute(ToolRequest('file.stat', {'path': str(tmp_path)})).data['size_bytes'] is None
    assert value.execute(ToolRequest('file.stat', {'path': str(tmp_path / 'missing')})).data == {'path': str(tmp_path / 'missing'), 'exists': False}

@pytest.mark.parametrize('utterance', ['Add a local test note: cobalt lighthouse rehearsal is Friday.', 'Create a task called appointment preparation for Monday at 9am.', 'Schedule a local checklist for Friday at 8am.', 'Add a file called meeting.txt tomorrow at noon.', 'Add a note: create an event on my calendar tomorrow at 4pm.', 'Add a record with the text "on my calendar" Friday at 8pm.', 'Add note:9am meeting on my calendar Friday.', 'Add amber cargo Friday at 3pm.'])
def test_storage_and_ambiguous_add_intents_do_not_authorize_provider_creation(registry, utterance):
    from hanni.mcp.host import McpHost
    from hanni.tools.calendar_routing import calendar_create_request
    value, provider = registry
    assert calendar_create_request(utterance, timezone_name='America/New_York') is None
    host = McpHost(value, read_only=True, allowed_actions=('google_calendar.create',))
    decision = host.route(utterance)
    assert not any((t.capability_id in {'google_calendar.create', 'google.calendar.create'} for t in decision.tools))
    assert not provider.calls

@pytest.mark.parametrize('utterance', ['Add amber cargo to my personal Google calendar tomorrow at 3pm.', 'Schedule amber rehearsal Friday at 8pm.', 'Add a two-hour study session tomorrow at 6pm.', 'Add amber cargo Friday at 14:30 to my personal calendar.'])
def test_actual_calendar_intent_retains_original_policy_authority(registry, utterance):
    from hanni.mcp.host import McpHost
    value, _ = registry
    allowed = McpHost(value, read_only=True, allowed_actions=('google_calendar.create',)).route(utterance)
    assert any((t.capability_id in {'google_calendar.create', 'google.calendar.create'} for t in allowed.tools))
    denied = McpHost(value, read_only=True).route(utterance)
    assert denied.status == 'blocked' and (not denied.tools)

@pytest.mark.parametrize('utterance,expected', [('Put an optometrist consultation next Thursday at 10am.', True), ('Add physiotherapy next Wednesday at 11am.', True), ('Put a picnic next Sunday at noon.', True), ('Add a concert next Saturday at 7pm.', True), ('Add a tutorial Wednesday at 1pm.', True), ('Put a chemistry lab Tuesday at 2pm.', True), ('Add a local note: my optometrist consultation is Thursday at 10am.', False), ('Add a task about buying supplies for the picnic Sunday at noon.', False), ('Create a local file with the text tutorial Wednesday at 1pm.', False), ('Add a record called "concert" next Saturday at 7pm.', False), ('Add amber cargo Friday at 3pm.', False)])
def test_prospective_scheduling_domains_preserve_destination_boundaries(registry, utterance, expected):
    from hanni.mcp.host import McpHost
    from hanni.tools.calendar_routing import calendar_create_request
    value, provider = registry
    resolved = calendar_create_request(utterance, timezone_name='America/New_York')
    assert (resolved is not None) is expected
    decision = McpHost(value, read_only=True, allowed_actions=('google_calendar.create',)).route(utterance)
    assert any((t.capability_id in {'google_calendar.create', 'google.calendar.create'} for t in decision.tools)) is expected
    assert not provider.calls
    assert not McpHost(value, read_only=True).route(utterance).tools

@pytest.mark.parametrize('utterance,expected', [('Add maths tuition Wednesday at 11am.', True), ('Put teaching practice Friday at 10am.', True), ('Add tutoring hours next Thursday at 2pm.', True), ('Add a local note about maths tuition Wednesday at 11am.', False), ('Create a task containing teaching practice Friday at 10am.', False)])
def test_academic_activity_noun_families_do_not_change_local_storage_authority(registry, utterance, expected):
    from hanni.tools.calendar_routing import calendar_create_request
    assert (calendar_create_request(utterance, timezone_name='America/New_York') is not None) is expected
GOOGLE_READS = [('google.accounts', {}), ('gmail.search', {'query': 'rehearsal'}), ('gmail.read', {'id': 'message-v36'}), ('google_calendar.list', {}), ('google.calendar.list_calendars', {}), ('google_calendar.agenda', {'start_date': '2026-10-10', 'days': 1}), ('google.calendar.events', {'start_date': '2026-10-10', 'days': 1}), ('google.calendar.availability', {'start_date': '2026-10-10', 'days': 1, 'availability_start': '14:00', 'availability_end': '15:00'}), ('google_calendar.next', {}), ('google.calendar.next', {}), ('google.drive.list', {}), ('google.drive.recent', {}), ('google.drive.search', {'query': 'Rehearsal'}), ('google.drive.metadata', {'id': 'doc-v36'}), ('google.docs.read', {'id': 'doc-v36'}), ('google.tasks.list', {}), ('google.gmail.recent', {}), ('google.gmail.search', {'query': 'rehearsal'}), ('google.gmail.read', {'id': 'message-v36'}), ('google.gmail.thread', {'id': 'thread-v36'}), ('google.calendar.read', {'id': 'event-v36'})]

@pytest.mark.parametrize('name,args', GOOGLE_READS)
def test_google_declared_success_fields_are_real_operation_payload_fields(registry, name, args):
    value, _ = registry
    result = value.execute(ToolRequest(name, {**args, 'account': 'personal'} if name != 'google.accounts' else {}))
    assert_contract(value.get(name), result)
    assert 'data' not in value.get(name).output_schema

@pytest.mark.parametrize('name', ['google_calendar.create', 'google.calendar.create'])
def test_calendar_creation_contract_preserves_existing_receipt_shape(registry, name):
    value, _ = registry
    args = {'account': 'personal', 'summary': 'Controlled V36 contract', 'all_day': True, 'start_date': '2026-11-04', 'end_date': '2026-11-05'}
    result = value.execute(ToolRequest(name, args))
    assert_contract(value.get(name), result)
    assert result.data['outcome'] == 'created_but_not_reverified'
    assert 'data' not in result.data

@pytest.mark.parametrize('name,args', [('google.tasks.create', {'title': 'V36 task'}), ('google.tasks.complete', {'id': 'task-v36'}), ('google.calendar.update', {'id': 'event-v36', 'summary': 'V36 revised'}), ('google.calendar.delete', {'id': 'event-v36'})])
def test_google_write_contract_does_not_change_approval_or_payload(registry, name, args):
    value, _ = registry
    result = value.execute(ToolRequest(name, {**args, 'account': 'personal'}, confirmed=True))
    assert_contract(value.get(name), result)

def test_local_task_contracts_follow_each_actual_operation(registry):
    value, _ = registry
    created = value.execute(ToolRequest('todo.add', {'title': 'Controlled V36 task', 'due': 'tomorrow'}))
    assert_contract(value.get('todo.add'), created)
    for name in ('todo.get', 'todo.complete'):
        result = value.execute(ToolRequest(name, {'id': created.data['id']}))
        assert_contract(value.get(name), result)
    for name in ('todo.list', 'todo.due'):
        result = value.execute(ToolRequest(name, {}))
        assert_contract(value.get(name), result)

def test_standard_user_folders_contract_is_object(registry):
    value, _ = registry
    result = value.execute(ToolRequest('env.user_folders'))
    assert_contract(value.get('env.user_folders'), result)
    assert value.get('env.user_folders').output_schema['folders'] == 'object'

@pytest.mark.skipif(os.name != 'nt', reason='Actual Windows PowerShell catch/error-ID behavior')
@pytest.mark.parametrize('error_id,empty', [('NoMatchingEventsFound', True), ('AccessDenied', False), ('NoMatchingLogsFound', False)])
def test_event_log_empty_match_is_distinct_from_denied_or_missing_log(monkeypatch, error_id, empty):
    from hanni.tools import security, winshell
    prefix = 'function Get-WinEvent { [CmdletBinding()] param([hashtable]$FilterHashtable,[int]$MaxEvents); '
    prefix += "$e = [System.Management.Automation.ErrorRecord]::new([Exception]::new('controlled provider error'), '" + error_id + "', [System.Management.Automation.ErrorCategory]::InvalidOperation, $null); $PSCmdlet.ThrowTerminatingError($e) }; "
    monkeypatch.setattr(security, 'run_powershell_json', lambda command, **kwargs: winshell.run_powershell_json(prefix + command, **kwargs))
    if empty:
        result = security._event_errors({'log': 'Application', 'hours': 1}, None, None)
        assert result.ok and result.data['events'] == [] and (result.data['total'] == 0)
    else:
        with pytest.raises(RuntimeError, match='system.event_errors failed'):
            security._event_errors({'log': 'Application', 'hours': 1}, None, None)

def test_digital_silence_never_calls_decoder_but_low_amplitude_still_does():
    from types import SimpleNamespace
    from hanni.speech.stt import FasterWhisperTranscriber
    from hanni.speech.vad import Utterance

    class ActualBoundaryRecorder:

        def __init__(self):
            self.calls = []

        def transcribe(self, audio, **kwargs):
            self.calls.append((audio.copy(), kwargs))
            return (iter([SimpleNamespace(text='delegated original decoder result')]), SimpleNamespace(language='en', language_probability=0.8))
    model = ActualBoundaryRecorder()
    transcriber = FasterWhisperTranscriber(model=model)
    for pcm in (b'', b'\x00' * 64000):
        assert transcriber.transcribe(Utterance(pcm, 0, 2, 16000, 1)).text == ''
    assert not model.calls
    pcm = b'\x00' * 1024 + b'\x01\x00' + b'\x00' * 1024
    result = transcriber.transcribe(Utterance(pcm, 0, 1, 16000, 1))
    assert result.text == 'delegated original decoder result' and len(model.calls) == 1
    assert model.calls[0][0].max() == 1 / 32768
