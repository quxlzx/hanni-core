"""Execution safety contracts through the real registry, not host.call mocks."""
from dataclasses import replace
import json
from pathlib import Path
from uuid import uuid4
import pytest
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.mcp.session import McpToolSession
from hanni.models.client import ModelToolCall, ModelTurn, ModelProtocolError
from hanni.reliability.context import request_scope, current_request_id
from hanni.reliability.execution import ReliabilityService, get_service, close_service
from hanni.reliability.verification import inspect_result
from hanni.tools.base import ToolRequest, ToolResult, ToolPermissionError
from hanni.tools.registry import build_default_registry
from tests.helpers import write_config_dir

@pytest.fixture
def registry(tmp_path):
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    registry = build_default_registry(config)
    registry.context.reliability = ReliabilityService(tmp_path / 'data')
    yield registry
    registry.context.reliability.close()

def substitute(registry, name, handler, **fields):
    original = registry.get(name)
    registry.unregister(name, expected=original)
    registry.register(replace(original, handler=handler, **fields))

class Fallback:
    history = ()

    def stream_response(self, prompt, **kwargs):
        yield 'I successfully completed everything.'

    def record_turn(self, prompt, response):
        pass

class Calls:

    def __init__(self, capability, arguments=None, repeated=False, parse_failure=False):
        self.capability, self.arguments = (capability, arguments or {})
        self.round = 0
        self.repeated, self.parse_failure = (repeated, parse_failure)

    def complete_with_tools(self, messages, tools, **kwargs):
        self.round += 1
        if self.round == 1 or self.repeated:
            return ModelTurn('', (ModelToolCall(str(self.round), McpHost._wire_name(self.capability), self.arguments),))
        if self.parse_failure:
            raise ModelProtocolError('private model payload must not enter trace')
        return ModelTurn('Everything succeeded and is independently verified.')

    def chat(self, messages, **kwargs):
        return 'Everything succeeded and is independently verified.'

def session(registry, client, actions=()):
    return McpToolSession(Fallback(), client, McpHost(registry, read_only=True, allowed_actions=actions))

def test_request_scope_reused_by_original_registry_and_trace(registry):
    identifier = str(uuid4())
    with request_scope(identifier, 'browser'):
        result = registry.execute(ToolRequest('time.now', {}))
        assert current_request_id() == identifier
    assert current_request_id() is None
    task = registry.context.reliability.snapshot()['tasks'][0]
    assert task['request_id'] == identifier and task['source'] == 'browser'
    assert result.verification['status'] == 'VERIFIED'
    states = [event['state'] for event in task['steps'][0]['events']]
    assert states == ['REQUESTED', 'PLANNED', 'EXECUTING', 'TOOL_COMPLETED', 'VERIFYING', 'VERIFIED']

def test_file_write_verified_through_real_stat_and_no_content_trace(registry, tmp_path):
    target = tmp_path / 'owner-private-name.txt'
    text = 'Owner private request body that must never be persisted in traces'
    result = registry.execute(ToolRequest('file.write', {'path': str(target), 'text': text}, confirmed=True))
    assert result.verification['status'] == 'VERIFIED'
    assert result.verification['independent'] is True
    trace = json.dumps(registry.context.reliability.snapshot())
    assert text not in trace and str(target) not in trace and ('owner-private-name' not in trace)
    assert 'content_matches' in trace

def test_verification_rechecks_original_authorization(registry, tmp_path):
    original = registry.get('file.stat')
    registry.unregister('file.stat', expected=original)
    registry.register(replace(original, permission_level=3, risk_level=3))
    target = tmp_path / 'check.txt'
    result = registry.execute(ToolRequest('file.write', {'path': str(target), 'text': 'safe'}, confirmed=True))
    assert target.read_text() == 'safe'
    assert result.verification['status'] == 'UNVERIFIED'
    assert result.verification['checks']['followup_unavailable'] is True

