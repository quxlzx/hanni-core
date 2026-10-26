"""Owner setup uses the real identity/scope checks with isolated credential storage."""
from dataclasses import replace
import http.client
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from uuid import uuid4
from urllib.parse import urlsplit

import pytest

from hanni.dashboard.features import DesktopFeatures
from hanni.dashboard.google_accounts import GoogleAccounts, account_revision
from hanni.tools.google_access import GoogleAccess, WindowsTokenVault, SERVICE
from hanni.tools.google_oauth_browser import BrowserGoogleFlow
from hanni.tools import google_auth
from hanni.tools.google_identity import GoogleAccessError, IDENTITY_SCOPE, PREFIX, scopes_for
from tests.unit.test_mcp_hub_api import config_for
from tests.unit.test_native_mcp import service

CLIENT = {'installed': {'client_id': 'fixture.apps.googleusercontent.com', 'client_secret': 'fixture-client-secret',
                       'auth_uri': 'https://accounts.google.com/o/oauth2/auth', 'token_uri': 'https://oauth2.googleapis.com/token'}}


class Vault:
    def __init__(self): self.records, self.settings = {}, {}
    def get(self, name): return self.records.get(name)
    def set(self, name, record): self.records[name] = record
    def delete(self, name):
        self.records.pop(name, None)
        self.settings = {key: value for key, value in self.settings.items() if value != name}
    def preferences(self): return dict(self.settings)
    def set_preference(self, name): self.settings['default_google_account'] = name


@pytest.fixture
def setup(tmp_path):
    cfg = config_for(tmp_path)
    cfg = replace(cfg, paths=replace(cfg.paths, config_dir=tmp_path / 'config'))
    features = DesktopFeatures(cfg)
    vault = Vault()
    features.registry.google_access = GoogleAccess(vault)
    gate = threading.Event(); calls = []
    email = {'value': 'personal@example.test'}
    class Credentials:
        refresh_token = 'fixture-refresh-token'
        def __init__(self, scopes): self.scopes, self.granted_scopes = scopes, scopes
        def to_json(self): return json.dumps({'token_uri': 'https://oauth2.googleapis.com/token', 'scopes': list(self.scopes),
                                              'refresh_token': self.refresh_token, 'client_id': 'fixture-client', 'token': 'fixture-access-token'})
    def factory(config, scopes):
        class Flow:
            def run_local_server(self, **kwargs):
                calls.append(kwargs)
                assert gate.wait(5), 'Test did not release sign-in'
                return Credentials(scopes)
        return Flow()
    control = GoogleAccounts(features, flow_factory=factory, transport=lambda *_: {'email': email['value']})
    yield SimpleNamespace(control=control, features=features, vault=vault, gate=gate, calls=calls, email=email)
    gate.set(); control.close()


def act(control, operation, data=None, key=None):
    return control.execute({'id': key or str(uuid4()), 'operation': operation, 'data': data or {}})


def import_client(control):
    return act(control, 'import_client', {'document': json.dumps(CLIENT), 'expected_revision': control.snapshot()['client']['revision']})


def start(control, account='personal', **overrides):
    return act(control, 'connect', {'account': account, 'scopes': ['calendar.read', 'gmail.read'],
                                   'replace': False, 'expected_revision': 'missing', **overrides})


def wait_job(control):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        result = control.snapshot()
        if result['job']['state'] not in {'waiting', 'cancelling'}:
            control.thread.join(1)
            return result
        time.sleep(.01)
    pytest.fail('Google sign-in did not settle')


def test_import_is_validated_versioned_and_does_not_expose_secrets(setup):
    c = setup.control
    assert c.snapshot()['available'] and not c.snapshot()['client']['ready']
    result = import_client(c)
    assert result['client']['ready']
    assert 'fixture-client-secret' not in json.dumps(result)
    assert json.loads(c.client_path.read_text()) == CLIENT
    with pytest.raises(ValueError, match='changed'):
        act(c, 'import_client', {'document': json.dumps(CLIENT), 'expected_revision': 'missing'})
    bad = {'installed': {**CLIENT['installed'], 'token_uri': 'https://foreign.example/token'}}
    with pytest.raises(ValueError, match='official Google'):
        act(c, 'import_client', {'document': json.dumps(bad), 'expected_revision': result['client']['revision']})
    audit = (setup.features.root / 'logs/tool_audit.jsonl').read_text()
    assert 'fixture-client-secret' not in audit and 'desktop-google-setup' in audit


