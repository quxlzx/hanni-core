"""Resolve simple calendar reads and their source from bounded owner context."""
from datetime import date, datetime, timedelta, timezone
import re
from zoneinfo import ZoneInfo
from hanni.tools.base import ToolRequest
from hanni.tools.time_routing import normalize_question
from hanni.tools.whenparse import WhenParseError, parse_when


def calendar_read_request(prompt, history=(), *, today=None, now=None, timezone_name=None):
    """Resolve calendar read context. No Google access and no tool execution."""
    if re.search(r'[;\n]', prompt):
        return None
    clean = normalize_question(prompt)
    if re.match(r"^(?:add|put|create|schedule|book|move|delete|remove|cancel)\b", clean):
        return None
    if re.search(r'\b(?:files?|documents?|pdfs?|grep|log|errors?|handler|listener)\b', clean):
        return None
    if re.search(r"\band\b", clean) and not clean.startswith('and '):
        return None
    from hanni.tools.calendar_search import academic_search_plan
    academic = academic_search_plan(prompt, history, now=now if now is not None else today,
                                    timezone_name=timezone_name)
    if academic is not None:
        return academic.request()
    reference = today or datetime.now(ZoneInfo('America/New_York')).date()
    owners = [m['content'].casefold() for m in history if m.get('role') == 'user']
    contextual = bool(owners and re.search(r'\b(?:calendar|agenda|schedule)\b', owners[-1]))
    explicit = bool(re.search(r'\b(?:calendar|calendars|agenda|schedules?|scheduled|timetable|diary|commitments|meetings?|events?|appointments?|class(?:es)?)\b', clean))
    implicit = bool(re.search(r"\b(?:what (?:do|did) i have|what do i got|what am i doing|what i got|do i got stuff|do i have anything|am i free|am i busy|how busy am i|anything|what about|got plans|what(?:'s| is) on)\b", clean)
                    or re.match(r"^(?:free|busy)\s+(?:today|tomorrow|tonight|this|next|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", clean))
    next_event = bool(re.search(r"\bnext (?:calendar )?(?:event|meeting|appointment|class|thing)\b|^what(?:'s| is) next$|\b(?:coming up|starting soon|what do i have next|event is next|before what(?:'s| is) next)\b", clean))
    if re.search(r"\b(?:after class|class tomorrow)\b", clean):
        implicit = True
    if not (explicit or implicit or contextual or next_event):
        return None
    account = None
    for utterance in owners + [clean]:
        if utterance == clean or re.search(r'\b(?:calendar|agenda|schedule)\b', utterance):
            if re.search(r'\b(?:both|all)\b', utterance): account = 'all'
            else:
                from hanni.tools.google_routing import requested_account
                account = requested_account(utterance) or account
    arguments = {'account': account} if account else {}
    if re.search(r'\b(?:calendars|calendar ids)\b', clean) and not re.search(r'\b(?:today|tomorrow|yesterday)\b', clean):
        return ToolRequest('google_calendar.list', arguments, source='calendar-read')
    if next_event:
        return ToolRequest('google_calendar.next', arguments, source='calendar-read')
    # Reject invalid, conflicting and ambiguous numeric dates instead of letting
    # the model guess. Reading after a clock time uses the whole day's evidence.
    iso = list(re.finditer(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', clean))
    relative = re.findall(r'\b(today|tomorrow|yesterday)\b', clean)
    if len(iso) > 1 or len(set(relative)) > 1 or (iso and relative) or re.search(r'\b\d{1,2}/\d{1,2}\b', clean):
        return None
    days = 1
    if iso:
        if re.search(r'\bat\s+\d', clean):
            return None
        try:
            day = date(*(int(v) for v in iso[0].groups()))
        except ValueError:
            return None
    elif re.search(r'\b(?:this|next) weekend\b', clean):
        day = reference + timedelta(days=(5-reference.weekday()) % 7)
        if reference.weekday() == 6 and 'this weekend' in clean:
            day = reference - timedelta(days=1)
        if 'next weekend' in clean:
            day += timedelta(days=7)
        days = 2
    elif re.search(r'\b(?:this|next) week\b', clean):
        day = reference - timedelta(days=reference.weekday())
        if 'next week' in clean: day += timedelta(days=7)
        days = 7
    else:
        from hanni.tools.whenparse import _match_date
        try:
            hit = _match_date(clean.replace('the next day', 'tomorrow') if contextual else clean, reference)
        except WhenParseError:
            return None
        if hit:
            day = hit[0]
        elif explicit or re.search(r'\b(?:am i free after|after class|what do i have after (?:breakfast|lunch|dinner))\b', clean):
            day = reference
        else:
            return None
    arguments.update(start_date=day.isoformat(), days=days)
    # Only an owner-specified event phrase may become Google's text filter.
    # Resolve even that phrase here, so a model cannot turn "Sunday" into
    # q=Sunday and hide events from a plain date read.
    search = (re.search(r'\b(?:search|look for)\s+(?:my\s+)?(?:google\s+)?(?:calendar|events?|meetings?|appointments?)\s+for\s+(.+)', clean)
              or re.search(r'\bfind\s+(?:my\s+)?(?:calendar\s+)?(?:event|meeting|appointment)\s+(?:named|called|about|with)\s+(.+)', clean)
              or re.search(r'\bdo i have anything with\s+(.+)', clean)
              or re.search(r'\bwhen is (?:my |the )?(.+?\b(?:appointment|meeting|event|class))\b', clean))
    event_query = search.group(1).strip(' ?.') if search else ''
    if event_query:
        date_suffix = r'(?:today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{4}-\d{1,2}-\d{1,2})'
        event_query = re.sub(rf'\s+(?:(?:on|for)\s+)?{date_suffix}$', '', event_query).strip()
        if re.fullmatch(date_suffix, event_query):
            event_query = ''
    arguments['query'] = event_query
    interval = re.search(r'\b(?:from|between)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s+(?:to|and|until)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b', clean)
    if interval and days == 1 and re.search(r'\b(?:free|busy|available|open)\b', clean):
        from hanni.tools.whenparse import _match_time
        first = _match_time(interval.group(1))[0]
        last = _match_time(interval.group(2))[0]
        if first >= last:
            return None
        arguments['availability_start'] = first.strftime('%H:%M')
        arguments['availability_end'] = last.strftime('%H:%M')
    point = re.search(r'\b(?:at|around)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b', clean)
    if point and not interval and re.search(r'\b(?:free|busy|available|open|anything|something)\b', clean):
        hour = int(point.group(1))
        minute = int(point.group(2) or 0)
        meridiem = point.group(3)
        if minute > 59 or hour > (12 if meridiem else 23):
            return None
        if meridiem:
            hour = hour % 12 + (12 if meridiem == 'pm' else 0)
        elif re.search(r'\b(?:tonight|this evening)\b', clean):
            if 5 <= hour <= 11:
                hour += 12
            else:
                return None
        elif hour <= 7:
            # A bare early hour has two plausible readings.
            return None
        arguments['availability_at'] = f'{hour:02d}:{minute:02d}'
    return ToolRequest('google_calendar.agenda', arguments, source='calendar-read')


def calendar_write_needs_time(prompt: str) -> bool:
    """A daypart is not an exact event start; ask the owner for a clock time."""
    clean = normalize_question(prompt)
    return bool(re.match(r'^(?:add|put|create|schedule|book)\b', clean)
                and re.search(r'\b(?:morning|afternoon|evening|tonight)\b', clean)
                and not re.search(r'\b(?:at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2}|noon|midnight)\b', clean))


def google_write_request(prompt):
    """Recognize a calendar mutation, never reinterpret it as a local write."""
    clean = normalize_question(prompt)
    return bool(re.match(r'^(?:put|add|create|schedule|book|move|delete|remove|cancel)\b', clean)
                and re.search(r'\b(?:calendars?|meetings?|events?(?!\s+(?:log|handler|listener|hook)\b))\b', clean)
)


_CREATE_VERB = re.compile(r"^(?:please\s+)?(?:add|create|schedule|book|put|make)\b", re.I)
# Activity-domain nouns establish scheduling intent, while a date alone cannot.
# These categories describe ordinary appointments, recreation and learning;
# they are not complete utterance matches or an executable-action allowlist.
_SCHEDULED_ACTIVITY = re.compile(
    r"\b(?:calendar|appointments?|meetings?|events?|sessions?|blocks?|"
    r"doctor|dentist|physician|optometrist|therapist|counsell?or|consultations?|"
    r"checkups?|physiotherapy|therapy|treatment|vaccination|"
    r"dinner|supper|lunch|breakfast|brunch|picnic|party|celebration|meetup|"
    r"game|tournament|concert|movie|rehearsal|practice|outing|hike|"
    r"class(?:es)?|lecture|seminar|tutor(?:ing|ials?)?|tuition|teach(?:ing)?|"
    r"lesson|lab|laboratory|workshop|exam|"
    r"(?:office|consultation|study)\s+hours)\b", re.I)
_RELATIVE_DAY = r"(?:today|tomorrow|tonight|day\s+after\s+tomorrow)"
_WEEKDAY = r"(?:(?:next|this|coming)\s+)?(?:monday|mon|tuesday|tue|tues|wednesday|wed|thursday|thu|thur|thurs|friday|fri|saturday|sat|sunday|sun)"
_TEMPORAL_START = re.compile(
    rf"\b(?:{_RELATIVE_DAY}|{_WEEKDAY}|\d{{4}}-\d{{2}}-\d{{2}}|(?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sept|sep|october|oct|november|nov|december|dec)\s+\d{{1,2}}(?:st|nd|rd|th)?|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sept|sep|october|oct|november|nov|december|dec)|in\s+\d+\s+(?:minutes?|mins?|hours?|hrs?|days?|weeks?)|at\s+\d{{1,2}}(?::\d{{2}})?\s*(?:am|pm)?|noon|midnight)\b",
    re.I,
)


def _calendar_account(text: str) -> str | None:
    from hanni.tools.google_routing import requested_account
    return requested_account(text)


def _event_summary(prompt: str) -> str:
    raw = " ".join(str(prompt or "").split()).strip(" .?!")
    raw = re.sub(r"\b(?:tmr|tmrw)\b", "tomorrow", raw, flags=re.I)
    quoted = re.search(r"[\"']([^\"']{1,300})[\"']", raw)
    if quoted:
        return quoted.group(1).strip()
    body = _CREATE_VERB.sub("", raw, count=1).strip()
    body = re.sub(r"^(?:an?\s+)?(?:calendar\s+)?(?:event|meeting|appointment)\s+(?:called|named)\s+", "", body, flags=re.I)
    body = re.sub(r"^(?:an?\s+)?(?:calendar\s+)?(?:event|meeting|appointment)\s+for\s+", "", body, flags=re.I)
    body = re.sub(r"^(?:an?\s+)", "", body, flags=re.I)
    body = re.sub(r"^(?:(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*[- ]\s*(?:hours?|hrs?|minutes?|mins?)\s+)", "", body, flags=re.I)
    marker = _TEMPORAL_START.search(body)
    if marker:
        body = body[:marker.start()]
    body = re.sub(r"\b(?:to|on|in)\s+(?:my\s+)?(?:(?:personal|school)\s+)?(?:google\s+)?calendar\b", "", body, flags=re.I)
    body = re.sub(r"\b(?:on|to)\s+the\s+calendar\b", "", body, flags=re.I)
    body = re.sub(r"\s+(?:for|on|at|to|in)$", "", body.strip(), flags=re.I)
    body = re.sub(r"\s+", " ", body).strip(" ,:-")
    return body[:300]


def _owner_wall_time(moment: datetime, zone: ZoneInfo) -> datetime:
    """Attach the owner zone, refusing nonexistent or ambiguous DST wall times."""
    candidates = []
    for fold in (0, 1):
        aware = moment.replace(tzinfo=zone, fold=fold)
        returned = aware.astimezone(timezone.utc).astimezone(zone)
        if returned.replace(tzinfo=None) == moment:
            candidates.append(aware)
    if not candidates:
        raise WhenParseError("that local time does not exist in the configured timezone")
    if len(candidates) == 2 and candidates[0].utcoffset() != candidates[1].utcoffset():
        raise WhenParseError("that local time is ambiguous at the daylight-saving transition")
    return candidates[0]


def calendar_create_request(prompt, *, now=None, timezone_name=None):
    """Resolve a clear natural-language Google Calendar creation request.

    The model never decides relative dates.  This parser converts the owner's
    wording to exact local start/end values before the tool is exposed.  Ambiguous
    requests return None so the conversational model can ask for clarification.
    """
    if re.search(r"[;\n]", str(prompt or "")):
        return None
    clean = normalize_question(prompt)
    # A time inside data to store is not permission to write to a provider.
    # Resolve destination/object intent before parsing dates. Quoted payloads
    # and a note's colon-separated body cannot grant calendar authority.
    intent = re.split(r'(?<!\d):|:(?!\d)', re.sub(r'"[^\"]*"|\'[^\']*\'', '', clean), maxsplit=1)[0]
    destination = re.search(
        r'\b(?:to|on|in|into)\s+(?:(?:my|the|a|an|personal|school|google)\s+)*calendar\b', intent)
    storage_destination = re.search(
        r'\b(?:local|offline)\b|\b(?:notes?|tasks?|todos?|checklists?|files?|folders?|documents?|records?|lists?)\b', intent)
    if storage_destination and not destination:
        return None
    calendar_object = bool(_SCHEDULED_ACTIVITY.search(intent))
    strong = bool(
        re.match(r"^(?:add|put|create|make)\b", intent) and (destination or calendar_object)
        or re.match(r"^(?:schedule|book)\b", intent)
    )
    if not strong:
        return None
    if calendar_write_needs_time(prompt):
        return None
    try:
        zone = ZoneInfo(timezone_name) if timezone_name else None
        reference = now
        if reference is None:
            reference = datetime.now(zone).replace(tzinfo=None) if zone else datetime.now().astimezone().replace(tzinfo=None)
        elif getattr(reference, "tzinfo", None) is not None:
            reference = reference.astimezone(zone).replace(tzinfo=None) if zone else reference.astimezone().replace(tzinfo=None)
        parsed = parse_when(clean, now=reference)
        if (re.search(r"\b(?:dinner|supper)\b", clean)
                and re.search(r"\bat\s+\d{1,2}\b(?!\s*(?:am|pm))", clean)
                and parsed.start.hour < 12):
            parsed = type(parsed)(parsed.start + timedelta(hours=12), parsed.all_day,
                                  parsed.duration_minutes, parsed.matched)
    except WhenParseError:
        return None
    summary = _event_summary(prompt)
    if not summary:
        return None
    args = {"summary": summary, "all_day": parsed.all_day}
    account = _calendar_account(clean)
    if account:
        args["account"] = account
    if parsed.all_day:
        args["start_date"] = parsed.start.date().isoformat()
        args["end_date"] = parsed.end.date().isoformat()
    else:
        try:
            args["start"] = (_owner_wall_time(parsed.start, zone) if zone else parsed.start.astimezone()).isoformat()
            args["end"] = (_owner_wall_time(parsed.end, zone) if zone else parsed.end.astimezone()).isoformat()
        except WhenParseError:
            return None
    return ToolRequest("google_calendar.create", args, source="calendar-create")