@pytest.mark.parametrize('text', ['first\nsecond\n', 'first\r\nsecond\r\n'])
def test_multiline_write_verification_matches_original_platform_newline_behavior(registry, tmp_path, text):
    import os
    target = tmp_path / 'multiline.txt'
    result = registry.execute(ToolRequest('file.write', {'path': str(target), 'text': text}, confirmed=True))
    assert target.read_bytes() == text.replace('\n', os.linesep).encode()
    assert result.verification['status'] == 'VERIFIED' and result.verification['checks']['content_matches']

@pytest.mark.parametrize('operation', ['file.copy', 'file.move'])
def test_existing_directory_destination_checks_actual_final_file(registry, tmp_path, operation):
    source = tmp_path / 'source.txt'
    source.write_bytes(b'original fixture bytes')
    destination = tmp_path / 'destination'
    destination.mkdir()
    result = registry.execute(ToolRequest(operation, {'source': str(source), 'destination': str(destination)}, confirmed=True))
    assert (destination / 'source.txt').read_bytes() == b'original fixture bytes'
    assert result.verification['status'] == 'VERIFIED'
    if operation == 'file.move':
        assert not source.exists()

def test_stop_during_post_write_check_does_not_repeat_action(registry, tmp_path):
    from hanni.core.shutdown import StopSource
    from hanni.core.identity import Actor
    original = registry.get('file.write')
    calls = []

    def write_and_stop(args, context, request):
        calls.append(1)
        result = original.handler(args, context, request)
        context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('test'), reason='fixture')
        return result
    substitute(registry, 'file.write', write_and_stop)
    result = registry.execute(ToolRequest('file.write', {'path': str(tmp_path / 'once.txt'), 'text': 'once'}, confirmed=True))
    assert calls == [1] and result.verification['status'] == 'UNVERIFIED'

def test_unknown_write_receipt_never_verified(registry):
    definition = registry.get('timer.set')
    result = inspect_result('timer.set', {}, {'ok': True, 'data': {'success': True, 'verified': True}}, definition=definition)
    assert result['status'] == 'UNVERIFIED' and (not result['independent'])

def test_external_self_reported_verified_never_independent():
    result = inspect_result('mcp.abcd.read', {}, {'ok': True, 'data': {'verified': True, 'success': True}})
    assert result['status'] == 'UNVERIFIED' and result['scope'] == 'external_tool_response'

def test_calendar_missing_identifier_or_wrong_schedule_unverified(registry):
    definition = registry.get('google_calendar.create')
    arguments = {'summary': 'Fixture appointment', 'start': '2026-10-10T14:00:00-04:00', 'end': '2026-10-10T15:00:00-04:00'}
    data = {'created': True, 'summary': arguments['summary'], 'start': {'dateTime': arguments['start']}, 'end': {'dateTime': arguments['end']}}
    assert inspect_result(definition.name, arguments, {'ok': True, 'data': data}, definition=definition)['status'] == 'UNVERIFIED'
    data['id'] = 'fixture-id'
    assert inspect_result(definition.name, arguments, {'ok': True, 'data': data}, definition=definition)['status'] == 'PARTIALLY_VERIFIED'
    data['end'] = {'dateTime': '2026-10-10T17:00:00-04:00'}
    assert inspect_result(definition.name, arguments, {'ok': True, 'data': data}, definition=definition)['status'] == 'UNVERIFIED'

def test_failed_non_idempotent_action_not_replayed_by_model(registry):
    calls = []

    def launch(args, context, request):
        calls.append(dict(args))
        return ToolResult('app.open', False, 'Launch outcome unknown.', error={'code': 'TIMEOUT', 'retryable': True})
    substitute(registry, 'app.open', launch)
    assistant = session(registry, Calls('app.open', {'app': 'Notepad'}, repeated=True), ('app.open',))
    answer = ''.join(assistant.stream_response('open notepad'))
    assert len(calls) == 1
    assert 'Everything succeeded' not in answer
    assert assistant.last_trace['verification_status'] == 'UNVERIFIED'

