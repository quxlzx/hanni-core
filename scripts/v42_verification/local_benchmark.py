"""Repeated real configured-primary inference and authoritative tool/memory checks."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import psutil
import statistics
import sys
import threading
import time
import urllib.request
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from hanni.config.loader import load_config
from hanni.core.orchestrator import TextSession
from hanni.mcp.host import McpHost
from hanni.mcp.session import McpToolSession
from hanni.memory.store import MemoryStore
from hanni.memory.retrieval import ContextAwareRetriever
from hanni.models.client import LlamaCppClient
from hanni.models.resource_manager import snapshot_resources
from hanni.tools.google_access import GoogleAccess
from hanni.tools.registry import build_default_registry
from hanni.workflows.verification import parse_evidence_json


def quantiles(values):
    values=sorted(values)
    return {'count':len(values),'p50':statistics.median(values),'p95':values[max(0,__import__('math').ceil(.95*len(values))-1)]} if values else None


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--session',type=Path,required=True);parser.add_argument('--context',action='store_true')
    args=parser.parse_args();output=args.output.resolve();session=args.session.resolve()
    assert output.is_relative_to((ROOT/'data/v42-verification').resolve()) and not output.exists()
    output.mkdir(parents=True)
    campaign=ROOT/'data/v42-verification/prospective-20261009-a'
    encoded=(campaign/'protocol.json').read_bytes();digest=hashlib.sha256(encoded).hexdigest()
    assert digest==(campaign/'protocol.sha256').read_text().strip();protocol=json.loads(encoded)
    owner=json.loads((session/'ownership.json').read_text());pid=owner['owned_pid']
    config=load_config(ROOT/'config',data_dir=output/'state',env={});spec=config.models.supervisor
    base=spec.endpoint.rstrip('/').removesuffix('/v1');rows=[]
    def request(path,payload=None):
        req=urllib.request.Request(base+path,data=None if payload is None else json.dumps(payload).encode(),
            headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=180) as response:return json.load(response)
    assert LlamaCppClient(spec,max_attempts=1).health().ok
    props=request('/props')
    resource_before=asdict(snapshot_resources())
    peaks=[];stop=threading.Event()
    def monitor():
        process=psutil.Process(pid)
        while not stop.wait(.1):
            try:peaks.append(process.memory_info().rss)
            except psutil.Error:break
    monitoring=threading.Thread(target=monitor,daemon=True);monitoring.start()
    def stream(category,messages,expected,iteration,**extra):
        payload={'model':spec.api_model,'messages':messages,**protocol['settings'],
                 'stream':True,'stream_options':{'include_usage':True},'response_format':{'type':'json_object'}}
        began=time.perf_counter();first=None;content='';usage={};timings={};complete=False
        row={'category':category,'iteration':iteration,'real_inference':True,'passed':False,
             'messages_sha256':hashlib.sha256(json.dumps(messages,sort_keys=True).encode()).hexdigest(),
             'queue_ms':None,'network_ms':None,'retrieval_ms':None,'tool_ms':None,**extra}
        try:
            req=urllib.request.Request(base+'/v1/chat/completions',data=json.dumps(payload).encode(),
                headers={'Content-Type':'application/json','Accept':'text/event-stream'})
            with urllib.request.urlopen(req,timeout=180) as response:
                for line in response:
                    if not line.startswith(b'data:'):continue
                    data=line[5:].strip()
                    if data==b'[DONE]':complete=True;break
                    event=json.loads(data)
                    if event.get('usage'):usage.update(event['usage'])
                    if event.get('timings'):timings.update(event['timings'])
                    choices=event.get('choices') or []
                    if choices:
                        chunk=(choices[0].get('delta') or {}).get('content')
                        if isinstance(chunk,str) and chunk:
                            if first is None:first=(time.perf_counter()-began)*1000
                            content+=chunk
                        if choices[0].get('finish_reason') not in {None,'stop','eos'}:row['truncated']=True
            row.update(response=content,usage=usage,server_timings=timings,
                passed=complete and not row.get('truncated') and parse_evidence_json(content)==expected)
        except Exception as error:row['error_class']=type(error).__name__
        row.update(latency_ms=(time.perf_counter()-began)*1000,ttft_ms=first,
            prompt_tps=timings.get('prompt_per_second'),generation_tps=timings.get('predicted_per_second'))
        print(json.dumps({k:row.get(k) for k in ('category','iteration','passed','latency_ms','ttft_ms','error_class')}),flush=True)
        return row
    try:
        for case in protocol['cases'][:2]:
            for iteration in range(protocol['repetitions'][case['id']]):
                rows.append(stream(case['id'],[{'role':'user','content':case['prompt']}],case['expected'],iteration,
                    start_state='first_after_load' if not rows else 'warm'))
        store=MemoryStore(output/'synthetic-memory.sqlite3')
        case=protocol['cases'][2]
        # Fixed synthetic records include exact source provenance, no owner's actual memories.
        with store._connect() as db:
            for i in range(2000):
                text=f'Synthetic atlas project benchmark neutral filler {i} uses route amber.'
                db.execute('INSERT INTO memories(id,content,normalized_content,memory_type,source,confidence,created_at,updated_at,project_id,semantic_status,source_ref) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (f'm{i}',text,text.casefold(),'fact','synthetic_owner',.8,'2026-10-09T00:00:00+00:00','2026-10-09T00:00:00+00:00','synthetic','statement','sealed-fixture'))
        store.remember(case['record'],source='synthetic_owner',project_id='synthetic',source_ref='sealed-exact-fact')
        retriever=ContextAwareRetriever(store,project_id='synthetic',min_score=25)
        retrieval_samples=[];context_hashes=[]
        for iteration in range(25):
            began=time.perf_counter();context=retriever.retrieve(case['query']);retrieval_samples.append((time.perf_counter()-began)*1000)
            assert case['record'] in context.text
            context_hashes.append(hashlib.sha256(context.text.encode()).hexdigest())
        assert len(set(context_hashes))==1
        for iteration in range(protocol['repetitions']['memory']):
            began=time.perf_counter();context=retriever.retrieve(case['query']);retrieval=(time.perf_counter()-began)*1000
            row=stream('memory',[{'role':'system','content':context.text},{'role':'user','content':case['prompt']}],case['expected'],iteration,retrieval_ms=retrieval)
            row['end_to_end_ms']=row['latency_ms']+retrieval;rows.append(row)
        for iteration in range(protocol['repetitions']['concurrent']):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(stream,'concurrent',[{'role':'user','content':protocol['cases'][0]['prompt']}],protocol['cases'][0]['expected'],iteration,client=i) for i in range(2)]
                rows.extend(future.result() for future in futures)
        class EmptyVault:
            def get(self,account):return None
            def labels(self):return ('personal','school')
            def preferences(self):return {}
        class OfflineGoogle(GoogleAccess):
            def __init__(self,vault=None,transport=None,timezone_name=None):super().__init__(EmptyVault(),transport,timezone_name)
        with patch('hanni.tools.google_access.GoogleAccess',OfflineGoogle):registry=build_default_registry(config)
        source=output/'synthetic-sensor-report.txt';source.write_text('dispatch_code=coral-8427\nSynthetic verification.\n',encoding='utf8')
        client=LlamaCppClient(spec,max_attempts=1)
        try:
            for iteration in range(protocol['repetitions']['tool']):
                tool_session=McpToolSession(TextSession(client),client,McpHost(registry,read_only=True,
                    max_tools=config.hanni.mcp.max_tools_per_turn,allowed_actions=()))
                receipts=[];call=tool_session.host.call
                def observed(tool,arguments,*a,**kw):
                    began=time.perf_counter();result=call(tool,arguments,*a,**kw)
                    receipts.append({'capability_id':tool.capability_id,'duration_ms':(time.perf_counter()-began)*1000,'result':result})
                    return result
                tool_session.host.call=observed
                began=time.perf_counter();row={'category':'tool','iteration':iteration,'real_inference':True,'passed':False}
                try:
                    chunks=tool_session.stream_response(f'Read the file at {source} and tell me its dispatch_code value.')
                    first=None;answer=''
                    for chunk in chunks:
                        if first is None and chunk:first=(time.perf_counter()-began)*1000
                        answer+=chunk
                    exact=[r for r in receipts if r['capability_id']=='file.read' and r['result'].get('ok')]
                    verified=any(r['result'].get('verification',{}).get('status')=='VERIFIED' for r in exact)
                    row.update(response=answer,original_receipts=receipts,trace=tool_session.last_trace,ttft_ms=first,
                        passed=bool(exact) and verified and 'coral-8427' in answer,verified_receipt=verified,
                        tool_ms=sum(r['duration_ms'] for r in receipts),retrieval_ms=0,queue_ms=None,network_ms=None)
                except Exception as error:row['error_class']=type(error).__name__
                row['latency_ms']=(time.perf_counter()-began)*1000;rows.append(row)
                print(json.dumps({k:row.get(k) for k in ('category','iteration','passed','latency_ms','tool_ms','error_class')}),flush=True)
        finally:
            if registry.context.reliability:registry.context.reliability.close()
        if args.context:
            expected={'head':'mica-8427','middle':'tulip-3621','tail':'orbit-7504'}
            for target in protocol['context_targets']:
                count=500
                for _ in range(5):
                    lines=[f'Neutral synthetic filler entry {i:05d} carries marker none.' for i in range(count)]
                    lines.insert(0,'HEAD_CODE=mica-8427');lines.insert(len(lines)//2,'MIDDLE_CODE=tulip-3621');lines.append('TAIL_CODE=orbit-7504')
                    prompt='\n'.join(lines)+'\nRetrieve exact HEAD_CODE, MIDDLE_CODE and TAIL_CODE. Return only {"head":"value","middle":"value","tail":"value"}.'
                    messages=[{'role':'user','content':prompt}]
                    formatted=request('/apply-template',{'messages':messages,'chat_template_kwargs':{'enable_thinking':False}})
                    tokens=request('/tokenize',{'content':formatted['prompt'],'add_special':False,'parse_special':True})['tokens']
                    if .91*target<=len(tokens)<=.98*target:break
                    count=max(1,int(count*.95*target/len(tokens)))
                assert .9*target<=len(tokens)<target-192
                for iteration in range(protocol['repetitions']['context_each']):
                    row=stream('long_context',messages,expected,iteration,target_context=target,tokenizer_prompt_tokens=len(tokens))
                    actual=row.get('usage',{}).get('prompt_tokens')
                    row['passed']=row['passed'] and type(actual) is int and .9*target<=actual<target-192
                    rows.append(row)
        resource_after=asdict(snapshot_resources())
        categories=sorted({row['category'] for row in rows})
        summaries={category:{field:quantiles([row[field] for row in rows if row['category']==category and isinstance(row.get(field),(float,int))])
             for field in ('latency_ms','ttft_ms','prompt_tps','generation_tps','retrieval_ms','tool_ms','end_to_end_ms')} for category in categories}
        report={'protocol_sha256':digest,'weights_sha256':owner['weights_sha256'],'model_load_time_ms':owner['load_time_ms'],
            'properties':props,'resources_before':resource_before,'resources_after':resource_after,
            'sampled_process_rss_peak_bytes':max(peaks) if peaks else None,'rss_sample_interval_seconds':.1,
            'peak_vram_bytes':None,'network_overhead_ms':None,'queue_time_scope':'Backend exposes no separate queue timer; request contention measured end to end, queue metric unknown',
            'gpu_scope':'Pre/post host-wide vendor readings; true peak allocated VRAM and per-request utilization unknown',
            'retrieval_summary':quantiles(retrieval_samples),'retrieval_context_sha256':context_hashes[0],
            'unsupported_context_targets':protocol['unsupported_targets'],'rows':rows,'summaries':summaries}
        (output/'results.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({'all_passed':all(row['passed'] for row in rows),'requests':len(rows),'summaries':summaries}),flush=True)
    finally:stop.set();monitoring.join(2)


if __name__=='__main__':main()
