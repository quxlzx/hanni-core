#!/usr/bin/env python3
"""Live check: native worker recalls migrated durable memory on the real brain."""
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = "/tmp/hanni-mem-live"
import socket as _socket
_s = _socket.socket(); _s.bind(("127.0.0.1", 0)); PORT = _s.getsockname()[1]; _s.close()
BASE = f"http://127.0.0.1:{PORT}"


def api(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    subprocess.run(["rm", "-rf", ROOT], check=True)
    os.makedirs(ROOT)
    bridge_root = os.environ.get("HANNI_BRIDGE_ROOT",
                                 os.path.join(os.path.expanduser("~"), "hanni-hermes-bridge", "state"))
    shutil.copy2(os.path.join(bridge_root, "memory.sqlite3"), f"{ROOT}/memory.sqlite3")
    token = secrets.token_hex(32)
    open(f"{ROOT}/bridge.token", "w").write(token)
    env = dict(os.environ, HANNI_MODEL_CONFIG=os.path.abspath("config/models.fleet.local.yaml"))
    service = subprocess.Popen(
        [sys.executable, "-m", "hanni.hermes.service", "--root", ROOT,
         "--hermes-config", "config/hanni.yaml", "--token-file", f"{ROOT}/bridge.token",
         "--brain", "native", "--port", str(PORT)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(20):
            try:
                if "protocol" in api("GET", "/health", token=token):
                    break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("bridge did not start")
        task = api("POST", "/tasks", {"key": "mem-1", "task": {
            "prompt": ("From your durable memories only: which fleet machine is the MCP hub, "
                       "and which port range do its core services use? Answer in one line."),
            "windows_tools": [], "origin": "hanni", "context": {}}}, token=token)
        deadline = time.time() + 240
        state = {}
        while time.time() < deadline:
            state = api("GET", f"/tasks/{task['id']}", token=token)
            if state["state"] in {"review_required", "failed", "interrupted", "uncertain"}:
                break
            time.sleep(2)
        claims = ((state.get("result") or {}).get("model_claims") or "")
        print("state:", state["state"])
        print("claims:", claims[:300])
        ok = "Karina" in claims and "8090" in claims
        print("MEMORY RECALL LIVE:", "PASS" if ok else "CHECK ABOVE")
        return 0 if ok else 1
    finally:
        service.terminate()
        service.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
