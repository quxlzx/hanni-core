import sys,json,pathlib,time,statistics,hashlib,math
from datetime import datetime
root=pathlib.Path(sys.argv[1]);source=pathlib.Path(sys.argv[2]) if len(sys.argv)>2 else root/'original';label=sys.argv[3] if len(sys.argv)>3 else 'baseline'
sys.path.insert(0,str(source/'src'))
from hanni.evals.routing import build_default_host
from hanni.tools.base import ToolDefinition
cases=[json.loads(s) for s in (root/'final.jsonl').read_text().splitlines()]
host=build_default_host(config_dir=root/'original/config',data_dir=root/(label+'-isolated-data'),timezone_name='America/New_York')
dyn='mcp.0123456789abcdef0123456789abcdef.1234567890abcdef'
def deny(*a,**k):raise AssertionError('execution prohibited in retrieval holdout')
definition=ToolDefinition(dyn,'Retrieve the newest habitat conservation sensor measurement from the Lantern archive; returns observed wetland reading and measurement timestamp.',0,0,{}, {},deny,side_effect='read',tags=('Lantern archive',),aliases=('habitat.latest',),json_input_schema={'type':'object','properties':{},'additionalProperties':False},external_definition_hash=hashlib.sha256(b'fixed-independent-dynamic-definition-v1').hexdigest())
host.registry.register(definition)
definition = host.registry.get(dyn)
registered={d.name for d in host.registry.definitions()}
assert not {n for c in cases for n in c['required'] if n not in registered}
clock=datetime.fromisoformat('2026-10-09T09:00:00-04:00')
results=[]
for c in cases:
 if c.get('dynamic_available') is False and dyn in {d.name for d in host.registry.definitions()}:assert host.registry.unregister(dyn,expected=definition)
 t=time.perf_counter();decision=host.route(c['query'],now=clock);latency=(time.perf_counter()-t)*1000
 menu=[d.capability_id for d in decision.tools];s=set(menu)
 required=set(c['required']);groups=[set(g) for g in c['required_any']]
 sufficient=required<=s and all(s&g for g in groups) if c['mode']=='tools' else not menu
 forbidden_hit=bool(s&set(c['forbidden']))
 acceptable=required|(set().union(*groups) if groups else set())
 results.append(dict(**c,selected=menu,status=decision.status,sufficient=sufficient and not forbidden_hit,forbidden_exposure=forbidden_hit,irrelevant_exposure=sorted(s-acceptable) if c['mode']=='tools' else menu,latency_ms=latency,fixed_arguments={t.capability_id:dict(t.fixed_arguments) for t in decision.tools}))
def wilson(ok,n):
 if not n:return None
 z=1.95996398454;p=ok/n;den=1+z*z/n;center=(p+z*z/(2*n))/den;radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
 return [100*(center-radius),100*(center+radius)]
tool=[r for r in results if r['mode']=='tools'];no=[r for r in results if r['mode']=='no_tool'];lats=sorted(r['latency_ms'] for r in results)
summary=dict(samples=len(results),required_tool_samples=len(tool),menu_sufficient=sum(r['sufficient'] for r in tool),menu_sufficiency_percent=100*sum(r['sufficient'] for r in tool)/len(tool),menu_sufficiency_wilson95=wilson(sum(r['sufficient'] for r in tool),len(tool)),correct_no_tool=sum(r['sufficient'] for r in no),no_tool_samples=len(no),no_tool_wilson95=wilson(sum(r['sufficient'] for r in no),len(no)),forbidden_menu_exposures=sum(r['forbidden_exposure'] for r in results),mean_candidate_count=statistics.mean(len(r['selected']) for r in results),irrelevant_exposure_count=sum(len(r['irrelevant_exposure']) for r in results),retrieval_latency_p50_ms=statistics.median(lats),retrieval_latency_p95_ms=lats[math.ceil(.95*len(lats))-1],model_tool_selection=None,argument_correctness=None,verified_completion=None,unauthorized_execution=None,disclosure='Metadata-only genuine original host retrieval; zero handler/model execution. Synthetic dynamic metadata registered solely for discovery/withdrawal testing. No task success inference.')
artifact=dict(summary=summary,results=results,manifest=json.loads((root/'manifest.json').read_text()),source_module=sys.modules['hanni.mcp.host'].__file__,clock=clock.isoformat(),config_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'original/config').glob('*.yaml')})
(root/(label+'-retrieval.json')).write_text(json.dumps(artifact,indent=2),encoding='utf8')
print(json.dumps(summary))

