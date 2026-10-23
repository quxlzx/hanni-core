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
    names = (("windows-vulkan", "windows-x86_64") if os.name == "nt"
             else ("linux-vulkan", "linux-x86_64"))
    for name in names:
        cand = stick_exe(STICK / "binaries" / name, "llama-bench")
        if not cand.is_file():
            continue
        try:
            done = subprocess.run([str(cand), "--version"], capture_output=True, timeout=10,
                                  env={**os.environ, "LD_LIBRARY_PATH": str(cand.parent)})
            if done.returncode in (0,):
                return cand.parent
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def candidates(facts: Facts, models_dir: Path | None = None) -> list[str]:
    """Largest-first model candidates that plausibly fit in RAM.
    GPU offload is decided by llama.cpp itself (-ngl 99 offloads what fits)."""
    models_dir = models_dir or STICK / "models"
    out = []
    for tier in ("large", "small", "pocket"):
        model = MODEL_FOR_TIER[tier]
        if facts.ram_gb >= MODEL_GB[model] + 2 and (models_dir / model).is_file():
            out.append(model)
    return out


def micro_bench(bin_dir: Path, model: str) -> float:
    cmd = [str(stick_exe(bin_dir, "llama-bench")), "-m", str(STICK / "models" / model),
           "-p", "256", "-n", "64", "-r", "1", "-ngl", "99", "-o", "json"]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                          env={**os.environ, "LD_LIBRARY_PATH": str(bin_dir)})
    for row in json.loads(done.stdout or "[]"):
        if row.get("n_gen"):
            return float(row["avg_ts"])
    return 0.0


_CORES = None


def facts_cores() -> int:
    global _CORES
    if _CORES is None:
        _CORES = os.cpu_count() or 4
    return _CORES


