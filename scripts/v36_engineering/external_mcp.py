"""Real SDK server/adapter/schema/audit plus actual resident-model selections.

Original default policy is preserved. The explicitly approved synthetic write is
tested directly with owner confirmation, never exposed by relaxing MCP policy.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from model_campaign import RecordingClient
from hanni.cli import _wrap_mcp_session,_wrap_memory_session,_close_interactive_session
from hanni.config.loader import load_config
from hanni.core.orchestrator import TextSession,system_prompt_for
from hanni.mcp.manager import MCPManager
from hanni.models import create_client
from hanni.tools import build_default_registry
from hanni.tools.base import ToolRequest
from hanni.tools.capabilities import describe
from controlled_launcher import EmptyVault


def main():
    p=argparse.ArgumentParser();p.add_argument('--identity',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'data') or output.exists():raise ValueError('Use a fresh campaign data output.')
    output.mkdir(parents=True)
    identity=json.loads(args.identity.read_text())
    config=load_config(identity['config_dir'],data_dir=output/'state',env={})
    registry=build_default_registry(config);registry.google_access._vault=EmptyVault()
    manager=MCPManager(output/'hub',registry=registry)
    results=[]
    try:
        server=manager.add({'name':'V36 durable fixture','transport':'stdio','command':sys.executable,
            'args':[str(ROOT/'scripts/v36_engineering/sdk_server.py'),'--directory',str(output/'server')],'timeout_seconds':3})
        snapshot=manager.connect(server['id'],approved=True,expected_config_hash=server['config_hash'])
        (output/'connection.json').write_text(json.dumps(snapshot,ensure_ascii=True,indent=2),encoding='utf-8')
        manager.enable_server(server['id'])
        current=next(s for s in manager.snapshot()['servers'] if s['id']==server['id'])
        manager.approve_tools(server['id'],[{'original_name':t['original_name'],'definition_hash':t['definition_hash'],
            'classification':'write' if t['original_name'].endswith('create_record') else 'read_only'} for t in current['tools']])
        current=next(s for s in manager.snapshot()['servers'] if s['id']==server['id'])
        tools={t['original_name']:t for t in current['tools']}
        definitions=[describe(registry.get(t['internal_id'])).to_dict() for t in tools.values()]
        (output/'inventory.json').write_text(json.dumps({'source':'Actual live MCPManager-discovered/approved original registry imports','capabilities':definitions},indent=2),encoding='utf-8')
        cases=[{'original_name':'v36.fixture.status','request':'Use v36.fixture.status to read the current fixture status and stored record count.','arguments':{}},
               {'original_name':'v36.fixture.echo','request':'Use v36.fixture.echo to echo the exact message amber rehearsal.','arguments':{'message':'amber rehearsal'}},
               {'original_name':'v36.fixture.create_record','request':'Use v36.fixture.create_record to save a test record titled amber rehearsal.','arguments':{'title':'amber rehearsal'}}]
        for case in cases:case['capability_id']=tools[case['original_name']]['internal_id']
        encoded=json.dumps({'version':1,'cases':cases,'criterion':'Original real local SDK and controller. Read tools genuine model selection; write denied by unchanged original MCP policy with response-only diagnostic explicitly distinguished.'},sort_keys=True,indent=2).encode()
        (output/'sealed-cases.json').write_bytes(encoded);digest=hashlib.sha256(encoded).hexdigest();(output/'sealed-cases.sha256').write_text(digest+'\n')
        original=create_client(config)
        if not original.health().ok:raise RuntimeError('Owned current configured model unavailable; no fallback/download/runtime.')
        with (output/'results.jsonl').open('x',encoding='utf-8') as log:
            for case in cases:
                name=case['capability_id'];record={'case':case,'cohort_sha256':digest,'classification':'ISOLATED','verification_status':'PENDING_INDEPENDENT_REVIEW'}
                direct=registry.execute(ToolRequest(name,case['arguments'],confirmed=True,source='v36-owner-fixed-mcp-fixture'))
                record['direct_valid']=direct.to_dict()
                before=(output/'server/calls.jsonl').read_text().splitlines()
                try:registry.execute(ToolRequest(name,{**case['arguments'],'unknown_field':True},confirmed=True))
                except Exception as error:record['direct_invalid']={'error_class':type(error).__name__,'rejected':True}
                else:record['direct_invalid']={'rejected':False}
                record['invalid_dispatched']=len((output/'server/calls.jsonl').read_text().splitlines())!=len(before)
                if case['original_name'].endswith('create_record'):
                    record['durable_readback']=json.loads((output/'server/records.json').read_text())
                client=RecordingClient(original)
                base=TextSession(client,system_prompt=system_prompt_for(config.hanni.personality))
                mcp=_wrap_mcp_session(config,base,client=client,registry=registry)
                controller=_wrap_memory_session(config,mcp,source='v36-external-model',registry=registry,emergency_stop=registry.context.emergency_stop)
                receipts=[];call=mcp.host.call
                def observed(tool,arguments,**kwargs):
                    result=call(tool,arguments,**kwargs);receipts.append({'capability_id':tool.capability_id,'arguments':arguments,'result':result});return result
                mcp.host.call=observed
                record['policy_eligible']=mcp.host._allowed(registry.get(name));started=time.perf_counter()
                try:
                    route=mcp.host.route(case['request']);record['route']={'status':route.status,'menu':[t.capability_id for t in route.tools]}
                    record['response']=''.join(controller.stream_response(case['request']))
                    if not client.records:record['response_only_diagnostic']=''.join(base.stream_response(case['request']))
                    record['actual_model_inferences']=client.records;record['receipts']=receipts
                    record['tool_selected']=any(t['name']==mcp.host._wire_name(name) for r in client.records if isinstance(r.get('output'),dict) for t in r['output'].get('tool_calls',[]))
                    record['selection_scope']='Actual model tool menu' if any(r['kind']=='tools' for r in client.records) else 'No model tool menu; original policy denial and actual response-only diagnostic'
                finally:_close_interactive_session(controller)
                record['latency_ms']=(time.perf_counter()-started)*1000
                log.write(json.dumps(record,ensure_ascii=True,default=str)+'\n');log.flush()
                print(json.dumps({'tool':case['original_name'],'direct_ok':direct.ok,'model_selected':record.get('tool_selected'),'policy_eligible':record['policy_eligible']}),flush=True)
        (output/'manager-final.json').write_text(json.dumps(manager.snapshot(),indent=2,ensure_ascii=True),encoding='utf-8')
    finally:manager.close();registry.context.reliability.close()
    return 0


if __name__=='__main__':raise SystemExit(main())
