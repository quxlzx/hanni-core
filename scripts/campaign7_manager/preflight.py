"""Read-only C7 inventory; never starts recording, playback, capture or models."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile
import httpx
import psutil
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf8', newline='\n')

def sources():
    chosen = {*ROOT.joinpath('src/hanni').rglob('*.py'), *ROOT.joinpath('config').rglob('*.yaml'), *ROOT.joinpath('tests').rglob('*.py'), ROOT / '.gitattributes', ROOT / 'pyproject.toml'}
    for folder in (ROOT / 'frontend/src', ROOT / 'src/hanni/dashboard/static'):
        chosen.update((p for p in folder.rglob('*') if p.is_file()))
    for name in ('package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts'):
        p = ROOT / 'frontend' / name
        if p.is_file():
            chosen.add(p)
    return sorted((p for p in chosen if p.is_file()))

def run():
    out = ROOT / 'data/campaign7-manager/preflight'
    out.mkdir(parents=True, exist_ok=False)
    source = {}
    with zipfile.ZipFile(out / 'source.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in sources():
            if path.is_symlink():
                raise ValueError('Refuse source symbolic links')
            name = path.relative_to(ROOT).as_posix()
            blob = path.read_bytes()
            source[name] = digest(blob)
            archive.writestr(name, blob)
    save(out / 'SOURCE_BEFORE.json', source)
    prior = {}
    for base in ('docs', 'scripts', 'evals'):
        for folder in (ROOT / base).glob('campaign[456]*'):
            for path in folder.rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    prior[path.relative_to(ROOT).as_posix()] = digest(path.read_bytes())
    for name in ('CALENDAR_FUTURE_DATE_ROOT_CAUSE.md', 'HANNI_LAYA_SHADOW_PATCH_20261009.zip', 'MODEL_BAKEOFF_FINAL.json', 'MODEL_BAKEOFF_FINAL.md', 'MODEL_PERSONALITY_BLIND.md'):
        path = ROOT / name
        if path.is_file():
            prior[name] = digest(path.read_bytes())
    for path in ROOT.joinpath('evals').rglob('campaign[456]*'):
        if path.is_file():
            prior[path.relative_to(ROOT).as_posix()] = digest(path.read_bytes())
    save(out / 'PRIOR_CAMPAIGN_AND_OWNER_FILES.json', prior)
    owner = {}
    for name in ('audio-routing.json', 'compute/deployment.json', 'compute/context-measurements.json'):
        path = ROOT / 'data' / name
        owner[name] = {'exists': path.is_file()}
        if path.is_file():
            owner[name]['sha256'] = digest(path.read_bytes())
    save(out / 'OWNER_FILE_IDENTITIES.json', owner)
    from hanni.speech.audio_devices import list_inputs, list_outputs, load_selection, routing_path
    from hanni.speech.tts import list_windows_voices
    devices = {'input_streams_opened': 0, 'playbacks_started': 0}
    for name, function in (('inputs', list_inputs), ('outputs', list_outputs)):
        try:
            devices[name] = [v.to_dict() for v in function()]
        except Exception as exc:
            devices[name] = []
            devices[name + '_error_class'] = type(exc).__name__
    try:
        devices['saved_selection'] = load_selection(routing_path(ROOT / 'data'))
    except Exception as exc:
        devices['selection_error_class'] = type(exc).__name__
    try:
        devices['sapi_voices'] = [{'name': v.name, 'culture': v.culture, 'gender': v.gender} for v in list_windows_voices()]
    except Exception as exc:
        devices['voice_error_class'] = type(exc).__name__
    save(out / 'DEVICES.json', devices)
    native = {}
    with httpx.Client(timeout=2, trust_env=False, follow_redirects=False) as client:
        for route in ('/health', '/v1/models', '/props'):
            try:
                reply = client.get('http://127.0.0.1:8080' + route)
                value = reply.json()
                if route == '/v1/models':
                    projected = {'model_ids': [v.get('id') for v in value.get('data', []) if isinstance(v, dict)]}
                elif route == '/props':
                    settings = value.get('default_generation_settings', {})
                    projected = {k: value.get(k) for k in ('modalities', 'model_ftype', 'model_path')}
                    projected['context_reported'] = settings.get('n_ctx') if isinstance(settings, dict) else None
                else:
                    projected = {'status': value.get('status')}
                native[route] = {'http_status': reply.status_code, **projected}
            except Exception as exc:
                native[route] = {'error_class': type(exc).__name__}
        try:
            chat = client.get('http://127.0.0.1:8765/api/chat?before=1').json()
            token = chat.get('token')
            del chat
            for route in ('/api/voice', '/api/awareness', '/api/state'):
                reply = client.get('http://127.0.0.1:8765' + route, headers={'X-Hanni-Token': token} if token else {})
                value = reply.json()
                if route == '/api/state':
                    value = {k: value.get(k) for k in ('sampled_at', 'activity', 'interaction')}
                native[route] = {'http_status': reply.status_code, 'snapshot': value}
            del token
        except Exception as exc:
            native['dashboard_error_class'] = type(exc).__name__
    save(out / 'NATIVE_READ_ONLY.json', native)
    from hanni.config.loader import load_config
    config = load_config(ROOT / 'config', data_dir=out / 'isolated-state', env={})
    memory = psutil.virtual_memory()
    budget = {'available_ram_bytes': memory.available, 'total_ram_bytes': memory.total, 'used_percent': memory.percent, 'configured_ram_reserve_mb': config.models.ram_reserve_mb, 'configured_critical_ram_percent': config.models.critical_ram_percent, 'additional_speech_model_budget_bytes': 1024 ** 3}
    budget['additional_model_load_allowed'] = memory.available >= config.models.ram_reserve_mb * 1024 ** 2 + budget['additional_speech_model_budget_bytes'] and memory.percent < config.models.critical_ram_percent
    save(out / 'RESOURCE_BUDGET.json', budget)
    identities = []
    for port in (8080, 8765):
        for connection in psutil.net_connections('tcp'):
            if connection.status == psutil.CONN_LISTEN and connection.laddr.port == port and connection.pid:
                process = psutil.Process(connection.pid)
                identities.append({'port': port, 'pid': process.pid, 'created': process.create_time(), 'parent_pid': process.ppid(), 'command_sha256': digest(json.dumps(process.cmdline()).encode())})
    save(out / 'LOCAL_RUNTIME.json', identities)
    after = {name: digest((ROOT / name).read_bytes()) for name in source}
    save(out / 'SOURCE_AFTER.json', after)
    if after != source:
        raise RuntimeError('Source changed during read-only discovery')
    summary = {'captured_at': time.time(), 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, cwd=ROOT).strip(), 'source_files': len(source), 'manifest_sha256': digest((out / 'SOURCE_BEFORE.json').read_bytes()), 'archive_sha256': digest((out / 'source.zip').read_bytes()), 'prior_files': len(prior), 'input_devices': len(devices.get('inputs', [])), 'output_devices': len(devices.get('outputs', [])), 'sapi_voices': len(devices.get('sapi_voices', [])), 'additional_model_load_allowed': budget['additional_model_load_allowed'], 'microphone_captures': 0, 'speaker_playbacks': 0, 'screen_captures': 0, 'webcam_access': 0, 'model_generation_requests': 0, 'source_stable': True}
    save(out / 'SUMMARY.json', summary)
    print(json.dumps(summary), flush=True)
if __name__ == '__main__':
    run()
