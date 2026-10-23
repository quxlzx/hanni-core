"""Private, immutable fixture/oracles for genuine configured-model paired evaluation."""
import sys,pathlib,json,time,hashlib,socket,statistics,math,re,os
from dataclasses import replace,asdict
from datetime import datetime
root=pathlib.Path(sys.argv[1]);source=pathlib.Path(sys.argv[2]);label=sys.argv[3]
sys.path.insert(0,str(source/'src'))
from hanni.config.loader import load_config
from hanni.tools.base import ToolRegistry,ToolDefinition,ToolResult,ToolPermissionError
from hanni.tools.registry import build_default_registry
from hanni.models.client import LlamaCppClient
from hanni.dashboard.launcher import start_model,stop_owned
from hanni.core.orchestrator import TextSession,system_prompt_for
from hanni.cli import _wrap_mcp_session
import psutil
cases=[json.loads(s) for s in (root/'final.jsonl').read_text().splitlines()]
cache=pathlib.Path(r'C:\Users\user\.cache\huggingface\hub\models--lmstudio-community--Qwen3.5-4B-GGUF\snapshots\f9f88ac3e234be915e23811a6d28ea287bdb927e\Qwen3.5-4B-Q4_K_M.gguf')
assert cache.is_file(),'Cached configured model missing; downloads prohibited.'
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
config=load_config(root/'original/config',data_dir=root/(label+'-live-state'),env={})
spec=replace(config.models.supervisor,endpoint=f'http://127.0.0.1:{port}/v1')
config=replace(config,models=replace(config.models,models=(spec,)))
clock=datetime.fromisoformat('2026-10-09T09:00:00-04:00')
dyn='mcp.0123456789abcdef0123456789abcdef.1234567890abcdef'
facts={
 'system.stats':('CPU is 31.5 percent; memory is 62 percent.',dict(cpu_percent=31.5,ram_percent=62,ram_total_gb=32,ram_used_gb=19.84)),
 'system.performance':('Measured CPU 31.5 percent and RAM 62 percent; sampled read-only evidence cannot prove a cause.',dict(cpu_percent=31.5,ram_percent=62,measured=True)),
 'process.top_memory':('VerifierProbe.exe uses 2032 MB of RAM; VerifierBackground.exe uses 486 MB.',dict(processes=[dict(name='VerifierProbe.exe',rss_mb=2032,rss_gb=1.98,memory_percent=6.2,pids=[41001]),dict(name='VerifierBackground.exe',rss_mb=486,rss_gb=.47,memory_percent=1.5,pids=[41003])])),
 'process.top_cpu':('VerifierRender.exe uses 44.5 percent of CPU.',dict(processes=[dict(name='VerifierRender.exe',cpu_percent=44.5,pids=[41002])])),
 'process.top_disk_io':('VerifierIndexer.exe currently reads 18 MB per second.',dict(processes=[dict(name='VerifierIndexer.exe',read_mb_s=18)])),
 'gpu.memory':('ReviewAdapter graphics memory: 3072 MB used of 8192 MB, 5120 MB free.',dict(gpus=[dict(name='ReviewAdapter',memory_used_mb=3072,memory_total_mb=8192,memory_free_mb=5120)])),
 'model.status':('Qwen3.5-4B-Q4_K_M is healthy on ReviewAdapter; quantization Q4_K_M and context length 16384.',dict(model_id='supervisor',state='healthy',reachable=True,selected_device_name='ReviewAdapter',placement_verified=True,observed_vram_mb=4600,quantization='Q4_K_M',context_length=16384)),
 'disk.usage':('C: has 120 GB free of 500 GB. D: has 410 GB free of 1000 GB.',dict(drives=[dict(drive='C:',free_gb=120,total_gb=500),dict(drive='D:',free_gb=410,total_gb=1000)])),
 'disk.free_space':('C: has 120 GB free of 500 GB.',dict(drive='C:',free_gb=120,total_gb=500)),
 'google_calendar.agenda':('Controlled review meeting is on October 10, 2026 at 14:00 America/New_York.',dict(events=[dict(id='fixture-event-1',summary='Controlled review meeting',start='2026-10-10T14:00:00-04:00',end='2026-10-10T14:30:00-04:00')],event_count=1,timezone='America/New_York')),
 'google.calendar.events':('Controlled review meeting is on October 10, 2026 at 14:00 America/New_York.',dict(events=[dict(id='fixture-event-1',summary='Controlled review meeting',start='2026-10-10T14:00:00-04:00',end='2026-10-10T14:30:00-04:00')],event_count=1)),
 'google_calendar.next':('Controlled review meeting is on October 10, 2026 at 14:00 America/New_York.',dict(events=[dict(id='fixture-event-1',summary='Controlled review meeting',start='2026-10-10T14:00:00-04:00',end='2026-10-10T14:30:00-04:00')],event_count=1)),
 dyn:('The measured habitat reading is 7.2 units at 2026-10-09T08:55:00-04:00.',dict(reading=7.2,measured_at='2026-10-09T08:55:00-04:00'))
}
# Same declared fixture answers on baseline/final; never rewrite from observed output.
file_terms={'FINAL-033':'warranty','FINAL-034':'budget','FINAL-035':'conference','FINAL-036':'application'}
def answer_pattern(name):
 return {'process.top_memory':r'VerifierProbe','process.top_cpu':r'VerifierRender','process.top_disk_io':r'VerifierIndexer','system.stats':r'31[.,]5|62','system.performance':r'31[.,]5|62','gpu.memory':r'3072|3(?:\.0)?\s*(?:GB|gig)','model.status':r'Qwen|ReviewAdapter|Q4_K_M|16384','disk.usage':r'120|410','disk.free_space':r'120','google_calendar.agenda':r'Controlled review meeting','google.calendar.events':r'Controlled review meeting','google_calendar.next':r'Controlled review meeting',dyn:r'7[.,]2','file.search':r'\.pdf|\.xlsx'}.get(name,r'(?!)')
