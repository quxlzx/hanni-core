"""One sealed synthetic streaming request per assigned real worker, measuring TTFT.

Run only after the manager releases context/cohort inference. This uses the
actual authenticated SSH transport to locate loopback endpoints. Role-only,
empty, reasoning and keep-alive events never count as first answer content.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from hanni.compute.registry import ComputeRegistry
from hanni.compute.transport import InferenceTransport

def protocol():
    rng=random.Random(370102)
    expected={'ledger':f'{rng.getrandbits(72):018x}'}
    return {'version':1,'expected':expected,
        'messages':[{'role':'system','content':'Retrieve the exact synthetic ledger value. Return only a JSON object with key ledger.'},
                    {'role':'user','content':'Synthetic streaming case 370102. The value of ledger is '+expected['ledger']+'. Return it exactly.'}],
        'requests_per_worker':1,'max_output_tokens':128,'timeout_seconds':60,
        'ttft_definition':'Client monotonic request start to first nonempty answer content delta, excluding initial role, empty deltas, reasoning, progress and SSE keepalive.',
        'pass_rule':'Complete stop/DONE with exact prospective JSON and registered model identity. No retries or retuning.',
        'cache_rule':'Report actual usage/cache fields when returned; absence stays null. Warm loaded endpoints, not cold startup performance.',
        'structured_format_rule':'No response_format validator: original Strata may buffer validated JSON before streaming, which would obscure TTFT.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal-only',action='store_true')
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--worker-id',action='append')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    seal=ROOT/'data/v37-verification/sealed/streaming-protocol.json'
    encoded=(json.dumps(protocol(),indent=2)+'\n').encode()
    sha=hashlib.sha256(encoded).hexdigest()
    if seal.exists():
        if seal.read_bytes()!=encoded or seal.with_suffix('.sha256').read_text().strip()!=sha:
            raise SystemExit('Prospective streaming protocol changed.')
    else:
        if not args.seal_only:
            raise SystemExit('Seal the prospective expectations before assigning inference.')
        seal.write_bytes(encoded);seal.with_suffix('.sha256').write_text(sha+'\n')
    if args.seal_only:
        print(json.dumps({'protocol_sha256':sha,'inference_performed':False}));return
    if not args.data_dir or not args.worker_id or not args.output or not 1<=len(args.worker_id)<=3:
        raise SystemExit('Choose explicitly assigned private deployment, up to three workers, and new artifact.')
    base,output=args.data_dir.resolve(),args.output.resolve()
    if ROOT/'data' not in base.parents or ROOT/'data' not in output.parents or output.exists():
        raise SystemExit('Use protected deployment and a new private evidence path.')
    plan=json.loads(encoded)
    record={'protocol_sha256':sha,'status':'BLOCKED','workers':[],
        'source':'Actual OpenAI-compatible streaming endpoints through existing strict SSH/authentication',
        'timing_scope':plan['ttft_definition'],'cache_disclosure':plan['cache_rule'],
        'credentials_logged':False,'private_context_transmitted':False,'requests_retried':False}
    registry=ComputeRegistry(base);transport=InferenceTransport(registry)
    output.parent.mkdir(parents=True,exist_ok=True)
    def save():output.write_text(json.dumps(record,indent=2),encoding='utf8')
    save()
    try:
        for key in args.worker_id:
            worker=registry.worker(key)
            item={'worker_id':key,'passed':False,'ttft_ms':None,'latency_ms':None,
                  'usage':None,'cached_tokens':None,'raw_events':[]}
            record['workers'].append(item);save()
            try:
                health=transport.health(worker)
                item['health']=health
                if health['status']!='healthy' or health['model_id']!=worker['model_id']:
                    raise RuntimeError('Assigned exact model is not healthy.')
                secret=transport.auth.get(key) if worker.get('auth_config_file') else os.environ.get(worker.get('api_key_env',''))
                headers={'Authorization':'Bearer '+secret} if secret else {}
                payload={'model':worker['model_id'],'messages':plan['messages'],
                    'max_tokens':plan['max_output_tokens'],'temperature':0,'stream':True,
                    'stream_options':{'include_usage':True},'cache_prompt':False,
                    'chat_template_kwargs':{'enable_thinking':False}}
                content=[];finish=None;done=False;observed_models=set();total_bytes=0
                with httpx.Client(timeout=httpx.Timeout(15,connect=3),trust_env=False,follow_redirects=False) as client:
                    started=time.monotonic()
                    with client.stream('POST',transport.endpoint(worker)+'/v1/chat/completions',json=payload,headers=headers) as response:
                        if response.is_redirect:raise RuntimeError('Worker redirect refused.')
                        response.raise_for_status()
                        if 'text/event-stream' not in response.headers.get('content-type',''):
                            raise RuntimeError('Actual endpoint did not return an event stream.')
                        for line in response.iter_lines():
                            if time.monotonic()-started>plan['timeout_seconds']:
                                raise RuntimeError('Bounded streaming deadline expired.')
                            total_bytes+=len(line.encode())
                            if total_bytes>1048576 or len(item['raw_events'])>4096:
                                raise RuntimeError('Streaming response exceeds bounded capture.')
                            if not line.startswith('data:'):continue
                            data=line[5:].strip()
                            if data=='[DONE]':done=True;break
                            event=json.loads(data);item['raw_events'].append(event)
                            if event.get('error'):raise RuntimeError('Actual model reported a streaming failure.')
                            if event.get('model'):observed_models.add(event['model'])
                            if event.get('usage'):
                                item['usage']=event['usage']
                                item['cached_tokens']=event['usage'].get('prompt_tokens_details',{}).get('cached_tokens')
                            for choice in event.get('choices',[]):
                                text=choice.get('delta',{}).get('content')
                                if isinstance(text,str) and text:
                                    if item['ttft_ms'] is None:item['ttft_ms']=(time.monotonic()-started)*1000
                                    content.append(text)
                                if choice.get('finish_reason'):finish=choice['finish_reason']
                    item['latency_ms']=(time.monotonic()-started)*1000
                item.update(finish_reason=finish,done_event=done,observed_model_ids=sorted(observed_models))
                item['answer']=json.loads(''.join(content))
                item['passed']=(item['answer']==plan['expected'] and finish=='stop' and done
                    and item['ttft_ms'] is not None and observed_models=={worker['model_id']})
            except Exception as error:
                item['error_type']=type(error).__name__
                item['status']='FAIL'
            save()
        record['status']='LIVE_PASS' if all(item['passed'] for item in record['workers']) else 'FAIL'
    finally:
        save();transport.close();registry.close()
    print(json.dumps({'status':record['status'],'workers':[{k:item.get(k) for k in ('worker_id','passed','ttft_ms','latency_ms','cached_tokens','error_type')} for item in record['workers']]}))

if __name__=='__main__':main()
