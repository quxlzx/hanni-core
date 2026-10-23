"""Read-only desktop delivery of recorded events, with bounded deduplication."""
from collections import deque


class NotificationFeed:
    def __init__(self):
        self.initialized = False
        self.seen = set()
        self.order = deque()

    def observe(self, snapshot):
        if not isinstance(snapshot, dict) or snapshot.get('available') is not True:
            return []
        items = snapshot.get('items')
        if not isinstance(items, list):
            return []
        fresh = []
        settings = snapshot.get('preferences')
        preferences = settings.get('categories', {}) if isinstance(settings, dict) else {}
        if not isinstance(preferences, dict):
            preferences = {}
        for item in items[:1000]:
            if not isinstance(item, dict):
                continue
            identifier = item.get('id')
            if not isinstance(identifier, str) or not identifier or len(identifier) > 128 or identifier in self.seen:
                continue
            self.seen.add(identifier)
            self.order.append(identifier)
            if len(self.order) > 2048:
                self.seen.discard(self.order.popleft())
            title = item.get('title')
            category = item.get('category') if isinstance(item.get('category'), str) else ''
            if (self.initialized and not item.get('read') and not item.get('dismissed')
                    and preferences.get(category) is not False and isinstance(title, str)):
                # Native balloons contain only the already-redacted event title, never message bodies.
                title = ''.join(character for character in ' '.join(title.split()) if character.isprintable())[:120]
                if title:
                    priority = item.get('priority')
                    fresh.append((priority if isinstance(priority, str) else 'informational', title))
        self.initialized = True
        rank = {'critical': 0, 'action_required': 1, 'informational': 2}
        return [title for priority, title in sorted(fresh, key=lambda value: rank.get(value[0], 3))]


class NotificationRateLimit:
    def __init__(self, maximum=3, seconds=60):
        self.maximum, self.seconds = maximum, seconds
        self.sent = deque()

    def admit(self, now):
        while self.sent and self.sent[0] <= now - self.seconds:
            self.sent.popleft()
        if len(self.sent) >= self.maximum:
            return False
        self.sent.append(now)
        return True


class VoiceModeFeed:
    """Fixed-text mode changes; no transcript data or replay of old sessions."""
    def __init__(self):
        self.session = None
        self.revision = 0
        self.mode = None
        self.phase = None

    @staticmethod
    def message(mode, state):
        if mode:
            return 'HANNI is listening.'
        if state in {'muted', 'muting'}:
            return 'HANNI is not listening. Microphone muted.'
        if state == 'disabled':
            return 'HANNI is not listening. Voice is unavailable.'
        return 'HANNI is in standby. Say "Hanni" to start listening.'

    def observe(self, snapshot):
        if not isinstance(snapshot, dict) or type(snapshot.get('listening_mode')) is not bool:
            return []
        session, revision = snapshot.get('mode_session'), snapshot.get('mode_revision')
        if (not isinstance(session, str) or not session or len(session) > 128
                or type(revision) is not int or revision < 0):
            return []
        mode = snapshot['listening_mode']
        state = snapshot.get('state')
        if state not in {'disabled', 'muting', 'muted', 'standby', 'listening', 'speaking', 'processing'}:
            return []
        available = snapshot.get('available') is True and state not in {'disabled', 'muting', 'muted'}
        if mode and not available:
            return []
        phase = 'listening' if mode else 'muted' if state in {'muting', 'muted'} else 'disabled' if state == 'disabled' else 'standby'
        if self.session != session:
            # Announce the current active voice state; never replay earlier history.
            previously_listening = self.mode is True
            self.session, self.revision, self.mode, self.phase = session, revision, mode, phase
            return [self.message(mode, state)] if snapshot.get('available') is True or previously_listening else []
        if revision < self.revision:
            return []  # Ignore an older in-flight snapshot.
        messages = []
        events = snapshot.get('mode_events')
        if available and isinstance(events, list):
            # Retain a quick wake/standby pair between polls. Large backlogs are
            # coalesced into the current state instead of flooding the desktop.
            fresh = [event for event in events[-32:] if isinstance(event, dict)
                and type(event.get('revision')) is int and self.revision < event['revision'] <= revision
                and type(event.get('engaged')) is bool]
            if len(fresh) <= 2:
                for event in sorted(fresh, key=lambda event: event['revision']):
                    if event['engaged'] != self.mode:
                        self.mode = event['engaged']
                        messages.append(self.message(self.mode, 'listening' if self.mode else 'standby'))
        if mode != self.mode:
            messages.append(self.message(mode, state))
        if not messages and phase != self.phase:
            messages.append(self.message(mode, state))
        self.mode, self.revision, self.phase = mode, revision, phase
        return messages
