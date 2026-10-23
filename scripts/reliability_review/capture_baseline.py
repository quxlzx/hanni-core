"""Verification-only metadata coverage; never execute capability handlers."""
from __future__ import annotations
import argparse
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    source=a.source.resolve()
    sys.path.insert(0,str(source/"src"))
    from hanni.evals.routing import build_default_host,load_cases,run_benchmark
    from hanni.evals.fixtures import fixture_timezone
    from hanni.mcp.host import classification,family_of
    a.output.mkdir(parents=True,exist_ok=True)
    corpus=source/"evals/routing/cases.jsonl"
    host=build_default_host(config_dir=source/"config",data_dir=a.output/"isolated-data",timezone_name=fixture_timezone(corpus))
    cases=load_cases(corpus)
    start=time.perf_counter()
    report=run_benchmark(host,cases)
    elapsed=time.perf_counter()-start
    test_text={}
    for file in (source/"tests").rglob("test_*.py"):
        test_text[str(file.relative_to(source))]=file.read_text(encoding="utf8")
    rows=[]
    for definition in host.registry.definitions():
        name=definition.name
        mentioned=[path for path,text in test_text.items() if repr(name) in text or json.dumps(name) in text]
        probes=[c for c in cases if name in c.required or name==c.primary or any(name in g for g in c.required_any)]
        selected=[r.case_id for r in report.results if name in r.selected]
        rows.append(dict(capability_id=name,domain=family_of(name),classification=classification(definition),
            permission_level=definition.permission_level,risk_level=definition.risk_level,
            side_effect=definition.side_effect,model_policy_allowed=host._allowed(definition),
            static_test_literal_mentions=mentioned,static_mentions_are_not_execution_proof=True,
            retrieval_annotated_cases=[c.id for c in probes],retrieval_observed_menu_case_ids=selected,
            model_selection_evidence="not measured in this audit",
            actual_handler_execution_evidence="not measured; metadata registry forbids all execution",
            outcome_verification_evidence="not measured; routing cannot establish verified outcome"))
    artifact=dict(scope="Default configured registry metadata; no runtime-attached desktop-management or dynamic MCP registrations assumed",
        source=str(source),corpus_sha256=hashlib.sha256(corpus.read_bytes()).hexdigest(),capability_count=len(rows),
        historical_corpus_is_development=True,corpus_cases=len(cases),strict_passed=sum(r.passed for r in report.results),
        average_score=report.average_score,strict_pass_rate=report.pass_rate,elapsed_seconds=elapsed,
        exact_literal_test_mentions_count=sum(bool(r["static_test_literal_mentions"]) for r in rows),
        observed_retrieval_capabilities=sum(bool(r["retrieval_observed_menu_case_ids"]) for r in rows),capabilities=rows)
    (a.output/"capability-coverage.json").write_text(json.dumps(artifact,indent=2),encoding="utf8")
    (a.output/"historical-routing.json").write_text(json.dumps(report.to_dict(),indent=2),encoding="utf8")
    print(json.dumps({k:v for k,v in artifact.items() if k not in {"source","capabilities"}}))
if __name__=="__main__":main()

