"""Independent V3.6 real-registry/HTTP/store core acceptance checks.

All writes target pytest temporary stores/files. Hardware, cloud, model,
microphone, clipboard, power and remote-control handlers are not executed.
No ReviewFixture or synthetic telemetry/controller response is used.
"""
from __future__ import annotations
import hashlib
import http.client
import json
import os
from pathlib import Path
import threading
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.core.identity import Actor
from hanni.core.shutdown import EmergencyStopActive, StopSource
from hanni.dashboard.features import DesktopFeatures
from hanni.dashboard.productivity import ProductivityStore
from hanni.dashboard.server import DashboardServer, Telemetry
from hanni.memory.retrieval import LocalMemoryRetriever
from hanni.memory.store import MemoryStore
from hanni.reliability.execution import close_service
from hanni.tools.base import ConfirmationRequired, ToolPermissionError, ToolRequest
from hanni.tools.registry import build_default_registry
from hanni.tools.todos import TodoStore
ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture
def original(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    registry = build_default_registry(config)
    features = DesktopFeatures(config, registry=registry)
    try:
        yield (config, registry, features)
    finally:
        close_service(tmp_path)

@pytest.fixture
def connected_calendar(original):
    """Routing availability must not depend on the owner's credential vault."""
    import sys
    sys.path.insert(0, str(ROOT / 'scripts/v36_engineering'))
    from fixtures import GoogleProvider, GoogleVault
    _, registry, _ = original
    registry.google_access._vault = GoogleVault()
    registry.google_access.transport = GoogleProvider()

def mutation(operation, data, *, confirmed=True, key=None):
    return dict(id=key or str(uuid4()), operation=operation, data=data, confirmed=confirmed)

def correction(record, text):
    return mutation('correct', dict(memory_id=record.id, expected_updated_at=record.updated_at.isoformat(), content=text, project_id='', semantic_status='statement'))

def test_core_file_roundtrip_is_grounded_in_independent_bytes(original, tmp_path):
    _, registry, _ = original
    target = tmp_path / 'unicode-evidence.txt'
    text = 'Synthetic verifier36: résumé\n7 of 11 samples passed.\n'
    result = registry.execute(ToolRequest('file.write', {'path': str(target), 'text': text}))
    assert result.ok
    assert target.read_bytes() == text.replace('\n', os.linesep).encode('utf8')
    actual = registry.execute(ToolRequest('file.read', {'path': str(target)}))
    assert actual.ok and actual.data['text'] == text
    stat = registry.execute(ToolRequest('file.stat', {'path': str(target), 'hash': True}))
    assert stat.data['sha256'] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert result.verification['status'] == 'VERIFIED'

def test_core_file_copy_move_preserves_original_fixture_bytes(original, tmp_path):
    _, registry, _ = original
    source = tmp_path / 'source.txt'
    source.write_bytes(b'verifier36\x00source\n')
    copy = tmp_path / 'copy.txt'
    destination = tmp_path / 'moved.txt'
    first = registry.execute(ToolRequest('file.copy', {'source': str(source), 'destination': str(copy)}))
    assert first.ok and copy.read_bytes() == source.read_bytes()
    second = registry.execute(ToolRequest('file.move', {'source': str(copy), 'destination': str(destination)}))
    assert second.ok and (not copy.exists()) and (destination.read_bytes() == source.read_bytes())
    assert first.verification['status'] == second.verification['status'] == 'VERIFIED'

def test_core_fixture_delete_requires_original_confirmation(original, tmp_path):
    _, registry, _ = original
    target = tmp_path / 'only-this-fixture.txt'
    target.write_text('retain until confirmed')
    with pytest.raises(ConfirmationRequired):
        registry.execute(ToolRequest('file.delete', {'path': str(target)}))
    assert target.read_text() == 'retain until confirmed'
    result = registry.execute(ToolRequest('file.delete', {'path': str(target)}, confirmed=True))
    assert result.ok and (not target.exists()) and (result.verification['status'] == 'VERIFIED')
    assert tmp_path.is_dir()

def test_core_todo_add_deduplication_and_completion_readback(original, tmp_path):
    _, registry, _ = original
    arguments = {'title': 'verifier36 isolated reminder', 'due': '2030-04-05 16:00', 'course': 'TEST36'}
    one = registry.execute(ToolRequest('todo.add', arguments)).data['task']
    two = registry.execute(ToolRequest('todo.add', arguments)).data['task']
    assert one['id'] == two['id']
    assert len(TodoStore(tmp_path).list({'status': 'all'})) == 1
    result = registry.execute(ToolRequest('todo.complete', {'id': one['id']}))
    assert result.data['task']['status'] == 'completed'
    assert TodoStore(tmp_path).get(one['id'])['status'] == 'completed'

def test_core_desktop_task_cas_preserves_newest_record(original):
    _, _, features = original
    item = features.mutate('productivity', mutation('task.create', {'title': 'verifier36 original'}))['task']
    data = dict(task_id=item['id'], expected_fingerprint=item['fingerprint'], title='verifier36 newer', course='', due='', priority='normal', project_id=None, status='open')
    current = features.mutate('productivity', mutation('task.update', data))['task']
    assert current['title'] == 'verifier36 newer'
    with pytest.raises(ValueError, match='changed'):
        features.mutate('productivity', mutation('task.update', {**data, 'title': 'stale overwrite'}))
    assert features.store.snapshot()['tasks'][0]['title'] == 'verifier36 newer'

def test_core_project_note_reopen_preserves_explicit_association(original, tmp_path):
    _, _, features = original
    project = features.mutate('productivity', mutation('project.create', {'name': 'verifier36 Cedar'}))['project']
    note = features.mutate('productivity', mutation('note.create', {'project_id': project['id'], 'title': 'Receipt', 'body': '7 of 11 samples passed.'}))['note']
    saved = ProductivityStore(tmp_path).snapshot()
    assert saved['notes'][0]['id'] == note['id']
    assert saved['notes'][0]['project_id'] == project['id']
    with pytest.raises(ValueError):
        features.mutate('productivity', mutation('note.create', {'project_id': 'missing-project', 'title': 'Refused', 'body': 'Not associated with any real project.'}))
    assert len(ProductivityStore(tmp_path).snapshot()['notes']) == 1

def test_core_fixed_uuid_does_not_duplicate_or_rebind_write(original):
    _, _, features = original
    key = str(uuid4())
    request = mutation('task.create', {'title': 'One verifier36 task'}, key=key)
    one = features.mutate('productivity', request)
    assert features.mutate('productivity', request) == one
    with pytest.raises(ValueError):
        features.mutate('productivity', mutation('task.create', {'title': 'Different task'}, key=key))
    assert len(features.store.snapshot()['tasks']) == 1

def test_core_memory_correction_replaces_current_context_without_stale_cas(original):
    _, _, features = original
    store = features.memory_store()
    first, _ = store.remember('My preferred code editor is Helix', source='owner_explicit:verifier36')
    changed = features.mutate('memory', correction(first, 'My preferred code editor is Neovim'))
    assert changed['record']['id'] == first.id
    current = LocalMemoryRetriever(store).retrieve('preferred code editor').text
    assert 'Neovim' in current and 'Helix' not in current
    assert store.history(first.id)[0]['content'] == first.content
    with pytest.raises(ValueError, match='changed'):
        features.mutate('memory', correction(first, 'My preferred code editor is stale'))
    assert store.get(first.id).content == 'My preferred code editor is Neovim'

def test_core_memory_delete_erases_source_bound_history_and_proposals(original, tmp_path):
    _, _, features = original
    store = features.memory_store()
    record, _ = store.remember('My preferred code editor is Helix', source='owner_explicit:verifier36')
    features.mutate('memory', correction(record, 'My preferred code editor is Neovim'))
    current = store.get(record.id)
    store.propose('correct', 'My preferred code editor is Helix', source='synthetic:verifier36', target_id=current.id, expected_updated_at=current.updated_at.isoformat())
    features.mutate('memory', mutation('forget', dict(memory_id=current.id, expected_updated_at=current.updated_at.isoformat())))
    assert store.get(record.id) is None and (not store.history(record.id))
    assert not LocalMemoryRetriever(store).retrieve('preferred code editor').text
    reopened = MemoryStore(tmp_path / 'memory.sqlite3')
    assert reopened.count() == 0
    assert not reopened.suggestions(status='pending')

def test_core_local_analysis_is_review_only_and_exact_owner_approval(original):
    _, _, features = original
    store = features.memory_store()
    features.mutate('memory', mutation('analyze', {'content': 'My preferred code editor is Helix', 'project_id': ''}))
    assert store.count() == 0
    pending = store.suggestions(status='pending')
    assert len(pending) == 1
    suggestion = pending[0]
    request = mutation('review', dict(suggestion_id=suggestion.id, expected_updated_at=suggestion.updated_at.isoformat(), action='approve', edited_content=None))
    result = features.mutate('memory', request)
    assert features.mutate('memory', request) == result and store.count() == 1
    assert 'Helix' in store.list()[0].content

def test_core_empty_google_credentials_do_not_create_a_connected_calendar(original):
    _, registry, _ = original

    class EmptyVault:

        def labels(self):
            return ()

        def get(self, label):
            return None

        def preferences(self):
            return {}
    registry.google_access._vault = EmptyVault()
    result = registry.execute(ToolRequest('google_calendar.next', {}))
    assert not result.ok
    assert not result.data.get('event')
    assert any((word in result.message.lower() for word in ('connect', 'account', 'auth', 'configured')))

def test_core_persistent_safe_mode_blocks_confirmed_file_and_memory_mutation(original, tmp_path):
    config, registry, features = original
    store = features.memory_store()
    record, _ = store.remember('I prefer plain text reports')
    registry.context.emergency_stop.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner('verifier36'), reason='Isolated verification stop state')
    target = tmp_path / 'must-not-exist.txt'
    with pytest.raises(EmergencyStopActive):
        registry.execute(ToolRequest('file.write', {'path': str(target), 'text': 'blocked'}, confirmed=True))
    with pytest.raises(EmergencyStopActive):
        features.mutate('memory', correction(record, 'I prefer changed reports'))
    reopened = build_default_registry(config)
    with pytest.raises(EmergencyStopActive):
        reopened.execute(ToolRequest('file.write', {'path': str(target), 'text': 'still blocked'}, confirmed=True))
    assert not target.exists() and store.get(record.id).content == record.content

