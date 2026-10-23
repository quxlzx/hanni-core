"""Focused owner-language development evaluation (no capability execution)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hanni.evals.routing import build_default_host, load_cases, run_benchmark
from hanni.evals.fixtures import fixture_timezone
from hanni.mcp.host import family_of


DEFAULT_CASES = Path("evals/routing/language_generalization_v2.jsonl")


def summarize(report, cases):
    by_id = {case.id: case for case in cases}
    required = sum(len(case.required) + len(case.required_any) for case in cases)
    found = sum(len(set(by_id[row.case_id].required) & set(row.selected))
                + sum(bool(set(group) & set(row.selected)) for group in by_id[row.case_id].required_any)
                for row in report.results)
    mixed = [row for row in report.results if by_id[row.case_id].family == "mixed"]
    multi_recall = (sum(all(any(tool in row.selected for tool in requirement)
                            for requirement in ([{tool} for tool in by_id[row.case_id].required]
                                                + [set(group) for group in by_id[row.case_id].required_any]))
                        for row in mixed) / len(mixed)) if mixed else None
    no_tool = [row for row in report.results if by_id[row.case_id].mode == "fallback"]
    selected_tool_count = sum(len(row.selected) for row in report.results)
    irrelevant_tool_count = sum(len(row.metrics.get('irrelevant_exposure', ())) for row in report.results)
    by_family = report.family_stats()
    return {
        "cases": report.total,
        "strict_success_percent": round(report.pass_rate, 2),
        "average_score": round(report.average_score, 2),
        "required_tool_recall_percent": round(100 * found / required, 2) if required else 100.0,
        "multi_domain_family_recall_percent": round(100 * multi_recall, 2) if multi_recall is not None else None,
        "no_tool_false_positive_percent": round(100 * sum(bool(row.selected) for row in no_tool) / len(no_tool), 2) if no_tool else 0.0,
        "irrelevant_tool_rate_percent": round(100 * irrelevant_tool_count / selected_tool_count, 2) if selected_tool_count else 0.0,
        "by_family": by_family,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument("--json", type=Path)
    parser.add_argument("--failures", type=int, default=12)
    parser.add_argument("--min-pass-rate", type=float, default=90.0)
    args = parser.parse_args(argv)
    cases = load_cases(args.cases)
    report = run_benchmark(build_default_host(config_dir=args.config,
                                              timezone_name=fixture_timezone(args.cases)), cases)
    summary = summarize(report, cases)
    print(f"HANNI Language Generalization development eval ({args.cases.name})")
    for key, value in summary.items():
        if key != "by_family":
            print(f"{key}: {value}")
    print("By family:")
    for name, stats in summary["by_family"].items():
        print(f"  {name:18} {stats['cases']:3} cases {stats['pass_rate']:6.2f}% strict")
    failed = [row for row in report.results if not row.passed]
    for row in failed[:args.failures]:
        print(f"  FAIL {row.case_id}: {row.query!r} -> {list(row.selected)}; {'; '.join(row.reasons[:3])}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"summary": summary, **report.to_dict()}, indent=2), encoding="utf-8")
    return 0 if report.pass_rate >= args.min_pass_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
