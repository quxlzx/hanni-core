"""Join a saved synthetic LLM benchmark with an explicit human failure review."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from hanni.evals.llm_tools import load_scenarios


DEFAULT_REPORT = Path("evals/llm_tools/results/language_v2_qwen_dev150_final.json")
DEFAULT_REVIEW = Path("evals/llm_tools/dev150_failure_review.json")
DEFAULT_OUTPUT = Path("evals/llm_tools/results/dev150_failure_ledger.json")


def build_ledger(report_path=DEFAULT_REPORT, review_path=DEFAULT_REVIEW):
    report_path, review_path = Path(report_path), Path(review_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in load_scenarios()}
    failed = [row for row in report["results"] if not row["passed"]]
    notes = review["reviews"]
    actual_ids = {row["id"] for row in failed}
    if actual_ids != set(notes):
        raise ValueError(f"Failure review mismatch: missing={sorted(actual_ids - set(notes))}, "
                         f"stale={sorted(set(notes) - actual_ids)}")
    rows = []
    for result in failed:
        case, note = cases[result["id"]], notes[result["id"]]
        rows.append({
            "id": result["id"], "family": result["family"], "query": result["query"],
            "menu": result["selected"], "calls": result["calls"],
            "mock_results": [call["result"] for call in result["calls"]],
            "final_answer": result["final_answer"],
            "expected_evidence": {"required_tools": case.get("required_tools", []),
                                  "required_any_tools": case.get("required_any_tools", []),
                                  "claims": case.get("claims", []),
                                  "arguments": case.get("arguments", {}),
                                  "synthetic_results": case.get("results", {})},
            "failure_classes": result["failure_classification"],
            "root_cause": note["root_cause"],
            "recommended_architectural_layer": note["layer"],
            "review_note": note["note"],
        })
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    return {"status": "reviewed_development_failures", "count": len(rows),
            "source_report": str(report_path), "source_report_sha256": digest(report_path),
            "review_sha256": digest(review_path), "failures": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--json", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    ledger = build_ledger(args.report, args.review)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(f"Reviewed {ledger['count']} failed development cases -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
