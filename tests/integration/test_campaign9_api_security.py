"""New API authorization, synthetic credential reflection and recovery controls."""
import errno
import json
import sqlite3
import uuid
from unittest.mock import patch
import pytest
from scripts.campaign8_ui.backend import original_backend
from scripts.campaign9_manager.api_security import CANARY, error_probes, log_probes, private_routes, raw_request

@pytest.fixture(scope='module')
def backend(tmp_path_factory):
    with original_backend(tmp_path_factory.mktemp('c9-http') / 'runtime') as instance:
        yield instance
    assert instance.closed and (not instance.thread.is_alive())

@pytest.mark.parametrize('path', private_routes() + ('/api/workflows/synthetic-id', '/api/memory/record/synthetic-id', '/api/model-lab/run/synthetic-id'))
@pytest.mark.parametrize('token', [None, 'C9_INVALID_AUTHORIZATION'])
def test_private_reads_refuse_absent_or_wrong_authorization(backend, path, token):
    headers = {} if token is None else {'X-Hanni-Token': token}
    with patch.object(backend.features, 'memories', side_effect=AssertionError('Forbidden handler entry')):
        status, _, _ = raw_request(backend, path, headers=headers)
    assert status == 403

@pytest.mark.parametrize('headers', [{'Host': 'c9.invalid'}, {'Origin': 'https://c9.invalid'}, {'Origin': 'null'}, {'Sec-Fetch-Site': 'cross-site'}, {'Host': '127.0.0.1:1'}])
def test_host_origin_fetch_guards_precede_private_reads(backend, headers):
    status, _, _ = raw_request(backend, '/api/memory', headers={'X-Hanni-Token': backend.chat.token} | headers)
    assert status == 403

@pytest.mark.parametrize('headers', [{'X-Hanni-Token': ''}, {'X-Hanni-Token': 'C9_INVALID_AUTHORIZATION'}, {'Origin': 'https://c9.invalid'}, {'Origin': 'null'}, {'Sec-Fetch-Site': 'cross-site'}, {'Host': 'c9.invalid'}])
def test_unauthorized_writes_enter_no_workspace_handler(backend, headers):
    defaults = {'Origin': backend.url, 'X-Hanni-Token': backend.chat.token, 'Content-Type': 'application/json'}
    with patch.object(backend.features, 'mutate') as action:
        status, _, _ = raw_request(backend, '/api/productivity', method='POST', body='{}', headers=defaults | headers)
    assert status == 403
    action.assert_not_called()

@pytest.mark.parametrize('body', ['[]', 'null', '"synthetic"', '{', '{"data":}', '42'])
def test_invalid_json_or_nonobject_enters_no_workspace_handler(backend, body):
    with patch.object(backend.features, 'mutate') as action:
        status, _, _ = raw_request(backend, '/api/productivity', method='POST', body=body, headers={'Origin': backend.url, 'X-Hanni-Token': backend.chat.token, 'Content-Type': 'application/json'})
    assert status == 400
    action.assert_not_called()

def test_registered_synthetic_secret_not_in_HTTP_dependency_errors(backend):
    from hanni.logs.redaction import register_secret, clear_registry
    register_secret('C9_SYNTHETIC_ONLY', CANARY)
    try:
        rows = error_probes(backend)
        assert len(rows) == 8
        assert all((not row['synthetic_canary_reflected'] for row in rows))
    finally:
        clear_registry()

def test_registered_synthetic_secret_not_in_logs():
    from hanni.logs.redaction import register_secret, clear_registry
    register_secret('C9_SYNTHETIC_ONLY', CANARY)
    try:
        assert all((not row['synthetic_canary_reflected'] for row in log_probes()))
    finally:
        clear_registry()

