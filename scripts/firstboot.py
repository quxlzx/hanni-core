#!/usr/bin/env python3
"""First boot of a portable HANNI stick ON THE HOST MACHINE.

Run from the stick root:  python3 firstboot.py [--serve] [--port 8300]

1. probe hardware (RAM/cores/GPU)
2. pick a runnable llama.cpp binary (SIGILL fallback chain)
3. 30-second micro-bench (pp256/tg64) of the best fitting model candidate
4. decide tier with measured truth overriding specs (hanni.native.probe)
5. write hanni-core/config/models.fleet.local.yaml
6. --serve: start llama-server in the background and print the bridge command
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# On a stick firstboot.py sits at the root; in the repo it lives in scripts/.
_here = Path(__file__).resolve().parent
STICK = _here if (_here / "models").is_dir() else _here.parent
CORE = next((c for c in (STICK / "hanni-core", STICK, STICK.parent)
               if (c / "src" / "hanni").is_dir()), STICK / "hanni-core")
for _src in (CORE / "src",):
    if (_src / "hanni").is_dir():
        sys.path.insert(0, str(_src))
        break

from hanni.native.probe import Facts, decide, probe  # noqa: E402

MODEL_FOR_TIER = {"pocket": "MiniCPM5-2B-Q4_K_M.gguf",
                  "small": "K2-Horizon-4B-Q4_K_M.gguf",
                  "large": "K2-Horizon-7B-Q4_K_M.gguf"}
MODEL_GB = {"MiniCPM5-2B-Q4_K_M.gguf": 1.6, "K2-Horizon-4B-Q4_K_M.gguf": 3.2,
            "K2-Horizon-7B-Q4_K_M.gguf": 5.6}


def stick_exe(bin_dir: Path, name: str) -> Path:
    cand = bin_dir / name
    if not cand.is_file() and os.name == "nt" and (bin_dir / (name + ".exe")).is_file():
        return bin_dir / (name + ".exe")
    return cand


def detach_kwargs() -> dict:
    if os.name == "nt":
        return {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def pick_binary(facts: Facts) -> Path | None:
    from hanni.native.acceleration import devices
    from hanni.models.bundled_runtime import runtime_directories
    cpu_fallback = None
    for directory in runtime_directories(STICK):
        cand = stick_exe(directory, "llama-bench")
        if not cand.is_file() or not stick_exe(cand.parent, 'llama-server').is_file():
            continue
        try:
            done = subprocess.run([str(cand), "--version"], capture_output=True, timeout=10,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                  env={**os.environ, "LD_LIBRARY_PATH": str(cand.parent)})
            if done.returncode in (0,):
                if devices(cand.parent):
                    return cand.parent
                if cpu_fallback is None or (not cpu_fallback.name.endswith('x86_64') and directory.name.endswith('x86_64')):
                    cpu_fallback = cand.parent
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            continue
    return cpu_fallback


def candidates(facts: Facts, models_dir: Path | None = None) -> list[str]:
    """Largest-first model candidates that plausibly fit in RAM.
    GPU offload is decided by llama.cpp's automatic VRAM fitting."""
    models_dir = models_dir or STICK / "models"
    out = []
    for tier in ("large", "small", "pocket"):
        model = MODEL_FOR_TIER[tier]
        if facts.ram_gb >= MODEL_GB[model] + 2 and (models_dir / model).is_file():
            out.append(model)
    return out


def micro_bench(bin_dir: Path, model: str) -> float:
    from hanni.native.acceleration import flags
    cmd = [str(stick_exe(bin_dir, "llama-bench")), "-m", str(STICK / "models" / model),
           "-p", "256", "-n", "64", "-r", "1", "-o", "json", *flags(bin_dir, benchmark=True)]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                          env={**os.environ, "LD_LIBRARY_PATH": str(bin_dir)})
    if done.returncode:
        raise RuntimeError('The local model benchmark failed; check available GPU/system memory.')
    for row in json.loads(done.stdout or "[]"):
        if row.get("n_gen"):
            return float(row["avg_ts"])
    return 0.0


_CORES = None
_owned_job = None
_supervised = False
_desktop_alive = None


