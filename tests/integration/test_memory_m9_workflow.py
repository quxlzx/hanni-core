"""Real SQLite/filesystem lifecycle. Only the Windows Explorer process is mocked."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from hanni.config import load_config
from hanni.memory import MemoryAwareSession, MemoryStore
from hanni.tools import build_default_registry
from hanni.tools.base import ToolRequest
from tests.helpers import write_config_dir

class NoModel:

    def stream_response(self, prompt, **kwargs):
        yield 'ordinary conversation'

def say(session, prompt):
    return ''.join(session.stream_response(prompt))

@pytest.fixture
def environment(tmp_path):
    cfg = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    registry = build_default_registry(cfg)
    folder = tmp_path / 'Hanni Project'
    folder.mkdir()
    db = tmp_path / 'durable.sqlite3'
    with patch('hanni.tools.windows.os', SimpleNamespace(name='nt', environ={'WINDIR': 'C:\\Windows'})), patch('hanni.tools.windows.subprocess.Popen') as launch:
        yield (registry, folder, db, launch)

def test_m9_exit_workflow_restart_reality_correction_and_forget(environment):
    registry, folder, db, launch = environment
    first = MemoryAwareSession(NoModel(), MemoryStore(db), registry=registry)
    assert 'full path' in say(first, 'Hanni, remember that this folder is my HANNI project')
    say(first, str(folder))
    second = MemoryAwareSession(NoModel(), MemoryStore(db), registry=registry)
    assert 'Requested File Explorer' in say(second, 'Open my HANNI project')
    launch.assert_called_once()
    assert launch.call_args.args[0][-1] == str(folder.resolve())
    assert 'shell' not in launch.call_args.kwargs
    moved = folder.with_name('Moved Hanni Project')
    folder.rename(moved)
    assert "isn't an existing directory" in say(second, 'Open my HANNI project')
    assert launch.call_count == 1
    assert 'differs' in say(second, f'My HANNI project is {moved}')
    assert 'updated' in say(second, f'Remember my HANNI project is {moved}')
    assert 'Requested File Explorer' in say(second, 'Open my HANNI project')
    assert launch.call_args.args[0][-1] == str(moved.resolve())
    assert MemoryStore(db).count() == 1
    say(first, 'Delete everything you remember about HANNI project')
    assert "don't have a remembered location" in say(second, 'Open my HANNI project')
    assert launch.call_count == 2
    assert not MemoryStore(db).search('HANNI project')
    assert MemoryStore(db).cleanup()['integrity'] == 'ok'
    db.unlink()

def test_alias_never_executes_a_remembered_script(environment):
    registry, folder, db, launch = environment
    script = folder / 'do-not-run.ps1'
    script.write_text('Write-Output should-never-run')
    session = MemoryAwareSession(NoModel(), MemoryStore(db), registry=registry)
    say(session, f'Remember my HANNI project is {script}')
    assert "isn't an existing directory" in say(session, 'Open my HANNI project')
    with pytest.raises(ValueError, match='directories'):
        registry.execute(ToolRequest('folder.open', {'path': str(script)}))
    assert not launch.called

def test_folder_confirmation_uses_runtime_policy_and_expires(environment):
    registry, folder, db, launch = environment
    permissions = registry.context.permissions
    registry.context.permissions = replace(permissions, profiles={**permissions.profiles, 'owner': replace(permissions.profiles['owner'], max_auto_approve_level=0)})
    clock = [0.0]
    session = MemoryAwareSession(NoModel(), MemoryStore(db), registry=registry, clock=lambda: clock[0])
    say(session, f'Remember my HANNI project is {folder}')
    assert 'confirmation' in say(session, 'Open my HANNI project')
    assert not launch.called
    clock[0] = 120
    assert 'expired' in say(session, 'Yes')
    assert not launch.called
    say(session, 'Open my HANNI project')
    assert 'Requested File Explorer' in say(session, 'Yes')
    assert launch.call_count == 1

def test_confirmation_cannot_be_reused_after_alias_changes(environment):
    registry, folder, db, launch = environment
    permissions = registry.context.permissions
    registry.context.permissions = replace(permissions, profiles={**permissions.profiles, 'owner': replace(permissions.profiles['owner'], max_auto_approve_level=0)})
    store = MemoryStore(db)
    session = MemoryAwareSession(NoModel(), store, registry=registry)
    say(session, f'Remember my HANNI project is {folder}')
    say(session, 'Open my HANNI project')
    other = folder.with_name('Other project')
    other.mkdir()
    MemoryStore(db).remember(f'My HANNI project is {other}')
    say(session, 'Yes')
    assert not launch.called
    assert 'confirmation' in say(session, 'Open my HANNI project')
    folder.rmdir()
    other.rmdir()
    assert "isn't an existing directory" in say(session, 'Yes')
    assert not launch.called

def test_memory_does_not_change_actor_profile_or_authority(environment):
    registry, folder, db, launch = environment
    permissions = registry.context.permissions
    registry.context.permissions = replace(permissions, profiles={**permissions.profiles, 'owner': replace(permissions.profiles['owner'], max_auto_approve_level=-1, chat_only=True)})
    session = MemoryAwareSession(NoModel(), MemoryStore(db), registry=registry)
    say(session, f'Remember my HANNI project is {folder}')
    assert 'no tool access' in say(session, 'Open my HANNI project')
    assert not launch.called
    assert registry.context.permissions.profiles['owner'].chat_only
