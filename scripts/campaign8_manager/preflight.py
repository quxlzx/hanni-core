"""Non-mutating original-source/runtime receipt for native Campaign 8 QA."""
from __future__ import annotations
import ctypes
import hashlib
import json
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import psutil
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/campaign8-manager'

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def get(path, token=None):
    headers = {'X-Hanni-Token': token} if token else {}
    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8765' + path, headers=headers), timeout=8) as response:
        return json.load(response)

def runtime():
    rows = []
    listeners = {}
    for connection in psutil.net_connections(kind='inet'):
        if connection.status == psutil.CONN_LISTEN and connection.laddr.port in {8080, 8765}:
            listeners[str(connection.laddr.port)] = connection.pid
    native = []
    for proc in psutil.process_iter(['pid', 'name', 'create_time', 'exe']):
        try:
            if (proc.info['name'] or '').casefold() == 'hanni os.exe':
                native.append({key: proc.info[key] for key in ('pid', 'name', 'create_time', 'exe')})
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    for pid in sorted(set(listeners.values())):
        if pid is None:
            continue
        proc = psutil.Process(pid)
        rows.append({'pid': pid, 'created': proc.create_time(), 'parent': proc.ppid(), 'command_sha256': hashlib.sha256('\x00'.join(proc.cmdline()).encode()).hexdigest()})
    memory = psutil.virtual_memory()
    return {'ports': listeners, 'processes': rows, 'native_clients': native, 'ram': {'total': memory.total, 'available': memory.available, 'percent': memory.percent}}

def run():
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT / 'original-source.zip'
    if archive.exists():
        raise RuntimeError('Original source already sealed; refusing overwrite.')
    files = set()
    for directory in ('src', 'frontend/src', 'frontend/public', 'desktop', 'config', 'tests', 'scripts'):
        for path in (ROOT / directory).rglob('*'):
            if path.is_file() and (not any((part in {'__pycache__', 'node_modules', '.pytest_cache'} for part in path.parts))):
                if path.suffix not in {'.pyc', '.log'}:
                    files.add(path)
    for name in ('.gitattributes', 'pyproject.toml', 'START_HANNI.cmd', 'START_HANNI_OS.cmd'):
        if (ROOT / name).is_file():
            files.add(ROOT / name)
    for path in (ROOT / 'frontend').glob('*'):
        if path.is_file():
            files.add(path)
    manifest = {str(path.relative_to(ROOT)).replace('\\', '/'): digest(path) for path in sorted(files)}
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(files):
            bundle.write(path, path.relative_to(ROOT))
    protected = {}
    for directory in ('docs/campaign4', 'docs/campaign5', 'docs/campaign6', 'docs/campaign7', 'scripts/campaign4', 'scripts/campaign5_benchmark', 'scripts/campaign5_intelligence', 'scripts/campaign6_cluster', 'scripts/campaign6_scheduling', 'scripts/campaign7_voice', 'scripts/campaign7_screen'):
        for path in (ROOT / directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                protected[path.relative_to(ROOT).as_posix()] = digest(path)
    for name in ('CALENDAR_FUTURE_DATE_ROOT_CAUSE.md', 'HANNI_LAYA_SHADOW_PATCH_20261009.zip', 'MODEL_BAKEOFF_FINAL.json', 'MODEL_BAKEOFF_FINAL.md', 'MODEL_PERSONALITY_BLIND.md', 'data/compute/deployment.json', 'data/compute/context-measurements.json'):
        path = ROOT / name
        if path.is_file():
            protected[name] = digest(path)
    artifact = ROOT / 'dist/HANNI OS/HANNI OS.exe'
    observation = {'timestamp': datetime.now(timezone.utc).isoformat(), 'runtime': runtime(), 'native_artifact': {'path': artifact.relative_to(ROOT).as_posix(), 'sha256': digest(artifact), 'bytes': artifact.stat().st_size, 'modified': artifact.stat().st_mtime}, 'source_manifest': manifest, 'archive_sha256': digest(archive), 'protected': protected}
    try:
        observation['workspace'] = get('/api/workspace')
        token = get('/api/chat?before=1').get('token')
        state = get('/api/state')
        observation['state'] = {key: state.get(key) for key in ('sampled_at', 'model_status', 'error', 'safe_mode', 'model', 'roles', 'model_residency')}
        voice = get('/api/voice', token)
        observation['voice'] = {key: voice.get(key) for key in ('available', 'status', 'phase', 'muted', 'reason')}
        aware = get('/api/awareness', token)
        observation['awareness'] = {key: aware.get(key) for key in ('available', 'enabled', 'reason', 'capture_enabled', 'status')}
    except Exception as exc:
        observation['owner_projection_error'] = type(exc).__name__
    try:
        user32 = ctypes.windll.user32
        observation['windows_display'] = {'system_dpi': user32.GetDpiForSystem(), 'primary_width': user32.GetSystemMetrics(0), 'primary_height': user32.GetSystemMetrics(1), 'monitor_count': user32.GetSystemMetrics(80)}
    except Exception as exc:
        observation['windows_display_error'] = type(exc).__name__
    path = OUT / 'PREFLIGHT.json'
    path.write_text(json.dumps(observation, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'receipt': path.relative_to(ROOT).as_posix(), 'files': len(manifest), 'archive_sha256': observation['archive_sha256'], 'runtime': observation['runtime'], 'screens': observation.get('workspace', {}).get('screens'), 'display': observation.get('windows_display')}, indent=2))
if __name__ == '__main__':
    run()
