"""Actual-model smoke over exposed engineering goals, never sealed cases.

Preparation/import starts nothing. Coordinator GO is required before running.
All responses are genuine original-client outputs; no repair/retry substitution.
"""
import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import psutil
from hanni.tools.base import ToolRequest
from hanni.workflows.types import WorkflowLimits
from scripts.v3_review.fixtures import fixture_facts
from scripts.v3_review.model_adapter import OwnedConfiguredRuntime, final_manifest
from scripts.v3_review.service_fixture import ServiceFixture

TERMINAL = {"completed", "partially_completed", "blocked", "failed", "cancelled", "paused"}
SAFE_READS = {"file.read", "file.stat", "file.list"}


def persisted_timing(detail):
    """Report authoritative workflow timestamps, never setup-inclusive timers."""
    def milliseconds(first, last):
        try:
            start, finish = (datetime.fromisoformat(value.replace("Z", "+00:00"))
                             for value in (first, last))
            if start.tzinfo is None or finish.tzinfo is None or finish < start:
                return None
            return round((finish - start).total_seconds() * 1000, 3)
        except (AttributeError, TypeError, ValueError, OverflowError):
            return None
    checkpoints = detail.get("checkpoints", [])
    started = next((item for item in checkpoints if item.get("kind") == "planning_started"), None)
    endpoints = {"planning_finished", "planning_blocked", "planning_failed", "planning_paused", "planning_cancelled"}
    # plan_saved precedes the authoritative post-plan grant/status commit.
    # Prefer the actual phase-end checkpoint; expose fallback kind explicitly.
    finished = next((item for item in checkpoints if item.get("kind") in endpoints), None)
    if finished is None:
        finished = next((item for item in checkpoints if item.get("kind") == "plan_saved"), None)
    final_at = finished.get("created_at") if finished else None
    completed = detail.get("status") == "completed"
    return {
        "source": "Persisted timezone-aware UTC timestamps; negative/missing/invalid intervals are NOT MEASURED.",
        "planning_endpoint_kind": finished.get("kind") if finished else None,
        "submitted_to_planning_endpoint_ms": milliseconds(detail.get("created_at"), final_at),
        "active_planning_to_endpoint_ms": milliseconds(started.get("created_at") if started else None, final_at),
        "completed_submission_to_finished_ms": milliseconds(detail.get("created_at"), detail.get("finished_at")) if completed else None,
        "completed_started_to_finished_ms": milliseconds(detail.get("started_at"), detail.get("finished_at")) if completed else None,
        "completion_duration_status": "MEASURED" if completed and milliseconds(detail.get("created_at"), detail.get("finished_at")) is not None else "NOT MEASURED",
        "scope": "Planning excludes fixture setup, runtime startup, post-case cleanup and external polling delay. Completed submission duration includes model/service work, automated exact test-owner approval/poll waits and execution/verification; no human timing claim.",
    }


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def inside(path, root):
    try:
        path = Path(path)
        return path.is_absolute() and path.resolve().is_relative_to(root.resolve())
    except (TypeError, ValueError, OSError):
        return False


def boundary(call):
    schema = ((call.get("response_format") or {}).get("json_schema") or {}).get("schema", {})
    properties = schema.get("properties", {})
    if "observations" in properties:
        return "evidence_report"
    return "outline" if "summary" in properties else "binding"


def drive(fixture, key, row):
    deadline = time.monotonic() + fixture.service.limits.max_duration_seconds + 30
    last_revision = None
    while time.monotonic() < deadline:
        detail = fixture.detail(key)
        if detail["revision"] != last_revision:
            row["observed_states"].append({"revision": detail["revision"], "state": detail["status"]})
            last_revision = detail["revision"]
        if detail["status"] == "awaiting_plan_approval":
            forbidden = []
            for step in detail["steps"]:
                if step["kind"] == "tool":
                    args = step.get("arguments") or {}
                    path = args.get("path")
                    ref = path.get("$ref") if isinstance(path, dict) and set(path) == {"$ref"} else None
                    source = next((item for item in detail["steps"] if isinstance(ref, dict) and item["step_id"] == ref.get("step_id")), None)
                    owned_artifact_ref = bool(source and source["kind"] == "artifact" and ref.get("path") == "/data/path" and ref.get("type") == "string" and source["step_id"] in step.get("dependencies", []))
                    if step.get("capability_id") not in SAFE_READS or not (inside(path, fixture.root) or owned_artifact_ref):
                        forbidden.append(step["step_id"])
                elif step["kind"] not in {"artifact", "analysis"}:
                    forbidden.append(step["step_id"])
            if forbidden:
                row["test_owner_scope_refusal"] = forbidden
                return detail
            fixture.control(key, "approve_plan")
            row["controls"].append({"operation": "approve_plan", "plan_hash": detail["plan_hash"]})
        elif detail["status"] == "ready":
            fixture.control(key, "start")
            row["controls"].append({"operation": "start", "plan_hash": detail["plan_hash"]})
        elif detail["status"] == "awaiting_step_approval":
            approval = next(item for item in detail["approvals"]
                            if item["kind"] == "action" and item["state"] == "pending")
            step = next(item for item in detail["steps"] if item["step_id"] == approval["step_id"])
            arguments = step.get("resolved_arguments") or {}
            artifact_root = fixture.config.paths.data_dir / "workflows" / "artifacts" / key
            allowed = (step["kind"] == "artifact" and step.get("capability_id") == "file.write"
                       and inside(arguments.get("path"), artifact_root))
            operation = "approve_step" if allowed else "reject"
            fixture.control(key, operation, approval=approval)
            row["controls"].append({"operation": operation,
                                    **{field: approval[field] for field in ("approval_id", "argument_hash", "definition_hash")}})
        elif detail["status"] in TERMINAL:
            return detail
        time.sleep(.1)
    row["test_timeout"] = True
    return fixture.detail(key)


