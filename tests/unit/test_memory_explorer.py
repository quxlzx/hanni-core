"""Real private API/registry boundaries for exact owner memory review."""
from dataclasses import replace
import http.client
import json
import threading
from types import SimpleNamespace
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.dashboard.features import DesktopFeatures
from hanni.dashboard.server import DashboardServer
from hanni.tools.base import ToolPermissionError
from tests.helpers import REPO_ROOT

def features(path):
    return DesktopFeatures(load_config(REPO_ROOT / 'config', data_dir=path, env={}))

def mutation(operation, data):
    return {'id': str(uuid4()), 'operation': operation, 'data': data, 'confirmed': True}

def correction(record, new_content, **extra):
    return mutation('correct', {'memory_id': record.id, 'expected_updated_at': record.updated_at.isoformat(), 'content': new_content, 'project_id': '', 'semantic_status': 'statement', **extra})

def test_browse_pagination_filters_and_uncalibrated_confidence(tmp_path):
    feature = features(tmp_path)
    store = feature.memory_store()
    for index in range(35):
        store.remember(f'Experiment {index} uses synthetic evaluation fixtures', source='owner_explicit:test')
    first = feature.memory_explorer.browse({'limit': '30'})
    second = feature.memory_explorer.browse({'limit': '30', 'offset': '30'})
    assert len(first['records']) == 30 and first['has_more']
    assert len(second['records']) == 5 and (not second['has_more'])
    assert first['total_stored'] == 35
    assert not {row['id'] for row in first['records']}.intersection((row['id'] for row in second['records']))
    assert 'confidence' not in first['records'][0]
    assert first['status']['production_retrieval_active'] is False

def test_missing_configuration_has_an_honest_unavailable_memory_projection():
    result = DesktopFeatures(None).memory_explorer.browse()
    assert result['available'] is False
    assert result['status']['production_retrieval_active'] is False

def test_requested_advisory_is_unavailable_until_actual_model_gate_is_verified(tmp_path):
    feature = features(tmp_path)
    config = replace(feature.config, hanni=replace(feature.config.hanni, laya=replace(feature.config.hanni.laya, advisory_enabled=True)))
    status = DesktopFeatures(config).memory_explorer.status()
    assert status['mode'] == 'unavailable'
    assert not status['model_inference_active'] and (not status['production_retrieval_active'])
    assert not list(tmp_path.iterdir())

def test_status_reads_live_remote_consent_and_controller_gates_without_sending(tmp_path):
    from hanni.laya.advisory import AdvisoryClient
    from hanni.laya.runtime import install_advisory, stop_advisory
    feature = features(tmp_path)
    requested = replace(feature.config.hanni.laya, advisory_enabled=True, retrieval_enabled=True, transport='remote-ssh', allow_stored_memories=True, allow_remote_text=True, allow_remote_memories=True)
    config = replace(feature.config, hanni=replace(feature.config.hanni, laya=requested))
    client = AdvisoryClient(enabled=True, retrieval_enabled=True, quality_gate_passed=True, url=requested.url, token='synthetic-authentication-value-00000000', transport='remote-ssh', allow_stored_memories=True, allow_remote_text=True, allow_remote_memories=True)
    try:
        install_advisory(config, client)
        view = DesktopFeatures(config).memory_explorer
        assert view.status()['remote_memory_transmission'] is True
        assert view.status()['mode'] == 'connecting'
        assert 'shadow observer' not in view.status()['description']
        assert client.sent == 0
        client.allow_remote_memories = False
        assert view.status()['remote_memory_transmission'] is False
        client.allow_remote_memories = True
        client.admission_guard = lambda: False
        assert view.status()['remote_memory_transmission'] is False
        assert client.sent == 0
    finally:
        stop_advisory(config)

def test_project_source_package_retains_exact_reported_bounded_text(tmp_path):
    feature = features(tmp_path)
    project = feature.store.mutate('project.create', {'name': 'Long synthetic project', 'description': ''}, str(uuid4()))['project']
    store = feature.memory_store()
    for index in range(12):
        store.remember(f'Experiment {index} includes ' + 'synthetic source details ' * 18, source='owner_explicit:test', project_id=project['id'])
    context = feature.memory_explorer.project(project['id'])['context']
    assert len(context['context_text']) == context['context_chars']
    assert 2000 < context['context_chars'] <= 8000

@pytest.mark.parametrize('query', [{'limit': '1000'}, {'offset': '-1'}, {'offset': '1.5'}, {'sort': 'random'}, {'execute': 'true'}])
def test_browse_rejects_unbounded_or_unknown_request_fields(tmp_path, query):
    with pytest.raises(ValueError):
        features(tmp_path).memory_explorer.browse(query)