def test_explicit_read_retry_bounded_and_original_gates_repeat(registry):
    calls = []

    def stats(args, context, request):
        calls.append(request)
        if len(calls) == 1:
            return ToolResult('system.stats', False, 'Temporary network failure.', error={'code': 'NETWORK_ERROR', 'retryable': True})
        return ToolResult('system.stats', True, 'CPU 21%, RAM 43%.', {'cpu_percent': 21, 'ram_percent': 43})
    substitute(registry, 'system.stats', stats, side_effect='read', retry_safe=True)
    assistant = session(registry, Calls('system.stats'))
    ''.join(assistant.stream_response('what is my cpu usage'))
    assert len(calls) == 2
    assert assistant.last_trace['retry_count'] == 1
    assert assistant.last_trace['verification_status'] == 'VERIFIED'
    assert all((request.actor_profile == 'owner' and (not request.confirmed) for request in calls))

def test_read_retry_optin_required_and_auth_denial_not_retried(registry):
    calls = []

    def denied(args, context, request):
        calls.append(1)
        return ToolResult('system.stats', False, 'Not authorized.', error={'code': 'PERMISSION_DENIED', 'retryable': True})
    substitute(registry, 'system.stats', denied, retry_safe=True, side_effect='read')
    assistant = session(registry, Calls('system.stats'))
    answer = ''.join(assistant.stream_response('what is my cpu usage'))
    assert len(calls) == 1 and 'Everything succeeded' not in answer

def test_malformed_read_cannot_preserve_model_false_success(registry):
    substitute(registry, 'system.stats', lambda *args: ToolResult('system.stats', True, 'Malformed observation.', {'cpu_percent': 'invalid', 'ram_percent': None}))
    assistant = session(registry, Calls('system.stats'))
    answer = ''.join(assistant.stream_response('what is my cpu usage'))
    assert 'Everything succeeded' not in answer and 'independently verified' not in answer
    assert 'could not be verified' in answer and assistant.last_trace['verification_status'] == 'UNVERIFIED'

def test_model_parse_error_after_write_retains_only_evidence(registry):
    calls = []

    def launch(args, context, request):
        calls.append(1)
        return ToolResult('app.open', True, 'Windows accepted the launch request.', {'app': args['app'], 'outcome': 'accepted', 'verified': False})
    substitute(registry, 'app.open', launch)
    assistant = session(registry, Calls('app.open', {'app': 'Notepad'}, parse_failure=True), ('app.open',))
    answer = ''.join(assistant.stream_response('open notepad'))
    assert len(calls) == 1 and 'independently verified' not in answer and ('successfully completed everything' not in answer)
    assert assistant.last_trace['error_class'] == 'MODEL_RESPONSE_ERROR'
    assert assistant.last_trace['execution_status'] == 'partial'

def test_validation_failure_is_class_only_trace(registry):
    with pytest.raises(Exception):
        registry.execute(ToolRequest('time.now', {'private_argument': 'secret owner content'}))
    record = json.dumps(registry.context.reliability.snapshot())
    assert 'secret owner content' not in record and 'private_argument' not in record
    assert 'INVALID_ARGUMENTS' in record

def test_corrupt_store_preserved_original_execution_still_once(tmp_path, registry):
    root = tmp_path / 'corrupt'
    path = root / 'logs' / 'execution_traces.sqlite3'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'original corrupt bytes preserved')
    service = ReliabilityService(root)
    registry.context.reliability = service
    registry.execute(ToolRequest('time.now'))
    assert not service.snapshot()['available'] and path.read_bytes() == b'original corrupt bytes preserved'

