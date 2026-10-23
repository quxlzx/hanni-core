"""Measure isolated deterministic routing startup, latency, and Python heap use."""
from __future__ import annotations

import argparse
import json
import statistics
import time
import tracemalloc
from pathlib import Path

from hanni.evals.routing import build_default_host, load_cases


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("evals/routing/language_generalization_v2.jsonl"))
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--json", type=Path, default=Path("evals/routing/results/language_v2_performance.json"))
    args = parser.parse_args(argv)
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    cases = load_cases(args.cases)
    tracemalloc.start()
    started = time.perf_counter()
    host = build_default_host()
    startup_ms = (time.perf_counter() - started) * 1000
    _, startup_peak = tracemalloc.get_traced_memory()
    timings = []
    for _ in range(args.iterations):
        for case in cases:
            started = time.perf_counter()
            host.route(case.query, history=case.history, now=case.now)
            timings.append((time.perf_counter() - started) * 1000)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    sorted_times = sorted(timings)
    report = {"cases": len(cases), "iterations": args.iterations,
              "measurements": len(timings), "startup_ms": round(startup_ms, 2),
              "mean_routing_ms": round(statistics.mean(timings), 3),
              "p50_routing_ms": round(statistics.median(timings), 3),
              "p95_routing_ms": round(sorted_times[min(len(sorted_times)-1, int(len(sorted_times)*0.95))], 3),
              "startup_heap_peak_kb": round(startup_peak/1024, 1),
              "total_python_heap_peak_kb": round(peak/1024, 1),
              "note": "tracemalloc Python heap only; excludes native/model/OS process memory"}
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
