"""Bounded original local model/controller/lab server; no whole HANNI startup.

Existing weights and exact production model configuration are required. All
ownership/configuration receipts are private. The stop marker requires this
session's nonce. Owned inference uses the original ModelManager/Popen cleanup;
explicitly reviewed external inference stays unowned and is preserved.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import socket
import sys
import threading
import time
import shutil
from types import SimpleNamespace
from uuid import uuid4

import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.config.loader import load_config
from hanni.compute import ComputeRegistry
from hanni.compute.transport import InferenceTransport
from hanni.dashboard.chat import ChatHub
from hanni.dashboard.server import DashboardServer
from hanni.models.manager import ModelManager, install as install_manager
from hanni.models.resource_manager import snapshot_resources
from hanni.reliability.execution import close_service


class EmptyVault:
    def labels(self): return ('personal', 'school')
    def get(self, account): return None
    def preferences(self): return {}


def save(path, value):
    pending = path.with_suffix('.tmp')
    pending.write_text(json.dumps(value, indent=2, default=str), encoding='utf8')
    pending.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=3600)
    parser.add_argument('--preserve-existing-primary', action='store_true')
    parser.add_argument('--state-from', type=Path)
    parser.add_argument('--conversation-controller', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    weights = args.weights.resolve()
    assert output.is_relative_to((ROOT / 'data/v44-verification').resolve()) and not output.exists()
    assert 60 <= args.seconds <= 7200
    state_directory = output / 'state'
    if args.state_from:
        previous = args.state_from.resolve()
        assert previous.is_relative_to((ROOT / 'data/v44-verification').resolve())
        prior_closed = json.loads((previous / 'closed.json').read_text(encoding='utf8'))
        assert prior_closed['closed_verified'] and prior_closed['external_original_preserved']
        assert args.preserve_existing_primary
        prior_owner = json.loads((previous / 'ownership.json').read_text(encoding='utf8'))
        state_directory = Path(prior_owner['state_directory']).resolve()
        assert state_directory.is_relative_to((ROOT / 'data/v44-verification').resolve())
        assert state_directory.is_dir()
    config = load_config(ROOT / 'config', data_dir=state_directory, env={})
    spec = config.models.supervisor
    assert weights.is_file() and weights.name == spec.model_file
    assert (spec.context_length, spec.parallel, spec.kv_key_type, spec.kv_value_type) == (16384, 1, 'q8_0', 'q8_0')
    base = __import__('urllib.parse', fromlist=['urlsplit']).urlsplit(spec.endpoint)
    with socket.socket() as probe:
        probe.settimeout(1)
        result = probe.connect_ex((base.hostname, base.port))
    external = result == 0
    assert result in (10061, 111) or (external and args.preserve_existing_primary), 'The original model endpoint is occupied or its ownership is unknown.'
    output.mkdir(parents=True)
    # Reuse the configured registry in a private state copy. Secrets never leave
    # ignored storage; no deployment permissions or remote helpers are changed.
    state_directory.mkdir(parents=True, exist_ok=True)
    original_deployment = ROOT / 'data/compute/deployment.json'
    if original_deployment.is_file() and not args.state_from:
        (state_directory / 'compute').mkdir(exist_ok=True)
        shutil.copyfile(original_deployment, state_directory / 'compute/deployment.json')
    with weights.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert digest == '25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c'
    nonce = uuid4().hex
    stop = threading.Event()
    manager = ModelManager(config, model_files={spec.id: str(weights)}, startup_timeout=180, shutdown_event=stop)
    install_manager(manager)
    process = None
    inference = None
    server = None
    hub = None
    thread = None
    evidence = {'session_nonce': nonce, 'helper_pid': __import__('os').getpid(),
                'helper_create_time': psutil.Process().create_time(), 'weights_sha256': digest,
                'weights_bytes': weights.stat().st_size, 'no_download': True,
                'model_configuration': asdict(spec), 'started_at': time.time(),
                'maximum_runtime_seconds': args.seconds, 'full_hanni_started': False}
    evidence['state_directory'] = str(state_directory)
    try:
        if external:
            listeners = {item.pid for item in psutil.net_connections(kind='tcp')
                         if item.status == psutil.CONN_LISTEN and item.laddr.port == base.port}
            assert listeners == {38832}, 'Fresh external listener differs from reviewed original primary.'
            inference = psutil.Process(38832)
            assert inference.create_time() == 1791595415.4806464
            parent = inference.parent()
            assert parent.pid == 46084 and parent.create_time() == 1791595411.2839503
            assert 'hanni.dashboard.launcher' in parent.cmdline()
            actual_command = inference.cmdline()
            expected_flags = {'--alias': spec.api_model, '--host': '127.0.0.1', '--port': str(base.port),
                              '-c': str(spec.context_length), '--parallel': '1', '-ngl': '99',
                              '--device': 'Vulkan1', '--split-mode': 'none', '--main-gpu': '0',
                              '--flash-attn': 'on', '-ctk': 'q8_0', '-ctv': 'q8_0',
                              '--reasoning': 'off', '--load-mode': 'mmap'}
            assert all(actual_command.count(flag) == 1 and actual_command[actual_command.index(flag)+1] == value
                       for flag, value in expected_flags.items()), 'External critical configuration differs.'
            assert actual_command[actual_command.index('-hf')+1] == f'{spec.hf_repo}:{spec.quantization}'
            registry = ComputeRegistry(output / 'state')
            transport = InferenceTransport(registry)
            worker = {'worker_id': 'local:supervisor', 'node_id': 'local', 'protocol': 'llamacpp_openai',
                      'local_url': f'http://{base.hostname}:{base.port}', 'model_id': spec.api_model}
            try:
                health = transport.health(worker)
                props = transport.request(worker, 'GET', '/props')
            finally:
                transport.close()
                registry.close()
            assert health['status'] == 'healthy' and health['model_id'] == spec.api_model
            assert health['context_reported'] == spec.context_length
            assert Path(props['model_path']).resolve() == weights, 'Reported loaded weights differ from exact cached weights.'
            evidence.update(external_parent_pid=parent.pid, external_parent_create_time=parent.create_time(),
                            fresh_original_health=health, critical_configuration_verified=expected_flags,
                            reported_weights_sha256=digest,
                            performance_limitations='Shared original external primary; interactive contention and warm-cache state uncontrolled. No competitive performance or optimization claims.')
        began = time.perf_counter()
        entry = manager.ensure_loaded(spec.id)
        process = entry.process
        assert (process is None) == external, 'External primary must remain unowned in original manager.'
        if not external:
            assert entry.command[entry.command.index('--device') + 1] == 'Vulkan1'
            inference = psutil.Process(process.pid)
            actual_command = inference.cmdline()
        manager._capture_resources()
        binary = Path(actual_command[0]).resolve()
        assert binary.is_file()
        with binary.open('rb') as stream:
            binary_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        evidence.update(inference_pid=inference.pid, inference_create_time=inference.create_time(),
                        inference_owned=not external,
                        command_sha256=hashlib.sha256(json.dumps(actual_command).encode()).hexdigest(),
                        actual_command=actual_command,
                        load_time_ms=None if external else (time.perf_counter() - began) * 1000,
                        external_recognition_ms=(time.perf_counter() - began) * 1000 if external else None,
                        backend_executable_sha256=binary_digest,
                        owned_snapshot=manager.snapshot())
        save(output / 'ownership.json', evidence)
        hub = ChatHub()
        hub.ready = False  # The workflow-only validation helper has no chat/voice consumer.
        resource_cache = {'sampled_at': 0, 'resources': None}
        resource_lock = threading.Lock()
        def telemetry():
            with resource_lock:
                if time.time() - resource_cache['sampled_at'] >= 5:
                    resource_cache['resources'] = snapshot_resources().to_dict()
                    resource_cache['sampled_at'] = time.time()
                actual_resources = resource_cache['resources']
                sampled_at = resource_cache['sampled_at']
            return {'sampled_at': sampled_at, 'model_status': 'ready', 'error': None,
                    'resources': actual_resources, 'safe_mode': False,
                    'model_residency': manager.snapshot(),
                    'activity': {'input_level': 0, 'speaking': False, 'microphone_active': False},
                    'interaction': {'response_in_progress': False, 'tts_speaking': False, 'voice_engaged': False},
                    'model': {'file': spec.model_file, 'quantization': spec.quantization, 'context': spec.context_length}}
        from hanni.dashboard.cluster import ClusterMonitor
        configured_cluster = ClusterMonitor(data_dir=ROOT / 'data')
        # The real roster and original unknown/repair states are retained. No
        # sampling thread is started; native review discloses passive monitoring.
        cluster = SimpleNamespace(start=lambda: None, close=configured_cluster.close,
                                  snapshot=configured_cluster.snapshot)
        from hanni.dashboard.cluster_power import ClusterPower
        from hanni.dashboard.cluster_terminal import ClusterTerminal
        power = ClusterPower(cluster, ROOT / 'data')
        terminal = ClusterTerminal(cluster, ROOT / 'data')
        server = DashboardServer(0, SimpleNamespace(config=config, snapshot=telemetry), hub,
                                 shutdown_event=stop, cluster=cluster, cluster_power=power, cluster_terminal=terminal)
        server.features.registry.google_access._vault = EmptyVault()
        server.mcp.attach_controller(server.features.registry, model_tools_enabled=True, observe_first=True)
        server.model_routing.controller_attached = True
        server.model_routing.refresh()
        from hanni.models.client import LlamaCppClient
        from hanni.mcp.host import McpHost
        original_host = McpHost(server.features.registry,
            read_only=config.hanni.mcp.read_only,
            max_tools=config.hanni.mcp.max_tools_per_turn,
            allowed_actions=config.hanni.mcp.allowed_actions)
        server.workflows.attach_controller(server.features.registry,
            server.model_routing.wrap_client(LlamaCppClient(spec)), original_host)
        conversational_session = None
        conversation_count = 0
        if args.conversation_controller:
            from hanni.core.orchestrator import TextSession
            from hanni.mcp.session import McpToolSession
            from hanni.memory import MemoryAwareSession, MemoryStore
            from hanni.dashboard.chat import ChatSession
            conversational_client = server.model_routing.wrap_client(LlamaCppClient(spec))
            memory_store = MemoryStore(config.paths.data_dir / config.hanni.memory.database_file,
                                       max_item_chars=config.hanni.memory.max_item_chars)
            conversational_session = ChatSession(MemoryAwareSession(
                McpToolSession(TextSession(conversational_client), conversational_client, original_host),
                memory_store, source='v44-private-native-validation', registry=server.features.registry),
                hub, 'browser')
            hub.ready = True
        assert hasattr(server, 'model_lab'), 'The production Model Lab service has not been integrated.'
        thread = threading.Thread(target=server.serve_forever, name='v44-owned-validation-server', daemon=True)
        thread.start()
        ready = {'url': f'http://127.0.0.1:{server.server_port}', 'ready_at': time.time(),
                 'helper_pid': evidence['helper_pid'], 'helper_create_time': evidence['helper_create_time'],
                 'session_nonce': nonce, 'controller_registry': 'original DesktopFeatures ToolRegistry',
                 'scope': 'Original bounded current-source controller, workflow runner and ModelLab; primary inference ' + ('shared external and preserved' if external else 'owned') + '. Cluster roster passive with unknown/repair metrics; original remote registry private copy; empty Google vault; no voice/interactive assistant.'}
        save(output / 'ready.json', ready)
        print(json.dumps({'state': 'ready', 'url': ready['url'], 'inference_pid': inference.pid,
                          'inference_owned': not external, 'load_time_ms': evidence['load_time_ms']}), flush=True)
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline and inference.is_running() and inference.create_time() == evidence['inference_create_time']:
            marker = output / 'stop.json'
            if marker.is_file():
                payload = json.loads(marker.read_text(encoding='utf-8-sig'))
                assert payload == {'session_nonce': nonce}, 'Stop marker ownership does not match.'
                break
            if conversational_session is not None:
                prompt = hub.take()
                if prompt is not None:
                    assert conversation_count < 4, 'Private validation conversation budget exhausted.'
                    conversation_count += 1
                    try:
                        answer = ''.join(conversational_session.stream_response(prompt))
                        save(output / f'conversation-{conversation_count}.json', {
                            'prompt': prompt, 'answer': answer, 'finished_at': time.time(),
                            'original_layers': ['ChatSession', 'MemoryAwareSession', 'McpToolSession', 'TextSession', 'AdaptiveModelClient'],
                            'scope': 'Original bounded local conversation/memory pipeline; no voice/autonomy/full HANNI startup.'})
                    except Exception as exc:
                        save(output / f'conversation-{conversation_count}.json', {
                            'prompt': prompt, 'error': {'type': type(exc).__name__, 'message': str(exc)}})
            final_marker = output / 'final-protocol.json'
            if final_marker.is_file() and not (output / 'final-started.json').exists():
                payload = json.loads(final_marker.read_text(encoding='utf-8-sig'))
                assert set(payload) == {'session_nonce', 'protocol', 'production_freeze'}
                assert payload['session_nonce'] == nonce and payload['production_freeze'] is True
                save(output / 'final-started.json', {'started_at': time.time(), 'session_nonce': nonce})
                from final_campaign import run_final
                run_final(server, Path(payload['protocol']), output / 'final-results.json')
            time.sleep(.5)
    finally:
        stop.set()
        if server is not None:
            if thread is not None:
                server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(5)
        if hub is not None:
            hub.close()
            hub.db.close()
        if process is not None and process.poll() is None:
            owned = psutil.Process(process.pid)
            assert owned.create_time() == evidence['inference_create_time']
            assert hashlib.sha256(json.dumps(owned.cmdline()).encode()).hexdigest() == evidence['command_sha256']
        manager.close()
        assert not external or entry.process is None
        install_manager(None)
        close_service(config.paths.data_dir)
        with socket.socket() as probe:
            probe.settimeout(1)
            connection_result = probe.connect_ex((base.hostname, base.port))
        listeners = [item.pid for item in psutil.net_connections(kind='tcp')
                     if item.status == psutil.CONN_LISTEN and item.laddr.port == base.port]
        external_intact = (external and inference is not None and inference.is_running()
                           and inference.create_time() == evidence['inference_create_time']
                           and listeners == [inference.pid] and connection_result == 0)
        closed = {'closed_at': time.time(), 'owned_pid': getattr(process, 'pid', None),
                  'owned_process_closed': process is None or process.poll() is not None,
                  'external_original_preserved': bool(external_intact),
                  'owned_http_server_closed': server is None or server.socket.fileno() == -1,
                  'original_loopback_connection_result': connection_result,
                  'original_loopback_listener_pids': listeners,
                  'original_loopback_connection_refused': connection_result in (10061, 111),
                  'closed_verified': (server is None or server.socket.fileno() == -1)
                                     and (external_intact if external else (process is None or process.poll() is not None)
                                          and connection_result in (10061, 111) and listeners == []),
                  'scope': 'Original ModelManager.close, exact owned process receipt; no external process killed.'}
        save(output / 'closed.json', closed)
        print(json.dumps({'state': 'closed', 'closed_verified': closed['closed_verified']}), flush=True)


if __name__ == '__main__':
    main()