def run_case(name, runtime, output, fixtures_root=None):
    root = (fixtures_root or (output / "cases")) / name
    case_output = output / "cases" / name
    limit_config = runtime.config.hanni.workflows
    limits = WorkflowLimits.from_config(limit_config)
    threshold = runtime.config.models.critical_ram_percent
    def resource_probe():
        ram = psutil.virtual_memory().percent
        return {"allowed": ram < threshold, "ram_percent": ram,
                "cpu_percent": psutil.cpu_percent(), "gpu": None,
                "reason": "Actual local RAM admission; original ModelManager owns GPU admission."}
    fixture = ServiceFixture(root, client=runtime.client, limits=limits, resource_probe=resource_probe)
    row = {"name": name, "source": "already-exposed public engineering goal", "controls": [],
           "observed_states": [], "original_limits": asdict(limits)}
    facts = {}
    initial = len(runtime.client.calls)
    started = time.perf_counter()
    try:
        if fixtures_root is None:
            facts = fixture_facts(root / "inputs")
        else:
            # Existing inputs are read only. Never overwrite previous evidence
            # or materialize a corrected fixture after seeing a model response.
            facts = {"source": root / "inputs/source.txt", "valid": root / "inputs/runs.json"}
            expected = {"source": b"fixture report\nunchanged source\n",
                        "valid": json.dumps({"runs": [
                            {"name": "first", "passed": 6, "total": 10},
                            {"name": "second", "passed": 9, "total": 10}]}).encode()}
            if any(path.read_bytes() != expected[key] for key, path in facts.items()):
                raise AssertionError("Original public input bytes changed; comparison refused")
            row["reused_fixture_history"] = "Prior isolated attempts and owned artifact effects are retained; history is never supplied to prompts. This run uses a fresh goal UUID and managed artifact scope; original inputs and prior result records remain unchanged."
        row["input_sha256_before"] = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in facts.items() if key in {"source", "valid"}}
        if name == "artifact_roundtrip":
            goal = f"Read the text file {facts['source']} and preserve its verified contents in a saved text artifact. Read back the saved artifact to check it matches the original."
        else:
            goal = f"Read {facts['valid']}. Compare both observed runs, compute pass percentages and their improvement, and save the report."
        row["goal"] = goal
        row["goal_sha256"] = hashlib.sha256(goal.encode()).hexdigest()
        if fixtures_root is not None:
            previous_case = root / "result.json"
            row["prior_evidence_sha256"] = hashlib.sha256(previous_case.read_bytes()).hexdigest()
            previous = json.loads(previous_case.read_text(encoding="utf-8"))
            row["goal_exactly_matches_cycle_1"] = previous["goal"] == goal
            if not row["goal_exactly_matches_cycle_1"]:
                raise AssertionError("Original public goal string changed; comparison refused")
        fixture.observe("file.read", "file.write", "file.stat")
        fixture.start()
        key = fixture.submit(goal)
        row["workflow_id"] = key
        detail = drive(fixture, key, row)
        row["final_detail"] = detail
        row["persisted_timing"] = persisted_timing(detail)
        artifact_root = fixture.config.paths.data_dir / "workflows" / "artifacts" / key
        outputs = []
        for step in detail.get("steps", []):
            path = (step.get("resolved_arguments") or {}).get("path")
            if step["kind"] != "artifact" or not inside(path, artifact_root) or not Path(path).is_file():
                continue
            raw = Path(path).read_bytes()
            independent_read = fixture.registry.execute(ToolRequest("file.read", {"path": path}, source="independent_public_smoke_readback"))
            outputs.append({"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                            "text": Path(path).read_text(encoding="utf-8"),
                            "original_readback_ok": independent_read.ok,
                            "original_readback_text": independent_read.data.get("text") if independent_read.ok else None})
        row["independent_artifacts"] = outputs
        row["handler_entries"] = list(fixture.ledger.rows)
        checks = {"service_completed": detail["status"] == "completed", "saved_owned_artifact": bool(outputs),
                  "original_artifact_readback": bool(outputs) and all(item["original_readback_ok"] for item in outputs)}
        if name == "artifact_roundtrip":
            expected = facts["source"].read_text(encoding="utf-8")
            checks["exact_preserved_text"] = any(item["text"] == expected and isinstance(item["original_readback_text"], str) and item["original_readback_text"].replace("\r\n", "\n") == expected for item in outputs)
            artifact_steps = {step["step_id"] for step in detail.get("steps", []) if step["kind"] == "artifact"}
            checks["planned_original_postwrite_read"] = any(step.get("capability_id") == "file.read" and artifact_steps.intersection(step.get("dependencies", [])) for step in detail.get("steps", []))
        else:
            observations = []
            for item in outputs:
                try:
                    observations.extend(json.loads(item["text"]).get("observations", []))
                except (ValueError, AttributeError):
                    pass
            percentages = [item.get("value") for item in observations if item.get("operation") == "percentage"]
            differences = [item.get("value") for item in observations if item.get("operation") == "difference"]
            # Same public fixture arithmetic oracle: 6/10=60%,9/10=90%,delta30.
            checks["actual_numeric_observations"] = 60 in percentages and 90 in percentages and 30 in differences
            checks["verified_analysis_prerequisite"] = any(step["kind"] == "analysis" and step["status"] == "verified" for step in detail.get("steps", []))
        row["checks"] = checks
        row["passed"] = all(checks.values())
    except Exception as error:
        row["passed"] = False
        row["error"] = {"class": type(error).__name__, "message": str(error)}
    finally:
        fixture.close()
    row["model_calls"] = runtime.client.calls[initial:]
    row["structured_boundaries"] = [{"boundary": boundary(call), "ok": call["ok"]} for call in row["model_calls"]]
    row["full_actual_call_ms_by_boundary"] = {
        name: [call["full_inference_ms"] for call in row["model_calls"] if boundary(call) == name]
        for name in ("outline", "binding", "evidence_report")}
    row["wall_ms"] = (time.perf_counter() - started) * 1000
    row["input_sha256_after"] = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in facts.items() if key in {"source", "valid"}}
    row["input_bytes_unchanged"] = row.get("input_sha256_before") == row["input_sha256_after"]
    if fixtures_root is not None:
        row["prior_evidence_unchanged"] = row.get("prior_evidence_sha256") == hashlib.sha256((root / "result.json").read_bytes()).hexdigest()
    row["passed"] = bool(row.get("passed") and row["input_bytes_unchanged"] and row.get("prior_evidence_unchanged", True))
    dump(case_output / "result.json", row)
    print(json.dumps({"case": name, "passed": row["passed"], "boundaries": row["structured_boundaries"],
                      "state": row.get("final_detail", {}).get("status"), "checks": row.get("checks")}), flush=True)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-file", type=Path, required=True)
    parser.add_argument("--fixtures-root", type=Path, help="Reuse original PUBLIC case directories without rewriting their inputs or evidence")
    args = parser.parse_args()
    output = args.output.resolve()
    fixtures_root = args.fixtures_root.resolve() if args.fixtures_root else None
    if fixtures_root is not None:
        if not fixtures_root.is_dir() or not fixtures_root.is_relative_to((ROOT / "data/hanni-v3-review").resolve()):
            raise SystemExit("Fixture reuse must target an existing isolated public review directory")
        if output == fixtures_root or output.is_relative_to(fixtures_root) or fixtures_root.is_relative_to(output):
            raise SystemExit("New evidence output must be separate from original fixture evidence")
    output.mkdir(parents=True, exist_ok=True)
    with (output / "STARTED.json").open("x", encoding="utf-8") as stream:
        json.dump({"protocol": "Public engineering smoke, no sealed cases or quality/generalization claim"}, stream)
    result = {"before": final_manifest(), "cases": [], "disclosure": "Actual original ModelManager/client and Service/host/registry/handlers; public goals; actual RAM and owned GPU admission; no fabricated model responses. Owner approves only own managed artifacts; independent original file.read checks output. No provider, SSH, power or user files."}
    runtime = OwnedConfiguredRuntime(output / "model-state", args.model_file)
    try:
        with runtime:
            for name in ("artifact_roundtrip", "numeric_report"):
                result["cases"].append(run_case(name, runtime, output, fixtures_root))
                dump(output / "results-in-progress.json", result)
        boundaries = [item for row in result["cases"] for item in row["structured_boundaries"]]
        result["all_three_structured_boundaries_generated"] = all(any(item["boundary"] == name and item["ok"] for item in boundaries) for name in ("outline", "binding", "evidence_report"))
        result["passed"] = all(row["passed"] for row in result["cases"]) and result["all_three_structured_boundaries_generated"]
    finally:
        result["runtime_settings"] = runtime.settings
        result["after"] = final_manifest()
        result["runtime_unchanged"] = result["before"] == result["after"]
        dump(output / "results.json", result)
    return 0 if result.get("passed") and result["runtime_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
