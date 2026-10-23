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
    args = parser.parse_args()
    output = args.output.resolve()
    weights = args.weights.resolve()
    assert output.is_relative_to((ROOT / 'data/v43-verification').resolve()) and not output.exists()
    assert 60 <= args.seconds <= 7200
    state_directory = output / 'state'
    if args.state_from:
        previous = args.state_from.resolve()
        assert previous.is_relative_to((ROOT / 'data/v43-verification').resolve())
        prior_closed = json.loads((previous / 'closed.json').read_text(encoding='utf8'))
        assert prior_closed['closed_verified'] and prior_closed['external_original_preserved']
        assert args.preserve_existing_primary
        state_directory = previous / 'state'
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
        hub.ready = True
        def telemetry():
            return {'sampled_at': time.time(), 'model_status': 'ready', 'error': None,
                    'resources': snapshot_resources().to_dict(), 'safe_mode': False,
                    'model_residency': manager.snapshot(),
                    'activity': {'input_level': 0, 'speaking': False, 'microphone_active': False},
                    'interaction': {'response_in_progress': False, 'tts_speaking': False, 'voice_engaged': False},
                    'model': {'file': spec.model_file, 'quantization': spec.quantization, 'context': spec.context_length}}
        cluster = SimpleNamespace(start=lambda: None, close=lambda: None,
                                  snapshot=lambda: {'nodes': [], 'available': False, 'sampled_at': None})
        power = SimpleNamespace(start=lambda: None, close=lambda: None, project=lambda value: value)
        terminal = SimpleNamespace(project=lambda value: value)
        server = DashboardServer(0, SimpleNamespace(config=config, snapshot=telemetry), hub,
                                 shutdown_event=stop, cluster=cluster, cluster_power=power, cluster_terminal=terminal)
        server.features.registry.google_access._vault = EmptyVault()
        server.mcp.attach_controller(server.features.registry, model_tools_enabled=True, observe_first=True)
        server.model_routing.controller_attached = True
        server.model_routing.refresh()
        assert hasattr(server, 'model_lab'), 'The production Model Lab service has not been integrated.'
        thread = threading.Thread(target=server.serve_forever, name='v43-owned-lab-server', daemon=True)
        thread.start()
        ready = {'url': f'http://127.0.0.1:{server.server_port}', 'ready_at': time.time(),
                 'helper_pid': evidence['helper_pid'], 'helper_create_time': evidence['helper_create_time'],
                 'session_nonce': nonce, 'controller_registry': 'original DesktopFeatures ToolRegistry',
                 'scope': 'Original bounded current-source controller and ModelLab; primary inference ' + ('shared external and preserved' if external else 'owned') + '. Cluster disabled; empty Google vault; no voice/interactive assistant.'}
        save(output / 'ready.json', ready)
        print(json.dumps({'state': 'ready', 'url': ready['url'], 'inference_pid': inference.pid,
                          'inference_owned': not external, 'load_time_ms': evidence['load_time_ms']}), flush=True)
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline and inference.is_running() and inference.create_time() == evidence['inference_create_time']:
            marker = output / 'stop.json'
            if marker.is_file():
                payload = json.loads(marker.read_text(encoding='utf8'))
                assert payload == {'session_nonce': nonce}, 'Stop marker ownership does not match.'
                break
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