oracle=dict(facts=facts,file_terms=file_terms,claim_patterns={n:answer_pattern(n) for n in [*facts,'file.search']},notes='Conservative lexical final-answer checks; actual model, original registry permission/schema/audit and controller; controlled read-only adapter output, not actual system/provider measurements.')
oracle_bytes=json.dumps(oracle,sort_keys=True).encode()
oracle_path=root/'live-oracle.json'
if oracle_path.exists():assert oracle_path.read_bytes()==oracle_bytes,'Oracle drift forbidden'
else:oracle_path.write_bytes(oracle_bytes)
class ObservedClient:
 def __init__(self,client):self.client=client;self.menus=[];self.turns=[];self.inference_ms=[]
 def complete_with_tools(self,messages,*,tools,**kwargs):
  t=time.perf_counter();turn=self.client.complete_with_tools(messages,tools=tools,**kwargs);self.inference_ms.append((time.perf_counter()-t)*1000)
  self.menus.append(tools);self.turns.append(dict(content=turn.content,calls=[dict(name=c.name,arguments=dict(c.arguments)) for c in turn.tool_calls]))
  return turn
 def chat(self,*a,**k):return self.client.chat(*a,**k)
 def stream_chat(self,*a,**k):yield from self.client.stream_chat(*a,**k)
