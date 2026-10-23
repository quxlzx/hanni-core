import base64
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import pytest
from hanni.config import load_config
from hanni.tools import build_default_registry
from hanni.tools.base import ToolRequest
from hanni.tools.google_access import GoogleAccess, GoogleAccessError, SCOPES, definitions, _body, validate_credentials
from hanni.tools.google_auth import connect, dependency_error, logout, prepare_client_secrets, status
from hanni.tools.audit import _audit_arguments
from hanni.tools.google_identity import scopes_for
LOGIN_SCOPES = scopes_for(('calendar.read', 'gmail.read'))

class Vault:

    def __init__(self, records=None):
        self.records = records if records is not None else {'personal': {'email': 'one@example.com', 'calendar_ids': ['primary'], 'credentials': {}}, 'school': {'email': 'two@example.edu', 'calendar_ids': ['primary'], 'credentials': {}}}

    def get(self, name):
        return self.records.get(name)

    def set(self, name, value):
        self.records[name] = value

    def delete(self, name):
        self.records.pop(name, None)

def test_search_two_accounts_preserves_provenance_and_body_needs_account():
    calls = []

    def transport(account, path, params):
        calls.append((account, path, params))
        if path.endswith('/messages'):
            return {'messages': [{'id': 'abc'}]}
        return {'id': 'abc', 'snippet': account + ' snippet', 'internalDate': '20' if account == 'school' else '10', 'payload': {'headers': [{'name': 'Subject', 'value': account + ' subject'}]}}
    access = GoogleAccess(Vault(), transport)
    result = access.mail_search({'account': 'all'})
    assert [r['account'] for r in result['messages']] == ['school', 'personal']
    assert result['messages'][0]['email'] == 'two@example.edu'
    with pytest.raises(GoogleAccessError):
        access.mail_read({'account': 'all', 'id': 'abc'})
    with pytest.raises(GoogleAccessError):
        access.mail_read({'account': 'school', 'id': '../token'})
    assert len(calls) == 4

def test_partial_failure_does_not_say_both_inboxes_are_empty():

    def transport(account, path, params):
        if account == 'school':
            raise GoogleAccessError('school: expired sign-in')
        return {'messages': []}
    result = GoogleAccess(Vault(), transport).mail_search({'account': 'all'})
    assert result['partial'] and result['errors'][0]['account'] == 'school'

def test_calendar_empty_result_and_partial_failure_have_distinct_spoken_answers():

    def transport(account, path, params):
        if account == 'school':
            raise GoogleAccessError('school: sign-in expired')
        assert params['timeMin'].startswith('2026-09-15T00:00:00')
        assert params['timeMax'].startswith('2026-09-16T00:00:00')
        return {'items': []}
    definition = next((d for d in definitions(GoogleAccess(Vault(), transport)) if d.name == 'google_calendar.agenda'))
    result = definition.handler({'account': 'personal', 'start_date': '2026-09-15', 'days': 1}, None, None)
    assert result.ok and 'empty for September 15' in result.message
    result = definition.handler({'account': 'all', 'start_date': '2026-09-15', 'days': 1}, None, None)
    assert not result.ok and 'incomplete' in result.message and ('school' in result.message)
    assert 'calendar is empty' not in result.message

def test_calendar_date_windows_use_configured_zone_across_dst():
    calls = []
    access = GoogleAccess(Vault(), lambda account, path, params: calls.append(dict(params)) or {'items': []}, timezone_name='America/Chicago')
    access.agenda({'account': 'personal', 'start_date': '2026-03-08', 'days': 1})
    assert calls[0]['timeMin'] == '2026-03-08T00:00:00-06:00'
    assert calls[0]['timeMax'] == '2026-03-09T00:00:00-05:00'

def test_calendar_spoken_events_include_time_account_and_truncation():
    from hanni.tools.google_access import calendar_summary
    data = {'events': [{'summary': 'Homework review', 'start_local': '2026-09-15T14:30:00-05:00', 'account': 'school'}], 'window_start': '2026-09-15T00:00:00-05:00', 'window_end': '2026-09-16T00:00:00-05:00', 'partial': False, 'errors': [], 'truncated': True}
    spoken = calendar_summary(data)
    assert 'Homework review' in spoken and '2:30 PM' in spoken and ('school' in spoken)
    assert 'incomplete' in spoken and 'may be more' in spoken

