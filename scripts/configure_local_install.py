"""Make a source installation launchable without manual model preparation."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import json
import http.client
import os
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.native.model_settings import ModelSettings, atomic_json

STARTER = 'MiniCPM5-2B-Q4_K_M.gguf'
DOWNLOADS = {STARTER: '2b', 'K2-Horizon-4B-Q4_K_M.gguf': '3.7b', 'K2-Horizon-7B-Q4_K_M.gguf': '7b'}


def valid_model(path):
    if not path.is_file() or path.stat().st_size < 1024**2: return False
    with path.open('rb') as stream:
        header = stream.read(8)
        return header[:4] == b'GGUF' and int.from_bytes(header[4:], 'little') in {2, 3}


def configure(root=ROOT, *, offline=False, run=subprocess.run):
    root = Path(root).resolve()
    control = ModelSettings(root / 'state', root / 'models')
    active = control.active()
    if active and active.get('source') == 'api':
        return {'source': 'api', 'selection_retained': True}
    filename = active.get('local_model') if active else None
    if not filename:
        filename = next((row['id'] for row in control.inventory()
                         if row['installed'] and valid_model(root / 'models' / row['id'])), STARTER)
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise ValueError('The saved model path is invalid. Choose a model in HANNI settings.')
    model = root / 'models' / filename
    if not valid_model(model):
        if model.exists(): raise RuntimeError('The selected GGUF is incomplete or invalid. Restore it before rerunning setup.')
        if offline: raise RuntimeError('No local GGUF model is available. Offline setup requires a model in the models folder.')
        if filename not in DOWNLOADS:
            raise RuntimeError('The saved custom model is missing. Restore that GGUF in the models folder; setup retained your selection.')
        print(f'Downloading {filename}. This first-run model download can take several minutes.', flush=True)
        run([sys.executable, str(root / 'scripts/get_models.py'), '--tier', DOWNLOADS[filename],
             '--skip-binaries', '--root', str(root)], check=True)
        if not valid_model(model): raise RuntimeError('Model download did not produce a valid GGUF. Check the download/network policy and rerun setup.')
    if not active:
        selection = control.validate({'source': 'local', 'local_model': filename, 'context': 65536})
        atomic_json(control.root / 'model-selection.json', selection)
        control.remember_profile(selection)
    return {'source': 'local', 'model': filename, 'selection_retained': bool(active)}


def repair_open_desktop(root=ROOT, *, timeout=600):
    """Repair an already-open offline window without killing or duplicating it."""
    import psutil
    root = Path(root).resolve()
    executable = root / 'dist/HANNI OS/HANNI OS.exe'
    status = local_status()
    if status['ready']: return
    owners = []
    for process in psutil.process_iter(['pid', 'exe']):
        try:
            if process.info['exe'] and Path(process.info['exe']).resolve() == executable: owners.append(process)
        except (OSError, psutil.Error): continue
    if len(owners) != 1: raise RuntimeError('Could not verify one open HANNI desktop. Close duplicate windows and run START_HANNI.cmd.')
    desktop = owners[0]
    existing = status['present'] or any(p.name().lower() in {'python.exe', 'pythonw.exe'} for p in desktop.children(recursive=True))
    child = None
    if not existing:
        logs = Path(os.environ.get('LOCALAPPDATA', str(root / 'state'))) / 'HANNI OS'
        logs.mkdir(parents=True, exist_ok=True)
        ready = logs / ('setup-ready-' + uuid4().hex + '.json')
        with (logs / 'setup-assistant.log').open('ab') as log:
            child = subprocess.Popen([sys.executable, str(root / 'scripts/firstboot.py'), '--serve', '--wait', '--ui',
                '--no-browser', '--desktop-owner-pid', str(desktop.pid), '--ready-file', str(ready)], cwd=root,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if local_status()['ready']: return
        if child and child.poll() is not None:
            raise RuntimeError('The assistant could not start after repair. Read %LOCALAPPDATA%/HANNI OS/setup-assistant.log for the exact runtime error.')
        if not desktop.is_running(): raise RuntimeError('The desktop closed during repair. Open HANNI again to start its assistant.')
        time.sleep(.5)
    raise RuntimeError('Assistant startup is still in progress. Check setup-assistant.log; setup did not start another model copy.')


def local_status():
    def get(path):
        connection = http.client.HTTPConnection('127.0.0.1', 8311, timeout=2)
        try:
            connection.request('GET', path); response = connection.getresponse()
            data = json.loads(response.read(1024**2))
            return data if response.status == 200 and isinstance(data, dict) else {}
        except (OSError, ValueError, http.client.HTTPException): return {}
        finally: connection.close()
    workspace = get('/api/workspace')
    screens = workspace.get('screens')
    present = (workspace.get('version') == 1 and workspace.get('transport') == 'http-snapshots'
               and isinstance(screens, list) and 'chat' in screens)
    chat = get('/api/chat?before=1') if present else {}
    return {'present': present, 'ready': present and chat.get('ready') is True}


def wait_for_assistant(*, timeout=600):
    print('Waiting for the configured assistant to become ready. The first model load can take several minutes.', flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if local_status()['ready']: return
        time.sleep(.5)
    raise RuntimeError('The assistant did not become ready. Read %LOCALAPPDATA%/HANNI OS/assistant.log for the exact runtime or model error. Setup has not registered a new startup entry.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--repair-open-desktop', action='store_true')
    parser.add_argument('--wait-ready', action='store_true')
    args = parser.parse_args()
    if args.wait_ready:
        wait_for_assistant()
        print('Assistant startup: verified and ready.')
        return
    if args.repair_open_desktop:
        repair_open_desktop(args.root)
        print('The open HANNI desktop is connected to its assistant.')
        return
    result = configure(args.root, offline=args.offline)
    print('Model startup: existing API connection retained.' if result['source'] == 'api'
          else 'Model startup: ready (' + result['model'] + ').')


if __name__ == '__main__': main()
