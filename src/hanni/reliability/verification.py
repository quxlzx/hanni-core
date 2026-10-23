"""Conservative evidence checks. Follow-ups are reads through the same registry.

External tool assertions are never independent verification. Receipt metadata
and process existence do not imply a visible window, audio or historical cause.
"""
from datetime import datetime
import hashlib
import math
import os
from collections.abc import Mapping
from pathlib import Path

def evidence(status='UNVERIFIED', method='tool_response', scope='execution_acknowledgement', *, independent=False, checks=None):
    return {'status': status, 'method': method, 'scope': scope, 'independent': independent, 'checks': checks or {}}

def _same_time(actual, expected):
    if not isinstance(actual, str) or not isinstance(expected, str):
        return False
    try:
        return datetime.fromisoformat(actual.replace('Z', '+00:00')) == datetime.fromisoformat(expected.replace('Z', '+00:00'))
    except ValueError:
        return False

def inspect_result(name, arguments, result, *, definition=None):
    """No follow-up calls; classify actual result evidence with bounded fields."""
    if not isinstance(result, Mapping) or not result.get('ok'):
        return evidence(scope='failed_execution')
    data = result.get('data')
    if not isinstance(data, Mapping):
        return evidence(scope='missing_result_data')
    if name.startswith('mcp.'):
        return evidence(scope='external_tool_response')
    read = definition is not None and (definition.side_effect == 'read' or
           definition.side_effect is None and definition.permission_level == definition.risk_level == 0)
    if data.get('partial') or data.get('truncated') or data.get('errors') or data.get('state') == 'partial':
        return evidence('PARTIALLY_VERIFIED' if read else 'UNVERIFIED',
                        scope='returned_excerpt' if read else 'action_receipt', checks={'partial': True})
    if name in {'google_calendar.create', 'google.calendar.create'}:
        expected_key = 'date' if arguments.get('all_day') else 'dateTime'
        start = data.get('start') or {}
        end = data.get('end') or {}
        expected_start = arguments.get('start_date' if expected_key == 'date' else 'start')
        expected_end = arguments.get('end_date' if expected_key == 'date' else 'end')
        compare = (lambda a, b: isinstance(a, str) and a == b) if expected_key == 'date' else _same_time
        checks = {'identifier_returned': isinstance(data.get('id'), str) and bool(data['id']),
                  'title_matches': isinstance(arguments.get('summary'), str) and bool(arguments['summary'].strip())
                     and data.get('summary') == arguments['summary'].strip(),
                  'schedule_matches': isinstance(start, Mapping) and isinstance(end, Mapping)
                     and compare(start.get(expected_key), expected_start) and compare(end.get(expected_key), expected_end),
                  'created': data.get('created') is True}
        return evidence('PARTIALLY_VERIFIED' if all(checks.values()) else 'UNVERIFIED', 'provider_response', 'calendar_creation_receipt', checks=checks)
    if name == 'app.open':
        if data.get('verified') is True and data.get('outcome') in {'window_detected', 'window_focused', 'verified'}:
            return evidence('VERIFIED', 'window_state', 'visible_application_window', independent=True)
        return evidence('PARTIALLY_VERIFIED' if data.get('outcome') == 'process_started' else 'UNVERIFIED',
                        'launch_response', 'process_launch_only', checks={'process_id_returned': type(data.get('process_id')) is int})
    if name.startswith('spotify.'):
        if name == 'spotify.launch' and data.get('running') is True:
            return evidence('VERIFIED', 'process_state', 'spotify_process_running', independent=True)
        observed = type(data.get('playing')) is bool and any(isinstance(data.get(key), str) for key in ('title', 'now_playing', 'window_title'))
        return evidence('PARTIALLY_VERIFIED' if observed else 'UNVERIFIED', 'window_title', 'reported_playback_state', checks={'audio_verified': False, 'window_state_returned': observed})
    if name == 'folder.open':
        return evidence('PARTIALLY_VERIFIED', 'filesystem_state', 'directory_exists_launch_requested', checks={'window_verified': False})
    if name in {'file.write', 'file.copy', 'file.move', 'file.mkdir', 'file.delete', 'process.stop'}:
        return evidence(scope='action_receipt')
    if name == 'system.stats':
        checks = {key: type(data.get(key)) in (int, float) and 0 <= data[key] <= 100 for key in ('cpu_percent', 'ram_percent')}
        return evidence('VERIFIED' if all(checks.values()) else 'PARTIALLY_VERIFIED' if any(checks.values()) else 'UNVERIFIED', 'tool_result', 'current_resource_snapshot', checks=checks)
    if name in {'process.top_cpu', 'process.top_memory', 'process.list'}:
        rows = data.get('processes')
        metric = 'cpu_percent' if name == 'process.top_cpu' else 'rss_mb' if name == 'process.top_memory' else 'memory_percent'
        valid = isinstance(rows, list) and bool(rows) and all(isinstance(row, Mapping) and
            isinstance(row.get('name'), str) and bool(row['name'].strip()) and
            type(row.get(metric)) in (int, float) and math.isfinite(row[metric]) and row[metric] >= 0
            and (name != 'process.list' or row[metric] <= 100) for row in rows)
        return evidence('VERIFIED' if valid else 'UNVERIFIED', 'tool_result', 'returned_process_snapshot', checks={'valid_rows': valid})
    if data.get('available') is False or data.get('state') in {'unavailable', 'not_connected', 'not_found'}:
        return evidence('UNVERIFIED', scope='resource_unavailable')
    return evidence('VERIFIED' if read and data else 'UNVERIFIED', 'tool_result', 'returned_data_only' if read else 'action_receipt')

