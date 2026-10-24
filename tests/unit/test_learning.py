"""Real local learning, staging, lifecycle and training boundaries; isolated model only."""
import http.client
import json
from pathlib import Path
import sqlite3
import threading
import time
from types import SimpleNamespace
from uuid import uuid4
import pytest

from hanni.dashboard.chat import ChatHub
from hanni.memory.store import MemoryStore
from hanni.native.learning import LearningReview, DEFAULTS
from hanni.native.skill_store import SkillStore
from hanni.native.training import TrainingStore, BATCH_TOOLS, atropos_group, trajectory
from hanni.hermes.state import TaskStore


def procedure(name='endpoint-check', **changes):
    return {'name': name, 'description': 'Diagnose the service endpoint', 'instructions': '1. Read /health.\n2. Use the model ID from /v1/models.\n3. Verify a completion.\nPitfall: a display name is not an API ID.',
            'triggers': ['endpoint', 'model ID'], 'expected_revision': '', 'verification': 'Health and completion succeeded in the recorded run.',
            'correction': 'Use the advertised model ID.', **changes}


@pytest.fixture(autouse=True)
def isolated_skills(tmp_path, monkeypatch):
    monkeypatch.setenv('HANNI_SKILLS_DIR', str(tmp_path / 'bundled'))


@pytest.fixture
def review(tmp_path):
    hub = ChatHub(tmp_path / 'dashboard-chat.sqlite3'); hub.ready = True; hub.native_mode = True
    user = hub._add('one', 'user', 'I prefer short status updates. The model ID must come from /v1/models.', 'browser', 'complete')
    assistant = hub._add('one', 'assistant', 'The advertised model ID returned a successful completion.', 'browser', 'complete')
    gate, entered = threading.Event(), threading.Event()
    captures = []; output = {'skills': [], 'memories': []}
    class Client:
        def __init__(self, model, timeout): pass
        def chat(self, messages, tools=None):
            assert tools is None
            captures.append(json.loads(messages[-1]['content'])); entered.set()
            assert gate.wait(5), 'Test did not release review model'
            return {'message': {'content': json.dumps(output)}}
    memory = MemoryStore(tmp_path / 'memory.sqlite3')
    engine = LearningReview(tmp_path, hub, memory_store=lambda: memory, model_loader=lambda: {}, client_factory=Client)
    yield SimpleNamespace(engine=engine, hub=hub, memory=memory, output=output, gate=gate, entered=entered, captures=captures, user=user, assistant=assistant)
    engine.close(); gate.set()
    for thread, _ in list(engine.workers.values()): thread.join(3)
    hub.close(); hub.db.close()


def finished(engine):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        runs = engine.runs()
        if runs and runs[0]['state'] != 'running': return runs[0]
        time.sleep(.01)
    pytest.fail('Review did not finish')


def test_staged_diff_is_inactive_versioned_and_persistent(tmp_path):
    store = SkillStore(tmp_path)
    p = store.stage(procedure(), source='task:fixture')
    assert '+1. Read /health.' in p['diff'] and not store.catalog()
    assert store.stage(procedure())['id'] == p['id']
    with pytest.raises(ValueError): store.review(p['id'], 'wrong', 'accept')
    store.review(p['id'], p['revision'], 'accept')
    detail = store.detail('endpoint-check')
    assert detail['revision'] and detail['history'][0]['verification']
    assert store.review(p['id'], p['revision'], 'accept')['status'] == 'accepted'
    update = store.stage(procedure(expected_revision=detail['revision'], instructions='Use the verified model ID; retry health only.'))
    store.save(**procedure(expected_revision=detail['revision'], instructions='New owner correction.'))
    with pytest.raises(ValueError, match='changed'): store.review(update['id'], update['revision'], 'accept')
    reopened = SkillStore(tmp_path)
    assert reopened.detail('endpoint-check')['instructions'] == 'New owner correction.'
    assert {'created', 'proposed', 'accepted', 'updated'} <= {r['action'] for r in reopened.journey()}


