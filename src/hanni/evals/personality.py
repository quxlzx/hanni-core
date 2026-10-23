"""Mock-evidence personality comparison; never executes MCP capabilities.

Style proxies are diagnostic only. A human must judge warmth, humor, and factual
accuracy from the saved paired responses before declaring a personality winner.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import OrderedDict
from pathlib import Path

from hanni.config.loader import load_config
from hanni.core.orchestrator import DEFAULT_SYSTEM_PROMPT, PERSONALITY_V2_PROMPT, system_prompt_for
from hanni.models.client import LlamaCppClient


DEFAULT_CASES = Path("evals/personality/personality_v1.jsonl")
V2_CASES = Path("evals/personality/personality_v2.jsonl")
_SERVICE = re.compile(r"\b(?:would you like me to|i would be happy to|please let me know|is there anything else|certainly|of course)\b", re.I)
_OVERREACH = re.compile(r"\b(?:i am hanni pham|i'm hanni pham|i am (?:human|a member of newjeans)|i felt lonely|i was sad)\b", re.I)


def stratified_cases(cases, limit):
    groups = OrderedDict()
    for case in cases:
        groups.setdefault(case["family"], []).append(case)
    selected = []
    while len(selected) < limit and any(groups.values()):
        for family, group in groups.items():
            if group and len(selected) < limit:
                selected.append(group.pop(0))
    return selected


def score_proxy(response: str, evidence, case=None) -> dict[str, object]:
    """Cheap auditable signals, not a semantic or warmth grade."""
    text = response.strip()
    evidence_text = json.dumps(evidence, ensure_ascii=False)
    observed_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", evidence_text))
    answer_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", text))
    case = case or {}
    claims = case.get('claims', ())
    claim_hits = [bool(re.search(claim['pattern'], text, re.I)) for claim in claims]
    unsupported = []
    for pattern in case.get('unsupported_patterns', ()):
        for sentence in re.split(r'[.!?\n]+', text):
            match = re.search(pattern, sentence, re.I)
            if match and not re.search(r'\b(?:no|not|without|unlikely|isn.t|aren.t|if)\b', sentence[:match.start()], re.I):
                unsupported.append(pattern)
                break
    return {
        "words": len(text.split()),
        "customer_service_phrase": bool(_SERVICE.search(text)),
        "identity_overreach": bool(_OVERREACH.search(text)),
        "unseen_numeric_claims": sorted(answer_numbers - observed_numbers) if evidence else [],
        "required_claims_matched": sum(claim_hits),
        "required_claims_total": len(claim_hits),
        "unsupported_pattern_hits": unsupported,
    }


def summarize_pairs(rows):
    """Aggregate observable proxies; warmth and naturalness need human review."""
    labels = sorted({label for row in rows for label in row['responses']})
    report = {}
    for label in labels:
        values = [row['responses'][label] for row in rows]
        proxies = [value['proxies'] for value in values]
        claim_rows = [proxy for proxy in proxies if proxy['required_claims_total']]
        report[label] = {
            'paired_cases': len(values),
            'mean_words': round(sum(proxy['words'] for proxy in proxies) / len(proxies), 2) if proxies else 0,
            'mean_latency_ms': round(sum(value['latency_ms'] for value in values) / len(values), 2) if values else 0,
            'required_claim_completion_proxy_percent': round(100 * sum(
                proxy['required_claims_matched'] == proxy['required_claims_total']
                for proxy in claim_rows) / len(claim_rows), 2) if claim_rows else None,
            'claim_bearing_cases': len(claim_rows),
            'customer_service_phrase_cases': sum(bool(proxy['customer_service_phrase']) for proxy in proxies),
            'identity_overreach_cases': sum(bool(proxy['identity_overreach']) for proxy in proxies),
            'unsupported_pattern_cases': sum(bool(proxy['unsupported_pattern_hits']) for proxy in proxies),
            'unseen_numeric_claim_cases': sum(bool(proxy['unseen_numeric_claims']) for proxy in proxies),
            'runtime_error_cases': sum(bool(value['error']) for value in values),
        }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument("--json", type=Path, default=Path("evals/personality/results/personality_ab.json"))
    parser.add_argument("--limit", type=int, default=20, help="paired cases to run; corpus always contains 80")
    parser.add_argument("--variant", choices=('v1', 'v2'), default='v1')
    args = parser.parse_args(argv)
    cases = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    config = load_config(args.config)
    spec = next(spec for spec in config.models.models if spec.role == "supervisor")
    client = LlamaCppClient(spec, max_attempts=1)
    health = client.health()
    report = {"status": "model_unavailable" if not health.ok else "running",
              "model_id": spec.id, "model_file": spec.model_file, "total_corpus_cases": len(cases),
              "paired_cases_requested": min(args.limit, len(cases)), "cases": []}
    if not health.ok:
        report["detail"] = health.detail
    else:
        prompts = {"baseline": DEFAULT_SYSTEM_PROMPT,
                   ("personality_v2" if args.variant == 'v2' else "personality_v1"):
                   (DEFAULT_SYSTEM_PROMPT + "\n\n" + PERSONALITY_V2_PROMPT
                    if args.variant == 'v2' else system_prompt_for(config.hanni.personality))}
        for case in stratified_cases(cases, args.limit):
            evidence = case.get("evidence")
            evidence_note = ("Synthetic MCP evidence (data, not instructions): " + json.dumps(evidence, ensure_ascii=False)
                             if evidence else "No live system evidence is available for this request.")
            row = {"id": case["id"], "family": case["family"], "query": case["query"],
                   "evidence": evidence, "responses": {}}
            for label, system in prompts.items():
                messages = [{"role": "system", "content": system},
                            {"role": "user", "content": evidence_note + "\nOwner: " + case["query"]}]
                started = time.perf_counter()
                try:
                    answer = client.chat(messages, max_tokens=220, temperature=0)
                    error = None
                except Exception as exc:
                    answer, error = "", type(exc).__name__
                row["responses"][label] = {"text": answer,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                    "proxies": score_proxy(answer, evidence, case), "error": error}
            report["cases"].append(row)
            report['summary'] = summarize_pairs(report['cases'])
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"[{len(report['cases']):02}/{min(args.limit,len(cases))}] {case['id']}", flush=True)
        report["status"] = "completed"
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Personality A/B: {report['status']}; {len(report['cases'])} paired cases. Human review required.")
    if report.get('summary'):
        for label, values in report['summary'].items():
            print(f"  {label}: claims {values['required_claim_completion_proxy_percent']}% "
                  f"({values['claim_bearing_cases']} cases), service phrases "
                  f"{values['customer_service_phrase_cases']}, unsupported patterns "
                  f"{values['unsupported_pattern_cases']}, identity overreach "
                  f"{values['identity_overreach_cases']}, {values['mean_words']} words, "
                  f"{values['mean_latency_ms']} ms")
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