def test_core_nonowner_denial_precedes_read_handler_execution(original, tmp_path):
    _, registry, _ = original
    target = tmp_path / 'private-synthetic-fixture.txt'
    target.write_text('Do not disclose this synthetic record')
    with pytest.raises(ToolPermissionError):
        registry.execute(ToolRequest('file.read', {'path': str(target)}, actor_profile='everyone_else', confirmed=True))
    assert target.read_text() == 'Do not disclose this synthetic record'

def test_core_actual_http_authentication_and_origin_reject_before_mutation(original):
    config, registry, features = original
    telemetry = Telemetry(config)
    server = DashboardServer(0, telemetry, features=features)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    payload = mutation('task.create', {'title': 'verifier36 hostile request'})

    def post(headers):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=4)
        try:
            connection.request('POST', '/api/productivity', body=json.dumps(payload), headers=headers)
            response = connection.getresponse()
            response.read()
            return response.status
        finally:
            connection.close()
    valid = {'Content-Type': 'application/json', 'Origin': origin, 'X-Hanni-Token': server.chat.token}
    try:
        for headers in ({k: v for k, v in valid.items() if k != 'X-Hanni-Token'}, {**valid, 'X-Hanni-Token': 'wrong-synthetic'}, {**valid, 'Origin': 'http://hostile.invalid'}, {**valid, 'Host': 'hostile.invalid'}, {k: v for k, v in valid.items() if k != 'Origin'}):
            assert post(headers) == 403
        assert not features.store.snapshot()['tasks']
        assert post(valid) == 200
        assert len(features.store.snapshot()['tasks']) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=4)
        server.chat.close()
        telemetry.close()

