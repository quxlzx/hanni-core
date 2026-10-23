"""Original scheduler and profiles with disclosed controlled endpoint/history fixtures.

This measures Python queue/aggregation overhead and exact association, not GPU speed.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from hanni.compute import ComputeRegistry, ComputeScheduler
from hanni.config.loader import load_config
from hanni.models.adaptive import AdaptiveModelEngine


def quantiles(values):
    values=sorted(values)
    return {'count':len(values),'p50':statistics.median(values),'p95':values[max(0,__import__('math').ceil(.95*len(values))-1)]}


@contextmanager
def endpoint(model_id):
    entered=threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            body={'/health':{'status':'ok'},'/v1/models':{'data':[{'id':model_id}]},
                  '/props':{'default_generation_settings':{'n_ctx':16384}}}.get(self.path,{})
            self.respond(body)
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            marker=data['messages'][-1]['content']
            if marker=='occupier': entered.set();time.sleep(.65)
            text='' if marker=='disconnect' and model_id=='controlled_A' else marker+':'+model_id
            self.respond({'model':model_id,'choices':[{'message':{'content':text},'finish_reason':'stop'}],
                          'usage':{'prompt_tokens':8,'completion_tokens':5}})
        def respond(self,data):
            body=json.dumps(data).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield {'url':f'http://127.0.0.1:{server.server_port}','entered':entered}
    finally:server.shutdown();server.server_close();thread.join(2)


def scheduler(root, endpoints, *, concurrency=1,reserve=0,retries=0,max_queue=16):
    folder=root/'compute';folder.mkdir(parents=True)
    workers=[{'worker_id':f'worker_{i}','node_id':'local','local_url':value['url'],
              'model_id':f'controlled_{chr(65+i)}','enabled':True,'allowed_categories':['synthetic'],
              'capabilities':['analysis','structured_json'],'concurrency':concurrency,'interactive_reserve':reserve}
             for i,value in enumerate(endpoints)]
    (folder/'deployment.json').write_text(json.dumps({'version':1,'enabled':True,'nodes':[],
        'workers':workers,'policy':{'max_queue':max_queue,'timeout_seconds':3,'max_retries':retries}}))
    service=ComputeScheduler(ComputeRegistry(root));service.refresh()
    for row in workers:service.registry.observe(row['worker_id'],max_context_verified=16384)
    return service


def infer(service,marker,worker_ids=None,**options):
    started=time.perf_counter()
    text,job=service.chat([{'role':'user','content':marker}],workflow_id='sealed-controlled-workflow',
        step_id=marker,invocation_id='sealed_'+marker,categories=['synthetic'],max_tokens=32,
        allowed_worker_ids=worker_ids,**options)
    service.finish(job,{'status':'VERIFIED' if text==marker+':'+job['model_id'] else 'UNVERIFIED'})
    return {'marker':marker,'latency_ms':(time.perf_counter()-started)*1000,'queue_ms':job.get('queue_ms'),
            'passed':text==marker+':'+job['model_id'],'worker_id':job['worker_id'],'job':job}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();assert output.is_relative_to((ROOT/'data/v42-verification').resolve()) and not output.exists()
    output.mkdir(parents=True)
    sealed=ROOT/'data/v42-verification/prospective-20261009-a'
    encoded=(sealed/'protocol.json').read_bytes();digest=hashlib.sha256(encoded).hexdigest()
    assert digest==(sealed/'protocol.sha256').read_text().strip();protocol=json.loads(encoded)
    rows=[]
    with endpoint('controlled_A') as first,endpoint('controlled_B') as second:
        for iteration in range(protocol['repetitions']['queue_each']):
            first['entered'].clear()
            service=scheduler(output/f'hol-{iteration}',[first,second])
            try:
                with ThreadPoolExecutor(max_workers=3) as pool:
                    occupied=pool.submit(infer,service,'occupier',{'worker_0'})
                    assert first['entered'].wait(2)
                    blocked=pool.submit(infer,service,'queued_A',{'worker_0'})
                    deadline=time.monotonic()+1
                    while len(service.waiting)<1 and time.monotonic()<deadline:time.sleep(.001)
                    assert len(service.waiting)==1
                    free=pool.submit(infer,service,'idle_B',{'worker_1'})
                    result=free.result(3);rows.append({'category':'parallel_workflow','iteration':iteration,**result})
                    for future in (occupied,blocked):assert future.result(3)['passed']
                assert all(value==0 for value in service.registry.active.values()) and not service.waiting
            finally:service.close()
        service=scheduler(output/'disconnect',[first,second],retries=1)
        try:
            service.registry.observe('worker_0',latency_ms=1);service.registry.observe('worker_1',latency_ms=100)
            rows.append({'category':'worker_disconnect',**infer(service,'disconnect')})
            assert rows[-1]['worker_id']=='worker_1' and rows[-1]['job']['attempt']==2
        finally:service.close()
        for iteration in range(protocol['repetitions']['queue_each']):
            first['entered'].clear();service=scheduler(output/f'contention-{iteration}',[first],concurrency=2,reserve=1)
            try:
                with ThreadPoolExecutor(max_workers=3) as pool:
                    occupied=pool.submit(infer,service,'occupier')
                    assert first['entered'].wait(2)
                    blocked=pool.submit(infer,service,'background')
                    deadline=time.monotonic()+1
                    while len(service.waiting)<1 and time.monotonic()<deadline:time.sleep(.001)
                    result=infer(service,'interactive',interactive=True)
                    rows.append({'category':'interactive_contention','iteration':iteration,**result})
                    for future in (occupied,blocked):assert future.result(3)['passed']
            finally:service.close()
    config=load_config(ROOT/'config',data_dir=output/'profiles',env={})
    engine=AdaptiveModelEngine(config)
    try:
        payload={'correct':True,'verified_success':True,'latency_ms':100,'queue_ms':0,
            'generation_tps':50,'prompt_tps':100,'error':False,'evidence_sha256':'a'*64,
            'environment':'explicit 5000-row synthetic fixture','created_at':time.time()}
        with engine.lock:
            db=engine._connect();db.executemany('INSERT INTO measurements VALUES(?,?,?,?,?)',
                [(str(i),'local:supervisor','fixture-identity','analysis',json.dumps(payload)) for i in range(5000)]);db.commit()
        timings=[];canonical=None
        for iteration in range(protocol['repetitions']['profile']):
            began=time.perf_counter();value=engine._profiles('local:supervisor','fixture-identity')
            timings.append((time.perf_counter()-began)*1000)
            encoded=json.dumps(value,sort_keys=True)
            if canonical is None:canonical=encoded
            assert encoded==canonical and value['analysis']['sample_count']==5000 and value['analysis']['correct_count']==5000
        rows.append({'category':'adaptive_profile_read','passed':True,'latency_ms_samples':timings,
            'summary':quantiles(timings),'aggregate_sha256':hashlib.sha256(canonical.encode()).hexdigest()})
    finally:engine.close()
    summaries={category:quantiles([row['latency_ms'] for row in rows if row['category']==category])
               for category in ('parallel_workflow','interactive_contention','worker_disconnect')}
    report={'protocol_sha256':digest,'fixture_only':True,'no_gpu_speed_claim':True,'rows':rows,'summaries':summaries,
            'profile_summary':rows[-1]['summary']}
    (output/'results.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({'summaries':summaries,'profile_summary':report['profile_summary'],'all_passed':all(row['passed'] for row in rows)}))


if __name__=='__main__':main()
