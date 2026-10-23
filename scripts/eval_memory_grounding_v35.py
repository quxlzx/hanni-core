"""Prospective real Qwen grounding comparison: synthetic records, original chat boundary."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import statistics
import subprocess
import sys
import time
import urllib.request
from uuid import uuid5,NAMESPACE_URL

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'evals/memory_intelligence_v35'
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
import yaml
from hanni.config.loader import load_config
from hanni.core.orchestrator import TextSession
from hanni.dashboard.productivity import ProductivityStore
from hanni.memory.integration import PersonalContextProvider
from hanni.memory.projects import ProjectContext
from hanni.memory.session import MemoryAwareSession
from hanni.memory.store import MemoryStore
from hanni.models.client import LlamaCppClient
from hanni.models.manager import ModelManager,current,install

def digest(path):
    sha=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):sha.update(block)
    return sha.hexdigest()

def save(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,allow_nan=False)

def source_manifest():
    paths=list((ROOT/'src/hanni').rglob('*.py'))+[ROOT/'config'/name for name in ('models.yaml','hanni.yaml','permissions.yaml','privacy.yaml')]
    files={str(path.relative_to(ROOT)).replace('\\','/'):digest(path) for path in sorted(paths)}
    return dict(sha256=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),files=files)

def make_fixture(case,folder):
    folder.mkdir()
    store=MemoryStore(folder/'memory.sqlite3')
    workspace=ProductivityStore(folder/'workspace')
    project_context=ProjectContext(store,workspace)
    mapping={}
    for name in sorted({row['project'] for row in case['records'] if row.get('project')}):
        project=workspace.mutate('project.create',dict(name=name.title(),description='Controlled synthetic '+name+' context project'),str(uuid5(NAMESPACE_URL,case['id']+name)))['project']
        project_context.add_alias(project['id'],name,expected_fingerprint=project['fingerprint'])
        mapping[name]=project['id']
    for index,row in enumerate(case['records']):
        content='Synthetic safe legacy placeholder' if row.get('legacy_import') else row['content']
        record,_=store.remember(content,source=row.get('source','owner_explicit:synthetic-fixture'),memory_type=row.get('type'),semantic_status=row.get('status','statement'),project_id=mapping.get(row.get('project',''),''),source_ref=case['id']+':'+str(index))
        if row.get('legacy_import'):
            with store._connect() as db:
                db.execute('UPDATE memories SET content=?,normalized_content=? WHERE id=?',(row['content'],row['content'].casefold(),record.id))
        if row.get('correction'):
            record=store.correct(record.id,row['correction'],expected_updated_at=record.updated_at.isoformat())
        if row.get('delete'):store.delete(record.id,expected_updated_at=record.updated_at.isoformat())
    return store,project_context

class CapturingClient:
    def __init__(self,client):self.client=client;self.messages=[]
    def stream_chat(self,messages,**kwargs):
        self.messages=[dict(row) for row in messages]
        yield from self.client.stream_chat(messages,**kwargs)

def tokenizer_count(spec,messages):
    """Read-only installed server formatting/tokenizer; no generation/retry."""
    base=spec.endpoint.rstrip('/').removesuffix('/v1')
    def post(path,payload):
        request=urllib.request.Request(base+path,data=json.dumps(payload).encode('utf-8'),method='POST',headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
    formatted=post('/apply-template',dict(messages=messages,chat_template_kwargs=dict(enable_thinking=spec.thinking_enabled)))
    tokens=post('/tokenize',dict(content=formatted['prompt'],add_special=False,parse_special=True))['tokens']
    assert isinstance(tokens,list) and all(type(token) is int for token in tokens)
    return len(tokens)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-file',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    weights=args.model_file.resolve();output=args.output.resolve()
    assert weights.is_file(),'Only existing installed weights allowed; no download.'
    assert weights.stat().st_size==2707513696 and digest(weights)=='25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c','Existing approved Qwen weights must match.'
    seal=json.loads((BASE/'main-grounding/manifest.json').read_text())
    for name,sha in seal.items():assert digest(BASE/'main-grounding'/name)==sha
    cases=[json.loads(line) for line in (BASE/'main-grounding/cases.jsonl').read_text().splitlines()]
    assert len(cases)==12
    output.mkdir(parents=True,exist_ok=False);profile=output/'profile';profile.mkdir()
    for name in ('hanni.yaml','models.yaml','permissions.yaml','privacy.yaml'):shutil.copyfile(ROOT/'config'/name,profile/name)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    settings=yaml.safe_load((profile/'models.yaml').read_text(encoding='utf-8'))
    assert len(settings['models'])==1
    settings['models'][0]['model_file']=weights.name;settings['models'][0]['endpoint']=f'http://127.0.0.1:{port}/v1'
    (profile/'models.yaml').write_text(yaml.safe_dump(settings,sort_keys=False),encoding='utf-8')
    config=load_config(profile,data_dir=output/'state',env={})
    baseline=json.loads((BASE/'baseline_f19dd00/manifest.json').read_text())
    for name,sha in baseline['files'].items():
        assert digest(BASE/'baseline_f19dd00'/name)==sha,'Original baseline snapshot must match its manifest.'
    spec=importlib.util.spec_from_file_location('verifier_frozen_retrieval',BASE/'baseline_f19dd00/retrieval.py')
    frozen=importlib.util.module_from_spec(spec);sys.modules[spec.name]=frozen;spec.loader.exec_module(frozen)
    metadata=dict(started_utc=datetime.now(timezone.utc).isoformat(),repository_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),weights_file=str(weights),weights_sha256=digest(weights),source_before=source_manifest(),runner_sha256=digest(__file__),cases_seal=seal,configured_model=asdict(config.models.supervisor),scope='Real current Qwen model, original TextSession and MemoryAwareSession, controlled synthetic authoritative records only. A uses original f19dd00 retriever on common current-schema fixture, D uses explicitly opted context provider. This is not real LAYA, an autonomous workflow, or a full schema-v2 M0 comparison.',generation_attempts_per_case_per_arm=1,profile_overrides=['fresh owned loopback endpoint','existing model filename'],token_scope='Server SSE usage measures complete input and generated output. Memory-only tokenizer cost and empty-context difference are not measured unless separately reported; chars/bytes are not token counts.')
    save(output/'prepared.json',metadata)
    previous=current();assert previous is None,'Refuse existing model manager replacement.'
    manager=None;rows=[];old_cwd=Path.cwd();os.chdir(output)
    try:
        manager=ModelManager(config,startup_timeout=180,model_files={config.models.supervisor.id:str(weights)})
        started=time.perf_counter();manager.start();install(manager);entry=manager.ensure_loaded(config.models.supervisor.id)
        assert entry.process is not None,'Must own isolated model process.'
        metadata.update(startup_ms=(time.perf_counter()-started)*1000,owned_pid=entry.process.pid,runtime_command=list(entry.command))
        save(output/'runtime-started.json',metadata)
        print(json.dumps(dict(phase='running',owned_pid=entry.process.pid,cases=12,arms=2)),flush=True)
        client=LlamaCppClient(config.models.supervisor,max_attempts=1)
        for case in cases:
            class NoInference:
                def stream_chat(self,messages,**kwargs):
                    if False:yield ''
            empty_capture=CapturingClient(NoInference())
            list(TextSession(empty_capture).stream_response(case['prompt']))
            try:empty_count=dict(tokens=tokenizer_count(config.models.supervisor,empty_capture.messages),measured=True)
            except Exception as exc:empty_count=dict(measured=False,error=type(exc).__name__+': '+str(exc))
            for arm in ('A','D'):
                store,projects=make_fixture(case,output/(case['id']+'-'+arm))
                reader=frozen.LocalMemoryRetriever(store,limit=5,max_chars=4000,min_score=25) if arm=='A' else PersonalContextProvider(store,project_context=projects,limit=5,max_chars=4000,max_tokens=4000,min_score=25)
                capture=CapturingClient(client);session=MemoryAwareSession(TextSession(capture),store,extraction_enabled=False,context_retriever=reader)
                before={row.id:row.to_dict() for row in store.list()};usage={};chunks=[];started=time.perf_counter();first_ms=None;error=None
                try:
                    for chunk in session.stream_response(case['prompt'],usage=usage):
                        if first_ms is None:first_ms=(time.perf_counter()-started)*1000
                        chunks.append(chunk)
                except Exception as exc:error=dict(type=type(exc).__name__,message=str(exc))
                elapsed=(time.perf_counter()-started)*1000;text=''.join(chunks)
                after={row.id:row.to_dict() for row in store.list()}
                try:
                    full_count=tokenizer_count(config.models.supervisor,capture.messages)
                    token_measurement=dict(full_formatted_tokens=full_count,empty_context=empty_count,agrees_with_actual_sse_prompt_usage=full_count==usage.get('prompt_tokens'))
                    token_measurement['extra_prompt_tokens_vs_empty']=full_count-empty_count['tokens'] if empty_count.get('measured') and token_measurement['agrees_with_actual_sse_prompt_usage'] else None
                except Exception as exc:token_measurement=dict(error=type(exc).__name__+': '+str(exc),extra_prompt_tokens_vs_empty=None)
                lowered=text.casefold();missing=[literal for literal in case['oracle']['required'] if literal.casefold() not in lowered];forbidden=[literal for literal in case['oracle']['forbidden'] if literal.casefold() in lowered]
                row=dict(id=case['id'],family=case['family'],arm=arm,prompt=case['prompt'],answer=text,messages=capture.messages,usage=usage,tokenizer_measurement=token_measurement,elapsed_ms=elapsed,first_content_ms=first_ms,error=error,required_missing=missing,forbidden_present=forbidden,literal_pass=not(error or missing or forbidden),semantic_review='PENDING independent review of raw answer',store_unchanged=before==after,original_session_used=True,model_inference=True,tools_registered=False,real_laya=False,disclosure=case.get('disclosure',''))
                save(output/(case['id']+'-'+arm+'.json'),row);rows.append(row)
                print(json.dumps(dict(id=case['id'],arm=arm,literal_pass=row['literal_pass'],prompt_tokens=usage.get('prompt_tokens'),elapsed_ms=round(elapsed,2))),flush=True)
        summaries={}
        for arm in ('A','D'):
            group=[row for row in rows if row['arm']==arm];latencies=[row['elapsed_ms'] for row in group];tokens=[row['usage']['prompt_tokens'] for row in group if 'prompt_tokens' in row['usage']]
            summaries[arm]=dict(cases=len(group),literal_passes=sum(row['literal_pass'] for row in group),errors=sum(row['error'] is not None for row in group),p50_ms=statistics.median(latencies),p95_ms=sorted(latencies)[max(0,int(.95*len(latencies))-1)],measured_prompt_tokens_count=len(tokens),total_measured_prompt_tokens=sum(tokens) if tokens else None,mean_measured_prompt_tokens=statistics.mean(tokens) if tokens else None,store_unchanged=all(row['store_unchanged'] for row in group))
        save(output/'literal-summary.json',dict(arms=summaries,semantic_review='PENDING',model='Actual existing Qwen3.5-4B-Q4_K_M.gguf, not LAYA',inference_attempts=24))
    except BaseException as exc:
        metadata['error']=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        if manager is not None:
            process=manager.entries[config.models.supervisor.id].process;manager.close();metadata['owned_closed']=process is None or process.poll() is not None
        install(previous);os.chdir(old_cwd)
        metadata.update(finished_utc=datetime.now(timezone.utc).isoformat(),completed_inference_attempts=len(rows),source_after=source_manifest())
        metadata['source_unchanged']=metadata['source_before']==metadata['source_after'];save(output/'run-metadata.json',metadata)
    print(json.dumps(dict(phase='closed',owned_closed=metadata.get('owned_closed'),source_unchanged=metadata['source_unchanged'])),flush=True)

if __name__=='__main__':main()