def test_curator_protects_bundled_pinned_and_schedule_references_and_restores_packages(tmp_path):
    store = SkillStore(tmp_path)
    for name in ('unused', 'pinned', 'scheduled'): store.save(**procedure(name))
    (tmp_path / 'skills/unused/references').mkdir(); (tmp_path / 'skills/unused/references/checks.md').write_text('Retained checks')
    store.lifecycle('pinned', store.detail('pinned')['revision'], 'pin')
    now = time.time() + 15 * 86400
    preview = store.curate(now=now, protected={'scheduled'}, dry_run=True)
    assert preview['changes'] == [{'name': 'unused', 'from': 'active', 'to': 'stale'}]
    assert all(s['state'] == 'active' for s in store.catalog())
    store.curate(now=now, protected={'scheduled'})
    assert next(s for s in store.catalog() if s['name'] == 'unused')['state'] == 'stale'
    result = store.curate(now=time.time() + 31 * 86400, protected={'scheduled'})
    assert result['deletes'] == 0 and {s['name'] for s in store.catalog()} == {'pinned', 'scheduled'}
    store.lifecycle('unused', store.detail('unused')['revision'], 'restore')
    assert store.read('unused', 'references/checks.md')['content'] == 'Retained checks'
    store.track('unused', 'use', source='one'); store.track('unused', 'use', source='one')
    assert next(s for s in store.inventory() if s['name'] == 'unused')['uses'] == 1


def test_consolidation_is_staged_recoverable_and_rechecks_protection(tmp_path):
    store = SkillStore(tmp_path)
    store.save(**procedure('endpoint-a')); store.save(**procedure('endpoint-b'))
    absorbs = [{'name': n, 'revision': store.detail(n)['revision']} for n in ('endpoint-a', 'endpoint-b')]
    proposal = store.stage(procedure('endpoint-workflow'), absorbs=absorbs)
    with pytest.raises(ValueError, match='protected'): store.review(proposal['id'], proposal['revision'], 'accept', protected={'endpoint-a'})
    assert len(store.catalog()) == 2
    store.review(proposal['id'], proposal['revision'], 'accept')
    assert [s['name'] for s in store.catalog()] == ['endpoint-workflow']
    assert (tmp_path / 'skills/endpoint-a/SKILL.md').exists()
    store.lifecycle('endpoint-a', absorbs[0]['revision'], 'restore')
    support = tmp_path / 'skills/endpoint-a/references'; support.mkdir(); (support/'notes.md').write_text('Do not flatten')
    with pytest.raises(ValueError, match='standalone'): store.stage(procedure('merged'), absorbs=absorbs[:1])


def test_review_uses_immutable_snapshot_and_stages_distinct_knowledge_homes(review):
    r = review
    r.output['skills'] = [{**procedure(), 'source_ids': [r.user, r.assistant]}]
    r.output['memories'] = [{'content': 'I prefer short status updates.', 'source_ids': [r.user], 'target_id': ''}]
    before = r.hub.snapshot()['messages']
    run = r.engine.begin('default', key='snapshot-one')
    assert r.entered.wait(2)
    r.hub._add('two', 'user', 'New task while the review is running', 'browser', 'complete')
    r.gate.set()
    result = finished(r.engine)
    assert result['state'] == 'complete', result
    assert r.hub.snapshot()['messages'][:2] == before
    assert len(r.captures[0]['messages']) == 2
    assert not r.engine.skills.catalog() and not r.memory.list()
    assert len(r.engine.skills.proposals()) == 1 and len(r.memory.suggestions()) == 1
    p = r.engine.skills.proposals()[0]
    r.engine.skills.review(p['id'], p['revision'], 'accept')
    memory = r.memory.suggestions()[0]
    r.memory.review_suggestion(memory.id, 'approve', expected_updated_at=memory.updated_at.isoformat())
    assert len(r.engine.skills.catalog()) == 1 and r.memory.list()[0].content == 'I prefer short status updates.'
    assert r.engine.begin('default', key='snapshot-one')['id'] == run['id']
    with r.engine._db() as db:
        assert db.execute('SELECT through_id FROM watermarks').fetchone()[0] == r.assistant


