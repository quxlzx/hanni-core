"""Report-only supplemental oracle; never starts a service or alters run evidence."""
import argparse
from datetime import datetime
import json
import ntpath
from pathlib import Path


def same_path(first, second):
    return (isinstance(first, str) and isinstance(second, str)
            and ntpath.isabs(first) and ntpath.isabs(second)
            and ntpath.normcase(ntpath.normpath(first)) == ntpath.normcase(ntpath.normpath(second)))


def after(first, second):
    try:
        first, second = (datetime.fromisoformat(value.replace("Z", "+00:00")) for value in (first, second))
        return first.tzinfo is not None and second.tzinfo is not None and second >= first
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False


def evaluate(row, expected_text):
    steps = (row.get("final_detail") or {}).get("steps", [])
    artifacts = {step["step_id"]: step for step in steps if step.get("kind") == "artifact"}
    reads = [step for step in steps if step.get("capability_id") == "file.read"
             and set(step.get("dependencies", [])).intersection(artifacts)]
    evidence = []
    for read in reads:
        result = read.get("result") or {}
        data = result.get("data") or {}
        for artifact_id in set(read.get("dependencies", [])).intersection(artifacts):
            artifact = artifacts[artifact_id]
            path = (artifact.get("resolved_arguments") or {}).get("path")
            item = {
                "artifact_step_id": artifact_id, "read_step_id": read.get("step_id"),
                "actual_saved_artifact": any(same_path(path, output.get("path")) for output in row.get("independent_artifacts", [])),
                "resolved_read_path_matches": same_path(path, (read.get("resolved_arguments") or {}).get("path")),
                "returned_read_path_matches": same_path(path, data.get("path")),
                "read_after_artifact": after(artifact.get("finished_at"), read.get("started_at")),
                "verified_original_read": read.get("status") == "verified" and result.get("name") == "file.read"
                    and result.get("ok") is True and (result.get("verification") or {}).get("status") == "VERIFIED",
                "full_exact_source_text": data.get("truncated") is False and isinstance(data.get("text"), str)
                    and data["text"].replace("\r\n", "\n") == expected_text.replace("\r\n", "\n"),
            }
            item["passed"] = all(value for key, value in item.items() if key not in {"artifact_step_id", "read_step_id"})
            evidence.append(item)
    checks = {"explicit_postartifact_read_present": bool(reads),
              "explicit_saved_artifact_path_and_exact_source_text": any(item["passed"] for item in evidence)}
    return {"checks": checks, "evidence": evidence, "passed": all(checks.values()),
            "scope": "Supplement only; original run/oracles unchanged. Automatic write verification and separate reviewer readback do not count as explicit requested workflow read."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-result", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in {args.case_result.resolve(), args.source.resolve()}:
        raise SystemExit("Supplement output must not overwrite original evidence or inputs")
    row = json.loads(args.case_result.read_text(encoding="utf-8"))
    report = evaluate(row, args.source.read_text(encoding="utf-8"))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
