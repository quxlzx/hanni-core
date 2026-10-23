"""Data-driven natural-language routing evaluation for HANNI.

This evaluator intentionally stops *before* capability execution.  It asks the
same MCP host used by text/voice/dashboard which capabilities it would expose,
then scores that retrieval decision against a JSONL corpus.  No Windows command,
Google API, filesystem mutation, or other capability handler is invoked.

The corpus is useful for two distinct stages:

1. HANNI retrieval/routing (implemented here): did natural language produce the
   right bounded tool set and deterministic date/entity arguments?
2. Resident-model tool selection (future/optional): the same cases can be fed to
   a live model after retrieval, while still mocking capability results.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from hanni.config.loader import load_config
from hanni.mcp.host import McpHost, classification, family_of
from hanni.evals.isolation import isolated_host
from hanni.tools.registry import build_default_registry


DEFAULT_CASES = Path("evals/routing/cases.jsonl")


def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


@dataclass(frozen=True, slots=True)
class RoutingCase:
    id: str
    family: str
    query: str
    expected_domain: str
    expected_intent: str
    mode: str = "tools"  # tools | blocked | fallback
    required: tuple[str, ...] = ()
    required_any: tuple[tuple[str, ...], ...] = ()
    acceptable: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    primary: str | None = None
    fixed_arguments: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    fixed_argument_prefixes: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    history: tuple[Mapping[str, Any], ...] = ()
    now: datetime | None = None
    tags: tuple[str, ...] = ()
    irrelevant: tuple[str, ...] = ()
    expected_families: tuple[str, ...] = ()
    expected_subintent: str | None = None
    expected_classifications: Mapping[str, str] = field(default_factory=dict)
    blocked_capabilities: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RoutingCase":
        required_any = tuple(tuple(str(v) for v in group) for group in raw.get("required_any", ()))
        now = raw.get("now")
        if now:
            now = datetime.fromisoformat(str(now))
        return cls(
            id=str(raw["id"]),
            family=str(raw["family"]),
            query=str(raw["query"]),
            expected_domain=str(raw.get("expected_domain", "other")),
            expected_intent=str(raw.get("expected_intent", "unknown")),
            mode='blocked' if raw.get('expected_blocked') else str(raw.get("mode", "tools")),
            required=_tuple(raw.get("required_capabilities", raw.get("required"))),
            required_any=required_any,
            acceptable=_tuple(raw.get("acceptable_capabilities", raw.get("acceptable"))),
            forbidden=_tuple(raw.get("forbidden_capabilities", raw.get("forbidden"))),
            primary=str(raw["primary"]) if raw.get("primary") else None,
            fixed_arguments=dict(raw.get("expected_resolved_arguments", raw.get("fixed_arguments", {}))),
            fixed_argument_prefixes=dict(raw.get("fixed_argument_prefixes", {})),
            history=tuple(raw.get("history", ())),
            now=now,
            tags=_tuple(raw.get("tags")),
            irrelevant=_tuple(raw.get('irrelevant_capabilities')),
            expected_families=_tuple(raw.get('expected_families', raw.get('expected_family'))),
            expected_subintent=raw.get('expected_subintent'),
            expected_classifications=dict(raw.get('expected_classifications', {})),
            blocked_capabilities=_tuple(raw.get('blocked_capabilities')),
            allowed_actions=tuple(raw['allowed_actions']) if 'allowed_actions' in raw else None,
        )


@dataclass(frozen=True, slots=True)
class RoutingCaseResult:
    case_id: str
    family: str
    query: str
    selected: tuple[str, ...]
    score: float
    target_score: float
    precision_score: float
    argument_score: float
    safety_score: float
    boundedness_score: float
    passed: bool
    reasons: tuple[str, ...]
    metrics: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.case_id,
            "family": self.family,
            "query": self.query,
            "selected": list(self.selected),
            "score": round(self.score, 2),
            "target_score": round(self.target_score, 2),
            "precision_score": round(self.precision_score, 2),
            "argument_score": round(self.argument_score, 2),
            "safety_score": round(self.safety_score, 2),
            "boundedness_score": round(self.boundedness_score, 2),
            "passed": self.passed,
            "reasons": list(self.reasons),
            "metrics": dict(self.metrics),
        }


@dataclass(frozen=True, slots=True)
class RoutingReport:
    results: tuple[RoutingCaseResult, ...]
    coverage: Mapping[str, Any] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def average_score(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / len(self.results)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return 100.0 * sum(1 for r in self.results if r.passed) / len(self.results)

    def family_stats(self) -> dict[str, dict[str, float | int]]:
        grouped: dict[str, list[RoutingCaseResult]] = defaultdict(list)
        for result in self.results:
            grouped[result.family].append(result)
        return {
            family: {
                "cases": len(rows),
                "average_score": round(sum(r.score for r in rows) / len(rows), 2),
                "pass_rate": round(100.0 * sum(1 for r in rows if r.passed) / len(rows), 2),
            }
            for family, rows in sorted(grouped.items())
        }

    def to_dict(self, *, include_results: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "total": self.total,
            "average_score": round(self.average_score, 2),
            "pass_rate": round(self.pass_rate, 2),
            "families": self.family_stats(),
            "coverage": dict(self.coverage),
            "metrics": {key: {'checks': len(values), 'pass_rate': round(100 * sum(values) / len(values), 2)}
                        for key in ('family', 'subintent', 'required_retrieval', 'primary_ranking', 'date_resolution',
                                    'multi_domain', 'classification', 'ambiguity', 'blocked', 'forbidden', 'precision')
                        if (values := [r.metrics[key] for r in self.results if r.metrics.get(key) is not None])},
        }
        if include_results:
            payload["results"] = [r.to_dict() for r in self.results]
        return payload


def load_cases(path: Path | str = DEFAULT_CASES) -> tuple[RoutingCase, ...]:
    path = Path(path)
    cases: list[RoutingCase] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            raw = json.loads(line)
            cases.append(RoutingCase.from_dict(raw))
        except Exception as exc:
            raise ValueError(f"{path}:{lineno}: invalid routing case: {exc}") from exc
    if len({case.id for case in cases}) != len(cases):
        raise ValueError(f'{path}: duplicate routing case IDs')
    return tuple(cases)


def _domain(name: str) -> str:
    if name.startswith("google_calendar."):
        return "google_calendar"
    if name.startswith("gmail."):
        return "gmail"
    if name.startswith(("process.",)):
        return "process"
    if name.startswith(("system.", "gpu.", "disk.", "device.", "net.", "security.", "service.", "startup.", "power.")):
        return "computer"
    if name.startswith(("file.", "archive.")):
        return "files"
    if name.startswith("time."):
        return "time"
    if name.startswith("model."):
        return "model"
    if name.startswith("hanni."):
        return "hanni"
    return name.partition(".")[0] or "other"


def _argument_matches(tools, case: RoutingCase) -> tuple[float, list[str]]:
    checks = 0
    hits = 0
    reasons: list[str] = []
    by_name = {item.capability_id: item for item in tools}
    for capability, expected in case.fixed_arguments.items():
        checks += len(expected)
        selected = by_name.get(capability)
        if selected is None:
            reasons.append(f"missing {capability} for fixed-argument check")
            continue
        for key, value in expected.items():
            if selected.fixed_arguments.get(key) == value:
                hits += 1
            else:
                reasons.append(
                    f"{capability}.{key} expected {value!r}, got {selected.fixed_arguments.get(key)!r}"
                )
    for capability, expected in case.fixed_argument_prefixes.items():
        checks += len(expected)
        selected = by_name.get(capability)
        if selected is None:
            reasons.append(f"missing {capability} for fixed-prefix check")
            continue
        for key, prefix in expected.items():
            actual = selected.fixed_arguments.get(key)
            if isinstance(actual, str) and actual.startswith(prefix):
                hits += 1
            else:
                reasons.append(f"{capability}.{key} expected prefix {prefix!r}, got {actual!r}")
    if checks == 0:
        return 20.0, reasons
    return 20.0 * hits / checks, reasons


def evaluate_case(host: McpHost, case: RoutingCase) -> RoutingCaseResult:
    host = isolated_host(host, allowed_actions=case.allowed_actions)
    decision = host.route(case.query, history=case.history, now=case.now)
    tools = decision.tools
    selected = tuple(tool.capability_id for tool in tools)
    selected_set = set(selected)
    reasons: list[str] = []

    # 35 points: required target retrieval. Blocked cases require zero tools.
    if case.mode == "blocked":
        target = 35.0 if not selected else 0.0
        if selected:
            reasons.append(f"blocked request exposed tools: {', '.join(selected)}")
    elif case.mode == "fallback":
        target = 35.0 if not selected else 17.5
        if selected:
            reasons.append("fallback request unexpectedly matched capability tools")
    else:
        requirements = len(case.required) + len(case.required_any) + (1 if case.primary else 0)
        hits = 0
        for name in case.required:
            if name in selected_set:
                hits += 1
            else:
                reasons.append(f"missing required capability {name}")
        for group in case.required_any:
            if selected_set.intersection(group):
                hits += 1
            else:
                reasons.append(f"missing one-of capability group {group}")
        if case.primary:
            if selected and selected[0] == case.primary:
                hits += 1
            else:
                reasons.append(f"primary expected {case.primary}, got {selected[0] if selected else '<none>'}")
        target = 35.0 if requirements == 0 and selected else (35.0 * hits / requirements if requirements else 0.0)

    # 20 points: precision. Tools outside required/acceptable groups count as noise.
    allowed = (set(case.required) | set(case.acceptable)) - set(case.irrelevant)
    for group in case.required_any:
        allowed.update(group)
    if case.mode in {"blocked", "fallback"}:
        precision = 20.0 if not selected else 0.0
    elif not selected:
        precision = 0.0
    elif not allowed:
        precision = 20.0
    else:
        relevant = sum(1 for name in selected if name in allowed)
        precision = 20.0 * relevant / len(selected)
        noisy = [name for name in selected if name not in allowed]
        if noisy:
            reasons.append(f"irrelevant exposure: {', '.join(noisy)}")

    argument, arg_reasons = _argument_matches(tools, case)
    reasons.extend(arg_reasons)

    # 20 points: forbidden capability / action safety and expected domain isolation.
    forbidden_hits = sorted(selected_set.intersection(case.forbidden))
    safety = 20.0
    if forbidden_hits:
        safety = 0.0
        reasons.append(f"forbidden capability exposed: {', '.join(forbidden_hits)}")
    elif case.mode == "blocked" and selected:
        safety = 0.0
    elif case.expected_domain and selected:
        domains = {_domain(name) for name in selected}
        # Mixed cases explicitly opt out by using expected_domain='mixed'.
        if case.expected_domain != "mixed" and case.expected_domain not in domains:
            safety = 10.0
            reasons.append(f"expected domain {case.expected_domain}, got {sorted(domains)}")

    boundedness = 5.0 if len(selected) <= host.max_tools else 0.0
    if not boundedness:
        reasons.append(f"tool budget exceeded: {len(selected)} > {host.max_tools}")

    score = target + precision + argument + safety + boundedness
    # A pass is intentionally strict: no forbidden exposure, all target points,
    # all deterministic arguments, and at least half of precision points.
    passed = target == 35.0 and argument == 20.0 and safety == 20.0 and precision >= 10.0 and boundedness == 5.0
    if case.mode in {"blocked", "fallback"}:
        passed = not selected and safety == 20.0
    checks = {
        'family': set(case.expected_families) <= set(decision.families) if case.expected_families else None,
        'subintent': case.expected_subintent in decision.subintents if case.expected_subintent else None,
        'required_retrieval': set(case.required) <= selected_set and all(selected_set.intersection(g) for g in case.required_any) if case.mode == 'tools' else None,
        'primary_ranking': bool(selected and selected[0] == case.primary) if case.primary else None,
        'date_resolution': argument == 20 if case.fixed_arguments or case.fixed_argument_prefixes else None,
        'multi_domain': set(case.expected_families) <= set(decision.families) if len(case.expected_families) > 1 else None,
        'classification': all(classification(host.registry.get(n)) == value for n, value in case.expected_classifications.items()) if case.expected_classifications else None,
        'ambiguity': not selected and decision.confidence == 'low' if case.mode == 'fallback' else None,
        'blocked': not selected and decision.status == 'blocked' and set(case.blocked_capabilities) <= set(decision.blocked_capabilities) if case.mode == 'blocked' else None,
        'forbidden': not forbidden_hits,
        'precision': precision == 20,
    }
    # New annotation checks strengthen strict scoring; the original numerical
    # weights and precision threshold stay unchanged for longitudinal comparison.
    for key in ('family', 'subintent', 'classification', 'ambiguity', 'blocked'):
        if checks[key] is False:
            passed = False
            reasons.append(f'{key} classification mismatch')
    checks.update(status=decision.status, confidence=decision.confidence, families=list(decision.families),
                  subintents=list(decision.subintents), blocked_capabilities=list(decision.blocked_capabilities),
                  irrelevant_exposure=[n for n in selected if n not in allowed], forbidden_exposure=forbidden_hits,
                  fixed_arguments={t.capability_id: dict(t.fixed_arguments) for t in tools if t.fixed_arguments})
    return RoutingCaseResult(
        case_id=case.id,
        family=case.family,
        query=case.query,
        selected=selected,
        score=score,
        target_score=target,
        precision_score=precision,
        argument_score=argument,
        safety_score=safety,
        boundedness_score=boundedness,
        passed=passed,
        reasons=tuple(reasons),
        metrics=checks,
    )


def run_benchmark(host: McpHost, cases: Sequence[RoutingCase]) -> RoutingReport:
    results = tuple(evaluate_case(host, case) for case in cases)
    return RoutingReport(results, capability_coverage(host, cases, results))


def capability_coverage(host, cases, results):
    by_id = {r.case_id: r for r in results}
    rows = []
    for definition in host.registry.definitions():
        name = definition.name
        probes = [c for c in cases if name in c.required or c.primary == name or name in c.blocked_capabilities]
        rows.append(dict(name=name, family=family_of(name), classification=classification(definition),
            side_effect=definition.side_effect, exposed=host._allowed(definition),
            has_routing_test=bool(probes), number_of_routing_cases=len(probes),
            aliases_tested=[c.query for c in probes], case_ids=[c.id for c in probes],
            reachable=any(name in by_id[c.id].selected for c in probes),
            correctly_blocked=any(name in by_id[c.id].metrics.get('blocked_capabilities', []) and by_id[c.id].passed for c in probes),
            passing_cases=sum(by_id[c.id].passed for c in probes)))
    missing = [r['name'] for r in rows if not r['has_routing_test']]
    unverified = [r['name'] for r in rows if r['has_routing_test'] and not (r['reachable'] or r['correctly_blocked'])]
    return dict(total=len(rows), missing=missing, unverified=unverified, capabilities=rows)


def build_default_host(*, config_dir: Path = Path("config"), data_dir: Path = Path("data/eval-routing"),
                       timezone_name: str | None = None) -> McpHost:
    config = load_config(config_dir, data_dir=data_dir, env={})
    registry = build_default_registry(config)
    mcp = config.hanni.mcp
    return isolated_host(McpHost(registry, read_only=mcp.read_only, max_tools=mcp.max_tools_per_turn,
                   allowed_actions=mcp.allowed_actions, timezone_name=timezone_name))


def _format_report(report: RoutingReport, *, failures: int = 12) -> str:
    lines = [
        f"HANNI Routing Eval: {report.total} cases",
        f"Average score: {report.average_score:.2f}/100",
        f"Strict pass rate: {report.pass_rate:.2f}%",
        "",
        "By family:",
    ]
    for family, stats in report.family_stats().items():
        lines.append(f"  {family:24} {stats['cases']:4} cases  score {stats['average_score']:6.2f}  pass {stats['pass_rate']:6.2f}%")
    failed = [r for r in report.results if not r.passed]
    if failed and failures:
        lines.extend(["", f"First {min(failures, len(failed))} failures:"])
        for row in failed[:failures]:
            lines.append(f"  {row.case_id}: {row.query!r}")
            lines.append(f"    selected={list(row.selected)!r} score={row.score:.1f}")
            if row.reasons:
                lines.append(f"    {'; '.join(row.reasons[:3])}")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate HANNI natural-language routing without executing capabilities")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument("--json", type=Path, help="write full JSON report")
    parser.add_argument("--failures", type=int, default=12)
    parser.add_argument('--coverage', type=Path, default=Path('evals/routing/capability-coverage.json'))
    parser.add_argument('--min-pass-rate', type=float, default=85.0)
    args = parser.parse_args(list(argv) if argv is not None else None)
    cases = load_cases(args.cases)
    from hanni.evals.fixtures import fixture_timezone
    host = build_default_host(config_dir=args.config, timezone_name=fixture_timezone(args.cases))
    report = run_benchmark(host, cases)
    print(_format_report(report, failures=args.failures))
    args.coverage.parent.mkdir(parents=True, exist_ok=True)
    args.coverage.write_text(json.dumps(report.coverage, indent=2), encoding='utf-8')
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    if report.coverage['missing']:
        print('ERROR: ZERO ROUTING COVERAGE: ' + ', '.join(report.coverage['missing']))
        return 2
    if report.coverage['unverified']:
        print('ERROR: UNREACHABLE OR UNVERIFIED BLOCK: ' + ', '.join(report.coverage['unverified']))
        return 2
    return 0 if report.pass_rate >= args.min_pass_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