def test_async_login_deduplicates_and_checks_identity_before_saving(setup):
    c = setup.control; import_client(c)
    key = str(uuid4())
    payload = {'id': key, 'operation': 'connect', 'data': {'account': 'personal', 'scopes': ['calendar.read', 'gmail.read'], 'replace': False, 'expected_revision': 'missing'}}
    first = c.execute(payload)
    assert c.execute(payload) == first
    assert first['job']['state'] == 'waiting' and not setup.vault.records
    with pytest.raises(RuntimeError, match='current Google sign-in'):
        start(c, 'work')
    setup.gate.set()
    connected = wait_job(c)
    assert connected['job']['state'] == 'connected', connected
    assert connected['accounts'][0]['email'] == 'personal@example.test'
    assert 'calendar.write' not in connected['accounts'][0]['services']
    assert len(setup.calls) == 1
    assert 'fixture-refresh-token' not in json.dumps(connected)
    assert 'fixture-access-token' not in json.dumps(connected)


def test_cancel_and_shutdown_prevent_late_credentials_from_being_saved(setup):
    c = setup.control; import_client(c)
    started = start(c)
    cancelled = act(c, 'cancel', {'attempt_id': started['job']['id']})
    assert cancelled['job']['state'] == 'cancelling'
    setup.gate.set()
    assert wait_job(c)['job']['state'] == 'cancelled'
    assert not setup.vault.records
    setup.gate.clear(); start(c)
    # A callback arriving after the dashboard closes must not reconnect an account.
    c.close(); setup.gate.set(); c.thread.join(2)
    assert not setup.vault.records


def test_multiple_accounts_default_disconnect_and_reconnect_preserve_other_accounts(setup):
    c = setup.control; import_client(c); setup.gate.set()
    start(c); personal = wait_job(c)['accounts'][0]
    setup.email['value'] = 'work@example.test'
    start(c, 'work'); rows = wait_job(c)['accounts']
    work = next(row for row in rows if row['account'] == 'work')
    assert len(rows) == 2
    assert act(c, 'default', {'account': 'work', 'expected_revision': work['revision']})['default_account'] == 'work'
    # Choosing a different email during Reconnect cannot replace the saved identity.
    setup.email['value'] = 'wrong@example.test'
    start(c, replace=True, expected_revision=personal['revision'])
    assert wait_job(c)['job']['state'] == 'failed'
    assert setup.vault.get('personal')['email'] == personal['email']
    result = act(c, 'disconnect', {'account': 'work', 'expected_revision': work['revision']})
    assert result['default_account'] == 'personal' and len(result['accounts']) == 1
    with pytest.raises(ValueError, match='changed'):
        act(c, 'disconnect', {'account': 'work', 'expected_revision': work['revision']})


def test_account_changed_during_sign_in_cannot_be_overwritten(setup):
    c = setup.control; import_client(c); start(c)
    setup.vault.set('personal', {'email': 'new@example.test', 'calendar_ids': ['primary'], 'credentials': {'scopes': []}})
    setup.gate.set()
    assert wait_job(c)['job']['state'] == 'failed'
    assert setup.vault.get('personal')['email'] == 'new@example.test'


