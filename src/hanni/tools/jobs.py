"""Runtime job capabilities; lifecycle operations use the same registry policy."""
import re
import json
from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult


def summary(record):
    if record is None: return 'There are no matching background jobs.'
    if record['status'] == 'COMPLETED':
        return record.get('result_summary') or 'That job is complete.'
    step = f" Step {record['current_step']} of {record['total_steps']}." if record['total_steps'] else ''
    active = f" Current capability: {record['active_capability']}." if record['active_capability'] else ''
    if record.get('model_state') == 'STARTING': active += ' The planner model is loading.'
    elif record.get('model_state') == 'UNHEALTHY' and record.get('heavy'):
        active += ' The specialist is unavailable; Phi-4 planning is the fallback.'
    if record.get('pending_action'):
        active += ' Pending approval: ' + json.dumps(record['pending_action'])
    return f"{record['job_id']} is {record['status'].lower().replace('_',' ')}.{step}{active}"


def definitions(manager):
    def confirmation(args):
        record = manager.get(args.get('job_id'))
        return 'Approve this pending job action: ' + json.dumps(record.get('pending_action') if record else None)
    def read(kind):
        def handler(args, context, request):
            rows = manager.list()
            if kind == 'recent': rows = [r for r in rows if r['status'] in {'COMPLETED','FAILED','CANCELED'}][:10]
            if kind in {'list','recent'}:
                return ToolResult('jobs.'+kind, True, '\n'.join(summary(r) for r in rows[:10]) or 'No background jobs.', {'jobs':rows[:10]})
            record = manager.get(args.get('job_id'))
            message = (record.get('full_result') if kind == 'get' and record else None) or summary(record)
            return ToolResult('jobs.'+kind, True, message, {'job':record})
        return handler
    rows = [ToolDefinition('jobs.'+name, 'Read factual local background job '+name, 0, 0,
                {'job_id':str}, {}, read(name), side_effect='read', background_allowed=False) for name in ('status','list','get','recent')]
    for name in ('pause','resume','cancel','confirm'):
        def handler(args, context, request, action=name):
            return ToolResult('jobs.'+action, True, manager.control(action, args.get('job_id'),
                              confirmed=request.confirmed, reply=args.get('reply')), {})
        rows.append(ToolDefinition('jobs.'+name, 'Control a local job at a safe boundary; no undo',
                    1, 1, {'job_id':str, 'reply':str}, {}, handler,
                    requires_confirmation_if=confirmation if name=='confirm' else None,
                    side_effect='reversible_write', background_allowed=False))
    return tuple(rows)


def route(prompt):
    clean = prompt.strip().lower().rstrip('.?!')
    key = re.search(r'\bjob_[a-f0-9]{12}\b', clean)
    args = {'job_id':key.group()} if key else {}
    if re.fullmatch(r"(?:is (?:that|it) still (?:running|in progress)|are you done(?: with that task)?|what are you working on|how far are you|(?:what's|what is) (?:the )?status(?: of (?:my|that) [\w ]+ task)?|job status)", clean):
        return ToolRequest('jobs.status', args, source='job-control')
    if re.fullmatch(r'(?:show|list)(?: me)?(?: my)? (?:queued |background )?(?:tasks|jobs)', clean):
        return ToolRequest('jobs.list', args, source='job-control')
    if clean in {'what finished recently','what did you finish'}:
        return ToolRequest('jobs.recent', {}, source='job-control')
    if re.fullmatch(r'(?:show|read)(?: me)? (?:the )?(?:result|results)(?: (?:of|for) (?:that task|job_[a-f0-9]{12}))?', clean):
        return ToolRequest('jobs.get', args, source='job-control')
    match = re.fullmatch(r'(pause|resume|cancel|confirm) (?:(?:that|this|the) (?:task|job)|it|that|job_[a-f0-9]{12}|job job_[a-f0-9]{12})', clean)
    if match:
        return ToolRequest('jobs.'+match.group(1), args, source='job-control')
    return None
