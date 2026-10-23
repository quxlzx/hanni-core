"""Resolve mailbox intent and time bounds before provider access."""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from hanni.tools.base import ToolRequest
from hanni.tools.calendar_search import _local_now
from hanni.tools.time_routing import normalize_question

log = logging.getLogger('hanni.email')
CONCEPTS = {
    'temporary password': ('temporary password', 'temp password', 'initial password', 'onboarding password', 'account credentials'),
    'laptop setup': ('laptop setup', 'computer setup', 'device setup', 'equipment setup', 'onboarding instructions', 'pc shipment', 'laptop delivery'),
    'interview': ('interview', 'availability', 'schedule a call'),
    'application link': ('application link', 'apply here', 'application portal'),
    'verify account': ('verify your account', 'verify your email', 'email verification', 'confirm your email'),
}
JOB_TERMS = ('application', 'candidate', 'recruiting', 'recruiter', 'interview', 'assessment',
             'internship', 'onboarding', 'workday', 'hirevue', 'coding challenge', 'job offer',
             'background check', 'talent acquisition', 'software engineer', 'machine learning',
             'phone screen', 'technical screen', 'codesignal', 'hackerrank', 'careers')
# Policy entries document future authority; only read/search definitions exist.
EMAIL_ACTION_POLICY = {
    'search': ('read', False), 'read': ('read', False),
    'draft': ('reversible_write', False), 'reply': ('external_action', True),
    'send': ('external_action', True), 'forward': ('external_action', True),
    'delete': ('destructive', True), 'archive': ('reversible_write', True),
    'mark_spam': ('external_action', True), 'change_labels': ('reversible_write', True),
}


def email_write_requested(prompt: str) -> bool:
    clean = normalize_question(prompt)
    command = r'(?:^|\band\s+|\bthen\s+)(?:(?:please|can you|could you|would you)\s+)?'
    return bool(re.search(command + r'(?:reply|forward)\b|' + command + r'(?:send|draft|compose)\b.*\b(?:email|mail|message|response|reply)\b|'
                          + command + r'(?:delete|archive|mark|label|unsubscribe)\b.*\b(?:email|mail|inbox|thread|message|spam)\b', clean))


@dataclass(frozen=True, slots=True)
class EmailSearchPlan:
    query_type: str
    entity: str = ''
    concepts: tuple[str, ...] = ()
    account: str = ''
    start_time: str = ''
    end_time: str = ''
    temporal_source: str = 'default_90_days'
    ordering: str = 'newest_first'
    limit: int = 5
    require_body: bool = False
    allow_expand: bool = True
    latest: bool = False
    followup: bool = False
    relation: str = 'recent'
    metadata_only: bool = True
    view: str = 'messages'
    numbered: bool = False
    workflow_intent: str = ''

    def request(self) -> ToolRequest:
        log.debug('[email-workflow-plan] intent=%s type=%s range=%s..%s source=%s metadata_initial=%s',
                  self.workflow_intent, self.query_type, self.start_time, self.end_time,
                  self.temporal_source, True)
        return ToolRequest('email.search', {'plan': asdict(self)}, source='email-planner')


def _range(clean, now):
    today = datetime.combine(now.date(), time.min, now.tzinfo)
    source, start, end = 'default_90_days', now - timedelta(days=90), now
    iso = re.search(r'\b20\d{2}-\d{2}-\d{2}\b', clean)
    if iso:
        start = datetime.combine(datetime.fromisoformat(iso[0]).date(), time.min, now.tzinfo)
        return start, start + timedelta(days=1), 'explicit_date'
    if 'yesterday' in clean: start, end, source = today - timedelta(days=1), today, 'yesterday'
    elif re.search(r'\btoday\b', clean): start, source = today, 'today'
    elif 'last week' in clean:
        end = today - timedelta(days=today.weekday()); start, source = end - timedelta(days=7), 'last_week'
    elif 'this week' in clean: start, source = today - timedelta(days=today.weekday()), 'this_week'
    elif 'this month' in clean: start, source = today.replace(day=1), 'this_month'
    elif 'last 7 days' in clean: start, source = now - timedelta(days=7), 'last_7_days'
    elif re.search(r'\b(?:recently|last month|past month)\b', clean) or (re.search(r'\brecent\b', clean) and 'most recent' not in clean):
        start, source = now - timedelta(days=30), 'recent_30_days'
    else:
        since = re.search(r'\bsince (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', clean)
        if since:
            weekday = ('monday','tuesday','wednesday','thursday','friday','saturday','sunday').index(since[1])
            start, source = today - timedelta(days=(today.weekday() - weekday) % 7), 'since_weekday'
    return start, end, source


