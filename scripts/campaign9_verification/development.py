"""Independent exposed-development probes. Never opens private final material.

Original handlers and authority layers execute; dangerous shell/provider leaves
are explicitly inert. Receipts retain booleans, counts and hashes, never secrets.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import zipfile
ROOT = Path(__file__).resolve().parents[2]
SOURCES = ('src/hanni/tools/base.py', 'src/hanni/tools/session.py', 'src/hanni/tools/files.py', 'src/hanni/tools/content.py', 'src/hanni/mcp/host.py', 'src/hanni/mcp/manager.py', 'src/hanni/memory/session.py', 'src/hanni/dashboard/server.py', 'src/hanni/logs/formatter.py', 'src/hanni/logs/redaction.py', 'src/hanni/models/client.py', 'src/hanni/tools/audit.py', 'src/hanni/dashboard/gateway.py')

def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def permissions():
    from hanni.config.schema import parse_permissions
    return parse_permissions({'levels': [{'level': i, 'name': f'tier{i}', 'auto_approve_allowed': i < 3} for i in range(4)], 'profiles': {'owner': {'max_auto_approve_level': 2, 'chat_only': False}, 'everyone_else': {'max_auto_approve_level': -1, 'chat_only': True}}})

def registry(root: Path):
    from hanni.core.shutdown import EmergencyStop
    from hanni.tools.audit import ToolAuditLog
    from hanni.tools.base import ToolContext, ToolRegistry
    from hanni.tools import files, content, powershell
    result = ToolRegistry(ToolContext(permissions(), EmergencyStop(), ToolAuditLog(root)))
    for module in (files, content, powershell):
        for definition in module.definitions():
            result.register(definition)
    return result

@contextmanager
def entries(handler):
    counter = {'handler_entries': 0}
    code, previous = (handler.__code__, sys.getprofile())

    def observe(frame, event, arg):
        if event == 'call' and frame.f_code is code:
            counter['handler_entries'] += 1
    sys.setprofile(observe)
    try:
        yield counter
    finally:
        sys.setprofile(previous)

class Conversation:

    def stream_response(self, prompt, **kwargs):
        yield 'A controlled conversation reply; no operation performed.'

def malformed_confirmation(root):
    from hanni.tools.base import ToolRequest
    reg = registry(root)
    rows = []
    for index, value in enumerate(('no', 2, {'authorized': False}, False, True)):
        victim = root / f'confirmation-{index}.txt'
        victim.write_text('Synthetic owned artifact', encoding='utf8')
        exception = None
        with entries(reg.get('file.delete').handler) as counter:
            try:
                reg.execute(ToolRequest('file.delete', {'path': str(victim)}, confirmed=value))
            except Exception as exc:
                exception = type(exc).__name__
        actual_delete = not victim.exists()
        expected_delete = value is True
        rows.append({'id': f'typed-confirmation-{index}', 'confirmed_type': type(value).__name__, **counter, 'actual_owned_deletions': int(actual_delete), 'exception': exception, 'passed': actual_delete == expected_delete, 'scope': 'original_registry_and_file_handler_owned_temp_file'})
    return rows

def pending_confirmation(root):
    from hanni.tools.session import ToolAwareSession
    from hanni.tools import powershell
    reg, rows = (registry(root), [])
    followups = ('yes, but do not execute the command', 'yes, describe the permissions instead', 'go ahead and tell me what the script would do', 'no', 'yes')
    for index, followup in enumerate(followups):
        calls = []

        def inert_shell(command, **kwargs):
            calls.append(sha(command[-1].encode()))
            return SimpleNamespace(returncode=0, stdout='Controlled shell leaf', stderr='')
        session = ToolAwareSession(Conversation(), reg)
        try:
            with patch.object(powershell.subprocess, 'run', inert_shell):
                first = ''.join(session.stream_response('run powershell command: Write-Output development-probe'))
                before = session._pending_confirmation is not None
                ''.join(session.stream_response(followup))
            rows.append({'id': f'pending-confirmation-{index}', 'initial_pending': before, 'initial_confirmation_message': 'confirmation' in first, 'mock_shell_entries': len(calls), 'actual_shell_processes': 0, 'passed': before and len(calls) == int(followup == 'yes'), 'scope': 'original_session_registry_shell_handler_inert_subprocess_leaf'})
        finally:
            session.close()
    return rows

def sensitive_source(root):
    from hanni.mcp.host import McpHost
    reg = registry(root)
    source, ordinary = (root / 'credentials.json', root / 'public-copy.txt')
    credential = secrets.token_urlsafe(31)
    source.write_text(json.dumps({'secret': credential}), encoding='utf8')
    host = McpHost(reg, allowed_actions=('file.copy', 'archive.zip'))

    def call(name, arguments):
        return host.call(host._as_tool(reg.get(name)), arguments)
    denied = False
    try:
        denied = call('file.read', {'path': str(source)}).get('ok') is False
    except Exception:
        denied = True
    rows = []
    for name, destination in (('file.copy', ordinary), ('archive.zip', root / 'public-copy.zip')):
        error = None
        with entries(reg.get(name).handler) as counter:
            try:
                call(name, {'source': str(source), 'destination': str(destination)})
            except Exception as exc:
                error = type(exc).__name__
        raw_secret_written = False
        if destination.exists():
            if destination.suffix == '.zip':
                with zipfile.ZipFile(destination) as archive:
                    raw_secret_written = any((credential.encode() in archive.read(item) for item in archive.namelist()))
            else:
                raw_secret_written = credential.encode() in destination.read_bytes()
        indirect_exposure = False
        if name == 'file.copy' and destination.exists():
            reply = call('file.read', {'path': str(destination)})
            indirect_exposure = credential in json.dumps(reply)
        rows.append({'id': 'sensitive-source-' + name, 'direct_sensitive_read_denied': denied, **counter, 'exception': error, 'owned_destination_created': destination.exists(), 'sensitive_bytes_copied': raw_secret_written, 'credential_reachable_via_ordinary_host_read': indirect_exposure, 'passed': denied and (not destination.exists()) and (counter['handler_entries'] == 0), 'scope': 'explicit_allowed_actions_original_host_and_handlers_temp_files'})
    plain = root / 'ordinary.txt'
    plain.write_text('An ordinary document', encoding='utf8')
    positive = root / 'ordinary-destination.txt'
    call('file.copy', {'source': str(plain), 'destination': str(positive)})
    rows.append({'id': 'ordinary-source-positive', 'passed': positive.read_text() == 'An ordinary document', 'scope': 'original_host_and_copy_handler_positive_readback'})
    return rows

def dispatch_boundary(root):
    from hanni.core.shutdown import Actor, StopSource
    from hanni.tools.base import ToolRequest
    rows = []
    for action in ('stop', 'revoke_profile', 'unchanged'):
        reg = registry(root / action)
        destination = root / action / 'guarded-directory'

        def transition():
            if action == 'stop':
                reg.context.emergency_stop.trip(source=StopSource.INTERNAL, requested_by=Actor.internal('independent-development'), reason='Controlled dispatch withdrawal')
            elif action == 'revoke_profile':
                policy = reg.context.permissions
                reg.context.permissions = replace(policy, profiles={**policy.profiles, 'owner': policy.profiles['everyone_else']})
        error = None
        with entries(reg.get('file.mkdir').handler) as counter:
            try:
                reg.execute(ToolRequest('file.mkdir', {'path': str(destination)}, execution_guard=transition))
            except Exception as exc:
                error = type(exc).__name__
        rows.append({'id': 'guard-boundary-' + action, **counter, 'exception': error, 'actual_owned_directory_created': destination.exists(), 'passed': destination.exists() == (action == 'unchanged'), 'scope': 'original_registry_supported_trusted_guard_and_mkdir_handler'})
    return rows

def mcp_outgoing_credentials(root):
    from hanni.config.schema import AppConfig, HanniConfig, Paths, PrivacyConfig, parse_models
    from hanni.mcp.manager import MCPManager
    from hanni.mcp.host import McpHost
    from hanni.mcp.security import resolve_credentials
    from hanni.tools.base import ToolRequest
    reg = registry(root)
    credential = secrets.token_urlsafe(33)
    env = {'C9_ONLY_INDEPENDENT_AUTH': credential}
    calls = []
    definition = {'name': 'independent.inspect', 'description': 'Read a controlled public marker.', 'inputSchema': {'type': 'object', 'properties': {'payload': {'type': 'object'}}, 'additionalProperties': False}, 'outputSchema': {'type': 'object', 'properties': {'marker': {'type': 'string'}}, 'required': ['marker'], 'additionalProperties': False}}

    class EmptyVault:

        def get(self, account):
            return None

        def get_password(self, service, key):
            return None

    class Connection:
        closed = False
        protected_values = ()

        def __init__(self, runtime, config, **kwargs):
            self.config = config

        def wait_ready(self):
            child, headers = resolve_credentials(self.config, env=env, vault=EmptyVault())
            self.protected_values = tuple(child.values()) + tuple((v.removeprefix('Bearer ') for v in headers.values()))

        def request(self, method, arguments=None):
            if method == 'list':
                return [definition]
            arguments['admit']()
            calls.append({'synthetic_secret_in_outgoing_arguments': credential in json.dumps(arguments['arguments']), 'mode': 'CONTROLLED_INERT_MCP_LEAF'})
            return {'content': [{'type': 'text', 'text': 'Public marker'}], 'structuredContent': {'marker': 'public'}}

        def cancel_tools(self, names):
            pass

        def signal_close(self):
            self.closed = True

        def close(self):
            self.closed = True
    manager = MCPManager(root, reg, connection_factory=Connection, env=env, vault=EmptyVault())
    rows = []
    try:
        added = manager.add({'name': 'Independent synthetic MCP', 'transport': 'streamable_http', 'url': 'http://127.0.0.1:49198/mcp', 'allow_local_http': True, 'auto_connect': False, 'auth': {'type': 'bearer_env', 'reference': 'C9_ONLY_INDEPENDENT_AUTH'}})
        connected = manager.connect(added['id'], approved=True, expected_config_hash=added['config_hash'])['servers'][-1]
        tool = connected['tools'][0]
        manager.approve_tools(connected['id'], [{'original_name': tool['original_name'], 'definition_hash': tool['definition_hash'], 'classification': 'read_only'}])
        for name, payload in (('nested-value', {'items': [{'note': credential}]}), ('dictionary-key', {credential: 'public value'}), ('ordinary-positive', {'items': ['A public observation']})):
            prior = len(calls)
            error = None
            try:
                reg.execute(ToolRequest(tool['internal_id'], {'payload': payload}))
            except Exception as exc:
                error = type(exc).__name__
            effects = calls[prior:]
            rows.append({'id': 'mcp-secret-' + name, 'rpc_entries': len(effects), 'exception': error, 'synthetic_secret_in_outgoing_arguments': any((x['synthetic_secret_in_outgoing_arguments'] for x in effects)), 'passed': len(effects) == int(name == 'ordinary-positive'), 'scope': 'original_credentials_approval_registry_adapter_inert_MCP_RPC_leaf'})
    finally:
        manager.close()
    return rows

def memory_disclosure(root):
    from hanni.logs.redaction import register_secret
    from hanni.memory import MemoryAwareSession, MemoryStore
    rows = []
    for index, (method, prompt) in enumerate((('remember', 'Remember that the atlas review is on Tuesday.'), ('delete', 'Forget atlas fixture review'), ('forget', 'Delete everything you remember about atlas fixture'))):
        store = MemoryStore(root / f'memory-{index}.sqlite3')
        store.remember('The atlas fixture review is on Monday.')
        fingerprint = store.fingerprint()
        canary = secrets.token_urlsafe(34)
        register_secret(f'C9_INDEPENDENT_{index}', canary)
        session = MemoryAwareSession(Conversation(), store)
        calls = []

        def unavailable(*args, **kwargs):
            calls.append(1)
            raise sqlite3.OperationalError('Temporary readback outage; protected diagnostic ' + canary)
        with patch.object(store, method, unavailable):
            output = ''.join(session.stream_response(prompt))
        rows.append({'id': 'memory-exception-' + method, 'dependency_entries': len(calls), 'synthetic_credential_reflected': canary in output, 'output_sha256': sha(output.encode()), 'store_unchanged': store.fingerprint() == fingerprint, 'passed': len(calls) == 1 and canary not in output and (store.fingerprint() == fingerprint), 'scope': 'original_memory_session_SQLite_store_controlled_mutation_error'})
    return rows

def logging_disclosure():
    from hanni.logs.redaction import register_secret, RedactionFilter
    from hanni.logs.formatter import JsonFormatter, TextFormatter
    canary = secrets.token_urlsafe(35)
    register_secret('C9_INDEPENDENT_LOG', canary)

    class Representation:

        def __str__(self):
            return 'Synthetic opaque object ' + canary
    rows = []
    for name, payload in (('key', {'inner': {canary: 'ordinary'}}), ('object', {'items': [Representation()]}), ('nested-string', {'items': [canary, 'public marker']})):
        record = logging.LogRecord('hanni.security.independent', logging.ERROR, __file__, 1, 'A public diagnostic', (), None)
        record.details = payload
        RedactionFilter().filter(record)
        output = JsonFormatter(node_id='owned-fixture').format(record)
        rows.append({'id': 'log-' + name, 'synthetic_credential_reflected': canary in output, 'json_parseable': isinstance(json.loads(output), dict), 'output_sha256': sha(output.encode()), 'passed': canary not in output, 'scope': 'original_filter_and_JSON_formatter'})
    for formatter in (JsonFormatter(node_id='owned-fixture'), TextFormatter()):
        try:
            raise RuntimeError('Protected exception ' + canary)
        except RuntimeError:
            info = sys.exc_info()
        record = logging.LogRecord('hanni.security.independent', logging.ERROR, __file__, 1, 'Public fault', (), info)
        output = formatter.format(record)
        rows.append({'id': 'log-exception-' + type(formatter).__name__, 'synthetic_credential_reflected': canary in output, 'output_sha256': sha(output.encode()), 'passed': canary not in output, 'scope': 'original_exception_formatter'})
    return rows

def http_disclosure(root):
    from scripts.campaign8_ui.backend import original_backend
    from hanni.logs.redaction import register_secret
    canary = secrets.token_urlsafe(37)
    register_secret('C9_INDEPENDENT_HTTP', canary)
    rows = []

    def request(backend, path, method='GET', body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', backend.server.server_port, timeout=6)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return (response.status, response.read())
        finally:
            connection.close()
    with original_backend(root / 'http-runtime') as backend:
        for route, target in (('/api/audio-devices', 'hanni.speech.audio_devices.routing_state'), ('/api/gpu-routing', 'hanni.dashboard.server.Handler._gpu_state')):
            with patch(target, side_effect=OSError('Owned dependency diagnostic ' + canary)):
                status, body = request(backend, route)
            rows.append({'id': 'http-disclosure-' + route, 'status': status, 'synthetic_credential_reflected': canary.encode() in body, 'output_sha256': sha(body), 'passed': status == 503 and canary.encode() not in body, 'scope': 'original_HTTP_handler_controlled_dependency_exception'})
        with patch.object(backend.features, 'mutate', side_effect=ValueError('Rejected private value ' + canary)) as leaf:
            status, body = request(backend, '/api/productivity', 'POST', '{}', {'Origin': backend.url, 'X-Hanni-Token': backend.chat.token, 'Content-Type': 'application/json'})
        rows.append({'id': 'http-disclosure-authorized-POST', 'status': status, 'dependency_entries': leaf.call_count, 'synthetic_credential_reflected': canary.encode() in body, 'output_sha256': sha(body), 'passed': status == 400 and canary.encode() not in body, 'scope': 'original_authorized_HTTP_handler_controlled_mutation_exception'})
        with patch.object(backend.features, 'mutate') as leaf:
            status, body = request(backend, '/api/productivity', 'POST', '{}', {'Origin': 'https://independent.invalid', 'X-Hanni-Token': backend.chat.token, 'Content-Type': 'application/json'})
        rows.append({'id': 'http-authority-positive', 'status': status, 'mutation_entries': leaf.call_count, 'passed': status == 403 and leaf.call_count == 0, 'scope': 'original_same_origin_gate'})
    assert backend.closed and (not backend.thread.is_alive())
    return rows

@contextmanager
def model_http(role, *, target=None, secret=None, redirect_code=302):
    observed = {'entries': 0, 'body_bytes': 0, 'methods': []}

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *args):
            pass

        def do_GET(self):
            self.reply()

        def do_POST(self):
            self.reply()

        def reply(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            observed['entries'] += 1
            observed['body_bytes'] += len(body)
            observed['methods'].append(self.command)
            if role == 'redirect':
                self.send_response(redirect_code)
                self.send_header('Location', target + '/changed-provider')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if role == 'error':
                self.send_response(401)
                result = json.dumps({'diagnostic': 'Protected credential ' + secret}).encode()
            elif self.command == 'GET' and role == 'health':
                self.send_response(200)
                result = b'{"status":"ok"}'
            else:
                self.send_response(200)
                result = b'data: {"choices":[{"delta":{"content":"Controlled HTTP protocol marker"}}]}\n\ndata: [DONE]\n\n'
            self.send_header('Content-Length', str(len(result)))
            self.end_headers()
            self.wfile.write(result)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield ('http://127.0.0.1:' + str(server.server_port), observed)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)
    assert not thread.is_alive()

def client_boundaries(root):
    from hanni.config.schema import parse_models
    from hanni.models.client import LlamaCppClient, ModelClientError
    from hanni.logs.redaction import register_secret

    def client(endpoint):
        spec = parse_models({'models': [{'id': 'independent-http-only', 'role': 'supervisor', 'backend': 'llama.cpp', 'model_file': str(root / 'NOT_LOADED.gguf'), 'endpoint': endpoint, 'request_timeout_seconds': 2, 'health_timeout_seconds': 2, 'keep_loaded': False}]}).supervisor
        return LlamaCppClient(spec, max_attempts=1)
    messages = [{'role': 'user', 'content': 'Synthetic protocol marker only.'}]
    rows = []
    for mode, code in (('health', 307), ('chat', 303)):
        with model_http('health' if mode == 'health' else 'stream') as (replacement, received), model_http('redirect', target=replacement, redirect_code=code) as (original, sent):
            instance = client(original + '/v1')
            error = None
            try:
                instance.health() if mode == 'health' else instance.chat(messages, max_tokens=12)
            except ModelClientError as exc:
                error = type(exc).__name__
        rows.append({'id': 'client-redirect-' + mode, 'redirect_code': code, 'original_entries': sent['entries'], 'changed_provider_entries': received['entries'], 'changed_provider_body_bytes': received['body_bytes'], 'exception': error, 'passed': sent['entries'] == 1 and received['entries'] == 0, 'scope': 'original_local_client_actual_two_owned_loopback_HTTP_servers_not_real_inference'})
    for mode in ('health', 'chat', 'tools'):
        canary = secrets.token_urlsafe(32)
        register_secret('C9_HTTP_PROVIDER_' + mode, canary)
        with model_http('error', secret=canary) as (endpoint, observed):
            instance = client(endpoint + '/v1')
            if mode == 'health':
                output = instance.health().detail
            else:
                try:
                    if mode == 'chat':
                        instance.chat(messages, max_tokens=12)
                    else:
                        instance.complete_with_tools(messages, tools=[])
                except ModelClientError as exc:
                    output = str(exc)
                else:
                    output = 'UNEXPECTED_SUCCESS'
        rows.append({'id': 'client-error-disclosure-' + mode, 'provider_entries': observed['entries'], 'synthetic_credential_reflected': canary in output, 'output_sha256': sha(output.encode()), 'passed': observed['entries'] == 1 and canary not in output and (output != 'UNEXPECTED_SUCCESS'), 'scope': 'original_local_client_actual_owned_HTTP_error_registered_synthetic_credential'})
    return rows

def audit_privacy(root):
    from hanni.tools import notes, powershell
    from hanni.tools.base import ToolRequest
    from hanni.logs.redaction import register_secret
    from hanni.dashboard.gateway import activity_snapshot
    reg = registry(root)
    for definition in notes.definitions(root):
        reg.register(definition)
    note = 'Moonstone design review moves to Thursday at fourteen hundred.'
    rows = []

    def metadata_retained(event):
        return event.get('ok') is True and event.get('actor_profile') == 'owner' and isinstance(event.get('timestamp'), str) and (type(event.get('duration_ms')) in (float, int)) and (event['duration_ms'] >= 0)
    for tool, arguments in (('note.append', {'text': note}), ('note.list', {}), ('note.search', {'query': 'Moonstone design review'})):
        result = reg.execute(ToolRequest(tool, arguments))
        raw = reg.context.audit.path.read_text(encoding='utf8')
        event = json.loads(raw.splitlines()[-1])
        serialized = json.dumps(event)
        phrase = note if tool != 'note.search' else arguments['query']
        rows.append({'id': 'audit-private-' + tool, 'private_text_in_sink': phrase in serialized, 'original_result_ok': result.ok, 'status_and_timing_retained': metadata_retained(event), 'passed': phrase not in serialized and result.ok and metadata_retained(event), 'scope': 'original_note_handler_actual_owned_note_and_audit_sink'})
    command_text = 'Write-Output Moonstone-private-maintenance-note'
    shell_output = 'A private diagnostic description for the Moonstone review'
    calls = []

    def inert(command, **kwargs):
        calls.append(1)
        return SimpleNamespace(returncode=0, stdout=shell_output, stderr='')
    with patch.object(powershell.subprocess, 'run', inert):
        result = reg.execute(ToolRequest('powershell.run', {'command': command_text}, confirmed=True))
    event = json.loads(reg.context.audit.path.read_text(encoding='utf8').splitlines()[-1])
    serialized = json.dumps(event)
    reflected = command_text in serialized or shell_output in serialized
    rows.append({'id': 'audit-private-shell', 'private_text_in_sink': reflected, 'mock_shell_entries': len(calls), 'actual_shell_processes': 0, 'status_and_timing_retained': metadata_retained(event), 'passed': not reflected and result.ok and metadata_retained(event), 'scope': 'original_shell_handler_inert_leaf_actual_audit_sink'})
    secret = secrets.token_urlsafe(34)
    register_secret('C9_INDEPENDENT_CORRELATION', secret)
    artifact = root / 'ordinary.txt'
    artifact.write_text('public fixture', encoding='utf8')
    reg.execute(ToolRequest('file.stat', {'path': str(artifact)}, correlation_id=secret))
    last = reg.context.audit.path.read_text(encoding='utf8').splitlines()[-1]
    last_event = json.loads(last)
    rows.append({'id': 'audit-registered-correlation', 'synthetic_credential_in_sink': secret in last, 'status_and_timing_retained': metadata_retained(last_event), 'passed': secret not in last and metadata_retained(last_event), 'scope': 'original_audit_metadata_serialization'})
    legacy_note = dict(last_event, tool='note.list', arguments={'query': note}, message=note, error=None)
    legacy_shell = dict(last_event, tool='powershell.run', arguments={'command': command_text}, message=shell_output, error=None)
    with reg.context.audit.path.open('a', encoding='utf8') as handle:
        for legacy in (legacy_note, legacy_shell):
            handle.write(json.dumps(legacy) + '\n')
    projected = json.dumps(activity_snapshot(root))
    projected_events = activity_snapshot(root)['events']
    status_timing = all((event.get('status') == 'completed' and type(event.get('duration_ms')) in (float, int) for event in projected_events))
    rows.append({'id': 'audit-historical-projection', 'private_note_in_projection': note in projected, 'private_shell_in_projection': command_text in projected or shell_output in projected, 'status_and_timing_retained': status_timing, 'passed': note not in projected and command_text not in projected and (shell_output not in projected) and status_timing, 'scope': 'original_activity_projection_actual_rows_plus_explicit_legacy_format_fixture'})
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--groups', nargs='+', choices=('confirmation', 'pending', 'sensitive-source', 'boundary', 'MCP', 'memory', 'logging', 'HTTP', 'client', 'audit'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    before = {name: sha((ROOT / name).read_bytes()) for name in SOURCES}
    archive = args.out / 'source-bytes'
    for name in SOURCES:
        destination = archive / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / name).read_bytes())
    rows = []
    with TemporaryDirectory(prefix='hanni-c9-independent-') as temporary:
        root = Path(temporary)
        for name, probe in (('confirmation', malformed_confirmation), ('pending', pending_confirmation), ('sensitive-source', sensitive_source), ('boundary', dispatch_boundary), ('MCP', mcp_outgoing_credentials), ('memory', memory_disclosure), ('logging', lambda _: logging_disclosure()), ('HTTP', http_disclosure), ('client', client_boundaries), ('audit', audit_privacy)):
            owned = root / name
            if args.groups and name not in args.groups:
                continue
            owned.mkdir()
            try:
                rows.extend(probe(owned))
            except Exception as exc:
                rows.append({'id': name + '-harness', 'harness_error': type(exc).__name__, 'passed': False})
    after = {name: sha((ROOT / name).read_bytes()) for name in SOURCES}
    receipt = {'campaign': 9, 'scope': 'independent_exposed_development_original_implementation', 'rows': rows, 'source_before': before, 'source_after': after, 'source_unchanged': before == after, 'original_sources_archived': True, 'owner_stores_mounted': False, 'real_model_calls': 0, 'real_shell_processes': 0, 'real_remote_or_MCP_provider_calls': 0, 'secret_values_persisted': False, 'private_final_material_opened': False}
    target = args.out / 'RESULTS.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'receipt': str(target), 'sha256': sha(target.read_bytes()), 'rows': len(rows), 'pass': sum((row['passed'] for row in rows)), 'nonpass': sum((not row['passed'] for row in rows)), 'harness_errors': sum(('harness_error' in row for row in rows)), 'source_unchanged': before == after}))
if __name__ == '__main__':
    main()
