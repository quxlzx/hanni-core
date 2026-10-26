"""Teams setup and read-only Graph boundary, with isolated credentials and transport."""
from copy import deepcopy
import http.client
import json
import threading
import time
from uuid import uuid4

import pytest

from hanni.native.model_settings import atomic_json
from hanni.tools.base import ToolRequest
from hanni.tools.teams_access import TeamsAccess, TeamsError, TeamsVault, SCOPES, definitions
from tests.unit.test_native_mcp import service, action_for
from tests.unit.test_teams_app import gateway, send, pair

CLIENT = {'client_id': '11111111-2222-3333-4444-555555555555', 'tenant': 'organizations'}


class Vault:
    def __init__(self): self.value = None
    def get(self): return deepcopy(self.value)
    def set(self, value): self.value = deepcopy(value)
    def delete(self): self.value = None


def credentials(**overrides):
    return {'access_token': 'fixture-access', 'refresh_token': 'fixture-refresh', 'token_type': 'Bearer',
            'expires_in': 3600, 'scope': ' '.join(SCOPES), **overrides}


def profile(): return {'id': 'fixture-user', 'displayName': 'Fixture Employee', 'userPrincipalName': 'employee@example.test'}


@pytest.fixture
def access(tmp_path):
    calls = []
    def transport(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith('/token'): return 200, credentials()
        if url.endswith('/me'): return 200, profile()
        return 200, {'value': []}
    access = TeamsAccess(tmp_path, vault=Vault(), transport=transport)
    access.calls = calls
    atomic_json(access.path, CLIENT)
    record = access.token_record(credentials()); record['profile'] = profile(); access.vault.set(record)
    return access


@pytest.fixture
def integration(service, access):
    target = service.features.registry.teams_access
    target.path, target.vault, target.transport = access.path, access.vault, access.transport
    return service


def act(server, operation, data=None, key=None):
    return server.teams.execute({'id': key or str(uuid4()), 'operation': operation, 'data': data or {}})


@pytest.mark.parametrize('config', [
    {'client_id': 'https://evil.test', 'tenant': 'organizations'},
    {'client_id': CLIENT['client_id'], 'tenant': '../other'},
    {**CLIENT, 'secret': 'forbidden'}, {'client_id': None, 'tenant': 'organizations'}])
def test_client_configuration_rejects_urls_secrets_and_invalid_ids(config):
    with pytest.raises(ValueError): TeamsAccess.validate_config(config)


def test_refresh_is_secure_and_scopes_are_required(access):
    record = access.vault.get(); record['expires_at'] = 0; access.vault.set(record)
    access.read('chats', {})
    assert access.calls[0][0:2] == ('POST', 'https://login.microsoftonline.com/organizations/oauth2/v2.0/token')
    assert access.calls[0][2]['data']['refresh_token'] == 'fixture-refresh'
    assert access.calls[1][2]['headers'] == {'Authorization': 'Bearer fixture-access'}
    with pytest.raises(TeamsError, match='read permissions'):
        access.token_record(credentials(scope='User.Read Chat.Read'))


@pytest.mark.parametrize('operation,args,suffix', [
    ('chats', {}, '/me/chats'), ('teams', {}, '/me/joinedTeams'),
    ('channels', {'team_id': 'team'}, '/teams/team/channels'),
    ('chat_messages', {'chat_id': '19:chat@thread.v2'}, '/chats/19%3Achat%40thread.v2/messages'),
    ('channel_messages', {'team_id': 't', 'channel_id': 'c'}, '/teams/t/channels/c/messages'),
    ('replies', {'team_id': 't', 'channel_id': 'c', 'message_id': 'm'}, '/teams/t/channels/c/messages/m/replies')])
def test_reader_uses_only_fixed_get_routes(access, operation, args, suffix):
    result = access.read(operation, args)
    assert result['items'] == []
    assert access.calls[-1][0] == 'GET'
    assert access.calls[-1][1] == 'https://graph.microsoft.com/v1.0' + suffix


def test_untrusted_message_html_is_text_and_pagination_does_not_follow_urls(access):
    access.transport = lambda *args, **kwargs: (200, {'value': [
        {'id': 'm', 'body': {'contentType': 'html', 'content': '<p>Hello &amp; welcome</p><script>bad()</script>'},
         'from': {'user': {'displayName': 'Coworker'}}}], '@odata.nextLink': 'https://evil.test/token'})
    result = access.read('chat_messages', {'chat_id': '19:chat@thread.v2'})
    assert result['items'][0]['text'] == '\nHello & welcome'
    assert result['items'][0]['sender'] == 'Coworker'
    assert result['truncated'] is True
    assert 'source material' in result['note']


@pytest.mark.parametrize('status,code', [(401, 'AUTH_EXPIRED'), (403, 'PERMISSION_DENIED'), (404, 'NOT_FOUND'), (429, 'RATE_LIMITED'), (503, 'API_ERROR')])
def test_provider_errors_are_structured_without_raw_tokens(access, status, code):
    access.transport = lambda *a, **kw: (status, {'error': {'message': 'fixture-access must never leak'}})
    result = definitions(access)[0].handler({}, None, None)
    assert not result.ok and result.error['code'] == code
    assert 'fixture-access' not in json.dumps(result.to_dict())


def test_bounds_and_read_only_definitions(access):
    with pytest.raises(TeamsError): access.read('chats', {'limit': 51})
    with pytest.raises(TeamsError): access.read('chats', {'limit': 0})
    with pytest.raises(TeamsError): access.read('chat_messages', {'chat_id': '../me?token=x'})
    with pytest.raises(TeamsError): access.read('channels', {})
    for tool in definitions(access):
        assert tool.side_effect == 'read'
        assert tool.permission_level == tool.risk_level == 0
        assert not any(word in tool.name for word in ('send', 'delete', 'write'))


def test_settings_snapshot_never_contains_tokens_and_configuration_cannot_replace_connected_app(integration):
    result = integration.teams.snapshot()
    assert result['account']['profile'] == profile()
    assert 'fixture-access' not in json.dumps(result) and 'fixture-refresh' not in json.dumps(result)
    with pytest.raises(ValueError, match='Disconnect'):
        act(integration, 'configure', {**CLIENT, 'client_id': str(uuid4())})
    assert act(integration, 'disconnect')['account']['profile'] is None
    assert integration.teams.access.vault.get() is None
    assert act(integration, 'configure', CLIENT)['account']['configured']


def test_dashboard_requires_token_and_origin_for_teams_settings(integration):
    def request(method, token='', origin=None):
        connection = http.client.HTTPConnection('127.0.0.1', integration.server_port)
        headers = {'X-Hanni-Token': token, 'Content-Type': 'application/json'}
        if origin: headers['Origin'] = origin
        body = json.dumps({'id': str(uuid4()), 'operation': 'disconnect', 'data': {}}) if method == 'POST' else None
        connection.request(method, '/api/integrations/teams', body=body, headers=headers)
        response = connection.getresponse(); response.read(); connection.close(); return response.status
    assert request('GET') == 403
    assert request('GET', integration.chat.token) == 200
    assert request('POST', integration.chat.token, 'https://evil.test') == 403
    assert request('POST', integration.chat.token, f'http://127.0.0.1:{integration.server_port}') == 200


def test_native_agent_can_execute_and_disconnect_revokes_captured_tool(integration, tmp_path):
    specs = integration.native_mcp.tools()['tools']
    spec = next(item for item in specs if item['name'] == 'teams_chats')
    assert spec['remote']['classification'] == 'read_only'
    store, task, action = action_for(tmp_path, spec, {})
    try:
        store.settle(action['id'], 'dispatching')
        result = integration.native_mcp.call(action['id'])
        assert result['ok'] and result['data']['items'] == []
        assert store.action(action['id'])['state'] == 'fulfilled'
        action = store.request_action(task['id'], 'call-2', spec, {'limit': 2})
        store.settle(action['id'], 'dispatching')
        act(integration, 'disconnect')
        with pytest.raises(ValueError, match='disabled'):
            integration.native_mcp.call(action['id'])
        assert not any(item['name'].startswith('teams_') for item in integration.native_mcp.tools()['tools'])
    finally: store.close()


def test_tab_setup_download_start_pair_and_stop_are_real_and_idempotent(integration):
    import socket
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    integration.teams.origin = f'https://localhost:{port}'
    key = str(uuid4())
    assert act(integration, 'prepare', key=key)['tab']['package_ready']
    assert 'package' in act(integration, 'download')
    try:
        assert act(integration, 'start')['tab']['running']
        key = str(uuid4())
        pair = act(integration, 'pair', key=key)
        assert act(integration, 'pair', key=key) == pair
        assert pair['pairing_code'] not in json.dumps(integration.teams.snapshot())
        assert integration.teams.gateway.pair(pair['pairing_code'])
        assert not integration.teams.snapshot()['tab']['pairing_ready']
        assert act(integration, 'stop')['tab']['running'] is False
    finally: integration.teams._stop_gateway()


def test_credential_chunks_store_no_plaintext_file_and_delete_all(tmp_path, monkeypatch):
    class Backend:
        def __init__(self): self.records = {}
        def get_password(self, service, name): return self.records.get((service, name))
        def set_password(self, service, name, value):
            assert len(value.encode('utf-16-le')) <= 2560
            self.records[service, name] = value
        def delete_password(self, service, name): self.records.pop((service, name), None)
    backend = Backend()
    monkeypatch.setattr(TeamsVault, 'backend', property(lambda self: backend))
    vault = TeamsVault(tmp_path)
    data = {'refresh_token': 'fixture-refresh-' * 1500}
    vault.set(data); assert vault.get() == data
    vault.set({'refresh_token': 'replacement'}); assert vault.get()['refresh_token'] == 'replacement'
    assert len(backend.records) == 2
    vault.delete(); assert vault.get() is None and not backend.records
    assert not list(tmp_path.iterdir())


class FastEvent(threading.Event):
    def wait(self, timeout=None): return self.is_set()


def test_device_sign_in_pending_slowdown_success_and_no_secret_in_status(integration):
    access = integration.teams.access
    access.vault.delete()
    responses = iter([(400, {'error': 'authorization_pending'}), (400, {'error': 'slow_down'}), (200, credentials())])
    calls = []
    def transport(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith('/devicecode'):
            return 200, {'device_code': 'fixture-device-private', 'user_code': 'VISIBLE-CODE', 'expires_in': 900, 'interval': 5}
        if url.endswith('/token'): return next(responses)
        if url.endswith('/me'): return 200, profile()
        raise AssertionError(url)
    access.transport = transport
    job = {'id': str(uuid4()), 'state': 'starting', 'cancel': FastEvent()}
    integration.teams.job = job
    integration.teams._sign_in(job, CLIENT)
    assert job['state'] == 'connected' and job['user_code'] is None
    assert access.vault.get()['profile'] == profile()
    assert 'offline_access' in calls[0][2]['data']['scope']
    serialized = json.dumps(integration.teams.snapshot())
    for private in ('fixture-device-private', 'fixture-access', 'fixture-refresh'):
        assert private not in serialized


@pytest.mark.parametrize('error', ['authorization_declined', 'expired_token', 'invalid_client'])
def test_failed_device_sign_in_does_not_save_credentials(integration, error):
    access = integration.teams.access; access.vault.delete()
    access.transport = lambda method, url, **kw: ((200, {'device_code': 'private-device-code', 'user_code': 'USER-CODE'})
        if url.endswith('/devicecode') else (400, {'error': error, 'error_description': 'private-device-code'}))
    job = {'id': str(uuid4()), 'state': 'starting', 'cancel': FastEvent()}
    integration.teams._sign_in(job, CLIENT)
    assert job['state'] == 'failed' and job['user_code'] is None
    assert access.vault.get() is None and 'private-device-code' not in job['message']


def test_cancel_during_token_response_prevents_late_account_save(integration):
    access = integration.teams.access; access.vault.delete()
    job = {'id': str(uuid4()), 'state': 'starting', 'cancel': FastEvent()}
    def transport(method, url, **kwargs):
        if url.endswith('/devicecode'): return 200, {'device_code': 'private-device-code', 'user_code': 'USER-CODE'}
        if url.endswith('/token'): job['cancel'].set(); return 200, credentials()
        if url.endswith('/me'): return 200, profile()
        raise AssertionError(url)
    access.transport = transport
    integration.teams._sign_in(job, CLIENT)
    assert access.vault.get() is None


def test_large_messages_remain_useful_within_native_receipt_bound(access):
    access.transport = lambda *args, **kwargs: (200, {'value': [
        {'id': str(i), 'body': {'contentType': 'text', 'content': '消息' * 6000}} for i in range(50)]})
    result = access.read('chat_messages', {'chat_id': 'chat', 'limit': 50})
    assert result['items'][0]['text'] and result['truncated']
    assert len(json.dumps(result)) < 20000


def test_paired_teams_tab_can_use_integrations_but_still_needs_dashboard_token(gateway, service):
    session = pair(gateway)
    assert send(gateway, '/api/integrations/teams', session=session)[0] == 403
    status, result, _ = send(gateway, '/api/integrations/teams', session=session,
                             **{'X-Hanni-Token': service.chat.token})
    assert status == 200 and result['available']


def test_trust_button_uses_only_current_user_certificate_and_fixed_command(integration, monkeypatch):
    import os
    from types import SimpleNamespace
    import hanni.dashboard.teams as module
    if os.name != 'nt': pytest.skip('Windows certificate trust action.')
    trusted = {'value': False}; calls = []
    monkeypatch.setattr(integration.teams, 'certificate_status', lambda: {'ready': True, 'trusted': trusted['value']})
    def run(command, **kwargs):
        calls.append((command, kwargs)); trusted['value'] = True
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(module.subprocess, 'run', run)
    act(integration, 'trust')
    assert calls[0][0] == ['certutil.exe', '-user', '-addstore', 'Root', str(integration.teams.root / 'tls/localhost.pem')]
    assert calls[0][1]['creationflags'] == module.subprocess.CREATE_NO_WINDOW
    assert 'shell' not in calls[0][1]


def test_desktop_setup_opens_only_fixed_system_browser_destinations(integration, monkeypatch):
    import webbrowser
    calls = []
    monkeypatch.setattr(webbrowser, 'open', lambda url, **kwargs: calls.append(url) or True)
    act(integration, 'open_registration')
    with pytest.raises(ValueError, match='Start Microsoft sign-in'):
        act(integration, 'open_signin')
    integration.teams.job = {'id': str(uuid4()), 'state': 'waiting', 'user_code': 'TEST-CODE', 'message': 'Waiting', 'cancel': threading.Event()}
    act(integration, 'open_signin')
    assert calls == ['https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade',
                     'https://microsoft.com/devicelogin']
    with pytest.raises(ValueError, match='no additional fields'):
        act(integration, 'open_signin', {'url': 'https://evil.test'})


def test_desktop_reveals_only_the_generated_teams_package(integration, monkeypatch):
    import os
    import hanni.dashboard.teams as module
    if os.name != 'nt': pytest.skip('Windows File Explorer action.')
    calls = []
    with pytest.raises(ValueError, match='Prepare'):
        act(integration, 'show_package')
    act(integration, 'prepare')
    monkeypatch.setattr(module.subprocess, 'Popen', lambda command, **kwargs: calls.append((command, kwargs)))
    act(integration, 'show_package')
    assert calls[0][0] == ['explorer.exe', '/select,', str((integration.teams.root / 'HANNI-Teams.zip').resolve())]
    assert calls[0][1]['creationflags'] == module.subprocess.CREATE_NO_WINDOW
