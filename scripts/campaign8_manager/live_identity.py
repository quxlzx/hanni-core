"""Bounded owner endpoint metadata, not model inference or hardware playback."""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import psutil
from .preflight import get
ROOT = Path(__file__).resolve().parents[2]

def main():
    sampled = datetime.now(timezone.utc)
    memory = psutil.virtual_memory()
    out = {'timestamp': sampled.isoformat(), 'evidence_class': 'LIVE_READ_ONLY', 'real_inference': 'NOT_RUN: this bounded probe reads metadata only', 'resource_observation': {'available_ram_bytes': memory.available, 'used_percent': memory.percent, 'original_reserve_mib': 3072, 'above_reserve_at_sample': memory.available >= 3072 * 1024 ** 2, 'not_an_admission_decision': True}}
    for route in ('/health', '/v1/models', '/props'):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8080' + route, timeout=8) as response:
                data = json.load(response)
            if route == '/props':
                defaults = data.get('default_generation_settings', {})
                data = {'model_path': data.get('model_path'), 'model_alias': data.get('model_alias'), 'total_slots': data.get('total_slots'), 'modalities': data.get('modalities'), 'context': defaults.get('n_ctx'), 'context_is_metadata_only': True}
            out[route] = data
        except Exception as exc:
            out[route] = {'error_type': type(exc).__name__}
    try:
        state = get('/api/state')
        out['dashboard_state'] = {key: state.get(key) for key in ('sampled_at', 'model_status', 'error', 'safe_mode', 'model', 'roles', 'model_residency')}
        token = get('/api/chat?before=1').get('token')
        voice = get('/api/voice', token)
        out['voice'] = {key: voice.get(key) for key in ('available', 'status', 'phase', 'muted', 'reason')}
        aware = get('/api/awareness', token)
        out['awareness'] = {key: aware.get(key) for key in ('available', 'enabled', 'reason', 'capture_enabled', 'status')}
    except Exception as exc:
        out['owner_projection_error'] = type(exc).__name__
    path = ROOT / 'docs/campaign8/LIVE_IDENTITY.json'
    snapshots = ROOT / 'data/campaign8-manager/live-identity'
    snapshots.mkdir(exist_ok=True)
    if path.is_file() and (not (snapshots / 'previous.json').exists()):
        (snapshots / 'previous.json').write_bytes(path.read_bytes())
    (snapshots / (sampled.strftime('%Y%m%dT%H%M%S%fZ') + '.json')).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(path.relative_to(ROOT))
    print(json.dumps(out, ensure_ascii=False, indent=2))
if __name__ == '__main__':
    main()
