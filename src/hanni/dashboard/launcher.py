"""Own the local dashboard and model process; run the original CLI voice loop."""
from __future__ import annotations

import argparse
import errno
import json
import os
from pathlib import Path
import shutil
import socket
import re
import subprocess
import threading
import time
from urllib.parse import urlsplit
import webbrowser

from dotenv import load_dotenv

from hanni.config.loader import load_config
from hanni.core.activity import activity
from hanni.dashboard.server import DashboardServer, Telemetry
from hanni.models.registry import create_client


from hanni.models.runtime import model_command


def launch_desktop(url, *, repo_root=None, env=None):
    """Open only the desktop client at this server's actual bound origin.

    The launcher watches this child's lifetime and closes its owned session
    when the desktop exits. Attached clients cannot stop unrelated sessions.
    """
    endpoint = urlsplit(url)
    if (endpoint.scheme != 'http' or endpoint.hostname != '127.0.0.1'
            or endpoint.username is not None or endpoint.password is not None
            or not endpoint.port or endpoint.path not in {'', '/'}
            or endpoint.query or endpoint.fragment):
        raise ValueError('The desktop client requires this dashboard\'s loopback origin.')
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]
    settings = os.environ if env is None else env
    configured = settings.get('HANNI_DESKTOP_EXE', '').strip()
    executable = Path(configured).expanduser() if configured else root/'dist'/'HANNI OS'/'HANNI OS.exe'
    if executable.is_file() and executable.suffix.lower() == '.exe':
        command = [str(executable.resolve())]
    elif not configured and (root/'build'/'desktop-venv'/'Scripts'/'pythonw.exe').is_file() and (root/'desktop'/'main.py').is_file():
        command = [str(root/'build'/'desktop-venv'/'Scripts'/'pythonw.exe'), str(root/'desktop'/'main.py')]
    else:
        raise RuntimeError('The Windows app is unavailable. Build it with scripts\\build_desktop.ps1, or configure HANNI_DESKTOP_EXE.')
    command += ['--url', url, '--attach-only', '--repo-root', str(root.resolve())]
    return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def write_desktop_ready(path, url, chat):
    """Publish nonsecret child identity for the native client's owned monitor.

    parent_pid handles Windows' virtual-environment Python redirector. A chat
    epoch identifies this monitor session; no request token is written to disk.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps({'pid': os.getpid(), 'parent_pid': os.getppid(),
                                      'url': url, 'epoch': chat.epoch}), encoding='utf-8')
    temporary.replace(path)


def stop_owned(process):
    if process is None or process.poll() is not None:
        return
    # llama-server is launched directly (no shell process or unrelated server).
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def watch_desktop_exit(alive, shutdown_event, chat, *, interval=.2):
    """Use the existing graceful cleanup, never kill shared model servers."""
    while not shutdown_event.is_set():
        if not alive():
            try:
                chat.request_shutdown()
            finally:
                shutdown_event.set()
            return
        shutdown_event.wait(interval)


def desktop_owner_alive(pid):
    """Pin process creation time so a reused PID cannot extend ownership."""
    import psutil
    try:
        owner = psutil.Process(pid)
        created = owner.create_time()
    except psutil.Error:
        return lambda: False

    def alive():
        try:
            return owner.is_running() and owner.create_time() == created
        except psutil.Error:
            return False
    return alive


def start_model(config, *, timeout=900, model_file=None, model_id=None, command=None, shutdown_event=None):
    from hanni.models.registry import model_spec
    spec = model_spec(config, model_id)
    endpoint = urlsplit(spec.endpoint)
    try:
        with socket.create_connection((endpoint.hostname, endpoint.port or 80), timeout=0.5):
            raise RuntimeError('Model port is occupied. Stop that server or use --reuse-model after verifying it serves the configured HANNI model.')
    except OSError:
        pass
    routing_path = (config.paths.data_dir/'gpu-routing.json'
                    if spec.id == config.models.supervisor.id else None)
    command = command if command is not None else model_command(
        spec, model_file, reserve_mb=config.models.vram_reserve_mb, routing_path=routing_path)
    if shutdown_event is not None and shutdown_event.is_set():
        raise RuntimeError('Shutdown requested before model startup')
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    log_path = config.paths.data_dir / ('dashboard-model.log' if not model_id else f'dashboard-{spec.id}.log')
    with log_path.open('w', encoding='utf-8') as log:
        log.write('HANNI launch: ' + subprocess.list2cmdline(command) + '\n')
        log.flush()
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print(f'Loading {spec.model_file}. First start downloads uncached weights. Progress: {log_path}', flush=True)
    if '--device' in command:
        print(f'{spec.id}: llama.cpp device {command[command.index("--device")+1]}', flush=True)
    client = create_client(config, model_id)
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            if shutdown_event is not None and shutdown_event.is_set():
                raise RuntimeError('Shutdown requested during model startup')
            if process.poll() is not None:
                raise RuntimeError(f'Model exited with code {process.returncode}; see {log_path}')
            if client.health().ok:
                if spec.gpu_layers and spec.gpu_selection in {'most_vram', 'smallest_8gb'}:
                    output = log_path.read_text(encoding='utf-8', errors='replace')
                    offloaded = re.search(r'offloaded\s+(\d+)/(\d+)\s+layers to GPU', output)
                    if not offloaded or int(offloaded[1]) <= 0:
                        raise RuntimeError(f'{spec.id}: GPU offload could not be verified; see {log_path}')
                    print(f'{spec.id}: verified {offloaded[1]}/{offloaded[2]} layers offloaded to GPU.', flush=True)
                return process
            if shutdown_event is None:
                time.sleep(1)
            else:
                shutdown_event.wait(1)
        raise RuntimeError(f'Model startup timed out; see {log_path}. Retry after checking the download/GPU settings.')
    except BaseException:
        stop_owned(process)
        raise


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--config-dir', type=Path, default=None)
    parser.add_argument('--data-dir', type=Path, default=None)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--desktop', action='store_true', help='open the native Windows client instead of a browser')
    parser.add_argument('--desktop-owner-pid', type=int, help='desktop process that launched this session; exit closes owned models')
    parser.add_argument('--ready-file', type=Path, help='native client-owned monitor readiness metadata; no credentials')
    parser.add_argument('--dashboard-only', action='store_true', help='monitor without starting a model or microphone')
    parser.add_argument('--workflow-only', action='store_true', help='run bounded workflows through the original controller without microphone or interactive input')
    parser.add_argument('--reuse-model', action='store_true', help='use an existing, user-verified HANNI model server; do not stop it on exit')
    parser.add_argument('--text', action='store_true', help='run the original keyboard session instead of voice')
    parser.add_argument('--device', default=None)
    parser.add_argument('--model-file', type=Path, default=None, help='use existing configured GGUF weights instead of the Hugging Face cache')
    parser.add_argument('--startup-timeout', type=float, default=900)
    args = parser.parse_args(argv)
    if args.dashboard_only and args.workflow_only:
        parser.error('choose dashboard-only or workflow-only')
    if not 1 <= args.port <= 65535 or args.startup_timeout <= 0:
        parser.error('port must be 1..65535 and startup-timeout must be positive')
    if args.desktop_owner_pid is not None and args.desktop_owner_pid <= 0:
        parser.error('desktop-owner-pid must be positive')
    if args.ready_file and not args.dashboard_only:
        parser.error('ready-file is only available for a client-owned dashboard-only monitor')
    return args


def main(argv=None):
    args = _parse_args(argv)
    args.desktop_alive = desktop_owner_alive(args.desktop_owner_pid) if args.desktop_owner_pid else None
    while True:
        restart = threading.Event()
        result = _run_launcher(args, restart)
        if not restart.is_set() or result != 0:
            return result
        # The existing desktop/browser reconnects to the same bound port.
        # Cleanup finishes before a new controller or owned model is started.
        args.desktop = False
        args.no_browser = True
        print('Restarting HANNI and its configured local models...', flush=True)


def _run_launcher(args, restart_event):
    load_dotenv(override=False)
    model_file = args.model_file or os.environ.get('HANNI_MODEL_FILE')
    process = server = telemetry = chat = manager = None
    shutdown_event = threading.Event()
    serving = None
    workflow_session = None
    try:
        config = load_config(args.config_dir, data_dir=args.data_dir)
        from hanni.models.manager import ModelManager, install as install_manager
        manager = ModelManager(config, startup_timeout=args.startup_timeout,
            model_files={config.models.supervisor.id:model_file} if model_file else {},
            health=lambda spec: create_client(config, spec.id).health().ok,
            shutdown_event=shutdown_event)
        install_manager(manager)
        manager.start()
        # Optional Laya sidecar and secure tunnel start asynchronously.
        from hanni.laya.manager import start_shadow_from_env
        shadow = start_shadow_from_env() if not args.dashboard_only else None
        if shadow is not None:
            print('Laya shadow mode requested; connecting in the background. It cannot change memories.', flush=True)
        from hanni.dashboard.chat import ChatHub, install
        config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        chat = ChatHub(None if os.environ.get('HANNI_CHAT_HISTORY', '').lower() == 'session'
                       else config.paths.data_dir / 'dashboard-chat.sqlite3')
        install(chat)
        telemetry = Telemetry(config)
        try:
            server = DashboardServer(args.port, telemetry, chat, shutdown_event=shutdown_event,
                                     restart_event=restart_event)
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE and getattr(exc, 'winerror', None) != 10048:
                raise
            server = DashboardServer(0, telemetry, chat, shutdown_event=shutdown_event,
                                     restart_event=restart_event)
            print(f'Dashboard port {args.port} is occupied; using {server.server_port}.', flush=True)
        serving = threading.Thread(target=server.serve_forever, name='hanni-dashboard', daemon=True)
        serving.start()
        telemetry.start()
        activity.enabled = not args.dashboard_only
        url = f'http://127.0.0.1:{server.server_port}'
        args.port = server.server_port
        if args.ready_file:
            write_desktop_ready(args.ready_file, url, chat)
        print(f'H.A.N.N.I. dashboard: {url}\nKeep this terminal open for confirmations. Ctrl+C stops this session.', flush=True)
        if args.desktop:
            desktop = launch_desktop(url)
            args.desktop_alive = lambda: desktop.poll() is None
        elif not args.no_browser:
            webbrowser.open(url)
        if args.desktop_alive is not None:
            threading.Thread(target=watch_desktop_exit,
                args=(args.desktop_alive, shutdown_event, chat),
                name='hanni-desktop-lifetime', daemon=True).start()
        if args.dashboard_only:
            shutdown_event.wait()
            return 0
        if args.reuse_model and not create_client(config).health().ok:
            raise RuntimeError('The existing HANNI model is not healthy. Start it or omit --reuse-model.')
        model_id = config.models.supervisor.id
        manager.ensure_loaded(model_id)
        if shutdown_event.is_set():
            return 0
        if args.workflow_only:
            from hanni.tools import build_default_registry
            from hanni.core.orchestrator import TextSession, system_prompt_for
            from hanni.cli import _wrap_mcp_session
            registry = build_default_registry(config, data_dir=config.paths.data_dir)
            client = create_client(config, model_id)
            base = TextSession(client, system_prompt=system_prompt_for(config.hanni.personality))
            workflow_session = _wrap_mcp_session(config, base, client=client, registry=registry)
            print('Workflow backend running. Exiting its owner desktop or pressing Ctrl+C stops this session.', flush=True)
            shutdown_event.wait()
            return 0
        # Same process: level-only observations reach the UI without IPC or storage.
        # Same main thread: CLI confirmations, Ctrl+C, relevance, barge-in and
        # emergency stop keep their established behavior.
        from hanni.cli import run
        command = ['text' if args.text else 'attend', '--model-id', model_id,
                   '--config-dir', str(config.paths.config_dir), '--data-dir', str(config.paths.data_dir)]
        if args.device and not args.text:
            command += ['--device', args.device]
        result = run(command, shutdown_event=shutdown_event)
        if result and not args.text and not shutdown_event.is_set():
            # A removed microphone or speech-model failure must not tear down
            # the webpage, workflow backend or owned inference server.
            print('Voice is unavailable. HANNI is staying online in keyboard mode; '
                  'use Restart HANNI after fixing the audio device.', flush=True)
            command = ['text', *command[1:]]
            if '--device' in command:
                position = command.index('--device')
                del command[position:position + 2]
            return run(command, shutdown_event=shutdown_event)
        return result
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        if shutdown_event.is_set():
            return 0
        print(f'Dashboard startup failed: {exc}', flush=True)
        return 1
    finally:
        shutdown_event.set()
        activity.enabled = False
        # Stop admissions and fence results before closing the model/controller.
        workflows = getattr(server, 'workflows', None)
        from hanni.dashboard.workflows import close_workflows_for_cleanup
        close_workflows_for_cleanup(workflows)
        if workflow_session is not None:
            from hanni.cli import _close_interactive_session
            _close_interactive_session(workflow_session)
        from hanni.laya.manager import stop_shadow
        stop_shadow()
        if chat:
            chat.close()
            from hanni.dashboard.chat import install
            install(None)
        try:
            if telemetry:
                telemetry.close()
            stop_owned(process)
            if manager:
                manager.close()
        finally:
            if server:
                if serving:
                    server.shutdown()
                    serving.join(timeout=3)
                server.server_close()
            if chat:
                chat.db.close()
            if manager:
                install_manager(None)
            if args.ready_file:
                try:
                    metadata = json.loads(args.ready_file.read_text(encoding='utf-8'))
                    if isinstance(metadata, dict) and metadata.get('pid') == os.getpid():
                        args.ready_file.unlink()
                except (OSError, ValueError):
                    pass


if __name__ == '__main__':
    raise SystemExit(main())
