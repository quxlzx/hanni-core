"""Offline Gmail transport evaluation; no live account, model or command execution.

Run: python -m hanni.evals.email
These metrics describe this fixture set, not general mailbox accuracy.
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from pathlib import Path

from hanni.evals.routing import build_default_host
from hanni.tools.email_tools import definitions
from hanni.tools.google_access import GoogleAccess, GoogleAccessError

NOW = datetime.fromisoformat('2026-09-25T10:00:00-04:00')
CASES = Path('evals/email/cases.json')


class FixtureMailbox:
    def __init__(self, case):
        self.calls, self.messages, self.error = [], [], case.get('provider_error')
        for item in case['messages']:
            self.messages.append({'id':item['id'],'threadId':item.get('thread',item['id']),
                'internalDate':str(int(datetime.fromisoformat(item.get('date','2026-09-24T12:00:00-04:00')).timestamp()*1000)),
                'snippet':'Fixture notification', 'labelIds':['INBOX'],
                'payload':{'mimeType':'text/plain','headers':[{'name':'From','value':item['sender']},
                           {'name':'Subject','value':item['subject']}],
                           'body':{'data':base64.urlsafe_b64encode(item['body'].encode()).decode()}}})

    def get(self, account):
        return {'email':'fixture@example.test','credentials':{}} if account == 'personal' else None

    def __call__(self, account, path, params):
        self.calls.append((path,dict(params)))
        if self.error: raise GoogleAccessError(self.error)
        if path.endswith('/messages'):
            query=params['q']; terms=re.findall(r'(?:(from|subject):)?"([^"]+)"',query)
            first,last=(int(re.search(key+r':(\d+)',query)[1]) for key in ('after','before'))
            rows=[]
            for row in self.messages:
                headers={h['name'].lower():h['value'] for h in row['payload']['headers']}
                text=' '.join(headers.values())+' '+base64.urlsafe_b64decode(row['payload']['body']['data']).decode()
                if first < int(row['internalDate'])/1000 < last and (not terms or any(t.casefold() in (headers.get(field,'') if field else text).casefold() for field,t in terms)):
                    rows.append({'id':row['id'],'threadId':row['threadId']})
            return {'messages':rows[:params['maxResults']]}
        if '/threads/' in path: return {'messages':[m for m in self.messages if m['threadId']==path.rsplit('/',1)[1]]}
        row=next(m for m in self.messages if m['id']==path.rsplit('/',1)[1])
        return row if params['format']=='full' else {**row,'payload':{'headers':row['payload']['headers']}}


def evaluate(case, host):
    mailbox=FixtureMailbox(case)
    tools={tool.name:tool for tool in definitions(GoogleAccess(mailbox,mailbox,'America/New_York'))}
    route=host.route(case['query'],history=case.get('history',()),now=NOW)
    expected=case.get('capability','email.search')
    checks={'routing':route.status=='blocked' if case.get('blocked') else
            len(route.tools)==1 and route.tools[0].capability_id==expected}
    if case.get('blocked'):
        checks['unsafe_action']=not route.tools and not mailbox.calls
        return {'id':case['id'],'category':case['category'],'checks':checks,'passed':all(checks.values())}
    if not checks['routing']: return {'id':case['id'],'category':case['category'],'checks':checks,'passed':False}
    args=route.tools[0].fixed_arguments
    plan=args.get('plan',{})
    checks['query_plan']=((not case.get('type') or plan.get('query_type')==case['type'])
                          and (not case.get('entity') or plan.get('entity')==case['entity']))
    result=tools[expected].handler(args,None,None)
    data=result.data
    ids=[row['message_id'] for row in data.get('messages',[])]
    checks['retrieval']=set(ids)==set(case['expected_ids'])
    checks['thread_selection']=len(ids)==len(set(ids)) and checks['retrieval']
    items={item['source_message_id']:item for item in data.get('action_items',[])}
    if 'pending' in case:
        checks['action_classification']={key for key,item in items.items() if item['status'] in {'ACTION_REQUIRED','POSSIBLE_ACTION'}}==set(case['pending'])
    if 'statuses' in case:
        checks['action_classification']=checks.get('action_classification',True) and all(items.get(key,{}).get('status')==status for key,status in case['statuses'].items())
    if 'deadlines' in case:
        checks['deadline_extraction']=all(items.get(key,{}).get('deadline')==value for key,value in case['deadlines'].items())
    checks['grounded_answer']=all(term in result.message for term in case.get('contains',[]))
    checks['no_hallucination']=all(term not in result.message for term in case.get('excludes',[])) and set(ids)<=set(m['id'] for m in case['messages'])
    if 'status' in case: checks['grounded_answer'] &= data.get('status')==case['status']
    if 'error' in case: checks['grounded_answer'] &= any(e['code']==case['error'] for e in data.get('errors',[]))
    if 'metadata_only' in case:
        checks['body_policy'] = (not any(params.get('format') == 'full' for _,params in mailbox.calls)
                                 if case['metadata_only'] else any(params.get('format') == 'full' for _,params in mailbox.calls))
    if 'ordered_ids' in case: checks['result_order'] = ids == case['ordered_ids']
    if 'relation' in case: checks['query_plan'] &= plan.get('relation') == case['relation']
    checks['unsafe_action']=set(tools)=={'email.search','email.read'} and all('/messages' in path or '/threads/' in path for path,_ in mailbox.calls)
    return {'id':case['id'],'category':case['category'],'checks':checks,'passed':all(checks.values())}


def run(path=CASES):
    host=build_default_host(timezone_name='America/New_York')
    rows=[evaluate(case,host) for case in json.loads(Path(path).read_text(encoding='utf-8'))]
    metrics={}
    for key in sorted({key for row in rows for key in row['checks']}):
        values=[row['checks'][key] for row in rows if key in row['checks']]
        metrics[key]={'passed':sum(values),'checks':len(values)}
    return {'cases':len(rows),'passed':sum(row['passed'] for row in rows),'metrics':metrics,'results':rows}


if __name__=='__main__':
    report=run(); print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['passed']==report['cases'] else 1)
