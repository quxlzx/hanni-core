"""Recognize bounded clock/date questions without model-supplied timezones."""
import re
from hanni.tools.base import ToolRequest


def normalize_question(prompt):
    clean = re.sub(r"\s+", " ", prompt.casefold().replace("\u2019", "'")).strip(" .?!")
    clean = re.sub(r"^(?:(?:hey|hi|hello)[, ]+)?(?:hanni|honey|hani)[, ]+", "", clean)
    clean = re.sub(r"^(?:please |(?:can|could|would) you )", "", clean)
    clean = re.sub(r"^whats\b", "what's", clean)
    clean = re.sub(r"\b(?:tmr|tmrw)\b", "tomorrow", clean)
    return re.sub(r",? please$", "", clean).strip()


def time_read_request(prompt):
    clean = normalize_question(prompt)
    clean = re.sub(r'^which day\b', 'what day', clean)
    clean = re.sub(r'^tell me (?:the )?date$', "what's the date", clean)
    clean = re.sub(r"^(today|tomorrow|yesterday)'s date$", r"what's \1's date", clean)
    clean = clean.replace('current local time', 'local time')
    clean = clean.replace('clock time', 'local time')
    match = re.fullmatch(
        r"(?:what(?:'s| is) (?:the )?(?:current |local )?time(?: is it)?|"
        r"what time is it|tell me (?:the )?(?:current |local )?time|"
        r"(?:the )?(?:current |local )?time)(?: (?:right )?now)?"
        r"(?: (?:in|for) (?P<zone>eastern|central|mountain|pacific|utc|gmt)(?: time(?: zone)?)?)?", clean)
    if match:
        zone = match.group('zone')
        return ToolRequest('time.now', {'kind': 'time', **({'timezone': zone} if zone else {})}, source='clock-read')
    if re.fullmatch(r"(?:what(?:'s| is)|tell me) (?:the )?(?:current )?date and time", clean):
        return ToolRequest('time.now', {}, source='clock-read')
    if clean in {'what day is it', 'what date is it'}:
        return ToolRequest('time.now', {'kind': 'date', 'day_offset': 0}, source='clock-read')
    match = re.fullmatch(
        r"(?:what(?:'s| is| was) (?:the )?(?:(?P<before>today|tomorrow|yesterday)'s )?(?:date|day)(?: of the week)?"
        r"(?: (?:is it|is|for))?(?: (?P<after>today|tomorrow|yesterday))?|"
        r"what (?:date|day) (?:is|was|will) (?P<subject>today|tomorrow|yesterday)(?: be)?|"
        r"tell me (?:the )?(?P<tell>today|tomorrow|yesterday)'s date)", clean)
    if not match:
        return None
    days = [value for value in match.groupdict().values() if value]
    if len(set(days)) > 1:
        return None
    day = days[0] if days else 'today'
    return ToolRequest('time.now', {'kind': 'date', 'day_offset': {'today': 0, 'tomorrow': 1, 'yesterday': -1}[day]},
                       source='clock-read')
