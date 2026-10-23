#!/usr/bin/env python3
"""Drive real agent tasks through the native HANNI loop against a tier brain.

Usage: e2e_tier_tasks.py <name> <endpoint>   e.g. k2-7b http://127.0.0.1:8302/v1
Tasks: (1) owner-approved tool roundtrip, (2) multi-step local file write+read,
(3) compute-with-verification via local_terminal. Scores each on state+content.
"""
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.request

NAME = sys.argv[1]
ENDPOINT = sys.argv[2]
ROOT = f"/tmp/hanni-tier-{NAME}"

import socket as _socket
_s = _socket.socket(); _s.bind(("127.0.0.1", 0)); PORT = _s.getsockname()[1]; _s.close()
BASE = f"http://127.0.0.1:{PORT}"

ECHO_SPEC = {"name": "echo_note", "target": "windows", "hash": "tier-test", "remote": {},
             "schema": {"type": "function", "function": {
                 "name": "echo_note",
                 "description": "Echo a short note back. Requires owner approval.",
                 "parameters": {"type": "object", "properties": {"note": {"type": "string", "maxLength": 200}},
                                "required": ["note"], "additionalProperties": False}}}}


def api(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def run_task(token, key, prompt, context, expect, windows_tools=(), approve=None):
    task = api("POST", "/tasks", {"key": key, "task": {
        "prompt": prompt, "windows_tools": list(windows_tools), "origin": "hanni",
        "context": context}}, token=token)
    deadline = time.time() + 300
    state = {}
    approved = False
    while time.time() < deadline:
        state = api("GET", f"/tasks/{task['id']}", token=token)
        if approve and not approved and state.get("actions"):
            action_id = state["actions"][0]["id"]
            api("POST", f"/actions/{action_id}", {"state": "dispatching"}, token=token)
            api("POST", f"/actions/{action_id}", {"state": "fulfilled",
                "receipt": {"ok": True, "message": "echoed", "data": {"echo": approve}}}, token=token)
            approved = True
        if state["state"] in {"review_required", "failed", "interrupted", "uncertain"}:
            break
        time.sleep(2)
    claims = (state.get("result") or {}).get("model_claims") or ""
    receipts = (state.get("result") or {}).get("receipts") or []
    ok = state["state"] == "review_required" and all(e in claims for e in expect)
    print(f"  {key}: state={state['state']} receipts={len(receipts)} "
          f"{'PASS' if ok else 'CHECK'} :: {claims[:180]}")
    return ok


def main():
    subprocess.run(["rm", "-rf", ROOT], check=True)
    os.makedirs(ROOT)
    yaml = f"""idle_unload_seconds: 0
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
    native_max_tokens: 1500
    native_temperature: 0.3
    native_reasoning_budget: 400
"""
    cfg = f"{ROOT}/model.yaml"
    open(cfg, "w").write(yaml)
    token = secrets.token_hex(32)
    open(f"{ROOT}/bridge.token", "w").write(token)
    env = dict(os.environ, HANNI_MODEL_CONFIG=os.path.abspath(cfg))
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
        auto = {"local_runtime": {"auto_approve": ["*"]}}
        print(f"== {NAME} @ {ENDPOINT} ==")
        results = [
            run_task(token, "t1", "Use the echo_note tool to echo exactly 'tier alive', "
                                  "then tell me what it returned.",
                     {}, ["tier alive"], windows_tools=[ECHO_SPEC], approve="tier alive"),
            run_task(token, "t2", "Use local_write_file to save the text 'k2-tier' into "
                                  "notes/tier.txt, then use local_read_file to read it back, "
                                  "and report the exact content you read.",
                     auto, ["k2-tier"]),
            run_task(token, "t3", "Compute 17 times 23 using local_terminal with the command "
                                  "python3 -c \"print(17*23)\", then report the number it printed.",
                     auto, ["391"]),
        ]
        print(f"== {NAME}: {sum(1 for r in results if r)}/{len(results)} clean passes ==")
        return 0 if all(results) else 1
    finally:
        service.terminate()
        service.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
