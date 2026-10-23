from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
import pytest
from hanni.config import load_config
from hanni.tools import build_default_registry
from hanni.tools.base import ToolRequest, ToolValidationError
from hanni.tools.whenparse import parse_when, WhenParseError
from hanni.tools.todos import TodoStore

@pytest.fixture
def registry(tmp_path):
    return build_default_registry(load_config(Path(__file__).resolve().parents[2] / 'config', data_dir=tmp_path, env={}))

def test_due_task_persists_is_idempotent_and_completes(tmp_path):
    store = TodoStore(tmp_path)
    args = {'title': 'Homework 1', 'course': 'CMSC330', 'due': 'tomorrow 11 59 pm'}
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda _: store.add(args), range(8)))
    assert len({r['id'] for r in rows}) == 1
    fresh = TodoStore(tmp_path)
    assert fresh.get(rows[0]['id'])['due'].endswith('T23:59:00')
    assert len(fresh.list({}, due_only=True)) == 1
    fresh.complete(rows[0]['id'])
    assert fresh.list({}) == []
    assert fresh.get(rows[0]['id'])['status'] == 'completed'

def test_todo_privacy_and_validation(registry):
    with pytest.raises(ValueError):
        registry.execute(ToolRequest('todo.add', {'title': 'my password is secret123', 'due': 'tomorrow'}))
    with pytest.raises(ToolValidationError):
        registry.execute(ToolRequest('todo.due', {'days': True}))
    with pytest.raises(ValueError):
        registry.execute(ToolRequest('todo.get', {'id': "' OR 1=1--"}))

def test_spoken_time_and_day_after_tomorrow():
    now = datetime(2026, 9, 13, 12)
    assert parse_when('tomorrow at 11 59 pm', now=now).start == datetime(2026, 9, 14, 23, 59)
    assert parse_when('day after tomorrow', now=now).start.date() == (now + timedelta(days=2)).date()
    for bad in ['tomorrow 13pm', 'tomorrow 11:99pm', '9/12 at 3pm']:
        with pytest.raises(WhenParseError):
            parse_when(bad, now=now)
