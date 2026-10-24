"""Recovery, bounded context, subprocess RPC and separate working contexts."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time

import httpx
import pytest

from hanni.hermes.state import TaskStore
from hanni.native.agent_tools import AgentTools, agent_tool_specs
from hanni.native.code_execution import run_code
from hanni.native.compact import compact, ContextOverflow, estimate_tokens
from hanni.native.loop import run_loop
from hanni.native.runtime import ToolRuntime
from hanni.native.skill_store import SkillStore


def payload(prompt='Inspect and verify', **context):
    return {'origin': 'hanni', 'prompt': prompt, 'context': context, 'windows_tools': []}


def spec(name='inspect'):
    return {'name': name, 'target': 'local', 'hash': 'test', 'remote': {}, 'schema': {
        'type': 'function', 'function': {'name': name, 'parameters': {
            'type': 'object', 'properties': {'value': {'type': 'integer'}}, 'additionalProperties': False}}}}


def reply(content='', calls=None):
    return {'message': {'content': content, **({'tool_calls': calls} if calls else {})}}


def call(name='inspect', call_id='one'):
    return {'id': call_id, 'type': 'function', 'function': {'name': name, 'arguments': '{}'}}


def test_transient_provider_failure_does_not_reexecute_write():
    actions, observations = [], []
    replies = iter([reply(calls=[call()]), httpx.ConnectError('temporarily down'), reply('Verified')])
    class Client:
        def chat(self, messages, tools):
            observations.append(deepcopy(messages))
            item = next(replies)
            if isinstance(item, Exception):
                raise item
            return item
    result = run_loop(Client(), system_prompt='sys', user_message='fix', tool_specs=[spec()],
                      execute=lambda *args: actions.append(args) or {'ok': True, 'data': 'changed'})
    assert len(actions) == 1 and result['claims'] == 'Verified'
    assert result['stats']['provider_failures'] == 1
    assert observations[1] == observations[2]


def test_tool_exception_is_observation_and_model_can_recover():
    snapshots = []
    class Client:
        def chat(self, messages, tools):
            snapshots.append(deepcopy(messages))
            return reply(calls=[call()]) if len(snapshots) == 1 else reply('Authentication needs renewal')
    def execute(*args):
        response = httpx.Response(401, request=httpx.Request('GET', 'http://fixture'))
        raise httpx.HTTPStatusError('authentication expired', request=response.request, response=response)
    result = run_loop(Client(), system_prompt='s', user_message='calendar', tool_specs=[spec()], execute=execute)
    receipt = json.loads(snapshots[-1][-1]['content'])['untrusted_observation']
    assert receipt['error_code'] == 'authentication_expired' and receipt['effects'] == 'unknown'
    assert result['claims'] == 'Authentication needs renewal'


def test_cancellation_between_calls_keeps_pairs_and_skips_second_effect():
    stopped, actions, checkpoints = [False], [], []
    class Client:
        def chat(self, *_):
            return reply(calls=[call(call_id='a'), call(call_id='b')])
    def execute(*args):
        actions.append(args)
        stopped[0] = True
        return {'ok': True}
    result = run_loop(Client(), system_prompt='s', user_message='go', tool_specs=[spec()], execute=execute,
                      cancelled=lambda: stopped[0], on_checkpoint=lambda value: checkpoints.append(deepcopy(value)))
    assert len(actions) == 1 and result['stop_reason'] == 'cancelled'
    assert [m['tool_call_id'] for m in checkpoints[-1]['messages'] if m['role'] == 'tool'] == ['a', 'b']


def test_auth_provider_failure_is_not_retried_and_remains_inspectable():
    calls = []
    class Client:
        def chat(self, *_):
            calls.append(1)
            response = httpx.Response(401, request=httpx.Request('POST', 'http://fixture'))
            raise httpx.HTTPStatusError('Expired authentication', request=response.request, response=response)
    result = run_loop(Client(), system_prompt='s', user_message='go', tool_specs=[], execute=lambda *_: None)
    assert len(calls) == 1 and result['stop_reason'] == 'provider_failure'
    assert result['failure']['error_code'] == 'authentication_expired'


def test_compaction_preserves_goal_tool_groups_and_stays_bounded():
    messages = [{'role': 'system', 'content': 'system'}, {'role': 'user', 'content': 'Never delete production; diagnose endpoint'}]
    for index in range(15):
        messages += [{'role': 'assistant', 'tool_calls': [call(call_id=str(index))]},
                     {'role': 'tool', 'tool_call_id': str(index), 'content': 'log' * 1500 + 'failure ID xyz'}]
    class Client:
        def chat(self, messages, tools):
            assert 'Blockers' in messages[0]['content']
            return reply('Goal: diagnose endpoint. Constraints: no deletes. Blockers: failure ID xyz. Next steps: check health.')
    result = compact(messages, Client(), max_tokens=2200)
    assert estimate_tokens(result) <= 2200
    assert 'Never delete production' in result[1]['content']
    ids = {c['id'] for m in result for c in m.get('tool_calls', [])}
    assert ids == {m['tool_call_id'] for m in result if m['role'] == 'tool'}


def test_uncompactable_task_fails_before_provider_call():
    with pytest.raises(ContextOverflow):
        compact([{'role': 'system', 'content': 's' * 8000}, {'role': 'user', 'content': 'x' * 8000}], None, max_tokens=1000)


def test_long_unicode_history_and_retry_receipts_fit_bridge_package(tmp_path):
    from hanni.native.context_budget import transfer_context
    context = {'conversation_summary': '\u4f1a\u8bae' * 12000, 'regenerate_only': True,
               'previous_receipts_task_id': 'prior', 'previous_tool_receipts': [{'ok': True, 'data': '\U0001f642' * 20000}],
               'conversation': [{'role': 'user', 'text': '\u7b56\u7565' * 4000} for _ in range(10)]}
    bounded = transfer_context(context)
    assert bounded['regenerate_only'] and bounded['previous_receipts_task_id'] == 'prior'
    assert bounded['context_transfer_excerpt'] and len(json.dumps(bounded)) <= 34000
    assert len(context['conversation']) == 10
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    try:
        assert store.submit('unicode', payload('\u4f1a' * 4000, **bounded))['state'] == 'queued'
    finally:
        store.close()


def test_registry_validates_before_dispatch_and_contains_handler_errors():
    calls = []
    runtime = ToolRuntime([spec()], lambda *args: calls.append(args) or {'ok': True})
    assert runtime.call('inspect', {'value': 'bad'}, '1')['error_code'] == 'invalid_arguments'
    assert runtime.call('unscoped', {}, '2')['error_code'] == 'unavailable'
    assert not calls
    assert runtime.call('inspect', {'value': 2}, '3')['ok']


def test_real_subprocess_tool_rpc_filters_intermediate_output(tmp_path):
    calls = []
    runtime = ToolRuntime([spec()], lambda name, args, key: calls.append((args, key)) or {'ok': True, 'data': args['value'] * 2})
    code = "from hanni_tools import call\nvalues=[call('inspect', {'value': i})['data'] for i in range(3)]\nprint(sum(values))\n"
    result = run_code(code, runtime=runtime, call_id='script', workspace=tmp_path, cancelled=lambda: False)
    assert result['ok'] and result['data']['stdout'].strip() == '6'
    assert len(calls) == 3 and result['data']['tool_calls'] == 3
    assert len({key for args, key in calls}) == 3


def test_real_subprocess_cannot_bypass_scope_or_schema(tmp_path):
    calls = []
    runtime = ToolRuntime([spec()], lambda *args: calls.append(args) or {'ok': True})
    result = run_code("from hanni_tools import call\nprint(call('missing', {}))\nprint(call('inspect', {'value':'bad'}))",
                      runtime=runtime, call_id='limited', workspace=tmp_path, cancelled=lambda: False)
    assert result['ok'] and not calls
    assert 'unavailable' in result['data']['stdout'] and 'invalid_arguments' in result['data']['stdout']


def test_script_timeout_is_enforced(tmp_path):
    result = run_code('import time; time.sleep(30)', runtime=None, call_id='timeout', workspace=tmp_path,
                      cancelled=lambda: False, timeout=.15)
    assert not result['ok'] and result['message'] == 'time_limit'


def test_script_timeout_rejects_unapproved_rpc_instead_of_executing_later(tmp_path):
    from hanni.native.local_tools import await_local
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    task = store.submit('script', payload())
    actions = []
    def dispatch(name, arguments, key):
        action = store.request_action(task['id'], key, spec(), arguments)
        actions.append(action['id'])
        return await_local(store, task['id'], action, tmp_path)
    try:
        runtime = ToolRuntime([spec()], dispatch)
        result = run_code("from hanni_tools import call\ncall('inspect', {})", runtime=runtime, call_id='waiting',
                          workspace=tmp_path, cancelled=lambda: False, timeout=.8)
        assert not result['ok'] and result['message'] == 'time_limit'
        assert len(actions) == 1 and store.action(actions[0])['state'] == 'rejected'
        assert store.action(actions[0])['receipt']['effects'] == 'none'
    finally:
        store.close()


@pytest.fixture
def agent(tmp_path):
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    task = store.submit('parent', payload(conversation_id='session', local_runtime={'auto_approve': ['inspect']}))
    value = AgentTools(store, task, [*agent_tool_specs(), spec()], cancelled=lambda: False)
    yield value
    store.close()


def test_child_has_separate_context_and_inherits_only_scoped_tools(agent):
    assert agent.workspace == agent.root / 'workspace'
    result = agent.execute('delegate_task', {'task': 'Check endpoint', 'tools': ['inspect'], 'context': 'Only status, no credentials'}, 'child')
    child = agent.store.get(result['data']['job_id'])
    assert child['request']['context']['allowed_tools'] == ['inspect']
    assert child['request']['context']['local_runtime'] == agent.task['request']['context']['local_runtime']
    assert 'conversation' not in child['request']['context']
    child_agent = AgentTools(agent.store, child, [spec()], cancelled=lambda: False)
    assert child_agent.workspace != agent.workspace
    with pytest.raises(ValueError, match='Nested'):
        child_agent.execute('delegate_task', {'task': 'nest', 'tools': []}, 'nested')
    with pytest.raises(ValueError, match='subset'):
        agent.execute('delegate_task', {'task': 'escalate', 'tools': ['unknown']}, 'bad')
    agent.store.event(child['id'], 'Done', state='review_required', result={'model_claims': 'Endpoint responded 200'})
    assert agent.execute('agent_job', {'id': child['id'], 'action': 'result'}, 'result')['data']['summary'] == 'Endpoint responded 200'
    assert agent.store.background_results(agent.task['id'])[0]['summary'] == 'Endpoint responded 200'
    other = agent.store.submit('other', payload(conversation_id='other'))
    assert not agent.store.background_results(other['id'])


def test_cancel_parent_cancels_owned_children_only(agent):
    child = agent.execute('delegate_task', {'task': 'go', 'tools': []}, 'one')['data']['job_id']
    other = agent.store.submit('other', payload())
    agent.store.cancel(agent.task['id'])
    assert agent.store.get(child)['state'] == 'cancelled'
    assert agent.store.get(other['id'])['state'] == 'queued'


def test_checkpoint_journal_survives_reopen_and_is_not_personal_memory(agent):
    result = agent.execute('working_state', {'blockers': 'Endpoint unavailable', 'next_steps': 'Check model listing'}, 'state')
    assert result['ok']
    reopened = TaskStore(agent.store.path)
    try:
        assert reopened.checkpoint(agent.task['id'])['journal']['blockers'] == 'Endpoint unavailable'
        assert not (agent.root / 'memory.sqlite3').exists()
    finally:
        reopened.close()


def test_external_memory_requires_configured_read_only_registered_tool(agent):
    missing = agent.execute('memory_search', {'query': 'status', 'provider': 'company'}, 'memory')
    assert missing['error_code'] == 'provider_unavailable'
    remote = {**spec('company_search'), 'target': 'mcp', 'remote': {'classification': 'read_only'}}
    agent.specs.append(remote)
    calls = []
    agent.runtime = ToolRuntime(agent.specs, lambda *args: calls.append(args) or {'ok': True, 'data': 'external evidence'})
    (agent.root / 'memory-providers.json').write_text(json.dumps({'company': {'tool': 'company_search', 'query_parameter': 'query'}}))
    # Correct the fixture schema to match this provider's actual query shape.
    remote['schema']['function']['parameters'] = {'type': 'object', 'properties': {'query': {'type': 'string'}}}
    result = agent.execute('memory_search', {'query': 'status', 'provider': 'company'}, 'memory')
    assert result['ok'] and calls == [('company_search', {'query': 'status'}, 'memory:provider')]


def test_worker_executes_inspect_change_test_with_fresh_readbacks(tmp_path, monkeypatch):
    from hanni.native import worker
    monkeypatch.setenv('HANNI_SKILLS_DIR', str(tmp_path / 'bundled'))
    monkeypatch.delenv('HANNI_DASHBOARD_URL', raising=False)
    monkeypatch.setattr(worker, 'load_soul', lambda: '')
    monkeypatch.setattr(worker, 'load_model', lambda: {'context_length': 65536})
    observations = []
    sequence = [('local_read_file', {'path': 'config.txt'}),
                ('local_write_file', {'path': 'config.txt', 'content': 'corrected'}),
                ('local_read_file', {'path': 'config.txt'})]
    class Client:
        max_tokens = 256
        config = {'context_length': 65536}
        def __init__(self, *_):
            self.index = 0
        def chat(self, messages, tools):
            observations.append(deepcopy(messages))
            if self.index == len(sequence):
                return reply('Readback confirms corrected configuration')
            name, args = sequence[self.index]
            self.index += 1
            item = call(name, str(self.index))
            item['function']['arguments'] = json.dumps(args)
            return reply(calls=[item])
    monkeypatch.setattr(worker, 'NativeClient', Client)
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    (workspace / 'config.txt').write_text('broken')
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    task = store.submit('repair', payload(local_runtime={'auto_approve': ['local_read_file', 'local_write_file']}))
    try:
        worker.run(store.path, task['id'], {'entries': []})
        completed = store.get(task['id'])
        assert completed['state'] == 'review_required', completed
        reads = [a['receipt']['data']['content'] for a in completed['actions'] if a['spec']['name'] == 'local_read_file']
        assert reads == ['broken', 'corrected']
        assert len(observations) == 4
        assert store.checkpoint(task['id'])['messages'][-1]['content'] == 'Readback confirms corrected configuration'
    finally:
        store.close()


@pytest.mark.parametrize('code,expected_created', [('not_connected', False), ('api_error', None)])
def test_calendar_failure_distinguishes_expired_auth_from_uncertain_creation(code, expected_created):
    from hanni.tools.google_access import GoogleAccess, GoogleAccessError, definitions
    from tests.unit.test_google_access import Vault
    access = GoogleAccess(Vault())
    def post(*args):
        raise GoogleAccessError('Authentication expired' if code == 'not_connected' else 'Response lost', code)
    access._post = post
    definition = next(d for d in definitions(access) if d.name == 'google_calendar.create')
    args = {'account': 'personal', 'summary': 'Fixture event',
            'start': '2026-10-25T09:00:00-05:00', 'end': '2026-10-25T09:30:00-05:00'}
    result = definition.handler(args, None, None).to_dict()
    assert not result['ok'] and result['data']['created'] is expected_created
    assert not result['error']['retryable']
    assert result['data']['outcome'] == ('unknown' if expected_created is None else 'failed')


def test_skill_update_requires_exact_revision_and_is_progressive(tmp_path, monkeypatch):
    monkeypatch.setenv('HANNI_SKILLS_DIR', str(tmp_path / 'bundled'))
    store = SkillStore(tmp_path)
    args = dict(name='endpoint-check', description='Diagnose a service endpoint', instructions='Read health, compare models, verify completion.',
                triggers=['endpoint'], expected_revision='', verification='Health returned 200', correction='Use advertised ID')
    first = store.save(**args)
    assert first['ok']
    assert 'body' not in store.catalog()[0]
    read = store.read('endpoint-check')
    with pytest.raises(ValueError, match='changed'):
        store.save(**args)
    args.update(expected_revision=read['revision'], instructions='Check health, then models, then completion.')
    assert store.save(**args)['data']['revision'] != read['revision']
    with pytest.raises(ValueError):
        store.read('endpoint-check', '../elsewhere.md')


def test_restart_preserves_queued_work_and_quarantines_unacknowledged_dispatch(agent):
    queued = agent.store.submit('queued', payload())
    agent.store.event(agent.task['id'], 'Running', state='running')
    action = agent.store.request_action(agent.task['id'], 'dispatch', spec(), {})
    agent.store.settle(action['id'], 'dispatching')
    recovered = TaskStore(agent.store.path, recover=True)
    try:
        assert recovered.get(queued['id'])['state'] == 'queued'
        assert recovered.get(agent.task['id'])['state'] == 'interrupted'
        assert recovered.action(action['id'])['state'] == 'uncertain'
    finally:
        recovered.close()


def test_background_approval_does_not_block_foreground_worker(tmp_path, monkeypatch):
    from hanni.hermes.service import Bridge
    monkeypatch.setattr('hanni.native.model_settings.ModelSettings.pending', lambda *_: False)
    fixture = tmp_path / 'worker.py'
    fixture.write_text("import sys,time\nfrom hanni.hermes.state import TaskStore\ns=TaskStore(sys.argv[1]); t=s.get(sys.argv[2])\nif t['key'].startswith('cron-'):\n s.event(t['id'],'Waiting',state='approval'); time.sleep(30)\nelse:\n s.event(t['id'],'Done',state='review_required',result={'model_claims':'foreground done'})\ns.close()\n")
    token = tmp_path / 'token'
    token.write_text('a' * 40)
    bridge = Bridge(tmp_path / 'bridge', tmp_path / 'config', token, worker_command=[sys.executable, str(fixture)])
    background = bridge.store.submit('cron-background', payload())
    foreground = bridge.store.submit('chat-foreground', payload())
    bridge.thread.start()
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if (bridge.store.get(foreground['id'])['state'] == 'review_required'
                    and bridge.store.get(background['id'])['state'] == 'approval'):
                break
            time.sleep(.05)
        assert bridge.store.get(foreground['id'])['state'] == 'review_required'
        assert bridge.store.get(background['id'])['state'] == 'approval'
        assert len(bridge.children) <= 4
    finally:
        bridge.close()
