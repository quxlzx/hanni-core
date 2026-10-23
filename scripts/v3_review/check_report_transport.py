"""Exposed transport probe: scripted public plan/binding, actual report model."""
import argparse
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.v3_review.check_public_model import boundary, drive, dump, persisted_timing
from scripts.v3_review.fixtures import fixture_facts
from scripts.v3_review.model_adapter import OwnedConfiguredRuntime, final_manifest
from scripts.v3_review.service_fixture import QueuedStructuredClient, ServiceFixture
from hanni.workflows.types import WorkflowLimits
import psutil


class ReportOnlyActualClient:
    def __init__(self, actual, public_planner):
        self.actual, self.public_planner = actual, public_planner
        self.scripted_planning_calls = 0

    def chat(self, messages, **kwargs):
        if "observations" in kwargs["response_format"]["json_schema"]["schema"]["properties"]:
            return self.actual.chat(messages, **kwargs)
        self.scripted_planning_calls += 1
        if self.scripted_planning_calls > 2:
            raise AssertionError("Only original outline/binding may be scripted")
        return self.public_planner.chat(messages, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-file", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "STARTED.json").open("x", encoding="utf-8") as stream:
        json.dump({"scope": "Disclosed public scripted outline/binding; real original REPORT model only. Not end-to-end planning quality."}, stream)
    result = {"before": final_manifest(), "scope": "Original known exposed numeric engineering plan and binding are scripted only; every report is real original model inference, unchanged production prompt/schema/validation/gates."}
    runtime = OwnedConfiguredRuntime(output / "model-state", args.model_file)
    try:
        with runtime:
            root = output / "case"
            facts = fixture_facts(root / "inputs")
            public = runpy.run_path(str(ROOT / "tests/integration/test_workflow_service_verifier.py"))
            queue = QueuedStructuredClient()
            public["numeric_plan"](queue, facts["valid"])
            hybrid = ReportOnlyActualClient(runtime.client, queue)
            limit_config = WorkflowLimits.from_config(runtime.config.hanni.workflows)
            def resources():
                ram = psutil.virtual_memory().percent
                return {"allowed": ram < runtime.config.models.critical_ram_percent, "ram_percent": ram,
                        "cpu_percent": psutil.cpu_percent(), "gpu": None}
            row = {"controls": [], "observed_states": []}
            fixture = ServiceFixture(root, client=hybrid, limits=limit_config, resource_probe=resources)
            try:
                fixture.observe("file.read", "file.write", "file.stat")
                fixture.start()
                key = fixture.submit("Compare both observed runs, compute pass percentages and their improvement, and save the report.")
                detail = drive(fixture, key, row)
                result.update(workflow_id=key, detail=detail, controls=row["controls"],
                              handler_entries=fixture.ledger.rows, scripted_planning_calls=hybrid.scripted_planning_calls,
                              persisted_timing=persisted_timing(detail))
                artifacts = []
                for step in detail.get("steps", []):
                    if step["kind"] == "artifact":
                        path = (step.get("resolved_arguments") or {}).get("path")
                        if path and Path(path).is_file():
                            artifacts.append({"path": path, "text": Path(path).read_text(encoding="utf-8")})
                result["artifacts"] = artifacts
                result["objective_completed"] = detail["status"] == "completed" and any(
                    any(obs.get("operation") == "difference" and obs.get("value") == 30
                        for obs in json.loads(item["text"]).get("observations", [])) for item in artifacts)
            finally:
                fixture.close()
        result["actual_calls"] = runtime.client.calls
        result["report_generation_exercised"] = any(call["ok"] and boundary(call) == "evidence_report" for call in runtime.client.calls)
        result["runtime_grammar_blocker"] = any(not call["ok"] for call in runtime.client.calls) and not result["report_generation_exercised"]
    finally:
        result["runtime_settings"] = runtime.settings
        result["after"] = final_manifest()
        result["runtime_unchanged"] = result["before"] == result["after"]
        dump(output / "results.json", result)
    print(json.dumps({"report_generation_exercised": result.get("report_generation_exercised"),
                      "objective_completed": result.get("objective_completed"),
                      "runtime_grammar_blocker": result.get("runtime_grammar_blocker"),
                      "actual_report_calls": len(runtime.client.calls), "state": result.get("detail", {}).get("status")}))
    return 0 if result.get("report_generation_exercised") and result["runtime_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
