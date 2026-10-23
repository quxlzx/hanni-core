"""Real HTTP/token/permission gates for model-routing preferences."""
from __future__ import annotations
import http.client
import json
import threading
from types import SimpleNamespace
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.core.shutdown import LocalStopControls
from hanni.dashboard.server import DashboardServer
from hanni.models.adaptive import current
from hanni.reliability.execution import close_service
from tests.helpers import REPO_ROOT

@pytest.fixture
def routing_server(tmp_path):
    config = load_config(REPO_ROOT / 'config', data_dir=tmp_path, env={})
    server = DashboardServer(0, SimpleNamespace(config=config, snapshot=lambda: {}), shutdown_event=threading.Event())
    server.model_routing.local_probe = lambda row: {'status': 'unreachable'}
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)
        server.chat.close()
        server.chat.db.close()
        close_service(tmp_path)

def request(server, *, body=None, token=None, origin=None):
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
    headers = {'X-Hanni-Token': token} if token is not None else {}
    if origin is not None:
        headers['Origin'] = origin
    if body is not None:
        headers['Content-Type'] = 'application/json'
    try:
        connection.request('POST' if body is not None else 'GET', '/api/model-routing', body=json.dumps(body) if body is not None else None, headers=headers)
        response = connection.getresponse()
        return (response.status, json.loads(response.read()))
    finally:
        connection.close()

def body(policy='fast'):
    return {'id': str(uuid4()), 'policy': policy, 'manual_endpoint_id': None, 'confirmed': False}

def test_routing_http_requires_original_token_and_origin(routing_server, monkeypatch):
    server = routing_server
    calls = []
    original = server.model_routing.configure

    def configure(**values):
        calls.append(values)
        return original(**values)
    monkeypatch.setattr(server.model_routing, 'configure', configure)
    origin = f'http://127.0.0.1:{server.server_port}'
    assert request(server)[0] == 403
    assert request(server, token='wrong-token')[0] == 403
    assert request(server, token=server.chat.token, origin='https://untrusted.example')[0] == 403
    assert request(server, body=body(), token=server.chat.token)[0] == 403
    assert request(server, body=body(), token=server.chat.token, origin='https://untrusted.example')[0] == 403
    assert not calls
    status, result = request(server, token=server.chat.token)
    assert status == 200 and result['endpoints']
    assert all((row['max_context_verified'] is None for row in result['endpoints']))
    assert all((not row['capabilities'] for row in result['endpoints']))
    assert request(server, body=body(), token=server.chat.token, origin=origin)[0] == 200
    assert calls == [{'policy': 'fast', 'manual_endpoint_id': None}]

def test_routing_policy_dedupes_and_rejects_uuid_reuse(routing_server, monkeypatch):
    server = routing_server
    calls = []
    original = server.model_routing.configure

    def configure(**values):
        calls.append(values)
        return original(**values)
    monkeypatch.setattr(server.model_routing, 'configure', configure)
    origin = f'http://127.0.0.1:{server.server_port}'
    change = body()
    assert request(server, body=change, token=server.chat.token, origin=origin)[0] == 200
    assert request(server, body=change, token=server.chat.token, origin=origin)[0] == 200
    assert len(calls) == 1
    collision = {**change, 'policy': 'quality'}
    assert request(server, body=collision, token=server.chat.token, origin=origin)[0] == 400
    assert len(calls) == 1

@pytest.mark.parametrize('change', [{'policy': []}, {'allowed_categories': ['sensitive']}, {'capabilities': ['vision']}, {'policy': 'manual', 'manual_endpoint_id': 'unregistered'}, {'manual_endpoint_id': 'unregistered'}, {'confirmed': 'yes'}])
def test_routing_controls_cannot_grant_capabilities_or_privacy(routing_server, change):
    server = routing_server
    before = server.model_routing.snapshot()['policy']
    status, _ = request(server, body={**body(), **change}, token=server.chat.token, origin=f'http://127.0.0.1:{server.server_port}')
    assert status == 400
    assert server.model_routing.snapshot()['policy'] == before

def test_safe_mode_blocks_policy_write_through_original_registry(routing_server):
    server = routing_server
    before = server.model_routing.snapshot()['policy']
    LocalStopControls(server.model_routing.data_dir).trip('Synthetic routing safety test')
    status, result = request(server, token=server.chat.token)
    assert status == 200 and (not result['controls']['configure']['enabled'])
    assert request(server, body=body('quality'), token=server.chat.token, origin=f'http://127.0.0.1:{server.server_port}')[0] == 409
    assert server.model_routing.snapshot()['policy'] == before

def test_dashboard_reuses_routing_engine_without_closing_its_owner(routing_server):
    owner = routing_server
    attached = DashboardServer(0, owner.telemetry)
    try:
        assert attached.model_routing is owner.model_routing
        assert attached.compute is owner.compute
        assert not attached._owns_model_routing and (not attached._owns_compute)
    finally:
        attached.server_close()
        attached.chat.close()
        attached.chat.db.close()
    assert not owner.model_routing.closed
    assert not owner.compute.closed
    assert current(owner.telemetry.config) is owner.model_routing
