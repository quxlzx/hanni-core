"""Real resident-model/memory/registry text scenarios in isolated owner storage.

No provider calls or remote personal context. Physical voice is NOT TESTED.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cases',type=Path,default=Path('evals/phase3/integrated.json'));args=p.parse_args()
    from hanni.config.loader import load_config
    from hanni.models.client import LlamaCppClient
    from hanni.core.orchestrator import TextSession,system_prompt_for
    from hanni.tools.registry import build_default_registry
    from hanni.mcp.host import McpHost
    from hanni.mcp.session import McpToolSession
    from hanni.memory.store import MemoryStore
    from hanni.memory.retrieval import ContextAwareRetriever
    from hanni.memory.grounded import GroundedPersonalContext
    from hanni.memory.session import MemoryAwareSession
    cases=json.loads(args.cases.read_text())
    freeze=json.loads(Path('evals/phase3/freeze.json').read_text())
    for name,digest in freeze.items():assert hashlib.sha256((Path('evals/phase3')/name).read_bytes()).hexdigest()==digest
    rows=[]
    with tempfile.TemporaryDirectory(prefix='hanni-phase3-',ignore_cleanup_errors=True) as temp:
        root=Path(temp);config=load_config(Path('config'),data_dir=root/'data',env={})
        registry=build_default_registry(config)
        class AbsentVault:
            def get(self,account):return None
            def labels(self):return []
            def preferences(self):return {}
        registry.google_access._vault=AbsentVault()
        client=LlamaCppClient(config.models.supervisor,max_attempts=1)
        text=TextSession(client,system_prompt=system_prompt_for(config.hanni.personality))
        tools=McpToolSession(text,client,McpHost(registry,read_only=True,allowed_actions=()))
        store=MemoryStore(root/'memory.sqlite')
        provider=GroundedPersonalContext(ContextAwareRetriever(store))
        session=MemoryAwareSession(tools,store,registry=registry,context_retriever=provider)
        source=root/'actual notes.txt';source.write_text('Orion has 12 completed tasks.',encoding='utf-8')
        for case in cases:
            started=time.perf_counter();prompt=case['prompt'].replace('{source}',str(source))
            try:
                answer=''.join(session.stream_response(prompt))
                checks=[]
                if 'contains' in case:checks.append(case['contains'].casefold() in answer.casefold())
                if case.get('absent'):checks.append(case['absent'].casefold() not in answer.casefold())
                if case.get('memory_value'):
                    checks.append(any(m.fact_value==case['memory_value'] for m in store.list(limit=50)))
                if case.get('deleted'):checks.append(not store.list(limit=50))
                if case.get('tool'):
                    checks.append(any(r[0]==case['tool'] and r[2].get('ok') for r in tools._turn_results))
                rows.append({'id':case['id'],'answer':answer,'passed':bool(checks) and all(checks),
                             'checks':checks,'duration_ms':(time.perf_counter()-started)*1000})
            except Exception as exc:rows.append({'id':case['id'],'passed':False,'error':str(exc)})
            print(case['id'],rows[-1]['passed'],flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'scope':'LIVE_RESIDENT_TEXT_MEMORY_TOOLS','freeze':freeze,'records':rows,
        'physical_voice':'NOT TESTED','live_calendar':'NOT TESTED','remote_private_context':'BLOCKED by current synthetic-only authorization'},indent=2))


if __name__=='__main__':main()