def test_exact_correction_uses_original_registry_is_idempotent_and_keeps_source_history(tmp_path):
    feature = features(tmp_path)
    store = feature.memory_store()
    record, _ = store.remember('I prefer long reports', source='owner_explicit:test')
    request = correction(record, 'I prefer concise reports')
    receipt = feature.mutate('memory', request)
    assert receipt['record']['id'] == record.id
    assert feature.mutate('memory', request) == receipt
    detail = feature.memory_explorer.detail(record.id)
    assert detail['record']['content'] == 'I prefer concise reports'
    assert detail['history'][0]['content'] == 'I prefer long reports'
    with pytest.raises(ValueError, match='changed'):
        feature.mutate('memory', correction(record, 'A stale correction'))
    audit = (tmp_path / 'logs/tool_audit.jsonl').read_text()
    assert 'concise reports' not in audit and 'memory.desktop_correct' in audit

@pytest.mark.parametrize('change', [{'semantic_status': 'verified_outcome'}, {'content': 'password is synthetic-secret'}, {'content': 17}, {'semantic_status': []}])
def test_correction_rejects_sensitive_text_untrusted_types_and_verification_claims(tmp_path, change):
    feature = features(tmp_path)
    store = feature.memory_store()
    record, _ = store.remember('I prefer compact reports', source='owner_explicit:test')
    with pytest.raises(ValueError):
        feature.mutate('memory', correction(record, 'Updated content', **change))
    assert store.get(record.id).content == record.content

def test_review_approved_add_then_delete_cannot_leave_stale_proposal(tmp_path):
    feature = features(tmp_path)
    store = feature.memory_store()
    proposal = store.propose('add', 'I prefer local summaries', source='laya:synthetic', source_ref='conversation:synthetic', reason='An explicit reusable preference.', uncertainty='Requires owner review.')
    body = mutation('review', {'suggestion_id': proposal.id, 'expected_updated_at': proposal.updated_at.isoformat(), 'action': 'approve', 'edited_content': None})
    result = feature.mutate('memory', body)
    assert result['suggestion']['status'] == 'approved'
    record = store.get(result['suggestion']['target_id'])
    assert record.content == proposal.content
    feature.mutate('memory', mutation('forget', {'memory_id': record.id, 'expected_updated_at': record.updated_at.isoformat()}))
    assert store.get_suggestion(proposal.id) is None
    assert feature.memory_explorer.suggestions({'status': 'approved'})['items'] == []

def test_review_reject_dismiss_and_changed_target_have_no_memory_write(tmp_path):
    feature = features(tmp_path)
    store = feature.memory_store()
    for action in ('reject', 'dismiss'):
        item = store.propose('add', 'Synthetic proposed preference ' + action, source='laya:synthetic')
        feature.mutate('memory', mutation('review', {'suggestion_id': item.id, 'expected_updated_at': item.updated_at.isoformat(), 'action': action, 'edited_content': None}))
    assert store.count() == 0
    record, _ = store.remember('I prefer precise notes', source='owner_explicit:test')
    item = store.propose('correct', 'I prefer brief notes', source='laya:synthetic', target_id=record.id, expected_updated_at=record.updated_at.isoformat())
    store.correct(record.id, 'I prefer detailed notes', expected_updated_at=record.updated_at.isoformat())
    with pytest.raises(ValueError, match='changed'):
        feature.mutate('memory', mutation('review', {'suggestion_id': item.id, 'expected_updated_at': item.updated_at.isoformat(), 'action': 'approve', 'edited_content': None}))
    assert store.get(record.id).content == 'I prefer detailed notes'

def test_owner_local_analysis_creates_review_candidate_without_authoritative_write(tmp_path):
    feature = features(tmp_path)
    store = feature.memory_store()
    request = mutation('analyze', {'content': 'I prefer concise answers', 'project_id': ''})
    result = feature.mutate('memory', request)
    assert result['created'] == 1 and store.count() == 0
    assert result['suggestion']['source'] == 'owner_requested:local_rules'
    assert result['suggestion']['status'] == 'pending'
    assert feature.mutate('memory', request) == result
    assert store.count_suggestions() == 1
    for text in ('Maybe I might choose another model', 'What model should I use?', 'I think I prefer another model'):
        result = feature.mutate('memory', mutation('analyze', {'content': text, 'project_id': ''}))
        assert result['created'] == 0
    assert store.count() == 0

def test_relationship_review_proposals_are_bounded_and_do_not_resolve_conflicts(tmp_path):
    feature = features(tmp_path)
    project = feature.store.mutate('project.create', {'name': 'Synthetic model', 'description': 'Evaluation fixture'}, str(uuid4()))['project']
    store = feature.memory_store()
    first, _ = store.remember('Synthetic experiment uses local weights', source='owner_explicit:test', project_id=project['id'])
    second, _ = store.remember('Synthetic experiment uses fixed seeds', source='owner_explicit:test', project_id=project['id'])
    result = feature.mutate('memory', mutation('consolidate', {'project_id': project['id']}))
    assert result['created'] == 1 and result['scanned'] == 2
    assert store.count() == 2
    assert store.suggestions()[0].related_ids == (second.id, first.id)
    assert feature.mutate('memory', mutation('consolidate', {'project_id': project['id']}))['created'] == 0
    assert store.get(first.id).content == first.content
    assert store.get(second.id).content == second.content

