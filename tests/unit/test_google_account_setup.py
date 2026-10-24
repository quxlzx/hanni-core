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
