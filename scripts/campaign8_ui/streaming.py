"""Bounded original controller on fresh stores, reusing the existing model only.

This helper does not launch a desktop or model. The coordinator must reserve the
exclusive native slot. Physical audio, remote tools, startup and owner history
remain excluded. A failed admission is retained without sending generation.
"""
from __future__ import annotations
from contextlib import ExitStack, contextmanager
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import socket
import threading
import time
from unittest.mock import patch
from urllib.parse import urlsplit
import urllib.request
import psutil
from .backend import REPO, original_backend, source_hashes
PROMPT = 'Explain in two short sentences how a bicycle gear changes pedaling effort.'
MODEL_PID = 38832
MODEL_CREATE_TIME = 1791595415.4806464
MODEL_COMMAND_SHA256 = 'eca1546bb86f6d07e2583465948461738a5bd60f171262bfc863470a19916dbd'
MODEL_BASENAME = 'Qwen3.5-4B-Q4_K_M.gguf'
MODEL_ORIGIN = ('http', '127.0.0.1', 8080)
MAX_GENERATIONS = 1

class StreamingAdmissionError(RuntimeError):
    pass

def resource_gate(sample):
    """Additional campaign reserve; original model admission is not replaced."""
    if type(sample.get('available_ram_bytes')) is not int or sample['available_ram_bytes'] < 3072 * 1024 ** 2:
        raise StreamingAdmissionError('Available RAM is below the campaign/original configuration 3072 MiB reserve.')
    percent = sample.get('used_percent')
    if type(percent) not in (int, float) or not 0 <= percent < 90:
        raise StreamingAdmissionError('RAM pressure is unknown or at the configured critical 90 percent threshold.')

def _metadata(path, *, opener=urllib.request.urlopen):
    request = urllib.request.Request('http://127.0.0.1:8080' + path, headers={'Accept': 'application/json'}, method='GET')
    with opener(request, timeout=3) as response:
        raw = response.read(262145)
    if len(raw) > 262144:
        raise StreamingAdmissionError('Model metadata exceeded the bounded read.')
    return json.loads(raw)

def _process_identity():
    process = psutil.Process(MODEL_PID)
    if not process.is_running() or process.name().casefold() != 'llama-server.exe':
        raise StreamingAdmissionError('The recorded existing model PID is no longer the original llama-server.')
    command = process.cmdline()
    command_hash = hashlib.sha256('\x00'.join(command).encode('utf8')).hexdigest()
    if process.create_time() != MODEL_CREATE_TIME or command_hash != MODEL_COMMAND_SHA256:
        raise StreamingAdmissionError('Existing model create-time/command identity differs from the original manager preflight.')
    model = None
    for key in ('--model', '-m'):
        if key in command and command.index(key) + 1 < len(command):
            model = command[command.index(key) + 1]
            break
    listeners = [connection for connection in process.net_connections(kind='tcp') if connection.status == psutil.CONN_LISTEN and connection.laddr.port == 8080 and (connection.laddr.ip in {'127.0.0.1', '::1'})]
    if not listeners:
        raise StreamingAdmissionError('Existing model PID no longer owns the allowed loopback endpoint.')
    identity_source = 'explicit_process_model_flag'
    if model is None:
        model = _metadata('/props').get('model_path')
        identity_source = 'fresh_exact_file_props_on_pid_owned_socket'
    if not isinstance(model, str) or model.replace('\\', '/').rsplit('/', 1)[-1] != MODEL_BASENAME:
        raise StreamingAdmissionError('Existing model process has a different configured model file.')
    return {'pid': process.pid, 'create_time': process.create_time(), 'name': process.name(), 'model_path': model, 'endpoint': 'http://127.0.0.1:8080/v1', 'identity_source': identity_source, 'command_sha256': command_hash}

def original_model_admission(expected_process=None, *, opener=urllib.request.urlopen):
    memory = psutil.virtual_memory()
    sample = {'at': time.time(), 'available_ram_bytes': memory.available, 'used_percent': memory.percent}
    resource_gate(sample)
    process = _process_identity()
    if expected_process is not None and process != expected_process:
        raise StreamingAdmissionError('Existing model process identity changed during the owned session.')
    health = _metadata('/health', opener=opener)
    props = _metadata('/props', opener=opener)
    slots = _metadata('/slots', opener=opener)
    if health.get('status') != 'ok':
        raise StreamingAdmissionError('Existing model is not healthy.')
    loaded = props.get('model_path')
    if loaded != process['model_path'] or props.get('model_alias') != 'supervisor':
        raise StreamingAdmissionError('Actual model props do not bind the existing PID/file and original supervisor alias.')
    if not isinstance(slots, list) or not slots or any((not isinstance(slot, dict) or slot.get('is_processing') is not False for slot in slots)):
        raise StreamingAdmissionError('Original endpoint slot availability cannot confirm idle inference.')
    return {'resource': sample, 'process': process, 'health': health, 'props': {'model_path': loaded, 'model_alias': props.get('model_alias'), 'total_slots': props.get('total_slots'), 'modalities': props.get('modalities')}, 'slots': [{'id': slot.get('id'), 'is_processing': slot.get('is_processing')} for slot in slots]}

