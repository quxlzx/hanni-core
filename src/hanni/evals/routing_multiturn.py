"""Read-only dialogue-routing evaluation; no MCP capability is called."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from hanni.evals.routing import build_default_host
from hanni.evals.fixtures import fixture_timezone


DEFAULT_CASES = Path("evals/routing/multiturn_v1.jsonl")
FIXED_NOW = datetime.fromisoformat("2026-09-24T12:00:00-05:00")


def evaluate(host, dialogues):
    results = []
    for dialogue in dialogues:
        history = []
        turns = []
        for item in dialogue["turns"]:
            decision = host.route(item["query"], history=tuple(history), now=FIXED_NOW)
            selected = [tool.capability_id for tool in decision.tools]
            required = list(item.get("required", []))
            mode = item.get("mode", "tools")
            passed = (set(required) <= set(selected) if mode == "tools" else
                      decision.status == "blocked" and not selected if mode == "blocked" else
                      decision.status == "clarification" and not selected)
            turns.append({"query": item["query"], "required": required, "mode": mode,
                          "selected": selected, "status": decision.status,
                          "confidence": decision.confidence, "passed": passed})
            history.extend(({"role": "user", "content": item["query"]},
                            {"role": "assistant", "content": ""}))
        results.append({"id": dialogue["id"], "family": dialogue["family"],
                        "passed": all(t["passed"] for t in turns), "turns": turns})
    total_turns = sum(len(row["turns"]) for row in results)
    return {"dialogues": len(results), "turns": total_turns,
            "dialogue_success_percent": round(100 * sum(row["passed"] for row in results) / len(results), 2) if results else 0.0,
            "turn_success_percent": round(100 * sum(t["passed"] for row in results for t in row["turns"]) / total_turns, 2) if total_turns else 0.0,
            "results": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument("--json", type=Path, default=Path("evals/routing/results/multiturn_v1.json"))
    args = parser.parse_args(argv)
    dialogues = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = evaluate(build_default_host(config_dir=args.config,
                                         timezone_name=fixture_timezone(args.cases)), dialogues)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Multi-turn routing: {report['dialogues']} dialogues, {report['turns']} turns; "
          f"{report['dialogue_success_percent']:.2f}% dialogue success, {report['turn_success_percent']:.2f}% turn success")
    for row in (row for row in report["results"] if not row["passed"]):
        failures = [t for t in row["turns"] if not t["passed"]]
        print(f"  {row['id']}: " + "; ".join(f"{t['query']!r} -> {t['selected']} ({t['status']})" for t in failures))
    return 0 if all(row["passed"] for row in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
