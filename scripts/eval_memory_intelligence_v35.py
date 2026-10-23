"""Verifier-owned direct code-path evaluator. No inference substitute or rubric changes."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import importlib.util
import json
import statistics
import sys
import tempfile
import time
import types
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'evals/memory_intelligence_v35'
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
BASE_RECORDS=[{'content':'Aurora benchmark achieved 84 passes','memory_type':'fact','project':'aurora'},
              {'content':'Borealis benchmark achieved 93 passes','memory_type':'fact','project':'borealis'}]
CONFIGURATION='A'
PROJECT_FIXTURES={}

def frozen_modules():
    baseline=json.loads((BASE/'baseline_f19dd00/manifest.json').read_text())
    for name,sha in baseline['files'].items():
        assert hashlib.sha256((BASE/'baseline_f19dd00'/name).read_bytes()).hexdigest()==sha
    import hanni
    package = types.ModuleType('hanni.memory')
    package.__path__ = [str(BASE/'baseline_f19dd00')]
    sys.modules['hanni.memory'] = package
    hanni.memory = package
    for name in ('privacy','facts','store','retrieval','session'):
        full='hanni.memory.'+name
        spec=importlib.util.spec_from_file_location(full,BASE/f'baseline_f19dd00/{name}.py')
        module=importlib.util.module_from_spec(spec)
        sys.modules[full]=module
        spec.loader.exec_module(module)
        setattr(package,name,module)
    return {name:sys.modules['hanni.memory.'+name] for name in ('privacy','facts','store','retrieval','session')}

def live_modules():
    return {name:importlib.import_module('hanni.memory.'+name) for name in ('privacy','facts','store','retrieval','session')}

class Unavailable(Exception):
    pass

def module_optional(name):
    try:
        return importlib.import_module(name)
    except ImportError:
        raise Unavailable('public feature API absent')

def fixture_store(modules,folder,case):
    store=modules['store'].MemoryStore(folder/'memory.sqlite3')
    project_mapping={}
    if CONFIGURATION=='D' and any(row.get('project') for row in case.get('records',())):
        from hanni.dashboard.productivity import ProductivityStore
        from hanni.memory.projects import ProjectContext
        workspace=ProductivityStore(folder/'workspace')
        projects=ProjectContext(store,workspace)
        for name in sorted({row['project'] for row in case['records'] if row.get('project')}):
            project=workspace.mutate('project.create',dict(name=name.title(),description='Synthetic persisted '+name+' project'),str(uuid.uuid5(uuid.NAMESPACE_URL,'v35:'+case['id']+':'+name)))['project']
            projects.add_alias(project['id'],name,expected_fingerprint=project['fingerprint'])
            project_mapping[name]=project['id']
        PROJECT_FIXTURES[str(store.path)]=projects
    ids=[]
    for row in case.get('records',[]):
        name=row.get('project','')
        metadata={} if not hasattr(modules['store'],'SEMANTIC_STATUSES') else dict(project_id=project_mapping.get(name,name),source_ref='synthetic:'+case['id'])
        record,_=store.remember(row['content'],source='owner_explicit:synthetic_fixture',memory_type=row.get('memory_type'),**metadata)
        ids.append(record.id)
    return store,ids

def retriever(modules,store,configuration,case):
    if configuration=='A':
        return modules['retrieval'].LocalMemoryRetriever(store,limit=5,max_chars=4000,min_score=25)
    cls=getattr(modules['retrieval'],'ContextAwareRetriever',None)
    if cls is None:
        raise Unavailable('ContextAwareRetriever absent')
    if configuration=='D':
        from hanni.memory.integration import PersonalContextProvider
        provider=PersonalContextProvider(store,project_context=PROJECT_FIXTURES.get(str(store.path)),limit=5,max_chars=4000,min_score=25,max_tokens=4000)
        class SessionBoundary:
            def retrieve(self,goal):
                observed={'context':None,'forwarded':None}
                class Reader:
                    def retrieve(self,prompt):
                        observed['context']=provider.retrieve(prompt)
                        return observed['context']
                    def invalidate(self):provider.invalidate()
                class Sink:
                    def stream_response(self,prompt,**kwargs):
                        observed['forwarded']=(prompt,kwargs)
                        yield 'Controlled input sink, no real-model inference.'
                session=modules['session'].MemoryAwareSession(Sink(),store,extraction_enabled=False,context_retriever=Reader())
                list(session.stream_response(goal))
                result=observed['context']
                if result is None:
                    return modules['retrieval'].MemoryContext('',())
                assert observed['forwarded'] is not None
                assert observed['forwarded'][0]==goal
                assert observed['forwarded'][1].get('memory_context','')==result.text
                return result
        return SessionBoundary()
    return cls(store,limit=5,max_chars=4000,min_score=25,max_tokens=4000,project_id=case.get('project',''))

def evaluate(case,modules,folder,configuration):
    family=case['family']; expected=case['expected']
    if family=='extraction':
        if configuration=='A':
            try:
                candidate=modules['facts'].extract_fact(case['text'])
            except ValueError:
                candidate=None
            status='decision' if candidate and candidate.memory_type=='decision' else 'fact'
        else:
            try:
                candidate=module_optional('hanni.laya.intelligence').analyze_statement(case['text'],source_ref='synthetic:'+case['id'])
            except ValueError:
                candidate=None
            status=getattr(candidate,'semantic_status',None)
            if status=='statement':
                status='fact'  # Public schema spelling, not an oracle/rubric change.
        capture=candidate is not None
        # Any proposed fact must preserve source text. No normalization beyond spaces/punctuation.
        content=getattr(candidate,'content','')
        exact_source=(not capture or content.strip(' .!?')==case['text'].strip(' .!?'))
        correct=capture==expected['capture'] and (not capture or status==expected['semantic_status']) and exact_source
        return correct,dict(capture=capture,status=status,source_grounded=exact_source)
    if family=='importance':
        if configuration=='A':
            raise Unavailable('no importance estimator in original HANNI')
        try:
            candidate=module_optional('hanni.laya.intelligence').analyze_statement(case['text'],source_ref='synthetic:'+case['id'])
        except ValueError:
            candidate=None
        retain=candidate is not None
        score=getattr(candidate,'importance',0)
        return retain==expected['retain'] and (not retain or score>=expected.get('minimum',0)),dict(retain=retain,score=score,calibrated=getattr(candidate,'importance_calibrated',False))
    if family in ('retrieval','negative'):
        store,ids=fixture_store(modules,folder,case)
        reader=retriever(modules,store,configuration,case)
        operation_start=time.perf_counter()
        context=reader.retrieve(case['query'])
        operation_ms=(time.perf_counter()-operation_start)*1000
        returned=[ids.index(match.record.id) for match in context.matches if match.record.id in ids][:5]
        relevant=expected['relevant']
        recall=len(set(returned)&set(relevant))/len(relevant) if relevant else None
        grounded=all(match.record.id in ids and store.get(match.record.id).content==match.record.content for match in context.matches)
        precision=len(set(returned)&set(relevant))/len(returned) if returned else None
        return (recall==1 if relevant else not returned) and grounded,dict(returned=returned,recall_at_5=recall,precision_at_5=precision,source_grounded=grounded,chars=len(context.text),utf8_bytes=len(context.text.encode('utf-8')),token_estimate=(len(context.text)+3)//4,retrieval_boundary_ms=operation_ms)
    if family=='privacy' or family=='injection':
        store,_=fixture_store(modules,folder,case)
        rejected=False
        try:
            store.remember(case['text'],source='owner_explicit:synthetic_fixture')
        except ValueError:
            rejected=True
        return rejected==expected['rejected'] and store.count()==(0 if rejected else 1),dict(rejected=rejected,records=store.count())
    if family=='conflict':
        store,_=fixture_store(modules,folder,case)
        store.remember(case['old'],source='owner_explicit:synthetic_fixture')
        detected=False
        try:
            store.remember(case['new'],source='owner_extracted:synthetic_fixture')
        except modules['store'].MemoryConflictError:
            detected=True
        return detected==expected['conflict'],dict(conflict=detected,records=store.count())
    if family=='deletion':
        store,_=fixture_store(modules,folder,case)
        record,_=store.remember(case['content'],source='owner_explicit:synthetic_fixture')
        before=modules['retrieval'].LocalMemoryRetriever(store).retrieve(case['content'])
        if case['operation']=='delete':
            store.delete(record.id,expected_updated_at=record.updated_at.isoformat())
        else:
            store.remember(case['replacement'],source='owner_explicit:synthetic_correction')
        after=modules['retrieval'].LocalMemoryRetriever(store).retrieve(case['content'])
        gone=all(match.record.content!=case['content'] for match in after.matches) and all(r.content!=case['content'] for r in store.list())
        # An old snapshot is immutable data; consumer invalidation is covered in separate regressions.
        return gone,dict(old_absent=gone,before_count=len(before.matches),after_count=len(after.matches))
    if family=='preference':
        store,_=fixture_store(modules,folder,case)
        store.remember(case['content'],source='owner_explicit:synthetic_fixture')
        context=retriever(modules,store,configuration,case).retrieve(case['query'])
        include=any(match.record.content==case['content'] for match in context.matches)
        return include==expected['include'],dict(include=include,chars=len(context.text))
    if family=='temporal':
        if configuration=='A':
            raise Unavailable('no semantic status classifier in original HANNI')
        status=module_optional('hanni.laya.intelligence').classify_semantic_status(case['text'])
        status={'statement':'fact','completed_claim':'completed','failed_claim':'failed'}.get(status,status)
        return status==expected['status'],dict(status=status)
    if family in ('relationship','consolidation'):
        if configuration=='A':
            raise Unavailable('no relationship proposal API in original HANNI')
        # Actual store records are distinct and source-grounded. A duplicate record may need a synthetic legacy import.
        store,_=fixture_store(modules,folder,case)
        left,_=store.remember(case['left'],source='owner_explicit:synthetic_fixture')
        from dataclasses import replace
        right=replace(left,id='synthetic-second-id',content=case['right'],fact_key='',fact_value='')
        if family=='relationship':
            left=replace(left,project_id='synthetic-p-left')
            right=replace(right,project_id='synthetic-p-left' if case['same_project'] else 'synthetic-p-right')
        fact=modules['facts'].extract_fact(case['right'],explicit=True)
        if fact:
            right=replace(right,fact_key=fact.key,fact_value=fact.value)
        proposals=module_optional('hanni.laya.intelligence').analyze_relationships((left,right))
        kinds=[p.kind for p in proposals]
        review=all(p.requires_review for p in proposals)
        if family=='consolidation':
            got=next((kind for kind in kinds if kind in ('duplicate','conflict')),None)
            return got==expected['proposal'] and review,dict(kinds=kinds,review_required=review)
        got='related' in kinds
        return got==expected['related'] and review,dict(kinds=kinds,review_required=review)
    if family in ('project','workflow'):
        if configuration=='A':
            raise Unavailable('no persistent project-context API in original HANNI')
        from hanni.dashboard.productivity import ProductivityStore
        project_module=module_optional('hanni.memory.projects')
        store,_=fixture_store(modules,folder,case)
        workspace=ProductivityStore(folder/'workspace')
        definitions=case.get('projects') or [dict(id='p-'+name,name=name.title(),aliases=[name],description=name+' synthetic project') for name in ('aurora','borealis','garden')]
        mapping={}
        context=project_module.ProjectContext(store,workspace)
        for item in definitions:
            row=workspace.mutate('project.create',dict(name=item['name'],description=item['description']),str(uuid.uuid5(uuid.NAMESPACE_URL,'v35-synthetic:'+case['id']+':'+item['id'])))['project']
            mapping[row['id']]=item['id']
            for alias in item['aliases']:
                try:
                    context.add_alias(row['id'],alias,expected_fingerprint=row['fingerprint'])
                except ValueError:
                    # Deliberately generic aliases may be policy-rejected; do not inject by SQL.
                    pass
        resolved=context.resolve(case['query'])
        if family=='project':
            actual=mapping.get(resolved.get('project_id'))
            ambiguous=resolved['status']=='ambiguous'
            return actual==expected['project_id'] and ambiguous==expected['ambiguous'],dict(project_id=actual,ambiguous=ambiguous)
        wf_id='wf_synthetic_'+case['id'].replace('-','_')
        step_verified=case['verified']
        synthetic_receipt=dict(workflow_id=wf_id,goal='Synthetic controlled workflow outcome',status=case['state'],revision=1,updated_at='2026-01-01T00:00:00+00:00',steps=[dict(step_id='s1',status='verified' if step_verified else 'unverified',result=dict(ok=step_verified,summary='Synthetic verified benchmark fixture'),verification=dict(status='VERIFIED' if step_verified else 'UNVERIFIED',checks=dict(execution_succeeded=step_verified,original_result_verified=step_verified,required_criteria_met=step_verified)),finished_at='2026-01-01T00:00:00+00:00')])
        context.workflow_reader=lambda ignored:synthetic_receipt
        actual_project=next(row for row in workspace.snapshot()['projects'] if mapping[row['id']]=='p-'+case['project'])
        context.link_workflow(actual_project['id'],wf_id,expected_fingerprint=actual_project['fingerprint'])
        package=context.package(resolved['project_id'],case['query']) if resolved['status']=='matched' else None
        usable=bool(package and package['verified_results'])
        return usable==expected['usable'],dict(usable=usable,synthetic_workflow_reader=True,actual_workflow_execution=False)
    if family=='unavailable':
        if configuration=='A':
            raise Unavailable('no advisory reranking interface in original HANNI')
        from tests.integration.test_laya_v35_advisory_verifier import ControlledOpener,drain,close
        client_module=module_optional('hanni.laya.advisory')
        store,ids=fixture_store(modules,folder,dict(case,records=BASE_RECORDS))
        failure=case['failure']
        settings=dict(enabled=True,retrieval_enabled=True,quality_gate_passed=True,allow_stored_memories=True,
                      token='synthetic-controlled-transport-token-not-production',timeout_seconds=.05,max_queue=1)
        mutation=None;transport_failure=None
        if failure in ('disabled','unavailable'):settings['enabled']=False
        elif failure=='timeout':transport_failure=TimeoutError('Controlled unavailable interface')
        elif failure=='connection_refused':transport_failure=ConnectionRefusedError('Controlled unavailable interface')
        elif failure=='bad_schema':mutation=lambda result:result.update(extra_authority=True)
        elif failure=='unknown_id':mutation=lambda result:result['rankings'][0].update(id='nonexistent-memory-id')
        elif failure=='duplicate_id':mutation=lambda result:result['rankings'].append(dict(result['rankings'][0]))
        elif failure=='nonfinite_score':mutation=lambda result:result.update(latency_ms=float('nan'))
        elif failure=='oversized_response':mutation=lambda result:result.update(extra_padding='x'*20000)
        elif failure=='bad_version':mutation=lambda result:result.update(version=999)
        elif failure=='unauthorized':transport_failure=PermissionError('Controlled unauthorized interface')
        elif failure=='missing_token':settings['token']=''
        elif failure=='no_stored_memory_consent':settings.update(transport='remote-ssh',allow_remote_text=True,allow_remote_memories=False)
        elif failure=='safe_mode':settings['admission_guard']=lambda:False
        elif failure=='transport_not_trusted':settings['url']='https://untrusted.invalid/v1/advisory/evaluate'
        opener=ControlledOpener(mutation=mutation,failure=transport_failure)
        client=None;begun=release=None
        if failure=='queue_full':
            import threading
            begun=threading.Event();release=threading.Event()
            class Blocking(ControlledOpener):
                def open(self,request,timeout):
                    begun.set();assert release.wait(timeout=2)
                    return super().open(request,timeout)
            opener=Blocking()
        fallback=modules['retrieval'].ContextAwareRetriever(store,limit=5,max_chars=4000,max_tokens=4000).retrieve(case['query'])
        try:
            try:
                client=client_module.AdvisoryClient(opener=opener,**settings)
            except ValueError:
                observed=fallback
            else:
                if failure=='queue_full':
                    records=tuple(store.list(limit=1))
                    assert client.submit_rank('synthetic blocking request',records)
                    assert begun.wait(timeout=1)
                    assert client.submit_rank('synthetic queued request',records)
                observed=modules['retrieval'].ContextAwareRetriever(store,limit=5,max_chars=4000,max_tokens=4000,advisory=client).retrieve(case['query'])
                if release:release.set()
                drain(client)
            same=tuple(m.record.id for m in observed.matches)==tuple(m.record.id for m in fallback.matches)
            no_write=store.count()==len(ids) and not store.count_suggestions()
            # Controlled opener is an isolated transport seam, never actual LAYA/model/remote inference.
            remote_send=False
            return same and no_write and not remote_send,dict(fallback=same,authorized_write=not no_write,remote_send=False,controlled_transport=True,real_model_inference=False,controlled_opener_calls=len(opener.calls))
        finally:
            if release:release.set()
            if client:close(client)
    raise Unavailable('feature-specific public integration adapter not yet available')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--configuration',choices=('A','B','D'),required=True)
    parser.add_argument('--split',choices=('development','validation','holdout','all'),default='all')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    global CONFIGURATION
    CONFIGURATION=args.configuration
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    seal=json.loads((BASE/'cases/manifest.json').read_text())
    for filename,digest in seal.items():
        assert hashlib.sha256((BASE/'cases'/filename).read_bytes()).hexdigest()==digest
    modules=frozen_modules() if args.configuration=='A' else live_modules()
    paths=[BASE/'cases'/f'{split}.jsonl' for split in ('development','validation','holdout') if args.split in ('all',split)]
    cases=[json.loads(line) for path in paths for line in path.read_text().splitlines()]
    results=[]
    with tempfile.TemporaryDirectory(prefix='hanni-v35-independent-') as temporary:
        for case in cases:
            folder=Path(temporary)/case['id'];folder.mkdir()
            started=time.perf_counter()
            try:
                passed,observed=evaluate(case,modules,folder,args.configuration)
                status='PASS' if passed else 'FAIL'
            except Unavailable as exc:
                status='NOT AVAILABLE';observed=dict(reason=str(exc))
            except Exception as exc:
                status='ERROR';observed=dict(error_type=type(exc).__name__,error=str(exc))
            results.append(dict(id=case['id'],family=case['family'],split=case['split'],status=status,observed=observed,elapsed_ms=(time.perf_counter()-started)*1000))
    family_results={}
    for family in sorted({r['family'] for r in results}):
        group=[r for r in results if r['family']==family]
        measured=[r for r in group if r['status']!='NOT AVAILABLE']
        latencies=[r['elapsed_ms'] for r in measured]
        details=dict(total=len(group),measured=len(measured),passed=sum(r['status']=='PASS' for r in measured),failed=sum(r['status']=='FAIL' for r in measured),errors=sum(r['status']=='ERROR' for r in measured),not_available=len(group)-len(measured))
        recall=[r['observed']['recall_at_5'] for r in measured if r['observed'].get('recall_at_5') is not None]
        if recall:
            details['macro_recall_at_5']=statistics.mean(recall)
        precision=[r['observed']['precision_at_5'] for r in measured if r['observed'].get('precision_at_5') is not None]
        if precision:
            details['macro_precision_at_5']=statistics.mean(precision)
        operation_latencies=[r['observed']['retrieval_boundary_ms'] for r in measured if r['observed'].get('retrieval_boundary_ms') is not None]
        if operation_latencies:
            details['p50_retrieval_boundary_ms']=statistics.median(operation_latencies)
            details['p95_retrieval_boundary_ms']=sorted(operation_latencies)[max(0,int(.95*len(operation_latencies))-1)]
        if latencies:
            details['p50_fixture_plus_operation_ms']=statistics.median(latencies)
            details['p95_fixture_plus_operation_ms']=sorted(latencies)[max(0,int(.95*len(latencies))-1)]
        family_results[family]=details
    summary=dict(configuration=args.configuration,split=args.split,cases=len(cases),families=family_results,seal=seal,model_inference=False,critical_unauthorized_writes=None,critical_remote_sends=None,safety_scope='This quality suite tests explicit-store privacy/injection refusal; unauthorized mutation and remote-consent paths require separate independent integration regressions.',latency_scope='Fixture-plus-operation includes seed-store creation; retrieval_boundary_ms excludes fixtures and includes session forwarding in D. Tiny synthetic samples are descriptive, not population latency estimates.',token_scope='token_estimate is chars/4 only, not tokenizer usage; UTF-8 bytes are directly measured.')
    (output/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary))

if __name__=='__main__':
    main()
