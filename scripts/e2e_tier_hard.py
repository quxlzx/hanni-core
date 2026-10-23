#!/usr/bin/env python3
"""Harder chained task per tier brain: create -> verify -> compute -> report."""
import subprocess
import sys

TASK = ("Do these steps in order using your tools: "
        "1) local_write_file: save the numbers 4, 8, 15, 16, 23, 42 one per line into data/nums.txt. "
        "2) local_read_file: read data/nums.txt back. "
        "3) local_terminal: run the command awk '{s+=$1} END {print s}' data/nums.txt "
        "(pass the awk program as the first argument and the file as the second). "
        "4) Report the exact sum that awk printed.")

# reuse the tier harness by injecting a custom t4: simplest is a tiny wrapper
# that calls e2e_tier_tasks machinery — instead, run it standalone via the same bridge pattern
import json, os, secrets, time, urllib.request
NAME, ENDPOINT = sys.argv[1], sys.argv[2]
ROOT = f"/tmp/hanni-tier-{NAME}-hard"
import socket as _s_
_s = _s_.socket(); _s.bind(("127.0.0.1", 0)); PORT = _s.getsockname()[1]; _s.close()
BASE = f"http://127.0.0.1:{PORT}"

def api(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

subprocess.run(["rm", "-rf", ROOT], check=True); os.makedirs(ROOT)
open(f"{ROOT}/model.yaml", "w").write(f"""idle_unload_seconds: 0
ram_reserve_mb: 0
vram_reserve_mb: 0
critical_ram_percent: 95
models:
  - id: tier
    role: supervisor
    api_model: tier
    endpoint: "{ENDPOINT}"
    keep_loaded: true
    context_length: 16384
    native_max_tokens: 2000
    native_temperature: 0.3
    native_reasoning_budget: 600
""")
token = secrets.token_hex(32); open(f"{ROOT}/bridge.token", "w").write(token)
env = dict(os.environ, HANNI_MODEL_CONFIG=os.path.abspath(f"{ROOT}/model.yaml"))
svc = subprocess.Popen([sys.executable, "-m", "hanni.hermes.service", "--root", ROOT,
                        "--hermes-config", "config/hanni.yaml", "--token-file", f"{ROOT}/bridge.token",
                        "--brain", "native", "--port", str(PORT)],
                       env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(20):
        try:
            if "protocol" in api("GET", "/health", token=token): break
        except Exception: time.sleep(0.5)
    t0 = time.time()
    task = api("POST", "/tasks", {"key": "hard", "task": {
        "prompt": TASK, "windows_tools": [], "origin": "hanni",
        "context": {"local_runtime": {"auto_approve": ["*"]}}}}, token=token)
    deadline = time.time() + 420
    state = {}
    while time.time() < deadline:
        state = api("GET", f"/tasks/{task['id']}", token=token)
        if state["state"] in {"review_required", "failed", "interrupted", "uncertain"}: break
        time.sleep(2)
    r = state.get("result") or {}
    claims = r.get("model_claims") or ""
    receipts = r.get("receipts") or []
    print(f"{NAME} hard: state={state['state']} steps={len(receipts)} "
          f"wall={time.time()-t0:.0f}s {'PASS' if '108' in claims else 'CHECK'}")
    print("claims:", claims[:250])
finally:
    svc.terminate(); svc.wait(timeout=5)
