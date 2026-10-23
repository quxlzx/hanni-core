"""Bounded CDP event observation; preserves the native download policy."""
from contextlib import contextmanager
import math
import re

class DownloadEvents:

    def __init__(self, limit=24):
        if type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError('Download event limit must be an integer from 1 through 128.')
        self.report = {'scope': 'Passive original native CDP events; no delivery or no-file inference', 'policy_overridden': False, 'owner_downloads_read': False, 'event_limit': limit, 'events': [], 'dropped_events': 0}

    def record(self, event, value):
        if event not in {'Page.downloadWillBegin', 'Page.downloadProgress'} or not isinstance(value, dict):
            return
        if len(self.report['events']) >= self.report['event_limit']:
            self.report['dropped_events'] = min(self.report['dropped_events'] + 1, 1000000)
            return
        item = {'event': event}
        state = value.get('state')
        if isinstance(state, str) and state in {'inProgress', 'completed', 'canceled'}:
            item['state'] = state
        for field in ['receivedBytes', 'totalBytes']:
            number = value.get(field)
            if type(number) in (int, float) and 0 <= number <= 2 ** 40 and math.isfinite(number):
                item[field] = number
        if event == 'Page.downloadWillBegin':
            url = value.get('url')
            item['url_class'] = 'blob' if isinstance(url, str) and url.startswith('blob:') else 'withheld'
            name = value.get('suggestedFilename')
            if isinstance(name, str) and len(name) <= 128 and re.fullmatch('hanni-model-lab-[0-9a-f-]{1,72}\\.json', name):
                item['suggested_filename'] = name
            else:
                item['suggested_filename'] = 'withheld'
        self.report['events'].append(item)

@contextmanager
def observe_downloads(session, *, enabled=False):
    if not enabled:
        yield None
        return
    events = DownloadEvents()
    session.report['passive_download_observation'] = events.report
    cdp = session.page.context.new_cdp_session(session.page)
    try:
        for name in ['Page.downloadWillBegin', 'Page.downloadProgress']:
            cdp.on(name, lambda value, event=name: events.record(event, value))
        cdp.send('Page.enable')
        events.report['attached'] = True
        yield events
    finally:
        try:
            cdp.detach()
            events.report['detached'] = True
        except Exception:
            events.report['detached'] = False
            events.report['detach_error'] = 'CDP observation could not detach; native ownership cleanup still applies.'