@pytest.mark.parametrize('bad', ['unknown-source', 'assistant-memory', 'secret', 'invalid-shape'])
def test_untrusted_model_output_cannot_activate_or_invent_memory_sources(review, bad):
    r = review
    if bad == 'unknown-source': r.output['skills'] = [{**procedure(), 'source_ids': [999999]}]
    elif bad == 'assistant-memory': r.output['memories'] = [{'content': 'Invented personal preference', 'source_ids': [r.assistant], 'target_id': ''}]
    elif bad == 'secret': r.output['skills'] = [{**procedure(instructions='Use password=fixture-private-secret'), 'source_ids': [r.user]}]
    else: r.output['skills'] = [{'instructions': 'Incomplete procedure'}]
    r.engine.begin('default'); r.gate.set()
    assert finished(r.engine)['state'] == 'failed'
    assert not r.engine.skills.catalog() and not r.engine.skills.proposals() and not r.memory.suggestions()


def test_cancellation_and_close_refuse_late_proposals(review):
    r = review; r.output['skills'] = [{**procedure(), 'source_ids': [r.user]}]
    run = r.engine.begin('default'); assert r.entered.wait(2)
    r.engine.cancel(run['id']); r.gate.set()
    assert finished(r.engine)['state'] == 'cancelled'
    assert not r.engine.skills.proposals()
    r.gate.clear(); r.engine.begin('default'); r.engine.close(); r.gate.set()
    assert finished(r.engine)['state'] == 'cancelled' and not r.engine.skills.proposals()


def test_background_threshold_watermark_and_cooldown_survive_restart(review):
    r = review
    cfg = {**DEFAULTS, 'exchange_threshold': 2, 'cooldown_seconds': 60}
    r.engine.configure(cfg, r.engine.settings()['revision'])
    r.engine.tick(); assert not r.engine.runs()
    r.hub._add('two', 'user', 'Second request', 'browser', 'complete')
    r.hub._add('two', 'assistant', 'Second answer', 'browser', 'complete')
    r.engine.tick(); assert not r.engine.runs()
    r.hub._add('three', 'user', 'Third request', 'browser', 'complete')
    r.hub._add('three', 'assistant', 'Third answer', 'browser', 'complete')
    r.engine.tick(); assert r.entered.wait(2)
    r.engine.tick(); assert len(r.engine.runs()) == 1
    r.gate.set(); assert finished(r.engine)['state'] == 'complete'
    r.engine.tick(); assert len(r.engine.runs()) == 1
    with pytest.raises(ValueError, match='changed'): r.engine.configure(DEFAULTS, 'old')
    r.engine.close()
    other = LearningReview(r.engine.root, r.hub, memory_store=lambda: r.memory, model_loader=lambda: {})
    try:
        other.tick(); assert len(other.runs()) == 1
        assert other.settings()['exchange_threshold'] == 2
    finally: other.close()


def test_paused_schedules_protect_referenced_skills(review):
    from hanni.native.cron import CronStore
    r = review; r.engine.skills.save(**procedure())
    cron = CronStore(r.engine.root / 'cron.sqlite3')
    key = cron.add('Use endpoint-check to diagnose the model endpoint')
    with sqlite3.connect(cron.path) as db: db.execute('UPDATE jobs SET enabled=0 WHERE id=?', (key,))
    assert r.engine.protected_skills() == {'endpoint-check'}
    assert r.engine.skills.curate(now=time.time()+100*86400, protected=r.engine.protected_skills())['changes'] == []


