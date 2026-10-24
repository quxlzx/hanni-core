"""Real dispatch boundaries, live changes, saved modes and authenticated controls."""
import http.client
import json
import threading
import time
from unittest.mock import patch
from uuid import uuid4

import pytest

from hanni.hermes.state import Conflict, TaskStore
from hanni.native import worker
from hanni.native.local_tools import local_tool_specs
from hanni.native.tool_access import ToolAccess, is_read
from tests.test_native_loop import FakeClient
from tests.unit.test_native_mcp import service, connect, action_for
from tests.unit.test_mcp_hub import ledger


def set_mode(root, mode):
    access = ToolAccess(root)
    return access.save(mode, access.snapshot()['revision'])


def tool(name):
    return next(s for s in local_tool_specs() if s['name'] == name)


def test_saved_modes_conflicts_and_corrupt_settings_fail_closed(tmp_path):
    access = ToolAccess(tmp_path)
    assert access.snapshot()['mode'] == 'configured'
    saved = set_mode(tmp_path, 'full')
    assert ToolAccess(tmp_path).snapshot() == saved
    with pytest.raises(ValueError, match='changed'):
        access.save('read_only', 'default')
    for invalid in ['invalid', None, [], True]:
        with pytest.raises(ValueError):
            access.save(invalid, saved['revision'])
    access.path.write_text('corrupted settings')
    assert access.decision(tool('local_write_file'), {}) == 'blocked'
    assert access.snapshot()['error']
    assert set_mode(tmp_path, 'ask')['error'] is None


@pytest.mark.parametrize('name,args,read', [
    ('local_read_document', {}, True), ('local_write_file', {}, False),
    ('local_terminal', {}, False), ('local_python', {}, False), ('execute_code', {}, False),
    ('scheduled_tasks', {'operation': 'list'}, True), ('scheduled_tasks', {'operation': 'delete'}, False),
    ('agent_job', {'action': 'result'}, True), ('agent_job', {'action': 'cancel'}, False),
    ('delegate_task', {}, True), ('working_state', {'completed': 'inspected'}, True),
])
def test_argument_dependent_read_classification(name, args, read):
    assert is_read(tool(name), args) is read


def run_worker(root, calls, *, context=None, key='chat-test'):
    store = TaskStore(root / 'tasks.sqlite3')
    task = store.submit(key, {'prompt': 'Use the requested test tools', 'windows_tools': [], 'origin': 'hanni',
                              'context': context or {}})
    fake = FakeClient([{'message': {'tool_calls': [
        {'id': str(i), 'function': {'name': name, 'arguments': json.dumps(args)}}
        for i, (name, args) in enumerate(calls)]}}, {'message': {'content': 'Finished.'}}])
    fake.max_tokens = 1200
    def run():
        with patch.object(worker, 'discover', return_value=[]), patch('hanni.native.mcp_client.discover', return_value=[]), \
             patch.object(worker, 'NativeClient', return_value=fake), \
             patch.object(worker, 'load_model', return_value={'context_length': 65536}):
            worker.run(store.path, task['id'], {'entries': []})
    return store, task, fake, run


def test_full_access_writes_and_records_actual_result_without_action_review(tmp_path):
    set_mode(tmp_path, 'full')
    store, task, fake, run = run_worker(tmp_path, [('local_write_file', {'path': 'report.txt', 'content': 'verified'})])
    try:
        run()
        result = store.get(task['id'])
        assert result['state'] == 'review_required', result
        assert (tmp_path / 'workspace/report.txt').read_text() == 'verified'
        assert result['actions'][0]['receipt']['ok']
        assert result['actions'][0]['receipt']['approved_by'] == 'tool_access_policy'
    finally:
        store.close()


def test_read_only_overrides_task_wildcard_and_scoped_child_and_schedule(tmp_path):
    set_mode(tmp_path, 'read_only')
    for key, context in [
        ('chat-test', {'local_runtime': {'auto_approve': ['*']}}),
        ('cron-test', {'scheduled_job_id': 'existing', 'local_runtime': {'auto_approve': ['*']}}),
        ('child-test', {'parent_task_id': 'parent', 'allowed_tools': ['local_write_file', 'scheduled_tasks'],
                        'local_runtime': {'auto_approve': ['*']}}),
    ]:
        store, task, fake, run = run_worker(tmp_path, [
            ('local_write_file', {'path': 'blocked.txt', 'content': 'must not write'}),
            ('scheduled_tasks', {'operation': 'delete', 'id': 'missing'})], context=context, key=key)
        try:
            run()
            assert not (tmp_path / 'workspace/blocked.txt').exists()
            offered = {s['function']['name'] for s in fake.calls[0]['tools']}
            assert 'local_write_file' not in offered
            assert store.get(task['id'])['actions'][0]['receipt']['error_code'] == 'tool_access_denied'
        finally:
            store.close()


