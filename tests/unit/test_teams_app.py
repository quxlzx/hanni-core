"""Real TLS, pairing, token/origin gates, proxied UI actions and Teams package."""
from io import BytesIO
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import ssl
import threading
import time
from uuid import uuid4
from zipfile import ZipFile

import pytest

pytest.importorskip('cryptography', minversion='46', reason='Install .[teams] to test the optional TLS gateway.')

from hanni.teams.server import TeamsServer, validate_origin, validate_upstream
from tests.unit.test_native_mcp import service

ROOT = Path(__file__).resolve().parents[2]
module_spec = importlib.util.spec_from_file_location('hanni_build_teams', ROOT / 'scripts/build_teams.py')
builder = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(builder)


@pytest.fixture
def gateway(service, tmp_path):
    cert, key = builder.local_certificate(tmp_path / 'tls')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    app = TeamsServer(f'https://localhost:{port}', f'http://127.0.0.1:{service.server_port}', cert, key)
    app.test_context = ssl.create_default_context(cafile=cert)
    thread = threading.Thread(target=app.serve_forever, daemon=True)
    thread.start()
    try:
        yield app
    finally:
        app.shutdown(); app.server_close(); thread.join(3)


def send(gateway, path, body=None, session=None, **extra):
    client = http.client.HTTPSConnection('localhost', gateway.server_port, context=gateway.test_context, timeout=8)
    headers = {'Origin': gateway.origin, 'Content-Type': 'application/json', **extra}
    if session: headers['X-Hanni-Teams-Session'] = session
    try:
        client.request('GET' if body is None else 'POST', path,
                       body=json.dumps(body) if body is not None else None, headers=headers)
        response = client.getresponse()
        raw = response.read()
        data = json.loads(raw) if 'application/json' in response.getheader('Content-Type', '') else raw
        return response.status, data, dict(response.getheaders())
    finally:
        client.close()


def pair(gateway):
    status, data, _ = send(gateway, '/api/teams/pair', {'code': gateway.pairing_code})
    assert status == 200, data
    return data['session']


@pytest.mark.parametrize('origin', ['http://localhost:8313', 'https://0.0.0.0:8313',
                                   'https://public.example:8313', 'https://localhost:8313/path',
                                   'https://@localhost:8313', 'https://localhost:8313/#secret'])
def test_local_hosting_refuses_public_insecure_or_credential_urls(origin):
    with pytest.raises(ValueError): validate_origin(origin)


@pytest.mark.parametrize('upstream', ['https://127.0.0.1:8311', 'http://other.example:8311',
                                     'http://localhost:8311/path', 'http://user@localhost:8311'])
def test_upstream_stays_on_exact_loopback_origin(upstream):
    with pytest.raises(ValueError): validate_upstream(upstream)


def test_unpaired_tab_cannot_read_chat_or_steal_dashboard_token(gateway):
    status, html, headers = send(gateway, '/?host=teams')
    assert status == 200 and b'app-root' in html
    assert 'https://*.cloud.microsoft' in headers['Content-Security-Policy']
    assert send(gateway, '/api/chat')[0] == 401
    assert send(gateway, '/api/workspace')[0] == 401
    assert send(gateway, '/api/chat', {'id': str(uuid4()), 'message': 'blocked'})[0] == 401
    assert 'Access-Control-Allow-Origin' not in headers


def test_pairing_requires_same_origin_is_one_use_and_logout_revokes(gateway):
    code = gateway.pairing_code
    assert send(gateway, '/api/teams/pair', {'code': code}, Origin='https://teams.microsoft.com')[0] == 403
    assert send(gateway, '/api/teams/pair', {'code': 'bad'})[0] == 400
    session = pair(gateway)
    assert send(gateway, '/api/teams/session', session=session)[0] == 200
    assert send(gateway, '/api/teams/pair', {'code': code})[0] == 400
    assert send(gateway, '/api/teams/logout', {}, session=session)[0] == 200
    assert send(gateway, '/api/chat', session=session)[0] == 401