def test_batch_scopes_idempotency_export_pairing_and_redaction(tmp_path):
    training = TrainingStore(tmp_path)
    batch = training.submit('test-batch', ['Inspect endpoint', 'Summarize report'])
    assert training.submit('test-batch', ['Inspect endpoint', 'Summarize report'])['task_ids'] == batch['task_ids']
    with pytest.raises(ValueError): training.submit('test-batch', ['Different task'])
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    try:
        key = batch['task_ids'][0]
        task = store.get(key)
        assert set(task['request']['context']['allowed_tools']) == set(BATCH_TOOLS)
        assert not {'local_write_file', 'execute_code', 'delegate_task', 'skill_save'} & set(BATCH_TOOLS)
        messages = [{'role': 'system', 'content': 'Hidden system prompt'}, {'role': 'user', 'content': 'Inspect endpoint'},
                    {'role': 'assistant', 'content': None, 'reasoning_content': 'Private analysis', 'tool_calls': [{'id': 'ok', 'type': 'function', 'function': {'name': 'inspect', 'arguments': '{"password":"private-fixture-secret"}'}}]},
                    {'role': 'tool', 'tool_call_id': 'ok', 'content': '{"ok":true,"refresh_token":"fixture-refresh"}'},
                    {'role': 'assistant', 'tool_calls': [{'id': 'orphan', 'function': {'name': 'inspect', 'arguments': '{}'}}]},
                    {'role': 'assistant', 'content': '<think>Private reasoning</think>Health is ready.'}]
        store.checkpoint(key, {'messages': messages}); store.event(key, 'Finished', state='review_required', result={'model_claims': 'Health ready'})
        row = trajectory(store, key)
        assert [m['role'] for m in row['messages']] == ['user', 'assistant', 'tool', 'assistant']
        serialized = json.dumps(row)
        assert not any(secret in serialized for secret in ('Hidden system prompt', 'Private reasoning', 'Private analysis', 'private-fixture-secret', 'fixture-refresh', 'orphan'))
        assert row['reward'] is None and row['verified_success'] is False
        assert training.export(batch['id'])['count'] == 1
        assert 'conversations' in json.loads(training.export(batch['id'], 'sharegpt')['content'])
    finally: store.close()
    training.cancel(batch['id'])
    assert all(t['state'] in {'review_required', 'cancelled'} for t in training.batches()['batches'][0]['tasks'])


def test_actual_batch_worker_cannot_execute_a_write(tmp_path, monkeypatch):
    from hanni.native import worker
    from tests.unit.test_agent_runtime import reply, call
    training = TrainingStore(tmp_path); batch = training.submit('scope-test', ['Try writing then explain'])
    calls = []
    class Client:
        max_tokens = 100
        def __init__(self, model): pass
        def chat(self, messages, tools=None):
            calls.append(messages[:])
            return reply(calls=[call('local_write_file')]) if len(calls) == 1 else reply('Writing is outside this batch scope.')
    monkeypatch.setattr(worker, 'NativeClient', Client)
    monkeypatch.setattr(worker, 'load_model', lambda: {})
    monkeypatch.setattr(worker, 'discover', lambda *a, **k: [])
    monkeypatch.setattr('hanni.native.mcp_client.discover', lambda *a: [])
    worker.run(tmp_path/'tasks.sqlite3', batch['task_ids'][0], {'entries': []})
    assert len(calls) == 2
    assert json.loads(calls[1][-1]['content'])['untrusted_observation']['error_code'] == 'unavailable'
    assert not list((tmp_path/'workspace').rglob('*.txt'))


def test_atropos_bridge_requires_reviewed_rewards_and_exact_token_alignment():
    records = [{'id': 'a', 'messages': [{'role': 'user', 'content': 'Prompt'}, {'role': 'assistant', 'content': 'Answer'}]}]
    class Tokenizer:
        def apply_chat_template(self, messages, add_generation_prompt, **kwargs):
            return [10, 11] if add_generation_prompt else [10, 11, 20, 21]
    with pytest.raises(ValueError, match='reward'): atropos_group(records, {}, Tokenizer())
    group = atropos_group(records, {'a': .75}, Tokenizer())
    assert group['tokens'] == [[10, 11, 20, 21]] and group['masks'] == [[-100, -100, 20, 21]]
    assert group['scores'] == [.75]
    class Invalid:
        def apply_chat_template(self, messages, add_generation_prompt, **kwargs): return [99] if add_generation_prompt else [10, 20]
    with pytest.raises(ValueError, match='prefix'): atropos_group(records, {'a': 1}, Invalid())


