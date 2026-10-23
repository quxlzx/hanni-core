"""Offline API, account, scope, routing and result-reference contracts."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import pytest
from hanni.config import load_config
from hanni.mcp.host import McpHost
from hanni.tools.base import ConfirmationRequired, ToolRequest
from hanni.tools.google_access import GoogleAccess, GoogleAccessError
from hanni.tools.google_identity import scopes_for, authorized, account_label
from hanni.tools.google_services import GoogleServices, definitions, NOT_IMPLEMENTED, DOC_MIME
from hanni.tools.google_routing import GoogleDialogue, google_request, requested_account
from hanni.tools.google_auth import connect, status
from hanni.tools.registry import build_default_registry
ROOT = Path(__file__).resolve().parents[2]

class Vault:

    def __init__(self, grants=('calendar.read', 'gmail.read', 'drive.read', 'docs.read', 'tasks.read'), settings=None):
        self.records = {name: {'email': name + '@example.test', 'calendar_ids': ['primary'], 'credentials': {'token_uri': 'https://oauth2.googleapis.com/token', 'scopes': list(scopes_for(grants))}} for name in ('personal', 'school', 'work')}
        self.settings = settings or {}

    def get(self, account):
        return self.records.get(account)

    def set(self, account, record):
        self.records[account] = record

    def delete(self, account):
        self.records.pop(account, None)

    def preferences(self):
        return self.settings

def file(id='doc1', mime=DOC_MIME):
    return {'id': id, 'name': 'Routing notes', 'mimeType': mime, 'modifiedTime': '2026-09-24T10:00:00Z', 'owners': [{'displayName': 'Owner'}], 'webViewLink': 'https://docs.google.com/document/d/' + id + '/edit'}

def test_default_scopes_are_calendar_read_only_and_service_grants_are_separate():
    scopes = scopes_for()
    assert authorized(scopes, 'calendar.read')
    assert not any((authorized(scopes, name) for name in ('calendar.write', 'gmail.read', 'drive.read', 'tasks.write')))
    assert authorized(scopes_for(['calendar.write']), 'calendar.read')
    assert authorized(scopes_for(['docs.read']), 'drive.read')
    assert not authorized(scopes_for(['drive.read']), 'docs.read')
    with pytest.raises(GoogleAccessError):
        scopes_for(['gmail.send'])

@pytest.mark.parametrize('name', ['work', 'research-lab', 'account_2'])
def test_named_account_labels(name):
    assert account_label(name) == name

@pytest.mark.parametrize('name', ['all', 'default', '../vault', 'a b', 'x' * 33])
def test_invalid_account_labels(name):
    with pytest.raises(GoogleAccessError):
        account_label(name)

def test_default_and_service_account_preferences_never_fan_out():
    vault = Vault(settings={'default_google_account': 'work', 'gmail': 'school'})
    access = GoogleAccess(vault, transport=lambda *a: {})
    assert access.resolve_account(service='gmail') == 'school'
    assert access.resolve_account(service='drive') == 'work'
    assert access.resolve_account('personal', 'gmail') == 'personal'
    with pytest.raises(GoogleAccessError, match='not connected'):
        access.resolve_account('missing')

def test_drive_search_is_bounded_metadata_only_and_query_escaped():
    calls = []
    access = GoogleAccess(Vault(), lambda *args: calls.append(args) or {'files': [file()]})
    result = GoogleServices(access).drive({'query': "owner's notes", 'account': 'school'}, 'search')
    assert len(calls) == 1 and calls[0][0] == 'school' and (calls[0][1] == '/drive/v3/files')
    assert "owner\\'s notes" in calls[0][2]['q']
    assert calls[0][2]['spaces'] == 'drive' and 'trashed = false' in calls[0][2]['q']
    assert result['files'][0]['account'] == 'school' and result['files'][0]['id'] == 'doc1'

def test_drive_partial_and_empty_are_distinct():
    service = GoogleServices(GoogleAccess(Vault(), lambda *a: {'files': [], 'nextPageToken': 'more'}))
    assert service.drive({}, 'list')['state'] == 'partial'
    service = GoogleServices(GoogleAccess(Vault(), lambda *a: {'files': []}))
    assert service.drive({}, 'list')['state'] == 'not_found'

def test_docs_export_requires_content_scope_and_native_document():
    calls = []

    def transport(account, path, params):
        calls.append(path)
        return 'verified document text' if path.endswith('/export') else file()
    service = GoogleServices(GoogleAccess(Vault(), transport))
    assert service.docs_read({'id': 'doc1'})['content'] == 'verified document text'
    assert calls[-1].endswith('/doc1/export')
    restricted = GoogleServices(GoogleAccess(Vault(('drive.read',)), transport))
    with pytest.raises(GoogleAccessError) as exc:
        restricted.docs_read({'id': 'doc1'})
    assert exc.value.code == 'permission_denied'
    pdf = GoogleServices(GoogleAccess(Vault(), lambda *a: file(mime='application/pdf')))
    with pytest.raises(GoogleAccessError) as exc:
        pdf.docs_read({'id': 'doc1'})
    assert exc.value.code == 'not_implemented'

def test_tasks_create_and_complete_use_google_provider_and_verified_ids():
    calls = []

    def transport(account, path, params, body=None, **kwargs):
        calls.append((account, path, body, kwargs))
        return {'id': 'task1', 'title': 'Homework', 'status': (body or {}).get('status', 'needsAction')}
    service = GoogleServices(GoogleAccess(Vault(('tasks.write',)), transport))
    assert service.tasks({'title': 'Homework'}, 'create')['provider'] == 'google'
    assert service.tasks({'id': 'task1'}, 'complete')['tasks'][0]['status'] == 'completed'
    assert calls[-1][3]['method'] == 'PATCH'
    with pytest.raises(GoogleAccessError):
        GoogleServices(GoogleAccess(Vault(('tasks.read',)), transport)).tasks({'title': 'Homework'}, 'create')

def test_calendar_sensitive_mutations_require_confirmation_before_network(tmp_path):
    calls = []
    access = GoogleAccess(Vault(('calendar.write',)), lambda *a, **kw: calls.append(a) or {'id': 'evt1'})
    registry = build_default_registry(load_config(ROOT / 'config', data_dir=tmp_path, env={}))
    for definition in definitions(access):
        registry._tools[definition.name] = definition
    for name in ('google.calendar.update', 'google.calendar.delete'):
        with pytest.raises(ConfirmationRequired):
            registry.execute(ToolRequest(name, {'id': 'evt1', 'summary': 'New'} if name.endswith('update') else {'id': 'evt1'}))
    assert not calls
    result = registry.execute(ToolRequest('google.calendar.delete', {'id': 'evt1'}, confirmed=True))
    assert result.ok and result.data['deleted']

def test_tasks_complete_requires_confirmation(tmp_path):
    registry = build_default_registry(load_config(ROOT / 'config', data_dir=tmp_path, env={}))
    with pytest.raises(ConfirmationRequired):
        registry.execute(ToolRequest('google.tasks.complete', {'id': 'task1'}))

def test_google_failure_is_not_empty_data():

    def fail(*a):
        raise GoogleAccessError('Drive access denied.', 'permission_denied')
    definition = next((d for d in definitions(GoogleAccess(Vault(), fail)) if d.name == 'google.drive.search'))
    result = definition.handler({'query': 'resume'}, None, None)
    assert not result.ok and result.data['state'] == 'permission_denied'
    assert 'No matching' not in result.message

def test_reference_is_exact_and_expires_without_research():
    now = [100]
    state = GoogleDialogue(clock=lambda: now[0], ttl=20)
    tool = SimpleNamespace(capability_id='google.drive.search', fixed_arguments={'query': 'resume', 'account': 'school'})
    state.remember(tool, {'ok': True, 'data': {'files': [{'id': 'abc', 'account': 'school', 'type': DOC_MIME}], 'content': 'PRIVATE'}})
    followup = state.followup('open 1')
    assert followup.name == 'google.drive.metadata' and followup.arguments == {'account': 'school', 'id': 'abc'}
    assert state.followup('read it').name == 'google.docs.read'
    assert 'PRIVATE' not in repr(vars(state))
    switch = state.followup('what about my work account')
    assert switch.arguments['account'] == 'work' and switch.arguments['query'] == 'resume'
    now[0] = 121
    with pytest.raises(GoogleAccessError, match='expired'):
        state.followup('open 1')

def test_multiple_results_require_number_and_do_not_guess():
    state = GoogleDialogue()
    state.remember(SimpleNamespace(capability_id='google.drive.search', fixed_arguments={}), {'data': {'files': [{'id': 'a', 'account': 'personal'}, {'id': 'b', 'account': 'personal'}]}})
    with pytest.raises(GoogleAccessError, match='Which result'):
        state.followup('open it')
    assert state.followup('open 2').arguments['id'] == 'b'

@pytest.mark.parametrize('query,name', [('find my resume in Drive', 'google.drive.search'), ('show me recent Google Docs', 'google.drive.recent'), ('search school Drive for syllabus', 'google.drive.search'), ('read Google Doc ID abc', 'google.docs.read'), ('what Google Tasks do I have', 'google.tasks.list'), ('add finish homework to my Google Tasks', 'google.tasks.create'), ('what are my 5 most recent Gmail messages', 'google.gmail.recent'), ('search Gmail from NVIDIA', 'google.gmail.search'), ('what is on my Google Calendar tomorrow', 'google.calendar.events'), ('am I free at 9 tonight on Google Calendar', 'google.calendar.availability')])
def test_small_google_menus(query, name):
    assert google_request(query, now=datetime.fromisoformat('2026-09-25T10:00:00-04:00')).name == name

def test_sender_is_not_account_and_local_drives_stay_local():
    assert requested_account('Did NVIDIA email me?') is None
    assert google_request('wipe this drive') is None
    assert google_request('check C drive') is None
    assert google_request('what program is thrashing my drive') is None
    assert google_request('how much room on drive') is None
    assert requested_account('check my school schedule tomorrow') == 'school'
    request = google_request('find my resume in Drive account research-lab')
    assert request.arguments['account'] == 'research-lab' and request.arguments['query'] == 'resume'

def test_write_scope_is_required_even_when_policy_allows_tasks(tmp_path):
    registry = build_default_registry(load_config(ROOT / 'config', data_dir=tmp_path, env={}))
    registry.google_access = GoogleAccess(Vault(('tasks.read',)))
    host = McpHost(registry, allowed_actions=('google.tasks.create',))
    assert host.route('add homework to my Google Tasks').status == 'blocked'
    registry.google_access = GoogleAccess(Vault(('tasks.write',)))
    assert host.route('add homework to my Google Tasks').tools[0].capability_id == 'google.tasks.create'

def test_unsupported_writes_are_explicit_and_unregistered(tmp_path):
    registry = build_default_registry(load_config(ROOT / 'config', data_dir=tmp_path, env={}))
    names = {d.name for d in registry.definitions()}
    assert all((name not in names and reason for name, reason in NOT_IMPLEMENTED.items()))

def test_status_reports_grants_without_network_or_tokens():
    vault = Vault(('drive.read',))
    vault.records['personal']['credentials']['refresh_token'] = 'never-print-this'
    rows = status(vault=vault, transport=lambda *a: pytest.fail('offline status must not connect'))
    row = next((row for row in rows if row['account'] == 'personal'))
    assert row['services']['drive']['read'] and (not row['services']['gmail']['read'])
    assert row['token_health'] == 'not_checked'
    assert 'never-print-this' not in json.dumps(rows)

@pytest.mark.parametrize('code,state', [(401, 'not_connected'), (403, 'permission_denied'), (404, 'not_found'), (429, 'rate_limited'), (500, 'api_error')])
def test_http_failures_preserve_state_and_redact_response(code, state):
    transport = pytest.importorskip('google.auth.transport.requests')
    vault = Vault()
    vault.records['personal']['credentials'].update(token='fixture-token', refresh_token='fixture-refresh', client_id='fixture-id', client_secret='fixture-secret')

    class Response:
        status_code = code

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def iter_content(self, size):
            pytest.fail('failure body must not be consumed or logged')

    class Session:

        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def request(self, *a, **kw):
            return Response()
    with patch.object(transport, 'AuthorizedSession', Session):
        with pytest.raises(GoogleAccessError) as exc:
            GoogleAccess(vault)._get('personal', '/drive/v3/files')
    assert exc.value.code == state and 'fixture-' not in str(exc.value)

@pytest.mark.parametrize('revoked', [False, True])
def test_network_and_revoked_token_errors_hide_library_secrets(revoked):
    transport = pytest.importorskip('google.auth.transport.requests')
    from google.auth.exceptions import RefreshError
    vault = Vault()
    vault.records['personal']['credentials'].update(token='fixture-token', refresh_token='fixture-refresh', client_id='fixture-id', client_secret='fixture-secret')
    error = RefreshError('secret-library-text') if revoked else OSError('secret-library-text')
    with patch.object(transport, 'AuthorizedSession', side_effect=error):
        with pytest.raises(GoogleAccessError) as exc:
            GoogleAccess(vault)._get('personal', '/drive/v3/files')
    assert exc.value.code == ('not_connected' if revoked else 'api_error')
    assert 'secret' not in str(exc.value) and exc.value.__suppress_context__

def test_named_doc_reads_only_unique_match_and_ambiguous_results_stay_metadata():
    calls = []
    matches = [file('first'), file('second')]

    def transport(account, path, params):
        calls.append(path)
        if path == '/drive/v3/files':
            return {'files': matches}
        if path.endswith('/export'):
            return 'verified routing design'
        return file('first')
    services = GoogleServices(GoogleAccess(Vault(), transport))
    request = google_request('read my HANNI design doc')
    assert request.name == 'google.docs.read' and request.arguments['query'] == 'hanni design'
    result = services.docs_read(request.arguments)
    assert result['needs_selection'] and 'content' not in result
    assert calls == ['/drive/v3/files']
    matches.pop()
    result = services.docs_read(request.arguments)
    assert result['content'] == 'verified routing design'
    assert calls[-1] == '/drive/v3/files/first/export'

def test_calendar_update_validates_exact_times_and_source_before_patch():
    calls = []

    def transport(account, path, params, body=None, **kw):
        calls.append((path, body, kw))
        return {'id': 'event1', **(body or {})}
    services = GoogleServices(GoogleAccess(Vault(('calendar.write',)), transport))
    with pytest.raises(GoogleAccessError):
        services.calendar_item({'id': 'event1', 'start': '2026-09-25T10:00:00', 'end': '2026-09-25T11:00:00'}, 'update')
    assert all((call[1] is None for call in calls))
    result = services.calendar_item({'id': 'event1', 'start': '2026-09-25T10:00:00-04:00', 'end': '2026-09-25T11:00:00-04:00'}, 'update')
    assert result['updated'] and calls[-1][2]['method'] == 'PATCH'

def test_thread_errors_are_safe_tool_results_and_ids_preserve_case():

    def transport(*a):
        raise GoogleAccessError('Missing scope', 'permission_denied')
    definition = next((d for d in definitions(GoogleAccess(Vault(), transport)) if d.name == 'google.gmail.thread'))
    result = definition.handler({'id': 'ABC123'}, None, None)
    assert not result.ok and result.data['state'] == 'permission_denied'
    assert google_request('read Gmail thread ID ABC123').arguments['id'] == 'ABC123'

def test_followup_account_switch_clears_old_results_on_failure():
    state = GoogleDialogue()
    state.remember(SimpleNamespace(capability_id='google.drive.search', fixed_arguments={'query': 'resume'}), {'data': {'files': [{'id': 'a', 'account': 'personal'}]}})
    switch = state.followup('what about my work account')
    state.remember(SimpleNamespace(capability_id=switch.name, fixed_arguments=switch.arguments), {'ok': False, 'data': {'state': 'not_connected'}})
    with pytest.raises(GoogleAccessError, match='no current Google result'):
        state.followup('open 1')

def test_session_cannot_claim_empty_drive_after_failed_api(tmp_path):
    from hanni.mcp.session import McpToolSession
    from hanni.models.client import ModelToolCall, ModelTurn

    class Fallback:
        history = []

        def record_turn(self, *a):
            pass

        def stream_response(self, *a, **kw):
            pytest.fail('Google failure must not enter generic fallback')

    class Client:
        calls = 0

        def complete_with_tools(self, messages, *, tools, **kw):
            self.calls += 1
            if self.calls == 1:
                return ModelTurn('', (ModelToolCall('call1', tools[0]['function']['name'], {}),))
            return ModelTurn('Your Drive is empty.')
    registry = build_default_registry(load_config(ROOT / 'config', data_dir=tmp_path, env={}))

    def transport(*a):
        raise GoogleAccessError('Google Drive access denied.', 'permission_denied')
    for definition in definitions(GoogleAccess(Vault(), transport)):
        registry._tools[definition.name] = definition
    session = McpToolSession(Fallback(), Client(), McpHost(registry), max_rounds=2)
    answer = ''.join(session.stream_response('find my resume in Drive'))
    assert 'access denied' in answer and 'empty' not in answer

def test_model_cannot_change_default_account_to_all_or_another_account(tmp_path):
    registry = build_default_registry(load_config(ROOT / 'config', data_dir=tmp_path, env={}))
    calls = []
    access = GoogleAccess(Vault(settings={'default_google_account': 'school'}), lambda account, *a: calls.append(account) or {'files': []})
    for definition in definitions(access):
        registry._tools[definition.name] = definition
    host = McpHost(registry)
    tool = host.route('find my resume in Drive').tools[0]
    assert host.call(tool, {'account': 'all'})['ok']
    assert host.call(tool, {'account': 'work'})['ok']
    assert calls == ['school', 'school']
