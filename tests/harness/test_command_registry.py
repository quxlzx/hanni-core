"""Every registered command is exercised through its actual deterministic router."""
from copy import deepcopy
from uuid import uuid4

import pytest

from hanni.dashboard.commands import CATALOG
from tests.unit.test_chat_commands import commands, command

NAMES = [row['name'][1:] for row in CATALOG]
EXPECTED = set('help new history resume retry undo stop status context compress model reasoning voice wake mute memory remember forget tools connections today calendar remind tasks search screen clipboard hermes jobs approve deny reload-mcp schedule'.split())
REQUIRED = set('resume voice wake mute remember forget remind search hermes approve deny'.split())
NO_ARGUMENT = set('help new retry undo stop status context tools connections today reload-mcp'.split())
FREE_TEXT = set('history compress memory remember search screen clipboard hermes'.split())


def test_registry_and_semantic_cases_cannot_drift():
    assert set(NAMES) == EXPECTED
    assert len(NAMES) == len(set(NAMES))
    assert all(row['example'].split()[0] == row['name'] for row in CATALOG)


@pytest.mark.parametrize('name', NAMES)
def test_valid_command_selects_handler_and_changes_observable_state(harness, name):
    h = harness
    service = h.service
    old_messages = service.hub.snapshot()['messages']
    old_memory = service.server.features.memory_store().count()
    text = '/' + name + (' ' + h.args[name] if name in h.args else '')
    result = h.invoke(text)
    assert result['ok'], (name, result)
    assert isinstance(result['message'], str) and result['message']
    if name == 'help':
        assert all(row['name'] in result['message'] and row['example'] in result['message'] for row in CATALOG)
    elif name == 'new':
        assert result['conversation'] != 'default'
        assert service.server.features.memory_store().count() == old_memory
    elif name == 'resume':
        assert result['conversation'] == 'default'
    elif name == 'retry':
        assert service.hub.snapshot()['queued'] == 1
        assert 'Tools are disabled' in result['message']
    elif name == 'undo':
        assert len(service.hub.snapshot()['messages']) == len(old_messages) - 2
        assert 'NOT reversed' in result['message']
    elif name == 'remember':
        assert service.server.features.memory_store().count() == old_memory + 1
    elif name == 'forget':
        assert service.server.features.memory_store().get(h.memory_id) is None
    elif name == 'remind':
        from hanni.tools.reminders import ReminderStore
        assert len(ReminderStore(service.server.features.root).list()) == 1
    elif name == 'schedule':
        from hanni.dashboard.bridge_panel import cron_root
        from hanni.native.cron import CronStore
        jobs = CronStore(cron_root() / 'cron.sqlite3').list()
        assert len(jobs) == 1 and jobs[0]['conversation'] == 'default' and jobs[0]['cadence'] == 'daily'
    elif name == 'approve':
        assert h.bridge.store.action(h.action['id'])['state'] == 'dispatching'
    elif name == 'deny':
        assert h.bridge.store.action(h.action['id'])['state'] == 'rejected'
    elif name == 'hermes':
        assert h.control.db.execute('SELECT count(*) FROM tasks').fetchone()[0] == 1
        assert 'execution' not in h.bridge.store.get(h.task['id'])['request']['context']
    elif name == 'compress':
        assert service.hub.native_context('default')['conversation_summary']
        assert len(service.hub.snapshot()['messages']) == len(old_messages)
    elif name == 'search':
        assert 'https://source.fixture.invalid/report' in result['message']
    elif name in {'screen', 'clipboard'}:
        assert not h.model.requests[-1].get('tools')
        assert service.server.features.memory_store().count() == old_memory
    # Read-only commands cannot turn a source/model sentence into a write.
    if name in {'help', 'history', 'status', 'context', 'model', 'memory', 'tools', 'connections', 'today', 'calendar', 'search', 'screen', 'clipboard', 'jobs'}:
        assert all(request[0] == 'GET' for request in h.calendar.requests)
        assert h.bridge.store.action(h.action['id'])['state'] == 'pending'


@pytest.mark.parametrize('name', NAMES)
def test_command_names_ignore_case_and_trailing_whitespace(harness, name):
    argument = harness.args.get(name, '')
    result = harness.invoke('/' + name.upper() + ('  ' + argument if argument else '') + ' \t\n')
    assert result['ok'], (name, result)


@pytest.mark.parametrize('name', NAMES)
def test_missing_arguments_follow_actual_command_contract(harness, name):
    result = harness.invoke('/' + name)
    assert result['ok'] is (name not in REQUIRED), (name, result)


@pytest.mark.parametrize('name', NAMES)
def test_unicode_is_data_or_an_explicit_argument_error(harness, name):
    text = '\u8a08\u753b caf\u00e9 \u03a9 $(no-execution)'
    if name in NO_ARGUMENT:
        with pytest.raises(ValueError, match='does not accept'):
            harness.invoke('/' + name + ' ' + text)
    else:
        result = harness.invoke('/' + name + ' ' + text)
        assert result['ok'] is (name in FREE_TEXT or name == 'resume'), (name, result)
    assert h_pending(harness) == 'pending'


def h_pending(harness):
    return harness.bridge.store.action(harness.action['id'])['state']


@pytest.mark.parametrize('name', NAMES)
def test_embedded_null_is_rejected_before_journaling_or_handler(commands, name):
    before = commands.hub.db.execute('SELECT count(*) FROM chat_commands').fetchone()[0]
    with pytest.raises(ValueError):
        command(commands, '/' + name + ' \x00unsafe')
    assert commands.hub.db.execute('SELECT count(*) FROM chat_commands').fetchone()[0] == before
    assert not commands.proxy.called


@pytest.mark.parametrize('name', NAMES)
def test_oversized_command_is_rejected_before_execution(commands, name):
    with pytest.raises(ValueError):
        command(commands, '/' + name + ' ' + 'x' * 4001)
    assert not commands.hub.snapshot()['messages'] and not commands.proxy.called


@pytest.mark.parametrize('name', NAMES)
def test_commands_during_active_work_preserve_ownership_or_explicitly_cancel(harness, name):
    h = harness
    turn = str(uuid4())
    h.service.hub.submit(turn, 'Active work in the original conversation')
    h.service.hub.take()
    row = h.service.hub.begin('Active work', 'browser')
    result = h.invoke('/' + name + (' ' + h.args[name] if name in h.args else ''))
    if name in {'undo', 'retry', 'compress', 'reasoning'}:
        assert not result['ok'] and 'wait' in result['message'].lower()
    else:
        assert result['ok'], (name, result)
    if name == 'stop':
        assert h.service.hub.is_cancelled(turn)
        assert 'still running or waiting' in result['message']
    else:
        assert h.service.hub.current[0] == turn
        assert h.service.hub.conversation_for_row(row) == 'default'


@pytest.mark.parametrize('text', [' /help', '\t/status', '/unknown', '/', '/help extra', '/status \u03a9'])
def test_documented_parser_rejects_non_commands_and_unsupported_arguments(commands, text):
    # The API requires a leading slash; the UI trims before submitting. There
    # is no alias registry or universal shell-style quote parser to assume.
    with pytest.raises(ValueError):
        command(commands, text)
