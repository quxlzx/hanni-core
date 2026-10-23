"""Provider-independent mail records and a Gmail GET-only adapter."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import getaddresses, parseaddr
from typing import Protocol

from hanni.tools.google_access import ACCOUNTS, GoogleAccess, GoogleAccessError, _body, _headers, _message_id, _text


class EmailProviderError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def provider_error(exc):
    text = str(exc).lower()
    code = ('EMAIL_NOT_CONNECTED' if 'not connected' in text or 'no google accounts' in text else
            'AUTH_EXPIRED' if any(s in text for s in ('401', 'expired', 'refresherror', 'invalid_grant')) else
            'PERMISSION_DENIED' if '403' in text or 'denied' in text or 'scope' in text else
            'RATE_LIMITED' if '429' in text or 'rate limit' in text else 'PROVIDER_ERROR')
    messages = {'EMAIL_NOT_CONNECTED': 'Your email account is not connected.',
                'AUTH_EXPIRED': 'Your Gmail connection needs to be reauthenticated.',
                'PERMISSION_DENIED': 'Gmail denied permission to read this mailbox.',
                'RATE_LIMITED': 'Gmail is rate limiting requests. Try again later.',
                'PROVIDER_ERROR': 'Gmail could not complete this request.'}
    return EmailProviderError(code, messages[code])


@dataclass(frozen=True, slots=True)
class NormalizedEmail:
    message_id: str
    thread_id: str | None
    account: str
    sender_name: str
    sender_email: str
    recipients: tuple[str, ...]
    subject: str
    received_at: datetime
    snippet: str
    body_text: str | None
    labels: tuple[str, ...]
    attachment_names: tuple[str, ...]
    body_truncated: bool = False
    untrusted_content: bool = True

    @property
    def has_attachments(self): return bool(self.attachment_names)

    def to_dict(self):
        return {**asdict(self), 'received_at': self.received_at.isoformat(),
                'has_attachments': self.has_attachments}


def normalize_message(raw, account, *, full=False):
    payload = raw.get('payload') or {}
    headers = _headers(payload)
    name, address = parseaddr(headers.get('from', ''))
    body = _body(payload) if full else {}
    pending, filenames, visited = [payload], [], 0
    while pending and visited < 80:
        part = pending.pop(); visited += 1
        if part.get('filename'): filenames.append(_text(part['filename'], 200))
        pending.extend(p for p in part.get('parts', [])[:40] if isinstance(p, dict))
    return NormalizedEmail(_message_id(raw.get('id')), raw.get('threadId'), account,
                           _text(name, 200), _text(address, 300),
                           tuple(address for _, address in getaddresses([headers.get('to', '')])),
                           headers.get('subject', ''), datetime.fromtimestamp(int(raw.get('internalDate', 0)) / 1000, timezone.utc),
                           _text(raw.get('snippet'), 800), body.get('text'),
                           tuple(raw.get('labelIds') or ()), tuple(filenames), bool(body.get('truncated')))


class EmailProvider(Protocol):
    def accounts(self, requested: str = '') -> tuple[str, ...]: ...
    def search(self, account: str, query: str, limit: int) -> tuple[list[dict], bool]: ...
    def read(self, account: str, message_id: str, *, full: bool = True) -> NormalizedEmail: ...
    def thread(self, account: str, thread_id: str) -> list[NormalizedEmail]: ...


class GmailEmailProvider:
    """Uses the existing vault, OAuth scope checks, timeout and response-size cap."""
    def __init__(self, access: GoogleAccess): self.access = access

    def accounts(self, requested=''):
        try:
            if requested == 'all':
                return self.access._selected('all')
            return (self.access.resolve_account(requested, 'gmail'),)
        except GoogleAccessError as exc: raise provider_error(exc) from None

    def _get(self, account, path, params):
        try: return self.access._get(account, '/gmail/v1/users/me/' + path, params)
        except GoogleAccessError as exc: raise provider_error(exc) from None

    def search(self, account, query, limit):
        rows, token = [], None
        for _ in range(2):
            params = {'q': query, 'maxResults': min(30, limit - len(rows)), 'includeSpamTrash': 'false'}
            if token: params['pageToken'] = token
            data = self._get(account, 'messages', params)
            rows.extend(data.get('messages') or [])
            token = data.get('nextPageToken')
            if not token or len(rows) >= limit: break
        return rows[:limit], bool(token or len(rows) > limit)

    def read(self, account, message_id, *, full=True):
        raw = self._get(account, 'messages/' + _message_id(message_id), {'format': 'full' if full else 'metadata'})
        try:
            return normalize_message(raw, account, full=full)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise EmailProviderError('PROVIDER_ERROR', 'Gmail returned an invalid message.') from None

    def thread(self, account, thread_id):
        raw = self._get(account, 'threads/' + _message_id(thread_id), {'format': 'full'})
        messages = raw.get('messages') or []
        # Retain the newest state even in exceptionally large threads.
        try:
            messages.sort(key=lambda row: int(row.get('internalDate') or 0), reverse=True)
            return [normalize_message(row, account, full=True) for row in messages[:30]]
        except (ValueError, TypeError, KeyError, AttributeError):
            raise EmailProviderError('PROVIDER_ERROR', 'Gmail returned an invalid thread.') from None
