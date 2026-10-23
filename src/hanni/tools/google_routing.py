"""Small Google service menus and short-lived, account-bound result references."""
from __future__ import annotations

import re
import time
from copy import deepcopy

from .base import ToolRequest
from .google_identity import GoogleAccessError


def requested_account(prompt):
    clean = prompt.casefold()
    explicit = re.search(r'\baccount\s+([a-z][a-z0-9_-]{0,31})\b', clean)
    before = (re.search(r'\b(personal|school|work)\s+(?:google\s+)?(?:calendar|schedule|gmail|email|drive|docs|tasks|account)\b', clean)
              or re.search(r'\b([a-z][a-z0-9_-]{0,31})\s+account\b', clean))
    hit = explicit or before
    if hit and hit[1] not in {'my', 'the', 'a', 'an', 'google', 'in', 'on', 'for', 'your', 'check', 'read', 'search', 'recent', 'new', 'all', 'both', 'list', 'what', 'which', 'this', 'default'}:
        return hit[1]
    return None


def google_request(prompt, *, history=(), now=None, timezone_name=None):
    clean = re.sub(r'\s+', ' ', prompt.strip().rstrip('?.!')).casefold()
    account = requested_account(clean)
    if account:
        # Account qualifiers select the provider; they are not search terms.
        qualifier = r'\b(?:account\s+' + re.escape(account) + r'|' + re.escape(account) + r'\s+account)\b'
        clean = re.sub(qualifier, '', clean).strip()
        prompt = re.sub(qualifier, '', prompt, flags=re.I).strip()
    args = {'account': account} if account else {}
    if re.search(r'\bgmail\b', clean):
        if re.match(r'^(?:search gmail for|find gmail messages from)\b', clean):
            return None  # Existing mail search handles these sender/query forms.
        if re.search(r'\b(?:full body|that gmail message)\b|\b(?:subject|from|in):', clean):
            return None  # Preserve established explicit Gmail query/body routes.
        item = re.search(r'\b(message|thread)\s+(?:id\s+)([a-z0-9_-]+)\b', prompt, re.I)
        if item and re.match(r'^(?:read|open|show)', clean):
            return ToolRequest('google.gmail.thread' if item[1].casefold() == 'thread' else 'google.gmail.read',
                               {**args, 'id': item[2]}, source='google-intent')
        if re.match(r'^(?:reply|send|delete|archive|forward|compose|draft|email)\b', clean): return None
        count = re.search(r'\b(\d{1,2})\b', clean)
        args['limit'] = min(30, max(1, int(count[1]))) if count else 5
        term = re.search(r'\b(from|about|subject)\s+(.+?)(?:\s+(?:in|on)\s+(?:my\s+)?gmail)?$', clean)
        if term:
            # Text is a query value for the fixed Gmail API, never a URL.
            args['query'] = ('from:' if term[1] == 'from' else 'subject:' if term[1] == 'subject' else '') + term[2]
            return ToolRequest('google.gmail.search', args, source='google-intent')
        return ToolRequest('google.gmail.recent', args, source='google-intent')
    if re.search(r'\bgoogle calendars?\b', clean):
        if re.search(r'\bwhich google calendars\b', clean) or re.match(r'^(?:personal|school|work|both|all) google calendars?\b', clean): return None
        item = re.search(r'\bevent\s+id\s+([a-z0-9_-]+)\b', prompt, re.I)
        if item:
            operation = 'delete' if re.match(r'^(?:delete|remove|cancel)', clean) else 'update' if re.match(r'^(?:update|move|rename)', clean) else 'read'
            return ToolRequest('google.calendar.' + operation, {**args, 'id': item[1]}, source='google-intent')
        from .calendar_routing import calendar_read_request, calendar_create_request
        plan = calendar_create_request(prompt, now=now, timezone_name=timezone_name) or calendar_read_request(prompt, history, now=now, today=now.date() if now else None, timezone_name=timezone_name)
        if plan:
            if plan.arguments.get('academic_concept') or clean.startswith('put '):
                return None  # Keep the established academic and creation routes.
            names = {'google_calendar.agenda': 'google.calendar.availability' if re.search(r'\b(?:free|busy|available)\b', clean) else 'google.calendar.events',
                     'google_calendar.next': 'google.calendar.next', 'google_calendar.list': 'google.calendar.list_calendars',
                     'google_calendar.create': 'google.calendar.create'}
            return ToolRequest(names[plan.name], {**plan.arguments, **args}, source='google-intent')
    if re.search(r'\bgoogle tasks?\b', clean):
        creation = re.match(r'^(?:please )?(?:add|create)\s+(.+?)\s+(?:to|in)\s+(?:my )?(?:(?:personal|school|work) )?google tasks?[.!?]?$', prompt.strip(), re.I)
        if creation:
            return ToolRequest('google.tasks.create', {**args, 'title': creation[1]}, source='google-intent')
        if re.match(r'^(?:mark|complete|finish|delete|remove)\b', clean):
            return ToolRequest('google.tasks.complete', args, source='google-intent')
        return ToolRequest('google.tasks.list', args, source='google-intent')
    docs = bool(re.search(r'\bgoogle docs?\b', clean))
    direct = re.search(r'\b(?:google doc|drive file)\s+id\s+([a-zA-Z0-9_-]+)\b', prompt, re.I)
    if direct:
        return ToolRequest('google.docs.read' if docs and re.match(r'^(?:read|summarize)', clean) else 'google.drive.metadata',
                           {**args, 'id': direct[1]}, source='google-intent')
    named_doc = re.match(r'^(?:read|summarize)\s+(?:my |the )?(.+?)(?:\s+in\s+(?:google\s+)?drive)?$', clean)
    if named_doc and (docs or re.search(r'\b(?:doc|document|research notes)\b', named_doc[1])):
        query = re.sub(r'\bgoogle docs?\b', '', named_doc[1]).strip()
        query = re.sub(r'\s+(?:doc|document)$', '', query)
        if query:
            return ToolRequest('google.docs.read', {**args, 'query': query[:300]}, source='google-intent')
    if not (docs or re.search(r'\bdrive\b', clean) and not re.search(r'\b[a-z](?::|\s+drive)\b|\bdrive\s+[a-z]\b|\b(?:hard|disk|usb|local|this|flash|external)\s+drive\b|\b(?:bitlocker|encrypted|capacity|disk space|free space|partition|storage|thrashing|full|failing|healthy|health|room)\b', clean)):
        return None
    if re.match(r'^(?:(?:please|can you|could you)\s+)?(?:delete|share|edit|write|move|upload|remove|wipe|format)\b', clean):
        return ToolRequest('google.drive.delete' if 'delete' in clean else 'google.docs.write', args, source='google-intent')
    docs = docs or bool(re.search(r'\b(?:read|summarize)\b.*\b(?:doc|document|notes)\b', clean))
    query = re.sub(r'^(?:please )?(?:find|search|look for|show|list|read|summarize|where is)(?: me)?\s+(?:my |the )?', '', clean)
    query = re.sub(r'^(?:(?:personal|school|work)\s+)?(?:google\s+)?(?:drive|docs?)\s+(?:for\s+)?', '', query)
    query = re.sub(r'\s+(?:in|on|from)\s+(?:my\s+)?(?:(?:' + re.escape(account or 'personal|school|work') + r')\s+)?(?:google\s+)?drive$', '', query)
    if docs:
        query = re.sub(r'\bgoogle docs?\b', '', query)
    recent = bool(re.search(r'\b(?:recent|latest|newest)\b', query))
    query = re.sub(r'\b(?:my|recent|latest|newest|files|documents|show|me)\b', '', query).strip()
    query = re.sub(r'^about\s+', '', query)
    args.update(limit=10, docs_only=docs)
    if query: args['query'] = query[:300]
    operation = 'search' if query else 'recent' if recent else 'list'
    return ToolRequest('google.drive.' + operation, args, source='google-intent')


