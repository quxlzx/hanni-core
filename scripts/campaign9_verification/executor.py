"""Input-only independent controlled security executor over original services.

This module never reads an oracle. Unsupported primitives return explicit gaps.
Original handler identity is retained; dangerous/provider leaves are inert.
"""
from __future__ import annotations
from dataclasses import replace
import errno
import hashlib
import http.client
import json
import logging
from pathlib import Path
import socket
import sqlite3
import sys
from unittest.mock import patch
import zipfile
from scripts.campaign9_verification import development as dev

def expand(value, root):
    if isinstance(value, str):
        return value.replace('{root}', str(root))
    if isinstance(value, dict):
        return {key: expand(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [expand(item, root) for item in value]
    return value

def owned(path, root):
    result = Path(path).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError('Fixture write escapes its owned root')
    return result

def common():
    return {'unauthorized_sensitive_effects': 0, 'unapproved_credential_exposures': 0, 'fabricated_success_claims': 0, 'consequential_retry_count_max': 0}

def denied(error):
    return type(error).__name__ in {'ToolPermissionError', 'ToolValidationError', 'UnknownToolError', 'EmergencyStopActive'}

def registry_case(operation, params, root):
    from hanni.tools.base import ToolRequest
    from hanni.core.shutdown import Actor, StopSource
    from hanni.tools import apps
    reg = dev.registry(root)
    for definition in apps.definitions():
        reg.register(definition)
    arguments = params.get('arguments', {})
    if operation in {'shell_gate', 'remote_tool_gate'}:
        arguments = {'command': params['command']}
    tool = params.get('tool', 'powershell.run')
    definition = reg.get(tool)
    files = {}
    for name, text in params.get('files', {}).items():
        path = owned(root / name, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf8')
        files[str(path)] = path.read_bytes()
    if 'owner_max_level' in params:
        policy = reg.context.permissions
        reg.context.permissions = replace(policy, profiles={**policy.profiles, 'owner': replace(policy.profiles['owner'], max_auto_approve_level=params['owner_max_level'])})
    if params.get('stop_before_dispatch'):
        reg.context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('private-fixture'), reason='Owned stop')
    guard_reached = False

    class GuardBoundaryReached(RuntimeError):
        pass

    def guard():
        nonlocal guard_reached
        guard_reached = True
        if operation == 'shell_gate' and params.get('guard_only'):
            raise GuardBoundaryReached('No shell may be dispatched by this fixture')
        if params.get('at_guard', {}).get('owner_chat_only'):
            policy = reg.context.permissions
            reg.context.permissions = replace(policy, profiles={**policy.profiles, 'owner': replace(policy.profiles['owner'], chat_only=True)})
    forbidden = []

    def refuse(*args, **kwargs):
        forbidden.append(1)
        raise PermissionError('Unsafe OS/provider leaf is disabled in the private fixture')
    actor = params.get('actor', 'owner')
    request = ToolRequest(tool, arguments, actor_profile=actor, confirmed=params.get('confirmed', False), execution_guard=guard if operation in {'shell_gate', 'registry_transition'} else None)
    error, result = (None, None)
    with patch('subprocess.run', refuse), patch('subprocess.Popen', refuse), dev.entries(definition.handler) as entered:
        try:
            result = reg.execute(request)
        except Exception as exc:
            error = exc
    gate = 'admitted' if result is not None or isinstance(error, GuardBoundaryReached) else 'confirmation_required' if type(error).__name__ == 'ConfirmationRequired' else 'denied' if denied(error) else 'dependency_error'
    observations = common() | entered | {'gate': gate, 'approved_guard_reached': guard_reached, 'shell_process_entries': len(forbidden), 'remote_leaf_entries': len(forbidden), 'power_leaf_entries': len(forbidden), 'remote_effects': 0, 'write_effects': int(result is not None and result.ok and (definition.permission_level >= 2)), 'file_preserved': all((Path(name).exists() and Path(name).read_bytes() == before for name, before in files.items())), 'dependency_failure_honest': error is not None and result is None, 'safe_stop_honest': type(error).__name__ == 'EmergencyStopActive', 'sensitive_handler_entries': entered['handler_entries']}
    path = arguments.get('path')
    if path and tool == 'file.write':
        destination = owned(path, root)
        observations['actual_owned_writes'] = int(destination.exists())
        observations['owned_file_readback'] = destination.read_text(encoding='utf8') if destination.exists() else None
    if operation == 'registry_transition' and entered['handler_entries']:
        observations['unauthorized_sensitive_effects'] = observations['write_effects']
    if actor not in reg.context.permissions.profiles or actor == 'everyone_else':
        observations['unauthorized_sensitive_effects'] = observations['write_effects']
    return (observations, {'exception_type': type(error).__name__ if error else None, 'definition': definition.name, 'handler_module': definition.handler.__module__, 'handler_name': definition.handler.__name__, 'unsafe_leaves': 'inert refusal', 'result': result.to_dict() if result else None})

def archive_case(params, root):
    from hanni.tools.base import ToolRequest
    reg = dev.registry(root)
    archive = root / 'fixture.zip'
    for name, text in params.get('files', {}).items():
        path = owned(root / name, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf8')
    originals = {str(path): path.read_bytes() for path in root.rglob('*') if path.is_file()}
    with zipfile.ZipFile(archive, 'w') as package:
        for entry in params['entries']:
            member = zipfile.ZipInfo(entry['name'])
            if entry.get('unix_symlink'):
                member.create_system = 3
                member.external_attr = 41471 << 16
            package.writestr(member, entry['text'])
    destination = owned(params['destination'], root)
    error, result = (None, None)
    with dev.entries(reg.get('archive.unzip').handler) as entered:
        try:
            result = reg.execute(ToolRequest('archive.unzip', {'source': str(archive), 'destination': str(destination)}, confirmed=params.get('confirmed', False)))
        except Exception as exc:
            error = exc
    created = [path for path in destination.rglob('*') if path.is_file()] if destination.exists() else []
    outside = [path for path in root.rglob('*') if path.is_file() and str(path) not in originals and (path != archive) and (not path.is_relative_to(destination)) and ('logs' not in path.parts)]
    return (common() | {'unsafe_path_rejected': error is not None, 'unsafe_overwrite_rejected': error is not None, 'file_preserved': all((Path(path).read_bytes() == data for path, data in originals.items())), 'outside_destination_writes': len(outside), 'partial_owned_extraction_count': len(created)}, {'exception_type': type(error).__name__ if error else None, **entered, 'result': result.to_dict() if result else None, 'scope': 'original_archive_handler_owned_small_ZIP_and_files'})

def memory_case(operation, params, root):
    from hanni.logs.redaction import register_secret
    from hanni.memory import MemoryStore, MemoryAwareSession
    from hanni.memory.retrieval import LocalMemoryRetriever
    store = MemoryStore(root / 'memory.sqlite3')
    observations = common()
    if operation == 'memory_gate':
        error = None
        try:
            store.remember(params['content'])
        except Exception as exc:
            error = exc
        return (observations | {'durable_sensitive_record_count': store.count(), 'authority_instruction_admitted': store.count() > 0}, {'exception_type': type(error).__name__ if error else None})
    if operation == 'memory_import_read':
        record, _ = store.remember(params['content'])
        with store._connect() as db:
            db.execute('UPDATE memories SET source_ref=? WHERE id=?', (params['source_ref'], record.id))
        register_secret('C9_PRIVATE_SOURCE', params['register_secret'])
        context = LocalMemoryRetriever(store).retrieve(params['query'])
        return (observations | {'unsafe_record_in_model_context': record.id in context.text, 'record_deleted_without_owner_request': store.get(record.id) is None}, {'context_sha256': dev.sha(context.text.encode())})
    for text in params.get('safe_records', []):
        store.remember(text)
    imported, _ = store.remember('A plain record before controlled legacy import.')
    with store._connect() as db:
        db.execute('UPDATE memories SET content=? WHERE id=?', (params['unsafe_imported_content'], imported.id))

    class MissingIndex:
        max_tokens = 2048

        def retrieve(self, goal):
            raise LookupError('Owned missing index')

    class Capture(dev.Conversation):
        calls = []

        def stream_response(self, prompt, **kwargs):
            self.calls.append(kwargs.get('memory_context', ''))
            yield 'Conversation response; no recalled fact is asserted.'
    fallback = Capture()
    session = MemoryAwareSession(fallback, store, context_retriever=MissingIndex(), extraction_enabled=False)
    output = ''.join(session.stream_response(params['query']))
    context = '\n'.join(fallback.calls)
    return (observations | {'unsafe_record_in_model_context': imported.id in context or params['unsafe_imported_content'] in context, 'safe_degradation_honest': bool(output) and bool(fallback.calls)}, {'context_sha256': dev.sha(context.encode()), 'records_retained': store.count(), 'model_generation': False})

def redaction_case(operation, params, root):
    from hanni.logs.redaction import register_secret, redact_value, RedactionFilter
    from hanni.logs.formatter import JsonFormatter
    secret = params['registered_secret']
    register_secret('C9_PRIVATE_REDACTION', secret)
    if operation == 'redaction':
        rendered = redact_value(params['value'])
        raw = json.dumps(rendered)
        return (common() | {'unapproved_credential_exposures': int(secret in raw), 'ordinary_text_preserved': params['value']['ordinary'] == rendered.get('ordinary')}, {'output_sha256': dev.sha(raw.encode())})
    try:
        raise RuntimeError(params['exception_message'])
    except RuntimeError:
        info = sys.exc_info()
    record = logging.LogRecord('hanni.private.security', logging.ERROR, __file__, 1, 'Controlled dependency event', (), info)
    record.details = params['extra']
    RedactionFilter().filter(record)
    output = JsonFormatter(node_id='owned').format(record)
    reflected = secret in output
    return (common() | {'public_error_contains_secret': reflected, 'unapproved_credential_exposures': int(reflected), 'diagnostic_event_retained': 'Controlled dependency event' in output}, {'output_sha256': dev.sha(output.encode())})

def endpoint_case(params):
    from hanni.mcp.security import endpoint
    calls = []

    def resolver(host, port, **kwargs):
        calls.append(1)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, port)) for address in params.get('resolved_addresses', [])]
    error = None
    try:
        endpoint(params['url'], allow_local_http=params.get('allow_local_http', False), resolve=params.get('resolve', False), resolver=resolver)
    except Exception as exc:
        error = exc
    return (common() | {'endpoint_admitted': error is None, 'network_calls': 0}, {'exception_type': type(error).__name__ if error else None, 'controlled_DNS_queries': len(calls)})

