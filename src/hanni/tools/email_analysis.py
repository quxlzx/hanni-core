"""Conservative, extractive reasoning over untrusted mailbox evidence."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from hanni.tools.email_provider import NormalizedEmail

_MARKETING = re.compile(r'\b(?:newsletter|job recommendations|jobs? (?:you may|for you)|weekly digest|promotional|sale ends)\b', re.I)
_JOB = re.compile(r'\b(?:applications?|candidate|recruit\w*|interview|assessment|coding challenge|technical screen|phone screen|software engineer|machine learning|careers?|talent|codesignal|hackerrank|lever|OA|HireVue|Workday|Greenhouse|SmartRecruiters|intern\w*|resume|job offer|onboarding|background check|talent acquisition)\b', re.I)
_ACTIONS = (
    (r'\b(?:complete|take|finish|submit)\b.{0,70}\b(?:assessment|coding challenge|hirevue|take.home|OA)\b|\b(?:coding|technical) assessment\b', 'Complete the assessment'),
    (r'\b(?:schedule|book|select|choose)\b.{0,55}\b(?:interview|slot|time|call|phone screen)\b|\b(?:provide|send|share|reply with|respond with)\b.{0,40}\bavailability\b', 'Schedule the interview or provide availability'),
    (r'\b(?:verify|confirm)\b.{0,35}\b(?:email|account)\b', 'Verify the email or account'),
    (r'\b(?:complete|finish|update)\b.{0,35}\bprofile\b|\bprofile\b.{0,30}\bincomplete\b', 'Complete the profile'),
    (r'\b(?:submit|complete|finish)\b.{0,35}\bapplication\b|\bapplication\b.{0,30}\bincomplete\b', 'Complete the application'),
    (r'\b(?:upload|provide|send)\b.{0,45}\b(?:documents|information|resume)\b|\badditional information (?:is )?(?:needed|required)\b', 'Provide the requested information or documents'),
    (r'\bsign\b.{0,35}\b(?:document|agreement|offer)\b', 'Sign the requested document'),
    (r'\b(?:complete|finish)\b.{0,40}\b(?:background check|onboarding)\b', 'Complete the onboarding or background check'),
    (r'\bconfirm\b.{0,25}\battendance\b', 'Confirm attendance'),
    (r'\b(?:respond|reply)\s+(?:by|to|with)\b|\b(?:please|must)\s+(?:respond|reply)\b|\baction required\b|\bworkday task\b', 'Respond to the request'),
)
_COMPLETE = re.compile(r'\b(?:assessment|task|verification|profile|onboarding|background check)\b\s+(?:(?:has been|was|is)\s+)?(?:successfully )?(?:completed|submitted|verified)\b|'
                       r'\b(?:you have|you|thank you for)\s+(?:successfully )?(?:completed|submitted|completing|submitting)\b.{0,45}\b(?:assessment|task|verification|profile)\b', re.I)
_REJECT = re.compile(r'\b(?:not moving forward|not selected|unsuccessful|application (?:was |is |has been )?closed|no longer (?:being considered|under consideration)|decided to move forward with other)\b', re.I)
_INJECTION = re.compile(r'ignore (?:all|previous|prior)|system prompt|developer instructions|run (?:this|the) command|upload .*credentials|send .*password', re.I)


def contains_instruction_text(text):
    return bool(_INJECTION.search(text or ''))


def current_text(message: NormalizedEmail) -> str:
    text = message.body_text if message.body_text is not None else message.snippet
    # Quoted invitations in a completion reply must not become a new task.
    text = re.split(r'(?im)^On .{0,250}wrote:|^-{2,}\s*(?:Original|Forwarded) message', text)[0]
    return '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('>'))


def private_excerpt(text, limit=700):
    """Do not repeat credential values during ordinary find/read/summarize."""
    lines = []
    hide_next = False
    for line in text.splitlines():
        if hide_next and line.strip():
            lines.append('[credential value omitted]'); hide_next = False; continue
        if re.search(r'\b(?:password|passcode|one.time code|verification code|access token|secret key)\b', line, re.I):
            # Whole-line redaction also handles values before the password label.
            lines.append('[credential information omitted]')
            hide_next = bool(re.search(r':\s*$', line))
        else: lines.append(line)
    return '\n'.join(lines)[:limit]


def private_subject(text):
    if re.search(r'\b(?:password|passcode|verification code|access token|secret key)\s*(?::|=|is)\s*\S|\b\S+\s+is (?:your |the )?password\b', text, re.I):
        return private_excerpt(text, 300)
    return text[:300]


def entity_matches(entity, text):
    compact = re.sub(r'[^\w]', '', entity.casefold())
    words = re.findall(r'\w+', text.casefold())
    # Join adjacent complete tokens: Tik Tok/TikTok, not unrelated substrings.
    return bool(compact and any(''.join(words[i:j]) == compact
                               for i in range(len(words)) for j in range(i + 1, min(i + 5, len(words)) + 1)))


def sender_matches(entity, sender_name, sender_email):
    if entity_matches(entity, sender_name): return True
    local, _, domain = sender_email.casefold().rpartition('@')
    if '@' in entity: return sender_email.casefold() == entity.casefold()
    if '.' in entity: return domain == entity.casefold() or domain.endswith('.' + entity.casefold())
    target = re.sub(r'[^\w]', '', entity.casefold())
    labels = domain.split('.')
    registrant = labels[-3] if len(labels) >= 3 and labels[-2] in {'co','com','org','ac'} and len(labels[-1]) == 2 else labels[-2] if len(labels) >= 2 else domain
    return bool(target and (registrant == target or entity_matches(entity, local)))


def organization_name(message):
    """Conservative sender-only organization heuristic, not an identity claim."""
    name, address = message.sender_name.strip(), message.sender_email.casefold()
    local, _, domain = address.rpartition('@')
    public = {'gmail.com','outlook.com','hotmail.com','yahoo.com','icloud.com','live.com','aol.com','proton.me','protonmail.com'}
    org_hint = bool(re.search(r'\b(?:rewards|team|recruiting|university|college|association|club|support|news|notifications|inc|llc)\b|\b[A-Z]{2,}\b', name))
    parts = re.findall(r'[A-Za-z]+', name)
    personal = (len(parts) == 2 and not org_hint and
                (local == parts[0].lower() or local.startswith(parts[0].lower() + '.')))
    if (domain in public and not org_hint) or personal: return None
    if not domain: return None
    return name or domain


_PRIORITY = re.compile(r'\b(?:action required|deadline|interview|assessment|account|payment|security|failed|urgent|outstanding|due|required)\b', re.I)
_RECEIPT = re.compile(r'\b(?:forms? response receipts?|response receipt|copy of your responses|form submission received)\b', re.I)
_SOCIAL = re.compile(r'\b(?:social|forum|digest|reddit|linkedin|facebook|instagram|pinterest|quora|discord|x notifications?)\b', re.I)
_PROMOTION = re.compile(r'\b(?:sale|deals?|rewards|coupon|promotion|shopping|food order|receipt)\b', re.I)
_RECRUIT_SENDER = re.compile(r'\b(?:recruit\w*|careers?|jobs?|talent|hiring|workday|greenhouse|lever|smartrecruiters|hirevue|codesignal|hackerrank)\b', re.I)


def recruiting_candidate_score(message):
    """Use headers only; a social post mentioning an interview is not a recruiter."""
    sender = f'{message.sender_name} {message.sender_email}'
    domain = message.sender_email.rpartition('@')[-1]
    subject = message.subject
    if _SOCIAL.search(sender) or _PROMOTION.search(sender + ' ' + subject) or _MARKETING.search(subject) or _RECEIPT.search(subject):
        return 0
    subject_job = bool(_JOB.search(subject))
    sender_job = bool(_RECRUIT_SENDER.search(sender))
    if not (subject_job or sender_job): return 0
    public = {'gmail.com','outlook.com','hotmail.com','yahoo.com','icloud.com','live.com','aol.com','proton.me','protonmail.com'}
    company = bool(domain and domain not in public and organization_name(message))
    return (30 if sender_job else 0) + (25 if subject_job else 0) + (15 if company else 0)


def email_verification_requested(text):
    return bool(re.search(r'\b(?:verify|confirm|validate|activate)\s+(?:your |my |the |this )?(?:email|e-mail)(?: address)?\b|'
                          r'\b(?:email|e-mail)\s+verification(?: link)?\b', text, re.I))


def interview_request(text):
    return bool(re.search(r'\b(?:schedule|book|choose|select|confirm|arrange)\b.{0,65}\b(?:interview|call|phone screen|time|slot)\b|'
                          r'\b(?:provide|send|share|reply with|respond with)\b.{0,50}\bavailability\b', text, re.I))


def response_request(text):
    return bool(re.search(r'\b(?:please|must|kindly)\s+(?:respond|reply)\b|\b(?:respond|reply)\s+(?:with|to|by)\b|'
                          r'\b(?:provide|send|share)\b.{0,45}\bavailability\b', text, re.I))


def metadata_relevance(message, plan):
    sender = f'{message.sender_name} {message.sender_email}'
    header = sender + ' ' + message.subject
    if plan.relation == 'from':
        return 100 if sender_matches(plan.entity, message.sender_name, message.sender_email) else 0
    if plan.view == 'organizations': return 10 if organization_name(message) else 0
    if plan.view == 'important':
        signals = len(_PRIORITY.findall(message.subject))
        if _MARKETING.search(message.subject): return 0
        return signals * 20 + (5 if 'UNREAD' in message.labels else 0) + (5 if _JOB.search(header) else 0)
    if plan.view == 'job' or plan.relation == 'workflow':
        score = recruiting_candidate_score(message)
        if plan.workflow_intent == 'verification':
            if _SOCIAL.search(sender) or _MARKETING.search(message.subject): return 0
            return (score + 50) if email_verification_requested(message.subject) else score if re.search(r'\b(?:verification|verify|confirm|activate|account)\b', message.subject, re.I) else 0
        if not score: return 0
        if plan.workflow_intent == 'job_deadline':
            return score + 35 * len(re.findall(r'\b(?:deadline|due|assessment|action required|outstanding)\b', message.subject, re.I))
        if plan.workflow_intent == 'interview':
            return score if re.search(r'\b(?:interview|availability|screen|schedule|call)\b', header, re.I) else 0
        return score
    if plan.relation == 'recent': return 10
    if plan.entity and not entity_matches(plan.entity, header): return 0
    hits = sum(entity_matches(concept, message.subject) for concept in plan.concepts)
    if not hits and plan.concepts:
        words = re.findall(r'\w+', plan.concepts[0].casefold())
        hits = int(bool(words) and all(re.search(r'\b' + re.escape(word) + r'\b', message.subject.casefold()) for word in words))
    sender_hit = bool(plan.entity and sender_matches(plan.entity, message.sender_name, message.sender_email))
    if any('interview' in concept for concept in plan.concepts):
        if _SOCIAL.search(sender) or _MARKETING.search(message.subject) or _PROMOTION.search(sender): return 0
        if hits and recruiting_candidate_score(message): return 100 + recruiting_candidate_score(message)
        return 0
    return (80 + hits + 20 * sender_hit) if hits else 20 if sender_hit else 0


def relevance(message, plan):
    score = metadata_relevance(message, plan)
    if score >= 80 or plan.relation != 'about' or message.body_text is None: return score
    if any('interview' in concept for concept in plan.concepts) and not recruiting_candidate_score(message):
        return 0
    text = f'{message.sender_name} {message.sender_email} {message.subject} {message.body_text}'
    if plan.entity and not entity_matches(plan.entity, text): return 0
    return max(5, score) if any(entity_matches(concept, text) for concept in plan.concepts) else 0


def deadline_from(text, received_at, timezone_name):
    """Only explicit dates or unambiguous 'within N days'; no guessed times."""
    zone = ZoneInfo(timezone_name or 'America/New_York')
    base = received_at.astimezone(zone)
    relative = re.search(r'\bwithin (\d{1,2}) days\b', text, re.I)
    if relative:
        return (base + timedelta(days=int(relative[1]))).isoformat(), 'relative_explicit', relative[0]
    months = {name: i for i, name in enumerate(('january','february','march','april','may','june','july','august','september','october','november','december'), 1)}
    months.update({name[:3]: i for name, i in list(months.items())})
    hit = re.search(r'\b(?:by|due(?: on| by)?|deadline(?: is|:)?|before)\s+('
                    + '|'.join(months) + r')\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(20\d{2}))?'
                    r'(?:\s+(?:at|by)\s+(\d{1,2})(?::(\d{2}))?\s*(AM|PM)(?:\s+(ET|EST|EDT|PT|PST|PDT|UTC))?)?', text, re.I)
    iso = re.search(r'\b(?:by|due|deadline)\s+(20\d{2}-\d{2}-\d{2})\b', text, re.I)
    if not hit:
        if iso:
            try: return datetime.fromisoformat(iso[1]).date().isoformat(), 'explicit_date', iso[0]
            except ValueError: pass
        return None, None, None
    month, day, year = months[hit[1].lower()], int(hit[2]), int(hit[3]) if hit[3] else base.year
    if not hit[3] and base.month == 12 and month == 1: year += 1
    try:
        date = datetime(year, month, day)
        if not hit[4]: return date.date().isoformat(), 'explicit_date', hit[0]
        hour = int(hit[4]); minute = int(hit[5] or 0)
        if not 1 <= hour <= 12 or minute > 59: return None, None, None
        tz = (hit[7] or '').upper()
        if tz in {'ET','EST','EDT'}: zone = ZoneInfo('America/New_York')
        elif tz in {'PT','PST','PDT'}: zone = ZoneInfo('America/Los_Angeles')
        elif tz == 'UTC': zone = ZoneInfo('UTC')
        value = date.replace(hour=hour % 12 + (12 if hit[6].upper() == 'PM' else 0), minute=minute, tzinfo=zone)
        return value.isoformat(), 'explicit', hit[0]
    except ValueError: return None, None, None


@dataclass(frozen=True, slots=True)
class EmailActionItem:
    company: str
    sender: str
    subject: str
    received_at: str
    action: str | None
    deadline: str | None
    deadline_source: str | None
    deadline_evidence: str | None
    status: str
    confidence: float
    source_message_id: str
    thread_id: str | None
    account: str
    evidence: str

    def to_dict(self):
        return {**asdict(self), 'subject': private_excerpt(self.subject, 300),
                'evidence': private_excerpt(self.evidence, 160)}


def classify(message, timezone_name):
    body = current_text(message)
    text = message.subject + '\n' + body
    status, action, evidence = 'UNKNOWN', None, ''
    if _MARKETING.search(text) or _RECEIPT.search(message.subject + ' ' + message.sender_name): status = 'INFORMATIONAL'
    elif _REJECT.search(text): status = 'REJECTED'
    elif _COMPLETE.search(body) and not re.search(r'\b(?:not|incomplete|haven.t|haven’t)\b.{0,25}\bcompleted\b', body, re.I): status = 'COMPLETED'
    elif re.search(r'\b(?:no (?:further )?action (?:is )?required|no need to (?:reply|respond|complete)|you (?:do not|don.t) need to|not required to)\b', body, re.I): status = 'INFORMATIONAL'
    elif _JOB.search(text) or email_verification_requested(text):
        for pattern, label in _ACTIONS:
            found = re.search(pattern, body, re.I | re.S)
            if found:
                action, status, evidence = label, 'ACTION_REQUIRED', private_excerpt(found[0], 160); break
        if action is None:
            if re.search(r'\b(?:application received|thank you for applying|received your application)\b', text, re.I): status = 'APPLICATION_RECEIVED'
            elif re.search(r'\b(?:offer of employment|pleased to offer|job offer)\b', text, re.I): status = 'OFFER'
            elif 'interview' in text.lower(): status = 'INTERVIEW'
            elif re.search(r'\b(?:deadline|action required|outstanding task|required|due)\b', body, re.I):
                status = 'POSSIBLE_ACTION'
                evidence = private_excerpt(body, 160)
            else: status = 'STATUS_UPDATE'
    deadline, source, deadline_evidence = deadline_from(body, message.received_at, timezone_name)
    if message.body_truncated and status == 'ACTION_REQUIRED': status = 'POSSIBLE_ACTION'
    return EmailActionItem(message.sender_name or message.sender_email, message.sender_email,
                           message.subject, message.received_at.isoformat(), action, deadline, source,
                           deadline_evidence, status, .9 if status == 'ACTION_REQUIRED' else .7,
                           message.message_id, message.thread_id, message.account, evidence)


def thread_state(messages, timezone_name):
    incoming = sorted((m for m in messages if not {'SENT', 'DRAFT'} & set(m.labels)),
                      key=lambda m: m.received_at, reverse=True)
    for message in incoming:
        item = classify(message, timezone_name)
        if item.status != 'UNKNOWN':
            if item.status in {'ACTION_REQUIRED', 'POSSIBLE_ACTION'} and not item.deadline:
                older = next((classify(prior, timezone_name) for prior in incoming
                              if prior.received_at < message.received_at and deadline_from(current_text(prior), prior.received_at, timezone_name)[0]), None)
                if older and older.deadline:
                    item = replace(item, deadline=older.deadline, deadline_source=older.deadline_source,
                                   deadline_evidence=older.deadline_evidence)
            return item
    return classify(incoming[0], timezone_name) if incoming else None


def workflow_matches(items, intent):
    active = [item for item in items if item['status'] in {'ACTION_REQUIRED', 'POSSIBLE_ACTION'}]
    if intent == 'job_deadline':
        return [item for item in active if item['deadline'] and item['deadline_source']]
    if intent == 'interview':
        return [item for item in active if item['evidence'] and interview_request(item['evidence'])]
    if intent == 'verification':
        return [item for item in active if item['evidence'] and email_verification_requested(item['evidence'])]
    if intent == 'respond':
        return [item for item in active if item['evidence'] and response_request(item['evidence'])]
    return [item for item in active if item['status'] == 'ACTION_REQUIRED' and item['evidence'] and item['action']]


def email_summary(data):
    errors = data.get('errors') or []
    messages = data.get('messages') or []
    if not messages and errors:
        return next(iter(dict.fromkeys(error['message'] for error in errors)))
    relation = data.get('relation')
    intent = data.get('workflow_intent') or ''
    period = {'today': 'Today', 'yesterday': 'Yesterday', 'this_week': 'This week',
              'last_week': 'Last week', 'this_month': 'This month'}.get(data.get('temporal_source'))

    def line(message, dated=False):
        sender = message['sender_name'] or message['sender_email']
        value = f'{sender} \u2014 "{private_subject(message["subject"])}"'
        if dated:
            moment = datetime.fromisoformat(message['received_at']).astimezone(ZoneInfo(data.get('timezone') or 'America/New_York'))
            value += ' \u2014 ' + moment.strftime('%b %d').replace(' 0', ' ')
        return value

    if data.get('query_type') == 'workflow':
        found = workflow_matches(data.get('action_items', []), intent)
        if intent == 'job_deadline':
            lines = []
            for item in found[:5]:
                date = datetime.fromisoformat(item['deadline']).strftime('%b %d').replace(' 0', ' ')
                description = 'Assessment' if item['action'] == 'Complete the assessment' else item['action'] or 'Application task'
                lines.append(f"\u2022 {item['company']} \u2014 {description} due {date}")
            answer = '\n'.join(lines) if lines else "I didn't find any explicit application deadlines in the recent recruiting emails I checked."
        elif intent == 'interview':
            answer = ('Yes.\n\n' + '\n'.join(f"{item['company']} \u2014 \"{private_subject(item['subject'])}\"" for item in found[:5])) if found else "I didn't find any recent recruiting emails asking you to schedule an interview."
        elif intent == 'verification':
            answer = ('Yes.\n\n' + '\n'.join(f"{item['company']} \u2014 \"{private_subject(item['subject'])}\"" for item in found[:5])) if found else "I didn't find any recent emails asking you to verify your email address."
        elif intent == 'respond':
            answer = ('Yes.\n\n' + '\n'.join(f"\u2022 {item['company']} \u2014 {item['action']}" for item in found[:5])) if found else "I didn't find any recent recruiting emails explicitly asking for a reply."
        else:
            answer = ('\n'.join(f"\u2022 {item['company']} \u2014 {item['action']}" +
                                (f"; due {item['deadline']}" if item['deadline'] else '') for item in found[:5])
                      if found else "I didn't find any clearly actionable application emails.")
        if not found and errors: return next(iter(dict.fromkeys(error['message'] for error in errors)))
    elif not messages:
        if relation == 'from':
            entity = (data.get('entities') or ['that sender'])[0]
            answer = f"I couldn't find any recent emails directly from {entity}."
        else: answer = 'No matching emails found' + (f' {period.lower()}.' if period else '.')
    elif data.get('view') == 'organizations':
        answer = (period + ':\n\n' if period else '') + '\n'.join('\u2022 ' + name for name in data.get('organizations', []))
    elif data.get('read'):
        answer = line(messages[0], dated=True)
        text = messages[0].get('body_text')
        if text:
            if data.get('instruction_content') or contains_instruction_text(text):
                answer += '\nThe message includes instructions aimed at an assistant; these are untrusted email content.'
            answer += '\n\nEmail excerpt:\n' + '\n'.join('> ' + part for part in private_excerpt(text).splitlines())
        else: answer += '\nThe message body was unavailable.'
    elif data.get('latest'):
        answer = line(messages[0], dated=True)
    elif data.get('numbered'):
        answer = '\n'.join(f'{index}. {line(message)}' for index, message in enumerate(messages, 1))
    else:
        heading = ('Yes.\n\n' if relation == 'from' else
                   'A few that stand out:\n\n' if data.get('view') == 'important' else
                   period + ':\n\n' if period else '')
        answer = heading + '\n'.join(('\u2022 ' if len(messages) > 1 and relation != 'from' else '') +
                                    line(message, dated=relation == 'about') for message in messages)
    # A normal top-N cap is not a failed search. Surface real failures once.
    if errors: answer += '\nSome accounts could not be checked.'
    elif data.get('partial'): answer += '\nSome requested email details could not be checked.'
    return answer
