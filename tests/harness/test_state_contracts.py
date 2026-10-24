from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading

import pytest

from hanni.dashboard.chat import ChatHub
from hanni.hermes.state import Conflict, TaskStore, digest
from hanni.memory.store import MemoryStore
from hanni.native.compact import compact, estimate_tokens
from hanni.native.skill_store import SkillStore
from hanni.native.skills import load_skills, match_skills
from hanni.tools.reminders import resolve_time
from .test_protocol_contracts import capability


def test_memory_deletion_does_not_claim_to_erase_history_or_backups(tmp_path):
    store = MemoryStore(tmp_path / 'memory.sqlite3')
    record, _ = store.remember('I prefer concise quarterly reports')
    hub = ChatHub(tmp_path / 'history.sqlite3')
    try:
        hub.note('Saved report preference', record.content)
        with sqlite3.connect(tmp_path / 'memory.sqlite3') as original, sqlite3.connect(tmp_path / 'backup.sqlite3') as backup:
            original.backup(backup)
        assert store.delete(record.id)
        assert not MemoryStore(tmp_path / 'memory.sqlite3').search('quarterly reports')
        assert record.content in str(hub.snapshot()['messages'])
        assert MemoryStore(tmp_path / 'backup.sqlite3').get(record.id).content == record.content
    finally:
        hub.close()
        hub.db.close()


def test_separate_profile_roots_do_not_share_personal_records(tmp_path):
    first = MemoryStore(tmp_path / 'first/memory.sqlite3')
    second = MemoryStore(tmp_path / 'second/memory.sqlite3')
    record, _ = first.remember('I prefer concise reports')
    assert second.get(record.id) is None and not second.search('reports')
    assert MemoryStore(tmp_path / 'first/memory.sqlite3').get(record.id).content == record.content


def test_task_transaction_rolls_back_actions_and_events_together(tmp_path):
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    try:
        task = store.submit('rollback', {'origin': 'hanni', 'prompt': 'Inspect', 'windows_tools': [], 'context': {}})
        with pytest.raises(RuntimeError, match='injected'):
            with store.transaction():
                store.request_action(task['id'], 'one', capability(), {})
                raise RuntimeError('injected interruption before commit')
        reopened = TaskStore(store.path)
        try:
            saved = reopened.get(task['id'])
            assert saved['state'] == 'queued' and not saved['actions'] and not saved['events']
        finally:
            reopened.close()
    finally:
        store.close()


def test_concurrent_approval_claims_allow_only_one_dispatch(tmp_path):
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    try:
        task = store.submit('approval', {'origin': 'hanni', 'prompt': 'Inspect', 'windows_tools': [], 'context': {}})
        action = store.request_action(task['id'], 'one', capability(), {})
        barrier = threading.Barrier(2)
        def approve():
            barrier.wait(timeout=5)
            try:
                store.settle(action['id'], 'dispatching', expected_hash=digest(action))
                return 'claimed'
            except Conflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: approve(), range(2)))
        assert sorted(results) == ['claimed', 'conflict']
        assert store.action(action['id'])['state'] == 'dispatching'
    finally:
        store.close()


def test_corrupt_task_database_is_reported_not_silently_recreated(tmp_path):
    path = tmp_path / 'tasks.sqlite3'
    original = b'Not a SQLite database; preserve for diagnosis.'
    path.write_bytes(original)
    with pytest.raises(sqlite3.DatabaseError):
        TaskStore(path)
    assert path.read_bytes() == original


def test_compaction_fallback_retains_request_constraints_and_paired_recent_results():
    anchor = 'Find the endpoint error. Do not restart or delete production files.'
    messages = [{'role': 'system', 'content': 'Stable instruction'}, {'role': 'user', 'content': anchor}]
    for index in range(15):
        messages += [{'role': 'assistant', 'content': 'Observation ' + 'x' * 300},
                     {'role': 'user', 'content': 'Continue ' + 'y' * 300}]
    class Unavailable:
        def chat(self, *_):
            raise ConnectionError('Synthetic summary backend outage')
    result = compact(messages, Unavailable(), max_tokens=1600, task_anchor=anchor)
    assert estimate_tokens(result) <= 1600 and result[0] == messages[0]
    assert anchor in result[1]['content'] and 'fallback' in result[1]['content']
    assert all(word in result[1]['content'] for word in ['Constraints', 'Completed', 'Blockers', 'Next steps'])


def test_skill_metadata_does_not_load_unselected_procedure_bodies(tmp_path, monkeypatch):
    for name, trigger in [('reports', 'quarterly'), ('calendar', 'calendar')]:
        folder = tmp_path / name
        folder.mkdir()
        (folder / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Handle {trigger}\ntriggers: [{trigger}]\n---\n{name} procedure\n')
    reads = []
    original = Path.read_text
    def observed(path, *args, **kwargs):
        reads.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', observed)
    catalog = load_skills(str(tmp_path), metadata_only=True)
    assert not reads and all('body' not in skill for skill in catalog)
    selected = match_skills(catalog, 'Prepare the quarterly report')
    assert 'reports procedure' in selected and 'calendar procedure' not in selected
    assert reads == [tmp_path / 'reports/SKILL.md']


def test_invalid_skill_yaml_and_missing_reference_are_explicit(tmp_path, monkeypatch):
    bundled = tmp_path / 'bundled'
    (bundled / 'invalid').mkdir(parents=True)
    (bundled / 'invalid/SKILL.md').write_text('---\nname: [broken\n---\nInvalid body\n')
    monkeypatch.setenv('HANNI_SKILLS_DIR', str(bundled))
    assert load_skills(str(bundled)) == []
    store = SkillStore(tmp_path / 'state')
    with pytest.raises(ValueError, match='not found'):
        store.read('missing')


def test_concurrent_skill_corrections_cannot_overwrite_an_unseen_revision(tmp_path, monkeypatch):
    monkeypatch.setenv('HANNI_SKILLS_DIR', str(tmp_path / 'bundled'))
    store = SkillStore(tmp_path)
    args = dict(name='reports', description='Prepare quarterly reports', instructions='Read the source and verify totals.',
                triggers=['quarterly'], expected_revision='', verification='Synthetic review completed', correction='Initial verified procedure')
    initial = store.save(**args)['data']['revision']
    barrier = threading.Barrier(2)
    def update(number):
        barrier.wait(timeout=5)
        try:
            return store.save(**{**args, 'instructions': f'Revised procedure {number}', 'expected_revision': initial})['data']['revision']
        except ValueError:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(update, [1, 2]))
    assert results.count('conflict') == 1
    assert store.read('reports')['revision'] in results


@pytest.mark.parametrize('local', ['2026-11-01T01:30', '2027-03-14T02:30'])
def test_dst_ambiguous_and_nonexistent_reminder_times_are_not_guessed(local):
    with pytest.raises(ValueError, match='ambiguous or missing'):
        resolve_time(local, 'America/Chicago', now=datetime(2026, 10, 24, tzinfo=timezone.utc))


def test_explicit_offset_disambiguates_reminder_time():
    result = resolve_time('2026-11-01T01:30-05:00', 'America/Chicago', now=datetime(2026, 10, 24, tzinfo=timezone.utc))
    assert result.isoformat() == '2026-11-01T01:30:00-05:00'