@pytest.mark.parametrize('failure', [sqlite3.OperationalError('C9 controlled locked DB'), OSError(errno.ENOSPC, 'C9 controlled disk full')])
def test_dependency_failure_does_not_claim_success_or_retry(backend, failure):
    headers = {'Origin': backend.url, 'X-Hanni-Token': backend.chat.token, 'Content-Type': 'application/json'}
    with patch.object(backend.features, 'mutate', side_effect=failure) as action:
        try:
            status, _, body = raw_request(backend, '/api/productivity', method='POST', body='{}', headers=headers)
        except __import__('http.client', fromlist=['RemoteDisconnected']).RemoteDisconnected:
            status, body = (None, b'')
    assert status is None or status >= 400
    assert b'"success": true' not in body
    assert action.call_count == 1
    assert raw_request(backend, '/api/productivity', headers={'X-Hanni-Token': backend.chat.token})[0] == 200

def test_actual_task_replay_is_payload_bound_and_persistent(backend):
    key = str(uuid.uuid4())
    body = {'id': key, 'operation': 'task.create', 'data': {'title': 'C9 synthetic fixture task'}, 'confirmed': True}
    first_status, first = backend.request('/api/productivity', method='POST', body=body)
    second_status, second = backend.request('/api/productivity', method='POST', body=body)
    assert first_status == second_status == 200 and first == second
    status, _ = backend.request('/api/productivity', method='POST', body=body | {'data': {'title': 'C9 changed fixture task'}})
    assert status == 400
    with sqlite3.connect(backend.features.store.path) as db:
        assert db.execute('SELECT count(*) FROM todos WHERE title=?', ('C9 synthetic fixture task',)).fetchone()[0] == 1

def test_auth_failure_flood_is_bounded_and_valid_request_recovers(backend):
    with patch.object(backend.features, 'mutate') as action:
        for _ in range(12):
            assert raw_request(backend, '/api/productivity', method='POST', body='{}', headers={'Origin': backend.url, 'X-Hanni-Token': 'C9_INVALID', 'Content-Type': 'application/json'})[0] == 403
    action.assert_not_called()
    assert backend.request('/api/productivity')[0] == 200

def test_history_clear_revokes_old_token_without_exposing_it(backend):
    old = backend.chat.token
    backend.chat.activate()
    status, result = backend.request('/api/chat/clear', method='POST', body={})
    assert status == 200 and result == {'cleared': True}
    assert backend.chat.token != old
    assert raw_request(backend, '/api/productivity', headers={'X-Hanni-Token': old})[0] == 403
    assert backend.request('/api/productivity')[0] == 200

def test_original_chat_restart_does_not_replay_pending_turns(tmp_path):
    from hanni.dashboard.chat import ChatHub
    path = tmp_path / 'synthetic-restart.sqlite3'
    old = ChatHub(path)
    old.activate()
    old_token = old.token
    key = str(uuid.uuid4())
    old.submit(key, 'C9 synthetic pending read request')
    old.close()
    old.db.close()
    new = ChatHub(path)
    try:
        new.activate()
        assert new.token != old_token
        assert not new.queue and new.take() is None
        new.submit(key, 'C9 synthetic pending read request')
        assert not new.queue
        rows = new.snapshot()['messages']
        assert len(rows) == 1 and rows[0]['status'] == 'interrupted'
    finally:
        new.close()
        new.db.close()

def test_metadata_and_serialized_object_strings_are_redacted_before_JSON_output():
    import logging
    from hanni.logs.formatter import JsonFormatter
    from hanni.logs.redaction import register_secret, clear_registry
    secret = 'C9_SYNTHETIC_unicode_雪_"quote"_\\path'

    class SyntheticObject:

        def __str__(self):
            return secret
    register_secret('C9_SYNTHETIC_ESCAPED', secret)
    try:
        record = logging.LogRecord('hanni.c9', logging.INFO, __file__, 1, 'Controlled metadata', (), None)
        record.payload = {secret: SyntheticObject()}
        output = JsonFormatter(node_id='synthetic-local').format(record)
        decoded = json.loads(output)
        assert secret not in decoded['payload']
        assert secret not in decoded['payload'].values()
    finally:
        clear_registry()
