"""Compare sealed cohorts without attributing cache/fixture gains to GPU speed."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[2]
ROOT_DATA=ROOT/'data/v42-verification'


def quantiles(values):
    values=sorted(values)
    return {'count':len(values),'p50':statistics.median(values),'p95':values[__import__('math').ceil(.95*len(values))-1]} if values else None


def reduction(a,b):return round(100*(a-b)/a,3) if a else None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline-suffix',default='20261009-a')
    parser.add_argument('--optimized-suffix',default='20261009-a')
    parser.add_argument('--output-suffix',default='20261009-a')
    args=parser.parse_args()
    suffix=args.output_suffix
    def read(name):
        selected=args.baseline_suffix if name.endswith('baseline') else args.optimized_suffix
        value=json.loads((ROOT_DATA/(name+'-'+selected)/'results.json').read_text())
        assert value.get('pairing_eligible',True), 'Known competing regression workload must not count as a fair paired optimization.'
        return value
    old,new=read('controlled-baseline'),read('controlled-optimized')
    assert old['protocol_sha256']==new['protocol_sha256']
    memold,memnew=read('memory-baseline'),read('memory-optimized')
    assert memold['protocol_sha256']==memnew['protocol_sha256'] and memold['context_sha256']==memnew['context_sha256']
    oldprofile=next(row for row in old['rows'] if row['category']=='adaptive_profile_read')
    newprofile=next(row for row in new['rows'] if row['category']=='adaptive_profile_read')
    assert oldprofile['aggregate_sha256']==newprofile['aggregate_sha256']
    objectives=[]
    for name,a,b in [('independent_worker_queue_latency',old['summaries']['parallel_workflow'],new['summaries']['parallel_workflow']),
                     ('profile_selection_overhead',oldprofile['summary'],newprofile['summary']),
                     ('memory_retrieval_overhead',memold['summary'],memnew['summary'])]:
        objectives.append({'id':name,'baseline':a,'optimized':b,'p50_reduction_percent':reduction(a['p50'],b['p50']),
            'p95_reduction_percent':reduction(a['p95'],b['p95']),'passed_predefined_target':b['p50']<=.5*a['p50'] and (name!='independent_worker_queue_latency' or b['p95']<=.5*a['p95'])})
    a,b=read('local-baseline'),read('local-optimized')
    assert a['protocol_sha256']==b['protocol_sha256'] and a['weights_sha256']==b['weights_sha256']
    assert len(a['rows'])==len(b['rows']) and all(row['passed'] for row in a['rows']+b['rows'])
    cohorts=[]
    for category in sorted({row['category'] for row in a['rows']}):
        targets=[8192,16384] if category=='long_context' else [None]
        for target in targets:
            for warm in (False,True):
                def selected(report):
                    return [row for row in report['rows'] if row['category']==category and row.get('target_context')==target
                            and (row['iteration']>0 if warm else row['iteration']==0)]
                oldrows,newrows=selected(a),selected(b)
                fields={field:{'baseline':quantiles([r[field] for r in oldrows if isinstance(r.get(field),(int,float))]),
                               'optimized':quantiles([r[field] for r in newrows if isinstance(r.get(field),(int,float))])}
                        for field in ('latency_ms','ttft_ms','prompt_tps','generation_tps','retrieval_ms','tool_ms','end_to_end_ms')}
                cohorts.append({'category':category,'target_context':target,'cache_state':'repeat_warm' if warm else 'first_per_workload',
                    'quality_baseline':f'{sum(r["passed"] for r in oldrows)}/{len(oldrows)}','quality_optimized':f'{sum(r["passed"] for r in newrows)}/{len(newrows)}',
                    'timings':fields})
    report={'baseline_suffix':args.baseline_suffix,'optimized_suffix':args.optimized_suffix,
        'objectives':objectives,'any_predefined_target_passed':any(row['passed_predefined_target'] for row in objectives),
        'all_quality_preserved':True,'primary_verified_responses_baseline':len(a['rows']),'primary_verified_responses_optimized':len(b['rows']),
        'baseline_load_time_ms':a['model_load_time_ms'],'optimized_load_time_ms':None,
        'resident_runtime_reused':True,
        'original_owned_startup_receipt_ms':b['model_load_time_ms'],
        'startup_scope':'One baseline owned server load; optimized arm reused that resident runtime and did not repeat startup.',
        'cohorts':cohorts,'controlled_interactive':{'baseline':old['summaries']['interactive_contention'],'optimized':new['summaries']['interactive_contention']},
        'rss_sampled_peak_bytes':{'baseline':a['sampled_process_rss_peak_bytes'],'optimized':b['sampled_process_rss_peak_bytes']},
        'scope':['Controlled queue gain is an original Python/HTTP scheduler improvement, not remoteGPU throughput.',
                 'Exact-profile aggregate and sealed fixed-timestamp recall context digests match before/after.',
                 'Real memory/tool fixture paths, recordIDs/timestamps can differ; authorized information and expectedanswer are equivalent.',
                 'Warm prompt processing uses backend prefixcache; rates must not imply fullprompt reprocessing.',
                 'The first-per-workload prompt is separate from warm repeat, and owned load is separate from first request.',
                 'Same resident primary runtime reused; optimized server load is unknown/not repeated, and inherited startup receipt is not a new observation.',
                 'Sampled RSS reflects the retained runtime and is not proof of memory reduction or true peak VRAM.',
                 'Separate backendqueue, network-only overhead, peakVRAM, energy and remoteGPU comparison remain unavailable.']}
    output=ROOT_DATA/('comparison-'+suffix+'.json');assert not output.exists()
    output.write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({'objectives':objectives,'quality_preserved':report['all_quality_preserved'],'output':str(output)},indent=2))


if __name__=='__main__':main()
