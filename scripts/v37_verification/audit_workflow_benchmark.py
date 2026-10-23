"""Independently reconcile retained GPU responses with the original workflow DB.

This is read-only. No planner, worker, model, or workflow is executed here.
"""
import hashlib
import argparse
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-dir',type=Path,default=ROOT/'data/v37-manager/workflow-benchmark/cycle3')
    parser.add_argument('--output',type=Path,default=ROOT/'data/v37-verification/workflow-benchmark-independent-audit.json')
    args=parser.parse_args()
    base=args.campaign_dir.resolve()
    destination=args.output.resolve()
    if ROOT/'data' not in base.parents or ROOT/'data' not in destination.parents:
        raise SystemExit('Audit assigned private evidence only.')
    results_path = base / 'results.json'
    results = json.loads(results_path.read_text())
    expected = {'observations':[{'operation':'percentage','sources':[
        {'step_id':'read','path':'/data/text','json_path':'/passed'},
        {'step_id':'read','path':'/data/text','json_path':'/total'}],'value':90}]}
    responses = {}
    for path in base.glob('response-*.json'):
        response = json.loads(path.read_text())
        content = response['choices'][0]['message']['content']
        assert response['choices'][0]['finish_reason'] == 'stop'
        assert json.loads(content) == expected
        digest = hashlib.sha256(content.encode()).hexdigest()
        responses.setdefault(digest, []).append({'artifact_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'model_id':response['model'],'cached_tokens':response['usage']['prompt_tokens_details']['cached_tokens'],
            'prompt_tokens':response['usage']['prompt_tokens'],'completion_tokens':response['usage']['completion_tokens']})
    db_path = ROOT / 'data/v37-manager/preview/state/workflows/workflows.sqlite3'
    views = []
    with sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro',uri=True) as db:
        for campaign in results:
            workflow_id = campaign['workflow_id']
            status = db.execute('SELECT status FROM workflows WHERE id=?',(workflow_id,)).fetchone()[0]
            assert campaign['status'] == status == 'completed'
            steps = {json.loads(row[0])['step_id']:json.loads(row[0])
                     for row in db.execute('SELECT payload FROM steps WHERE workflow_id=?',(workflow_id,))}
            count=len(campaign['jobs'])
            assert count in {2,3} and len(steps) == count+1 and all(step['status'] == 'verified' for step in steps.values())
            assert json.loads(steps['read']['result']['data']['text']) == {'passed':9,'total':10}
            for job in campaign['jobs']:
                assert job['workflow_id'] == workflow_id and job['state'] == job['verification_status'] == 'VERIFIED'
                assert job['output_sha256'] in responses
                step = steps[job['step_id']]
                assert step['verification']['status'] == 'VERIFIED'
                assert step['verification']['scope'] == 'cited_observations_and_calculations'
                assert step['result']['data']['report'] == expected
                invocation_row = db.execute('SELECT workflow_id,step_id,state,payload FROM invocations WHERE id=?',
                                             (job['invocation_id'],)).fetchone()
                assert invocation_row[:3] == (workflow_id,job['step_id'],'finished')
                invocation = json.loads(invocation_row[3])
                assert invocation['result']['data']['report'] == expected and invocation['write'] is False
            jobs=campaign['jobs']
            overlap = min(job['finished_at'] for job in jobs) - max(job['started_at'] for job in jobs)
            if campaign['mode'] == 'parallel':
                assert overlap > 0 and len({job['worker_id'] for job in jobs}) == count
            else:
                ordered=sorted(jobs,key=lambda job:job['started_at'])
                assert all(a['finished_at']<=b['started_at'] for a,b in zip(ordered,ordered[1:]))
            views.append({'mode':campaign['mode'],'duration_seconds':campaign['duration_seconds'],
                'workflow_id':workflow_id,'verified_steps':count+1,'verified_jobs':count,'execution_overlap_seconds':max(0,overlap),
                'worker_ids':[job['worker_id'] for job in campaign['jobs']],
                'completion_tokens':sum(job['tokens']['completion_tokens'] for job in jobs),
                'aggregate_completion_tokens_per_second':sum(job['tokens']['completion_tokens'] for job in jobs)/campaign['duration_seconds'],
                'original_controller_reconciliation':'PASS','real_model_response_checks':'PASS'})
    seq = next(v['duration_seconds'] for v in views if v['mode']=='sequential')
    par = next(v['duration_seconds'] for v in views if v['mode']=='parallel')
    record = {'status':'LIVE_PASS','results_sha256':hashlib.sha256(results_path.read_bytes()).hexdigest(),
        'campaigns':views,'speed_ratio':seq/par,'duration_reduction_percent':100*(seq-par)/seq,
        'response_count':sum(map(len,responses.values())),
        'cache_tokens_in_responses':[response['cached_tokens'] for rs in responses.values() for response in rs],
        'limitations':'One synthetic 9/10 percentage workload, disclosed synthetic planner fixture, existing alternate Q4_K_S and original Strata models, mixed warm/cold KV and runtime state. Observed timing is not universal scaling, uncached throughput or model-quality proof.',
        'database_opened_readonly':True,'inference_performed_by_auditor':False}
    destination.write_text(json.dumps(record,indent=2),encoding='utf8')
    print(json.dumps(record,indent=2))

if __name__ == '__main__':
    main()