def test_repair_audio_unavailable_is_not_verified_unmuted(original, monkeypatch):
    from hanni.tools import media
    monkeypatch.setattr(media, '_endpoint_volume', lambda: None)
    monkeypatch.setattr(media, 'run_powershell_json', lambda *args, **kwargs: [{'Name': 'Synthetic healthy endpoint', 'Status': 'OK'}])
    _, registry, _ = original
    result = registry.execute(ToolRequest('audio.status'))
    assert result.ok and result.data['precise'] is False
    assert result.data['muted'] is None and result.data['percent'] == -1
    assert 'unknown' in result.message.casefold()
    assert registry.get('audio.status').output_schema['muted'] == 'boolean|null'

def test_repair_grep_query_and_filename_filter_are_separate_observations(original, tmp_path):
    _, registry, _ = original
    target = tmp_path / 'evidence'
    target.mkdir()
    (target / 'first.txt').write_text('amber36 compass\nAMBER36 COMPASS\n', encoding='utf-8')
    (target / 'second.md').write_text('amber36 compass\n', encoding='utf-8')
    (target / 'unrelated.txt').write_text('no matching words\n', encoding='utf-8')
    broad = registry.execute(ToolRequest('file.grep', {'root': str(target), 'query': 'amber36 compass'}))
    assert broad.data['search_performed'] is True
    assert broad.data['scanned_files'] == 3 and broad.data['match_count'] == 3
    exact = registry.execute(ToolRequest('file.grep', {'root': str(target), 'query': 'amber36 compass', 'pattern': '*.txt', 'case_sensitive': True}))
    assert exact.data['scanned_files'] == 2 and exact.data['match_count'] == 1
    assert exact.data['matches'][0]['path'] == str(target / 'first.txt')
    wrong = registry.execute(ToolRequest('file.grep', {'root': str(target), 'query': 'amber36 compass', 'pattern': 'amber36 compass'}))
    assert wrong.data['search_performed'] is False and wrong.data['scanned_files'] == 0
    assert 'unknown' in wrong.message.casefold()
    schema = registry.get('file.grep').argument_schema()
    assert {'root', 'query'}.issubset(schema['required'])
    assert schema['properties']['pattern']['default'] == ''
    assert schema['properties']['pattern']['type'] == 'string'

