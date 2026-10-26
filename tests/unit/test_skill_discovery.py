"""Skill discovery and receipt-based learning without live models or downloads."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from hanni.native.agent_tools import AgentTools, agent_tool_specs
from hanni.native import skill_discovery
from hanni.native.skill_store import SkillStore
from hanni.native.skills import search_skills, render_skills
from hanni.native.tool_access import ToolAccess, is_read
from hanni.hermes.state import TaskStore
from tests.unit.test_agent_runtime import payload, reply, call, spec


def procedure(name='work-diary', **values):
    return dict(name=name, description='Inspect calendar appointments and availability',
        instructions='Use `google.calendar.events` with the current requested date and account. Check its receipt.',
        triggers=['work diary'], expected_revision='', verification='Fixture read receipt returned ok.',
        correction='Use the existing connected calendar.', **values)


@pytest.fixture
def skills(tmp_path, monkeypatch):
    monkeypatch.setenv('HANNI_SKILLS_DIR', str(tmp_path / 'bundled'))
    store = SkillStore(tmp_path)
    store.save(**procedure())
    return store


def successful_task(prompt='Can you check my calendar?', **changes):
    value = {'id': 'fixture-task', 'state': 'running', 'request': {'prompt': prompt}, 'actions': [
        {'spec': {'name': 'calendar_adapter', 'remote': {'name': 'google_calendar.agenda'}},
         'state': 'fulfilled', 'receipt': {'ok': True, 'data': {'events': []}}}]}
    value.update(changes)
    return value


def test_search_uses_descriptions_when_exact_triggers_do_not_match(skills):
    found = skills.search('Can you can you check my calendar?')
    assert [s['name'] for s in found] == ['work-diary']
    assert 'body' not in found[0]
    assert 'google.calendar.events' in render_skills(found)
    assert not skills.search('Calculate the thermal resistance')


def test_successful_match_is_persistent_idempotent_and_does_not_store_prompt_content(skills):
    task = successful_task('Please inspect the polarisbriefing')
    assert not skills.search(task['request']['prompt'])
    assert skills.remember_success(task, ['work-diary']) == ['work-diary']
    skills.remember_success(task, ['work-diary'])
    reopened = SkillStore(skills.root)
    assert reopened.search('Can you inspect the polarisbriefing?')[0]['learned_match']
    assert len([r for r in reopened.journey() if r['action'] == 'learned_match']) == 1
    with reopened._db() as db:
        rows = db.execute('SELECT * FROM skill_routes').fetchall()
        assert 'polarisbriefing' not in str([tuple(r) for r in rows])
    reopened.lifecycle('work-diary', reopened.detail('work-diary')['revision'], 'archive')
    assert not reopened.search('inspect the polarisbriefing')


@pytest.mark.parametrize('failure', ['cancelled', 'no-receipt', 'tool-failed', 'partial', 'uncertain', 'only-skill-read'])
def test_failed_or_unverified_work_cannot_teach_a_successful_route(skills, failure):
    task = successful_task()
    if failure == 'cancelled': task['state'] = 'cancelled'
    elif failure == 'no-receipt': task['actions'] = []
    elif failure == 'tool-failed': task['actions'][0]['receipt'] = {'ok': False}
    elif failure == 'partial': task['actions'][0]['receipt']['data']['partial'] = True
    elif failure == 'uncertain': task['actions'][0]['state'] = 'uncertain'
    else: task['actions'][0]['spec']['name'] = 'skill_read'
    assert not skills.remember_success(task, ['work-diary'])
    with skills._db() as db: assert db.execute('SELECT count(*) FROM skill_routes').fetchone()[0] == 0


def test_an_unrelated_successful_tool_is_not_evidence_for_a_calendar_skill(skills):
    task = successful_task()
    task['actions'][0]['spec'] = {'name': 'system_info', 'remote': {}}
    assert not skills.remember_success(task, ['work-diary'])


def package_fetch(files=None, *, change_tree=None, bad_content=False):
    files = files or {'skills/calendar-helper/SKILL.md': b'---\nname: calendar-helper\ndescription: Inspect calendar availability\n---\nUse the available calendar tool.\n',
        'skills/calendar-helper/references/checks.md': b'Check the actual returned interval.',
        'skills/calendar-helper/scripts/helper.py': b"raise RuntimeError('This downloaded file must never execute')\n"}
    commit = 'a' * 40
    nodes = [{'path': name, 'mode': '100644', 'type': 'blob', 'size': len(raw),
              'sha': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()} for name, raw in files.items()]
    if change_tree: change_tree(nodes)
    calls = []
    def fetch(url, cap):
        calls.append(url)
        if url.endswith('/commits/HEAD'): raw = json.dumps({'sha': commit}).encode()
        elif '/git/trees/' in url: raw = json.dumps({'tree': nodes, 'truncated': False}).encode()
        else:
            path = url.split('/' + commit + '/', 1)[1]
            raw = files[path] + (b'changed' if bad_content else b'')
        assert len(raw) <= cap
        return raw
    return fetch, calls


def test_online_search_is_bounded_and_validates_repository_identifiers():
    calls = []
    def fetch(url, cap):
        calls.append(url)
        return json.dumps({'skills': [{'name': 'calendar-helper', 'source': 'example/calendar'},
            {'name': '../escape', 'source': 'example/calendar'}, {'name': 'remote', 'source': 'https://localhost'}]}).encode()
    result = skill_discovery.online_search('calendar scheduling', fetch=fetch)
    assert len(result) == 1 and result[0]['repository'] == 'example/calendar'
    assert 'skills.sh/api/search?' in calls[0] and 'q=calendar+scheduling' in calls[0]
    with pytest.raises(ValueError): skill_discovery.online_search('person@example.test', fetch=fetch)
    assert len(calls) == 1


def test_install_pins_complete_package_keeps_provenance_and_never_executes_helpers(skills):
    fetch, calls = package_fetch()
    payload, files, provenance = skill_discovery.download_skill('example/calendar', 'calendar-helper', fetch=fetch)
    result = skills.install_package(payload, files, provenance)
    assert result['ok'] and result['data']['installed'] and result['data']['commit_sha'] == 'a' * 40
    assert all('/' + 'a' * 40 + '/' in url for url in calls if 'raw.githubusercontent' in url)
    folder = skills.root / 'skills/calendar-helper'
    assert (folder / 'scripts/helper.py').is_file() and (folder / 'UPSTREAM_SKILL.md').is_file()
    assert skills.read('calendar-helper', 'references/checks.md')['content'].startswith('Check the actual')
    assert skills.install_package(payload, files, provenance)['data']['installed'] is False
    assert any(r['source'].startswith('internet:example/calendar@') for r in skills.journey())
    with skills._db() as db:
        assert db.execute('SELECT content_sha256 FROM skill_sources').fetchone()[0] == provenance['content_sha256']


@pytest.mark.parametrize('bad', ['traversal', 'symlink', 'oversize', 'case-collision', 'nested-skill', 'windows-device'])
def test_untrusted_package_paths_and_sizes_are_rejected_before_install(bad, skills):
    def change(nodes):
        if bad == 'symlink': nodes[0]['mode'] = '120000'
        elif bad == 'oversize': nodes[0]['size'] = 1024 * 1024
        else:
            path = {'traversal': 'skills/calendar-helper/../../escape.txt',
                    'case-collision': 'skills/calendar-helper/skill.md',
                    'nested-skill': 'skills/calendar-helper/nested/SKILL.md',
                    'windows-device': 'skills/calendar-helper/CON.txt'}[bad]
            nodes.append({**nodes[1], 'path': path})
    fetch, calls = package_fetch(change_tree=change)
    with pytest.raises(ValueError): skill_discovery.download_skill('example/calendar', 'calendar-helper', fetch=fetch)
    assert not (skills.root / 'skills/calendar-helper').exists()
    assert not any('raw.githubusercontent' in url for url in calls)


def test_hash_mismatch_cancellation_and_name_collision_cannot_activate_a_download(skills):
    fetch, _ = package_fetch(bad_content=True)
    with pytest.raises(ValueError, match='match the pinned'): skill_discovery.download_skill('example/calendar', 'calendar-helper', fetch=fetch)
    fetch, _ = package_fetch()
    with pytest.raises(InterruptedError):
        skill_discovery.download_skill('example/calendar', 'calendar-helper', fetch=fetch, cancelled=lambda: True)
    payload, resources, source = skill_discovery.download_skill('example/calendar', 'calendar-helper', fetch=fetch)
    skills.save(**procedure(name='calendar-helper'))
    before = skills.read('calendar-helper')['revision']
    with pytest.raises(ValueError, match='already owns'): skills.install_package(payload, resources, source)
    assert skills.read('calendar-helper')['revision'] == before


def test_search_is_read_only_and_installation_retains_write_policy(tmp_path):
    specs = {s['name']: s for s in agent_tool_specs()}
    access = ToolAccess(tmp_path); access.save('read_only', 'default')
    assert is_read(specs['skill_search'], {}) and not is_read(specs['skill_install'], {})
    assert access.decision(specs['skill_search'], {}) == 'auto'
    assert access.decision(specs['skill_install'], {}) == 'blocked'
    access.save('ask', access.snapshot()['revision'])
    assert access.decision(specs['skill_install'], {}) == 'ask'
    assert access.decision(specs['skill_search'], {}) == 'auto'


@pytest.mark.parametrize('bad', ['private', 'redirect', 'oversize'])
def test_public_fetch_rejects_unapproved_hosts_redirects_and_excess_bytes(monkeypatch, bad):
    from hanni.native import local_tools
    def fetch(url, cap):
        if bad == 'private': pytest.fail('Private skill URL reached the HTTP client')
        return ('https://foreign.example/skill' if bad == 'redirect' else url,
                b'12345' if bad == 'oversize' else b'{}')
    monkeypatch.setattr(local_tools, '_http_get', fetch)
    url = 'https://127.0.0.1/SKILL.md' if bad == 'private' else 'https://api.github.com/example'
    with pytest.raises(ValueError): skill_discovery.fetch_public(url, 4)


def test_agent_discovers_local_skills_without_network_and_respects_read_only_installation(skills, monkeypatch):
    store = TaskStore(skills.root / 'tasks.sqlite3')
    task = store.submit('search', payload())
    agent = AgentTools(store, task, agent_tool_specs(), cancelled=lambda: False)
    monkeypatch.setattr(skill_discovery, 'online_search', lambda *_: pytest.fail('Local discovery contacted the internet'))
    try:
        result = agent.execute('skill_search', {'query': 'calendar'}, 'find')
        assert result['data']['local'][0]['name'] == 'work-diary'
        assert 'path' not in result['data']['local'][0] and not result['data']['execution_authority_granted']
        access = ToolAccess(skills.root); access.save('read_only', 'default')
        monkeypatch.setattr(skill_discovery, 'download_skill', lambda *a, **k: pytest.fail('Read-only mode downloaded a package'))
        with pytest.raises(ValueError, match='Read-only'):
            agent.execute('skill_install', {'repository': 'example/calendar', 'name': 'calendar-helper'}, 'install')
    finally: store.close()


def test_cancel_or_changed_policy_after_download_prevents_installation(skills, monkeypatch):
    fetch, _ = package_fetch()
    downloaded = skill_discovery.download_skill('example/calendar', 'calendar-helper', fetch=fetch)
    store = TaskStore(skills.root / 'tasks.sqlite3'); task = store.submit('download', payload())
    cancelled = [False]
    agent = AgentTools(store, task, agent_tool_specs(), cancelled=lambda: cancelled[0])
    def cancel(*a, **k): cancelled[0] = True; return downloaded
    monkeypatch.setattr(skill_discovery, 'download_skill', cancel)
    try:
        with pytest.raises(InterruptedError):
            agent.execute('skill_install', {'repository': 'example/calendar', 'name': 'calendar-helper'}, 'install')
        cancelled[0] = False
        def restrict(*a, **k): ToolAccess(skills.root).save('read_only', 'default'); return downloaded
        monkeypatch.setattr(skill_discovery, 'download_skill', restrict)
        with pytest.raises(ValueError, match='changed during download'):
            agent.execute('skill_install', {'repository': 'example/calendar', 'name': 'calendar-helper'}, 'install')
        assert not (skills.root / 'skills/calendar-helper').exists()
    finally: store.close()


def test_worker_discovers_calendar_procedure_and_remembers_only_real_success(tmp_path, monkeypatch):
    from hanni.native import worker
    monkeypatch.setenv('HANNI_SKILLS_DIR', str(tmp_path / 'bundled'))
    monkeypatch.delenv('HANNI_DASHBOARD_URL', raising=False)
    monkeypatch.setattr(worker, 'load_soul', lambda: '')
    monkeypatch.setattr(worker, 'load_model', lambda: {'context_length': 65536})
    original_specs = worker.local_tool_specs
    calendar_spec = {**spec('calendar_read'), 'remote': {'name': 'google_calendar.agenda'}}
    monkeypatch.setattr(worker, 'local_tool_specs', lambda: [*original_specs(), calendar_spec])
    skills = SkillStore(tmp_path); skills.save(**{**procedure(), 'triggers': ['my calendar']})
    skills.save(**{**procedure('workday-brief'), 'description': 'Calendar and workday briefing',
                  'triggers': ['morning briefing'], 'instructions': 'Prepare a complete workday briefing.'})
    prompts = []
    class Client:
        max_tokens = 256
        config = {'context_length': 65536}
        def __init__(self, *_): self.index = 0
        def chat(self, messages, tools):
            prompts.append(deepcopy(messages))
            if self.index:
                return reply('The calendar read was verified.')
            self.index += 1
            assert '### skill: work-diary' in messages[0]['content']
            assert '### skill: workday-brief' not in messages[0]['content']
            return reply(calls=[call('calendar_read', 'read')])
    monkeypatch.setattr(worker, 'NativeClient', Client)
    monkeypatch.setattr(worker, 'execute_local', lambda *_: {'ok': True, 'data': {'events': []}})
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    task = store.submit('discover', {**payload(local_runtime={'auto_approve': ['calendar_read']}), 'prompt': 'Can you can you check my calendar?'})
    try:
        worker.run(store.path, task['id'], {'entries': []})
        assert store.get(task['id'])['state'] == 'review_required'
        assert SkillStore(tmp_path).search(task['request']['prompt'])[0]['learned_match']
    finally: store.close()


def test_model_can_search_download_read_and_use_a_new_skill_in_one_task(tmp_path, monkeypatch):
    from hanni.native import worker
    monkeypatch.setenv('HANNI_SKILLS_DIR', str(tmp_path / 'bundled'))
    monkeypatch.delenv('HANNI_DASHBOARD_URL', raising=False)
    monkeypatch.setattr(worker, 'load_soul', lambda: '')
    monkeypatch.setattr(worker, 'load_model', lambda: {'context_length': 65536})
    fetch, _ = package_fetch()
    downloaded = skill_discovery.download_skill('example/calendar', 'calendar-helper', fetch=fetch)
    monkeypatch.setattr(skill_discovery, 'online_search', lambda _: [{'name': 'calendar-helper', 'repository': 'example/calendar'}])
    monkeypatch.setattr(skill_discovery, 'download_skill', lambda *a, **k: downloaded)
    original_specs = worker.local_tool_specs
    calendar_spec = {**spec('calendar_read'), 'remote': {'name': 'google_calendar.agenda'}}
    monkeypatch.setattr(worker, 'local_tool_specs', lambda: [*original_specs(), calendar_spec])
    monkeypatch.setattr(worker, 'execute_local', lambda *_: {'ok': True, 'data': {'events': []}})
    sequence = [('skill_search', {'query': 'calendar', 'online': True}),
        ('skill_install', {'repository': 'example/calendar', 'name': 'calendar-helper'}),
        ('skill_read', {'name': 'calendar-helper'}), ('calendar_read', {})]
    class Client:
        max_tokens = 256
        config = {'context_length': 65536}
        def __init__(self, *_): self.index = 0
        def chat(self, messages, tools):
            if self.index == len(sequence): return reply('Your checked calendar has no events in this window.')
            name, arguments = sequence[self.index]; self.index += 1
            item = call(name, str(self.index)); item['function']['arguments'] = json.dumps(arguments)
            return reply(calls=[item])
    monkeypatch.setattr(worker, 'NativeClient', Client)
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    task = store.submit('find-new', {**payload(local_runtime={'auto_approve': ['calendar_read']}), 'prompt': 'Check my calendar'})
    try:
        worker.run(store.path, task['id'], {'entries': []})
        result = store.get(task['id'])
        assert result['state'] == 'review_required', result
        assert len(result['actions']) == 4 and all(a['state'] == 'fulfilled' and a['receipt']['ok'] for a in result['actions'])
        reopened = SkillStore(tmp_path)
        assert reopened.search('Check my calendar')[0]['learned_match']
        assert reopened.read('calendar-helper')['provenance']['commit_sha'] == 'a' * 40
    finally: store.close()