def body_requested(prompt):
    clean = normalize_question(prompt)
    return bool(re.search(r'\b(?:read|summarize|full body)\b|\bwhat .+?\b(?:say|says|said|want|deadline|password)\b|'
                          r'\bwhat (?:is|are) (?:the |their )?(?:deadline|instructions)\b', clean))


def workflow_intent(clean):
    """Route recruiting questions before the general mailbox/LLM path."""
    if re.search(r'\b(?:applications?|recruiting|internships?|job)\b.*\bdeadlines?\b|\bdeadlines?\b.*\b(?:applications?|recruiting|internships?|job)\b', clean):
        return 'job_deadline'
    if re.search(r'\b(?:verify|confirm) (?:my |your |the )?email\b|\bemail verification\b', clean) and re.search(r'\b(?:company|email|asked?|message)\b', clean):
        return 'verification'
    if re.search(r'\b(?:company|recruiter|recruiting|email)\b.*\b(?:schedule|book|choose|availability|interview|phone screen|technical interview|call)\b|\b(?:interview|recruiter) availability\b', clean) and re.search(r'\b(?:ask|schedule|book|choose|availability|call)\b', clean):
        return 'interview'
    if re.search(r'\b(?:company|recruiter|recruiting|email)\b.*\b(?:ask|request)\b.*\b(?:respond|reply)\b', clean):
        return 'respond'
    job = r'\b(?:job |internship |recruiting )?applications?\b|\b(?:internships?|recruiting (?:tasks?|emails?))\b'
    need = r'\b(?:need|pending|unfinished|outstanding|attention|action|respond|reply|finish|complete|do anything|anything to do)\b'
    if re.search(job, clean) and re.search(need, clean):
        return 'job_action'
    return ''


