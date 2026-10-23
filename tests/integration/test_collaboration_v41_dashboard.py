"""Actual private HTTP submission and durable V3 preference bindings.

The planner reply and RAM probe are controlled; no live inference, remote SSH,
or tool action runs. Authentication, HTTP routing, hub, service, and SQLite are
the original implementations.
"""
import http.client
import json
import threading
import time
from types import SimpleNamespace
from uuid import uuid4
from hanni.dashboard.server import DashboardServer
from hanni.dashboard.workflows import WorkflowHub
from scripts.v3_review.service_fixture import ServiceFixture

class UnsupportedPlanner:

    def chat(self, _messages, **_options):
        return json.dumps({'summary': 'Controlled HTTP preference admission.', 'unsupported_reason': 'This isolated preference test has no executable task.', 'steps': []})

def post(server, body, *, token=True, origin=True):
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['X-Hanni-Token'] = server.chat.token
    if origin:
        headers['Origin'] = f'http://127.0.0.1:{server.server_port}'
    try:
        connection.request('POST', '/api/workflows', json.dumps(body), headers)
        response = connection.getresponse()
        return (response.status, json.loads(response.read()))
    finally:
        connection.close()

def test_actual_http_preferences_are_durable_payload_bound_and_cannot_grant_sharing(tmp_path):
    with ServiceFixture(tmp_path / 'isolated', client=UnsupportedPlanner()) as fixture:
        fixture.service.detach()
        telemetry = SimpleNamespace(snapshot=lambda: {'sampled_at': time.time(), 'resources': {'ram_percent': 20}})
        features = SimpleNamespace(store=SimpleNamespace(ingest=lambda _events: None))
        hub = WorkflowHub(fixture.config, features, telemetry, service=fixture.service)
        hub.attach_controller(fixture.registry, fixture.client, fixture.host)
        server = DashboardServer(0, telemetry, workflows=hub)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for pattern in ('auto', 'single', 'parallel', 'specialists', 'review'):
                body = {'id': str(uuid4()), 'operation': 'goal.submit', 'data': {'goal': 'Controlled preference admission', 'collaboration': pattern}}
                assert post(server, body, token=False)[0] == 403
                assert post(server, body, origin=False)[0] == 403
                status, response = post(server, body)
                assert status == 200, response
                key = response['workflow_id']
                assert fixture.service.store.get(key)['collaboration'] == pattern
                assert fixture.service.detail(key)['collaboration'] == pattern
                assert not fixture.service.store.history(key)['invocations']
                replay_status, replay = post(server, body)
                assert replay_status == 200 and replay['workflow_id'] == key
                changed = {**body, 'data': {**body['data'], 'collaboration': 'parallel' if pattern != 'parallel' else 'single'}}
                assert post(server, changed)[0] == 400
                assert fixture.service.store.get(key)['collaboration'] == pattern
            count = len(fixture.service.store.list())
            for added in ({'privacy_categories': ['synthetic']}, {'actor_profile': 'owner'}, {'endpoint_id': 'worker:unregistered'}, {'approved_capabilities': ['shell.execute']}):
                body = {'id': str(uuid4()), 'operation': 'goal.submit', 'data': {'goal': 'Controlled invalid preference', 'mode': 'assisted', 'collaboration': 'parallel', **added}}
                assert post(server, body)[0] == 400
            assert len(fixture.service.store.list()) == count
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)

def test_invalid_json_preference_types_are_controlled_errors_without_model_dispatch(tmp_path):
    with ServiceFixture(tmp_path / 'isolated', client=UnsupportedPlanner()) as fixture:
        fixture.service.detach()
        telemetry = SimpleNamespace(snapshot=lambda: {'sampled_at': time.time(), 'resources': {'ram_percent': 20}})
        features = SimpleNamespace(store=SimpleNamespace(ingest=lambda _events: None))
        hub = WorkflowHub(fixture.config, features, telemetry, service=fixture.service)
        hub.attach_controller(fixture.registry, fixture.client, fixture.host)
        server = DashboardServer(0, telemetry, workflows=hub)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for preference in (None, True, 1, [], {}, 'unbounded'):
                body = {'id': str(uuid4()), 'operation': 'goal.submit', 'data': {'goal': 'Controlled invalid preference', 'mode': 'assisted', 'collaboration': preference}}
                status, response = post(server, body)
                assert status == 400, (preference, response)
            assert fixture.service.store.list() == []
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)
