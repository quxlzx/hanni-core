"""Seal every actual private desktop capability's NL inquiry, without authority.

Those operations belong to DesktopFeatures' owner-only fixed-operation registry,
not the original chat MCP registry. This runs genuine resident-model responses in
the original TextSession and explicitly marks tool selection BLOCKED. It does not
invent a chat adapter, expose a private registry, execute an action or count the
model's words as successful CRUD.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
from model_campaign import RecordingClient
from hanni.config.loader import load_config
from hanni.core.orchestrator import TextSession,system_prompt_for
from hanni.models import create_client

REQUESTS={
 'memory.desktop_analyze':'Analyze contradictions among my saved memories in the HANNI desktop memory screen.',
 'memory.desktop_consolidate':'Consolidate the duplicate synthetic project memories in the desktop memory review.',
 'memory.desktop_correct':'Correct synthetic desktop memory 999999 to say amber rehearsal starts at 3pm.',
 'memory.desktop_forget':'Forget synthetic desktop memory 999999 through its explicit desktop action.',
 'memory.desktop_project.alias':'Give the desktop project Amber Rehearsal the alias Lantern Practice.',
 'memory.desktop_project.unlink':'Unlink synthetic desktop memory 999999 from the Amber Rehearsal project.',
 'memory.desktop_project.workflow':'Link the synthetic desktop workflow wf_fixture to the Amber Rehearsal project.',
 'memory.desktop_review':'Approve synthetic desktop memory 999999 in the memory review queue.',
 'workspace.link.create':'Add an example.test reference link to the Amber Rehearsal desktop project.',
 'workspace.link.delete':'Remove synthetic reference link 999999 from that desktop project.',
 'workspace.note.create':'Create a local desktop note titled Amber Rehearsal with the text Lantern practice is ready.',
 'workspace.note.delete':'Delete only synthetic desktop note 999999.',
 'workspace.note.update':'Update synthetic desktop note 999999 to say Lantern practice is ready.',
 'workspace.notification.clear':'Clear the synthetic desktop notification history.',
 'workspace.notification.dismiss':'Dismiss synthetic desktop notification 999999.',
 'workspace.notification.preferences':'Disable desktop notification toasts for the synthetic campaign account.',
 'workspace.notification.read':'Mark synthetic desktop notification 999999 as read.',
 'workspace.project.create':'Create a local HANNI desktop project called Amber Rehearsal.',
 'workspace.project.delete':'Delete only synthetic desktop project 999999.',
 'workspace.project.update':'Rename synthetic desktop project 999999 to Lantern Practice.',
 'workspace.task.create':'Create a local HANNI desktop task titled Arrange amber rehearsal due tomorrow.',
 'workspace.task.delete':'Delete only synthetic desktop task 999999.',
 'workspace.task.update':'Mark synthetic desktop task 999999 completed.',
 'workspace.workspace.backup':'Create a desktop workspace backup of this synthetic campaign account.',
}


def main():
    p=argparse.ArgumentParser();p.add_argument('--identity',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'data') or output.exists():raise ValueError('Use fresh ignored campaign output.')
    output.mkdir(parents=True)
    inventory=json.loads(args.inventory.read_text(encoding='utf-8'))
    names={d['id'] for d in inventory['capabilities']}
    if names!=set(REQUESTS):raise ValueError('Private inventory changed; define its actual NL scenarios before any inference.')
    cases=[{'capability_id':name,'request':REQUESTS[name],'selection_expectation':'BLOCKED: owner-only private registry not model-facing. No operation may be claimed completed without an actual receipt.'} for name in sorted(names)]
    encoded=json.dumps({'version':1,'cases':cases,'scope':'Real original TextSession inference, explicitly response-only; no tool menu or execution authority.'},sort_keys=True,indent=2).encode()
    (output/'sealed-cases.json').write_bytes(encoded);digest=hashlib.sha256(encoded).hexdigest();(output/'sealed-cases.sha256').write_text(digest+'\n')
    identity=json.loads(args.identity.read_text(encoding='utf-8'))
    config=load_config(identity['config_dir'],data_dir=output/'state',env={})
    original=create_client(config)
    if not original.health().ok:raise RuntimeError('Owned configured endpoint unavailable; no runtime/download fallback.')
    with (output/'results.jsonl').open('x',encoding='utf-8') as handle:
        for case in cases:
            client=RecordingClient(original);session=TextSession(client,system_prompt=system_prompt_for(config.hanni.personality))
            record={**case,'cohort_sha256':digest,'layer_b':'BLOCKED','blocker':'Original private desktop capability is not registered/exposed in the normal chat controller; no selection measurement or handler execution is possible without changing authority.','verification_status':'PENDING_INDEPENDENT_RESPONSE_REVIEW','actual_tools_executed':[]}
            started=time.perf_counter()
            try:record['response']=''.join(session.stream_response(case['request']))
            except Exception as error:record['error']={'class':type(error).__name__,'message':str(error)}
            record['latency_ms']=(time.perf_counter()-started)*1000;record['actual_model_inferences']=client.records
            handle.write(json.dumps(record,ensure_ascii=True,default=str)+'\n');handle.flush()
            print(json.dumps({'capability_id':case['capability_id'],'layer_b':'BLOCKED','actual_model_requests':len(client.records)}),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
