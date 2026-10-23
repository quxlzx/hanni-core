"""Independent original DashboardServer authorization and lab API tests."""
from copy import deepcopy
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import urllib.error
import urllib.request
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.dashboard.chat import ChatHub
from hanni.dashboard.features import DesktopFeatures
from hanni.dashboard.server import DashboardServer
from hanni.models.adaptive import AdaptiveModelEngine, install, uninstall
from hanni.reliability.execution import close_service
from hanni.tools.registry import build_default_registry
ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture
def server(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path / 'state', env={})
    registry = build_default_registry(config)
    engine = AdaptiveModelEngine(config, local_probe=lambda row: {'status': 'unhealthy', 'model_id': None, 'last_heartbeat': time.time()})
    install(engine)
    engine.refresh()
    hub = ChatHub()
    shutdown = threading.Event()
    cluster = SimpleNamespace(start=lambda: None, close=lambda: None, snapshot=lambda: {'nodes': []})
    power = SimpleNamespace(start=lambda: None, close=lambda: None, project=lambda result: result)
    terminal = SimpleNamespace(project=lambda result: result)
    app = DashboardServer(0, SimpleNamespace(config=config, snapshot=lambda: {'sampled_at': time.time()}), hub, features=DesktopFeatures(config, registry=registry), shutdown_event=shutdown, cluster=cluster, cluster_power=power, cluster_terminal=terminal)
    thread = threading.Thread(target=app.serve_forever, daemon=True)
    thread.start()
    yield (app, f'http://127.0.0.1:{app.server_port}', hub.token)
    shutdown.set()
    app.shutdown()
    app.server_close()
    thread.join(3)
    engine.close()
    uninstall(engine)
    hub.close()
    hub.db.close()
    close_service(config.paths.data_dir)

def request(server, path, body=None, *, authorized=True, headers=None):
    app, origin, token = server
    selected = {'Accept': 'application/json'}
    if authorized:
        selected['X-Hanni-Token'] = token
    if body is not None:
        selected.update({'Content-Type': 'application/json', 'Origin': origin})
    selected.update(headers or {})
    req = urllib.request.Request(origin + path, data=None if body is None else json.dumps(body).encode(), headers=selected)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return (response.status, json.load(response))
    except urllib.error.HTTPError as error:
        return (error.code, json.load(error))

def control(data=None, action='start'):
    return {'id': str(uuid4()), 'action': action, 'confirmed': True, 'data': data or {'suite_id': 'routing-development', 'endpoint_id': None, 'max_cases': 2, 'repetitions': 1, 'max_tokens': 192, 'max_rounds': 3}}

@pytest.mark.parametrize('path', ['/api/model-lab', '/api/model-lab/run/' + str(uuid4()), '/api/model-lab/export/' + str(uuid4()), '/api/model-lab/compare?ids=a,b', '/api/model-lab/unknown'])
def test_every_lab_read_requires_original_session_token(server, path):
    assert request(server, path, authorized=False)[0] == 403
    assert request(server, path, headers={'X-Hanni-Token': 'wrong-token'})[0] == 403

@pytest.mark.parametrize('headers', [{'Origin': 'https://hostile.invalid'}, {'Origin': 'null'}, {'X-Hanni-Token': ''}, {'Host': 'hostile.invalid'}])
def test_original_origin_host_and_token_gate_rejects_writes(server, headers):
    assert request(server, '/api/model-lab', control(), headers=headers)[0] == 403
    assert not server[0].model_lab.snapshot()['runs']

@pytest.mark.parametrize('body', [control(action='shell'), control() | {'command': 'untrusted'}, control() | {'id': 'invalid'}, control() | {'confirmed': 'yes'}])
def test_invalid_action_and_body_cannot_execute(server, body):
    assert request(server, '/api/model-lab', body)[0] in {400, 409}
    assert not server[0].model_lab.snapshot()['runs']

def test_failed_endpoint_cannot_start_model_work(server):
    body = control()
    body['data'].update(suite_id='structured-development', endpoint_id='local:supervisor', max_cases=1)
    assert request(server, '/api/model-lab', body)[0] in {400, 409, 503}
    assert not server[0].model_lab.snapshot()['runs']

def test_original_http_persistence_detail_export_and_comparison(server):
    body = control()
    status, first = request(server, '/api/model-lab', body)
    assert status == 200
    assert request(server, '/api/model-lab', deepcopy(body))[1]['id'] == first['id']
    run_id = first['id']
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        status, detail = request(server, '/api/model-lab/run/' + run_id)
        if detail['run']['status'] == 'completed':
            break
        time.sleep(0.02)
    assert status == 200 and detail['run']['completed'] == 2
    assert all((row['real_inference'] is False and row['tool_execution'] is False for row in detail['cases']))
    status, export = request(server, '/api/model-lab/export/' + run_id)
    assert status == 200 and export['results'] == detail['cases']
    assert request(server, '/api/model-lab/run/' + run_id + '?limit=501')[0] == 400
    assert request(server, '/api/model-lab/run/' + run_id + '?offset=-1')[0] == 400
    assert request(server, '/api/model-lab/compare?ids=' + run_id + ',' + run_id)[0] == 400
    assert request(server, '/api/model-lab?unknown=injection')[0] == 400
    assert request(server, '/api/model-lab?status=completed')[1]['history_count'] == 1
    assert request(server, '/api/model-lab?q=' + run_id)[1]['history_count'] == 1

