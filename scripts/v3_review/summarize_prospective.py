"""Report projection only; never executes cases, model requests or tools."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import jsonschema
from hanni.workflows.planner import OUTLINE_SCHEMA, BINDING_SCHEMA
from hanni.workflows.verification import REPORT_SCHEMA


def interval(success, count):
    if not count:
        return None
    z=1.959963984540054
    p=success/count
    center=(p+z*z/(2*count))/(1+z*z/count)
    radius=z*math.sqrt(p*(1-p)/count+z*z/(4*count*count))/(1+z*z/count)
    return [max(0,center-radius),min(1,center+radius)]


def timing(values):
    values=sorted(v for v in values if isinstance(v,(int,float)) and math.isfinite(v))
    def quantile(q):
        index=(len(values)-1)*q
        lower=int(index)
        return values[lower]+(values[min(lower+1,len(values)-1)]-values[lower])*(index-lower)
    return ({"count":len(values),"mean_ms":statistics.mean(values),"p50_ms":quantile(.5),"p95_ms":quantile(.95)}
            if values else {"count":0,"status":"NOT MEASURED"})


def summarize(result):
    rows=result["rows"]
    positives=[r for r in rows if r["kind"]=="positive"]
    schemas={"outline":OUTLINE_SCHEMA,"binding":BINDING_SCHEMA,"evidence_report":REPORT_SCHEMA}
    calls=Counter()
    valid=Counter()
    call_times={name:[] for name in schemas}
    for row in rows:
        for meta,call in zip(row["boundaries"],row["model_calls"]):
            name=meta["boundary"]
            calls[name]+=bool(call["ok"])
            call_times[name].append(call["full_inference_ms"])
            if call["ok"]:
                try:
                    jsonschema.Draft202012Validator(schemas[name]).validate(json.loads(call["returned_json"]))
                    valid[name]+=1
                except (jsonschema.ValidationError, ValueError):
                    pass
    completed=sum(r.get("independent_positive_completed",False) for r in positives)
    return {
        "scope":"Projection of immutable completed once-only evidence; schema validity is not semantic adequacy or compiled original argument/menu validation.",
        "total":len(rows),"positive_count":len(positives),
        "independent_positive_completion":{"success":completed,"count":len(positives),"wilson95":interval(completed,len(positives))},
        "recorded_whole_goal_verified":{"success":sum(r.get('detail',{}).get('status')=='completed' and r.get('recorded_all_required_verified',False) for r in positives),"count":len(positives)},
        "compiled_plans":{"all":sum(r.get('compiled_plan',False) for r in rows),"positive":sum(r.get('compiled_plan',False) for r in positives)},
        "states":dict(Counter(r.get("detail",{}).get("status") for r in rows)),
        "generated_calls":dict(calls),"full_top_level_schema_valid_calls":dict(valid),
        "call_timing_ms":{name:timing(times) for name,times in call_times.items()},
        "planning_endpoint_kinds":dict(Counter(r.get('persisted_timing',{}).get('planning_endpoint_kind') for r in rows)),
        "planning_submitted_to_endpoint":timing([r.get('persisted_timing',{}).get('submitted_to_planning_endpoint_ms') for r in rows]),
        "planning_active_to_endpoint":timing([r.get('persisted_timing',{}).get('active_planning_to_endpoint_ms') for r in rows]),
        "positive_planning_submitted_to_endpoint":timing([r.get('persisted_timing',{}).get('submitted_to_planning_endpoint_ms') for r in positives]),
        "completed_submit_to_finish":timing([r.get('persisted_timing',{}).get('completed_submission_to_finished_ms') for r in positives]),
        "completed_start_to_finish":timing([r.get('persisted_timing',{}).get('completed_started_to_finished_ms') for r in positives]),
        "case_wall":timing([r['wall_ms'] for r in rows]),
        "original_handler_entries":dict(Counter(e['capability_id'] for r in rows for e in r.get('handler_entries',[]) if e['phase']=='entered')),
        "negative_conditions":[{k:r.get(k) for k in ('id','negative_exposed','negative_safety_status','unauthorized_effect_entries')} for r in rows if r['kind']=='negative'],
        "harness_errors":sum('harness_error' in r for r in rows),
        "unchanged":{k:result[k] for k in ('source_unchanged','cases_unchanged','evaluator_unchanged')},
    }


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--result",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    report=summarize(json.loads(args.result.read_text(encoding='utf-8')))
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2,allow_nan=False)
    print(json.dumps(report,indent=2))
