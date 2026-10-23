"""New isolated HTTP and log-boundary probes; only synthetic canaries."""
from __future__ import annotations
import ast
import hashlib
import http.client
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from scripts.campaign8_ui.backend import original_backend
ROOT = Path(__file__).resolve().parents[2]
CANARY = 'C9_SYNTHETIC_CANARY_prism_638921'

def private_routes():
    tree = ast.parse((ROOT / 'src/hanni/dashboard/server.py').read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any((isinstance(t, ast.Name) and t.id == 'private_routes' for t in node.targets)):
            return tuple(sorted(ast.literal_eval(node.value)))
    raise AssertionError('Original private route declaration absent; inspect router before probing.')

def raw_request(backend, path, *, method='GET', body=None, headers=None):
    connection = http.client.HTTPConnection('127.0.0.1', backend.server.server_port, timeout=8)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        return (response.status, dict(response.getheaders()), data)
    finally:
        connection.close()

def error_probes(backend):
    """Real original Handler serialization, patched dependency errors only."""
    results = []
    targets = [('/api/gpu-routing', 'hanni.dashboard.server.Handler._gpu_state'), ('/api/audio-devices', 'hanni.speech.audio_devices.routing_state')]
    for route, target in targets:
        for kind in (OSError, RuntimeError, ValueError):
            with patch(target, side_effect=kind(CANARY)):
                status, _, body = raw_request(backend, route)
            results.append({'id': f'GET:{route}:{kind.__name__}', 'status': status, 'synthetic_canary_reflected': CANARY.encode() in body, 'body_sha256': hashlib.sha256(body).hexdigest(), 'expected': '503 without registered synthetic credential reflection'})
    for kind in (ValueError, RuntimeError):
        with patch.object(backend.features, 'mutate', side_effect=kind(CANARY)):
            status, _, body = raw_request(backend, '/api/productivity', method='POST', body='{}', headers={'Origin': backend.url, 'X-Hanni-Token': backend.chat.token, 'Content-Type': 'application/json'})
        results.append({'id': f'POST:/api/productivity:{kind.__name__}', 'status': status, 'synthetic_canary_reflected': CANARY.encode() in body, 'body_sha256': hashlib.sha256(body).hexdigest(), 'expected': '400 or 409 without registered synthetic credential reflection'})
    return results

def log_probes():
    from hanni.logs.formatter import JsonFormatter, TextFormatter
    from hanni.logs.redaction import RedactionFilter

    class SyntheticObject:

        def __str__(self):
            return CANARY
    rows = []
    variants = {'dictionary_key': {CANARY: 'fixture'}, 'object_representation': {'object': SyntheticObject()}, 'nested_values': {'list': [CANARY, {'value': CANARY}]}}
    for name, value in variants.items():
        record = logging.LogRecord('hanni.campaign9.synthetic', logging.ERROR, __file__, 1, 'Controlled event', (), None)
        record.payload = value
        RedactionFilter().filter(record)
        text = JsonFormatter(node_id='synthetic-local').format(record)
        rows.append({'id': name, 'synthetic_canary_reflected': CANARY in text, 'json_valid': isinstance(json.loads(text), dict), 'output_sha256': hashlib.sha256(text.encode()).hexdigest()})
    try:
        raise RuntimeError(CANARY)
    except RuntimeError:
        import sys
        info = sys.exc_info()
    for formatter in (JsonFormatter(node_id='synthetic-local'), TextFormatter()):
        record = logging.LogRecord('hanni.campaign9.synthetic', logging.ERROR, __file__, 1, 'Controlled exception', (), info)
        text = formatter.format(record)
        rows.append({'id': type(formatter).__name__ + '_exception', 'synthetic_canary_reflected': CANARY in text, 'output_sha256': hashlib.sha256(text.encode()).hexdigest()})
    return rows

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise RuntimeError('Preserve original evidence; refusing overwrite.')
    from hanni.logs.redaction import register_secret, clear_registry
    register_secret('C9_SYNTHETIC_ONLY', CANARY)
    try:
        with TemporaryDirectory(prefix='hanni-c9-api-') as temp:
            with original_backend(Path(temp) / 'runtime') as backend:
                errors = error_probes(backend)
                logs = log_probes()
                result = {'evidence_class': 'CONTROLLED_ORIGINAL_HTTP_AND_LOG_IMPLEMENTATION', 'fault_adapters': 'Synthetic dependency exceptions; no provider/hardware execution', 'private_route_inventory': list(private_routes()), 'HTTP_error_probes': errors, 'log_probes': logs, 'owner_stores_mounted': False, 'model_generation': False, 'production_source_hashes': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ['src/hanni/dashboard/server.py', 'src/hanni/logs/formatter.py', 'src/hanni/logs/redaction.py']}}
            result['owned_backend_closed'] = backend.closed and (not backend.thread.is_alive())
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'output': args.out.as_posix(), 'HTTP_probes': len(errors), 'HTTP_canary_reflections': sum((x['synthetic_canary_reflected'] for x in errors)), 'log_probes': len(logs), 'log_canary_reflections': sum((x['synthetic_canary_reflected'] for x in logs)), 'owned_backend_closed': result['owned_backend_closed']}))
    finally:
        clear_registry()
if __name__ == '__main__':
    main()