def test_safe_mode_blocks_api_controls_without_changing_history(server):
    from hanni.core.shutdown import Actor, EmergencyStop, FileStopStateStore, StopSource
    store = FileStopStateStore.for_data_dir(server[0].telemetry.config.paths.data_dir)
    emergency = EmergencyStop(store)
    actor = Actor.local('independent-fixture')
    emergency.trip(source=StopSource.LOCAL_TERMINAL, requested_by=actor, reason='independent controlled safe mode')
    try:
        assert request(server, '/api/model-lab', control())[0] in {409, 503}
        snapshot = request(server, '/api/model-lab')[1]
        assert not snapshot['controls']['start']['enabled'] and (not snapshot['runs'])
    finally:
        emergency.clear(actor)

def test_authenticated_reads_apply_new_secret_policy_to_old_records(server, monkeypatch):
    from hanni.evals.model_lab import digest
    from hanni.logs import redaction
    monkeypatch.setattr(redaction, '_registry', {})
    app = server[0]
    original = app.model_lab._evaluate

    def evaluate(run, case):
        return original(run, case) | {'final_answer': 'late_http_canary_931842'}
    monkeypatch.setattr(app.model_lab, '_evaluate', evaluate)
    status, run = request(server, '/api/model-lab', control())
    assert status == 200
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        value = app.model_lab.detail(run['id'])
        if value['run']['status'] == 'completed':
            break
        time.sleep(0.02)
    stored = value['run'] | {'status_reason': 'late_http_canary_931842'}
    app.model_lab._save(stored)
    redaction.register_secret('V43_HTTP_CANARY', 'late_http_canary_931842')
    for path in ['/api/model-lab', '/api/model-lab/run/' + run['id'], '/api/model-lab/export/' + run['id']]:
        status, public = request(server, path)
        assert status == 200 and 'late_http_canary_931842' not in json.dumps(public)
    row = public['results'][0]
    checksum = row.pop('evidence_sha256')
    assert digest(row) == checksum

def test_serialized_export_preserves_float_manifest_and_late_secret_hashes(server, monkeypatch):
    """Regression for the genuine native 1500.0 -> 1500 downloaded hash defect."""
    from hanni.evals.model_lab import digest
    from hanni.logs import redaction
    monkeypatch.setattr(redaction, '_registry', {})
    app = server[0]
    evaluate = app.model_lab._evaluate
    configuration = app.model_lab._configuration
    monkeypatch.setattr(app.model_lab, '_evaluate', lambda run, case: evaluate(run, case) | {'latency_ms': 1500.0, 'final_answer': 'serialized_canary_812741 "quoted": {"x":1}'})
    monkeypatch.setattr(app.model_lab, '_configuration', lambda endpoint: configuration(endpoint) | {'serialization_probe': 1.0})
    status, run = request(server, '/api/model-lab', control())
    assert status == 200
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        persisted = app.model_lab.detail(run['id'])
        if persisted['run']['status'] == 'completed':
            break
        time.sleep(0.01)
    assert persisted['run']['completed'] == 2
    redaction.register_secret('V43_SERIALIZED_CANARY', 'serialized_canary_812741')
    path = '/api/model-lab/export/' + run['id'] + '?representation=serialized'
    assert request(server, path, authorized=False)[0] == 403
    assert request(server, path + 'x')[0] == 400
    status, encoded = request(server, path)
    assert status == 200 and encoded['export_complete'] is True and (encoded['next_offset'] is None)
    assert 'serialized_canary_812741' not in json.dumps(encoded)
    manifest = json.loads(encoded['run_json'])
    assert type(manifest['configuration']['serialization_probe']) is float
    assert digest(manifest['configuration']) == manifest['configuration_sha256']
    assert digest(manifest['protocol']) == manifest['protocol_sha256']
    decoded = [json.loads(raw) for raw in encoded['results_json']]
    assert [row['ordinal'] for row in decoded] == [0, 1]
    for row in decoded:
        assert type(row['latency_ms']) is float and row['latency_ms'] == 1500.0
        checksum = row.pop('evidence_sha256')
        assert digest(row) == checksum and row['stored_evidence_sha256']
    status, final_page = request(server, path + '&offset=1&limit=1')
    assert status == 200 and len(final_page['results_json']) == 1 and final_page['export_complete']
    assert json.loads(final_page['results_json'][0])['ordinal'] == 1
