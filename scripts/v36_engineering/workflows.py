"""Three sealed goals through the running original authenticated workflow API.

The resident actual model makes every outline/binding/analysis decision. This
harness never writes a plan or substitutes a planner client. Approval is limited
to ordinary reads of its own files and managed report artifacts. Other proposals
are recorded and cancelled without changing production authorization.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from desktop.main import request_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--identity', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--resume-auth-harness', action='store_true', help='Retain initial missing-GET-token harness failure and observe its same already-submitted workflows without replanning.')
    args = p.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT/'data'):
        raise ValueError('Evidence must stay under ignored data.')
    output.mkdir(parents=True, exist_ok=True)
    fixture = output/'fixture'
    fixture.mkdir(exist_ok=True)
    (fixture/'observations.txt').write_text('cobalt lighthouse\nRehearsal has 12 seats; 3 are reserved.\n', encoding='utf-8')
    (fixture/'other.txt').write_text('The synthetic report owner is V36 Fixture.\n', encoding='utf-8')
    goals = [
        {'id':'folder-analysis-report', 'goal':f'Analyze the ordinary text files in {fixture}. Identify their contents and write a concise factual report to the managed workflow artifact folder. Do not run code or change the source files.'},
        {'id':'multi-step-local-task', 'goal':'Create a local task titled V36 rehearsal checklist due tomorrow. Read back the saved task, mark it completed, and verify completion. Use only local task storage; no Google service.'},
        {'id':'memory-continuity', 'goal':'Retrieve what this isolated session already knows about the synthetic cobalt lighthouse project. Distinguish saved memory from unknown details, then write a concise report in the managed workflow artifact folder. Do not invent or change memories.'},
    ]
    encoded = json.dumps({'version':1,'cases':goals,'criterion':'Actual original model planning and verified execution; planning failure is not completed work.'},sort_keys=True,indent=2).encode()
    sealed = output/'sealed-goals.json'
    if sealed.exists() and sealed.read_bytes()!=encoded:
        raise ValueError('Frozen goals changed.')
    if (output/'results.jsonl').exists() and not args.resume_auth_harness:
        raise ValueError('Refuse to overwrite/repeat an evaluated workflow cohort.')
    sealed.write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    sealed.with_suffix('.sha256').write_text(digest+'\n',encoding='ascii')
    identity = json.loads(args.identity.read_text(encoding='utf-8'))
    origin = identity['origin']
    token = request_json(origin,'/api/chat')['token']
    artifacts = Path(identity['data_dir'])/'workflows'/'artifacts'

    def mutation(operation,data):
        return request_json(origin,'/api/workflows',body={'id':str(uuid.uuid4()),'operation':operation,'data':data},token=token,timeout=15)

    def safe_plan(detail):
        for step in detail.get('steps',[]):
            kind,cap,arguments = step.get('kind'),step.get('capability_id'),step.get('arguments') or {}
            if kind=='analysis':
                continue
            if kind=='artifact' and cap=='file.write':
                path = arguments.get('path')
                if not isinstance(path,str) or not Path(path).resolve().is_relative_to(artifacts.resolve()):
                    return False
                continue
            if cap in {'file.read','file.stat','file.list_dir','file.grep','file.head','file.tail','file.composition','disk.folder_size'}:
                paths = [arguments[k] for k in ('root','path') if isinstance(arguments.get(k),str)]
                if not paths or any(not Path(path).resolve().is_relative_to(fixture.resolve()) for path in paths):
                    return False
                continue
            if cap in {'note.list','todo.list','todo.due'}:
                continue
            # Explicit isolated local task writes are authorized by this cohort.
            if cap in {'todo.add','todo.get','todo.complete'} and detail['goal']==goals[1]['goal']:
                continue
            return False
        return bool(detail.get('steps'))

    existing = {r['id']:r for r in (json.loads(line) for line in (output/'results.jsonl').read_text(encoding='utf-8').splitlines())} if args.resume_auth_harness else {}
    result_path = output/('results-auth-resumed.jsonl' if args.resume_auth_harness else 'results.jsonl')
    with result_path.open('x',encoding='utf-8') as handle:
        for case in goals:
            record={'id':case['id'],'goal':case['goal'],'cohort_sha256':digest,'events':[],'verification_status':'PENDING_INDEPENDENT_REVIEW'}
            started=time.monotonic()
            try:
                response=existing[case['id']]['events'][0]['response'] if args.resume_auth_harness else mutation('goal.submit',{'goal':case['goal'],'mode':'assisted'})
                key=response['workflow_id']
                record['workflow_id']=key
                record['events'].append({'operation':'goal.submit','response':response})
                previous=None
                deadline=started+180
                while time.monotonic()<deadline:
                    detail=request_json(origin,f'/api/workflows/{key}',token=token)['workflow']
                    if detail.get('revision')!=previous:
                        record['events'].append({'detail':detail})
                        previous=detail.get('revision')
                    state=detail['status']
                    if state in {'completed','partially_completed','blocked','cancelled','failed'}:
                        record.update(final_status=state,final_detail=detail)
                        break
                    if state=='awaiting_plan_approval':
                        safe=safe_plan(detail)
                        record['safety_review']={'authorized_isolated_plan':safe}
                        if not safe:
                            mutation('cancel',{'workflow_id':key,'expected_revision':detail['revision']})
                            record.update(final_status='BLOCKED_UNSAFE_PROPOSAL',final_detail=detail)
                            break
                        record['events'].append({'operation':'approve_plan','response':mutation('approve_plan',{'workflow_id':key,'expected_revision':detail['revision'],'plan_hash':detail['plan_hash']})})
                    elif state=='ready':
                        record['events'].append({'operation':'start','response':mutation('start',{'workflow_id':key,'expected_revision':detail['revision'],'plan_hash':detail['plan_hash']})})
                    elif state=='awaiting_step_approval':
                        approval=next(a for a in detail['approvals'] if a['state']=='pending' and a.get('kind')=='step')
                        data={k:approval[k] for k in ('step_id','approval_id','plan_hash','argument_hash','definition_hash')}
                        data.update(workflow_id=key,expected_revision=detail['revision'])
                        record['events'].append({'operation':'approve_step','response':mutation('approve_step',data)})
                    elif state=='paused':
                        record.update(final_status='BLOCKED_PAUSED',final_detail=detail)
                        break
                    time.sleep(.1)
                else:
                    detail=request_json(origin,f'/api/workflows/{key}',token=token)['workflow']
                    mutation('cancel',{'workflow_id':key,'expected_revision':detail['revision']})
                    record.update(final_status='FAIL_TIMEOUT',final_detail=detail)
                record['verified_completion']=record.get('final_status')=='completed' and record.get('final_detail',{}).get('verification_status')=='verified'
            except Exception as error:
                record.update(final_status='FAIL',error={'class':type(error).__name__,'message':str(error)})
            record['elapsed_seconds']=time.monotonic()-started
            handle.write(json.dumps(record,ensure_ascii=True,default=str)+'\n');handle.flush()
            print(json.dumps({k:record.get(k) for k in ('id','final_status','verified_completion','elapsed_seconds')}),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
