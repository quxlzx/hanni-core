"""HTTP/controller integration checks, separate from workflow engine outcomes."""
from __future__ import annotations
import http.client
import json
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.dashboard.server import DashboardServer
from hanni.dashboard.workflows import WorkflowHub

@pytest.fixture
def workflow_server():
    adapter = Mock()
    adapter.snapshot.return_value = {'available': False, 'reason': 'No controller', 'items': []}
    adapter.detail.return_value = {'workflow': None}
    adapter.mutate.return_value = {'workflow_id': 'wf-example'}
    server = DashboardServer(0, SimpleNamespace(snapshot=lambda: {}), workflows=adapter)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield (server, adapter)
    server.shutdown()
    server.server_close()
    thread.join(3)

def _request(server, path, *, body=None, token=None, origin=True):
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
    headers = {}
    if token is not None:
        headers['X-Hanni-Token'] = token
    if body is not None:
        headers['Content-Type'] = 'application/json'
        if origin:
            headers['Origin'] = f'http://127.0.0.1:{server.server_port}'
    try:
        connection.request('POST' if body is not None else 'GET', path, body=json.dumps(body) if body is not None else None, headers=headers)
        response = connection.getresponse()
        return (response.status, json.loads(response.read()))
    finally:
        connection.close()

def test_workflow_history_and_detail_require_original_dashboard_token(workflow_server):
    server, adapter = workflow_server
    for path in ('/api/workflows', '/api/workflows/wf-example'):
        assert _request(server, path)[0] == 403
        assert _request(server, path, token='stale')[0] == 403
        assert _request(server, path, token=server.chat.token)[0] == 200
    adapter.snapshot.assert_called_once_with(limit=50)
    adapter.detail.assert_called_once_with('wf-example')

def test_universal_task_api_reuses_workflow_auth_and_controller(workflow_server):
    server, adapter = workflow_server
    assert _request(server, '/api/tasks')[0] == 403
    assert _request(server, '/api/tasks', token=server.chat.token)[0] == 200
    assert _request(server, '/api/tasks/wf-example', token=server.chat.token)[0] == 200
    body = {'id': str(uuid4()), 'operation': 'goal.submit', 'data': {'goal': 'Inspect RAM'}}
    assert _request(server, '/api/tasks', body=body, token=server.chat.token, origin=False)[0] == 403
    assert _request(server, '/api/tasks', body=body, token=server.chat.token)[0] == 200
    adapter.mutate.assert_called_once_with(body)

def test_workflow_mutations_require_origin_and_have_no_dynamic_dispatch(workflow_server):
    server, adapter = workflow_server
    body = {'id': str(uuid4()), 'operation': 'goal.submit', 'data': {'goal': 'Inspect RAM'}}
    assert _request(server, '/api/workflows', body=body)[0] == 403
    assert _request(server, '/api/workflows', body=body, token=server.chat.token, origin=False)[0] == 403
    assert _request(server, '/api/workflows/execute', body=body, token=server.chat.token)[0] == 404
    adapter.mutate.assert_not_called()
    assert _request(server, '/api/workflows', body=body, token=server.chat.token)[0] == 200
    adapter.mutate.assert_called_once_with(body)

def test_workflow_hub_rejects_arbitrary_authority_and_detaches_before_close(tmp_path):
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    service = Mock()
    telemetry = SimpleNamespace(snapshot=lambda: {})
    hub = WorkflowHub(config, Mock(), telemetry, service=service)
    registry, client, host = (Mock(), Mock(), Mock())
    hub.attach_controller(registry, client, host)
    service.attach.assert_called_once()
    service.start.assert_called_once()
    for body in ({'id': str(uuid4()), 'operation': 'execute', 'data': {}}, {'id': str(uuid4()), 'operation': [], 'data': {}}, {'id': str(uuid4()), 'operation': 'start', 'data': {}, 'actor_profile': 'owner'}):
        with pytest.raises(ValueError):
            hub.mutate(body)
    service.mutate.assert_not_called()
    hub.detach_controller(Mock())
    assert hub.runner_attached
    hub.detach_controller(registry)
    assert not hub.runner_attached
    service.detach.assert_called_once()
    with pytest.raises(RuntimeError):
        hub.mutate({'id': str(uuid4()), 'operation': 'goal.submit', 'data': {'goal': 'Inspect RAM'}})
    hub.close()
    hub.close()
    service.close.assert_called_once()