def test_service_cache_lazy_shared_and_close_releases_files(tmp_path):
    service = get_service(tmp_path)
    assert get_service(tmp_path) is service
    assert not (tmp_path / 'logs').exists()
    assert service.snapshot()['tasks'] == [] and (not (tmp_path / 'logs').exists())
    with service.task('test'):
        pass
    close_service(tmp_path)
    (tmp_path / 'logs' / 'execution_traces.sqlite3').unlink()

def test_retry_safe_rejects_non_boolean_metadata(registry):
    original = registry.get('time.now')
    with pytest.raises(ValueError, match='retry_safe'):
        registry.register(replace(original, name='fixture.invalid', retry_safe='true'))

def test_original_pending_confirmation_trace_resumes_after_explicit_yes(registry, tmp_path):
    from hanni.tools.session import ToolAwareSession
    target = tmp_path / 'remove.txt'
    target.write_text('fixture')
    assistant = ToolAwareSession(Fallback(), registry)
    ''.join(assistant._execute(ToolRequest('file.delete', {'path': str(target)})))
    task = registry.context.reliability.snapshot()['tasks'][0]
    assert task['execution_status'] == 'waiting_approval' and task['completed_at'] is None and target.exists()
    ''.join(assistant.stream_response('yes'))
    task = registry.context.reliability.snapshot()['tasks'][0]
    assert task['execution_status'] == 'succeeded' and (not target.exists())
    assert task['steps'][0]['approval'] == 'confirmation_required'
    assert task['steps'][-1]['approval'] == 'explicit_confirmation'

def test_original_pending_confirmation_cancel_never_executes(registry, tmp_path):
    from hanni.tools.session import ToolAwareSession
    target = tmp_path / 'keep.txt'
    target.write_text('fixture')
    assistant = ToolAwareSession(Fallback(), registry)
    ''.join(assistant._execute(ToolRequest('file.delete', {'path': str(target)})))
    ''.join(assistant.stream_response('cancel'))
    task = registry.context.reliability.snapshot()['tasks'][0]
    assert task['execution_status'] == 'cancelled' and target.exists()

def test_pending_confirmation_is_historical_after_service_restart(registry, tmp_path):
    from hanni.tools.session import ToolAwareSession
    target = tmp_path / 'keep-on-restart.txt'
    target.write_text('fixture')
    assistant = ToolAwareSession(Fallback(), registry)
    ''.join(assistant._execute(ToolRequest('file.delete', {'path': str(target)})))
    service = registry.context.reliability
    original = service.snapshot()['tasks'][0]
    assert original['approval_active'] is True
    service.close()
    reloaded = ReliabilityService(tmp_path / 'data')
    record = reloaded.snapshot()['tasks'][0]
    assert record['execution_status'] == 'approval_unavailable' and record['approval_active'] is False
    assert record['events'] == original['events'] and record['completed_at'] is None and target.exists()
    reloaded.close()

def test_closing_original_tool_session_cancels_only_pending_confirmation(registry, tmp_path):
    from hanni.tools.session import ToolAwareSession
    target = tmp_path / 'keep-on-close.txt'
    target.write_text('fixture')
    assistant = ToolAwareSession(Fallback(), registry)
    ''.join(assistant._execute(ToolRequest('file.delete', {'path': str(target)})))
    assistant.close()
    assert registry.context.reliability.snapshot()['tasks'][0]['execution_status'] == 'cancelled'
    assert assistant._pending_confirmation is None and target.exists()

@pytest.mark.parametrize('due', ['2026-10-10T15:00:00', 'tomorrow at 3pm'])
def test_task_verification_uses_original_due_normalization(registry, tmp_path, due):
    from hanni.tools.todos import TodoStore
    from hanni.tools.whenparse import parse_when
    result = registry.execute(ToolRequest('todo.add', {'title': 'Fixture due normalization', 'due': due}, confirmed=True))
    saved = TodoStore(tmp_path / 'data').get(result.data['id'])
    assert saved['due'] == parse_when(due, default_minutes=0).start.isoformat()
    assert result.verification['status'] == 'VERIFIED'
    assert result.verification['checks']['due_matches'] is True

