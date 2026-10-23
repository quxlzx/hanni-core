"""Input-only original implementation calls; unsupported perception stays absent."""
from contextlib import ExitStack
from dataclasses import replace
import hashlib
import http.client
import json
from pathlib import Path
import socket
import subprocess
import threading
from types import SimpleNamespace
from unittest.mock import patch
REPO = Path(__file__).resolve().parents[2]
OPERATIONS = frozenset({'awareness_status', 'denied_awareness_mutation', 'registry_capability_missing', 'native_multimodal_rejected', 'vision_eligibility', 'frontend_disabled_projection'})
UNIMPLEMENTED = frozenset({'snapshot', 'enable', 'capture', 'analyze', 'stop', 'expiry', 'sensitivity'})

def source_hashes():
    paths = ['src/hanni/dashboard/features.py', 'src/hanni/dashboard/server.py', 'src/hanni/models/adaptive.py', 'src/hanni/models/registry.py', 'frontend/src/awareness.tsx', 'src/hanni/dashboard/static/app.js']
    return {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in paths}

def configuration(root, settings):
    from hanni.config.loader import load_config
    from hanni.config.schema import parse_privacy
    config = load_config(REPO / 'config', data_dir=root, env={})
    retention = settings.get('retention_seconds', settings.get('screen_frames_seconds', 120))
    privacy = parse_privacy({'ephemeral_retention': {'screen_frames_seconds': retention}, 'screen_exclusions': settings.get('screen_exclusions', {})})
    return replace(config, privacy=privacy)

def eligibility_row(request):
    row = {'blocked_reasons': [], 'legacy_default': bool(request.get('legacy_default', False)), 'model_id': 'synthetic-model', 'configured_model': 'synthetic-model', 'local': True, 'allowed_categories': ['synthetic'], 'max_context_verified': 4096, 'context_configured': 4096, 'capabilities': ['text'], 'structured_output_formats': [], 'tool_calling_formats': [], 'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': 2 * 1024 ** 3, 'concurrency': 1, 'current_requests': 0, 'queue_depth': 0}
    if request.get('remote'):
        row.update(local=False, worker={'worker_id': 'controlled-only'})
    row.update(request.get('row', {}))
    return row

def run_case(case, root):
    if set(case) & {'expected', 'oracle', 'checker_inputs'}:
        raise ValueError('Execution does not accept expected answers.')
    root = Path(root).resolve()
    if root.exists():
        raise ValueError('Use a fresh disposable case directory.')
    root.mkdir(parents=True)
    operation = case.get('operation')
    request = case.get('request', {})
    settings = case.get('settings', request.get('settings', {}))
    before = source_hashes()
    observation, error, connections = ({}, None, [])

    def forbidden_connect(sock, destination):
        connections.append(str(destination))
        raise AssertionError('This implementation control forbids network dispatch.')
    with ExitStack() as stack:
        try:
            config = configuration(root, settings)
            from hanni.dashboard.features import DesktopFeatures
            feature = DesktopFeatures(config)
            if operation in UNIMPLEMENTED:
                observation = {'classification': 'NOT_IMPLEMENTED', 'reason': feature.awareness()['reason'], 'status': feature.awareness(), 'operation_executed': False}
            elif operation == 'awareness_status':
                observation = {'status': feature.awareness(), 'classification': 'OBSERVED_DISABLED', 'retention_scope': 'Saved configuration only; no captured context or expiry mechanism exists.'}
            elif operation == 'denied_awareness_mutation':
                from hanni.dashboard.server import DashboardServer
                stop = threading.Event()
                if request.get('stop_active'):
                    stop.set()
                server = DashboardServer(0, SimpleNamespace(config=config, snapshot=lambda: {}), shutdown_event=stop)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    headers = {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{server.server_port}'}
                    if request.get('authorized', True):
                        headers['X-Hanni-Token'] = server.chat.token
                    if request.get('foreign_origin'):
                        headers['Origin'] = 'http://foreign.invalid'
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                    try:
                        connection.request('POST', '/api/awareness', headers=headers, body=json.dumps({'action': request.get('action', 'capture')}))
                        response = connection.getresponse()
                        observation = {'http_status': response.status, 'body': json.loads(response.read()), 'classification': 'UNREGISTERED_MUTATION', 'status': feature.awareness()}
                    finally:
                        connection.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(5)
                observation['owned_server_closed'] = not thread.is_alive()
            elif operation == 'registry_capability_missing':
                from hanni.tools.registry import build_default_registry
                registry = build_default_registry(config, data_dir=root)
                names = [d.name for d in registry.definitions()]
                name = request.get('name', 'screen.capture')
                observation = {'registered_names': names, 'requested_name': name, 'perception_definitions': [n for n in names if n.startswith(('screen.', 'vision.', 'camera.'))]}
                registry.get(name)
            elif operation == 'native_multimodal_rejected':
                from hanni.models.adaptive import AdaptiveModelEngine, ModelRequest
                stack.enter_context(patch.object(socket.socket, 'connect', forbidden_connect))
                engine = AdaptiveModelEngine(config)
                stack.callback(engine.close)
                messages = request.get('messages', [{'role': 'user', 'content': [{'type': 'text', 'text': 'Synthetic image fixture only.'}, {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,iVBORw0KGgo='}}]}])
                observation['message_scope'] = 'Synthetic image-like input; no image acquisition or decoding.'
                engine.execute(messages, request=ModelRequest(capabilities=frozenset({'vision'}), privacy_categories=frozenset({'synthetic'}), output_tokens=16), max_tokens=16)
            elif operation == 'vision_eligibility':
                from hanni.models.adaptive import AdaptiveModelEngine, ModelRequest
                stack.enter_context(patch.object(socket.socket, 'connect', forbidden_connect))
                if request.get('model') is not None:
                    from hanni.models.registry import model_spec
                    if not isinstance(request['model'], str):
                        raise ValueError('The model diagnostic expects a configured model identifier.')
                    observation['requested_model'] = request['model']
                    observation['configured_model_id'] = model_spec(config, request['model']).id
                engine = AdaptiveModelEngine(config)
                stack.callback(engine.close)
                row = eligibility_row(request)
                model_request = ModelRequest(capabilities=frozenset(request.get('capabilities', ['vision'])), privacy_categories=frozenset(request.get('privacy_categories', ['synthetic'])), allow_legacy_default=bool(request.get('legacy_default', False)), output_tokens=16)
                observation.update({'reasons': engine._reasons(row, model_request), 'row': row, 'scope': 'Original pure eligibility guard with controlled row; not live endpoint selection or vision proof.'})
            elif operation == 'frontend_disabled_projection':
                status = feature.awareness()
                wire = json.dumps({'status': status, 'error': request.get('error', ''), 'token_present': request.get('token_present', True)})
                result = subprocess.run(['node', str(REPO / 'scripts/campaign7_screen/render.cjs')], input=wire, text=True, capture_output=True, timeout=15, cwd=REPO)
                if result.returncode:
                    raise RuntimeError(result.stderr)
                observation = json.loads(result.stdout)
                observation['status'] = status
            else:
                raise ValueError('Unsupported audit operation.')
        except Exception as exc:
            error = {'type': type(exc).__name__, 'message': str(exc)}
    return {'id': case.get('id'), 'operation': operation, 'observation': observation, 'error': error, 'network_attempts': connections, 'model_dispatches': 0, 'physical_capture_calls': 0, 'scope': 'Original isolated implementation controls; no camera, desktop capture, audio or model invocation.', 'source_before': before, 'source_after': source_hashes()}