def test_calendar_defaults_to_connected_slots_but_explicit_all_reports_missing_slot():
    vault = Vault({'personal': {'email': 'one@example.com', 'calendar_ids': ['primary'], 'credentials': {}}})
    calls = []
    access = GoogleAccess(vault, lambda account, path, params: calls.append(account) or {'items': []})
    assert not access.agenda({})['partial']
    assert calls == ['personal']
    result = access.agenda({'account': 'all'})
    assert result['partial'] and result['errors'][0]['account'] == 'school'
    with pytest.raises(GoogleAccessError, match='No Google accounts'):
        GoogleAccess(Vault({}), lambda *a: {}).agenda({})

def test_google_next_orders_instants_across_offsets_and_skips_cancelled():
    now = datetime.now(timezone.utc)

    def transport(account, path, params):
        assert params['singleEvents'] == 'true'
        assert params['orderBy'] == 'startTime'
        when = now + timedelta(hours=1 if account == 'school' else 2)
        offset = timezone(timedelta(hours=-5 if account == 'school' else 8))
        return {'timeZone': 'UTC', 'items': [{'id': 'cancelled', 'status': 'cancelled', 'start': {'dateTime': now.isoformat()}}, {'id': account, 'summary': 'A meeting', 'start': {'dateTime': when.astimezone(offset).isoformat()}, 'end': {'dateTime': (when + timedelta(hours=1)).isoformat()}}]}
    result = GoogleAccess(Vault(), transport).agenda({'account': 'all'}, next_only=True)
    assert result['event']['account'] == 'school'
    assert not result['partial']
    assert result['minutes_until_start'] >= 59
    assert result['minutes_until_start'] <= 61
    assert result['current_local_time']
    assert result['event_start_local'] == result['event']['start_local']

def test_calendar_pagination_and_bounded_truncation():
    calls = []

    def transport(account, path, params):
        calls.append(dict(params))
        return {'items': [], 'nextPageToken': 'next'}
    result = GoogleAccess(Vault(), transport).agenda({'account': 'personal'})
    assert len(calls) == 3 and result['truncated']
    assert calls[1]['pageToken'] == 'next'

def test_calendar_all_day_preserves_date_semantics():
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
    access = GoogleAccess(Vault(), lambda *args: {'timeZone': 'America/New_York', 'items': [{'id': 'day', 'summary': 'Vacation', 'start': {'date': tomorrow}, 'end': {'date': tomorrow}}]})
    event = access.agenda({'account': 'personal'})['events'][0]
    assert event['all_day'] and event['start']['date'] == tomorrow

def test_mail_html_is_inert_and_attachments_not_downloaded():
    encoded = base64.urlsafe_b64encode(b'<p>Deadline tomorrow</p><script>steal()</script>').decode()
    result = _body({'mimeType': 'multipart/mixed', 'parts': [{'mimeType': 'text/html', 'body': {'data': encoded}}, {'mimeType': 'text/plain', 'filename': 'attachment.txt', 'body': {'data': encoded}}]})
    assert 'Deadline tomorrow' in result['text'] and 'steal' not in result['text']
    assert result['untrusted_content']

def test_google_tools_are_read_only_except_explicit_calendar_create_and_stop_blocks_network(tmp_path):
    registry = build_default_registry(load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={}))
    calls = []
    access = GoogleAccess(Vault(), lambda *args: calls.append(args) or {})
    defs = definitions(access)
    for definition in defs:
        if definition.name == 'google_calendar.create':
            assert definition.side_effect == 'external_action' and definition.permission_level == 2
        else:
            assert definition.side_effect == 'read' and definition.permission_level == 0
        registry._tools[definition.name] = definition
    from hanni.core.shutdown import StopSource, EmergencyStopActive
    from hanni.core.identity import Actor
    registry.context.emergency_stop.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner('test'), reason='test')
    with pytest.raises(EmergencyStopActive):
        registry.execute(ToolRequest('gmail.search', {}))
    assert calls == []
    assert not any((d.name.endswith(('.send', '.delete')) for d in defs))

