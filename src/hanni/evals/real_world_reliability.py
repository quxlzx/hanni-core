"""Independent development probe for everyday owner language.

This is a read-only router evaluation. It never opens apps, reads accounts,
starts a model, or loads the sealed live-session holdout.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass

from hanni.evals.routing import build_default_host


@dataclass(frozen=True)
class Case:
    family: str
    query: str
    required: tuple[str, ...]
    previous: str = ''


_FAMILIES = {
    'calendar_date_reads': ('google_calendar.agenda', [
        'show my agenda tomorrow', 'what meetings do i have on Sunday',
        'check my calendar for September 28', 'anything on my calendar yesterday',
        'what am i doing this Friday', 'show my schedule next Monday',
        'which appointments are on 2026-09-29', 'do i have anything this weekend',
        'what is on my calendar this afternoon', 'show events on my calendar today']),
    'calendar_availability': ('google_calendar.agenda', [
        'am i free tomorrow at 10am', 'am i busy Sunday at 9pm',
        'do i have anything at noon today', 'am i available Friday at 3pm',
        'am i free tonight', 'am i busy this afternoon',
        'do i have something tomorrow morning', 'am i free on Saturday at 11am',
        'is my calendar clear next Tuesday', 'do i have any meetings this evening']),
    'calendar_writes': ('google_calendar.create', [
        'schedule biology review tomorrow at 4pm', 'add dentist appointment Friday at 2pm',
        'put lunch on my calendar tomorrow at noon', 'book a meeting Monday at 9am',
        'create an event called reading on 2026-10-03 at 3pm',
        'schedule a study block Tuesday at 5pm', 'add a call to my calendar today at 8pm',
        'book a doctor appointment next Wednesday at 10am',
        'schedule chores Sunday at 1pm', 'put groceries on my calendar tomorrow at 6pm']),
    'system_grounding': ('disk.usage', [
        'do i have an e drive', 'which drives are mounted', 'list all my drives',
        'is my f drive present', 'show disk space on every drive',
        'how full is the c drive', 'is there a d drive on this computer',
        'show used space for all drives', 'what volumes do i have',
        'does this pc have a g drive']),
    'model_status': ('model.status', [
        'is hanni using the gpu', 'which gpu is hanni on', 'check the model status',
        'is the llm server reachable', 'what quantization is loaded',
        'is your model on cpu', 'show hanni model placement',
        'what context length is the model using', 'is llama running locally',
        'what device did the model load on']),
    'app_actions': ('app.open', [
        'open chrome', 'launch notepad', 'bring up firefox',
        'open one note', 'start discord', 'fire up steam',
        'open the calculator app', 'launch paint',
        'open file explorer', 'bring up vscode']),
    'file_search': ('file.search', [
        'find my invoice file in documents', 'search downloads for tax form',
        'find the project proposal pdf', 'look for my budget spreadsheet',
        'search documents for meeting notes', 'find my cover letter file',
        'look for the warranty pdf in downloads', 'search desktop for travel plan',
        'find the grocery list document', 'search my files for application letter']),
    'diagnostic_completion': ('system.performance', [
        'why is my computer so sluggish', 'check why this pc is slow',
        'everything takes ages to load', 'my laptop is lagging badly',
        'why does the desktop keep stalling', 'check system performance',
        'what is making my pc crawl', 'my machine feels unresponsive',
        'why are apps taking forever to open', 'diagnose this slow computer']),
}


def cases() -> list[Case]:
    rows = [Case(family, query, (tool,)) for family, (tool, queries) in _FAMILIES.items()
            for query in queries]
    rows.extend(Case('media_context', query, required, previous) for previous, query, required in [
        ('play spotify', 'pause it', ('spotify.play_pause',)),
        ('play spotify', 'resume that', ('spotify.play_pause',)),
        ('play spotify', 'skip it', ('spotify.next',)),
        ('play spotify', 'what is playing', ('spotify.status',)),
        ('pause my music', 'resume it', ('media.play_pause',)),
        ('pause my music', 'play that', ('media.play_pause',)),
        ('play a song', 'skip this', ('media.next_track',)),
        ('play a song', 'pause that', ('media.play_pause',)),
        ('play spotify', 'next', ('spotify.next',)),
        ('play spotify', 'previous', ('spotify.previous',)),
    ])
    rows.extend(Case('mixed_domain', query, required) for query, required in [
        ('show my calendar tomorrow and cpu usage', ('google_calendar.agenda', 'system.stats')),
        ('check my calendar Friday and ram usage', ('google_calendar.agenda', 'system.stats')),
        ('open notepad and show my memory usage', ('app.open', 'system.stats')),
        ('what is my model status and gpu memory', ('model.status', 'gpu.memory')),
        ('check disk space and cpu usage', ('disk.usage', 'system.stats')),
        ('open chrome and check system performance', ('app.open', 'system.performance')),
        ('show my calendar today and model status', ('google_calendar.agenda', 'model.status')),
        ('check storage space and gpu memory', ('disk.usage', 'gpu.memory')),
        ('show my meetings tomorrow and current time', ('google_calendar.agenda', 'time.now')),
        ('check ram usage and top cpu process', ('system.stats', 'process.top_cpu')),
    ])
    return rows


def evaluate(host=None) -> dict:
    host = host or build_default_host()
    results = []
    for index, case in enumerate(cases(), 1):
        history = [{'role': 'user', 'content': case.previous}] if case.previous else ()
        decision = host.route(case.query, history=history)
        selected = [tool.capability_id for tool in decision.tools]
        results.append({'id': f'DEV-{index:03d}', 'family': case.family,
                        'query': case.query, 'required': list(case.required),
                        'selected': selected, 'passed': set(case.required) <= set(selected)})
    totals = Counter(row['family'] for row in results)
    passed = Counter(row['family'] for row in results if row['passed'])
    return {'scope': 'read_only_router', 'total': len(results),
            'passed': sum(row['passed'] for row in results),
            'families': {name: {'passed': passed[name], 'total': total}
                         for name, total in sorted(totals.items())}, 'results': results}


def main() -> None:
    print(json.dumps(evaluate(), indent=2))


if __name__ == '__main__':
    main()
