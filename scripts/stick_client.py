#!/usr/bin/env python3
"""Post-boot client: prove the stick's bridge has soul+skills+memory+tools live."""
import json
import os
import sys
import time
import urllib.request

STICK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.expanduser("~"), "stick-sim")
PORT = sys.argv[2] if len(sys.argv) > 2 else "8322"
BASE = f"http://127.0.0.1:{PORT}"
token = open(f"{STICK}/state/bridge.token").read().strip()


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


task = api("POST", "/tasks", {"key": "stick-live-2", "task": {
    "prompt": ("Two things: (a) from your durable memories, which fleet machine is the MCP hub? "
               "(b) use local_write_file to save 'stick-live' into hello.txt and confirm the "
               "receipt. Answer in two short lines."),
    "windows_tools": [], "origin": "hanni",
    "context": {"local_runtime": {"auto_approve": ["*"]}}}})
deadline = time.time() + 240
state = {}
while time.time() < deadline:
    state = api("GET", f"/tasks/{task['id']}")
    if state["state"] in {"review_required", "failed", "interrupted", "uncertain"}:
        break
    time.sleep(2)
r = state.get("result") or {}
claims = r.get("model_claims") or ""
print("state:", state["state"], "| receipts:", len(r.get("receipts") or []))
print("claims:", claims[:300])
ok = "Karina" in claims and state["state"] == "review_required"
print("STICK FULL-STACK LIVE:", "PASS" if ok else "CHECK")