def test_queries_and_bodies_do_not_enter_tool_audit(tmp_path):
    registry = build_default_registry(load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={}))
    access = GoogleAccess(Vault(), lambda *args: {'messages': []})
    for d in definitions(access):
        registry._tools[d.name] = d
    registry.execute(ToolRequest('gmail.search', {'account': 'personal', 'query': 'sensitive-subject'}))
    audit = (tmp_path / 'logs/tool_audit.jsonl').read_text()
    assert 'sensitive-subject' not in audit and 'PRIVATE QUERY' in audit

def test_credential_scopes_and_token_endpoint_are_restricted():
    validate_credentials({'token_uri': 'https://oauth2.googleapis.com/token', 'scopes': list(SCOPES)})
    for info in [{'token_uri': 'https://evil.example/token', 'scopes': list(SCOPES)}, {'token_uri': 'https://oauth2.googleapis.com/token', 'scopes': list(SCOPES) + ['https://mail.google.com/']}, {'token_uri': 'https://oauth2.googleapis.com/token', 'scopes': []}]:
        with pytest.raises(GoogleAccessError):
            validate_credentials(info)

def test_oauth_verifies_identity_before_saving_and_keeps_accounts_separate(tmp_path):
    config = tmp_path / 'client.json'
    config.write_text(json.dumps({'installed': {'client_id': 'id', 'client_secret': 'secret', 'auth_uri': 'https://accounts.google.com/o/oauth2/auth', 'token_uri': 'https://oauth2.googleapis.com/token'}}))

    class Credentials:
        refresh_token = 'test-refresh'
        granted_scopes = LOGIN_SCOPES

        def to_json(self):
            return json.dumps({'token_uri': 'https://oauth2.googleapis.com/token', 'scopes': list(LOGIN_SCOPES)})

    class Flow:

        def run_local_server(self, **kwargs):
            assert kwargs['host'] == '127.0.0.1' and kwargs['timeout_seconds'] == 180
            assert kwargs['prompt'] == 'consent select_account'
            return Credentials()
    factory = lambda *args: Flow()
    vault = Vault({})
    with pytest.raises(GoogleAccessError, match='does not match'):
        connect('personal', 'one@example.com', config, vault=vault, flow_factory=factory, scopes=['calendar.read', 'gmail.read'], transport=lambda *args: {'email': 'wrong@example.com'})
    assert vault.records == {}
    for label, email in [('personal', 'one@example.com'), ('school', 'two@example.edu')]:
        connect(label, email, config, vault=vault, flow_factory=factory, scopes=['calendar.read', 'gmail.read'], transport=lambda *args, email=email: {'email': email})
    assert vault.get('personal')['email'] != vault.get('school')['email']
    with pytest.raises(GoogleAccessError, match='already connected'):
        connect('personal', 'one@example.com', config, vault=vault, flow_factory=factory)

def test_oauth_can_discover_email_and_status_and_logout_without_secret_leakage(tmp_path):
    config = tmp_path / 'client.json'
    config.write_text(json.dumps({'installed': {'client_id': 'id', 'client_secret': 'secret', 'auth_uri': 'https://accounts.google.com/o/oauth2/auth', 'token_uri': 'https://oauth2.googleapis.com/token'}}))

    class Credentials:
        refresh_token = 'fixture-refresh-secret'
        granted_scopes = LOGIN_SCOPES

        def to_json(self):
            return json.dumps({'token_uri': 'https://oauth2.googleapis.com/token', 'scopes': list(LOGIN_SCOPES), 'refresh_token': self.refresh_token})

    class Flow:

        def run_local_server(self, **kwargs):
            assert kwargs['open_browser'] and 'login_hint' not in kwargs
            return Credentials()
    vault = Vault({})
    transport = lambda account, path, params: {'email': 'one@example.com'} if 'userinfo' in path else {'items': []}
    connected = connect('personal', None, config, vault=vault, flow_factory=lambda *a: Flow(), transport=transport, scopes=['calendar.read', 'gmail.read'])
    rendered = json.dumps(connected)
    assert connected['gmail'] and connected['calendar'] and ('fixture-refresh-secret' not in rendered)
    rows = status(vault=vault, transport=transport, verify=True)
    assert rows[0]['connected'] and rows[0]['gmail'] and rows[0]['calendar']
    assert 'refresh' not in json.dumps(rows).lower()
    assert logout('personal', vault=vault)['local_connection_removed']
    assert not status(vault=vault)[0]['connected']