def test_browser_oauth_validates_state_and_exchanges_only_the_accepted_code():
    requests = []; response_codes = []; cancel = threading.Event()
    class Flow:
        credentials = object()
        redirect_uri = None
        def authorization_url(self, **kwargs): return 'https://accounts.google.com/o/oauth2/auth?state=fixture-state', 'fixture-state'
        def fetch_token(self, **kwargs): requests.append(kwargs)
    flow = Flow()
    def callback():
        parts = urlsplit(flow.redirect_uri)
        for state in ('wrong-state', 'fixture-state'):
            conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=3)
            conn.request('GET', '/?state=' + state + '&code=fixture-code')
            response = conn.getresponse(); response.read(); response_codes.append(response.status); conn.close()
    thread = threading.Thread(target=callback)
    def open_browser(*args, **kwargs): thread.start(); return True
    browser = BrowserGoogleFlow({}, (), cancel, flow=flow, open_browser=open_browser)
    assert browser.run_local_server(host='127.0.0.1', port=0, timeout_seconds=5) is flow.credentials
    thread.join(2)
    assert response_codes == [400, 200]
    assert requests == [{'code': 'fixture-code', 'timeout': 20}]


def test_browser_oauth_cancels_while_waiting_without_a_token_exchange():
    cancel = threading.Event()
    class Flow:
        def authorization_url(self, **kwargs): return 'https://accounts.google.com/o/oauth2/auth', 'state'
        def fetch_token(self, **kwargs): pytest.fail('Cancelled flow exchanged a token')
    def open_browser(*args, **kwargs): cancel.set(); return True
    browser = BrowserGoogleFlow({}, (), cancel, flow=Flow(), open_browser=open_browser)
    with pytest.raises(InterruptedError): browser.run_local_server(host='127.0.0.1', port=0, timeout_seconds=5)


def test_official_google_library_issues_pkce_and_a_random_loopback_callback():
    from urllib.parse import parse_qs
    from hanni.tools.google_identity import scopes_for
    cancel = threading.Event(); urls = []
    def open_browser(url, **kwargs): urls.append(url); cancel.set(); return True
    browser = BrowserGoogleFlow(CLIENT, scopes_for(['calendar.read']), cancel, open_browser=open_browser)
    with pytest.raises(InterruptedError):
        browser.run_local_server(host='127.0.0.1', port=0, timeout_seconds=5, access_type='offline', prompt='consent select_account')
    query = parse_qs(urlsplit(urls[0]).query)
    assert query['code_challenge_method'] == ['S256']
    assert len(query['code_challenge'][0]) >= 43 and query['state'][0]
    assert query['redirect_uri'][0].startswith('http://127.0.0.1:')
    assert query['access_type'] == ['offline']


def test_google_setup_http_requires_token_and_same_origin(service, setup):
    service.google_accounts.close(); service.google_accounts = setup.control
    conn = http.client.HTTPConnection('127.0.0.1', service.server_port)
    origin = f'http://127.0.0.1:{service.server_port}'
    body = {'id': str(uuid4()), 'operation': 'import_client', 'data': {'document': json.dumps(CLIENT), 'expected_revision': 'missing'}}
    def send(method, token, origin_value=origin):
        conn.request(method, '/api/google/accounts', body=json.dumps(body) if method == 'POST' else None,
                     headers={'Content-Type': 'application/json', 'Origin': origin_value, 'X-Hanni-Token': token})
        response = conn.getresponse(); raw = response.read(); return response.status, json.loads(raw)
    try:
        assert send('GET', '')[0] == 403
        assert send('POST', service.chat.token, 'https://foreign.example')[0] == 403
        assert send('POST', service.chat.token)[0] == 200
        assert send('GET', service.chat.token)[1]['client']['ready']
    finally: conn.close()


def test_disconnect_clears_default_preferences_in_windows_vault():
    from hanni.tools.google_identity import scopes_for
    data = {('personal'): json.dumps({'email': 'one@example.test', 'credentials': {'scopes': list(scopes_for())}}),
            '__settings__': json.dumps({'default_google_account': 'personal', 'calendar': 'personal', 'gmail': 'work'})}
    class Backend:
        def get_password(self, service, key): return data.get(key)
        def set_password(self, service, key, value): data[key] = value
        def delete_password(self, service, key): data.pop(key)
    vault = WindowsTokenVault.__new__(WindowsTokenVault); vault.backend = Backend()
    vault.delete('personal')
    assert vault.get('personal') is None
    assert vault.preferences() == {'gmail': 'work'}


