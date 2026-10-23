"""Independent adversarial probes. Original registry gates remain real."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from uuid import uuid4
from pathlib import Path
import pytest
from hanni.config.loader import load_config
from hanni.tools.base import ToolContext, ToolDefinition, ToolRegistry, ToolRequest, ToolResult, ToolPermissionError
from hanni.tools.audit import ToolAuditLog
from hanni.core.shutdown import EmergencyStop, StopSource
from hanni.core.identity import Actor
from hanni.models.client import ModelProtocolError
from hanni.reliability.execution import ReliabilityService
from hanni.reliability.context import request_scope
from hanni.reliability.verification import inspect_result, verify_action
ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture
def lane(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path / 'state', env={})
    service = ReliabilityService(config.paths.data_dir)
    registry = ToolRegistry(ToolContext(config.permissions, EmergencyStop(), ToolAuditLog(config.paths.data_dir), 'America/New_York', service))
    yield (registry, service, config.paths.data_dir)
    service.close()

@pytest.mark.parametrize('name', ['custom.create_record', 'custom.remove_record', 'clipboard.write'])
def test_unknown_mutation_response_does_not_establish_verified_outcome(name):
    verdict = inspect_result(name, {}, {'ok': True, 'data': {'created': True, 'verified': True, 'id': 'untrusted-receipt'}})
    assert verdict['status'] != 'VERIFIED'

def test_persisted_pending_approval_cannot_be_offered_as_live_or_resumed_after_restart(tmp_path):
    from hanni.tools.registry import build_default_registry
    from hanni.tools.session import ToolAwareSession

    class Fallback:

        def stream_response(self, *args, **kwargs):
            yield 'No action requested.'

        def record_turn(self, *args, **kwargs):
            pass
    root = tmp_path / 'state'
    config = load_config(ROOT / 'config', data_dir=root, env={})
    registry = build_default_registry(config)
    original = registry.context.reliability
    target = tmp_path / 'retained-private-file.txt'
    target.write_text('keep', encoding='utf8')
    assistant = ToolAwareSession(Fallback(), registry)
    ''.join(assistant._execute(ToolRequest('file.delete', {'path': str(target)})))
    pending = original.snapshot()['tasks'][0]
    assert pending['execution_status'] == 'waiting_approval' and target.exists()
    original.close()
    restarted = ReliabilityService(root)
    try:
        registry.context.reliability = restarted
        current = restarted.snapshot()['tasks'][0]
        assert current['execution_status'] == 'approval_unavailable'
        assert current['approval_active'] is False
        assert current['events'] == pending['events']
        assert current['steps'] == pending['steps']
        fresh_session = ToolAwareSession(Fallback(), registry)
        ''.join(fresh_session.stream_response('yes'))
        assert target.read_text(encoding='utf8') == 'keep'
        assert restarted.snapshot()['tasks'][0]['execution_status'] == 'approval_unavailable'
    finally:
        restarted.close()

def test_mcp_self_assertion_never_becomes_independent_verification():
    verdict = inspect_result('mcp.server.import', {}, {'ok': True, 'data': {'verified': True, 'created': True}})
    assert verdict['status'] == 'UNVERIFIED'
    assert verdict['independent'] is False

@pytest.mark.parametrize('partial_flag', [{'partial': True}, {'truncated': True}, {'errors': ['receipt-only']}, {'state': 'partial'}])
def test_unknown_mutation_partial_receipt_does_not_establish_any_outcome_evidence(partial_flag):
    definition = ToolDefinition('custom.create_record', 'Controlled unknown mutation.', 1, 1, {}, {}, lambda *args: None, side_effect='reversible_write')
    verdict = inspect_result(definition.name, {}, {'ok': True, 'data': {'received': True, **partial_flag}}, definition=definition)
    assert verdict['status'] == 'UNVERIFIED'

def test_invalid_process_measurements_do_not_establish_verified_diagnostic():
    verdict = inspect_result('process.top_memory', {}, {'ok': True, 'data': {'processes': [{'name': '', 'rss_mb': 'not a measured number'}]}})
    assert verdict['status'] != 'VERIFIED'

def test_empty_media_result_does_not_establish_playback_evidence():
    verdict = inspect_result('spotify.next', {}, {'ok': True, 'data': {}})
    assert verdict['status'] == 'UNVERIFIED'

def register(registry, name, handler, *, schema=None, permission=0, risk=0, effect='read', confirmation=None, external=''):
    registry.register(ToolDefinition(name, 'Controlled independent fixture.', permission, risk, schema or {}, {}, handler, side_effect=effect, requires_confirmation_if=confirmation, external_definition_hash=external))
    return registry.get(name)

def test_calendar_readback_wrong_requested_title_is_not_verified(lane):
    registry, service, _ = lane
    arguments = {'summary': 'Dentist appointment', 'start': '2026-10-10T15:00:00-04:00', 'end': '2026-10-10T16:00:00-04:00'}
    actual = {'id': 'controlled-event-id', 'summary': 'Different appointment', 'start': {'dateTime': arguments['start']}, 'end': {'dateTime': arguments['end']}}

    def observed_read(values, context, request):
        return ToolResult('google.calendar.read', True, 'Controlled provider readback.', {'events': [actual]})
    register(registry, 'google.calendar.read', observed_read, schema={'account': str, 'calendar_id': str, 'id': str})
    definition = ToolDefinition('google_calendar.create', 'Controlled provider receipt.', 1, 1, {}, {}, lambda *args: None, side_effect='reversible_write')
    receipt = ToolResult(definition.name, True, 'Creation accepted.', {**actual, 'created': True, 'account': 'fixture', 'calendar_id': 'primary'})
    verdict = verify_action(registry, definition, ToolRequest(definition.name, arguments, confirmed=True), arguments, receipt)
    assert verdict['status'] != 'VERIFIED', 'Matching identifier/time alone does not verify the requested appointment title'

def test_verification_read_retains_confirmation_gate_and_does_not_repeat_write(lane):
    registry, service, _ = lane
    calls = []

    def write(args, ctx, request):
        calls.append('write')
        return ToolResult('file.write', True, 'Receipt only.', {'path': args['path']})

    def read(args, ctx, request):
        calls.append('stat')
        return ToolResult('file.stat', True, 'File exists.', {'exists': True, 'sha256': hashlib.sha256(b'x').hexdigest()})
    register(registry, 'file.write', write, schema={'path': str, 'text': str}, permission=2, risk=2, effect='reversible_write')
    register(registry, 'file.stat', read, schema={'path': str, 'hash': bool}, confirmation=lambda args: 'Independent additional approval required')
    result = registry.execute(ToolRequest('file.write', {'path': 'controlled.txt', 'text': 'x'}, confirmed=True))
    assert calls == ['write']
    assert result.verification['status'] == 'UNVERIFIED'
    assert result.verification['checks']['followup_unavailable'] is True

def test_verification_refuses_capability_that_is_not_read_only(lane):
    registry, _, _ = lane
    calls = []
    action = register(registry, 'file.write', lambda *args: ToolResult('file.write', True, 'receipt', {}), schema={'path': str, 'text': str}, permission=2, risk=2, effect='reversible_write')
    register(registry, 'file.stat', lambda *args: calls.append('side_effect') or ToolResult('file.stat', True, 'changed', {'exists': True, 'sha256': hashlib.sha256(b'x').hexdigest()}), schema={'path': str, 'hash': bool}, effect='reversible_write')
    verdict = verify_action(registry, action, ToolRequest('file.write', confirmed=True), {'path': 'controlled.txt', 'text': 'x'}, ToolResult('file.write', True, 'receipt', {}))
    assert calls == []
    assert verdict['status'] == 'UNVERIFIED'

def test_stop_after_write_denies_verification_read_without_repeating_action(lane):
    registry, service, _ = lane
    calls = []

    def write(args, ctx, request):
        calls.append('write')
        ctx.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('independent-test'))
        return ToolResult('file.write', True, 'Receipt only.', {})
    register(registry, 'file.write', write, schema={'path': str, 'text': str}, permission=2, risk=2, effect='reversible_write')
    register(registry, 'file.stat', lambda *args: calls.append('stat') or ToolResult('file.stat', True, 'exists', {'exists': True}), schema={'path': str, 'hash': bool})
    result = registry.execute(ToolRequest('file.write', {'path': 'controlled.txt', 'text': 'x'}, confirmed=True))
    assert calls == ['write']
    assert result.verification['status'] == 'UNVERIFIED'

def test_non_owner_cannot_execute_either_action_or_verification(lane):
    registry, service, _ = lane
    calls = []
    register(registry, 'file.write', lambda *args: calls.append('write') or ToolResult('file.write', True, 'receipt', {}), schema={'path': str, 'text': str}, permission=2, risk=2, effect='reversible_write')
    with pytest.raises(ToolPermissionError):
        registry.execute(ToolRequest('file.write', {'path': 'controlled.txt', 'text': 'x'}, actor_profile='everyone_else', confirmed=True))
    assert calls == []
    task = service.snapshot()['tasks'][0]
    assert task['execution_status'] == 'rejected'

def test_file_write_hash_mismatch_is_not_verified(lane):
    registry, _, _ = lane
    register(registry, 'file.write', lambda *args: ToolResult('file.write', True, 'receipt', {}), schema={'path': str, 'text': str}, permission=2, risk=2, effect='reversible_write')
    register(registry, 'file.stat', lambda *args: ToolResult('file.stat', True, 'exists', {'exists': True, 'sha256': '0' * 64}), schema={'path': str, 'hash': bool})
    result = registry.execute(ToolRequest('file.write', {'path': 'controlled.txt', 'text': 'expected'}, confirmed=True))
    assert result.verification['status'] == 'UNVERIFIED'
    assert result.verification['checks']['content_matches'] is False

def test_trace_store_does_not_persist_payload_message_or_source_suffix(lane):
    registry, service, state = lane
    marker = 'independent-private-note-not-a-token-9fb1'
    register(registry, 'custom.observe', lambda args, *rest: ToolResult('custom.observe', True, marker, {'raw_body': marker}), schema={'query': str})
    with request_scope(uuid4(), 'mcp.' + marker):
        registry.execute(ToolRequest('custom.observe', {'query': marker}, source='mcp.' + marker))
    task = service.snapshot()['tasks'][0]
    assert marker not in json.dumps(task)
    service.close()
    for path in (state / 'logs').glob('execution_traces.sqlite3*'):
        assert marker.encode() not in path.read_bytes()

@pytest.mark.parametrize('kind', ['corrupt', 'future'])
def test_broken_trace_storage_preserves_bytes_and_never_repeats_action(lane, kind):
    registry, service, state = lane
    path = state / 'logs/execution_traces.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == 'corrupt':
        path.write_bytes(b'existing evidence: not SQLite')
    else:
        db = sqlite3.connect(path)
        db.execute('PRAGMA user_version=999')
        db.commit()
        db.close()
    before = path.read_bytes()
    calls = []
    register(registry, 'custom.action', lambda *args: calls.append('once') or ToolResult('custom.action', True, 'receipt', {}), permission=1, risk=1, effect='reversible_write')
    result = registry.execute(ToolRequest('custom.action'))
    assert result.ok and calls == ['once']
    assert service.snapshot()['available'] is False
    service.close()
    assert path.read_bytes() == before

def test_model_protocol_failure_has_failed_execution_status(lane):
    _, service, _ = lane
    with pytest.raises(ModelProtocolError):
        with service.task('mcp.session'):
            raise ModelProtocolError('Controlled malformed response.')
    task = service.snapshot()['tasks'][0]
    assert task['execution_status'] == 'failed'
    assert task['error_class'] == 'EXECUTION_FAILED'

def test_failed_non_idempotent_action_cannot_be_replayed(lane):
    registry, service, _ = lane
    from hanni.mcp.host import McpHost
    from hanni.mcp.session import McpToolSession
    writes = []

    def uncertain(args, ctx, request):
        writes.append(dict(args))
        return ToolResult('custom.create', False, 'Response lost after committing.', {}, error={'code': 'TIMEOUT', 'retryable': True})
    definition = register(registry, 'custom.create', uncertain, schema={'title': str}, permission=1, risk=1, effect='reversible_write')
    host = McpHost(registry, allowed_actions=('custom.create',))
    session = McpToolSession(None, None, host)
    tool = host._as_tool(definition)
    first = session._call(tool, {'title': 'controlled record'})
    second = session._call(tool, {'title': 'controlled record'})
    assert first['ok'] is False and second['ok'] is False
    assert second['error']['code'] == 'DUPLICATE_ATTEMPTED_ACTION'
    assert len(writes) == 1

def test_safe_read_retry_stops_after_one_retry_and_rechecks_permissions(lane):
    registry, service, _ = lane
    from dataclasses import replace
    from hanni.mcp.host import McpHost
    from hanni.mcp.session import McpToolSession
    attempts = []

    def transient(args, ctx, request):
        attempts.append('read')
        if len(attempts) == 1:
            return ToolResult('custom.observe', False, 'Transient read failure.', {}, error={'code': 'NETWORK_ERROR', 'retryable': True})
        return ToolResult('custom.observe', True, 'Measured.', {'count': 3})
    original = ToolDefinition('custom.observe', 'Read-only controlled observation.', 0, 0, {}, {}, transient, side_effect='read', retry_attempts=5, retry_safe=True)
    registry.register(original)
    definition = registry.get('custom.observe')
    session = McpToolSession(None, None, McpHost(registry))
    with service.task('test'):
        result = session._call(session.host._as_tool(definition), {})
    assert result['ok'] is True
    assert len(attempts) == 2
    assert service.snapshot()['tasks'][0]['retry_count'] == 1

def test_external_read_timeout_does_not_assume_replay_safety(lane):
    registry, _, _ = lane
    from hanni.mcp.host import McpHost
    from hanni.mcp.session import McpToolSession
    attempts = []
    name = 'mcp.server.external'
    definition = register(registry, name, lambda *args: attempts.append('rpc') or ToolResult(name, False, 'Unknown completion.', {}, error={'code': 'TIMEOUT', 'retryable': True}), external='f' * 64)
    host = McpHost(registry)
    result = McpToolSession(None, None, host)._call(host._as_tool(definition), {})
    assert result['ok'] is False and attempts == ['rpc']

def test_partial_task_failure_keeps_success_and_failed_scope_distinct(lane):
    registry, service, _ = lane
    register(registry, 'custom.observe', lambda *args: ToolResult('custom.observe', True, 'Observed.', {'count': 3}))
    register(registry, 'custom.unavailable', lambda *args: ToolResult('custom.unavailable', False, 'Unavailable.', {}, error={'code': 'AUTH_REQUIRED', 'retryable': False}))
    with service.task('test'):
        registry.execute(ToolRequest('custom.observe'))
        registry.execute(ToolRequest('custom.unavailable'))
    task = service.snapshot()['tasks'][0]
    assert task['execution_status'] == 'partial'
    assert task['verification_status'] != 'VERIFIED'
    assert any((step['error_class'] == 'AUTH_REQUIRED' for step in task['steps']))

def test_cancelled_request_has_actual_cancelled_outcome_without_fake_execution(lane):
    registry, service, _ = lane
    with pytest.raises(GeneratorExit):
        with service.task('test'):
            raise GeneratorExit()
    task = service.snapshot()['tasks'][0]
    assert task['execution_status'] == 'cancelled'
    assert task['verification_status'] == 'UNVERIFIED'
    assert task['steps'] == []

def test_trace_step_bound_does_not_hide_later_failure(lane):
    registry, service, _ = lane
    counter = []

    def observe(*args):
        counter.append(1)
        if len(counter) == 65:
            return ToolResult('custom.observe', False, 'Final step failed.', {}, error={'code': 'TIMEOUT', 'retryable': False})
        return ToolResult('custom.observe', True, 'Measured.', {'count': 3})
    register(registry, 'custom.observe', observe)
    with service.task('test'):
        for _ in range(65):
            registry.execute(ToolRequest('custom.observe'))
    task = service.snapshot()['tasks'][0]
    assert len(counter) == 65
    assert task['execution_status'] != 'succeeded'
    assert task['verification_status'] != 'VERIFIED'
