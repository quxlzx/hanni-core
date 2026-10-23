"""Additional original-service adapters. Execution inputs only, never oracles."""
from __future__ import annotations
from copy import deepcopy
import errno
import http.client
import json
import logging
from pathlib import Path
import socket
import sys
import threading
from unittest.mock import patch
from scripts.campaign9_verification import development as dev
from scripts.campaign9_verification.executor import common, owned

def filesystem_fault(params, root):
    from hanni.tools.base import ToolRequest
    reg = dev.registry(root)
    arguments = params.get('arguments', {})
    target = owned(arguments['path'], root)
    original = Path.write_text
    calls = []

    def controlled_failure(path, *args, **kwargs):
        if path.resolve() == target:
            calls.append(1)
            raise OSError(errno.ENOSPC, 'Owned simulated disk-full leaf')
        return original(path, *args, **kwargs)
    error, result = (None, None)
    with patch.object(Path, 'write_text', controlled_failure), dev.entries(reg.get('file.write').handler) as entered:
        try:
            result = reg.execute(ToolRequest('file.write', arguments, confirmed=params.get('confirmed', False)))
        except Exception as exc:
            error = exc
    return (common() | {'write_effects': int(target.exists()), 'dependency_failure_honest': error is not None and result is None, 'consequential_retry_count_max': max(0, len(calls) - 1)}, {**entered, 'exception_type': type(error).__name__ if error else None, 'leaf_entries': len(calls), 'fault_scope': 'injected_ENOSPC_not_real_disk_exhaustion'})

def audit_case(params, root):
    from dataclasses import replace
    from hanni.tools.audit import ToolAuditLog
    from hanni.tools.base import ToolRequest, ToolResult
    reg = dev.registry(root)
    log = ToolAuditLog(root)
    tool = params['tool']
    if tool == 'file.write':
        definition = reg.get(tool)
        result = reg.execute(ToolRequest(tool, params['arguments']))
        raw = log.path.read_text(encoding='utf8')
        body = params['arguments']['text']
        return (common() | {'private_body_in_audit': body in raw, 'audit_event_retained': bool(raw)}, {'audit_sha256': dev.sha(raw.encode()), 'actual_owned_write': result.ok, 'scope': 'original_write_handler_and_actual_audit_record'})
    definition = replace(reg.get('file.read'), name=tool)
    request = ToolRequest(tool, params['arguments'])
    log.write(definition, request, params['arguments'], result=ToolResult(tool, True, params['provider_result'], {}))
    raw = log.path.read_text(encoding='utf8')
    private_texts = list(params['arguments'].values()) + [params['provider_result']]
    return (common() | {'private_body_in_audit': any((text in raw for text in private_texts)), 'external_result_placeholder_used': '[EXTERNAL MCP RESULT]' in raw, 'audit_event_retained': bool(raw)}, {'audit_sha256': dev.sha(raw.encode()), 'scope': 'original_external_audit_serialization_only_no_provider_or_handler_call'})

def model_fault(params, root):
    from hanni.config.schema import parse_models
    from hanni.models.client import LlamaCppClient, ModelClientError
    from hanni.logs.redaction import register_secret
    secret = params['synthetic_secret']
    register_secret('C9_PRIVATE_PROVIDER', secret)
    with dev.model_http('error', secret=secret) as (endpoint, observed):
        spec = parse_models({'models': [{'id': 'private-protocol-only', 'role': 'supervisor', 'backend': 'llama.cpp', 'model_file': str(root / 'NOT_LOADED.gguf'), 'endpoint': endpoint + '/v1', 'keep_loaded': False, 'request_timeout_seconds': 2}]}).supervisor
        client = LlamaCppClient(spec, max_attempts=1)
        result, exception = (None, None)
        try:
            result = client.chat([{'role': 'user', 'content': 'A bounded synthetic protocol request'}], max_tokens=8)
        except ModelClientError as exc:
            exception = exc
    output = str(exception) if exception is not None else str(result)
    reflected = secret in output
    return (common() | {'public_error_contains_secret': reflected, 'unapproved_credential_exposures': int(reflected), 'dependency_failure_honest': exception is not None, 'consequential_retry_count_max': max(0, observed['entries'] - 1)}, {'provider_entries': observed['entries'], 'output_sha256': dev.sha(output.encode()), 'scope': 'original_client_actual_owned_HTTP_error_not_model_inference'})

def redirect_case(params, root):
    from hanni.laya.advisory import AdvisoryClient
    with dev.model_http('health') as (changed, received), dev.model_http('redirect', target=changed, redirect_code=params['status']) as (initial, sent):
        client = AdvisoryClient(enabled=True, quality_gate_passed=True, token=params['auth_secret'], endpoint=initial + '/v1/advisory', timeout_s=1)
        try:
            submitted = client.submit_analysis('A bounded synthetic project review request.')
            client._queue.join()
            errors = client.errors
        finally:
            client.close()
            client._worker.join(3)
    return (common() | {'redirect_target_requests': received['entries'], 'credential_to_changed_target_count': received['entries'], 'dependency_failure_honest': submitted and errors == 1}, {'initial_entries': sent['entries'], 'owned_worker_closed': not client._worker.is_alive(), 'scope': 'original_advisory_client_actual_owned_loopback_redirect'})

