"""One real, synthetic public research task. No voice or Windows mutations.

The owner-requested validation scope authorizes only the existing core web
search/extract capabilities. Unexpected capabilities are rejected. Every run
retains its own output; no inference failure is overwritten or scored as success.
"""
import argparse
import json
from pathlib import Path
import time
from uuid import uuid4

from hanni.hermes.client import Client
from hanni.hermes.tunnel import ManagedTunnel
from hanni.hermes.state import TERMINAL


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parents[1]/'data')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--windows-save',action='store_true',help='Programmatic HANNI registry approval and independently checked fixture file; not a physical voice/UI test.')
    args=parser.parse_args()
    if args.output.exists():
        raise SystemExit('Choose a fresh receipt file; failures are retained.')
    config=json.loads((args.data_dir/'hermes/config.json').read_text())
    tunnel=ManagedTunnel(config['tunnel']);tunnel.start()
    task=None
    client=Client(config)
    control=None
    destination=None
    isolated_mcp=None
    try:
        for _ in range(25):
            try:
                health=client.request('GET','/health')
                if health.get('protocol')!=1:raise RuntimeError('Unsupported protocol')
                break
            except RuntimeError:time.sleep(.2)
        else:raise RuntimeError('Private bridge health unavailable.')
        request={'prompt':'Use the registered web_search capability to find the official Python documentation website. Briefly report its URL with source evidence. Use only web_search or web_extract, no browser or file actions.',
                 'windows_tools':[],'origin':'hanni','context':{}}
        started=time.monotonic()
        if args.windows_save:
            import tempfile
            from types import SimpleNamespace
            from hanni.config.loader import load_config
            from hanni.core.shutdown import EmergencyStop
            from hanni.hermes.client import HermesControl
            from hanni.tools.base import ToolContext, ToolRegistry
            from hanni.tools.files import definitions
            from hanni.tools.audit import ToolAuditLog
            from hanni.mcp.manager import MCPManager
            test_root=Path(tempfile.mkdtemp(prefix='hanni-hermes-live-save-'))
            (test_root/'hermes').mkdir()
            isolated={**config,'enabled':True,'windows_capabilities':['file.write','file.read','file.stat'],
                      'windows_roots':[str(test_root)]}
            isolated.pop('tunnel',None)
            (test_root/'hermes/config.json').write_text(json.dumps(isolated))
            cfg=load_config(data_dir=test_root)
            registry=ToolRegistry(ToolContext(cfg.permissions,EmergencyStop(),ToolAuditLog(test_root)))
            for definition in definitions():registry.register(definition)
            isolated_mcp=MCPManager(test_root)
            control=HermesControl(test_root,SimpleNamespace(controller_registry=registry,features=SimpleNamespace(registry=registry),require=lambda:isolated_mcp))
            control.bind(registry)
            destination=test_root/'shortlist.txt'
            prompt='Search for the official Python documentation website using web_search and save its official URL in the Windows text file '+str(destination)+'. Use only the core web search/extract and Windows file write/read/stat capabilities.'
            task=control.submit(prompt,registry,key='live-save-'+uuid4().hex)
        else:
            task=client.request('POST','/tasks',{'key':'live-research-'+uuid4().hex,'task':request})
        submission_ms=1000*(time.monotonic()-started)
        history=[]
        while time.monotonic()-started < 60:
            row=client.request('GET','/tasks/'+task['id'])
            history.append({'at_ms':1000*(time.monotonic()-started),'state':row['state']})
            for action in row['actions']:
                if action['state']!='pending':continue
                spec=action['spec'];remote=spec['remote']
                if control is not None and spec['target']=='windows' and remote.get('retry_read') is True:
                    continue  # Original-registry background reads are handled by the scoped controller.
                permit=(spec['target']=='karina' and remote.get('server')=='hanni_capabilities' and remote.get('name') in {'web_search','web_extract'})
                permit=permit or (control is not None and spec['target']=='windows' and remote.get('capability_id') in {'file.write','file.read','file.stat'})
                if control is not None:
                    from hanni.hermes.state import digest
                    control.mutate({'id':action['id'],'operation':'approve','data':{'task_id':task['id'],
                        'action_id':action['id'],'expected_hash':digest(action),'reject':not permit},'confirmed':True})
                elif permit:
                    client.request('POST','/actions/'+action['id'],{'state':'dispatching'})
                else:
                    client.request('POST','/actions/'+action['id'],{'state':'rejected','receipt':{'ok':False,'error':'Outside synthetic public read validation scope.'}})
            if row['state'] in TERMINAL:break
            time.sleep(.2)
        else:
            client.request('POST','/tasks/'+task['id']+'/cancel',{})
            row=client.request('GET','/tasks/'+task['id'])
        receipt={'kind':'live_synthetic_text_Hermes_Wonyoung_MCP','submission_ms':submission_ms,
                 'duration_ms':1000*(time.monotonic()-started),'task':row,'history':history,
                 'voice_tested':False,'windows_write_tested':False}
        if destination is not None:
            saved=destination.read_text() if destination.exists() else None
            receipt.update(windows_write_tested=True, owner_approval='programmatic original registry management',
                           saved_path=str(destination),saved_contents=saved,
                           independent_saved_contents_ok=saved is not None and 'https://docs.python.org' in saved,
                           natural_language_ingress_tested=False)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
        print(json.dumps({'id':row['id'],'state':row['state'],'error':row['error'],
                          'action_count':len(row['actions']),'submission_ms':submission_ms,'receipt':str(args.output),
                          'saved_contents_ok':receipt.get('independent_saved_contents_ok')}))
        passed = row['state']=='review_required' and (destination is None or receipt['independent_saved_contents_ok'])
        return 0 if passed else 1
    finally:
        if task is not None:
            try:client.request('POST','/tasks/'+task['id']+'/cancel',{})
            except RuntimeError:pass
        if control is not None:
            control.close()
        if isolated_mcp is not None:
            isolated_mcp.close()
        tunnel.close()


if __name__=='__main__':
    raise SystemExit(main())