def guard_desktop():
    if _desktop_alive is not None and not _desktop_alive():
        raise RuntimeError('The owner application closed; stopping its HANNI session.')


def facts_cores() -> int:
    global _CORES
    if _CORES is None:
        _CORES = os.cpu_count() or 4
    return _CORES


def ensure_deps(dashboard=False) -> None:
    """Install into the selected interpreter, including the dashboard's full deps."""
    import importlib.util
    if dashboard and sys.version_info < (3, 12):
        raise RuntimeError("Hanni OS requires Python 3.12+. Rebuild .venv with SETUP_HANNI.cmd.")
    required = ["dotenv", "httpx", "jsonschema", "psutil", "yaml", "tzdata"]
    if dashboard:
        required += ["mcp", "httpx2", "httpcore2", "huggingface_hub", "keyring", "google.auth", "pypdf", "PIL", "openpyxl", "xlrd", "defusedxml", "docx", "pptx"]
    missing = []
    for name in required:
        try:
            if importlib.util.find_spec(name) is None:
                missing.append(name)
        except ModuleNotFoundError:
            missing.append(name)
    if not missing:
        return
    print("Installing missing dependencies: " + ", ".join(missing), flush=True)
    command = [sys.executable, "-m", "pip", "install"]
    wheels = STICK / ("wheels-win" if os.name == "nt" else "wheels")
    if wheels.is_dir():
        command += ["--find-links", str(wheels)]
    command += (["-e", str(CORE)] if dashboard else
                ["python-dotenv", "jsonschema", "httpx", "psutil", "pyyaml", "tzdata"])
    subprocess.run(command, check=True)