def test_repair_task_contracts_validate_real_payload_without_false_generic_fields(original):
    _, registry, _ = original
    item = registry.execute(ToolRequest('todo.add', {'title': 'Independent amber36 deadline', 'due': '2031-06-09 12:15'}))
    for name, result in [('todo.add', item), ('todo.get', registry.execute(ToolRequest('todo.get', {'id': item.data['id']}))), ('todo.complete', registry.execute(ToolRequest('todo.complete', {'id': item.data['id']})))]:
        assert result.ok and registry.get(name).output_schema == {'task': 'object', 'id': 'string'}
        assert isinstance(result.data['task'], dict) and result.data['task']['id'] == result.data['id']
    for name in ('todo.list', 'todo.due'):
        result = registry.execute(ToolRequest(name))
        assert result.ok and isinstance(result.data['tasks'], list)
        assert result.data['count'] == len(result.data['tasks'])
        assert registry.get(name).output_schema == {'tasks': 'array', 'count': 'integer'}

def test_repair_google_metadata_matches_actual_provider_receipts(original):
    import sys
    sys.path.insert(0, str(ROOT / 'scripts/v36_engineering'))
    from fixtures import GoogleProvider, GoogleVault
    _, registry, _ = original
    registry.google_access._vault = GoogleVault()
    registry.google_access.transport = GoogleProvider()
    cases = [('gmail.read', {'id': 'message-v36'}), ('google.calendar.read', {'id': 'event-v36'}), ('google.drive.metadata', {'id': 'doc-v36'}), ('google.gmail.thread', {'id': 'thread-v36'}), ('google.tasks.list', {})]
    kinds = {'string': str, 'object': dict, 'array': list, 'boolean': bool, 'integer': int}
    for name, args in cases:
        result = registry.execute(ToolRequest(name, {**args, 'account': 'personal'}))
        assert result.ok, (name, result.message)
        contract = registry.get(name).output_schema
        assert 'data' not in contract
        assert all((key in result.data and isinstance(result.data[key], kinds[kind]) for key, kind in contract.items()))
    body = registry.execute(ToolRequest('gmail.read', {'id': 'message-v36', 'account': 'personal'})).data['body']
    assert isinstance(body, dict)

