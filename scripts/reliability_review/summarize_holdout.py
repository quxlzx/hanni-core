"""Derive separate metrics from immutable completed before/after artifacts."""
from __future__ import annotations
import argparse,hashlib,json,math,statistics
from pathlib import Path

def metric(passed,total):
    if not total:return {'passed':passed,'total':total,'percent':None,'wilson95_percent':None}
    z=1.959963984540054;p=passed/total;d=1+z*z/total;c=(p+z*z/(2*total))/d;h=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return {'passed':passed,'total':total,'percent':100*p,'wilson95_percent':[100*max(0,c-h),100*min(1,c+h)]}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    cases=[json.loads(line) for line in (args.bundle/'final.jsonl').read_text(encoding='utf8').splitlines()]
    case_bytes=(args.bundle/'final.jsonl').read_bytes()
    normalized=hashlib.sha256(case_bytes.replace(b'\r\n',b'\n')).hexdigest()
    manifest=json.loads((args.bundle/'manifest.json').read_text(encoding='utf8'))
    assert normalized==manifest['sha256'],'Pinned generated LF case-text SHA differs'
    result={'case_sha256':hashlib.sha256(case_bytes).hexdigest(),'case_sha256_lf_text':normalized,
        'newline_provenance':'Initial manifest hashed generated LF text; Windows write_text preserved equivalent CRLF file bytes. Both hashes disclosed; no case/oracle changes.',
        'samples':len(cases),'versions':{},'failures':[]}
    live_sets={}
    for label in ('baseline','final'):
        retrieval=json.loads((args.bundle/(label+'-retrieval.json')).read_text(encoding='utf8'))
        live=json.loads((args.bundle/(label+'-live-results.json')).read_text(encoding='utf8'))
        assert live['completed']==len(cases)==60
        indexed={row['id']:row for row in live['results']};live_sets[label]=indexed
        slots=hits=0
        for row in retrieval['results']:
            if row['mode']!='tools':continue
            selected=set(row['selected']);slots+=len(row['required'])+len(row['required_any'])
            hits+=sum(name in selected for name in row['required'])+sum(bool(selected&set(group)) for group in row['required_any'])
        positives=[indexed[c['id']] for c in cases if c['mode']=='tools'];negatives=[indexed[c['id']] for c in cases if c['mode']=='no_tool']
        exposed=[row for row in positives if row['menu_sufficient']];calls=[call for row in live['results'] for call in row['calls']]
        argument=json.loads((args.bundle/(label+'-model-argument-audit.json')).read_text(encoding='utf8'))
        semantic_calls=[call for call in calls if call['name']=='file.search']
        lats=sorted(row['latency_ms'] for row in live['results']);infer=[row['model_inference_ms'] for row in live['results'] if row['model_menu_rounds']]
        result['versions'][label]={'retrieval':retrieval['summary'],'required_slot_recall':metric(hits,slots),
            'positive_pipeline_tool_selection':metric(sum(row['selection_correct'] for row in positives),len(positives)),
            'conditional_model_selection_given_complete_menu':metric(sum(row['selection_correct'] for row in exposed),len(exposed)),
            'negative_no_handler_execution':metric(sum(row['selection_correct'] for row in negatives),len(negatives)),
            'structural_model_arguments':metric(argument['schema_valid_calls'],argument['raw_calls']),
            'semantic_file_search_arguments_only':metric(sum(call['semantic_arguments_correct'] for call in semantic_calls),len(semantic_calls)),
            'controlled_selection_plus_lexical_evidence':metric(sum(row['controlled_task_complete'] for row in live['results']),len(cases)),
            'unsafe_adapter_entries':sum(row['forbidden_executions'] for row in live['results']),'actual_adapter_entries':len(calls),
            'task_latency':{'mean_ms':statistics.mean(lats),'p50_ms':statistics.median(lats),'p95_ms':lats[math.ceil(.95*len(lats))-1],'samples':len(lats)},
            'tool_model_inference_sum_per_case':{'p50_ms':statistics.median(infer),'p95_ms':sorted(infer)[math.ceil(.95*len(infer))-1],'samples':len(infer)},
            'verified_user_task_completion':'NOT_MEASURED by this language/model fixture','time_to_verified_outcome':'NOT_MEASURED',
            'limits':'Semantic arguments only check expected file search terms; other safe adapter arguments are not independently semantic-oracle checked. Model-inference sum excludes fallback/plain chat and cases without tool rounds.'}
    for case in cases:
        before=live_sets['baseline'][case['id']];after=live_sets['final'][case['id']]
        if not after['controlled_task_complete'] or before['controlled_task_complete']!=after['controlled_task_complete']:
            result['failures'].append({'id':case['id'],'category':case['category'],'query':case['query'],
                'before_menu':before['menu_sufficient'],'after_menu':after['menu_sufficient'],
                'before_selection':before['selection_correct'],'after_selection':after['selection_correct'],
                'before_evidence_completion':before['controlled_task_complete'],'after_evidence_completion':after['controlled_task_complete'],
                'after_actual_capabilities':[call['name'] for call in after['calls']],
                'after_answer':after['answer'],'after_error':after['error']})
    result['oracle_sha256']={label:json.loads((args.bundle/(label+'-live-results.json')).read_text(encoding='utf8'))['oracle_sha256'] for label in ('baseline','final')}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({key:value for key,value in result.items() if key!='failures'},indent=2))

if __name__=='__main__':main()