def email_search_plan(prompt, history=(), *, now=None, timezone_name=None) -> EmailSearchPlan | None:
    clean = normalize_question(prompt)
    if email_write_requested(prompt) or re.search(r'[;\n]', clean): return None
    local = _local_now(now, ZoneInfo(timezone_name or 'America/New_York'))
    if re.fullmatch(r'(?:show|read|open)(?: me)? (?:the )?(?:latest|newest|most recent) one', clean):
        previous = next((str(row.get('content') or '') for row in reversed(history) if row.get('role') == 'user'), '')
        prior = email_search_plan(previous, now=local, timezone_name=timezone_name) if previous else None
        read = body_requested(clean) or clean.startswith('open ')
        return replace(prior, latest=True, limit=1, require_body=read, metadata_only=not read, followup=True) if prior else None
    intent = workflow_intent(clean)
    workflow = bool(intent)
    job_search = bool(re.search(r'\b(?:recruiting|job applications?|application|internship) emails?\b', clean)
                      and re.search(r'\b(?:what|which|show|list|latest|newest|most recent|did i get|did i receive)\b', clean)
                      and not workflow)
    email_word = bool(re.search(r'\b(?:emails?|emailed|e-?mail|inbox|gmail|messages?)\b', clean))
    implicit_sender = re.search(r'^did (.+?) (?:get back to me|contact me|send me anything)(?: recently)?$', clean)
    body_question = bool(re.search(r'^what .+?password did .+? send me', clean))
    if not (workflow or job_search or email_word or implicit_sender or body_question): return None
    # Keep low-level Gmail query/ID requests compatible with the existing tools.
    if re.search(r'\b(?:id|unread|inbox)\b|\b(?:from|subject|label|in):', clean): return None
    if re.match(r'^(?:what is|explain|define|how does)\b', clean) and not re.search(r'\b(?:my|this|latest)\b', clean): return None
    entity = ''
    hit = (re.search(r'^did (.+?) (?:email me|send me (?:an? )?email|send me anything|get back to me|contact me)(?: recently)?$', clean)
           or re.search(r'\b(?:emails?|messages?|mail) from (.+)', clean)
           or re.search(r'\bwhat .+? did (.+?) send me\b', clean)
           or re.search(r'^what (?:did|does) (?:the |my )?(.+?) email (?:say|says|mean)\b', clean))
    if hit:
        entity = re.split(r'\b(?:today|yesterday|this week|last week|this month|recently|in the last month|since|about)\b', hit[1])[0].strip(' .?!')
    concepts = ()
    for key, values in CONCEPTS.items():
        if key in clean or any(value in clean for value in values) or (key == 'verify account' and 'verify my account' in clean):
            concepts = values; break
    if not concepts and not entity and not workflow:
        topic = (re.search(r'\b(?:emails?|messages?|gmail|mail) (?:about|mentioning|with|where|for) (.+)', clean)
                 or re.search(r'\bfind (?:the |my |an? )?(.+?) (?:email|message)$', clean))
        if topic:
            value = re.sub(r'^(?:my|the)\s+', '', topic[1]).strip()
            # "Intel onboarding" has two independent metadata requirements.
            compound = re.fullmatch(r'(.+?) (onboarding|interview|assessment)', value)
            if compound:
                entity, concepts = compound[1], (compound[2],)
            else:
                concepts = (value,) if value else ()
    is_list = bool(re.search(r'\b(?:what|which) companies\b|\b(?:latest|newest|most recent) emails?\b|'
                             r'\b(?:check|show|list) (?:my |the )?emails?\b|\bwhat emails? (?:did|have) i (?:get|receive|got|received)\b|'
                             r'\bimportant emails?\b', clean))
    if not (workflow or job_search or entity or concepts or is_list): return None
    start, end, source = _range(clean, local)
    account = re.search(r'\b(personal|school)\s+(?:gmail|email|mail|account|inbox)\b', clean)
    count = re.search(r'\b(\d{1,2}) (?:most recent|latest|newest|recent) emails?\b', clean)
    plural = bool(re.search(r'\b(?:latest|newest|most recent) emails\b', clean))
    latest = not count and not plural and (body_question or bool(re.search(r'\b(?:latest|newest|most recent)\b', clean)))
    read = bool(workflow or body_requested(clean))
    if read and entity and not count: latest = True
    relation = 'workflow' if workflow else 'about' if concepts and not hit else 'from' if entity else 'recent'
    view = ('organizations' if re.search(r'\b(?:what|which) companies\b', clean) else
            'important' if re.search(r'\bimportant emails?\b', clean) else 'job' if job_search else 'messages')
    return EmailSearchPlan('workflow' if workflow else 'job_search' if job_search else 'semantic' if concepts else 'sender' if entity else 'list',
                           entity, concepts, account[1] if account else '', start.isoformat(), end.isoformat(), source,
                           'relevance' if ((concepts or view == 'important') and not latest) or intent == 'job_deadline' else 'newest_first',
                           limit=min(20, max(1, int(count[1]))) if count else 1 if latest else 5,
                           require_body=read, metadata_only=not read, relation=relation, view=view, numbered=bool(count),
                           allow_expand=source == 'default_90_days' and (relation in {'from','about'} or job_search), latest=latest,
                           workflow_intent=intent)


def email_request(prompt, history=(), *, now=None, timezone_name=None):
    explicit = re.fullmatch(r'(?:read|open) (?:email|message) ([a-zA-Z0-9_-]+) (?:from |in )?(personal|school)(?: email)?[?.!]*', prompt.strip(), re.I)
    if explicit:
        return ToolRequest('email.read', {'id': explicit[1], 'account': explicit[2].lower()}, source='email-read')
    try:
        plan = email_search_plan(prompt, history, now=now, timezone_name=timezone_name)
    except ValueError:
        return None
    return plan.request() if plan else None
