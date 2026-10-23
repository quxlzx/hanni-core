"""Bounded academic Calendar plans and local event matching.

The planner fixes time, subject, course and account before any model tool call.
Google event text remains data: no synonym is sent as Google's ``q`` filter.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from hanni.tools.base import ToolRequest
from hanni.tools.time_routing import normalize_question


log = logging.getLogger('hanni.calendar.search')
_MONTHS = {name: number for number, name in enumerate(
    ('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
     'september', 'october', 'november', 'december'), 1)}
_MONTHS.update({name[:3]: number for name, number in list(_MONTHS.items())})
_MONTHS['sept'] = 9
_MONTH_PATTERN = '|'.join(sorted(_MONTHS, key=len, reverse=True))
_SUBJECT = re.compile(r'\bmid[ -]?terms?\b|\bexams?\b|\btests?\b|\bquizzes?\b', re.I)
_COURSE = re.compile(r'\b([a-z]{2,6})\s*-?\s*(\d{3,4}[a-z]?)\b', re.I)
_SOURCE_ONLY = re.compile(
    r"(?:(?:it's|its|it is|they're|they are|look|search|check|actually)\s+)?"
    r"(?:on\s+)?(?:my\s+)?(personal|school)\s+(?:google\s+)?calendar", re.I)
_UNRELATED = re.compile(
    r'\b(?:review|practice|mock|prep|preparation|study session|lecture|office hours?|'
    r'homework|assignment|birthday|concert|party|social|tickets?)\b', re.I)


@dataclass(frozen=True, slots=True)
class CalendarSearchPlan:
    concept: str
    start: datetime
    end: datetime
    temporal_source: str
    account: str | None = None
    course: str | None = None
    first_only: bool = False
    followup_context_used: bool = False

    def request(self) -> ToolRequest:
        arguments = {'time_min': self.start.isoformat(), 'time_max': self.end.isoformat(),
                     'academic_concept': self.concept, 'course': self.course or '',
                     'first_only': self.first_only, 'temporal_source': self.temporal_source,
                     'followup_context_used': self.followup_context_used, 'query': '', 'limit': 10}
        if self.account:
            arguments['account'] = self.account
        log.debug('[calendar-plan] account=%s temporal_source=%s start=%s end=%s concept=%s course=%s followup=%s',
                  self.account or 'connected', self.temporal_source, self.start.isoformat(),
                  self.end.isoformat(), self.concept, self.course or '', self.followup_context_used)
        return ToolRequest('google_calendar.agenda', arguments, source='academic-calendar-search')


def _local_now(now: datetime | date | None, zone: ZoneInfo) -> datetime:
    if now is None:
        return datetime.now(zone)
    if isinstance(now, date) and not isinstance(now, datetime):
        return datetime.combine(now, time.min, zone)
    return now.replace(tzinfo=zone) if now.tzinfo is None else now.astimezone(zone)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _window(clean: str, now: datetime, zone: ZoneInfo) -> tuple[datetime, datetime, str] | None:
    today = now.date()
    iso = re.search(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', clean)
    if iso:
        try:
            day = date(*(int(part) for part in iso.groups()))
        except ValueError:
            return None
        start = datetime.combine(day, time.min, zone)
        return start, datetime.combine(day + timedelta(days=1), time.min, zone), 'explicit_date'
    if re.search(r'\btoday\b', clean):
        start = datetime.combine(today, time.min, zone)
        return start, datetime.combine(today + timedelta(days=1), time.min, zone), 'today'
    if re.search(r'\btomorrow\b', clean):
        day = today + timedelta(days=1)
        start = datetime.combine(day, time.min, zone)
        return start, datetime.combine(day + timedelta(days=1), time.min, zone), 'tomorrow'
    if re.search(r'\bnext week\b', clean):
        monday = today + timedelta(days=7 - today.weekday())
        start = datetime.combine(monday, time.min, zone)
        return start, datetime.combine(monday + timedelta(days=7), time.min, zone), 'next_week'
    if re.search(r'\bthis week\b', clean):
        monday = today - timedelta(days=today.weekday())
        start = datetime.combine(monday, time.min, zone)
        return start, datetime.combine(monday + timedelta(days=7), time.min, zone), 'this_week'
    if re.search(rf'\b(?:{_MONTH_PATTERN})\s+\d{{1,2}}\b|\b\d{{1,2}}\s+(?:{_MONTH_PATTERN})\b|'
                 r'\b(?:this|next)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', clean):
        from hanni.tools.whenparse import WhenParseError, _match_date
        try:
            named = _match_date(clean, today)
        except WhenParseError:
            return None
        if named:
            day = named[0]
            explicit_year = re.search(rf'\b(?:{_MONTH_PATTERN})\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+(20\d{{2}})\b|'
                                      rf'\b\d{{1,2}}\s+(?:{_MONTH_PATTERN})\s+(20\d{{2}})\b', clean)
            if explicit_year:
                try:
                    day = day.replace(year=int(explicit_year.group(1) or explicit_year.group(2)))
                except ValueError:
                    return None
            start = datetime.combine(day, time.min, zone)
            return start, datetime.combine(day + timedelta(days=1), time.min, zone), 'explicit_date'
    month_hit = re.search(rf'\b({_MONTH_PATTERN})(?:\s+(20\d{{2}}))?\b', clean)
    if (month_hit and month_hit.group(1) == 'may' and not month_hit.group(2)
            and not re.search(r'\b(?:in|for|during|this|next)\s+may\b', clean)):
        month_hit = None
    if month_hit or re.search(r'\b(?:this|next) month\b', clean):
        if month_hit:
            month = _MONTHS[month_hit.group(1)]
            year = int(month_hit.group(2)) if month_hit.group(2) else today.year
            if not month_hit.group(2) and month < today.month:
                year += 1
            source = 'explicit_month'
        else:
            year, month = today.year, today.month
            if 'next month' in clean:
                year, month = _next_month(year, month)
            source = 'next_month' if 'next month' in clean else 'this_month'
        end_year, end_month = _next_month(year, month)
        start = datetime(year, month, 1, tzinfo=zone)
        return start, datetime(end_year, end_month, 1, tzinfo=zone), source
    return now, now + timedelta(days=180), 'future_180_days'


def _course_filter(prompt: str, clean: str) -> str | None:
    for full in _COURSE.finditer(prompt):
        if full.group(1).casefold() not in {'my', 'the', 'for', 'next', 'first', 'exam',
                                            'test', 'school', 'what', 'when'}:
            return (full.group(1) + full.group(2)).upper()
    for match in re.finditer(r'\b(\d{3,4})\b', clean):
        number = int(match.group(1))
        if not 1900 <= number <= 2100:
            return match.group(1)
    return None


def academic_search_plan(prompt: str, history=(), *, now: datetime | date | None = None,
                         timezone_name: str | None = None) -> CalendarSearchPlan | None:
    """Resolve an exam question or a source-only follow-up to structured slots."""
    if re.search(r'[;\n]', prompt):
        return None
    clean = normalize_question(prompt)
    zone = ZoneInfo(timezone_name or 'America/New_York')
    local_now = _local_now(now, zone)
    source = _SOURCE_ONLY.fullmatch(clean)
    if source:
        previous = next((str(row.get('content') or '') for row in reversed(history)
                         if row.get('role') == 'user'), '')
        prior = academic_search_plan(previous, now=local_now, timezone_name=timezone_name) if previous else None
        return replace(prior, account=source.group(1).casefold(), followup_context_used=True) if prior else None
    if re.match(r'^(?:add|put|create|schedule|book|move|delete|remove|cancel)\b', clean):
        return None
    subject = _SUBJECT.search(clean)
    if not subject:
        return None
    concept = ('midterm' if re.search(r'mid[ -]?term', subject.group(), re.I) else
               'exam' if subject.group().startswith('exam') else
               'quiz' if subject.group().startswith('quiz') else 'test')
    if concept == 'test' and not re.search(r'\b(?:calendar|school|course|class|when|have|upcoming|next|week|month|today|tomorrow)\b', clean):
        return None
    window = _window(clean, local_now, zone)
    if window is None:
        return None
    start, end, temporal_source = window
    future = bool(re.search(r'\b(?:first|next|upcoming|coming up)\b', clean))
    if future and temporal_source in {'this_week', 'this_month', 'explicit_month'} and start < local_now < end:
        start = local_now
    first_only = bool(re.search(r'\bfirst\b', clean) or
                      re.search(r'\bnext\b', clean) and not re.search(r'\b(?:mid[ -]?terms|exams|tests|quizzes)\b', clean))
    account_hit = re.search(r'\b(personal|school)\s+(?:google\s+)?calendar\b', clean)
    return CalendarSearchPlan(concept, start, end, temporal_source,
                              account_hit.group(1) if account_hit else None,
                              _course_filter(prompt, clean), first_only)


def rank_academic_events(events: list[dict], concept: str, course: str = '') -> tuple[list[dict], dict]:
    """Match title semantics after the bounded fetch; chronology remains primary."""
    candidates: list[dict] = []
    exam_candidates = 0
    for event in events:
        title = str(event.get('summary') or '')
        lower = title.casefold()
        if _UNRELATED.search(lower):
            continue
        midterm = bool(re.search(r'\bmid[ -]?terms?\b', lower))
        exam = bool(re.search(r'\b(?:exams?|examinations?)\b', lower))
        test = bool(re.search(r'\btests?\b', lower))
        quiz = bool(re.search(r'\bquizzes?\b', lower))
        if concept == 'quiz':
            if not quiz: continue
        elif concept == 'midterm':
            if not (midterm or (exam and 'final' not in lower) or test): continue
        elif not (midterm or exam or test):
            continue
        code_hit = _COURSE.search(title)
        code = (code_hit.group(1) + code_hit.group(2)).upper() if code_hit else ''
        if course and (code != course if not course.isdigit() else
                       not code_hit or code_hit.group(2).upper() != course):
            continue
        score = (100 if midterm else 80 if exam else 60 if test else 50)
        score += 10 if code else 0
        score += 8 if re.search(r'\b(?:exam|test)\s*(?:1|i)\b', lower) else 0
        if midterm or exam or test:
            exam_candidates += 1
        candidates.append({**event, 'academic_score': score, 'course_code': code,
                           'literal_midterm': midterm})
    candidates.sort(key=lambda event: (event.get('start_utc') or '', -event['academic_score']))
    codes = {event['course_code'] for event in candidates if event['course_code']}
    ambiguous_course = bool(course.isdigit() and len(codes) > 1)
    counts = {'events_fetched': len(events), 'academic_candidates': len(candidates),
              'exam_candidates': exam_candidates, 'ambiguous_course': ambiguous_course,
              'first_literal_midterm': next((event for event in candidates if event['literal_midterm']), None)}
    log.debug('[calendar-filter] events_fetched=%d academic_candidates=%d exam_candidates=%d selected_count=%d',
              len(events), len(candidates), exam_candidates, len(candidates))
    return candidates, counts


def academic_summary(data: dict) -> str:
    """Ground a concise answer in the matched events and requested scope."""
    events = data.get('events', [])
    concept = data.get('academic_concept') or 'exam'
    account = data.get('account') or 'connected'
    scope = f'your {account} calendar' if account != 'connected' else 'your connected calendars'
    start = datetime.fromisoformat(data['window_start'])
    end = datetime.fromisoformat(data['window_end'])
    source = data.get('temporal_source')
    period = (start.strftime('%B %Y') if source in {'explicit_month', 'this_month', 'next_month'} else
              'next week' if source == 'next_week' else
              'this week' if source == 'this_week' else
              start.strftime('%B %d').replace(' 0', ' ') if source in {'today', 'tomorrow', 'explicit_date'} else
              f'the next {max(1, (end.date() - start.date()).days)} days')
    incomplete = bool(data.get('errors') or data.get('truncated') or data.get('partial'))

    def describe(event: dict) -> str:
        moment = datetime.fromisoformat(event['start_local'])
        when = moment.strftime('%A, %B %d').replace(' 0', ' ')
        if not event.get('all_day'):
            when += ' at ' + moment.strftime('%I:%M %p').lstrip('0')
            end_value = (event.get('end') or {}).get('dateTime')
            if end_value:
                try:
                    finish = datetime.fromisoformat(end_value.replace('Z', '+00:00')).astimezone(moment.tzinfo)
                    if finish > moment:
                        when += '–' + finish.strftime('%I:%M %p').lstrip('0')
                except ValueError:
                    pass
        location = str(event.get('location') or '').strip()
        return f"{event.get('summary') or 'Untitled event'} on {when}" + (f' in {location}' if location else '')

    if not events:
        if incomplete:
            answer = f'I could not complete the search of {scope} for {period}; no matching {concept} event was verified.'
        else:
            labels = 'a quiz' if concept == 'quiz' else 'a midterm, exam, or test'
            answer = f"I checked {scope} for {period} and didn't find an event labeled as {labels}."
    elif data.get('ambiguous_course'):
        answer = (f"I found {concept} events for multiple courses ending in {data.get('course')}; "
                  'please specify the department. Matches: ' + '; '.join(describe(event) for event in events[:5]) + '.')
    elif data.get('first_only'):
        first = events[0]
        label = f'first {concept}' if first.get('literal_midterm') or concept != 'midterm' else 'first exam-like event'
        answer = f'Your {label} is {describe(first)}.'
        literal = data.get('first_literal_midterm')
        if concept == 'midterm' and literal and literal.get('id') != first.get('id'):
            answer += f' The first event explicitly labeled Midterm is {describe(literal)}.'
    else:
        answer = f'Your {period} {concept} events are: ' + '; '.join(describe(event) for event in events) + '.'
        if data.get('matched_count', 0) > len(events):
            answer += f" Showing the first {len(events)} of {data['matched_count']} matches."
    if incomplete:
        answer += ' This search is incomplete.'
    if data.get('errors'):
        answer += ' ' + ' '.join(f"{error.get('account')}: {error.get('error')}" for error in data['errors'])
    return answer