def streaming_config(root):
    from hanni.config.loader import load_config
    base = load_config(REPO / 'config', data_dir=root, env={})
    supervisor = base.models.supervisor
    if supervisor.endpoint != 'http://127.0.0.1:8080/v1' or supervisor.model_file != MODEL_BASENAME:
        raise StreamingAdmissionError('Original configured supervisor changed; this sealed bounded probe does not adapt silently.')
    spec = replace(supervisor, request_timeout_seconds=30, max_tokens=64, temperature=0, health_timeout_seconds=3)
    return replace(base, models=replace(base.models, models=(spec,)))

def _publish(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf8', newline='\n')
    temporary.replace(path)

@contextmanager
def streaming_backend(root):
    """Attach the original text/MCP/memory/controller chain in this process only."""
    admission = original_model_admission()
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {'HANNI_LAYA_SHADOW_ENABLED': '0'}))
        stack.enter_context(patch('scripts.campaign8_ui.backend.fixture_config', streaming_config))
        with original_backend(root) as backend:
            original_connect = socket.socket.connect
            raw_connect = None
            for cell in getattr(original_connect, '__closure__', ()) or ():
                value = cell.cell_contents
                if getattr(value, '__name__', '') == 'connect':
                    raw_connect = value
            if raw_connect is None:
                raise StreamingAdmissionError('Owned fixture socket boundary cannot be identified safely.')

            def existing_endpoint_only(sock, address):
                if isinstance(address, tuple) and address[:2] == ('127.0.0.1', 8080):
                    return raw_connect(sock, address)
                return original_connect(sock, address)
            stack.enter_context(patch.object(socket.socket, 'connect', existing_endpoint_only))
            from scripts.campaign5_benchmark.runner import capture_http
            from hanni.models.client import ModelUnavailableError, LlamaCppClient
            from hanni.models.manager import ModelManager, install as install_manager
            from hanni.core.orchestrator import TextSession, system_prompt_for
            from hanni.dashboard.chat import ChatSession
            from hanni.cli import _wrap_mcp_session, _wrap_memory_session, _close_interactive_session
            from hanni.core.interaction import interaction
            native_urlopen = urllib.request.urlopen
            admissions, requests, snapshots = ([], [], [])
            budget_lock = threading.Lock()

            def guarded_urlopen(request, *args, **kwargs):
                parsed = urlsplit(getattr(request, 'full_url', str(request)))
                method = getattr(request, 'method', None) or ('POST' if getattr(request, 'data', None) is not None else 'GET')
                if (parsed.scheme, parsed.hostname, parsed.port) == MODEL_ORIGIN and method == 'POST':
                    if parsed.path != '/v1/chat/completions':
                        raise StreamingAdmissionError('Only the original bounded completion route is authorized.')
                    payload = json.loads(request.data)
                    last_user = next((message.get('content') for message in reversed(payload.get('messages', ())) if message.get('role') == 'user'), None)
                    if last_user != PROMPT or payload.get('max_tokens') != 64 or payload.get('temperature') != 0:
                        raise StreamingAdmissionError('Only the prospectively fixed synthetic prompt and limits are authorized.')
                    with budget_lock:
                        if len(requests) >= MAX_GENERATIONS:
                            raise StreamingAdmissionError('Bounded generation budget exhausted; no replay is authorized.')
                        check = original_model_admission(admission['process'], opener=native_urlopen)
                        admissions.append(check)
                        requests.append({'at': time.time(), 'path': parsed.path, 'prompt_sha256': hashlib.sha256(PROMPT.encode()).hexdigest(), 'max_tokens': 64, 'temperature': 0})
                    kwargs['timeout'] = min(kwargs.get('timeout', 30), 30)
                return native_urlopen(request, *args, **kwargs)
            stack.enter_context(patch.object(urllib.request, 'urlopen', guarded_urlopen))
            wire = stack.enter_context(capture_http({MODEL_ORIGIN}))

            def forbidden_launch(*args, **kwargs):
                raise ModelUnavailableError('Only the already running endpoint may be reused; no process startup is authorized.')
            manager = ModelManager(backend.config, launch=forbidden_launch, stop=forbidden_launch)
            install_manager(manager)
            base = TextSession(LlamaCppClient(backend.config.models.supervisor, max_attempts=1), system_prompt=system_prompt_for(backend.config.hanni.personality))
            session = _wrap_mcp_session(backend.config, base, client=base.client, registry=backend.registry)
            from hanni.models.adaptive import current as current_routing
            engine = current_routing(backend.config)
            deadline = time.monotonic() + 40
            healthy = False
            while engine is not None and time.monotonic() < deadline:
                with engine.lock:
                    healthy = any((row.get('status') == 'healthy' for row in engine.observations.values()))
                if healthy:
                    break
                time.sleep(0.05)
            if engine is None or not healthy:
                manager.close()
                install_manager(None)
                raise StreamingAdmissionError('Original adaptive monitor did not establish fresh genuine local identity/health within the owned deadline.')
            session = _wrap_memory_session(backend.config, session, source='campaign8-isolated-chat', registry=backend.registry, emergency_stop=backend.registry.context.emergency_stop)
            chat_session = ChatSession(session, backend.chat, 'browser')
            halt = threading.Event()
            errors = []

            def consume_original_inbox():
                while not halt.wait(0.02) and (not backend.stop.is_set()):
                    prompt = backend.chat.take()
                    if prompt is None:
                        continue
                    try:
                        if prompt != PROMPT:
                            raise StreamingAdmissionError('Native input differs from the sole authorized synthetic prompt.')
                        with interaction.foreground():
                            interaction.responding(True)
                            try:
                                for _ in chat_session.stream_response(prompt, max_tokens=64, temperature=0, top_p=1):
                                    snapshot = backend.chat.snapshot()
                                    snapshot.pop('token', None)
                                    snapshots.append({'at': time.time(), 'snapshot': snapshot})
                                    if halt.is_set():
                                        break
                            finally:
                                interaction.responding(False)
                    except Exception as error:
                        errors.append({'type': type(error).__name__, 'message': str(error)[:800]})
                    _publish(backend.root / 'STREAM.json', {'admissions': admissions, 'requests': requests, 'snapshots': snapshots, 'errors': errors, 'scope': 'Actual original ChatSession persistence over real bounded local model output; semantic correctness ungraded.'})
            controller = threading.Thread(target=consume_original_inbox, name='campaign8-original-text-inbox', daemon=True)
            backend.chat.activate()
            controller.start()
            ready = backend.ready()
            ready.update(chat_controller_attached=True, model_generation='ADMITTED_ONLY_AFTER_REQUEST_TIME_CHECK', scope='CONTROLLED original isolated backend/stores/controller with genuine existing local model generation; no speech/remote execution.', streaming={'prompt': PROMPT, 'max_tokens': 64, 'max_generation_requests': MAX_GENERATIONS, 'request_timeout_seconds': 30, 'initial_admission': admission, 'quality_scoring': 'NOT_PERFORMED'})
            try:
                yield (backend, ready)
            finally:
                halt.set()
                controller.join(35)
                if controller.is_alive():
                    errors.append({'type': 'ControllerJoinTimeout', 'message': 'Owned controller did not close within the HTTP deadline.'})
                _close_interactive_session(session, registry=backend.registry)
                manager.close()
                install_manager(None)
                _publish(backend.root / 'STREAM_CLOSED.json', {'controller_closed': not controller.is_alive(), 'requests': requests, 'admissions': admissions, 'errors': errors, 'actual_wire': [{k: bytes(value).decode('utf8', errors='replace') if isinstance(value, bytearray) else value for k, value in row.items() if k != '_raw'} | ({'raw_response': bytes(row['_raw']).decode('utf8', errors='replace')} if '_raw' in row else {}) for row in wire], 'source_before': backend.before, 'source_after': source_hashes(), 'owner_model_process_after': _process_identity(), 'owner_model_stopped': False, 'owner_history_modified': False, 'no_new_model_process': True})

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 360:
        raise ValueError('Use an owned-session deadline of at most 360 seconds.')
    if args.root.exists():
        raise ValueError('Choose a fresh isolated session directory.')
    try:
        with streaming_backend(args.root) as (backend, ready):
            _publish(backend.root / 'READY.json', ready)
            print(json.dumps(ready), flush=True)
            backend.stop.wait(args.timeout)
    except Exception as error:
        args.root.mkdir(parents=True, exist_ok=True)
        _publish(args.root / 'BLOCKED.json', {'outcome': 'BLOCKED_OR_FAILED', 'type': type(error).__name__, 'message': str(error)[:800], 'inference_claimed': False})
        raise
if __name__ == '__main__':
    main()
