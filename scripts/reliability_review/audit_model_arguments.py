"""Post-run structural audit only; no model inference or handler execution."""
from __future__ import annotations
import argparse,json,sys,tempfile
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--label',required=True)
    args=parser.parse_args();sys.path.insert(0,str(args.source/'src'))
    from hanni.config.loader import load_config
    from hanni.tools.registry import build_default_registry
    from hanni.tools.base import ToolDefinition
    from hanni.mcp.host import McpHost
    oracle=json.loads((args.bundle/'live-oracle.json').read_text(encoding='utf8'))
    dynamic=next(name for name in oracle['facts'] if name.startswith('mcp.'))
    report=json.loads((args.bundle/(args.label+'-live-results.json')).read_text(encoding='utf8'))
    rows=[]
    with tempfile.TemporaryDirectory(prefix='hanni-argument-audit-') as directory:
        config=load_config(args.bundle/'original/config',data_dir=Path(directory),env={})
        registry=build_default_registry(config)
        try:
            definitions={McpHost._wire_name(d.name):d for d in registry.definitions()}
            definitions[McpHost._wire_name(dynamic)]=ToolDefinition(dynamic,'Pinned controlled definition.',0,0,{}, {},lambda *a:None,
                side_effect='read',json_input_schema={'type':'object','properties':{},'additionalProperties':False})
            for case in report['results']:
                for turn in case['model_turns']:
                    for call in turn['calls']:
                        definition=definitions.get(call['name']);valid=False
                        if definition:
                            try:definition.validate_arguments(call['arguments']);valid=True
                            except Exception:pass
                        rows.append({'case_id':case['id'],'capability_id':definition.name if definition else None,
                            'known_wire_name':definition is not None,'schema_valid':valid})
        finally:
            service=getattr(registry.context,'reliability',None)
            if service:service.close()
    result={'raw_calls':len(rows),'schema_valid_calls':sum(row['schema_valid'] for row in rows),
        'unknown_wire_calls':sum(not row['known_wire_name'] for row in rows),'calls':rows,
        'scope':'Original definition.validate_arguments on captured actual model calls; metadata-only, no handlers/inference. Dynamic schema fixed by unchanged probe.'}
    (args.bundle/(args.label+'-model-argument-audit.json')).write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({key:value for key,value in result.items() if key!='calls'}))

if __name__=='__main__':main()
