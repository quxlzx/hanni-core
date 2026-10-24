"""Conversation review uses real durable actions and exact approval snapshots."""
from copy import deepcopy

import pytest

from hanni.dashboard import bridge_panel
from hanni.hermes.state import Conflict, TaskStore, digest
from hanni.native.local_tools import local_tool_specs
from tests.unit.test_dashboard_chat import chat_server, send


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    task = store.submit('review-fixture', {'prompt': 'Write a note', 'windows_tools': [], 'origin': 'hanni', 'context': {}})
    spec = next(item for item in local_tool_specs() if item['name'] == 'local_write_file')
    action = store.request_action(task['id'], 'write-call', spec, {'path': 'note.txt', 'content': 'exact reviewed text'})
    posts = []
    def proxy(method, path, body=None):
        if method == 'GET' and path.startswith('/tasks/'):
            return store.get(path.split('/')[2])
        if method == 'GET' and path.startswith('/actions/'):
            return store.action(path.split('/')[2])
        if method == 'POST' and path.startswith('/actions/'):
            posts.append(body)
            return store.settle(path.split('/')[2], body['state'], expected_hash=body.get('expected_hash'))
        raise AssertionError((method, path))
    monkeypatch.setattr(bridge_panel, 'bridge_proxy', proxy)
    yield store, task, action, posts
    store.db.close()


@pytest.mark.parametrize('decision', ['dispatching', 'rejected'])
def test_review_snapshot_can_decide_only_its_exact_request(bridge, decision):
    store, task, action, posts = bridge
    detail = bridge_panel.bridge_task_detail(task['id'])
    reviewed = detail['actions'][0]
    assert reviewed['review_hash'] == digest(action)
    assert 'review_hash' not in store.action(action['id'])
    result = bridge_panel.bridge_decision(action['id'], {
        'state': decision, 'task_id': task['id'], 'expected_hash': reviewed['review_hash']})
    assert result['state'] == decision and result['receipt'] is None
    assert posts == [{'state': decision, 'expected_hash': digest(action)}]


@pytest.mark.parametrize('change', ['arguments', 'definition', 'expiry', 'state', 'task'])
def test_changes_after_review_block_dispatch_before_any_effect(bridge, change):
    store, task, action, posts = bridge
    expected = bridge_panel.bridge_task_detail(task['id'])['actions'][0]['review_hash']
    changed = deepcopy(action)
    if change == 'arguments': changed['arguments']['content'] = 'different content'
    elif change == 'definition': changed['spec']['hash'] = 'changed definition'
    elif change == 'expiry': changed['expires'] += 1
    elif change == 'state': changed['state'] = 'dispatching'
    else: changed['task'] = 'different task'
    store._action_save(changed)
    with pytest.raises(ValueError, match='changed|another task'):
        bridge_panel.bridge_decision(action['id'], {'state': 'dispatching', 'task_id': task['id'], 'expected_hash': expected})
    assert not posts


def test_bridge_store_checks_atomic_fingerprint_even_if_action_changes_after_proxy_read(bridge, monkeypatch):
    store, task, action, posts = bridge
    original = bridge_panel.bridge_proxy
    def race(method, path, body=None):
        result = original(method, path, body)
        if method == 'GET' and path.startswith('/actions/'):
            changed = deepcopy(action); changed['arguments']['content'] = 'raced change'
            store._action_save(changed)
        return result
    monkeypatch.setattr(bridge_panel, 'bridge_proxy', race)
    with pytest.raises(Conflict, match='changed'):
        bridge_panel.bridge_decision(action['id'], {'state': 'dispatching', 'task_id': task['id'], 'expected_hash': digest(action)})
    assert store.action(action['id'])['state'] == 'pending'


@pytest.mark.parametrize('blocked', ['expired', 'cancelled'])
def test_even_a_matching_snapshot_cannot_approve_expired_or_cancelled_work(bridge, blocked):
    store, task, action, posts = bridge
    if blocked == 'expired':
        action['expires'] = 0
        store._action_save(action)
    else:
        store.cancel(task['id'])
    reviewed = bridge_panel.bridge_task_detail(task['id'])['actions'][0]
    with pytest.raises(Conflict, match='cancelled|expired'):
        bridge_panel.bridge_decision(action['id'], {'state': 'dispatching', 'task_id': task['id'], 'expected_hash': reviewed['review_hash']})
    assert store.action(action['id'])['state'] == 'pending'


def test_task_review_api_preserves_session_and_origin_protection(chat_server, bridge):
    store, task, action, posts = bridge
    # send helper includes the current session token and same-origin header.
    import http.client
    import json
    connection = http.client.HTTPConnection('127.0.0.1', chat_server.server_port, timeout=3)
    path = '/api/bridge/task/' + task['id']
    try:
        connection.request('GET', path)
        response = connection.getresponse(); response.read()
        assert response.status == 403
        connection.request('GET', path, headers={'X-Hanni-Token': chat_server.chat.token})
        response = connection.getresponse(); detail = json.loads(response.read())
        assert response.status == 200 and detail['actions'][0]['review_hash'] == digest(action)
    finally:
        connection.close()
    body = {'state': 'dispatching', 'task_id': task['id'], 'expected_hash': digest(action)}
    path = '/api/bridge/action/' + action['id']
    for headers in [{'X-Hanni-Token': 'wrong'}, {'Origin': 'https://evil.example'}]:
        assert send(chat_server, path=path, body=body, headers=headers)[0] == 403
    assert not posts
    status, result = send(chat_server, path=path, body=body)
    assert status == 200 and result['state'] == 'dispatching'
    # A repeated click cannot replay an approved action.
    assert send(chat_server, path=path, body=body)[0] == 400
    assert len(posts) == 1


@pytest.mark.parametrize('body', [None, {}, {'state': 'fulfilled'}, {'state': 'dispatching', 'receipt': {'ok': True}},
    {'state': 'dispatching', 'expected_hash': 'bad'}, {'state': 'dispatching', 'task_id': 'task-without-hash'}])
def test_malformed_decisions_do_not_request_dispatch(bridge, body):
    store, task, action, posts = bridge
    with pytest.raises(ValueError):
        bridge_panel.bridge_decision(action['id'], body)
    assert not posts and store.action(action['id'])['state'] == 'pending'