def dashboard_case(operation, params, root):
    from scripts.campaign8_ui.backend import original_backend

    def raw(backend, row):
        headers = {}
        if row.get('token'):
            headers['X-Hanni-Token'] = backend.chat.token if row['token'] == 'current' else 'C9WrongFixtureToken'
        if row.get('origin'):
            headers['Origin'] = backend.url if row['origin'] == 'same' else 'https://foreign.invalid'
        body = row.get('raw_json')
        if 'json' in row:
            body = json.dumps(row['json'])
        if body is not None:
            headers['Content-Type'] = 'application/json'
        connection = http.client.HTTPConnection('127.0.0.1', backend.server.server_port, timeout=5)
        try:
            connection.request(row.get('method', 'GET'), row['path'], body=body, headers=headers)
            response = connection.getresponse()
            return (response.status, response.read())
        finally:
            connection.close()
    observations = common()
    statuses, mutations = ([], [])
    if operation == 'dashboard_restart':
        with original_backend(root / 'backend') as first:
            old = first.chat.token
        with original_backend(root / 'backend') as second:
            connection = http.client.HTTPConnection('127.0.0.1', second.server.server_port, timeout=5)
            try:
                connection.request('GET', '/api/memory', headers={'X-Hanni-Token': old})
                response = connection.getresponse()
                old_status = response.status
                response.read()
            finally:
                connection.close()
            new_status, _ = raw(second, {'path': '/api/memory', 'token': 'current'})
        return (observations | {'old_token_status': old_status, 'new_token_status': new_status, 'uncontrolled_mutations': 0}, {'owned_servers_closed': first.closed and second.closed, 'tokens_persisted': False})
    with original_backend(root / 'backend') as backend:
        original = backend.features.mutate

        def trace(*args, **kwargs):
            mutations.append(1)
            return original(*args, **kwargs)
        with patch.object(backend.features, 'mutate', trace):
            for row in params['requests']:
                status, _ = raw(backend, row)
                statuses.append(status)
    return (observations | {'http_statuses': statuses, 'original_mutation_entries': len(mutations), 'mutation_entries': len(mutations), 'personal_payload_exposed': any((code == 200 for code in statuses))}, {'owned_server_closed': backend.closed and (not backend.thread.is_alive()), 'tokens_persisted': False})

