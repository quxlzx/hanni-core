"""One-shot private final paired evaluation through the original model engine.

Expected answers are loaded exclusively from ignored verifier-owned storage.
No holdout is used for repair, retries, route proof, or production answer maps.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import threading
import time

ROOT = Path(__file__).resolve().parents[2]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    allow_nan=False).encode("utf8")).hexdigest()


def exact(value, expected):
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return value.keys() == expected.keys() and all(exact(value[k], expected[k]) for k in expected)
    if isinstance(expected, list):
        return len(value) == len(expected) and all(exact(a, b) for a, b in zip(value, expected))
    return value == expected


def wilson(successes, count):
    if not count:
        return None
    z, p = 1.96, successes / count
    centre = (p + z*z/(2*count)) / (1 + z*z/count)
    radius = z * math.sqrt(p*(1-p)/count + z*z/(4*count*count)) / (1 + z*z/count)
    return [centre-radius, centre+radius]


def save(path, value):
    pending = path.with_suffix(".tmp")
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf8")
    pending.replace(path)


def run_final(server, protocol_path, destination):
    from hanni.models.adaptive import ModelRequest
    from hanni.workflows.verification import parse_evidence_json
    protocol_path = protocol_path.resolve()
    assert protocol_path.is_relative_to((ROOT / "data/v44-verification").resolve())
    assert not destination.exists()
    protocol = json.loads(protocol_path.read_text(encoding="utf8"))
    frozen = protocol.pop("protocol_sha256")
    assert frozen == digest(protocol)
    engine = server.model_routing
    sources = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted((ROOT / "src/hanni").rglob("*.py"))}
    sources.update({str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted((ROOT / "src/hanni/dashboard/static").rglob("*")) if path.is_file()})
    initial = engine.snapshot()
    report = {"scope": protocol["scope"], "protocol_sha256": frozen,
              "source_sha256": digest(sources), "source_files": sources,
              "started_at": time.time(), "inference_configuration": asdict(engine.config.models.supervisor),
              "routing_settings": deepcopy(initial.get("settings")),
              "model_identities": [{"endpoint_id": row["endpoint_id"], "identity": row["identity"],
                                    "health": row["health"]} for row in initial["endpoints"]],
              "conditions": "Shared externally managed original primary, cache warmness and interactive contention uncontrolled; alternating pairs, one slot, no adaptive-improvement claim from one endpoint.",
              "results": [], "critical_safety_failures": [], "complete": False}
    save(destination, report)
    for ordinal, case in enumerate(protocol["cases"]):
        arms = ["fixed", "adaptive"] if ordinal % 2 == 0 else ["adaptive", "fixed"]
        for arm in arms:
            if (destination.parent / 'stop.json').exists():
                report.update(status='cancelled', finished_at=time.time(), complete=False,
                              remaining_status='NOT TESTED')
                save(destination, report)
                return
            engine.refresh()
            if (destination.parent / 'stop.json').exists():
                report.update(status='cancelled', finished_at=time.time(), complete=False,
                              remaining_status='NOT TESTED')
                save(destination, report)
                return
            request = ModelRequest(task_category=case["category"], complexity=case["complexity"],
                privacy_categories=frozenset({"synthetic"}), capabilities=frozenset({"text", "structured_json"}),
                response_format="json_object", output_tokens=protocol["max_tokens"],
                allow_legacy_default=True, interactive=True)
            telemetry = {}
            row = {"case_id": case["id"], "ordinal": ordinal, "arm": arm,
                   "prompt_sha256": hashlib.sha256(case["prompt"].encode("utf8")).hexdigest(),
                   "started_at": time.time(), "request": asdict(request), "response": None,
                   "error": None, "passed": False}
            began = time.perf_counter()
            cancellation = threading.Event()
            def admit():
                if (destination.parent / 'stop.json').exists():
                    cancellation.set()
                    raise RuntimeError('Owned validation campaign cancelled at original admission boundary.')
            def capture_local(client):
                value = client.chat([{'role': 'user', 'content': case['prompt']}],
                    temperature=protocol['temperature'], top_p=protocol['top_p'],
                    max_tokens=protocol['max_tokens'], response_format={'type': 'json_object'})
                row['transport_response'] = value
                return value
            try:
                row["response"] = engine.execute([{"role": "user", "content": case["prompt"]}],
                    request=request, endpoint_id="local:supervisor" if arm == "fixed" else None,
                    max_fallbacks=0, telemetry=telemetry, temperature=protocol["temperature"],
                    cancellation=cancellation, admission=admit, local_operation=capture_local,
                    top_p=protocol["top_p"], max_tokens=protocol["max_tokens"],
                    response_format={"type": "json_object"})
                parsed = parse_evidence_json(row["response"])
                row["passed"] = exact(parsed, case["expected"])
                row["shape_valid"] = isinstance(parsed, dict) and parsed.keys() == case["expected"].keys()
            except Exception as exc:
                row["error"] = {"type": type(exc).__name__, "message": str(exc)}
                row["shape_valid"] = False
            row["elapsed_ms"] = (time.perf_counter() - began) * 1000
            row["telemetry"] = deepcopy(telemetry)
            eligible = telemetry.get("endpoint_id") == "local:supervisor"
            bounded = row["error"] is None and (telemetry.get("tokens") or {}).get("completion_tokens", 193) <= 192
            row["rubric"] = {"user_intent": 2 if row["shape_valid"] else 0,
                "model_tool_selection": 2 if eligible else 0,
                "factual_accuracy": 2 if row["passed"] else 0,
                "evidence_verification": 2 if row["passed"] else 0,
                "clarity_helpfulness": 1 if row["shape_valid"] else 0,
                "efficiency": 1 if bounded else 0}
            row["quality_score"] = sum(row["rubric"].values())
            if telemetry.get("endpoint_id") and not eligible:
                report["critical_safety_failures"].append({"case_id": case["id"],
                    "arm": arm, "reason": "Unexpected nonlocal dispatch in single-primary final protocol."})
                row["passed"] = False
            report["results"].append(row)
            save(destination, report)
    summary = {}
    for arm in ("fixed", "adaptive"):
        rows = [row for row in report["results"] if row["arm"] == arm]
        times = sorted(row["elapsed_ms"] for row in rows)
        successes = sum(row["passed"] for row in rows)
        summary[arm] = {"cases": len(rows), "successes": successes,
            "success_percent": successes/len(rows)*100,
            "wilson_95_percent": [v*100 for v in wilson(successes, len(rows))],
            "p50_ms": statistics.median(times), "p95_ms": times[math.ceil(.95*len(times))-1],
            "mean_quality_score": statistics.mean(row["quality_score"] for row in rows),
            "errors": sum(row["error"] is not None for row in rows)}
    pairs = [(next(row for row in report["results"] if row["case_id"] == case["id"] and row["arm"] == "fixed"),
              next(row for row in report["results"] if row["case_id"] == case["id"] and row["arm"] == "adaptive"))
             for case in protocol["cases"]]
    summary["paired"] = {"adaptive_only_success": sum(not a["passed"] and b["passed"] for a,b in pairs),
                         "fixed_only_success": sum(a["passed"] and not b["passed"] for a,b in pairs),
                         "adaptive_improvement_demonstrated": False,
                         "reason": "Only one healthy endpoint; n=8; shared external contention. Endpoint placement is identical."}
    report.update(summary=summary, finished_at=time.time(), complete=True)
    save(destination, report)
