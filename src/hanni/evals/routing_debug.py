"""Explain deterministic routing state without executing or revealing model reasoning."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hanni.evals.routing import build_default_host
from hanni.tools.language_concepts import conceptual_query
from hanni.tools.routing_intents import clauses, normalize
from hanni.tools.routing_intents import specific_menu
from hanni.tools.intent_prototypes import app_entity, concepts, rank_intents
from hanni.tools.capabilities import diagnostic_subintent


def explain(host, query: str, *, history=()):
    parts = clauses(query)
    decision = host.route(query, history=history)
    clause_details = []
    for part in parts:
        normalized = normalize(conceptual_query(part, history))
        part_decision = host.route(part, history=history)
        candidates = rank_intents(normalized)
        eligible = [row for row in candidates if row.eligible]
        top = eligible[0] if eligible else None
        runner = eligible[1] if len(eligible) > 1 else None
        negative_signals = []
        if "ram" in normalized or "memory" in normalized:
            if not any(word in normalized for word in ("gpu", "vram", "graphics")):
                negative_signals.append("plain_memory_not_gpu_memory")
        if "right now" in normalized or " rn" in normalized:
            if "time" not in normalized and "clock" not in normalized:
                negative_signals.append("recency_not_clock_intent")
        if part_decision.status == "blocked":
            negative_signals.append("permission_or_action_block")
        clause_details.append({
            "normalized_clause": normalized,
            "concepts": sorted(concepts(normalized)),
            "app_entity": app_entity(normalized),
            "hard_rule_candidates": list(specific_menu(normalized)),
            "negative_signals": negative_signals,
            "diagnostic_subintent": (diagnostic_subintent(normalized).name
                                     if diagnostic_subintent(normalized) else None),
            "prototype_candidates": [
                {"name": row.name, "family": row.family, "score": row.score,
                 "similarity": row.similarity, "anchor_boost": row.anchor_boost,
                 "matched_anchors": row.matched_anchors, "total_anchors": row.total_anchors,
                 "eligible": row.eligible}
                for row in candidates[:8]
            ],
            "best_confidence": top.score if top else 0.0,
            "second_best_confidence": runner.score if runner else 0.0,
            "margin": round(top.score - runner.score, 4) if top else 0.0,
            "selected_families": list(part_decision.families),
            "selected_subintents": list(part_decision.subintents),
            "selected_capabilities": [tool.capability_id for tool in part_decision.tools],
        })
    return {
        "normalized_text": normalize(conceptual_query(query, history)),
        "clauses": list(parts),
        "clause_details": clause_details,
        "families": list(decision.families),
        "subintents": list(decision.subintents),
        "selected_tools": [tool.capability_id for tool in decision.tools],
        "fixed_arguments": {tool.capability_id: dict(tool.fixed_arguments) for tool in decision.tools if tool.fixed_arguments},
        "status": decision.status,
        "confidence": decision.confidence,
        "blocked_capabilities": list(decision.blocked_capabilities),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="+")
    parser.add_argument("--config", type=Path, default=Path("config"))
    args = parser.parse_args(argv)
    print(json.dumps(explain(build_default_host(config_dir=args.config), " ".join(args.query)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