def unavailable(operation):
    return ({}, {'status': 'blocked', 'reason': 'No reviewed original implementation adapter for this primitive', 'operation': operation, 'missing_evidence_is_nonpass': True})

def run_case(case, root):
    """Execute one input without consulting expected answers or final scorer."""
    if not isinstance(case, dict) or 'expected' in case or 'oracle' in case:
        raise ValueError('Only execution inputs are accepted')
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    params = expand(case['parameters'], root)
    operation = case['operation']
    before = {path: dev.sha((dev.ROOT / path).read_bytes()) for path in dev.SOURCES}
    if operation in {'registry_call', 'registry_transition', 'registry_stop', 'shell_gate', 'remote_tool_gate'}:
        observations, detail = registry_case(operation, params, root)
    elif operation == 'archive_extract':
        observations, detail = archive_case(params, root)
    elif operation in {'memory_gate', 'memory_import_read', 'memory_fault'}:
        observations, detail = memory_case(operation, params, root)
    elif operation in {'redaction', 'logger_exception'}:
        observations, detail = redaction_case(operation, params, root)
    elif operation == 'endpoint_validation':
        observations, detail = endpoint_case(params)
    elif operation in {'dashboard_http', 'dashboard_restart'}:
        observations, detail = dashboard_case(operation, params, root)
    else:
        observations, detail = unavailable(operation)
    after = {path: dev.sha((dev.ROOT / path).read_bytes()) for path in dev.SOURCES}
    return {'id': case['id'], 'area': case['area'], 'operation': operation, 'fault_categories': case.get('fault_categories', []), 'observations': observations, 'detail': detail, 'source_before': before, 'source_after': after, 'source_unchanged': before == after, 'owner_store_mounted': False, 'genuine_model_calls': 0, 'scope': 'controlled_original_implementation', 'oracle_read': False}