def test_original_calendar_transient_aggregate_retries_once(registry):
    from hanni.tools.google_access import GoogleAccessError
    from tests.unit.test_google_access import Vault
    access = registry.google_access
    access._vault = Vault({'personal': {'email': 'fixture@example.invalid', 'calendar_ids': ['primary'], 'credentials': {}}})
    calls = []

    def provider(account, path, params):
        calls.append(path)
        if len(calls) == 1:
            raise GoogleAccessError('Transient fixture read', 'api_error')
        return {'items': [{'id': 'fixture-id', 'summary': 'Fixture appointment', 'start': {'dateTime': '2026-10-10T15:00:00-04:00'}, 'end': {'dateTime': '2026-10-10T16:00:00-04:00'}}]}
    access.transport = provider
    answer = ''.join(session(registry, Calls('google_calendar.agenda')).stream_response('what is on my calendar tomorrow'))
    assert len(calls) == 2 and 'Fixture appointment' in answer

@pytest.mark.parametrize('partial,code', [(False, 'permission_denied'), (True, 'api_error')])
def test_calendar_denial_or_partial_results_never_retry(registry, partial, code):
    from hanni.tools.google_access import GoogleAccessError
    from tests.unit.test_google_access import Vault
    access = registry.google_access
    access._vault = Vault()
    calls = []

    def provider(account, path, params):
        calls.append(account)
        if account == 'school' or not partial:
            raise GoogleAccessError('Fixture failure', code)
        return {'items': [{'id': 'fixture-id', 'summary': 'Fixture appointment', 'start': {'dateTime': '2026-10-10T15:00:00-04:00'}, 'end': {'dateTime': '2026-10-10T16:00:00-04:00'}}]}
    access.transport = provider
    result = registry.execute(ToolRequest('google_calendar.agenda', {'account': 'all', 'start_date': '2026-10-10', 'days': 1}))
    assert not result.ok and (not result.error) and (len(calls) == 2)

def test_original_missing_file_answer_explains_failed_check(registry, tmp_path):
    path = tmp_path.parent / f'missing-{uuid4().hex}.txt'
    assistant = McpToolSession(Fallback(), Calls('file.read', {'path': str(path)}), McpHost(registry, read_only=False))
    answer = ''.join(assistant.stream_response(f'read {path}'))
    assert 'could not complete the requested check' in answer.lower()
    assert answer != str(path) and 'Everything succeeded' not in answer

def test_success_different_arguments_does_not_erase_failed_retry_scope(registry):
    calls = []

    def measured(values, context, request):
        calls.append(values['limit'])
        if values['limit'] == 1:
            return ToolResult('process.top_memory', False, 'Fixture transient failure', error={'code': 'NETWORK_ERROR', 'retryable': True})
        return ToolResult('process.top_memory', True, 'Fixture other scope evidence', {'processes': [{'name': 'fixture', 'rss_mb': 40}]})
    substitute(registry, 'process.top_memory', measured, argument_constraints={'limit': {'required': True}})

    class ChangedRead(Calls):

        def complete_with_tools(self, messages, tools, **kwargs):
            self.round += 1
            if self.round <= 2:
                return ModelTurn('', (ModelToolCall(str(self.round), McpHost._wire_name('process.top_memory'), {'limit': self.round}),))
            return ModelTurn('Fixture other scope evidence')
    assistant = session(registry, ChangedRead('process.top_memory'))
    ''.join(assistant.stream_response('what is eating my RAM'))
    assert calls == [1, 1, 2]
    assert assistant.last_trace['execution_status'] == 'partial'
    assert assistant.last_trace['verification_status'] == 'PARTIALLY_VERIFIED'
    steps = assistant.last_trace['steps']
    assert steps[0]['attempt_group'] == steps[1]['attempt_group'] != steps[2]['attempt_group']
    assert [step['attempts'] for step in steps] == [1, 2, 1]
