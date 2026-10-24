"""Persistent schedules, DST, bounded repeat execution, and conversation delivery."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
import time
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from hanni.dashboard.bridge_panel import cron_create
from hanni.dashboard.chat import ChatHub
from hanni.dashboard.native_chat import NativeChat
from hanni.hermes.state import TaskStore
from hanni.native.agent_tools import AgentTools, agent_tool_specs
from hanni.native.cron import CronStore, READ_TOOLS, next_run, submit_due
from hanni.native.scheduling import create_schedule, manage_schedules
from hanni.native.skills import load_skills, match_skills
from tests.unit.test_chat_commands import commands, command, wait_command
from tests.unit.test_dashboard_chat import chat_server, send


def stamp(text):
    return datetime.fromisoformat(text).timestamp()


def test_daily_and_weekly_follow_local_wall_time_across_dst():
    spring = next_run('daily', 3600, '09:00', 'America/Chicago', 0, stamp('2026-03-07T10:00:00-06:00'))
    assert datetime.fromtimestamp(spring, ZoneInfo('America/Chicago')).isoformat() == '2026-03-08T09:00:00-05:00'
    skipped = next_run('daily', 3600, '02:30', 'America/Chicago', 0, stamp('2026-03-07T03:00:00-06:00'))
    assert datetime.fromtimestamp(skipped, ZoneInfo('America/Chicago')).isoformat() == '2026-03-08T03:00:00-05:00'
    first = stamp('2026-11-01T01:30:00-05:00')
    following = next_run('daily', 3600, '01:30', 'America/Chicago', 0, first, previous=first)
    assert datetime.fromtimestamp(following, ZoneInfo('America/Chicago')).isoformat() == '2026-11-02T01:30:00-06:00'
    weekly = next_run('weekly', 3600, '09:00', 'America/Chicago', 0, stamp('2026-10-25T12:00:00-05:00'))
    assert datetime.fromtimestamp(weekly, ZoneInfo('America/Chicago')).isoformat() == '2026-10-26T09:00:00-05:00'


def test_old_cron_store_migrates_without_losing_jobs(tmp_path):
    path = tmp_path / 'cron.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,prompt TEXT,interval_seconds INTEGER,auto_approve TEXT,enabled INTEGER,next_run REAL,last_task_id TEXT,created_at REAL)')
        db.execute("INSERT INTO jobs VALUES('legacy','Check status',3600,'[]',0,123,NULL,100)")
    store = CronStore(path)
    job = store.get('legacy')
    assert job['prompt'] == 'Check status' and job['enabled'] == 0 and job['next_run'] == 123
    assert job['cadence'] == 'interval' and job['conversation'] == 'default'
    assert not store.pending_runs()


def test_persistent_creation_is_idempotent_and_does_not_duplicate_after_restart(tmp_path):
    args = dict(title='AI news', prompt='Search current AI news with sources', frequency='daily', timezone='America/Chicago')
    first = create_schedule(tmp_path, args, conversation='default', request_key='same-request')
    again = create_schedule(tmp_path, args, conversation='default', request_key='same-request')
    assert first == again and first['auto_approve'] == list(READ_TOOLS)
    assert 'local_python' not in first['auto_approve'] and '*' not in first['auto_approve']
    assert len(CronStore(tmp_path / 'cron.sqlite3').list()) == 1
    with pytest.raises(ValueError, match='different settings'):
        create_schedule(tmp_path, {**args, 'prompt': 'Changed task'}, conversation='default', request_key='same-request')
    manage_schedules(tmp_path, 'pause', first['id'])
    assert not CronStore(tmp_path / 'cron.sqlite3').get(first['id'])['enabled']
    manage_schedules(tmp_path, 'resume', first['id'])
    assert CronStore(tmp_path / 'cron.sqlite3').get(first['id'])['enabled']
    manage_schedules(tmp_path, 'delete', first['id'])
    assert not manage_schedules(tmp_path, 'list')['jobs']
    with pytest.raises(ValueError, match='deleted'):
        create_schedule(tmp_path, args, conversation='default', request_key='same-request')


@pytest.mark.parametrize('settings', [dict(frequency='yearly'), dict(frequency=[]), dict(at_time='25:00'),
    dict(timezone='Not/AZone'), dict(weekday=7), dict(interval_seconds=1), dict(interval_seconds=True),
    dict(prompt=''), dict(auto_approve=['*'])])
def test_invalid_settings_cannot_create_jobs(tmp_path, settings):
    with pytest.raises(ValueError):
        create_schedule(tmp_path, {'prompt': 'Task', 'title': 'Test', **settings}, conversation='default', request_key='invalid')
    path = tmp_path / 'cron.sqlite3'
    assert not path.exists() or not CronStore(path).list()


def test_missed_runs_catch_up_once_and_do_not_overlap(tmp_path):
    cron = CronStore(tmp_path / 'cron.sqlite3'); tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    job = cron.add('Search current sources and return a digest', 60, READ_TOOLS, title='AI news')
    past = time.time() - 86400
    with cron._tx() as db: db.execute('UPDATE jobs SET next_run=? WHERE id=?', (past, job))
    run = submit_due(cron, tasks, time.time())[0]
    assert len(tasks.list()) == 1 and not submit_due(cron, tasks, time.time())
    assert tasks.get(run)['request']['context']['scheduled_job_id'] == job
    assert cron.pending_runs()[0]['task_id'] == run
    with cron._tx() as db: db.execute('UPDATE jobs SET next_run=? WHERE id=?', (past, job))
    assert not submit_due(cron, tasks, time.time())  # prior run still queued
    tasks.event(run, 'Done', state='review_required', result={'model_claims': 'First digest'})
    assert submit_due(cron, tasks, time.time())[0] == run  # crash recovery of same slot remains idempotent
    tasks.db.close()


def test_scheduled_results_are_isolated_idempotent_and_do_not_block_foreground_chat(tmp_path):
    hub = ChatHub(tmp_path / 'chat.sqlite3'); hub.ready = True
    conversation = hub.create_conversation(str(uuid4()))
    run = {'conversation': conversation, 'title': 'AI news'}
    task = {'id': 'scheduled-task', 'state': 'approval', 'result': None}
    try:
        assert hub.scheduled_result(run, task)
        rows = hub.snapshot(conversation=conversation)['messages']
        assert len(rows) == 2 and rows[1]['task_id'] == task['id']
        assert rows[1]['status'] == 'working' and rows[1]['channel'] == 'scheduled'
        assert not hub.snapshot()['busy'] and not hub.snapshot(conversation='default')['messages']
        hub.submit(str(uuid4()), 'Foreground message', 'default')
        hub.take(); row = hub.begin('Foreground message', 'browser')
        task.update(state='review_required', result={'model_claims': 'Five sourced headlines'})
        hub.scheduled_result(run, task); hub.scheduled_result(run, task)
        assert hub.current is not None
        hub.update(row, 'Foreground answer', 'complete')
        assert len(hub.snapshot(conversation=conversation)['messages']) == 2
        assert hub.snapshot(conversation=conversation)['messages'][1]['content'] == 'Five sourced headlines'
        hub.close(); hub.db.close()

        hub = ChatHub(tmp_path / 'chat.sqlite3'); hub.ready = True
        hub.scheduled_result(run, task)
        assert len(hub.snapshot(conversation=conversation)['messages']) == 2
        hub.clear(); hub.scheduled_result(run, task)
        assert not hub.snapshot()['messages']  # clearing history cannot resurrect old reports
    finally:
        hub.close(); hub.db.close()


def test_delivery_worker_returns_actual_result_to_chat_once(tmp_path, monkeypatch):
    monkeypatch.setenv('HANNI_CRON_ROOT', str(tmp_path))
    cron = CronStore(tmp_path / 'cron.sqlite3'); tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    identifier = cron.add('Give the current report', 60)
    with cron._tx() as db: db.execute('UPDATE jobs SET next_run=? WHERE id=?', (time.time() - 1, identifier))
    run_id = submit_due(cron, tasks, time.time())[0]
    tasks.event(run_id, 'Finished', state='review_required', result={'model_claims': 'Actual scheduled report'})
    hub = ChatHub(tmp_path / 'chat.sqlite3'); hub.ready = True
    native = NativeChat(hub, threading.Event(), proxy=lambda method, path, body=None: tasks.get(path.split('/')[2]))
    try:
        native.delivery_thread.start()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and cron.pending_runs():
            time.sleep(.05)
        assert not cron.pending_runs()
        messages = hub.snapshot(conversation='default')['messages']
        assert len(messages) == 2 and messages[1]['content'] == 'Actual scheduled report'
        assert messages[1]['task_id'] == run_id
    finally:
        native.close(); hub.close(); hub.db.close(); tasks.db.close()


def test_agent_can_schedule_without_filesystem_and_cannot_reschedule_a_scheduled_run(tmp_path):
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    task = store.submit('create', {'prompt': 'Update me daily on AI news', 'windows_tools': [], 'origin': 'hanni', 'context': {'conversation_id': 'default'}})
    agent = AgentTools(store, task, agent_tool_specs(), cancelled=lambda: False)
    args = {'prompt': 'Search current AI news and cite sources', 'title': 'AI news', 'frequency': 'daily'}
    result = agent.execute('schedule_task', args, 'call-1')
    assert result['ok'] and result['data']['id']
    assert agent.execute('schedule_task', args, 'call-1')['data']['id'] == result['data']['id']
    task['request']['context']['scheduled_job_id'] = 'existing-job'
    with pytest.raises(ValueError, match='once'):
        agent.execute('schedule_task', args, 'call-2')
    assert len(CronStore(tmp_path / 'cron.sqlite3').list()) == 1
    store.db.close()


def test_example_routes_to_recurring_skill_without_code_review():
    text = match_skills(load_skills(metadata_only=True), 'can you update me daily on whats happening in the ai world')
    assert '### skill: recurring-tasks' in text and '### skill: requesting-code-review' not in text


def test_bridge_preserves_explicit_read_only_policy_even_in_auto_mode(tmp_path, monkeypatch):
    from hanni.hermes.service import Bridge
    monkeypatch.setenv('HANNI_AUTO_APPROVE', '1')
    monkeypatch.setenv('HANNI_MODEL_STATE', str(tmp_path))
    bridge = Bridge.__new__(Bridge)
    bridge.lock = threading.RLock(); bridge.store = TaskStore(tmp_path / 'tasks.sqlite3')
    try:
        explicit = bridge.dispatch('POST', '/tasks', {'key': 'restricted', 'task': {
            'prompt': 'Read sources', 'windows_tools': [], 'origin': 'hanni',
            'context': {'local_runtime': {'auto_approve': ['web_search']}}}})
        assert explicit['request']['context']['local_runtime']['auto_approve'] == ['web_search']
        default = bridge.dispatch('POST', '/tasks', {'key': 'default', 'task': {
            'prompt': 'Ordinary chat', 'windows_tools': [], 'origin': 'hanni', 'context': {}}})
        assert default['request']['context']['local_runtime']['auto_approve'] == ['*']
    finally:
        bridge.store.db.close()


@pytest.mark.parametrize('timing,expected', [('weekly fri 14:30', ('weekly', 4, '14:30', 3600)),
    ('hourly', ('interval', 0, '09:00', 3600)), ('every 2 hours', ('interval', 0, '09:00', 7200))])
def test_other_repeat_commands_reach_persistent_schedule(commands, timing, expected):
    result = wait_command(commands, command(commands, '/schedule ' + timing + ' | Read current sources'))
    assert result['ok'], result
    from hanni.dashboard.bridge_panel import cron_root
    job = CronStore(cron_root() / 'cron.sqlite3').list()[0]
    assert (job['cadence'], job['weekday'], job['at_time'], job['interval_seconds']) == expected


def test_schedule_command_creates_real_job_and_can_manage_it(commands, tmp_path, monkeypatch):
    monkeypatch.setenv('HANNI_CRON_ROOT', str(tmp_path / 'cron'))
    key = str(uuid4())
    result = wait_command(commands, command(commands, '/schedule daily 09:00 | Search current AI news with sources', key=key))
    assert result['ok'] and 'Next run' in result['message']
    assert wait_command(commands, command(commands, '/schedule daily 09:00 | Search current AI news with sources', key=key)) == result
    job = CronStore(tmp_path / 'cron/cron.sqlite3').list()[0]
    assert job['conversation'] == 'default' and job['at_time'] == '09:00'
    for operation, enabled in [('pause', 0), ('resume', 1)]:
        assert wait_command(commands, command(commands, f'/schedule {operation} {job["id"]}'))['ok']
        assert CronStore(tmp_path / 'cron/cron.sqlite3').get(job['id'])['enabled'] == enabled
    assert job['id'] in wait_command(commands, command(commands, '/schedule list'))['message']
    assert wait_command(commands, command(commands, f'/schedule delete {job["id"]}'))['ok']
    assert not CronStore(tmp_path / 'cron/cron.sqlite3').list()


def test_schedule_api_is_protected_and_links_a_real_conversation(chat_server, tmp_path, monkeypatch):
    monkeypatch.setenv('HANNI_CRON_ROOT', str(tmp_path / 'cron'))
    chat_server.chat.native_mode = True
    body = {'id': str(uuid4()), 'title': 'AI news', 'prompt': 'Search current sources', 'frequency': 'daily', 'timezone': 'America/Chicago'}
    for headers in [{'X-Hanni-Token': 'wrong'}, {'Origin': 'https://evil.example'}]:
        assert send(chat_server, path='/api/cron/jobs', body=body, headers=headers)[0] == 403
    status, job = send(chat_server, path='/api/cron/jobs', body=body)
    assert status == 200 and job['next_run_local'] and job['conversation'] != 'default'
    assert send(chat_server, path='/api/cron/jobs', body=body) == (status, job)
    assert any(c['id'] == job['conversation'] and c['title'] == 'AI news' for c in chat_server.chat.conversations())
    assert send(chat_server, path=f'/api/cron/job/{job["id"]}/disable', body={})[0] == 200
    assert send(chat_server, path=f'/api/cron/job/{job["id"]}/delete', body={})[0] == 200
    assert not CronStore(tmp_path / 'cron/cron.sqlite3').list()
