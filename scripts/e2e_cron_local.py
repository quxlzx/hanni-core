#!/usr/bin/env python3
"""Live check: cron job -> bridge queue -> native worker -> local runtime on the real brain."""
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.request

ROOT = "/tmp/hanni-cron-live"
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
    subprocess.run(["pkill", "-f", f"hanni.hermes.service --root {ROOT}"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    subprocess.run(["rm", "-rf", ROOT], check=True)
    os.makedirs(ROOT)
    token = secrets.token_hex(32)
    open(f"{ROOT}/bridge.token", "w").write(token)
    env = dict(os.environ, HANNI_MODEL_CONFIG=os.path.abspath("config/models.fleet.local.yaml"))
    service = subprocess.Popen(
        [sys.executable, "-m", "hanni.hermes.service", "--root", ROOT,
         "--hermes-config", "config/hanni.yaml", "--token-file", f"{ROOT}/bridge.token",
         "--brain", "native", "--port", str(PORT)],
        env=env, stdout=open(f"{ROOT}/service.log", "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(20):
            try:
                if "protocol" in api("GET", "/health", token=token):
                    break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("bridge did not start")
        # owner creates a cron job with a pre-authorized local policy
        subprocess.run([sys.executable, "-m", "hanni.native.cron", "--root", ROOT, "add",
                        "--prompt", ("Use local_terminal to run the command 'echo cron-fired-ok', "
                                     "then use local_write_file to save that output as report.txt, "
                                     "and report both results."),
                        "--interval", "60", "--auto-approve-all"], check=True)
        # force it due and fire once
        subprocess.run(["python3", "-c", f"""
import sqlite3, time
db = sqlite3.connect('{ROOT}/cron.sqlite3')
db.execute('UPDATE jobs SET next_run=?', (time.time() - 1,))
db.commit()"""], check=True)
        subprocess.run([sys.executable, "-m", "hanni.native.cron", "--root", ROOT, "daemon", "--once"], check=True)

        deadline = time.time() + 300
        state = {}
        while time.time() < deadline:
            import sqlite3
            row = sqlite3.connect(f"{ROOT}/tasks.sqlite3").execute(
                "SELECT * FROM tasks").fetchone()
            state = json.loads(row[3])
            if state["state"] in {"review_required", "failed", "interrupted", "uncertain"}:
                break
            time.sleep(2)
        result = state.get("result") or {}
        receipts = result.get("receipts") or []
        print("state:", state["state"])
        print("receipts:", json.dumps(receipts)[:500])
        print("claims:", (result.get("model_claims") or "")[:300])
        report = os.path.exists(f"{ROOT}/workspace/report.txt")
        print("workspace/report.txt exists:", report)
        ok = (state["state"] == "review_required" and report
              and any(r.get("approved_by") == "task_policy" for r in receipts))
        print("CRON+LOCAL RUNTIME:", "PASS" if ok else "CHECK ABOVE")
        if not ok:
            print("SERVICE LOG:", open(f"{ROOT}/service.log").read()[-800:])
        return 0 if ok else 1
    finally:
        service.terminate()
        service.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