def test_learning_http_owner_origin_idempotency_and_private_audit(service, tmp_path):
    conn = http.client.HTTPConnection('127.0.0.1', service.server_port)
    origin = f'http://127.0.0.1:{service.server_port}'
    body = {'id': str(uuid4()), 'operation': 'skill.stage', 'data': procedure(description='Private owner workflow detail')}
    def send(method, path='/api/learning', token=None, origin_value=origin):
        conn.request(method, path, body=json.dumps(body) if method == 'POST' else None,
                     headers={'Content-Type': 'application/json', 'Origin': origin_value, 'X-Hanni-Token': token or ''})
        res = conn.getresponse(); raw = res.read(); return res.status, json.loads(raw)
    try:
        for path in ('/api/learning', '/api/learning/journey', '/api/learning/source?id=unknown', '/api/learning/skill?name=endpoint-check', '/api/learning/export', '/api/learning/batches'):
            assert send('GET', path)[0] == 403
        assert send('POST', token=service.chat.token, origin_value='https://foreign.example')[0] == 403
        status, staged = send('POST', token=service.chat.token)
        assert status == 200, staged
        assert send('POST', token=service.chat.token)[1] == staged
        body['data']['description'] = 'A different request'
        assert send('POST', token=service.chat.token)[0] == 400
        status, state = send('GET', token=service.chat.token)
        assert status == 200 and len(state['proposals']) == 1
        assert not service.learning.engine.skills.catalog()
        log = (tmp_path/'logs/tool_audit.jsonl').read_text()
        assert 'Private owner workflow detail' not in log and '[PRIVATE WORKSPACE DATA]' in log
    finally: conn.close()


def test_learning_commands_and_safe_mode_use_original_authority(service):
    from hanni.dashboard.commands import ChatCommands
    from hanni.core.shutdown import Actor, StopSource
    service.chat.native_mode = True
    service.chat._add('learning', 'user', 'We diagnosed an endpoint.', 'browser', 'complete')
    service.chat._add('learning', 'assistant', 'Use the advertised API ID.', 'browser', 'complete')
    engine = service.learning.engine; gate = threading.Event()
    class Client:
        def __init__(self, model, timeout): pass
        def chat(self, messages, tools=None):
            gate.wait(2); return {'message': {'content': '{"skills":[],"memories":[]}'}}
    engine.client_factory = Client; engine.model_loader = lambda: {}
    def command(text): return service.chat_commands.execute({'id': str(uuid4()), 'command': text, 'conversation': 'default'})
    result = command('/refine endpoint recovery')
    assert result['ok'] and result['learning']['state'] == 'running'
    assert not service.chat.queue and len(service.chat.snapshot()['messages']) == 2
    gate.set(); assert finished(engine)['state'] == 'complete'
    assert 'Learning journey' in command('/journey')['message']
    assert command('/curator dry-run')['ok']
    service.features.registry.context.emergency_stop.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner('test'), reason='test')
    blocked = command('/refine')
    assert not blocked['ok'] and len(engine.runs()) == 1


# Reuse the real authenticated dashboard fixture, not a mocked HTTP boundary.
from tests.unit.test_native_mcp import service


def test_revising_proposal_supersedes_old_diff_and_preserves_baseline(tmp_path):
    store = SkillStore(tmp_path)
    old = store.stage(procedure(), source='review:fixture:messages:1')
    revised = store.stage(procedure(instructions='Read health first, then verify the exact model ID.'), replaces=(old['id'], old['revision']))
    assert [p['id'] for p in store.proposals()] == [revised['id']]
    with pytest.raises(ValueError, match='reviewed'): store.review(old['id'], old['revision'], 'accept')
    store.review(revised['id'], revised['revision'], 'accept')
    assert store.detail('endpoint-check')['instructions'].startswith('Read health first')


def test_bundled_override_keeps_reference_files(tmp_path):
    bundled = tmp_path/'bundled/endpoint-check'
    (bundled/'references').mkdir(parents=True)
    (bundled/'SKILL.md').write_text('---\nname: endpoint-check\ndescription: Diagnose an endpoint\n---\nRead references/checks.md.')
    (bundled/'references/checks.md').write_text('Verify a real completion.')
    store = SkillStore(tmp_path)
    before = store.read('endpoint-check')
    store.save(**procedure(expected_revision=before['revision']))
    assert store.read('endpoint-check', 'references/checks.md')['content'] == 'Verify a real completion.'
    assert (bundled/'SKILL.md').read_text().endswith('Read references/checks.md.')
    assert store.curate(now=time.time()+100*86400)['changes'] == []


