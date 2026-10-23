"""Real planner + original workflow/controller exercise on owned private input.

No scripted plan/response is supplied. Every approved generated operation is
reviewed against the narrow fixture objective; external accounts are excluded.
All failure records survive. This is exposed development, not the final set.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.request
from uuid import uuid4

import psutil

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--objective", choices=("analysis", "mirror"), default="analysis")
    args = parser.parse_args()
    session, out = args.session.resolve(), args.output.resolve()
    private = (ROOT / "data/v44-verification").resolve()
    assert session.is_relative_to(private) and out.is_relative_to(private) and not out.exists()
    ready = json.loads((session / "ready.json").read_text(encoding="utf8"))
    ownership = json.loads((session / "ownership.json").read_text(encoding="utf8"))
    state_directory = Path(ownership['state_directory']).resolve()
    assert state_directory.is_relative_to(private)
    assert psutil.Process(ready["helper_pid"]).create_time() == ready["helper_create_time"]
    out.mkdir(parents=True)
    url = ready["url"]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    token = None
    report = {"scope": "Actual original model planner/controller with independent owned fixture; exposed development.",
              "started_at": time.time(), "workflows": [], "planner_responses_substituted": False,
              "external_account_actions": 0, "input_root": None}
    def save():
        (out / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf8")
    def request(path, payload=None):
        headers = {"Content-Type": "application/json", "Origin": url, "Accept": "application/json"}
        if token:
            headers["X-Hanni-Token"] = token
        req = urllib.request.Request(url + path, headers=headers,
            data=None if payload is None else json.dumps(payload).encode())
        try:
            with opener.open(req, timeout=15) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)
    def mutate(operation, data):
        status, body = request("/api/workflows", {"id": str(uuid4()), "operation": operation, "data": data})
        assert status == 200, (operation, status, body)
        return body
    def detail(key):
        status, body = request("/api/workflows/" + key)
        assert status == 200
        return body["workflow"]
    status, chat = request("/api/chat?before=1")
    assert status == 200
    token = chat["token"]
    input_root = Path(tempfile.mkdtemp(prefix="hanni-v44-owned-", dir=tempfile.gettempdir())).resolve()
    assert input_root.parent == Path(tempfile.gettempdir()).resolve()
    report["input_root"] = str(input_root)
    facts = {"runs": [{"passed": 3, "total": 4}, {"passed": 5, "total": 8}]}
    source = input_root / "counts.json"
    source.write_text(json.dumps(facts), encoding="utf8")
    report["input_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    goal = ("Read the JSON file " + str(source) + ". Calculate each run's pass percentage "
            "and the absolute percentage-point gap, using evidence from that file. "
            "Save the verified calculation report in your private workflow artifact root, "
            "then read back the saved report to verify its contents. No remote accounts or application actions.")
    if args.objective == "mirror":
        goal = ("Read the text file " + str(source) + ". Save its exact original text as a report "
                "inside your supplied private workflow artifact root. Read back the saved report. "
                "Each read step description must include the original full file path or generated predecessor path. "
                "Do not use remote accounts or execute applications.")
    row = {"goal": goal, "scope": "Real-model planning, actual original file read, evidence analysis and managed artifact/readback if admitted.",
           "observations": [], "independent_success": False}
    report["workflows"].append(row)
    save()
    key = mutate("goal.submit", {"goal": goal, "mode": "assisted"})["workflow_id"]
    row["workflow_id"] = key
    deadline = time.monotonic() + 300
    try:
        while time.monotonic() < deadline:
            current = detail(key)
            observed = {"status": current["status"], "revision": current["revision"], "counts": current.get("counts")}
            if not row["observations"] or row["observations"][-1] != observed:
                row["observations"].append(observed)
                print(json.dumps({"workflow": key, "status": current["status"]}), flush=True)
                save()
            if current["status"] == "awaiting_plan_approval":
                # Review the actual generated bound plan; never alter or inject it.
                permitted = True
                for step in current.get("steps", []):
                    kind, cap = step.get("kind"), step.get("capability_id")
                    if kind == "analysis":
                        permitted &= bool(step.get("dependencies"))
                    elif cap == "file.read":
                        path = step.get("arguments", {}).get("path")
                        permitted &= isinstance(path, dict) or (isinstance(path, str) and Path(path).resolve() == source)
                    elif kind == "artifact" and cap == "file.write":
                        path = step.get("arguments", {}).get("path")
                        expected_root = (state_directory / "workflows/artifacts" / key).resolve()
                        permitted &= isinstance(path, str) and Path(path).resolve().is_relative_to(expected_root)
                    else:
                        permitted = False
                if not permitted:
                    row["review_blocked"] = "Actual generated plan exceeded the predeclared private file/calculation/artifact objective."
                    break
                data = {"workflow_id": key, "expected_revision": current["revision"], "plan_hash": current["plan_hash"]}
                mutate("approve_plan", data)
                current = detail(key)
                mutate("start", {"workflow_id": key, "expected_revision": current["revision"], "plan_hash": current["plan_hash"]})
            elif current["status"] == "awaiting_step_approval":
                # Managed artifact writes are the only consequential operation
                # allowed by this specific user-authorized isolated objective.
                approval = next(a for a in current["approvals"] if a["kind"] == "action" and a["state"] == "pending")
                step = next(s for s in current["steps"] if s["step_id"] == approval["step_id"])
                if step.get("kind") != "artifact" or step.get("capability_id") != "file.write":
                    row["review_blocked"] = "Unrequested consequential operation in actual plan."
                    break
                data = {"workflow_id": key, "expected_revision": current["revision"]}
                data.update({k: approval.get(k) for k in ("approval_id", "step_id", "plan_hash", "argument_hash", "definition_hash")})
                mutate("approve_step", data)
            elif current["status"] in {"completed", "failed", "blocked", "cancelled", "needs_review"}:
                break
            time.sleep(.15)
        current = detail(key)
        row["final_detail"] = current
        row["status"] = current["status"]
        artifacts = []
        for step in current.get("steps", []):
            if step.get("kind") == "artifact" and step.get("result", {}).get("ok"):
                target = Path(step["result"]["data"]["path"]).resolve()
                assert target.is_relative_to((state_directory / "workflows/artifacts" / key).resolve())
                artifacts.append({"path": str(target), "text": target.read_text(encoding="utf8"),
                                  "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
        row["actual_artifacts"] = artifacts
        row["independent_success"] = (current["status"] == "completed" and
            current.get("counts", {}).get("verified", 0) >= (3 if args.objective == "mirror" else 4) and bool(artifacts) and
            all(i.get("state") == "finished" for i in current.get("invocations", [])) and
            all(s.get("status") == "verified" for s in current.get("steps", []) if s.get("required")))
        if args.objective == "mirror":
            row["independent_success"] &= all(a["text"] == source.read_text(encoding="utf8") for a in artifacts)
    finally:
        current = detail(key)
        if current["status"] not in {"completed", "failed", "cancelled", "blocked"}:
            try:
                mutate("cancel", {"workflow_id": key, "expected_revision": current["revision"]})
                row["cleanup_cancellation"] = detail(key)
            except Exception as exc:
                row["cleanup_error"] = {"type": type(exc).__name__, "message": str(exc)}
        report["finished_at"] = time.time()
        save()
        print(json.dumps({"status": row.get("status"), "independent_success": row["independent_success"]}), flush=True)


if __name__ == "__main__":
    main()
