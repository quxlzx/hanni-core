"""Actual stdio MCP SDK server with durable test-owned record storage."""
import argparse
import asyncio
import json
import os
from pathlib import Path
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

TOOLS = [
    {'name':'v36.fixture.status','description':'Read the local V36 integration fixture status and stored record count.',
     'inputSchema':{'type':'object','properties':{},'additionalProperties':False},
     'outputSchema':{'type':'object','properties':{'status':{'type':'string'},'record_count':{'type':'integer'}},'required':['status','record_count']},'annotations':{'readOnlyHint':True}},
    {'name':'v36.fixture.echo','description':'Echo the exact supplied message in the V36 integration fixture.',
     'inputSchema':{'type':'object','properties':{'message':{'type':'string','maxLength':500}},'required':['message'],'additionalProperties':False},
     'outputSchema':{'type':'object','properties':{'message':{'type':'string'}},'required':['message']},'annotations':{'readOnlyHint':True}},
    {'name':'v36.fixture.create_record','description':'Create and durably store a titled record in the local V36 integration fixture.',
     'inputSchema':{'type':'object','properties':{'title':{'type':'string','minLength':1,'maxLength':100}},'required':['title'],'additionalProperties':False},
     'outputSchema':{'type':'object','properties':{'created':{'type':'boolean'},'title':{'type':'string'},'record_count':{'type':'integer'}},'required':['created','title','record_count']},'annotations':{'readOnlyHint':False,'destructiveHint':False}},
]


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);args=p.parse_args()
    root=args.directory.resolve()
    workspace=Path(__file__).resolve().parents[2]/'data'
    if not root.is_relative_to(workspace):raise ValueError('Server state must remain in ignored campaign data.')
    root.mkdir(parents=True,exist_ok=True)
    (root/'pid').write_text(str(os.getpid()),encoding='ascii')
    records=root/'records.json'
    if not records.exists():records.write_text('[]',encoding='utf-8')
    async def listed(context,params):
        return types.ListToolsResult(tools=[types.Tool.model_validate(tool) for tool in TOOLS])

    async def called(context,params):
        name,arguments=params.name,params.arguments or {}
        rows=json.loads(records.read_text(encoding='utf-8'))
        if name=='v36.fixture.status':data={'status':'ok','record_count':len(rows)}
        elif name=='v36.fixture.echo':data={'message':arguments['message']}
        elif name=='v36.fixture.create_record':
            title=arguments['title'];rows.append({'title':title})
            temporary=records.with_suffix('.tmp');temporary.write_text(json.dumps(rows),encoding='utf-8');temporary.replace(records)
            data={'created':True,'title':title,'record_count':len(rows)}
        else:raise ValueError('Unknown fixture capability')
        with (root/'calls.jsonl').open('a',encoding='utf-8') as log:
            log.write(json.dumps({'name':name,'arguments':arguments,'result':data})+'\n')
        return types.CallToolResult(content=[types.TextContent(type='text',text=json.dumps(data))],structuredContent=data)

    server=Server('V36 durable fixture',version='1.0',on_list_tools=listed,on_call_tool=called)
    async def run():
        async with stdio_server() as streams:
            await server.run(*streams,server.create_initialization_options())
    asyncio.run(run())


if __name__=='__main__':main()