@pytest.mark.parametrize('entrypoint', ['cli', 'settings'])
def test_real_library_token_exchange_accepts_equivalent_google_identity_grants(tmp_path, monkeypatch, setup, entrypoint):
    """Real callback, PKCE, oauthlib parsing and account save; Google alone is faked."""
    import requests
    from requests_oauthlib import OAuth2Session
    from urllib.parse import parse_qs, urlencode
    import webbrowser

    client = tmp_path / 'client.json'
    client.write_text(json.dumps(CLIENT))
    requested = scopes_for(['calendar.read', 'gmail.read'])
    granted = [scope if scope != IDENTITY_SCOPE else 'email' for scope in requested] + ['openid']
    calls, callbacks, statuses = [], [], []
    response = requests.Response()
    response.status_code = 200
    response.encoding = 'utf-8'
    response._content = json.dumps({'access_token': 'fixture-access', 'refresh_token': 'fixture-refresh',
        'id_token': 'fixture-redundant-jwt', 'token_type': 'Bearer', 'expires_in': 3600,
        'scope': ' '.join(granted)}).encode()
    response.request = requests.Request('POST', 'https://oauth2.googleapis.com/token').prepare()
    def exchange(self, **kwargs):
        calls.append(kwargs)
        assert kwargs['url'] == 'https://oauth2.googleapis.com/token' and kwargs['timeout'] == 20
        assert kwargs['data']['code_verifier']
        return response
    monkeypatch.setattr(OAuth2Session, 'request', exchange)
    def open_browser(url, **kwargs):
        query = parse_qs(urlsplit(url).query)
        target = urlsplit(query['redirect_uri'][0])
        def callback():
            connection = http.client.HTTPConnection(target.hostname, target.port, timeout=3)
            try:
                connection.request('GET', '/?' + urlencode({'state': query['state'][0], 'code': 'fixture-code'}))
                result = connection.getresponse(); result.read(); statuses.append(result.status)
            finally: connection.close()
        thread = threading.Thread(target=callback); callbacks.append(thread); thread.start()
        return True
    monkeypatch.setattr(webbrowser, 'open', open_browser)
    vault = Vault(); phases = []
    try:
        if entrypoint == 'cli':
            result = google_auth.connect('personal', None, client, vault=vault, scopes=['calendar.read', 'gmail.read'],
                transport=lambda *_: {'email': 'personal@example.test'}, progress=phases.append)
            assert result['connected'] and result['gmail'] and result['calendar']
            assert phases == ['verifying', 'identity', 'saving']
        else:
            c = setup.control; c.flow_factory = None; vault = setup.vault
            import_client(c); start(c); result = wait_job(c)
            assert result['job']['state'] == 'connected', result['job']
            assert result['accounts'][0]['email'] == 'personal@example.test'
    finally:
        for thread in callbacks: thread.join(3)
    assert statuses == [200] and len(calls) == 1
    saved = vault.get('personal')['credentials']
    assert set(saved['scopes']) == set(requested) and 'id_token' not in saved
    assert not any(secret in json.dumps(result) for secret in ('fixture-access', 'fixture-refresh'))


@pytest.mark.parametrize('grants', [
    [IDENTITY_SCOPE],  # Partial consent must not become a full service grant.
    [*scopes_for(['calendar.read', 'gmail.read']), PREFIX + 'calendar.events'],
    [*scopes_for(['calendar.read', 'gmail.read']), PREFIX + 'userinfo.profile'],
])
def test_real_library_rejects_missing_or_extra_permissions_before_saving(grants):
    import requests
    browser = BrowserGoogleFlow(CLIENT, scopes_for(['calendar.read', 'gmail.read']), threading.Event())
    response = requests.Response(); response._content = json.dumps({'scope': ' '.join(grants)}).encode()
    with pytest.raises(GoogleAccessError) as error: browser._token_response(response)
    assert error.value.code == 'scope_mismatch'