external_before=sorted(p.pid for p in psutil.process_iter(['name']) if 'llama' in (p.info['name'] or '').lower())
process=None;results=[]
try:
 process=start_model(config,timeout=180,model_file=cache)
 client=LlamaCppClient(spec)
 # One neutral warmup; no test query and no expected answer is exposed.
 client.chat([{'role':'user','content':'Reply with the word ready.'}],max_tokens=8)
 for index,case in enumerate(cases,1):
  original=build_default_registry(config)
  registry=ToolRegistry(original.context);calls=[];write_denials=[]
  class FixtureGoogle:
   def resolve_account(self,requested=None,service=None):return requested or 'personal'
   def has_capability(self,account,capability):return True
  registry.google_access=FixtureGoogle()
  def handler(name,definition):
   def run(args,context,request):
    if definition.permission_level or definition.risk_level or definition.side_effect not in {None,'read'}:
     write_denials.append(name);raise ToolPermissionError('Independent fixture forbids production writes.')
    valid=True
    if name=='file.search':
     term=file_terms.get(case['id']);valid=bool(term and term in str(args.get('query','')).casefold())
     file='controlled-'+(term or 'unknown')+('.xlsx' if term=='budget' else '.pdf')
     message='Controlled search result: '+file;data=dict(matches=[dict(name=file,path=str(config.paths.data_dir/file))],count=1,fixture=True)
    else:message,data=facts.get(name,('No controlled data source supports this capability.',{}))
    ok=name in facts or name=='file.search'
    calls.append(dict(name=name,arguments=dict(args),ok=ok,semantic_arguments_correct=valid,data=data))
    return ToolResult(name,ok,message,data,error=None if ok else dict(code='UNSUPPORTED',retryable=False))
   return run
  for d in original.definitions():registry.register(replace(d,handler=handler(d.name,d)))
  dynamic=ToolDefinition(dyn,'Retrieve the newest habitat conservation sensor measurement from the Lantern archive; returns observed wetland reading and measurement timestamp.',0,0,{}, {},lambda *a:None,side_effect='read',tags=('Lantern archive',),aliases=('habitat.latest',),json_input_schema={'type':'object','properties':{},'additionalProperties':False},external_definition_hash=hashlib.sha256(b'fixed-independent-dynamic-definition-v1').hexdigest())
  if case.get('dynamic_available',True):registry.register(replace(dynamic,handler=handler(dyn,dynamic)))
  observed=ObservedClient(client)
  fallback=TextSession(observed,system_prompt=system_prompt_for(config.hanni.personality))
  session=_wrap_mcp_session(config,fallback,client=observed,registry=registry)
  route=session.host.route
  session.host.route=lambda query,**kwargs:route(query,**{**kwargs,'now':clock})
  decision=session.host.route(case['query'])
  menu={tool.capability_id for tool in decision.tools};required=set(case['required']);groups=[set(g) for g in case['required_any']]
  available=required<=menu and all(menu&g for g in groups) if case['mode']=='tools' else not menu
  start=time.perf_counter();error=None
  try:answer=''.join(session.stream_response(case['query']))
  except Exception as exc:answer='';error=type(exc).__name__+': '+str(exc)
  elapsed=(time.perf_counter()-start)*1000
  selected={c['name'] for c in calls if c['ok']}
  selection=required<=selected and all(selected&g for g in groups) if case['mode']=='tools' else not calls
  arguments=all(c['semantic_arguments_correct'] for c in calls) and not error
  groups_to_check=[{n} for n in required]+groups
  claims=all(any(n in selected and re.search(answer_pattern(n),answer,re.I) for n in group) for group in groups_to_check) if case['mode']=='tools' else not calls
  row=dict(id=case['id'],menu_sufficient=available,selection_correct=selection,arguments_correct=arguments,answer_supported=bool(answer) and claims,controlled_task_complete=selection and arguments and bool(answer) and claims,latency_ms=elapsed,model_inference_ms=sum(observed.inference_ms),model_menu_rounds=len(observed.menus),model_turns=observed.turns,calls=calls,answer=answer,error=error,forbidden_executions=len(write_denials),no_tool=case['mode']=='no_tool')
  results.append(row)
  (root/(label+'-live-results.json')).write_text(json.dumps(dict(completed=len(results),total=len(cases),results=results,oracle_sha256=hashlib.sha256(oracle_bytes).hexdigest(),model_spec=asdict(spec),source=str(source),disclosure=oracle['notes']),indent=2),encoding='utf8')
  if index%10==0:print(json.dumps(dict(progress=index,total=len(cases))),flush=True)
finally:
 stop_owned(process)
 external_after=sorted(p.pid for p in psutil.process_iter(['name']) if 'llama' in (p.info['name'] or '').lower())
 lats=sorted(r['latency_ms'] for r in results)
 summary=dict(samples=len(results),completed=len(results)==60,model_selection_correct=sum(r['selection_correct'] for r in results),argument_correct=sum(r['arguments_correct'] for r in results),controlled_task_complete=sum(r['controlled_task_complete'] for r in results),answer_supported=sum(r['answer_supported'] for r in results),forbidden_executions=sum(r['forbidden_executions'] for r in results),p50_ms=statistics.median(lats) if lats else None,p95_ms=lats[math.ceil(.95*len(lats))-1] if lats else None,external_before=external_before,external_after=external_after,owned_pid=getattr(process,'pid',None),owned_closed=process is None or process.poll() is not None,oracle_sha256=hashlib.sha256(oracle_bytes).hexdigest(),fixture_only=True)
 (root/(label+'-live-summary.json')).write_text(json.dumps(summary,indent=2),encoding='utf8')
 print(json.dumps(summary),flush=True)