def test_explicit_controller_detaches_even_without_session():
    from hanni.cli import _close_interactive_session
    registry = SimpleNamespace(context=SimpleNamespace(reliability=None))
    with patch('hanni.mcp.runtime.detach_controller') as detach:
        _close_interactive_session(None, registry=registry)
    detach.assert_called_once_with(registry)

def test_workflow_resource_admission_does_not_invent_missing_or_stale_ram(tmp_path):
    import time
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    telemetry = Mock()
    hub = WorkflowHub(config, Mock(), telemetry, service=Mock())
    for sample in ({}, {'sampled_at': time.time() - 100, 'resources': {'ram_percent': 10}}, {'sampled_at': time.time(), 'resources': {'ram_percent': float('nan')}}, {'sampled_at': time.time(), 'resources': {'ram_percent': 95}}):
        telemetry.snapshot.return_value = sample
        assert not hub._resource_probe()['allowed']
    telemetry.snapshot.return_value = {'sampled_at': time.time(), 'resources': {'ram_percent': 20}}
    result = hub._resource_probe()
    assert result['allowed']
    assert result['gpu'] is None

def test_store_unavailable_projection_does_not_become_empty_available_history(tmp_path):
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    service = Mock()
    service.snapshot.return_value = {'available': False, 'items': []}
    hub = WorkflowHub(config, Mock(), Mock(), service=service)
    hub.runner_attached = True
    result = hub.snapshot()
    assert result['available'] is False
    assert result['controls']['goal.submit']['enabled'] is False

def test_keyboard_goal_uses_attached_service_and_does_not_claim_execution(tmp_path):
    from hanni.cli import _workflow_command
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    hub = Mock()
    hub.mutate.return_value = {'workflow_id': 'wf-example'}
    with patch('hanni.mcp.runtime.workflow_hub', return_value=hub):
        assert _workflow_command('Explain RAM usage', config) is None
        result = _workflow_command('/goal Collect measurements', config)
    body = hub.mutate.call_args.args[0]
    assert body['operation'] == 'goal.submit'
    assert body['data'] == {'goal': 'Collect measurements', 'mode': 'assisted'}
    assert 'wf-example' in result
    assert 'Execution has not been verified' in result

def test_keyboard_workflow_command_does_not_start_unattached_controller(tmp_path):
    from hanni.cli import _workflow_command
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    with patch('hanni.mcp.runtime.workflow_hub', return_value=None):
        assert 'Start the HANNI dashboard backend' in _workflow_command('/goal Collect measurements', config)

def test_workflow_close_fault_still_closes_original_server_resources():
    adapter, cluster, power = (Mock(), Mock(), Mock())
    adapter.close.side_effect = RuntimeError('Synthetic workflow storage fault')
    server = DashboardServer(0, SimpleNamespace(snapshot=lambda: {}), workflows=adapter, cluster=cluster, cluster_power=power)
    server.server_close()
    assert server.socket.fileno() == -1
    adapter.close.assert_called_once()
    cluster.close.assert_called_once()
    power.close.assert_called_once()

def test_workflow_events_use_existing_persistent_notification_preferences_and_deduplication(tmp_path):
    from hanni.dashboard.features import DesktopFeatures
    from hanni.dashboard.productivity import ProductivityStore
    config = load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={})
    features = DesktopFeatures(config)
    hub = WorkflowHub(config, features, Mock(), service=Mock())
    event = {'key': 'workflow:wf-fixture:4', 'category': 'approvals', 'priority': 'high', 'title': 'Workflow review required', 'message': 'Review the saved plan in Workflows.', 'target': {'screen': 'workflows', 'id': 'wf-fixture'}}
    hub._notify(event)
    hub._notify(event)
    records = features.store.notifications()['items']
    assert len(records) == 1
    assert records[0]['priority'] == 'action_required'
    assert records[0]['target'] == event['target']
    assert event['priority'] == 'high'
    features.store.notification_mutate('notification.dismiss', {'notification_id': records[0]['id']}, str(uuid4()))
    restarted = DesktopFeatures(config, store=ProductivityStore(tmp_path))
    hub.features = restarted
    hub._notify(event)
    assert len(restarted.store.notifications()['items']) == 1
    assert restarted.store.notifications()['items'][0]['dismissed']
    restarted.store.notification_mutate('notification.preferences', {'categories': {'tasks': False}}, str(uuid4()))
    hub._notify({**event, 'key': 'workflow:wf-fixture:5', 'category': 'tasks', 'priority': 'normal', 'title': 'Workflow completed'})
    assert len(restarted.store.notifications()['items']) == 1
