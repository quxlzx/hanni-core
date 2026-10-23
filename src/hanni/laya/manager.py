"""Best-effort Laya shadow lifecycle tied to a HANNI run.

No network access by default. With explicit opt-in, can run a local model
or connect to a user's own Linux model machine over an SSH loopback tunnel.
Never reads or changes the durable memory store.
"""
from __future__ import annotations

import atexit
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from .client import ShadowClient, _NoRedirect
from .server import default_token_path

_LOCAL = '127.0.0.1'
_REMOTE_COMMAND = ('cd ~/hanni-laya && exec .venv-rocm/bin/python -m '
                   'hanni_laya_shadow.server --model '
                   '~/hanni-laya-models/laya-general-v2 --port 8765')
_manager = None
_lock = threading.Lock()


def enabled(env=None):
    env = os.environ if env is None else env
    return env.get('HANNI_LAYA_SHADOW_ENABLED', '').lower() in ('1', 'true', 'yes')


class LayaShadowManager:
    """A single optional shadow observer; all start/stop work is off the turn path."""

    def __init__(self, env=None, *, popen=subprocess.Popen, run=subprocess.run):
        self.env = dict(os.environ if env is None else env)
        self._popen = popen
        self._run = run
        self._worker = None
        self._shutdown = threading.Event()
        self._processes = []
        self._client = None
        self.status = 'disabled'
        self.mode = self.env.get('HANNI_LAYA_TRANSPORT', 'local').strip().lower()
        self.port = int(self.env.get('HANNI_LAYA_LOCAL_PORT', '8766'))
        self.remote_port = int(self.env.get('HANNI_LAYA_REMOTE_PORT', '8765'))
        if self.mode not in ('local', 'remote-ssh') or not (1024 <= self.port <= 65535) or not (1024 <= self.remote_port <= 65535):
            raise ValueError('Invalid Laya transport/port configuration')
        self._url = f'http://{_LOCAL}:{self.port}/v1/shadow/evaluate'
        self._health_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def start(self):
        if not enabled(self.env) or self._worker is not None:
            return
        # The opt-in must cover text crossing machines, not only model startup.
        if self.mode == 'remote-ssh' and self.env.get('HANNI_LAYA_ALLOW_REMOTE_TEXT') != '1':
            self.status = 'disabled: remote text consent not enabled'
            return
        self.status = 'connecting'
        self._worker = threading.Thread(target=self._connect, name='hanni-laya-startup', daemon=True)
        self._worker.start()

    def _ssh(self):
        host = self.env.get('HANNI_LAYA_SSH_HOST', '').strip()
        if not host or host.startswith('-') or any(c.isspace() for c in host):
            raise ValueError('Set HANNI_LAYA_SSH_HOST to a trusted user@host')
        identity = self.env.get('HANNI_LAYA_SSH_IDENTITY', '').strip()
        args = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                '-o', 'ConnectTimeout=5', '-o', 'ServerAliveInterval=10',
                '-o', 'ServerAliveCountMax=2']
        if identity:
            args += ['-i', str(Path(identity).expanduser())]
        return args, host

    def _read_token(self):
        if self.mode == 'local':
            token_file = Path(self.env.get('HANNI_LAYA_TOKEN_FILE', str(default_token_path()))).expanduser()
            if not token_file.is_file() or token_file.is_symlink():
                raise ValueError('Laya token file unavailable')
            return token_file.read_text(encoding='utf-8').strip()
        ssh, host = self._ssh()
        result = self._run([*ssh, host, 'cat ~/.config/hanni/laya-shadow.token'],
                           capture_output=True, text=True, timeout=9, check=True)
        return result.stdout.strip()

    def _healthy(self, token):
        url = f'http://{_LOCAL}:{self.port}/v1/shadow/health'
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
        try:
            with self._health_opener.open(req, timeout=0.6) as res:
                return res.status == 200
        except (OSError, ValueError):
            return False

    def _spawn(self, args):
        if self._shutdown.is_set():
            return None
        # No shell locally, no output to console logs that could contain a secret.
        proc = self._popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        self._processes.append(proc)
        return proc

    def _connect(self):
        try:
            if self.mode == 'remote-ssh':
                ssh, host = self._ssh()
                tunnel = self._spawn([*ssh, '-o', 'ExitOnForwardFailure=yes', '-N',
                                      '-L', f'{_LOCAL}:{self.port}:{_LOCAL}:{self.remote_port}', host])
                if tunnel is None:
                    return
            else:
                model = self.env.get('HANNI_LAYA_MODEL_PATH', '').strip()
                if not model:
                    raise ValueError('Set HANNI_LAYA_MODEL_PATH to a local Laya checkpoint')
                # When already running, leave the existing service alone.
                if not default_token_path().is_file() or not self._healthy(self._read_token()):
                    self._spawn([sys.executable, '-m', 'hanni.laya.server',
                                 '--model', model, '--port', str(self.port)])

            # A tunnel may be ready before the remote service. Read the token
            # without printing it, then check the authenticated service.
            token = ''
            for attempt in range(6):
                if self._shutdown.is_set():
                    return
                try:
                    token = self._read_token()
                    if len(token) >= 32 and self._healthy(token):
                        break
                except (OSError, ValueError, subprocess.SubprocessError):
                    pass
                self._shutdown.wait(0.5)
            else:
                if self.mode != 'remote-ssh':
                    raise RuntimeError('Local Laya service did not become healthy')
                # The installed older sidecar is supported on Wonyoung. The
                # command is configurable to allow a public repo installation.
                ssh, host = self._ssh()
                remote_command = self.env.get('HANNI_LAYA_REMOTE_COMMAND', _REMOTE_COMMAND)
                if not remote_command.strip():
                    raise ValueError('Remote Laya command is empty')
                self._spawn([*ssh, '-T', host, remote_command])
                for attempt in range(35):
                    if self._shutdown.is_set():
                        return
                    try:
                        token = self._read_token()
                        if len(token) >= 32 and self._healthy(token):
                            break
                    except (OSError, ValueError, subprocess.SubprocessError):
                        pass
                    self._shutdown.wait(0.5)
                else:
                    raise RuntimeError('Remote Laya shadow service was not healthy')

            if not self._shutdown.is_set():
                self._client = ShadowClient(enabled=True, url=self._url, token=token, timeout_s=1.5)
                self.status = 'shadow connected'
                print('Laya shadow: connected (observe-only).', flush=True)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            # No tokens, utterances, or remote command values are ever logged.
            self.status = 'unavailable (' + type(exc).__name__ + ')'
            print('Laya shadow: unavailable; HANNI continues normally.', flush=True)
            self._stop_processes()

    def observe(self, utterance):
        """Never block the assistant and never return a model prediction."""
        client = self._client
        if self._shutdown.is_set() or client is None or not isinstance(utterance, str):
            return False
        from hanni.memory.privacy import SensitiveMemoryError, validate_memory_text
        try:
            # This is a conservative pre-send filter, not a security guarantee.
            sanitized = validate_memory_text(utterance, max_chars=1200)
        except (SensitiveMemoryError, ValueError):
            return False
        return client.observe(utterance=sanitized)

    def _stop_processes(self):
        for process in reversed(self._processes):
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
            except (OSError, AttributeError, subprocess.SubprocessError):
                pass
        self._processes.clear()

    def close(self):
        self._shutdown.set()
        if self._client is not None:
            self._client.close()
            self._client = None
        self._stop_processes()


def current_manager():
    return _manager


def start_shadow_from_env():
    """Idempotent, safe to call from both dashboard and standalone CLI."""
    global _manager
    if not enabled():
        return None
    with _lock:
        if _manager is None:
            try:
                _manager = LayaShadowManager()
            except (ValueError, TypeError):
                return None
            atexit.register(_manager.close)
        _manager.start()
        return _manager


def stop_shadow():
    global _manager
    with _lock:
        if _manager is not None:
            _manager.close()
            _manager = None
    from .runtime import stop_advisory
    stop_advisory()