def ensure_deps() -> None:
    """Install the bridge's deps from the stick's offline wheels if missing."""
    try:
        import dotenv, httpx, jsonschema, psutil, yaml  # noqa: F401
        if os.name == "nt":
            import zoneinfo  # noqa: F401
            try:
                zoneinfo.ZoneInfo("America/New_York")
            except Exception:
                raise ImportError("tzdata missing")
        return
    except ImportError:
        pass
    wdir = STICK / ("wheels-win" if os.name == "nt" else "wheels")
    if not wdir.is_dir():
        # Repo mode: no bundled wheels — install from the index instead.
        online = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q",
             "dotenv", "jsonschema", "httpx", "psutil", "pyyaml", "tzdata"],
            capture_output=True, text=True)
        if online.returncode == 0:
            print("installed bridge deps from PyPI")
            return
        print("deps missing and PyPI install failed — run: pip install -e . "
              "(or: pip install jsonschema httpx psutil pyyaml)")
        print(online.stderr[-300:])
        sys.exit(3)
    # bootstrap pip if the host has none (ensurepip, then bundled get-pip.py)
    def has_pip():
        return subprocess.run([sys.executable, "-m", "pip", "--version"],
                              capture_output=True).returncode == 0
    if not has_pip():
        subprocess.run([sys.executable, "-m", "ensurepip", "--quiet"], capture_output=True)
    if not has_pip() and (wdir / "get-pip.py").is_file():
        for extra in (["--user"], ["--user", "--break-system-packages"], []):
            subprocess.run([sys.executable, str(wdir / "get-pip.py"), *extra, "-q"], capture_output=True)
            if has_pip():
                break
    base = [sys.executable, "-m", "pip", "install", "--no-index", "--find-links", str(wdir)]
    for extra in (["--user"], ["--user", "--break-system-packages"], ["--break-system-packages"], []):
        done = subprocess.run(base + extra + ["dotenv", "jsonschema", "httpx", "psutil", "pyyaml", "tzdata"],
                              capture_output=True, text=True)
        if done.returncode == 0:
            print("installed bridge deps from stick wheels")
            return
    # Bundled wheels didn't fit this interpreter — fall back to the index.
    online = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q",
         "dotenv", "jsonschema", "httpx", "psutil", "pyyaml", "tzdata"],
        capture_output=True, text=True)
    if online.returncode == 0:
        print("installed bridge deps from PyPI")
        return
    print("could not install deps:", done.stderr[-300:], online.stderr[-300:])
    sys.exit(3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--wait", action="store_true",
                        help="keep firstboot alive after serving (job-object hosts like sshd)")
    parser.add_argument("--no-browser", action="store_true",
                        help="skip auto-opening the front door in a browser")
    parser.add_argument("--ui", action="store_true",
                        help="also serve the full Hanni OS dashboard, wired to this brain")
    parser.add_argument("--port", type=int, default=8300)
    parser.add_argument("--secure", action="store_true",
                        help="keep the token wall and approval gates "
                             "(default is open, Hermes-like: tools just run)")
    parser.add_argument("--tier", choices=("auto", "2b", "3.7b", "7b"),
                        default="auto",
                        help="force a model tier instead of the auto cascade")
    parser.add_argument("--model", default=None, metavar="FILE.gguf",
                        help="use a specific GGUF from models/ (skips the cascade)")
    parser.add_argument("--brain-url", default=None, metavar="URL",
                        help="skip local models entirely and use a remote "
                             "OpenAI-compatible endpoint (…/v1)")
    parser.add_argument("--no-cron", action="store_true",
                        help="do not start the recurring-task (cron) daemon")
    args = parser.parse_args()
    if args.serve:
        # a stale HANNI on this port (or a zombie llama-server) poisons the
        # bench cascade — refuse loudly instead of measuring garbage.
        import socket as _sock
        for _p in (args.port, args.port + 1):
            _s = _sock.socket()
            try:
                _in_use = _s.connect_ex(("127.0.0.1", _p)) == 0
            finally:
                _s.close()
            if _in_use:
                sys.exit(f"Another HANNI is already serving on :{_p} — "
                         "close the other window first, then retry.")
        ensure_deps()

    facts = probe(str(STICK))

    chosen, measured, bin_dir = None, None, None
    if args.brain_url:
        print(f"remote brain mode: {args.brain_url} (no local model)")
    else:
        bin_dir = pick_binary(facts)
        if bin_dir is None:
            print("No runnable llama.cpp binary — see binaries/README.txt (build on first use).")
            sys.exit(1)
        if args.model:
            if not (STICK / "models" / args.model).is_file():
                sys.exit(f"models/{args.model} not found — put it there or run scripts/get_models.py")
            chosen = args.model
            measured = micro_bench(bin_dir, chosen)
            print(f"forced model {chosen}: {measured:.1f} tok/s decode")
        else:
            pool = candidates(facts)
            if args.tier != "auto":
                want = MODEL_FOR_TIER[{"2b": "pocket", "3.7b": "small",
                                       "7b": "large"}[args.tier]]
                if want not in pool:
                    sys.exit(f"tier {args.tier} ({want}) not available — "
                             "run scripts/get_models.py first")
                pool = [want]
            for model in pool:
                tps = micro_bench(bin_dir, model)
                print(f"bench {model}: {tps:.1f} tok/s decode")
                if args.tier != "auto":  # user chose: take it regardless
                    chosen, measured = model, tps
                    break
                if tps >= 15:  # real-agent floor for this model: take it
                    chosen, measured = model, tps
                    break
                if tps >= 8 and (measured is None or tps > measured):  # pocket-grade: keep the best
                    chosen, measured = model, tps
        if chosen is None:
            print("This host cannot host any tier locally. Pick one anyway with "
                  "--tier/--model, or use a remote brain: --brain-url URL "
                  "(or see config/models.fleet.example.yaml)")
            sys.exit(2)

    endpoint = args.brain_url or f"http://127.0.0.1:{args.port}/v1"
    cfg = {
        "idle_unload_seconds": 0, "ram_reserve_mb": 0, "vram_reserve_mb": 0,
        "critical_ram_percent": 95,
        "models": [{"id": "stick-brain", "role": "supervisor", "api_model": "stick-brain",
                    "endpoint": endpoint, "keep_loaded": True,
                    "context_length": 16384, "native_max_tokens": 1200,
                    "native_temperature": 0.6, "native_reasoning_budget": 512}],
    }
    cfg_path = CORE / "config" / "models.fleet.local.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, indent=1).replace(": true", ": true"))  # json is valid yaml here
    print(f"selected: {chosen} ({measured:.1f} tok/s) -> {cfg_path}")

    proc, cmd = None, None
    if args.serve and not args.brain_url:
        cmd = [str(stick_exe(bin_dir, "llama-server")), "-m", str(STICK / "models" / chosen),
               "-c", "16384", "--host", "127.0.0.1", "--port", str(args.port),
               "--alias", "stick-brain", "-ngl", "99"]
        log = open(STICK / "llama-server.log", "w")
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, **detach_kwargs(),
                                env={**os.environ, "LD_LIBRARY_PATH": str(bin_dir)})
        print(f"llama-server pid {proc.pid} on :{args.port} (log: llama-server.log)")

        # full stack: seed the state root, then start the native bridge so
        # skills, soul, memories and tool calls are ready immediately
        state = STICK / "state"
        state.mkdir(exist_ok=True)
        mem = STICK / "soul" / "memory.sqlite3"
        if mem.is_file() and not (state / "memory.sqlite3").is_file():
            shutil.copy2(mem, state / "memory.sqlite3")
        token_file = state / "bridge.token"
        if not token_file.is_file():
            token_file.write_text(os.urandom(32).hex())
        bridge_env = dict(os.environ,
                          HANNI_MODEL_CONFIG=str(cfg_path),
                          HANNI_SOUL=str(STICK / "soul" / "SOUL.md"),
                          HANNI_SKILLS_DIR=str(STICK / "soul" / "skills"),
                          PYTHONPATH=str(CORE / "src"))
        if not args.secure:
            bridge_env["HANNI_BRIDGE_OPEN"] = "1"
            bridge_env["HANNI_AUTO_APPROVE"] = "1"
        blog = open(STICK / "bridge.log", "w")
        bridge = subprocess.Popen(
            [sys.executable, "-m", "hanni.hermes.service", "--root", str(state),
             "--hermes-config", str(CORE / "config" / "hanni.yaml"),
             "--token-file", str(token_file), "--brain", "native",
             "--port", str(args.port + 1)],
            cwd=CORE, env=bridge_env,
            stdout=blog, stderr=subprocess.STDOUT, **detach_kwargs())
        print(f"native bridge pid {bridge.pid} on :{args.port + 1} "
              f"(token: {token_file}) — soul, skills, memories and tool calls are live")
        print("point Hanni OS at http://127.0.0.1:" + str(args.port + 1))
        cron = None
        if not args.no_cron:
            clog = open(STICK / "cron.log", "w")
            cron = subprocess.Popen(
                [sys.executable, "-m", "hanni.native.cron", "--root", str(state), "daemon"],
                cwd=CORE, env={**os.environ, "PYTHONPATH": str(CORE / "src")},
                stdout=clog, stderr=subprocess.STDOUT, **detach_kwargs())
            print(f"cron daemon pid {cron.pid} — recurring tasks fire automatically "
                  "(python -m hanni.native.cron --root state add --prompt ... --interval ...)")
        ui_port = None
        ui = None
        if args.ui:
            ui_port = args.port + 2
            uilog = open(STICK / "dashboard.log", "w")
            ui = subprocess.Popen(
                [sys.executable, "-m", "hanni.dashboard.launcher",
                 "--dashboard-only", "--port", str(ui_port), "--no-browser",
                 "--config-dir", str(STICK / "config"),
                 "--data-dir", str(state)],
                cwd=CORE,
                env={**os.environ,
                     "PYTHONPATH": str(CORE / "src"),
                     "HANNI_BRIDGE_URL": f"http://127.0.0.1:{args.port + 1}",
                     "HANNI_BRIDGE_TOKEN_FILE": str(token_file)},
                stdout=uilog, stderr=subprocess.STDOUT, **detach_kwargs())
            print(f"Hanni OS dashboard on http://127.0.0.1:{ui_port} (log: dashboard.log)")
        if not args.no_browser:
            import socket as _sk
            import time as _time
            import webbrowser
            for _ in range(30):  # wait for the bridge to accept, then open the door
                with _sk.socket() as gate:
                    if gate.connect_ex(("127.0.0.1", args.port + 1)) == 0:
                        break
                _time.sleep(1)
            try:
                webbrowser.open(f"http://127.0.0.1:{ui_port or args.port + 1}/")
            except Exception:
                print("(no desktop here — open http://127.0.0.1:"
                      + str(ui_port or args.port + 1) + "/ yourself)")
        if args.wait:
            import time as _t
            restarts = ui_restarts = 0
            stopped_by_user = False
            while True:
                while (bridge.poll() is None
                       and (proc is None or proc.poll() is None)
                       and (ui is None or ui.poll() is None)):
                    _t.sleep(5)
                if bridge.poll() is not None:
                    print("bridge exited; shutting the stack down.")
                    break
                if ui is not None and ui.poll() is not None:
                    if ui.returncode == 0:
                        # The dashboard's Stop HANNI button: clean exit.
                        stopped_by_user = True
                        print("Stop requested from Hanni OS — closing everything.")
                        break
                    ui_restarts += 1
                    if ui_restarts > 3:
                        break
                    print(f"dashboard exited; restarting (attempt {ui_restarts}/3)")
                    uilog = open(STICK / "dashboard.log", "a")
                    ui = subprocess.Popen(
                        [sys.executable, "-m", "hanni.dashboard.launcher",
                         "--dashboard-only", "--port", str(ui_port), "--no-browser",
                         "--config-dir", str(STICK / "config"),
                         "--data-dir", str(state)],
                        cwd=CORE,
                        env={**os.environ,
                             "PYTHONPATH": str(CORE / "src"),
                             "HANNI_BRIDGE_URL": f"http://127.0.0.1:{args.port + 1}",
                             "HANNI_BRIDGE_TOKEN_FILE": str(token_file)},
                        stdout=uilog, stderr=subprocess.STDOUT, **detach_kwargs())
                    continue
                if proc is not None and proc.poll() is not None:
                    restarts += 1
                    if restarts > 3:
                        break
                    print(f"llama-server exited; restarting (attempt {restarts}/3)")
                    log = open(STICK / "llama-server.log", "a")
                    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                            **detach_kwargs(),
                                            env={**os.environ, "LD_LIBRARY_PATH": str(bin_dir)})
            # tear down everything we own: model server, bridge, cron, dashboard
            for victim in (proc, bridge, cron, ui):
                if victim is not None and victim.poll() is None:
                    victim.terminate()
            for victim in (proc, bridge, cron, ui):
                if victim is not None:
                    try:
                        victim.wait(timeout=8)
                    except Exception:
                        victim.kill()
            sys.exit(0 if stopped_by_user else 1)
    else:
        print("(dry run — add --serve to start the brain)")


if __name__ == "__main__":
    main()