def google_service(name):
    if name.startswith(('email.', 'gmail.', 'google.gmail.')): return 'gmail'
    if name.startswith(('google_calendar.', 'google.calendar.')): return 'calendar'
    if name.startswith('google.drive.'): return 'drive'
    if name.startswith('google.docs.'): return 'docs'
    if name.startswith('google.tasks.'): return 'tasks'
    return None


class GoogleDialogue:
    """Only object IDs and minimal metadata survive a turn; never raw content."""
    def __init__(self, clock=time.monotonic, ttl=900):
        self.clock, self.ttl = clock, ttl
        self.updated = 0
        self.active_google_service = self.active_google_account = None
        self.last_google_query = None
        self.last_google_results = []
        self.last_selected_google_item = None

    def remember(self, tool, result, arguments=None):
        service = google_service(tool.capability_id)
        if not service: return
        data = result.get('data') or {}
        rows = data.get('messages') or data.get('files') or data.get('events') or data.get('tasks') or []
        if not rows and data.get('event'): rows = [data['event']]
        args = deepcopy({**(arguments or {}), **tool.fixed_arguments})
        if 'id' in args and self.last_google_results:
            matching = next((row for row in self.last_google_results if row['id'] == args['id'] and
                             row['account'] == args.get('account')), None)
            if matching:
                self.last_selected_google_item = dict(matching)
                return
        self.active_google_service = service
        self.last_google_results = []
        self.last_selected_google_item = None
        if 'id' not in args:
            self.last_google_query = (tool.capability_id, args)
        for row in rows[:30]:
            item_id = row.get('message_id') or row.get('id')
            account = row.get('account') or data.get('account')
            if not item_id or not account: continue
            item = {'id': item_id, 'account': account, 'service': service,
                    **{key: row[key] for key in ('type', 'calendar_id', 'tasklist_id', 'thread_id') if row.get(key)}}
            self.last_google_results.append(item)
            row['ref'] = str(len(self.last_google_results))
        accounts = {row['account'] for row in self.last_google_results}
        self.active_google_account = next(iter(accounts)) if len(accounts) == 1 else data.get('account') or args.get('account')
        self.updated = self.clock()

    def followup(self, prompt):
        clean = prompt.casefold().strip(' .?!')
        reference = re.fullmatch(r'(open|read|show|summarize)(?: me)?(?: the)? (\d+|it|newest one|latest one|first one)', clean)
        account_switch = re.fullmatch(r'(?:what about|how about|and|check)(?: my| the)? ([a-z][a-z0-9_-]{0,31}) account', clean)
        if not (reference or account_switch): return None
        if not self.active_google_service: return None
        if self.clock() - self.updated > self.ttl:
            self.last_google_results = []
            self.last_google_query = None
            raise GoogleAccessError('That Google reference expired. Search again before opening it.', 'not_found')
        if account_switch:
            if not self.last_google_query: return None
            name, args = deepcopy(self.last_google_query)
            args['account'] = account_switch[1]
            if isinstance(args.get('plan'), dict): args['plan']['account'] = account_switch[1]
            return ToolRequest(name, args, source='google-followup')
        if not self.active_google_service: return None
        if not self.last_google_results:
            raise GoogleAccessError('There is no current Google result to open. Search again.', 'not_found')
        index = int(reference[2]) - 1 if reference[2].isdigit() else 0
        if reference[2] == 'it' and len(self.last_google_results) != 1:
            raise GoogleAccessError('Which result number should I open?', 'invalid_arguments')
        if not 0 <= index < len(self.last_google_results):
            raise GoogleAccessError('That result number is not in the current Google results.', 'not_found')
        item = self.last_google_results[index]
        self.last_selected_google_item = dict(item)
        service = item['service']
        args = {key: item[key] for key in ('account', 'id', 'calendar_id', 'tasklist_id') if key in item}
        if service == 'gmail': return ToolRequest('email.read', {**args, 'metadata_only': reference[1] == 'show'}, source='google-followup')
        if service == 'calendar': return ToolRequest('google.calendar.read', args, source='google-followup')
        if service in {'drive', 'docs'}:
            name = 'google.docs.read' if reference[1] in {'read', 'summarize'} else 'google.drive.metadata'
            return ToolRequest(name, args, source='google-followup')
        return None
