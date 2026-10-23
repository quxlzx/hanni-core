"""Deterministic natural date/time parsing for calendar capabilities.

The owner says "dentist thursday at 3"; the model must not be the thing that
decides what date that is. This parser is a small, explicit grammar with no
model involvement and no third-party dependency, and it refuses anything it
cannot resolve rather than guessing.

Supported, deliberately: today / tomorrow / tonight, weekday names with an
optional "next" or "this", "in N minutes|hours|days", ISO dates and date-times,
"12 September" and "September 12", clock times ("3", "3pm", "3:30pm", "15:00",
"noon", "midnight"), and a trailing "for <duration>".

Not supported, deliberately: bare numeric dates such as 9/12, which mean
different days on different sides of the Atlantic. Those must be given as ISO.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

_WEEKDAYS = {"monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2,
             "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "friday": 4, "fri": 4,
             "saturday": 5, "sat": 5, "sunday": 6, "sun": 6}
_MONTHS = {name: index for index, name in enumerate(
    ("january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"), start=1)}
_MONTHS.update({name[:3]: index for name, index in list(_MONTHS.items())})
_MONTHS["sept"] = 9

_UNIT_MINUTES = {"minute": 1, "minutes": 1, "min": 1, "mins": 1, "m": 1,
                 "hour": 60, "hours": 60, "hr": 60, "hrs": 60, "h": 60,
                 "day": 1440, "days": 1440}
_MAX_DURATION_MINUTES = 24 * 60


class WhenParseError(ValueError):
    """Raised when a phrase cannot be resolved to a concrete date and time."""


@dataclass(frozen=True, slots=True)
class ParsedWhen:
    start: datetime
    all_day: bool
    duration_minutes: int
    matched: str

    @property
    def end(self) -> datetime:
        if self.all_day:
            return datetime.combine(self.start.date() + timedelta(days=1), time.min)
        return self.start + timedelta(minutes=self.duration_minutes)


def parse_duration_minutes(text: str) -> int:
    """Parse '90 minutes', '1h30', '2 hours' into whole minutes."""
    raw = " ".join(str(text or "").split()).casefold()
    words = {"one":"1", "two":"2", "three":"3", "four":"4", "five":"5", "six":"6",
             "seven":"7", "eight":"8", "nine":"9", "ten":"10", "eleven":"11", "twelve":"12"}
    raw = re.sub(r"^(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
                 lambda match: words[match.group(1)], raw)
    if not raw:
        raise WhenParseError("duration is required")
    compact = re.fullmatch(r"(\d{1,2})\s*h(?:ours?|rs?)?\s*(\d{1,2})?\s*(?:m(?:in(?:utes?)?)?)?", raw)
    if compact:
        minutes = int(compact.group(1)) * 60 + int(compact.group(2) or 0)
    else:
        match = re.fullmatch(r"(\d{1,4})\s*([a-z]+)", raw)
        if not match or match.group(2) not in _UNIT_MINUTES:
            raise WhenParseError("duration must look like '30 minutes', '1h30', or '2 hours'")
        minutes = int(match.group(1)) * _UNIT_MINUTES[match.group(2)]
    if not 1 <= minutes <= _MAX_DURATION_MINUTES:
        raise WhenParseError(f"duration must be between 1 minute and {_MAX_DURATION_MINUTES // 60} hours")
    return minutes


def _match_time(text: str) -> tuple[time, str] | None:
    if re.search(r"\bnoon\b|\bmidday\b", text):
        return time(12, 0), "noon"
    if re.search(r"\bmidnight\b", text):
        return time(0, 0), "midnight"
    match = re.search(r"\b(?:at\s+)?(\d{1,2})(?:(?::|\s+)(\d{2}))?\s*(am|pm)\b", text)
    if match:
        if not 1 <= int(match.group(1)) <= 12 or int(match.group(2) or 0) > 59:
            raise WhenParseError("invalid 12-hour clock time")
        hour = int(match.group(1)) % 12
        if match.group(3) == "pm":
            hour += 12
        return time(hour, int(match.group(2) or 0)), match.group(0).strip()
    match = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            raise WhenParseError(f"{match.group(0)} is not a valid time")
        return time(hour, minute), match.group(0)
    match = re.search(r"\bat\s+(\d{1,2})\b", text)
    if match:
        hour = int(match.group(1))
        if hour > 23:
            raise WhenParseError(f"{hour} is not a valid hour")
        if re.search(r"\b(?:tonight|evening)\b", text):
            if 5 <= hour <= 11:
                hour += 12
            elif hour < 13:
                raise WhenParseError("include am or pm for that evening time")
        # A bare "at 3" for an appointment means the afternoon far more often
        # than 3am; 8-11 stay in the morning where that reading is natural.
        elif 1 <= hour <= 7:
            hour += 12
        return time(hour, 0), match.group(0)
    return None


def _match_date(text: str, today: date) -> tuple[date, str] | None:
    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))), iso.group(0)
        except ValueError as exc:
            raise WhenParseError(f"{iso.group(0)} is not a real date") from exc
    if re.search(r"\btoday\b|\btonight\b|\bthis (?:evening|afternoon|morning)\b", text):
        return today, "today"
    if re.search(r"\bday after tomorrow\b", text):
        return today + timedelta(days=2), "day after tomorrow"
    if re.search(r"\btomorrow\b", text):
        return today + timedelta(days=1), "tomorrow"
    if re.search(r"\byesterday\b", text):
        return today - timedelta(days=1), "yesterday"

    relative = re.search(r"\bin\s+(\d{1,3})\s+(day|days|week|weeks)\b", text)
    if relative:
        step = int(relative.group(1)) * (7 if relative.group(2).startswith("week") else 1)
        return today + timedelta(days=step), relative.group(0)

    month_first = re.search(r"\b([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?\b", text)
    day_first = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3,9})\b", text)
    for match, month_group, day_group in ((month_first, 1, 2), (day_first, 2, 1)):
        if not match:
            continue
        month_name = match.group(month_group)
        if month_name not in _MONTHS:
            continue
        day_number = int(match.group(day_group))
        month = _MONTHS[month_name]
        year = today.year
        try:
            candidate = date(year, month, day_number)
        except ValueError as exc:
            raise WhenParseError(f"{match.group(0)} is not a real date") from exc
        if candidate < today:
            candidate = date(year + 1, month, day_number)
        return candidate, match.group(0)

    weekday = re.search(r"\b(next|this|last|coming)?\s*(" + "|".join(sorted(_WEEKDAYS, key=len, reverse=True)) + r")\b",
                        text)
    if weekday:
        target = _WEEKDAYS[weekday.group(2)]
        qualifier = weekday.group(1)
        if qualifier in {'this', 'last'}:
            week_start = today - timedelta(days=today.weekday())
            selected = week_start + timedelta(days=target - (7 if qualifier == 'last' else 0))
            return selected, weekday.group(0).strip()
        ahead = (target - today.weekday()) % 7
        if qualifier == "next":
            ahead = ahead + 7 if ahead else 7
        return today + timedelta(days=ahead), weekday.group(0).strip()
    return None


def parse_when(phrase: str, *, now: datetime | None = None, default_minutes: int = 60) -> ParsedWhen:
    """Resolve an owner phrase to a concrete start, all-day flag, and duration."""
    text = " ".join(str(phrase or "").split()).casefold()
    if not text:
        raise WhenParseError("a date or time phrase is required")
    if len(text) > 160:
        raise WhenParseError("date phrase is limited to 160 characters")
    if re.search(r"\b\d{1,2}/\d{1,2}\b", text):
        raise WhenParseError("ambiguous numeric date; use YYYY-MM-DD")
    reference = now or datetime.now()

    duration = default_minutes
    duration_match = re.search(r"\bfor\s+((?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[\dhms:\s]*[a-z]*)\b", text)
    if duration_match:
        duration = parse_duration_minutes(duration_match.group(1))
        text = text.replace(duration_match.group(0), " ")
    else:
        adjective = re.search(
            r"\b(?:a\s+)?(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*[- ]\s*(hours?|hrs?|minutes?|mins?)\b",
            text,
        )
        if adjective:
            duration = parse_duration_minutes(f"{adjective.group(1)} {adjective.group(2)}")
            text = text.replace(adjective.group(0), " ", 1)

    # Exact ISO inputs carry an owner-reviewed date and optional UTC offset.
    # Parse them before the natural-language clock matcher, which otherwise
    # sees only the clock following T and can select tomorrow instead.
    iso_text = text.strip()
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}(?:$|[t\s+\-]|z)", iso_text):
        iso_date = re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso_text)
        iso_datetime = re.fullmatch(
            r"\d{4}-\d{2}-\d{2}[t ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?"
            r"(?:z|[+-]\d{2}:\d{2})?", iso_text)
        try:
            if iso_date:
                start = datetime.combine(date.fromisoformat(iso_text), time.min)
                return ParsedWhen(start, True, 0, iso_text)
            if iso_datetime:
                offset = re.search(r"([+-])(\d{2}):(\d{2})$", iso_text)
                if offset and (int(offset.group(2)) > 23 or int(offset.group(3)) > 59):
                    raise ValueError('invalid UTC offset')
                start = datetime.fromisoformat(iso_text.replace('t', 'T').replace('z', '+00:00'))
                return ParsedWhen(start, False, duration, iso_text)
        except ValueError as exc:
            raise WhenParseError('invalid ISO date or date-time') from exc
        # Preserve existing natural date phrasing such as YYYY-MM-DD at 3pm,
        # but never reinterpret malformed ISO date-times or offset tails.
        if (re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", iso_text)
                or re.match(r"^\d{4}-\d{1,2}-\d{1,2}[t+\-z]", iso_text)
                or re.match(r"^\d{4}-\d{1,2}-\d{1,2}\s+\d", iso_text)):
            raise WhenParseError('invalid ISO date-time; use an exact date, time, and optional UTC offset')

    minutes_ahead = re.search(r"\bin\s+(\d{1,4})\s*(minute|minutes|min|mins|hour|hours|hr|hrs)\b", text)
    if minutes_ahead:
        step = int(minutes_ahead.group(1)) * _UNIT_MINUTES[minutes_ahead.group(2)]
        if step > 60 * 24 * 30:
            raise WhenParseError("relative times are limited to 30 days ahead")
        start = (reference + timedelta(minutes=step)).replace(second=0, microsecond=0)
        return ParsedWhen(start, False, duration, minutes_ahead.group(0))

    date_hit = _match_date(text, reference.date())
    time_hit = _match_time(text)
    # A compact owner phrasing such as "tomorrow 3 to 5" is a timed event,
    # not an all-day event. Resolve only unambiguous same-half-day ranges.
    bare_range = re.search(r"\b(\d{1,2})\s+to\s+(\d{1,2})\b", text)
    if date_hit is not None and time_hit is None and bare_range:
        first, last = int(bare_range.group(1)), int(bare_range.group(2))
        if 1 <= first < last <= 7:
            first += 12
            last += 12
        elif not 8 <= first < last <= 11:
            raise WhenParseError("ambiguous time range; include am or pm")
        day, day_label = date_hit
        return ParsedWhen(datetime.combine(day, time(first)), False,
                          (last - first) * 60, f"{day_label} {bare_range.group(0)}")
    if date_hit is None and time_hit is None:
        raise WhenParseError(
            "could not resolve a date or time; try 'tomorrow at 3pm', 'thursday 15:00', "
            "or an ISO date such as 2026-09-12 14:30")

    if date_hit is None:
        clock, label = time_hit
        day = reference.date()
        candidate = datetime.combine(day, clock)
        if candidate <= reference:
            day = day + timedelta(days=1)
            candidate = datetime.combine(day, clock)
        return ParsedWhen(candidate, False, duration, f"{label} (next occurrence)")

    day, day_label = date_hit
    if time_hit is None:
        return ParsedWhen(datetime.combine(day, time.min), True, 0, day_label)
    clock, time_label = time_hit
    return ParsedWhen(datetime.combine(day, clock), False, duration, f"{day_label} {time_label}")