def test_deleted_project_keeps_memory_accessible_and_suggestions_dismissable(tmp_path):
    feature = features(tmp_path)
    project = feature.store.mutate('project.create', {'name': 'Disposable synthetic project', 'description': ''}, str(uuid4()))['project']
    store = feature.memory_store()
    record, _ = store.remember('Project synthetic reusable fact', source='owner_explicit:test', project_id=project['id'])
    proposal = store.propose('add', 'A pending synthetic decision', source='laya:synthetic', project_id=project['id'])
    feature.store.mutate('project.delete', {'project_id': project['id'], 'expected_fingerprint': project['fingerprint']}, str(uuid4()))
    detail = feature.memory_explorer.detail(record.id)
    assert detail['record']['id'] == record.id and detail['project'] is None and detail['project_missing']
    result = feature.mutate('memory', mutation('review', {'suggestion_id': proposal.id, 'expected_updated_at': proposal.updated_at.isoformat(), 'action': 'dismiss', 'edited_content': None}))
    assert result['suggestion']['status'] == 'dismissed'
    assert store.get(record.id) is not None

def test_chat_only_and_stop_gates_block_memory_write(tmp_path):
    feature = features(tmp_path)
    record, _ = feature.memory_store().remember('Synthetic safe fact', source='owner_explicit:test')
    config = feature.config
    profile = replace(config.permissions.profiles['owner'], chat_only=True)
    config = replace(config, permissions=replace(config.permissions, profiles={**config.permissions.profiles, 'owner': profile}))
    with pytest.raises(ToolPermissionError):
        DesktopFeatures(config).mutate('memory', correction(record, 'Blocked correction'))
    from hanni.core.shutdown import Actor, StopSource
    feature.registry.context.emergency_stop.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner('test'), reason='test')
    with pytest.raises(RuntimeError):
        feature.mutate('memory', correction(record, 'Blocked correction'))
    assert feature.memory_store().get(record.id).content == record.content

def test_unsafe_legacy_correction_history_is_withheld(tmp_path):
    feature = features(tmp_path)
    store = feature.memory_store()
    record, _ = store.remember('A safe original fact', source='owner_explicit:test')
    record = store.correct(record.id, 'A safe corrected fact', expected_updated_at=record.updated_at.isoformat())
    with store._connect() as db:
        db.execute('UPDATE memory_history SET content=? WHERE memory_id=?', ('password is private synthetic history', record.id))
    detail = feature.memory_explorer.detail(record.id)
    assert detail['history'] == [] and detail['history_withheld'] == 1

def test_history_pagination_preserves_original_version_dates(tmp_path):
    feature = features(tmp_path)
    store = feature.memory_store()
    record, _ = store.remember('Synthetic version initial', source='owner_explicit:test')
    for index in range(55):
        record = store.correct(record.id, f'Synthetic version {index}', expected_updated_at=record.updated_at.isoformat())
    first = feature.memory_explorer.detail(record.id)
    last = feature.memory_explorer.detail(record.id, {'offset': '50'})
    assert len(first['history']) == 50 and first['history_has_more']
    assert len(last['history']) == 5 and (not last['history_has_more'])
    assert first['history_count'] == 55
    assert all((item['updated_at'] == item['original_updated_at'] for item in first['history']))

@pytest.fixture
def server(tmp_path):
    config = load_config(REPO_ROOT / 'config', data_dir=tmp_path, env={})
    service = DashboardServer(0, SimpleNamespace(config=config, snapshot=lambda: {}))
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    yield service
    service.shutdown()
    service.server_close()
    thread.join(3)

def call(server, path, token=None, body=None, origin=None):
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
    headers = {'X-Hanni-Token': token} if token else {}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    if origin:
        headers['Origin'] = origin
    try:
        connection.request('POST' if body is not None else 'GET', path, body=json.dumps(body) if body is not None else None, headers=headers)
        response = connection.getresponse()
        return (response.status, json.loads(response.read()))
    finally:
        connection.close()

@pytest.mark.parametrize('route', ['explorer', 'suggestions', 'record/unknown', 'project/unknown'])
def test_all_new_private_views_require_owner_token(server, route):
    assert call(server, '/api/memory/' + route)[0] == 403
    assert call(server, '/api/memory/' + route, token='stale')[0] == 403

def test_http_memory_correction_cannot_skip_origin_or_confirmation(server):
    record, _ = server.features.memory_store().remember('A synthetic owner preference', source='owner_explicit:test')
    body = correction(record, 'An updated synthetic preference')
    assert call(server, '/api/memory', token=server.chat.token, body=body)[0] == 403
    origin = f'http://127.0.0.1:{server.server_port}'
    assert call(server, '/api/memory', token=server.chat.token, body={**body, 'confirmed': False}, origin=origin)[0] == 400
    assert call(server, '/api/memory', token=server.chat.token, body=body, origin=origin)[0] == 200
    assert call(server, '/api/memory/run', token=server.chat.token, body=body, origin=origin)[0] == 404