def verify_action(registry, definition, request, arguments, result):
    initial = inspect_result(definition.name, arguments, result.to_dict(), definition=definition)
    if not result.ok or definition.external_definition_hash:
        return initial
    from hanni.tools.base import ToolRequest
    def read(name, values):
        target = registry.get(name)
        if target.permission_level != 0 or target.risk_level != 0 or target.external_definition_hash or target.side_effect not in {None, 'read'}:
            raise PermissionError('Verification requires an original low-risk read.')
        return registry.execute(ToolRequest(name, values, actor_profile=request.actor_profile,
                              confirmed=False, source='tool.verification', correlation_id=request.correlation_id,
                              expected_definition=target, execution_guard=request.execution_guard))
    name, data = definition.name, result.data
    try:
        if name == 'app.open' and type(data.get('process_id')) is int and data['process_id'] > 0:
            observed = read('process.inspect', {'pid': data['process_id']})
            exists = observed.ok and observed.data.get('pid') == data['process_id'] and observed.data.get('exists') is True
            return evidence('PARTIALLY_VERIFIED' if exists else 'UNVERIFIED', 'process_state', 'exact_launch_process', independent=True,
                            checks={'process_running': exists, 'window_verified': False})
        if name in {'file.write', 'file.copy', 'file.move', 'file.mkdir', 'file.delete'}:
            path = arguments.get('destination') if name in {'file.copy', 'file.move'} else arguments.get('path')
            if name in {'file.copy', 'file.move'}:
                destination = read('file.stat', {'path': path})
                if destination.ok and destination.data.get('exists') is True and destination.data.get('type') == 'folder':
                    path = str(Path(path) / Path(arguments['source']).name)
            observed = read('file.stat', {'path': path, 'hash': name in {'file.write', 'file.copy'}})
            matches = observed.ok and observed.data.get('exists') is (name != 'file.delete')
            checks = {'expected_existence': matches}
            if name == 'file.write':
                # Path.write_text uses newline=None: Windows translates every
                # LF, including one already preceded by CR. Match the actual
                # handler's byte semantics rather than changing file writes.
                expected = hashlib.sha256(str(arguments.get('text', '')).replace('\n', os.linesep).encode('utf-8')).hexdigest()
                checks['content_matches'] = observed.data.get('sha256') == expected
            if name == 'file.copy':
                checks['content_matches'] = bool(data.get('source_sha256')) and observed.data.get('sha256') == data.get('source_sha256')
            if name == 'file.mkdir':
                checks['directory_type'] = observed.data.get('type') == 'folder'
            if name == 'file.move':
                source = read('file.stat', {'path': arguments.get('source')})
                checks['source_absent'] = source.ok and source.data.get('exists') is False
            return evidence('VERIFIED' if all(checks.values()) else 'UNVERIFIED', 'read_after_write', 'requested_filesystem_state', independent=True, checks=checks)
        if name == 'process.stop':
            observed = read('process.inspect', {'pid': arguments.get('pid')})
            absent = observed.ok and observed.data.get('exists') is False
            return evidence('VERIFIED' if absent else 'UNVERIFIED', 'process_state', 'requested_pid_absent', independent=True, checks={'process_absent': absent})
        if name in {'todo.add', 'todo.complete'}:
            task = data.get('task') or {}
            identifier = data.get('id')
            if not isinstance(identifier, str) or task.get('id') != identifier:
                return initial
            observed = read('todo.get', {'id': identifier})
            saved = observed.data.get('task') or {} if observed.ok else {}
            checks = {'identifier_matches': saved.get('id') == identifier}
            if name == 'todo.add':
                checks['fields_match'] = all(str(saved.get(key, '')).strip() == str(value).strip()
                                            for key, value in arguments.items() if key in {'title', 'course'})
                if arguments.get('due'):
                    from hanni.tools.whenparse import parse_when
                    expected_due = parse_when(str(arguments['due']).strip(), default_minutes=0).start.isoformat()
                    checks['due_matches'] = _same_time(saved.get('due'), expected_due)
            else:
                checks['completed'] = saved.get('status') == 'completed'
            return evidence('VERIFIED' if all(checks.values()) else 'UNVERIFIED', 'read_after_write', 'saved_local_task', independent=True, checks=checks)
        if name == 'note.append' and isinstance(data.get('path'), str):
            observed = read('file.read', {'path': data['path']})
            text = str(arguments.get('text') or '').strip()
            body = observed.data.get('text', '') if observed.ok else ''
            lines = body.splitlines() if isinstance(body, str) else []
            matches = bool(text and lines and lines[-1].endswith(text) and not observed.data.get('truncated'))
            return evidence('VERIFIED' if matches else 'UNVERIFIED', 'read_after_write', 'last_saved_note', independent=True, checks={'last_entry_matches': matches})
        if name in {'google_calendar.create', 'google.calendar.create'} and initial['status'] == 'PARTIALLY_VERIFIED':
            observed = read('google.calendar.read', {'account': data.get('account'), 'calendar_id': data.get('calendar_id'), 'id': data.get('id')})
            rows = observed.data.get('events', []) if observed.ok else []
            found = next((row for row in rows if row.get('id') == data['id']), None)
            checks = {'identifier_matches': found is not None, 'schedule_matches': False, 'title_matches': False}
            if found:
                checked = inspect_result(name, arguments, {'ok': True, 'data': {**found, 'created': True}})
                checks['schedule_matches'] = checked['checks'].get('schedule_matches', False)
                checks['title_matches'] = checked['checks'].get('title_matches', False)
            return evidence('VERIFIED' if all(checks.values()) else 'UNVERIFIED', 'provider_read_after_write', 'created_calendar_resource', independent=True, checks=checks)
    except Exception:
        # Do not repeat the action or claim confirmation after a failed check.
        initial = {**initial, 'checks': {**initial['checks'], 'followup_unavailable': True}}
    return initial