def port_in_use(port):
    import socket
    with socket.socket() as sock:
        sock.settimeout(.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def get_json(url, timeout=3, token=None):
    import httpx
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        response = client.get(url, headers={"Authorization": "Bearer " + (token if token is not None else os.environ.get("HANNI_MODEL_API_KEY", "local"))})
        response.raise_for_status()
        return response.json()


def remote_model(endpoint, wanted=None, *, api_key=None):
    models = get_json(endpoint + "/models", token=api_key).get("data", [])
    ids = [m["id"] for m in models if isinstance(m, dict) and isinstance(m.get("id"), str)]
    if wanted:
        if wanted not in ids:
            raise ValueError(f"Model {wanted!r} is not advertised by {endpoint}/models; available: {', '.join(ids)}")
        return wanted
    if len(ids) != 1:
        raise ValueError("Use --brain-model to select one of the server's model IDs: " + ", ".join(ids))
    return ids[0]


def write_configs(endpoint, model_id, chosen, port, context=65536, *, source=None, api_key_ref=None):
    import re
    import yaml
    native = {"idle_unload_seconds": 0, "ram_reserve_mb": 0, "vram_reserve_mb": 0,
        "critical_ram_percent": 95, "models": [{"id": "stick-brain", "role": "supervisor",
        "api_model": model_id, "endpoint": endpoint, "keep_loaded": True,
        "context_length": context, "native_max_tokens": 1200, "native_temperature": .6,
        "kv_key_type": "q8_0", "kv_value_type": "q8_0",
        "native_reasoning_budget": 512, "model_file": str(chosen) if chosen else model_id}]}
    native['models'][0].update(source=source or ('local' if chosen else 'api'), api_key_ref=api_key_ref)
    match = re.search(r"(Q\d[\w]*)", str(chosen or ""))
    native["models"][0]["quantization"] = match.group(1) if match else "Not reported"
    state = STICK / "state"
    state.mkdir(parents=True, exist_ok=True)
    native_path = state / "models.native.yaml"
    native_path.parent.mkdir(parents=True, exist_ok=True)
    native_path.write_text(yaml.safe_dump(native), encoding="utf-8")
    # Core remains loopback-only. Remote status is projected by the authenticated
    # bridge rather than relaxing the legacy controller's endpoint policy.
    dash = {**native, "models": [{k: v for k, v in native["models"][0].items()
                                 if not k.startswith("native_") and k not in {'source', 'api_key_ref'}}]}
    from urllib.parse import urlsplit
    dash_endpoint = endpoint if urlsplit(endpoint).hostname in {'127.0.0.1', 'localhost', '::1'} else f"http://127.0.0.1:{port + 1}/v1"
    dash["models"][0].update(backend="llama.cpp", endpoint=dash_endpoint)
    dash_path = state / "models.dashboard.yaml"
    dash_path.write_text(yaml.safe_dump(dash), encoding="utf-8")
    return state, native_path, dash_path, native["models"][0]


def spawn(command, log_name, env):
    global _owned_job
    guard_desktop()
    if _supervised and os.name == 'nt' and _owned_job is None:
        from hanni.native.lifecycle import WindowsJob
        _owned_job = WindowsJob()
    with (STICK / log_name).open("a", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=CORE, env=env, stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, **detach_kwargs())
    if _owned_job is not None:
        try:
            _owned_job.assign(process)
        except BaseException:
            process.terminate()
            process.wait(timeout=5)
            raise
    return process


def stop_owned(process):
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, timeout=10,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    else:
        import signal
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def wait_ready(url, process, timeout, *, predicate=lambda result: True, token=None):
    import time
    deadline = time.monotonic() + timeout
    detail = "Service has not accepted a connection."
    while time.monotonic() < deadline:
        guard_desktop()
        if process.poll() is not None:
            raise RuntimeError(f"Service exited with code {process.returncode} while starting {url}; inspect its log.")
        try:
            result = get_json(url, token=token)
            if predicate(result):
                return result
            detail = str(result.get("detail") or result.get("state") or "Service is not ready.")
        except Exception as exc:
            detail = str(exc)
        time.sleep(.25)
    raise RuntimeError(f"Startup timed out at {url}: {detail}")


def supervise(children, restart_model=None, poll_control=None):
    import time
    restarts = 0
    while True:
        if _desktop_alive is not None and not _desktop_alive():
            print('Owner application closed; stopping owned services.', flush=True)
            return 0
        if poll_control:
            poll_control()
        for name, child in list(children.items()):
            if child.poll() is None:
                continue
            if name == "dashboard" and child.returncode == 0:
                print("Stop requested from Hanni OS; closing owned services.", flush=True)
                return 0
            if name == "model" and restart_model and restarts < 3:
                restarts += 1
                print(f"Model exited; restarting ({restarts}/3).", flush=True)
                children[name] = restart_model()
                continue
            raise RuntimeError(f"{name} exited with code {child.returncode}; inspect {name}.log.")
        time.sleep(.5)


def model_command_for(bin_dir, chosen, port, context):
    from hanni.native.acceleration import flags
    return [str(stick_exe(bin_dir, 'llama-server')), '-m', str(chosen), '-c', str(context),
            '--parallel', '1', '--jinja', '--host', '127.0.0.1', '--port', str(port + 100),
            '--alias', 'stick-brain', *flags(bin_dir, context=context)]


def apply_model_change(control, children, runtime, *, port, timeout, base_env):
    """Swap only the owned model. Bridge workers read the native config per task."""
    from hanni.native.model_settings import atomic_json, model_config
    from hanni.native.provider import NativeClient
    request = control.change()
    if not request or request.get('status') != 'pending':
        return
    # The bridge serializes this read with submission. Once the mailbox says
    # pending, later submissions cannot race this last check.
    from hanni.hermes.state import TERMINAL
    try:
        tasks = get_json(f'http://127.0.0.1:{port + 1}/tasks',
                         token=(control.root / 'bridge.token').read_text().strip())
        if any(task['state'] not in TERMINAL for task in tasks.get('tasks', [])):
            control.mark(request, 'failed', 'Finish or cancel active tasks before changing models. The current model was retained.')
            return
    except Exception:
        control.mark(request, 'failed', 'The agent could not confirm that all tasks finished. The current model was retained.')
        return
    previous = control.active()
    selected = request['selection']
    old_command = runtime.get('command')
    old_native = (control.root / 'models.native.yaml').read_bytes()
    old_dashboard = (control.root / 'models.dashboard.yaml').read_bytes()
    control.mark(request, 'applying', 'Loading the selected model…')
    replacement = None
    stopped_old = False
    try:
        if selected['source'] == 'local':
            if 'model' not in children and port_in_use(port + 100):
                raise RuntimeError('The local model port belongs to another server. Stop that server before loading a local model.')
            chosen = control.models_dir / selected['local_model']
            if not chosen.is_file():
                raise RuntimeError('The selected local model file is no longer available.')
            bin_dir = pick_binary(probe(str(STICK)))
            if bin_dir is None:
                raise RuntimeError('No runnable local model server is installed.')
            command = model_command_for(bin_dir, chosen, port, selected['context'])
            stop_owned(children.pop('model', None))
            stopped_old = True
            replacement = spawn(command, 'llama-server.log', base_env)
            selected = {**selected, 'endpoint': f'http://127.0.0.1:{port + 100}/v1', 'api_model': 'stick-brain'}
            wait_ready(selected['endpoint'] + '/models', replacement, timeout,
                       predicate=lambda result: any(m.get('id') == 'stick-brain' for m in result.get('data', [])))
        else:
            chosen, command = None, None
        status = NativeClient(model_config(selected)).status()
        if not status['ready']:
            raise RuntimeError(status.get('detail') or 'The selected model is unavailable.')
        if selected['source'] == 'local' and (not status.get('context_verified') or status['context'] < selected['context']):
            raise RuntimeError('The local server did not load the requested context size.')
        write_configs(selected['endpoint'], selected['api_model'], chosen, port, selected['context'],
                      source=selected['source'], api_key_ref=selected.get('api_key_ref'))
        if selected['source'] == 'api':
            stop_owned(children.pop('model', None))
            stopped_old = True
        elif replacement:
            children['model'] = replacement
        runtime['command'] = command
        atomic_json(control.root / 'model-selection.json', selected)
        control.mark(request, 'ready', 'Model connected. New messages use this model.')
    except Exception:
        # Neither model errors nor credentials are copied into persistent logs.
        stop_owned(replacement)
        (control.root / 'models.native.yaml').write_bytes(old_native)
        (control.root / 'models.dashboard.yaml').write_bytes(old_dashboard)
        runtime['command'] = old_command
        restored = not stopped_old or old_command is None
        if stopped_old and old_command:
            try:
                restored_model = spawn(old_command, 'llama-server.log', base_env)
                children['model'] = restored_model
                wait_ready(previous['endpoint'] + '/models', restored_model, timeout)
                restored = True
            except Exception:
                restored = False
        control.mark(request, 'failed', 'Could not load the model with these settings. ' +
                     ('The previous model was retained. Try a smaller context or check the endpoint and model server log.' if restored else
                      'The previous model could not be restored. Restart HANNI and inspect the model server log.'))


def main(argv=None) -> int:
    global _supervised, _owned_job, _desktop_alive
    import time
    from hanni.native.provider import NativeClient, normalize_endpoint
    parser = argparse.ArgumentParser(description="Start HANNI: dashboard :8311, agent :8312, model :8411.")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--wait", action="store_true", help="supervise owned services and stop them on exit")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--ui", action="store_true")
    parser.add_argument('--desktop-owner-pid', type=int, help='stop this owned stack when its desktop app exits')
    parser.add_argument('--ready-file', type=Path, help='publish nonsecret desktop startup ownership')
    parser.add_argument("--port", type=int, default=8311)
    parser.add_argument("--secure", action="store_true", help="require credentials and per-action approvals")
    parser.add_argument("--tier", choices=("auto", "2b", "3.7b", "7b"), default="auto")
    parser.add_argument("--model", metavar="FILE.gguf")
    parser.add_argument('--context', type=int, help='context tokens: 65536..262144 (default 65536)')
    parser.add_argument("--brain-url", metavar="URL", help="use an existing OpenAI-compatible model server")
    parser.add_argument("--brain-model", help="exact remote model ID from /v1/models")
    parser.add_argument("--reuse-model", action="store_true", help="reuse the model on port+100 without owning or stopping it")
    parser.add_argument("--no-cron", action="store_true")
    parser.add_argument("--startup-timeout", type=float, default=180)
    args = parser.parse_args(argv)
    if args.desktop_owner_pid is not None and (args.desktop_owner_pid <= 0 or not (args.serve and args.wait and args.ui)):
        parser.error('desktop-owner-pid requires a positive PID and --serve --wait --ui')
    if args.ready_file is not None and not args.desktop_owner_pid:
        parser.error('ready-file requires a desktop owner')
    _desktop_alive = None
    if args.desktop_owner_pid:
        from hanni.dashboard.launcher import desktop_owner_alive
        _desktop_alive = desktop_owner_alive(args.desktop_owner_pid)
    from hanni.native.model_settings import ModelSettings, context_size, atomic_json
    control = ModelSettings(STICK / 'state', STICK / 'models')
    saved = control.active()
    explicit_model = args.model or args.brain_url or args.reuse_model or args.tier != 'auto'
    if saved and not explicit_model:
        if saved['source'] == 'api':
            args.brain_url, args.brain_model = saved['endpoint'], saved['api_model']
        else:
            args.model = saved['local_model']
    try:
        args.context = context_size(args.context if args.context is not None else (saved['context'] if saved and not explicit_model else 65536))
    except ValueError as exc:
        parser.error(str(exc))
    _supervised = args.wait
    if not 1 <= args.port <= 65435 or args.startup_timeout <= 0:
        parser.error("port must be 1..65435 and startup-timeout must be positive")
    if args.brain_url and (args.reuse_model or args.model or args.tier != "auto"):
        parser.error("remote brain selection cannot be combined with local model/tier selection")
    children, leave_running = {}, False
    try:
        guard_desktop()
        if args.serve:
            ensure_deps(dashboard=args.ui)
            if args.ui and port_in_use(args.port):
                existing = get_json(f"http://127.0.0.1:{args.port}/api/chat")
                if not isinstance(existing, dict) or "epoch" not in existing or "ready" not in existing:
                    raise RuntimeError(f"Port {args.port} is occupied by another application.")
                print(f"HANNI is already running at http://localhost:{args.port}")
                if not args.no_browser:
                    import webbrowser
                    webbrowser.open(f"http://localhost:{args.port}")
                return 0
            if port_in_use(args.port + 1):
                raise RuntimeError(f"Agent port {args.port + 1} is occupied. Stop the previous HANNI launcher first.")
            if not (args.brain_url or args.reuse_model) and port_in_use(args.port + 100):
                raise RuntimeError(f"A model is already running on :{args.port + 100}. Use --reuse-model to reconnect without loading another copy.")
        chosen, measured, bin_dir = None, None, None
        endpoint = normalize_endpoint(args.brain_url or f"http://127.0.0.1:{args.port + 100}/v1")
        api_key_ref = saved.get('api_key_ref') if saved and endpoint == saved.get('endpoint') and args.brain_url else None
        model_id = "stick-brain"
        if args.brain_url or args.reuse_model:
            from hanni.native.model_settings import stored_api_key
            model_id = remote_model(endpoint, args.brain_model or ("stick-brain" if args.reuse_model else None),
                                    api_key=stored_api_key(api_key_ref) if api_key_ref else None)
            if args.reuse_model:
                props = get_json(endpoint.removesuffix("/v1") + "/props")
                chosen = Path(props["model_path"])
                if args.model and Path(args.model).name != chosen.name:
                    raise ValueError("The running model differs from --model; stop it before switching.")
                if args.tier != "auto" and chosen.name != MODEL_FOR_TIER[{"2b":"pocket", "3.7b":"small", "7b":"large"}[args.tier]]:
                    raise ValueError("The running model differs from --tier; stop it before switching.")
            print(f"Using existing model {model_id!r} at {endpoint}", flush=True)
        else:
            facts = probe(str(STICK))
            bin_dir = pick_binary(facts)
            if bin_dir is None:
                raise RuntimeError("No runnable llama.cpp runtime. Run SETUP_HANNI.cmd or rebuild the desktop application to restore its bundled runtime.")
            if args.model:
                pool = [str(Path(args.model))]
            elif args.tier != "auto":
                pool = [MODEL_FOR_TIER[{"2b":"pocket", "3.7b":"small", "7b":"large"}[args.tier]]]
            else:
                pool = candidates(facts)
            slow_fallback = None
            for model in pool:
                path = (STICK / "models" / model).resolve()
                if not path.is_file():
                    raise ValueError(f"Model file does not exist: {path}. Run scripts/get_models.py first.")
                try:
                    tps = micro_bench(bin_dir, model)
                except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired):
                    if args.model or args.tier != 'auto':
                        raise
                    print(f'bench {path.name}: unavailable; trying a smaller model.', flush=True)
                    continue
                print(f"bench {path.name}: {tps:.1f} tok/s", flush=True)
                if tps > 0:
                    slow_fallback = (path, tps)
                if args.model or args.tier != "auto" or tps >= 15:
                    chosen, measured = path, tps
                    break
                if tps >= 8 and (measured is None or tps > measured):
                    chosen, measured = path, tps
            if chosen is None and slow_fallback:
                chosen, measured = slow_fallback
                print('Using the smallest runnable model; this machine is below the preferred speed floor.', flush=True)
            if chosen is None:
                raise RuntimeError("No local model could run. Check available RAM/VRAM, select --tier explicitly, or use --brain-url.")
        if chosen:
            from hanni.native.gguf_context import context_limit
            trained_context = context_limit(chosen)
            if trained_context and args.context > trained_context:
                raise ValueError(f'{chosen.name} supports up to {trained_context // 1024}K context. Choose K2 for 256K.')
        state, native_path, dash_path, model_cfg = write_configs(endpoint, model_id, chosen, args.port, args.context,
            source='local' if chosen else 'api', api_key_ref=api_key_ref)
        print(f"Selected: {chosen or model_id}" + (f" ({measured:.1f} tok/s)" if measured is not None else ""), flush=True)
        if not args.serve:
            print("Dry run; add --serve --wait --ui to start HANNI.")
            return 0
        base_env = {**os.environ, "PYTHONPATH": str(CORE / "src"), "PYTHONUTF8": "1",
            'HANNI_MODEL_STATE': str(state), 'HANNI_MODELS_DIR': str(STICK / 'models'),
            'HANNI_MODEL_CONTROL': '1' if args.wait else '0'}
        if args.ui:
            base_env['HANNI_DASHBOARD_URL'] = f'http://127.0.0.1:{args.port}'
        model_command = None
        if not (args.brain_url or args.reuse_model):
            model_command = model_command_for(bin_dir, chosen, args.port, args.context)
            children["model"] = spawn(model_command, "llama-server.log", base_env)
            wait_ready(endpoint + "/models", children["model"], args.startup_timeout,
                       predicate=lambda d: any(m.get("id") == model_id for m in d.get("data", [])))
        status = NativeClient(model_cfg).status()
        if not status["ready"]:
            raise RuntimeError(status.get("detail") or "Model did not become ready.")
        if model_command and (not status.get('context_verified') or status['context'] < args.context):
            raise RuntimeError('The local server did not load the requested context size.')
        selection = {'source': 'local' if chosen else 'api', 'context': args.context,
                     'endpoint': endpoint, 'api_model': model_id}
        if chosen:
            selection['local_model'] = chosen.name
        if api_key_ref:
            selection['api_key_ref'] = api_key_ref
        atomic_json(state / 'model-selection.json', selection)
        if control.pending():
            control.mark(control.change(), 'failed', 'The previous model change was interrupted. HANNI restarted with the saved model.')
        token = state / "bridge.token"
        if not token.exists():
            token.write_text(os.urandom(32).hex(), encoding="utf-8")
        memory = STICK / "soul" / "memory.sqlite3"
        if memory.is_file() and not (state / "memory.sqlite3").exists():
            shutil.copy2(memory, state / "memory.sqlite3")
        bridge_env = {**base_env, "HANNI_MODEL_CONFIG": str(native_path), "HANNI_MODEL_ID": "stick-brain",
            "HANNI_SOUL": str(STICK / "soul" / "SOUL.md"), "HANNI_SKILLS_DIR": str(STICK / "soul" / "skills"),
            "HANNI_BRIDGE_OPEN": "0" if args.secure else "1", "HANNI_AUTO_APPROVE": "0" if args.secure else "1"}
        children["bridge"] = spawn([sys.executable, "-m", "hanni.hermes.service", "--root", str(state),
            "--hermes-config", str(CORE / "config" / "hanni.yaml"), "--token-file", str(token),
            "--brain", "native", "--port", str(args.port + 1)], "bridge.log", bridge_env)
        wait_ready(f"http://127.0.0.1:{args.port + 1}/health", children["bridge"], args.startup_timeout,
                   predicate=lambda d: d.get("ready") is True, token=token.read_text().strip())
        if not args.no_cron:
            children["cron"] = spawn([sys.executable, "-m", "hanni.native.cron", "--root", str(state), "daemon"], "cron.log", base_env)
        if args.ui:
            dashboard_env = {**bridge_env, "HANNI_MODEL_CONFIG": str(dash_path),
                "HANNI_BRIDGE_URL": f"http://127.0.0.1:{args.port + 1}", "HANNI_BRIDGE_TOKEN_FILE": str(token),
                "HANNI_CRON_ROOT": str(state)}
            dashboard_ready_file = args.ready_file.with_suffix('.dashboard.json') if args.ready_file else None
            ready_arguments = ['--ready-file', str(dashboard_ready_file)] if dashboard_ready_file else []
            children["dashboard"] = spawn([sys.executable, "-m", "hanni.dashboard.launcher", "--dashboard-only",
                "--port", str(args.port), "--no-browser", "--config-dir", str(CORE / "config"),
                "--data-dir", str(state), *ready_arguments], "dashboard.log", dashboard_env)
            def dashboard_ready(data):
                if dashboard_ready_file:
                    if not dashboard_ready_file.is_file(): return False
                    ready = json.loads(dashboard_ready_file.read_text(encoding='utf-8'))
                    if (children['dashboard'].pid not in {ready.get('pid'), ready.get('parent_pid')}
                            or ready.get('url') != f'http://127.0.0.1:{args.port}'
                            or data.get('epoch') != ready.get('epoch')):
                        raise RuntimeError('Dashboard ownership did not match this application launch.')
                return data.get('ready') is True
            dashboard_state = wait_ready(f"http://127.0.0.1:{args.port}/api/chat", children["dashboard"], args.startup_timeout,
                                         predicate=dashboard_ready)
        url = f"http://localhost:{args.port if args.ui else args.port + 1}"
        print(f"HANNI ready: {url}\nAgent API: :{args.port + 1}; model API: {endpoint}", flush=True)
        (state / 'launcher.json').write_text(json.dumps({'pid': os.getpid(), 'url': url,
            'model_endpoint': endpoint, 'model_id': model_id, 'model_file': str(chosen or model_id),
            'children': {name: child.pid for name, child in children.items()}}, indent=2), encoding='utf-8')
        if args.ready_file:
            atomic_json(args.ready_file, {'pid': os.getpid(), 'parent_pid': os.getppid(),
                                         'url': f'http://127.0.0.1:{args.port}', 'epoch': dashboard_state['epoch']})
        if not args.no_browser:
            import webbrowser
            webbrowser.open(url)
        if args.wait:
            runtime = {'command': model_command}
            def poll_model_control():
                apply_model_change(control, children, runtime, port=args.port, timeout=args.startup_timeout, base_env=base_env)
                active = control.active()
                signature = (tuple((name, child.pid) for name, child in children.items()), json.dumps(active, sort_keys=True))
                if runtime.get('metadata_signature') == signature:
                    return
                runtime['metadata_signature'] = signature
                atomic_json(state / 'launcher.json', {'pid': os.getpid(), 'url': url,
                    'model_endpoint': active['endpoint'], 'model_id': active['api_model'],
                    'model_file': str(STICK / 'models' / active['local_model']) if active['source'] == 'local' else active['api_model'],
                    'context': active['context'], 'children': {name: child.pid for name, child in children.items()}})
            return supervise(children, lambda: spawn(runtime['command'], 'llama-server.log', base_env), poll_model_control)
        leave_running = True
        return 0
    except KeyboardInterrupt:
        print("HANNI stopped.")
        return 0
    except Exception as exc:
        print(f"HANNI startup failed: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        if not leave_running:
            try:
                for child in reversed(list(children.values())):
                    stop_owned(child)
            finally:
                if _owned_job is not None:
                    _owned_job.close()
                    _owned_job = None
                if args.ready_file:
                    args.ready_file.with_suffix('.dashboard.json').unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