def test_missing_oauth_client_file_is_actionable(tmp_path):
    with pytest.raises(GoogleAccessError, match='was not found') as exc:
        connect('personal', None, tmp_path / 'google-oauth-client.json', vault=Vault({}))
    assert 'google-oauth-client.json' in str(exc.value)

def test_google_login_imports_desktop_client_in_one_command_without_browser_in_tests(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    downloaded = tmp_path / 'client_secret_download.json'
    downloaded.write_text(json.dumps({'installed': {'client_id': 'id', 'client_secret': 'fixture-secret', 'auth_uri': 'https://accounts.google.com/o/oauth2/auth', 'token_uri': 'https://oauth2.googleapis.com/token'}}))
    config_dir = tmp_path / 'config'
    opened, printed = ([], [])
    target = prepare_client_secrets(config_dir, input_fn=lambda prompt: str(downloaded), open_url=opened.append, output_fn=printed.append)
    assert target == config_dir / 'google-oauth-client.json'
    assert target.is_file()
    assert len(opened) == 1 and opened[0].startswith('https://console.cloud.google.com/')
    assert 'fixture-secret' not in '\n'.join(printed)
    assert prepare_client_secrets(config_dir, open_url=lambda url: pytest.fail('browser reopened')) == target

def test_google_login_finds_single_downloaded_desktop_client(tmp_path, monkeypatch):
    downloads = tmp_path / 'Downloads'
    downloads.mkdir()
    downloaded = downloads / 'client_secret_123.json'
    downloaded.write_text(json.dumps({'installed': {'client_id': 'id', 'client_secret': 'fixture-secret', 'auth_uri': 'https://accounts.google.com/o/oauth2/auth', 'token_uri': 'https://oauth2.googleapis.com/token'}}))
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    printed = []
    target = prepare_client_secrets(tmp_path / 'config', input_fn=lambda prompt: pytest.fail('path prompt opened'), open_url=lambda url: pytest.fail('setup page opened'), output_fn=printed.append)
    assert target.is_file()
    assert target.name == 'google-oauth-client.json'
    assert 'fixture-secret' not in '\n'.join(printed)

def test_google_login_rejects_non_desktop_json_before_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    downloaded = tmp_path / 'web_client.json'
    downloaded.write_text(json.dumps({'web': {'client_id': 'id', 'client_secret': 'fixture-secret'}}))
    with pytest.raises(GoogleAccessError, match='Desktop app'):
        prepare_client_secrets(tmp_path / 'config', input_fn=lambda prompt: str(downloaded), open_url=lambda url: None, output_fn=lambda text: None)
    assert not (tmp_path / 'config/google-oauth-client.json').exists()

def test_hanni_google_login_runs_import_then_oauth_in_one_invocation(tmp_path, monkeypatch, capsys):
    from argparse import Namespace
    from hanni.cli import _run_google
    from hanni.tools import google_auth
    steps = []
    client_file = tmp_path / 'config/google-oauth-client.json'

    def prepare(config_dir, *, explicit):
        steps.append('prepare')
        assert config_dir == tmp_path and explicit is None
        return client_file

    def oauth(account, email, path, *, calendar_ids, replace, scopes=None):
        steps.append('oauth')
        assert path == client_file and account == 'personal'
        return {'email': 'one@example.com', 'services': ['calendar.read']}
    monkeypatch.setattr(google_auth, 'prepare_client_secrets', prepare)
    monkeypatch.setattr(google_auth, 'connect', oauth)
    monkeypatch.setattr(google_auth, 'dependency_error', lambda: None)
    args = Namespace(google_command='login', client_secrets=None, account='personal', email=None, calendar_ids=None, replace=False)
    assert _run_google(args, tmp_path) == 0
    assert steps == ['prepare', 'oauth']
    output = capsys.readouterr().out
    assert 'one@example.com' in output and 'Authorized: calendar.read' in output

def test_hanni_google_login_checks_dependencies_before_opening_setup(tmp_path, monkeypatch, capsys):
    from argparse import Namespace
    from hanni.cli import _run_google
    from hanni.tools import google_auth
    monkeypatch.setattr(google_auth, 'dependency_error', lambda: 'Google support is not installed.')
    monkeypatch.setattr(google_auth, 'prepare_client_secrets', lambda *args, **kwargs: pytest.fail('setup browser opened'))
    args = Namespace(google_command='login', client_secrets=None, account='personal', email=None, calendar_ids=None, replace=False)
    assert _run_google(args, tmp_path) == 1
    assert 'Google support is not installed.' in capsys.readouterr().err

def test_google_cli_output_works_with_legacy_windows_console_encoding(tmp_path, monkeypatch):
    from argparse import Namespace
    from hanni.cli import _run_google
    from hanni.tools import google_auth
    monkeypatch.setattr(google_auth, 'dependency_error', lambda: None)
    monkeypatch.setattr(google_auth, 'prepare_client_secrets', lambda *a, **kw: tmp_path / 'client.json')
    monkeypatch.setattr(google_auth, 'connect', lambda *a, **kw: {'email': 'one@example.com', 'services': ['calendar.read', 'gmail.read']})
    monkeypatch.setattr(google_auth, 'status', lambda **kw: [{'connected': True, 'account': 'personal', 'email': 'one@example.com', 'calendar': True, 'gmail': True, 'services': {'calendar': {'read': True, 'write': False}}, 'token_health': 'not_checked', 'last_successful_api_check': None}])
    monkeypatch.setattr(google_auth, 'logout', lambda account: {'local_connection_removed': True})
    encoded = io.BytesIO()
    console = io.TextIOWrapper(encoded, encoding='cp1252', errors='strict')
    with patch('sys.stdout', console):
        assert _run_google(Namespace(google_command='login', client_secrets=None, account='personal', email=None, calendar_ids=None, replace=False), tmp_path) == 0
        assert _run_google(Namespace(google_command='status', verify=False, json=False), tmp_path) == 0
        assert _run_google(Namespace(google_command='logout', account='personal'), tmp_path) == 0
        console.flush()
    output = encoded.getvalue().decode('cp1252')
    assert 'Google account connected' in output
    assert 'Google connection: connected' in output
    assert "Removed HANNI's local Google authorization" in output

def test_missing_google_dependency_has_exact_recovery(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == 'google_auth_oauthlib.flow':
            raise ImportError('fixture secret must not escape')
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', missing)
    message = dependency_error()
    assert 'Google support is not installed' in message
    assert 'pip install -e ".[google]"' in message
    assert 'fixture secret' not in message

def test_real_http_adapter_sets_fixed_host_timeouts_and_no_redirects():
    google_requests = pytest.importorskip('google.auth.transport.requests')
    info = {'token': 'fixture-token', 'refresh_token': 'fixture-refresh', 'client_id': 'id', 'client_secret': 'secret', 'token_uri': 'https://oauth2.googleapis.com/token', 'scopes': list(SCOPES)}
    vault = Vault({'personal': {'email': 'one@example.com', 'credentials': info}})

    class Response:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_content(self, size):
            yield b'{"messages": []}'

    class Session:

        def __init__(self, credentials, **kwargs):
            assert kwargs['max_refresh_attempts'] == 1 and kwargs['refresh_timeout'] == 20

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def request(self, method, url, **kwargs):
            assert method == 'GET'
            assert url == 'https://www.googleapis.com/gmail/v1/users/me/messages'
            assert kwargs['timeout'] == 20 and kwargs['allow_redirects'] is False
            return Response()
    with patch.object(google_requests, 'AuthorizedSession', Session):
        result = GoogleAccess(vault).mail_search({'account': 'personal'})
    assert not result['errors']

def test_calendar_create_posts_exact_event_and_uses_default_account():
    calls = []

    def transport(account, path, params, body):
        calls.append((account, path, params, body))
        return {'id': 'evt1', 'summary': body['summary'], 'start': body['start'], 'end': body['end'], 'htmlLink': 'https://calendar.google.com/event?eid=fixture'}
    access = GoogleAccess(Vault(), transport)
    default = access.create_event({'summary': 'Dinner', 'all_day': False, 'start': '2026-09-25T20:00:00-04:00', 'end': '2026-09-25T21:00:00-04:00'})
    assert default['account'] == 'personal'
    result = access.create_event({'account': 'personal', 'summary': 'Dinner', 'all_day': False, 'start': '2026-09-25T20:00:00-04:00', 'end': '2026-09-25T21:00:00-04:00'})
    assert result['created'] and result['account'] == 'personal'
    assert calls[0][1] == '/calendar/v3/calendars/primary/events'
    assert calls[0][3]['summary'] == 'Dinner'