@pytest.mark.parametrize('error_id,should_be_empty', [('NoMatchingEventsFound', True), ('AccessDenied', False), ('FixtureNoMatchingEventsFoundAccessDenied', False)])
def test_repair_event_empty_scope_does_not_hide_other_failures(monkeypatch, error_id, should_be_empty):
    import subprocess
    from types import SimpleNamespace
    from hanni.tools import security, winshell
    dispatched = []
    def controlled_process(command, **kwargs):
        dispatched.append(command)
        return subprocess.CompletedProcess(command, 0 if should_be_empty else 1,
            '[]' if should_be_empty else '', '' if should_be_empty else error_id)
    monkeypatch.setattr(winshell, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(winshell, 'subprocess', SimpleNamespace(run=controlled_process))
    if should_be_empty:
        result = security._event_errors({'log': 'Application', 'hours': 1}, None, None)
        assert result.ok and result.data['total'] == 0 and (result.data['events'] == [])
    else:
        with pytest.raises(RuntimeError, match='system.event_errors failed'):
            security._event_errors({'log': 'Application', 'hours': 1}, None, None)
    assert len(dispatched) == 1 and dispatched[0][0] == 'powershell.exe'

@pytest.mark.parametrize('utterance', ['Create an offline reminder: meeting tomorrow at 09:00.', 'Add to my notes a reminder about my calendar tomorrow at 09:00.', 'Create a task titled "put this on my calendar" due Friday at 5pm.', "Save a notebook entry for tomorrow's dinner at 8pm.", 'Please add a local record: calendar session next Monday at 11am.', 'Make a file named calendar.txt tomorrow at noon.'])
def test_repair_unseen_local_destinations_cannot_authorize_calendar_write(original, utterance):
    from hanni.mcp.host import McpHost
    from hanni.tools.calendar_routing import calendar_create_request
    _, registry, _ = original
    assert calendar_create_request(utterance, timezone_name='America/New_York') is None
    decision = McpHost(registry, read_only=True, allowed_actions=('google_calendar.create',)).route(utterance)
    assert not any((t.capability_id in {'google_calendar.create', 'google.calendar.create'} for t in decision.tools))

@pytest.mark.parametrize('utterance,title', [('Add "amber36 review" to my calendar tomorrow at 9am.', 'amber36 review'), ('Schedule a "notes cleanup task" in my Google calendar tomorrow at 9am.', 'notes cleanup task'), ('Book dinner next Saturday at 7pm.', 'dinner')])
def test_repair_unseen_explicit_calendar_destinations_preserve_owner_policy(original, connected_calendar, utterance, title):
    from hanni.mcp.host import McpHost
    from hanni.tools.calendar_routing import calendar_create_request
    _, registry, _ = original
    request = calendar_create_request(utterance, timezone_name='America/New_York')
    assert request is not None and request.arguments['summary'] == title
    allowed = McpHost(registry, read_only=True, allowed_actions=('google_calendar.create',)).route(utterance)
    assert any((t.capability_id in {'google_calendar.create', 'google.calendar.create'} for t in allowed.tools))
    denied = McpHost(registry, read_only=True).route(utterance)
    assert denied.status == 'blocked' and (not denied.tools)

def test_probe_evidence_published_only_after_complete_fsync(tmp_path, monkeypatch):
    from scripts.v3_review import service_process_probe
    target = tmp_path / 'independent-committed-evidence.json'
    prior = {'scope': 'old complete record'}
    target.write_text(json.dumps(prior), encoding='utf-8')
    original_fsync = service_process_probe.os.fsync
    observed = []

    def observe_fsync(fd):
        observed.append(json.loads(target.read_text(encoding='utf-8')))
        original_fsync(fd)
    monkeypatch.setattr(service_process_probe.os, 'fsync', observe_fsync)
    new = {'scope': 'new complete record', 'values': list(range(200))}
    service_process_probe.durable_json(target, new)
    assert observed == [prior]
    assert json.loads(target.read_text(encoding='utf-8')) == new
    assert not list(tmp_path.glob('*.publishing'))
_CALENDAR_ADDENDUM_PATH = ROOT / 'scripts/v36_verification/calendar_addendum_cases.json'
_CALENDAR_ADDENDUM = json.loads(_CALENDAR_ADDENDUM_PATH.read_text(encoding='utf-8'))
assert hashlib.sha256(_CALENDAR_ADDENDUM_PATH.read_bytes()).hexdigest() == '6191b2c91f1cbc7c12e6171b02c0afb4ba062e215c7bf8e5e1f44111d17b94fa'

@pytest.mark.parametrize('case', _CALENDAR_ADDENDUM['cases'], ids=lambda case: case['id'])
def test_calendar_activity_addendum_prospective_independent_cases(original, connected_calendar, case):
    from hanni.mcp.host import McpHost
    from hanni.tools.calendar_routing import calendar_create_request
    _, registry, _ = original
    request = calendar_create_request(case['request'], timezone_name='America/New_York')
    assert (request is not None) == case['calendar_write_menu']
    allowed = McpHost(registry, read_only=True, allowed_actions=('google_calendar.create',)).route(case['request'])
    selected = any((tool.capability_id in {'google_calendar.create', 'google.calendar.create'} for tool in allowed.tools))
    assert selected == case['calendar_write_menu']
    denied = McpHost(registry, read_only=True).route(case['request'])
    assert not any((tool.capability_id in {'google_calendar.create', 'google.calendar.create'} for tool in denied.tools))

@pytest.mark.parametrize('utterance,title', [('put dentist monday at 9', 'dentist'), ('add game night saturday 8pm', 'game night'), ('add office hours next monday 2pm', 'office hours')])
def test_calendar_activity_addendum_preserves_legacy_menu_expectations(original, connected_calendar, utterance, title):
    from hanni.mcp.host import McpHost
    from hanni.tools.calendar_routing import calendar_create_request
    _, registry, _ = original
    request = calendar_create_request(utterance, timezone_name='America/New_York')
    assert request is not None and request.arguments['summary'].casefold() == title
    allowed = McpHost(registry, read_only=True, allowed_actions=('google_calendar.create',)).route(utterance)
    assert any((tool.capability_id == 'google_calendar.create' for tool in allowed.tools))

@pytest.mark.parametrize('utterance,expected', [('Create note:07:45 class in my calendar next Thursday.', False), ('Add a local record:8pm party on my calendar next Wednesday.', False), ('Put ceramics practice Friday at 07:45 in my calendar.', True), ('Add "amber36 follow-up" at 18:20 to my calendar next Tuesday.', True)])
def test_calendar_activity_addendum_distinguishes_body_colon_and_clock(original, connected_calendar, utterance, expected):
    from hanni.mcp.host import McpHost
    from hanni.tools.calendar_routing import calendar_create_request
    _, registry, _ = original
    request = calendar_create_request(utterance, timezone_name='America/New_York')
    assert (request is not None) == expected
    allowed = McpHost(registry, read_only=True, allowed_actions=('google_calendar.create',)).route(utterance)
    assert any((tool.capability_id == 'google_calendar.create' for tool in allowed.tools)) == expected
