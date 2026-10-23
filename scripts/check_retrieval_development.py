"""Controlled metadata-only comparison against the original M1 host source.

Only explicitly development corpora are loaded. Final holdout is never accessed.
"""
from datetime import datetime
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
import types

from hanni.evals.routing import build_default_host,load_cases,run_benchmark
import hanni.evals.routing as routing_eval
from hanni.evals.llm_tools import load_scenarios, audit_scenarios
import hanni.evals.llm_tools as llm_eval
from hanni.evals.fixtures import fixture_timezone
from hanni.mcp.host import McpHost

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/reliability-v2/development'
BASELINE='ca95b05'
_baseline_class=None

def original_host(registry, current):
    global _baseline_class
    if _baseline_class is None:
        source=subprocess.run(['git','show',BASELINE+':src/hanni/mcp/host.py'],check=True,capture_output=True,text=True,encoding='utf-8').stdout
        module=types.ModuleType('hanni.mcp.development_baseline')
        sys.modules[module.__name__]=module
        exec(compile(source,'M1 host '+BASELINE,'exec'),module.__dict__)
        _baseline_class=module.McpHost
    return _baseline_class(registry,read_only=current.read_only,max_tools=current.max_tools,
                          allowed_actions=tuple(current.allowed_actions),timezone_name=current.timezone_name)

def menu(host,case):
    return host.route(case['query'],history=case.get('history',()),now=datetime.fromisoformat(case.get('now','2026-09-22T10:00:00'))).tools

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='hanni-development-comparison-') as temporary:
        after=build_default_host(data_dir=Path(temporary),timezone_name='America/New_York')
        before=original_host(after.registry,after)
        paths={'historical_scenarios':Path('evals/llm_tools/cases.jsonl'),
               'historical_capability_probes':Path('evals/llm_tools/capability_coverage_v1.jsonl'),
               'unfamiliar_development':ROOT/'evals/retrieval/development_v2.jsonl'}
        corpora={name:load_scenarios(path) for name,path in paths.items()}
        report={'scope':'DEVELOPMENT ONLY; no model, execution or holdout','baseline_commit':BASELINE,
                'conditions':'same process, metadata registry, hardware; three warm passes, five interleaved measured passes','corpora':{}}
        for name,cases in corpora.items():
            after.timezone_name=fixture_timezone(paths[name]) or 'America/New_York'
            before.timezone_name=after.timezone_name
            for _ in range(3):
                for host in (before,after):
                    for case in cases:menu(host,case)
            values={key:{'latency':[],'rows':[]} for key in ('before','after')}
            for repeat in range(5):
                for case in cases:
                    for key,host in (('before',before),('after',after)) if repeat%2==0 else (('after',after),('before',before)):
                        started=time.perf_counter();tools=menu(host,case)
                        values[key]['latency'].append((time.perf_counter()-started)*1000)
                        if repeat:continue
                        selected={t.capability_id for t in tools}
                        required=set(case.get('required_tools',()))
                        groups=[set(g) for g in case.get('required_any_tools',())]
                        hit=len(required & selected)+sum(bool(g&selected) for g in groups)
                        total=len(required)+len(groups)
                        values[key]['rows'].append({'id':case['id'],'query':case['query'],'menu':sorted(selected),
                            'hit':hit,'total':total,'sufficient':hit==total if total else not selected,
                            'schema_chars':sum(len(json.dumps(t.openai_schema())) for t in tools)})
            result={}
            for key,data in values.items():
                rows=data['rows'];positive=[r for r in rows if r['total']];negative=[r for r in rows if not r['total']]
                result[key]={'samples':len(rows),'positive_samples':len(positive),'negative_samples':len(negative),
                    'required_recall':sum(r['hit'] for r in positive)/max(1,sum(r['total'] for r in positive)),
                    'menu_sufficiency':sum(r['sufficient'] for r in positive)/max(1,len(positive)),
                    'correct_no_tool':sum(r['sufficient'] for r in negative)/len(negative) if negative else None,
                    'mean_candidates':statistics.mean(len(r['menu']) for r in rows),
                    'mean_schema_chars':statistics.mean(r['schema_chars'] for r in rows),
                    'p50_ms':statistics.median(data['latency']),
                    'p95_ms':sorted(data['latency'])[int((len(data['latency'])-1)*.95)],'rows':rows}
            report['corpora'][name]=dict(result)
            report['corpora'][name]['timezone']=after.timezone_name
            # Required recall alone can hide extra unmocked capabilities or
            # changed fixed arguments. Retain the complete original audit.
            if name != 'unfamiliar_development':
                audits={}
                for key,host in [('before',before),('after',after)]:
                    original_isolation=llm_eval.isolated_host
                    if key=='before':
                        def baseline_isolation(host,**kwargs):
                            isolated=original_isolation(host,**kwargs)
                            return original_host(isolated.registry,isolated)
                        llm_eval.isolated_host=baseline_isolation
                    try:
                        audit=audit_scenarios(host,cases)
                    finally:
                        llm_eval.isolated_host=original_isolation
                    audits[key]={k:audit[k] for k in ('total_scenarios','routing_coverage_rate',
                                                     'corpus_failures','routed_menus_sha256')}
                report['corpora'][name]['complete_corpus_audit']=audits
                print(name+'_complete_audit',json.dumps({key:{k:v for k,v in row.items()
                     if k!='routed_menus_sha256'} for key,row in audits.items()}))
            print(name,json.dumps({key:{k:v for k,v in row.items() if k!='rows'} for key,row in result.items()}))
        routing=load_cases('evals/routing/cases.jsonl')
        after.timezone_name=fixture_timezone(Path('evals/routing/cases.jsonl'))
        before.timezone_name=after.timezone_name
        for key,host in [('before',before),('after',after)]:
            original_isolation = routing_eval.isolated_host
            if key=='before':
                def baseline_isolation(host,**kwargs):
                    isolated = original_isolation(host,**kwargs)
                    return original_host(isolated.registry,isolated)
                routing_eval.isolated_host = baseline_isolation
            try:
                result=run_benchmark(host,routing)
            finally:
                routing_eval.isolated_host=original_isolation
            report.setdefault('historical_routing',{})[key]={'samples':result.total,'pass_rate':result.pass_rate,'average_score':result.average_score,
                      'failures':[r.to_dict() for r in result.results if not r.passed]}
        print('historical_routing',json.dumps({k:{a:b for a,b in v.items() if a!='failures'} for k,v in report['historical_routing'].items()}))
        (OUT/'controlled-before-after.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

if __name__=='__main__':main()