def test_reconnect_can_upgrade_a_read_scope_without_requesting_redundant_grants(setup):
    c = setup.control; import_client(c); setup.gate.set()
    start(c); personal = wait_job(c)['accounts'][0]
    captured = []
    original = c.flow_factory
    def factory(config, scopes): captured.extend(scopes); return original(config, scopes)
    c.flow_factory = factory
    start(c, replace=True, expected_revision=personal['revision'], scopes=['calendar.write'])
    result = wait_job(c)
    assert result['job']['state'] == 'connected'
    assert 'calendar.write' in result['accounts'][0]['services']
    assert PREFIX + 'calendar.events.readonly' not in captured


@pytest.mark.parametrize('failure,code,phrase', [
    ('storage', 'credential_storage', 'Windows Credential Manager'),
    ('identity', 'identity_unavailable', 'verify the account email'),
    ('changed', 'account_changed', 'changed during sign-in'),
])
def test_post_consent_failure_is_actionable_and_never_exposes_secrets(setup, failure, code, phrase, monkeypatch):
    c = setup.control; import_client(c)
    previous = dict(setup.vault.records)
    if failure == 'storage':
        monkeypatch.setattr(setup.vault, 'set', lambda *_: (_ for _ in ()).throw(RuntimeError('fixture-private-token')))
    elif failure == 'identity':
        c.transport = lambda *_: {}
    started = start(c)
    if failure == 'changed':
        setup.vault.set('personal', {'email': 'other@example.test', 'credentials': {'scopes': []}})
    setup.gate.set()
    result = wait_job(c)
    assert result['job']['state'] == 'failed' and result['job']['error_code'] == code
    assert phrase in result['job']['message']
    assert 'fixture-private-token' not in json.dumps(result)
    if failure != 'changed': assert setup.vault.records == previous


@pytest.mark.parametrize('error,code', [
    (TimeoutError('fixture-secret'), 'sign_in_timeout'),
    (RuntimeError('fixture-secret'), 'sign_in_failed'),
])
def test_sign_in_failure_classification_never_displays_provider_exception_text(error, code):
    result = google_auth._flow_error(error)
    assert result.code == code and 'fixture-secret' not in str(result)


def test_silent_credential_storage_failure_is_not_reported_connected(tmp_path):
    client = tmp_path / 'client.json'; client.write_text(json.dumps(CLIENT))
    class Credentials:
        refresh_token = 'fixture-refresh'
        granted_scopes = scopes_for()
        def to_json(self):
            return json.dumps({'token_uri': 'https://oauth2.googleapis.com/token', 'scopes': list(self.granted_scopes)})
    class Flow:
        def run_local_server(self, **kwargs): return Credentials()
    class SilentVault(Vault):
        def set(self, *args): pass
    with pytest.raises(GoogleAccessError) as error:
        google_auth.connect('personal', None, client, vault=SilentVault(), flow_factory=lambda *_: Flow(),
            transport=lambda *_: {'email': 'personal@example.test'})
    assert error.value.code == 'credential_storage'


@pytest.mark.parametrize('failure,code', [
    ('invalid_client', 'invalid_client'), ('invalid_grant', 'invalid_grant'),
    ('connection', 'network_error'), ('timeout', 'network_error'),
])
def test_failed_reconnect_retains_existing_credentials_and_explains_the_failure(setup, failure, code):
    from oauthlib.oauth2 import InvalidClientError, InvalidGrantError
    from requests.exceptions import ConnectionError, ReadTimeout
    c = setup.control; import_client(c); setup.gate.set()
    start(c); personal = wait_job(c)['accounts'][0]
    previous = dict(setup.vault.get('personal'))
    errors = {'invalid_client': InvalidClientError, 'invalid_grant': InvalidGrantError,
              'connection': ConnectionError, 'timeout': ReadTimeout}
    class Flow:
        def run_local_server(self, **kwargs): raise errors[failure]('fixture-private-token')
    c.flow_factory = lambda *_: Flow()
    start(c, replace=True, expected_revision=personal['revision'])
    result = wait_job(c)
    assert result['job']['state'] == 'failed' and result['job']['error_code'] == code
    assert setup.vault.get('personal') == previous
    assert 'fixture-private-token' not in json.dumps(result)
