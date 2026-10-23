"""Exercise all fixed desktop operations through their original lazy registry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hanni.config.loader import load_config
from hanni.dashboard.features import DesktopFeatures, PRODUCTIVITY_OPERATIONS, NOTIFICATION_OPERATIONS
from hanni.dashboard.memory import OPERATIONS as MEMORY_OPERATIONS
from hanni.memory.store import MemoryStore
from hanni.tools.base import ToolRequest, ToolValidationError, ToolPermissionError, ConfirmationRequired
from hanni.tools.registry import build_default_registry
from hanni.workflows.service import WorkflowService
from scripts.v36_engineering.fixtures import GoogleVault


def descriptor(d):
    return dict(id=d.name, description=d.description, input_schema=d.argument_schema(),
                output_contract=dict(d.output_schema), domain=d.name.split('.')[0],
                permission_level=d.permission_level, risk_level=d.risk_level,
                side_effect=d.side_effect, confirmation_policy='normal registry policy',
                required_dependencies=list(d.prerequisites), handler_module=d.handler.__module__,
                origin='fixed_desktop_adapter', model_availability='BLOCKED: desktop registry is not the conversational controller registry')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=ROOT/'data/v36-campaign/desktop-cycle1')
    opts = p.parse_args()
    root = opts.output.resolve()
    assert root.is_relative_to((ROOT/'data').resolve())
    root.mkdir(parents=True, exist_ok=True)
    config = load_config(ROOT/'config', data_dir=root/'state', env={})
    registry = build_default_registry(config)
    registry.google_access._vault = GoogleVault(grants=())
    registry.google_access._vault.records.clear()
    features = DesktopFeatures(config, registry=registry)
    service = WorkflowService(config.paths.data_dir)
    features.memory_explorer.workflow_reader = service.detail
    workflow = service.store.create('V36 synthetic project continuity record', 'assisted')
    records, created = {}, {}
    def mutate(area, op, data):
        return features.mutate(area, dict(id=str(uuid4()), operation=op, data=data, confirmed=True))
    base = mutate('productivity', 'project.create', {'name': 'V36 continuity project'})['project']
    store = features.memory_store()
    record, _ = store.remember('I prefer brief V36 test status updates.', source='owner_explicit:v36')
    temporary, _ = store.remember('V36 temporary rehearsal is Friday.', source='owner_explicit:v36')
    features.store.ingest([dict(key='v36-notification', category='application', priority='informational',
        title='V36 synthetic notification', message='Fixture record only', target={'screen':'notifications'})])
    notification = features.store.notifications()['items'][0]
    # The source operation sets, not a fixed count, determine the cohort.
    product_order = ['task.create', 'task.update', 'task.delete', 'project.create',
                     'project.update', 'project.delete', 'note.create', 'note.update',
                     'note.delete', 'link.create', 'link.delete', 'workspace.backup']
    notification_order = ['notification.read', 'notification.dismiss', 'notification.clear', 'notification.preferences']
    memory_order = ['correct', 'forget', 'analyze', 'review', 'consolidate',
                    'project.alias', 'project.workflow', 'project.unlink']
    assert set(product_order) == set(PRODUCTIVITY_OPERATIONS)
    assert set(notification_order) == set(NOTIFICATION_OPERATIONS)
    assert set(memory_order) == set(MEMORY_OPERATIONS)
    cohort = [(x,'productivity') for x in product_order]+[(x,'notifications') for x in notification_order]+[(x,'memory') for x in memory_order]
    (root/'protocol.json').write_text(json.dumps({'operations':cohort,
        'ordinary_expectation':'persist exact requested synthetic record change; preserve other rows; independent original-store readback',
        'negative_expectation':'unsupported argument rejected and chat-only profile denied before handler',
        'model_selection':'BLOCKED: fixed desktop adapter registry is separate from conversational tool menu; no fabricated model choice'}, indent=2), encoding='utf-8')
    journal = root/'results.jsonl'
    if journal.exists(): raise SystemExit('Use a fresh output directory; original evidence is immutable')
    try:
        for operation, area in cohort:
            name = ('memory.desktop_' if area == 'memory' else 'workspace.')+operation
            data = {}
            if operation == 'task.create': data={'title':'V36 desktop ordinary task','due':'2030-04-05','course':'V36'}
            elif operation == 'task.update':
                old=created['task']; data={'task_id':old['id'],'expected_fingerprint':old['fingerprint'],
                    'title':'V36 updated task','due':'2030-04-06','course':'V36','priority':'high','project_id':base['id'],'status':'completed'}
            elif operation == 'task.delete':
                old=created['task']; data={'task_id':old['id'],'expected_fingerprint':old['fingerprint']}
            elif operation == 'project.create': data={'name':'V36 disposable project','description':'Synthetic registered operation'}
            elif operation == 'project.update':
                old=created['project'];data={'project_id':old['id'],'expected_fingerprint':old['fingerprint'],'name':'V36 renamed project','description':'Updated synthetic description'}
            elif operation == 'project.delete':
                old=created['project'];data={'project_id':old['id'],'expected_fingerprint':old['fingerprint']}
            elif operation == 'note.create': data={'project_id':base['id'],'title':'V36 receipt','body':'7 of 11 samples passed.'}
            elif operation == 'note.update':
                old=created['note'];data={'note_id':old['id'],'expected_fingerprint':old['fingerprint'],'title':'V36 corrected receipt','body':'9 of 11 samples passed.'}
            elif operation == 'note.delete':
                old=created['note'];data={'note_id':old['id'],'expected_fingerprint':old['fingerprint']}
            elif operation == 'link.create': data={'project_id':base['id'],'label':'V36 local fixture','target':str(root/'fixture.txt'),'kind':'file'}
            elif operation == 'link.delete': data={'link_id':created['link']['id']}
            elif operation in {'notification.read','notification.dismiss'}: data={'notification_id':notification['id']}
            elif operation == 'notification.preferences': data={'categories':{'cluster':False,'application':True}}
            elif operation == 'correct':
                data={'memory_id':record.id,'expected_updated_at':record.updated_at.isoformat(),'content':'I prefer detailed V36 test status updates.','project_id':base['id'],'semantic_status':'statement'}
            elif operation == 'forget': data={'memory_id':temporary.id,'expected_updated_at':temporary.updated_at.isoformat()}
            elif operation == 'analyze': data={'content':'My preferred report format is plain text','project_id':base['id']}
            elif operation == 'review':
                suggestion=store.get_suggestion(created['suggestion']['id']);data={'suggestion_id':suggestion.id,'expected_updated_at':suggestion.updated_at.isoformat(),'action':'approve','edited_content':None}
            elif operation == 'consolidate': data={'project_id':base['id']}
            elif operation == 'project.alias': data={'project_id':base['id'],'expected_fingerprint':base['fingerprint'],'alias':'V36 cobalt lighthouse'}
            elif operation == 'project.workflow': data={'project_id':base['id'],'expected_fingerprint':base['fingerprint'],'workflow_id':workflow['workflow_id']}
            elif operation == 'project.unlink': data={'project_id':base['id'],'expected_fingerprint':base['fingerprint'],'kind':'alias','value':'V36 cobalt lighthouse'}
            row=dict(test_id='v36-A-'+name,capability_id=name,category='A_direct',input_request=data,
                expected_behavior='fixed original operation plus durable readback; negative/authority rejection',
                environment_type='isolated',model_configuration=None,actual_tool_calls=[],
                model_selection_test={'outcome':'BLOCKED','reason':'Fixed desktop registry is separate from model controller; requires explicit UI owner confirmation'},
                verification_status='AWAITING_INDEPENDENT_VERIFIER',fix_reference=None)
            start=time.perf_counter()
            try:
                response=mutate(area,operation,data)
                row['actual_response']=response
                row['actual_tool_calls']=[{'name':name,'args':{'payload':{'data':data}}}]
                for key in ('task','project','note','link','suggestion'):
                    if key in response: created[key]=response[key]
                d=registry.get(name)
                for args, profile, exc_type in [({'unexpected':True},'owner',ToolValidationError),
                    ({'payload':{'id':str(uuid4()),'data':data}},'everyone_else',ToolPermissionError)]:
                    try: registry.execute(ToolRequest(name,args,actor_profile=profile,source='v36-desktop-negative'))
                    except exc_type as exc: row.setdefault('negative_cases',[]).append({'exception_type':type(exc).__name__,'message':str(exc)})
                    else: raise AssertionError('Desktop argument or permission rejection failed')
                snapshot=features.store.snapshot()
                if operation.endswith('.create') and not operation.startswith('notification.'):
                    key=operation.split('.')[0]; saved=created[key]
                    assert any(x['id']==saved['id'] for x in snapshot[key+'s'])
                elif operation.endswith('.delete'):
                    key=operation.split('.')[0];assert all(x['id'] != response['deleted_id'] for x in snapshot[key+'s'])
                elif operation.endswith('.update'):
                    key=operation.split('.')[0]; saved=created[key];fresh=next(x for x in snapshot[key+'s'] if x['id']==saved['id']);assert fresh==saved
                elif operation == 'workspace.backup':
                    with sqlite3.connect(config.paths.data_dir/'workspace-backups'/response['backup_file']) as db: assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
                elif operation.startswith('notification.'):
                    fresh=features.store.notifications()
                    if operation=='notification.preferences': assert fresh['preferences']['categories']['cluster'] is False
                    elif operation=='notification.read': assert next(x for x in fresh['items'] if x['id']==notification['id'])['read']
                    else: assert all(x['dismissed'] for x in fresh['items'])
                elif operation=='correct': assert store.get(record.id).content==data['content']
                elif operation=='forget': assert MemoryStore(store.path).get(temporary.id) is None
                elif operation=='analyze': assert response['created']==1 and store.get_suggestion(created['suggestion']['id']).status=='pending'
                elif operation=='review': assert store.get_suggestion(data['suggestion_id']).status=='approved'
                elif operation=='consolidate': assert response['scanned']>=1 and 'No memory was changed' in response['message']
                elif operation=='project.alias': assert 'V36 cobalt lighthouse' in features.memory_explorer.projects().project(base['id'])['aliases']
                elif operation=='project.workflow': assert any(x['workflow_id']==workflow['workflow_id'] for x in features.memory_explorer.projects().package(base['id'])['workflow_links'])
                elif operation=='project.unlink': assert 'V36 cobalt lighthouse' not in features.memory_explorer.projects().project(base['id'])['aliases']
                assert d.output_schema=={'result':'object'}
                row['outcome']='ISOLATED_PASS';row['failure_category']=None
            except Exception as exc:
                row['outcome']='FAIL';row['failure_category']='execution_or_outcome';row['failure']=str(exc)
            row['latency_seconds']=round(time.perf_counter()-start,4)
            with journal.open('a',encoding='utf-8') as out: out.write(json.dumps(row,ensure_ascii=True,default=str)+'\n')
            print(name,row['outcome'],row.get('failure',''),flush=True)
        extras=[descriptor(d) for d in registry.definitions() if d.name.startswith(('memory.desktop_','workspace.'))]
        (root/'inventory.json').write_text(json.dumps({'count':len(extras),'capabilities':extras},indent=2),encoding='utf-8')
        awareness=features.awareness()
        (root/'awareness.json').write_text(json.dumps(awareness,indent=2),encoding='utf-8')
    finally:
        service.close()
        registry.context.reliability.close()


if __name__=='__main__':main()