def test_read_only_still_reads_workspace_files_without_action_review(tmp_path):
    set_mode(tmp_path, 'read_only')
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    (workspace / 'notes.txt').write_text('Known read-only content')
    store, task, fake, run = run_worker(tmp_path, [('local_read_file', {'path': 'notes.txt'})])
    try:
        run()
        result = store.get(task['id'])
        assert result['state'] == 'review_required', result
        receipt = result['actions'][0]['receipt']
        assert receipt['ok']
        assert 'Known read-only content' in json.dumps(receipt)
        assert receipt['approved_by'] == 'tool_access_policy'
    finally:
        store.close()


@pytest.mark.parametrize('next_mode,created', [('read_only', False), ('full', True)])
def test_ask_overrides_preapproval_and_mode_change_updates_waiting_action(tmp_path, next_mode, created):
    set_mode(tmp_path, 'ask')
    store, task, fake, run = run_worker(tmp_path, [('local_write_file', {'path': 'pending.txt', 'content': 'approved'})],
                                      context={'local_runtime': {'auto_approve': ['*']}})
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not store.get(task['id'])['actions'] and time.monotonic() < deadline:
            time.sleep(.025)
        assert store.get(task['id'])['actions'][0]['state'] == 'pending'
        assert not (tmp_path / 'workspace/pending.txt').exists()
        set_mode(tmp_path, next_mode)
        thread.join(10)
        assert not thread.is_alive()
        assert (tmp_path / 'workspace/pending.txt').exists() is created
        action = store.get(task['id'])['actions'][0]
        assert action['state'] == ('fulfilled' if created else 'rejected')
    finally:
        if thread.is_alive():
            store.cancel(task['id']); thread.join(2)
        store.close()


def test_read_only_blocks_even_explicit_dispatch_of_previously_pending_write(tmp_path):
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    try:
        task = store.submit('pending', {'prompt': 'test', 'windows_tools': [], 'origin': 'hanni', 'context': {}})
        action = store.request_action(task['id'], 'a', tool('local_write_file'), {'path': 'x', 'content': 'x'})
        set_mode(tmp_path, 'read_only')
        with pytest.raises(Conflict, match='Read-only'):
            store.settle(action['id'], 'dispatching')
    finally:
        store.close()


def test_full_access_mcp_write_and_revocation_before_actual_dispatch(service, tmp_path):
    from hanni.native import mcp_client
    connect(service, tmp_path, 'write', 'mock.create_record')
    spec = mcp_client.discover(tmp_path)[0]
    store, task, action = action_for(tmp_path, spec, {'title': 'full access'})
    try:
        set_mode(tmp_path, 'full')
        assert mcp_client.execute(store, task['id'], action)['ok']
        assert len([row for row in ledger(tmp_path) if row['event'] == 'call']) == 1
        next_action = store.request_action(task['id'], 'second', spec, {'title': 'revoked'})
        store.settle(next_action['id'], 'dispatching')
        set_mode(tmp_path, 'read_only')
        receipt = service.native_mcp.call(next_action['id'])
        assert receipt['error_code'] == 'tool_access_denied'
        assert len([row for row in ledger(tmp_path) if row['event'] == 'call']) == 1
    finally:
        store.close()


def test_tool_access_http_requires_owner_origin_and_token_and_deduplicates(service, tmp_path):
    service.chat.native_mode = True
    client = http.client.HTTPConnection('127.0.0.1', service.server_port)
    origin = f'http://127.0.0.1:{service.server_port}'
    def send(method, data=None, **overrides):
        headers = {'Origin': origin, 'Content-Type': 'application/json', 'X-Hanni-Token': service.chat.token, **overrides}
        client.request(method, '/api/tool-access', body=json.dumps(data) if data is not None else None, headers=headers)
        response = client.getresponse()
        return response.status, json.loads(response.read())
    try:
        assert send('GET', **{'X-Hanni-Token': ''})[0] == 403
        before = send('GET')[1]
        body = {'id': str(uuid4()), 'mode': 'read_only', 'expected_revision': before['revision']}
        assert send('POST', body, Origin='https://foreign.invalid')[0] == 403
        assert send('POST', body, **{'X-Hanni-Token': ''})[0] == 403
        status, saved = send('POST', body)
        assert status == 200 and saved['mode'] == 'read_only', saved
        assert send('POST', body) == (status, saved)
        assert send('POST', {**body, 'id': str(uuid4()), 'mode': 'full'})[0] == 400
        assert send('POST', {**body, 'mode': 'full'})[0] == 400
        assert send('GET')[1]['mode'] == 'read_only'
        assert 'desktop-settings' in (tmp_path / 'logs/tool_audit.jsonl').read_text()
    finally:
        client.close()
