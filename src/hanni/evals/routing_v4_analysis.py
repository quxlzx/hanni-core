"""Vocabulary novelty and routing-confusion audit for development corpora."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from hanni.evals.routing import load_cases


def _grams(text: str, size: int) -> list[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9]+", text.casefold())
    return [tuple(words[i:i + size]) for i in range(len(words) - size + 1)]


def analyze(cases_path: Path, comparisons: tuple[Path, ...], report_path: Path) -> dict:
    cases = load_cases(cases_path)
    previous = [case for path in comparisons for case in load_cases(path)]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    old = {size: {gram for case in previous for gram in _grams(case.query, size)}
           for size in (1, 2, 3)}
    novelty = {}
    for size, label in ((1, "token"), (2, "bigram"), (3, "trigram")):
        current = [gram for case in cases for gram in _grams(case.query, size)]
        unique = set(current)
        novelty[label] = {
            "unique_total": len(unique),
            "unique_new": len(unique - old[size]),
            "unique_new_percent": round(100 * len(unique - old[size]) / len(unique), 2) if unique else 0,
            "occurrence_new_percent": round(100 * sum(gram not in old[size] for gram in current) / len(current), 2)
            if current else 0,
        }
    by_id = {case.id: case for case in cases}
    confusion = Counter()
    exposed = 0
    irrelevant = 0
    for row in report["results"]:
        selected = tuple(row["metrics"].get("families", ()))
        confusion[(by_id[row["id"]].family, "+".join(selected) or "none")] += 1
        exposed += len(row["selected"])
        irrelevant += len(row["metrics"].get("irrelevant_exposure", ()))
    return {
        "corpus": str(cases_path),
        "compared_with": [str(path) for path in comparisons],
        "cases": len(cases),
        "novelty": novelty,
        "strict_success_percent": report["summary"]["strict_success_percent"],
        "required_tool_recall_percent": report["summary"]["required_tool_recall_percent"],
        "mixed_domain_family_recall_percent": report["summary"]["multi_domain_family_recall_percent"],
        "average_menu_size": round(exposed / len(cases), 3) if cases else 0,
        "irrelevant_tool_exposure_percent": round(100 * irrelevant / exposed, 2) if exposed else 0,
        "confusion": [
            {"expected": expected, "selected": selected, "cases": count}
            for (expected, selected), count in sorted(confusion.items())
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("evals/routing/language_generalization_v4.jsonl"))
    parser.add_argument("--compare", type=Path, nargs="+", default=[
        Path("evals/routing/language_generalization_v2.jsonl"),
        Path("evals/routing/language_generalization_v3.jsonl")])
    parser.add_argument("--report", type=Path, default=Path("evals/routing/results/language_generalization_v4.json"))
    parser.add_argument("--json", type=Path, default=Path("evals/routing/results/language_generalization_v4_analysis.json"))
    args = parser.parse_args(argv)
    result = analyze(args.cases, tuple(args.compare), args.report)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "confusion"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