@pytest.mark.parametrize('source', ['local', 'api'])
def test_review_provider_uses_constrained_json_without_tools(source, monkeypatch):
    from hanni.native.provider import NativeClient
    client = NativeClient({'endpoint': 'http://127.0.0.1:9999/v1', 'id': 'fixture', 'source': source}, timeout=60)
    calls = []
    def complete(payload, **kwargs):
        calls.append((payload, kwargs)); return {'message': {'content': '{"skills":[],"memories":[]}'}}
    monkeypatch.setattr(client, '_complete', complete)
    assert client.chat_json([{'role': 'user', 'content': 'Review'}], {'type': 'object'})['message']['content']
    payload, options = calls[0]
    assert not payload.get('tools') and options == {'attempts': 1}
    assert payload['response_format']['type'] == ('json_object' if source == 'local' else 'json_schema')
    if source == 'local': assert payload['chat_template_kwargs']['enable_thinking'] is False


def test_review_provider_fallback_requires_an_explicit_format_rejection(monkeypatch):
    import httpx
    from hanni.native.provider import NativeClient
    client = NativeClient({'endpoint': 'http://127.0.0.1:9999/v1', 'id': 'fixture', 'source': 'api'})
    calls = []; status = {'value': 400, 'param': 'response_format'}
    def complete(payload, **kwargs):
        calls.append(payload)
        if 'response_format' in payload:
            response = httpx.Response(status['value'], json={'error': {'param': status['param'], 'message': 'not supported'}}, request=httpx.Request('POST', client.endpoint))
            raise httpx.HTTPStatusError('Rejected', request=response.request, response=response)
        return {'message': {'content': '{"skills":[],"memories":[]}'}}
    monkeypatch.setattr(client, '_complete', complete)
    client.chat_json([], {'type': 'object'})
    assert len(calls) == 2 and 'response_format' not in calls[-1]
    calls.clear(); status.update(value=401, param='authentication')
    with pytest.raises(httpx.HTTPStatusError): client.chat_json([], {'type': 'object'})
    assert len(calls) == 1


def test_memory_journey_keeps_corrections_but_removes_forgotten_content(service):
    memory = service.features.memory_store()
    record, _ = memory.remember('I prefer concise project summaries', source='owner_explicit')
    memory.correct(record.id, 'I prefer detailed project summaries', expected_updated_at=record.updated_at.isoformat())
    items = service.learning.journey()['items']
    assert any(i['text'] == 'I prefer concise project summaries' and i['action'] == 'previous revision' for i in items)
    assert any(i['text'] == 'I prefer detailed project summaries' and i['action'] == 'corrected' for i in items)
    memory.delete(record.id)
    assert not any('project summaries' in i['text'] for i in service.learning.journey()['items'])


def test_partial_matched_skill_heading_cannot_fail_the_actual_worker(tmp_path, monkeypatch):
    from hanni.native import worker
    from tests.unit.test_agent_runtime import reply, payload
    skills = SkillStore(tmp_path)
    skills.save(**procedure('a'*63, instructions='X'*5900))
    skills.save(**procedure('b'*63))
    class Client:
        max_tokens = 100
        def __init__(self, model): pass
        def chat(self, messages, tools=None): return reply('Endpoint explanation complete.')
    monkeypatch.setattr(worker, 'NativeClient', Client)
    monkeypatch.setattr(worker, 'load_model', lambda: {})
    monkeypatch.setattr(worker, 'discover', lambda *a, **k: [])
    monkeypatch.setattr('hanni.native.mcp_client.discover', lambda *a: [])
    store = TaskStore(tmp_path/'tasks.sqlite3')
    task = store.submit('partial-heading', payload(prompt='Explain the endpoint'))
    try:
        worker.run(store.path, task['id'], {'entries': []})
        assert store.get(task['id'])['state'] == 'review_required'
        assert next(s for s in skills.inventory() if s['name'] == 'a'*63)['uses'] == 1
    finally: store.close()
