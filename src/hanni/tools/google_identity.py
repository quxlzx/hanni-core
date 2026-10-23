"""Google account labels and least-privilege capability scopes (no network)."""
from __future__ import annotations

import re

PREFIX = 'https://www.googleapis.com/auth/'
IDENTITY_SCOPE = PREFIX + 'userinfo.email'
CAPABILITY_SCOPES = {
    'calendar.read': (PREFIX + 'calendar.events.readonly', PREFIX + 'calendar.calendarlist.readonly'),
    'calendar.write': (PREFIX + 'calendar.events', PREFIX + 'calendar.calendarlist.readonly'),
    'gmail.read': (PREFIX + 'gmail.readonly',),
    'drive.read': (PREFIX + 'drive.metadata.readonly',),
    'docs.read': (PREFIX + 'drive.readonly',),
    'tasks.read': (PREFIX + 'tasks.readonly',),
    'tasks.write': (PREFIX + 'tasks',),
}
ALLOWED_SCOPES = frozenset({IDENTITY_SCOPE, *(scope for group in CAPABILITY_SCOPES.values() for scope in group)})
IMPLIES = {PREFIX + 'calendar.events': {PREFIX + 'calendar.events.readonly'},
           PREFIX + 'drive.readonly': {PREFIX + 'drive.metadata.readonly'},
           PREFIX + 'tasks': {PREFIX + 'tasks.readonly'}}


class GoogleAccessError(ValueError):
    def __init__(self, message, code='api_error'):
        super().__init__(message)
        self.code = code


def account_label(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}', value) or value in {'all', 'default'}:
        raise GoogleAccessError('Use a local account label such as personal, school or work (1–32 lowercase letters, digits, _ or -).', 'invalid_arguments')
    return value


def scopes_for(capabilities=None):
    requested = capabilities or ('calendar.read',)
    unknown = set(requested) - CAPABILITY_SCOPES.keys()
    if unknown:
        raise GoogleAccessError('Unsupported scope group; choose: ' + ', '.join(CAPABILITY_SCOPES), 'invalid_arguments')
    scopes = {IDENTITY_SCOPE}
    for capability in requested:
        scopes.update(CAPABILITY_SCOPES[capability])
    for broad, narrower in IMPLIES.items():
        if broad in scopes:
            scopes.difference_update(narrower)
    return tuple(sorted(scopes))


def authorized(scopes, capability):
    expanded = set(scopes)
    for scope in tuple(expanded):
        expanded.update(IMPLIES.get(scope, ()))
    return set(CAPABILITY_SCOPES[capability]) <= expanded


def account_labels(vault):
    if callable(getattr(vault, 'labels', None)):
        return tuple(vault.labels())
    # Simple in-memory vaults are used by offline tests and provider adapters.
    records = getattr(vault, 'records', {})
    return tuple(dict.fromkeys(('personal', 'school', *records)))


def preferences(vault):
    getter = getattr(vault, 'preferences', None)
    return getter() if callable(getter) else {}
