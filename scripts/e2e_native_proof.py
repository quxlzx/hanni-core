#!/usr/bin/env python3
"""Proof-of-life: native HANNI loop end-to-end against the live Wonyoung brain.

Starts the bridge with --brain native, submits one task whose only capability
is a fake local 'echo_note' tool, plays the owner's role by fulfilling the
durable action request with a receipt, and verifies the task reaches
review_required with a matching receipt and a model claim.
"""
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.request

ROOT = "/tmp/hanni-native-e2e"
PORT = 8093
BASE = f"http://127.0.0.1:{PORT}"


def api(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    os.makedirs(ROOT, exist_ok=True)
    token = secrets.token_hex(32)
    open(f"{ROOT}/bridge.token", "w").write(token)

    env = dict(os.environ,
               HANNI_MODEL_CONFIG=os.path.abspath("config/models.fleet.local.yaml"),
               HANNI_MODEL_API_KEY=os.environ["HANNI_MODEL_API_KEY"])
    service = subprocess.Popen(
        [sys.executable, "-m", "hanni.hermes.service", "--root", ROOT,
         "--hermes-config", "config/hanni.yaml", "--token-file", f"{ROOT}/bridge.token",
         "--brain", "native", "--port", str(PORT)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(20):
            try:
                api("GET", "/health", token=token)
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("bridge did not start")

        tool_spec = {"name": "echo_note", "target": "windows", "hash": "test", "remote": {},
                     "schema": {"type": "function", "function": {
                         "name": "echo_note",
                         "description": "Echo a short note back to the assistant. Requires owner approval.",
                         "parameters": {"type": "object", "properties": {"note": {"type": "string", "maxLength": 200}},
                                        "required": ["note"], "additionalProperties": False}}}}
        task = api("POST", "/tasks", {"key": "e2e-1", "task": {
            "prompt": "Use the echo_note tool to echo exactly 'hello native hanni', then tell me what the tool returned.",
            "context": {}, "origin": "hanni", "windows_tools": [tool_spec]}}, token=token)
        task_id = task["id"]
        print("task submitted:", task_id)

        action_id = None
        deadline = time.time() + 240
        while time.time() < deadline:
            state = api("GET", f"/tasks/{task_id}", token=token)
            actions = state.get("actions") or []
            if actions:
                action_id = actions[0]["id"]
                break
            if state["state"] in {"failed", "review_required", "interrupted"}:
                print("FULL STATE:", json.dumps(state, indent=1)[:2000])
                raise RuntimeError(f"task ended before any action: {state['state']} {state.get('error')}")
            time.sleep(1)
        if action_id is None:
            raise RuntimeError("no action request appeared in time")
        print("owner approval simulated for action:", action_id)
        api("POST", f"/actions/{action_id}", {"state": "dispatching"}, token=token)
        api("POST", f"/actions/{action_id}", {"state": "fulfilled",
            "receipt": {"ok": True, "message": "echoed", "data": {"echo": "hello native hanni"}}}, token=token)

        state = {}
        while time.time() < deadline:
            state = api("GET", f"/tasks/{task_id}", token=token)
            if state["state"] in {"review_required", "failed", "interrupted", "uncertain"}:
                break
            time.sleep(1)
        result = state.get("result") or {}
        claims = (result.get("model_claims") or "")[:400]
        receipts = result.get("receipts") or []
        print("final state:", state["state"])
        print("reported_by:", result.get("reported_by"))
        print("receipts:", json.dumps(receipts)[:300])
        print("model claims:", claims)
        ok = (state["state"] == "review_required" and receipts and receipts[0].get("ok")
              and "hello native hanni" in claims)
        print("PROOF-OF-LIFE:", "PASS" if ok else "PARTIAL — inspect above")
        return 0 if ok else 1
    finally:
        service.terminate()
        service.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