def test_pairing_and_sessions_expire_and_attempts_are_bounded(gateway):
    gateway.pairing_expires = time.monotonic() - 1
    assert send(gateway, '/api/teams/pair', {'code': gateway.pairing_code})[0] == 400
    gateway.pairing_expires = time.monotonic() + 60
    gateway.failed_pairings = 10
    assert send(gateway, '/api/teams/pair', {'code': gateway.pairing_code})[0] == 400
    gateway.failed_pairings = 0
    session = pair(gateway)
    for key in gateway.sessions: gateway.sessions[key] = 0
    assert send(gateway, '/api/chat', session=session)[0] == 401


def test_proxy_retains_upstream_token_checks_and_saves_real_access_settings(gateway, service, tmp_path):
    service.chat.native_mode = True
    session = pair(gateway)
    status, chat, _ = send(gateway, '/api/chat', session=session)
    assert status == 200 and chat['token'] == service.chat.token
    assert send(gateway, '/api/tool-access', session=session)[0] == 403
    headers = {'X-Hanni-Token': chat['token']}
    status, settings, _ = send(gateway, '/api/tool-access', session=session, **headers)
    assert status == 200 and settings['available']
    body = {'id': str(uuid4()), 'mode': 'read_only', 'expected_revision': settings['revision']}
    assert send(gateway, '/api/tool-access', body, session=session, **headers)[0] == 200
    assert json.loads((tmp_path / 'tool-access.json').read_text())['mode'] == 'read_only'
    assert send(gateway, '/api/tool-access', body, session=session, Origin='https://foreign.example', **headers)[0] == 403
    assert send(gateway, '/api/chat', session=session, Host='foreign.example')[0] == 403
    assert send(gateway, '/api/chat', session=session, **{'Sec-Fetch-Site': 'cross-site'})[0] == 403
    assert send(gateway, '/api/native-mcp/tools', session=session)[0] == 404
    assert send(gateway, '/api/sandbox/v1/chat/completions', {}, session=session)[0] == 404


def test_real_chat_attachment_upload_and_download_through_gateway(gateway, service):
    import base64
    service.chat.native_mode = True
    session = pair(gateway)
    headers = {'X-Hanni-Token': service.chat.token}
    payload = {'operation': 'add', 'id': str(uuid4()), 'conversation': 'default', 'name': 'notes.txt',
               'data': base64.b64encode(b'Teams document content').decode()}
    status, uploaded, _ = send(gateway, '/api/chat/files', payload, session=session, **headers)
    assert status == 201, uploaded
    # Unsent files remain protected but can be downloaded with the conversation token.
    status, raw, response_headers = send(gateway, '/api/chat/file?id=' + uploaded['id'] + '&conversation=default', session=session, **headers)
    assert status == 200, raw
    assert raw == b'Teams document content'
    assert 'notes.txt' in response_headers['Content-Disposition']


def test_app_package_contains_valid_personal_manifest_and_brand_icons(tmp_path):
    from PIL import Image
    path = tmp_path / 'HANNI.zip'
    manifest = builder.build_package('https://localhost:8313', path)
    with ZipFile(path) as archive:
        assert set(archive.namelist()) == {'manifest.json', 'color.png', 'outline.png'}
        assert manifest == json.loads(archive.read('manifest.json'))
        assert manifest['staticTabs'][0]['scopes'] == ['personal']
        assert manifest['validDomains'] == ['localhost']
        assert 'webApplicationInfo' not in manifest and 'bots' not in manifest
        assert Image.open(BytesIO(archive.read('color.png'))).size == (192, 192)
        outline = Image.open(BytesIO(archive.read('outline.png')))
        assert outline.size == (32, 32)
        assert outline.getchannel('A').getextrema() == (0, 255)
        assert outline.getchannel('R').getextrema() == (255, 255)
        assert outline.getchannel('G').getextrema() == (255, 255)
        assert outline.getchannel('B').getextrema() == (255, 255)