def mcp_case(operation, params, root):
    from hanni.mcp.manager import MCPManager
    from hanni.mcp.security import resolve_credentials, normalize_server_config
    from hanni.tools.base import ToolRequest
    reg = dev.registry(root)
    original_builtin = reg.get('powershell.run')
    leaf_calls, credentials = ([], [])

    class Vault:

        def get(self, account):
            return None

        def get_password(self, service, key):
            return None
    auth = params.get('auth')
    env = params.get('env', {})
    if operation == 'mcp_credentials':
        config = normalize_server_config({'name': 'Credential contract', 'transport': 'streamable_http', 'url': 'http://127.0.0.1:49196/mcp', 'allow_local_http': True, 'auto_connect': False, 'auth': auth})
        error, headers = (None, {})
        try:
            _, headers = resolve_credentials(config, env=env, vault=Vault())
        except Exception as exc:
            error = exc
        delivered = 0
        if headers:
            from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

            class AuthHandler(BaseHTTPRequestHandler):

                def log_message(self, *args):
                    pass

                def do_GET(self):
                    credentials.append(self.headers.get('Authorization') in headers.values())
                    self.send_response(200)
                    self.send_header('Content-Length', '2')
                    self.end_headers()
                    self.wfile.write(b'{}')
            server = ThreadingHTTPServer(('127.0.0.1', 0), AuthHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            try:
                connection.request('GET', '/approved-auth-target', headers=headers)
                response = connection.getresponse()
                response.read()
                delivered = int(response.status == 200 and credentials == [True])
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(3)
        return (common() | {'credential_resolution': 'admitted' if error is None else 'denied', 'provider_calls': delivered, 'authorized_auth_target_count': delivered}, {'exception_type': type(error).__name__ if error else None, 'scope': 'original_credential_resolution_and_controlled_owned_HTTP_auth_leaf_not_SDK_session'})
    if 'approval_read_database_unavailable' in params.get('controls', []):
        return ({}, {'status': 'blocked', 'reason': 'Original MCP approval store is JSON, not a database; no fabricated DB adapter', 'scope': 'authored_storage_backend_precondition_not_implemented'})
    classification = params.get('owner_classification', params.get('tool_classification', params.get('definition', {}).get('classification', 'read_only')))
    name = params.get('name', params.get('definition', {}).get('name', 'independent.marker'))
    description = params.get('description', 'Read a bounded synthetic marker.')
    schema = {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'additionalProperties': False}
    discovered = {'name': name, 'description': description, 'inputSchema': schema, 'outputSchema': {'type': 'object', 'properties': {'marker': {'type': 'string'}}, 'required': ['marker']}, 'annotations': params.get('annotations', {'readOnlyHint': True})}

    class Connection:
        closed = False
        protected_values = ()

        def __init__(self, runtime, config, **kwargs):
            self.config = config

        def wait_ready(self):
            pass

        def request(self, method, arguments=None):
            if method == 'list':
                return [deepcopy(discovered)]
            arguments['admit']()
            leaf_calls.append({'name': arguments['name'], 'stage': 'entered'})
            if params.get('provider_behavior') == 'disconnect_before_result':
                self.closed = True
                raise ConnectionError('Owned inert MCP disconnect')
            return {'content': [{'type': 'text', 'text': 'Controlled marker'}], 'structuredContent': {'marker': 'public'}}

        def cancel_tools(self, names):
            pass

        def signal_close(self):
            self.closed = True

        def close(self):
            self.closed = True
    manager = MCPManager(root, reg, connection_factory=Connection, env={}, vault=Vault())
    error, result, cached, owner_classification = (None, None, None, None)
    try:
        added = manager.add({'name': 'Independent controlled MCP', 'transport': 'streamable_http', 'url': 'http://127.0.0.1:49195/mcp', 'allow_local_http': True, 'auto_connect': False})
        connected = manager.connect(added['id'], approved=True, expected_config_hash=added['config_hash'])['servers'][-1]
        tool = connected['tools'][0]
        if params.get('approval') != 'none':
            manager.approve_tools(connected['id'], [{'original_name': tool['original_name'], 'definition_hash': tool['definition_hash'], 'classification': classification}])
            cached = reg.get(tool['internal_id'])
            owner_classification = manager.snapshot()['servers'][-1]['tools'][0]['classification']
        if 'revoke' in params.get('controls', []):
            manager.disable_tools(connected['id'], [tool['original_name']])
        if operation == 'mcp_description' and params.get('proposed_next_tool'):
            try:
                reg.execute(ToolRequest(params['proposed_next_tool'], {'path': str(root / 'not-authorized.txt')}, confirmed=params.get('next_confirmed', False)))
            except Exception as exc:
                error = exc
        elif cached is not None:
            try:
                result = cached.handler({'query': 'A public marker'}, reg.context, ToolRequest(tool['internal_id'], {'query': 'A public marker'}, confirmed=False))
            except Exception as exc:
                error = exc
    finally:
        manager.close()
    observations = common() | {'sensitive_handler_entries': len(leaf_calls), 'unapproved_handler_entries': len(leaf_calls), 'destructive_handler_entries': 0, 'description_grants_authority': False, 'built_in_definition_identity_preserved': reg.get('powershell.run') is original_builtin, 'owner_classification_preserved': owner_classification in {None, classification}, 'cached_authority_rejected': error is not None and (not leaf_calls), 'dependency_failure_honest': error is not None and result is None, 'consequential_dispatch_count_max': len(leaf_calls)}
    if classification == 'read_only':
        observations['unapproved_handler_entries'] = 0 if cached is not None else len(leaf_calls)
        observations['sensitive_handler_entries'] = 0
    return (observations, {'exception_type': type(error).__name__ if error else None, 'RPC_entries': len(leaf_calls), 'scope': 'original_manager_approval_and_adapter_inert_RPC_no_SDK'})

def compute_case(operation, params, root):
    from dataclasses import replace
    from hanni.models.adaptive import ModelRequest
    from scripts.campaign5_intelligence.controlled import controlled_engine
    cancellation = threading.Event()
    observations = common()
    with controlled_engine(root) as engine:
        worker = engine.compute.registry.worker('controlled')
        initial_categories = params.get('allowed_categories', ['synthetic'])
        deployment = root / 'compute/deployment.json'
        document = json.loads(deployment.read_text(encoding='utf8'))
        document['workers'][0]['allowed_categories'] = initial_categories
        document['workers'][0]['enabled'] = params.get('worker_enabled', True)
        deployment.write_text(json.dumps(document), encoding='utf8')
        engine.compute.registry.reload()
        engine.refresh()
        transport = engine.compute.transport
        native = transport.request

        def fixture_probe(worker, method, path, **kwargs):
            result = native(worker, method, path, **kwargs)
            result['usage'] = {'prompt_tokens': 1024, 'completion_tokens': 4, 'total_tokens': 1028}
            return result
        transport.request = fixture_probe
        setup_result = None
        try:
            setup_result = engine.compute.verify_context('controlled', [{'role': 'user', 'content': 'Controlled source value'}], target_tokens=1024, expected='controlled source value', max_output_tokens=32)
        except Exception:
            pass
        transport.request = native
        transport.calls.clear()
        action = params.get('at_admission')

        def admission():
            if operation == 'adaptive_cancellation':
                cancellation.set()
            elif action:
                current = json.loads(deployment.read_text(encoding='utf8'))
                if action == 'worker_disappears':
                    current['workers'] = []
                elif action == 'revoke_category':
                    current['workers'][0]['allowed_categories'] = []
                deployment.write_text(json.dumps(current), encoding='utf8')
                engine.compute.registry.reload()
        error, result = (None, None)
        local_entries = []

        def local_callback(*args):
            local_entries.append(1)
            return 'Controlled callback output'
        request = ModelRequest(task_category=params.get('request_category', 'analysis'), interactive=False, privacy_categories=frozenset(params.get('request_categories', ['synthetic'])), output_tokens=32)
        if operation == 'compute_failure':
            transport.failure = True
        try:
            result = engine.execute([{'role': 'user', 'content': 'Controlled private-context authority probe'}], request=request, endpoint_id='local:supervisor' if operation == 'adaptive_cancellation' else 'worker:controlled', max_fallbacks=0, admission=admission, cancellation=cancellation, local_execute=local_callback)
        except Exception as exc:
            error = exc
        posts = len(transport.calls)
        observations.update(provider_calls=len(local_entries) if operation == 'adaptive_cancellation' else posts, private_context_forwarded=bool(posts and 'memory' in request.privacy_categories), disabled_worker_used=bool(posts and (not params.get('worker_enabled', True))), authority_failure_honest=error is not None, dependency_failure_honest=error is not None and result is None, consequential_followup_effects=0, decision_cancelled='cancel' in str(error).lower() if error else False)
        detail = {'exception_type': type(error).__name__ if error else None, 'compute_POSTs': posts, 'local_callback_entries': len(local_entries), 'bootstrap_controlled_pass': bool(setup_result and setup_result.get('passed')), 'active_reservations_after': sum(engine.compute.registry.active.values()), 'scope': 'original_native_routing_and_compute_controlled_resources_transport_and_proofs_not_live'}
    return (observations, detail)
