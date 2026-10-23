"""Own an isolated ORIGINAL dashboard/text controller and its cached local model.

This harness does not replace the controller, tools, telemetry or model replies.
Only configuration paths and durable state are isolated. Model identity/sampling,
MCP permissions and rollout defaults are copied unchanged from current config.
Native clients attach separately; no microphone or TTS is started.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from desktop.main import request_json


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model-file', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'data'):
        raise ValueError('Campaign output must remain under ignored repository data.')
    if not args.model_file.is_file() or args.model_file.stat().st_size < 1_000_000:
        raise ValueError('An existing cached GGUF is required; no downloads allowed.')
    output.mkdir(parents=True, exist_ok=True)
    configs, data = output / 'config', output / 'state'
    configs.mkdir(exist_ok=True)
    data.mkdir(exist_ok=True)
    config_hashes = {}
    for original in sorted((ROOT / 'config').glob('*.yaml')):
        target = configs / original.name
        shutil.copy2(original, target)
        config_hashes[original.name] = hashlib.sha256(original.read_bytes()).hexdigest()
    port = free_port()
    url = f'http://127.0.0.1:{port}'
    command = [sys.executable, str(ROOT/'scripts/v36_engineering/controlled_launcher.py'), '--text',
               '--no-browser', '--port', str(port), '--config-dir', str(configs),
               '--data-dir', str(data), '--model-file', str(args.model_file.resolve()),
               '--startup-timeout', '180']
    env = os.environ.copy()
    env.update(HANNI_DATA_DIR=str(data), HANNI_CONFIG_DIR=str(configs),
               HANNI_CHAT_HISTORY='session', HANNI_LAYA_SHADOW_ENABLED='0',
               HANNI_V36_EVIDENCE_DIR=str(output),
               PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8')
    result = {'version': 1, 'harness_pid': os.getpid(), 'origin': url,
              'data_dir': str(data), 'config_dir': str(configs),
              'command': command, 'config_original_sha256': config_hashes,
              'production_state_database_access': False,
              'google_dependency': 'Explicit empty vault bound before original controller/features imports; no Windows Credential Manager lookup or live Google transmission.',
              'native_client': 'attach-only separately',
              'model': 'Current configured cached Qwen supervisor; original ModelManager owns startup/shutdown.',
              'disclosure': 'Actual dashboard.launcher -> original CLI text -> original MemoryAwareSession/McpToolSession, real OS telemetry. Temporary durable databases; unchanged MCP permission policy. No microphone, TTS, mocked telemetry, controller fixture, downloads or production assistant startup.'}
    (output / 'identity.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    child = None
    with (output / 'controller.log').open('w', encoding='utf-8') as log:
        try:
            child = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.PIPE,
                                     stdout=log, stderr=subprocess.STDOUT,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            result['controller_pid'] = child.pid
            deadline = time.monotonic() + 195
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    raise RuntimeError('Original controller exited during startup; inspect controller.log.')
                try:
                    status = request_json(url, '/api/chat', timeout=2)
                    if status.get('ready'):
                        break
                except (OSError, ValueError, RuntimeError):
                    pass
                time.sleep(.25)
            else:
                raise RuntimeError('Original controller never became chat-ready.')
            result['ready'] = True
            result['workspace'] = request_json(url, '/api/workspace')
            # The metadata contains no authentication token, user messages or memory.
            (output / 'identity.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(json.dumps({key: result[key] for key in
                              ('origin', 'controller_pid', 'data_dir', 'config_dir', 'ready')}), flush=True)
            while child.poll() is None and not (output / 'STOP').exists():
                time.sleep(.5)
        finally:
            if child is not None and child.poll() is None:
                try:
                    status = request_json(url, '/api/chat', timeout=3)
                    request_json(url, '/api/shutdown', body={}, token=status['token'], timeout=3)
                    child.wait(timeout=55)
                except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
                    # Only this exact owned launcher, never any unrelated process.
                    child.terminate()
                    child.wait(timeout=15)
            result.update(closed=child is None or child.poll() is not None,
                          controller_exit_code=None if child is None else child.returncode)
            (output / 'identity.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return 0 if result.get('ready') and result.get('closed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
