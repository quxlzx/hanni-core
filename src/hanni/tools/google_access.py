"""Opt-in Google access for mail reads and owner-requested Calendar reads/writes."""
from __future__ import annotations

import base64
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from html import unescape
from html.parser import HTMLParser
from urllib.parse import quote

from hanni.tools.base import ToolDefinition, ToolResult
from hanni.tools.google_identity import (GoogleAccessError, account_label, account_labels,
    authorized, preferences, ALLOWED_SCOPES, PREFIX, IDENTITY_SCOPE)

ACCOUNTS = ('personal', 'school')
SCOPES = ('https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/calendar.events',
          'https://www.googleapis.com/auth/calendar.calendarlist.readonly')
SERVICE = 'HANNI.Google.v2'
API = 'https://www.googleapis.com'
MAX_RESPONSE = 2_000_000


class WindowsTokenVault:
    """Explicit Windows Credential Manager backend; never plaintext fallback."""
    def __init__(self):
        if sys.platform != 'win32':
            raise GoogleAccessError('Google sign-in uses Windows Credential Manager; run on Windows.')
        try:
            from keyring.backends.Windows import WinVaultKeyring
            self.backend = WinVaultKeyring()
        except ImportError as exc:
            raise GoogleAccessError('Google support is not installed. Run HANNI setup again, or install: python -m pip install -e ".[google]"') from exc

    def get(self, account):
        _account(account)
        raw = self.backend.get_password(SERVICE, account)
        if not raw:
            return None
        try:
            record = json.loads(raw)
            if not isinstance(record, dict) or not isinstance(record.get('email'), str) or not isinstance(record.get('credentials'), dict):
                raise ValueError()
            return record
        except (ValueError, TypeError) as exc:
            raise GoogleAccessError('Stored Google connection is invalid; reconnect that account.') from exc

    def set(self, account, record):
        _account(account)
        self.backend.set_password(SERVICE, account, json.dumps(record))
        labels = self.labels()
        if account not in labels:
            self.backend.set_password(SERVICE, '__accounts__', json.dumps([*labels, account]))

    def labels(self):
        raw = self.backend.get_password(SERVICE, '__accounts__')
        try:
            labels = json.loads(raw) if raw else []
            if not isinstance(labels, list): raise ValueError()
            return tuple(dict.fromkeys((*ACCOUNTS, *(_account(label) for label in labels))))
        except (ValueError, TypeError):
            raise GoogleAccessError('Stored Google account index is invalid.') from None

    def preferences(self):
        raw = self.backend.get_password(SERVICE, '__settings__')
        try:
            data = json.loads(raw) if raw else {}
            if not isinstance(data, dict): raise ValueError()
            return data
        except (ValueError, TypeError):
            raise GoogleAccessError('Stored Google account preferences are invalid.') from None

    def set_preference(self, account, service=None):
        if self.get(_account(account)) is None:
            raise GoogleAccessError('Connect that account before selecting it.', 'not_connected')
        if service not in {None, 'calendar', 'gmail', 'drive', 'docs', 'tasks'}:
            raise GoogleAccessError('Unknown Google service.', 'invalid_arguments')
        data = self.preferences()
        data[service or 'default_google_account'] = account
        self.backend.set_password(SERVICE, '__settings__', json.dumps(data))

    def delete(self, account):
        _account(account)
        if self.get(account) is not None:
            self.backend.delete_password(SERVICE, account)


def _account(value):
    return account_label(value)


def _limit(value, default=10, maximum=30):
    value = default if value is None else value
    if type(value) is not int or not 1 <= value <= maximum:
        raise GoogleAccessError(f'limit must be an integer from 1 to {maximum}')
    return value


def _text(value, limit=1000):
    # Keep external text inert in a terminal as well as in model context.
    return ''.join(c for c in str(value or '') if c in '\n\t' or ord(c) >= 32 and ord(c) != 127)[:limit]


def validate_credentials(info):
    if not isinstance(info, dict) or info.get('token_uri') != 'https://oauth2.googleapis.com/token':
        raise GoogleAccessError('Unexpected Google token endpoint; reconnect using an official desktop client.')
    scopes = info.get('scopes', [])
    if not isinstance(scopes, list) or not scopes or not set(scopes) <= ALLOWED_SCOPES:
        raise GoogleAccessError('Google connection has unsupported scopes; reconnect with the requested service scopes.')


class GoogleAccess:
    def __init__(self, vault=None, transport=None, timezone_name=None):
        self._vault = vault
        self.transport = transport  # Offline fixture seam. Production always uses fixed Google URLs.
        self.timezone_name = timezone_name

    @property
    def vault(self):
        if self._vault is None:
            self._vault = WindowsTokenVault()
        return self._vault

    def accounts(self):
        rows = []
        for label in account_labels(self.vault):
            record = self.vault.get(label)
            rows.append({'account': label, 'connected': record is not None,
                         'email': record['email'] if record else None,
                         'calendar_ids': record.get('calendar_ids', ['primary']) if record else []})
        return rows

    def _record(self, account):
        record = self.vault.get(_account(account))
        if record is None:
            raise GoogleAccessError(f'{account} is not connected. Run: hanni google login --account {account}', 'not_connected')
        return record

    def resolve_account(self, requested=None, service='calendar'):
        if requested:
            self._record(_account(requested))
            return requested
        settings = preferences(self.vault)
        preferred = settings.get(service) or settings.get('default_google_account')
        if preferred:
            self._record(preferred)
            return preferred
        connected = [label for label in account_labels(self.vault) if self.vault.get(label) is not None]
        if not connected:
            raise GoogleAccessError('No Google accounts are connected. Run: hanni google login', 'not_connected')
        return 'personal' if 'personal' in connected else connected[0]

    def has_capability(self, account, capability):
        record = self._record(account)
        return authorized(record.get('credentials', {}).get('scopes', ()), capability)

    def _get(self, account, path, params=None):
        return self._request(account, path, params=params)

    def _post(self, account, path, body, params=None):
        return self._request(account, path, method='POST', body=body, params=params)

    def _request(self, account, path, *, method='GET', params=None, body=None, text_response=False):
        # Only fixed Google origins and service paths are used by adapters.
        if method not in {'GET', 'POST', 'PATCH', 'DELETE'}:
            raise GoogleAccessError('Unsupported Google method', 'invalid_arguments')
        if path.startswith('/gmail/v1/'):
            if method != 'GET':
                raise GoogleAccessError('Gmail writes are not implemented.', 'not_implemented')
            capability, origin = 'gmail.read', API
        elif path.startswith('/calendar/v3/'):
            capability, origin = ('calendar.read' if method == 'GET' else 'calendar.write'), API
        elif path.startswith('/drive/v3/'):
            if method != 'GET':
                raise GoogleAccessError('Drive writes are not implemented.', 'not_implemented')
            capability, origin = ('docs.read' if path.endswith('/export') else 'drive.read'), API
        elif path.startswith('/tasks/v1/'):
            capability, origin = ('tasks.read' if method == 'GET' else 'tasks.write'), 'https://tasks.googleapis.com'
        elif path == '/oauth2/v2/userinfo' and method == 'GET':
            capability, origin = None, API
        else:
            raise GoogleAccessError('Unsupported Google API path', 'invalid_arguments')
        record = self._record(account)
        info = record.get('credentials', {})
        # Empty credentials are only accepted by explicitly injected offline transports.
        if self.transport is None or info:
            validate_credentials(info)
            if capability and not authorized(info['scopes'], capability):
                raise GoogleAccessError(f'{account}: authorize {capability} with hanni google login --account {account} --scopes {capability} --replace', 'permission_denied')
            if capability is None and IDENTITY_SCOPE not in info['scopes']:
                raise GoogleAccessError('Account identity scope is missing; reconnect.', 'permission_denied')
        if body is not None and (not isinstance(body, dict) or len(json.dumps(body).encode('utf-8')) > 64000):
            raise GoogleAccessError('Google request body is invalid or too large.', 'invalid_arguments')
        if self.transport is not None:
            if method == 'GET': return self.transport(account, path, params or {})
            if method == 'POST': return self.transport(account, path, params or {}, body)
            return self.transport(account, path, params or {}, body, method=method)
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import AuthorizedSession, Request
            from google.auth.exceptions import RefreshError
            import requests
            credentials = Credentials.from_authorized_user_info(info, info['scopes'])
            class TimedRequest(Request):
                def __call__(self, *args, **kwargs):
                    kwargs['timeout'] = 20
                    return super().__call__(*args, **kwargs)
            with requests.Session() as auth_session:
                with AuthorizedSession(credentials, auth_request=TimedRequest(auth_session),
                                       max_refresh_attempts=1, refresh_timeout=20) as session:
                    with session.request(method, origin + path, params=params or {}, json=body,
                                         timeout=20, allow_redirects=False, stream=True) as response:
                        code = response.status_code
                        if code not in {200, 201, 204}:
                            state, reason = {400: ('invalid_arguments', 'Google rejected the request'),
                                401: ('not_connected', 'sign-in expired or revoked; reconnect'),
                                403: ('permission_denied', 'API disabled, scope missing, or account policy denied access'),
                                404: ('not_found', 'the requested Google item was not found'),
                                429: ('rate_limited', 'rate limited; try again later')}.get(code, ('api_error', 'Google request failed'))
                            raise GoogleAccessError(f'{account}: {reason} (HTTP {code})', state)
                        chunks, size = [], 0
                        for chunk in response.iter_content(32768):
                            size += len(chunk)
                            if size > MAX_RESPONSE:
                                raise GoogleAccessError('Google response too large; narrow the request.', 'partial')
                            chunks.append(chunk)
                        raw = b''.join(chunks)
                        result = raw.decode('utf-8') if text_response else (json.loads(raw) if raw else {})
            if not text_response and not isinstance(result, dict):
                raise GoogleAccessError('Google returned an invalid response')
            self.vault.set(account, {**record, 'credentials': json.loads(credentials.to_json()),
                                    'last_successful_api_check': datetime.now(timezone.utc).isoformat()})
            return result
        except GoogleAccessError:
            raise
        except ImportError:
            raise GoogleAccessError('Google support is not installed. Run HANNI setup again.') from None
        except Exception as exc:
            # Never include library exception text, response bodies, or credentials.
            state = 'not_connected' if type(exc).__name__ == 'RefreshError' else 'api_error'
            raise GoogleAccessError(f'{account}: Google access failed; check network or reconnect.', state) from None

    def _write_account(self, requested=None):
        return self.resolve_account(requested, 'calendar')

    def create_event(self, args):
        account = self._write_account(args.get('account'))
        record = self._record(account)
        summary = _text(args.get('summary'), 300).strip()
        if not summary:
            raise GoogleAccessError('event summary is required')
        calendar_id = str(args.get('calendar_id') or 'primary')
        allowed = record.get('calendar_ids', ['primary'])
        if calendar_id not in allowed and calendar_id != 'primary':
            raise GoogleAccessError('Create events only on a calendar selected during Google connection.')
        all_day = bool(args.get('all_day', False))
        if all_day:
            try:
                start_date = datetime.strptime(str(args.get('start_date')), '%Y-%m-%d').date()
                end_date = datetime.strptime(str(args.get('end_date')), '%Y-%m-%d').date()
            except (ValueError, TypeError):
                raise GoogleAccessError('all-day events require YYYY-MM-DD start_date and end_date') from None
            if end_date <= start_date:
                raise GoogleAccessError('end_date must be after start_date')
            event = {'summary': summary, 'start': {'date': start_date.isoformat()}, 'end': {'date': end_date.isoformat()}}
        else:
            try:
                start = datetime.fromisoformat(str(args.get('start')))
                end = datetime.fromisoformat(str(args.get('end')))
            except (ValueError, TypeError):
                raise GoogleAccessError('timed events require ISO start and end timestamps') from None
            if start.tzinfo is None or end.tzinfo is None:
                raise GoogleAccessError('timed events require timezone-aware start and end timestamps')
            if end <= start:
                raise GoogleAccessError('event end must be after start')
            if end - start > timedelta(days=1):
                raise GoogleAccessError('single event duration is limited to 24 hours')
            event = {'summary': summary, 'start': {'dateTime': start.isoformat()}, 'end': {'dateTime': end.isoformat()}}
        location = _text(args.get('location'), 400).strip()
        description = _text(args.get('description'), 1500).strip()
        if location: event['location'] = location
        if description: event['description'] = description
        try:
            result = self._post(account, '/calendar/v3/calendars/' + quote(calendar_id, safe='') + '/events', event)
        except GoogleAccessError as exc:
            if exc.code in {'api_error', 'partial'}:
                raise GoogleAccessError('Calendar creation outcome is unknown. Check the calendar before retrying; the request was not replayed.', 'outcome_unknown') from None
            raise
        event_id = _text(result.get('id'), 500)
        if not event_id:
            raise GoogleAccessError('Google did not return an event ID; creation could not be confirmed. Check the calendar before retrying.', 'outcome_unknown')
        return {'account': account, 'email': record['email'], 'calendar_id': calendar_id,
                'id': event_id, 'summary': _text(result.get('summary') or summary, 300),
                'start': result.get('start', event['start']), 'end': result.get('end', event['end']),
                'html_link': _text(result.get('htmlLink'), 1000), 'created': True,
                'outcome': 'created_but_not_reverified'}

    def _selected(self, account):
        if account == 'all':
            return account_labels(self.vault)
        return (_account(account),)

    def mail_search(self, args):
        query = args.get('query') or 'in:inbox'
        if not isinstance(query, str) or len(query) > 500:
            raise GoogleAccessError('query must be at most 500 characters')
        limit = _limit(args.get('limit'))
        rows, errors, truncated = [], [], False
        for account in self._selected(args.get('account') or self.resolve_account(service='gmail')):
            try:
                found = self._get(account, '/gmail/v1/users/me/messages', {'q': query, 'maxResults': limit})
                truncated |= bool(found.get('nextPageToken'))
                for item in found.get('messages', [])[:limit]:
                    msg = self._get(account, '/gmail/v1/users/me/messages/' + _message_id(item['id']), {'format': 'metadata'})
                    headers = _headers(msg.get('payload', {}))
                    rows.append({'account': account, 'email': self._record(account)['email'],
                                 'id': msg['id'], 'subject': headers.get('subject', ''),
                                 'from': headers.get('from', ''), 'date': headers.get('date', ''),
                                 'snippet': _text(msg.get('snippet'), 600),
                                 'internal_date_ms': int(msg.get('internalDate') or 0)})
            except GoogleAccessError as exc:
                errors.append({'account': account, 'error': str(exc)})
        rows.sort(key=lambda row: row['internal_date_ms'], reverse=True)
        return {'messages': rows[:limit], 'errors': errors, 'partial': bool(errors),
                'truncated': truncated or len(rows) > limit, 'fetched_at': datetime.now(timezone.utc).isoformat()}

    def mail_read(self, args):
        account = self.resolve_account(args.get('account'), 'gmail')
        message_id = _message_id(args.get('id'))
        msg = self._get(account, '/gmail/v1/users/me/messages/' + message_id, {'format': 'full'})
        return {'account': account, 'email': self._record(account)['email'], 'id': message_id,
                'headers': _headers(msg.get('payload', {})), 'body': _body(msg.get('payload', {})),
                'snippet': _text(msg.get('snippet'), 600), 'attachments_downloaded': False}

    def calendar_list(self, args):
        account = self.resolve_account(args.get('account'), 'calendar')
        result = self._get(account, '/calendar/v3/users/me/calendarList', {'maxResults': 100})
        return {'account': account, 'calendars': [
            {'id': _text(c.get('id'), 500), 'summary': _text(c.get('summary'), 300),
             'time_zone': _text(c.get('timeZone'), 100), 'primary': bool(c.get('primary'))}
            for c in result.get('items', [])[:100]], 'truncated': bool(result.get('nextPageToken'))}

    def agenda(self, args, *, next_only=False):
        limit = _limit(args.get('limit'))
        days = args.get('days', 30 if next_only else 7)
        if type(days) is not int or not 1 <= days <= 366:
            raise GoogleAccessError('days must be 1..366')
        academic = args.get('academic_concept')
        if academic is not None and academic not in {'midterm', 'exam', 'test', 'quiz'}:
            raise GoogleAccessError('unsupported academic Calendar concept')
        course = args.get('course') or ''
        if academic and (not isinstance(course, str) or len(course) > 16 or
                         (course and not re.fullmatch(r'[A-Za-z0-9]+', course))):
            raise GoogleAccessError('invalid course filter')
        now = datetime.now(timezone.utc)
        start = now
        if academic:
            try:
                start = datetime.fromisoformat(args['time_min'])
                end = datetime.fromisoformat(args['time_max'])
            except (KeyError, ValueError, TypeError):
                raise GoogleAccessError('academic search requires exact time bounds') from None
            if (start.tzinfo is None or end.tzinfo is None or end <= start or
                    end - start > timedelta(days=366)):
                raise GoogleAccessError('academic search has invalid time bounds')
        elif args.get('start_date'):
            try:
                day = datetime.strptime(args['start_date'], '%Y-%m-%d')
                start = day.replace(tzinfo=ZoneInfo(self.timezone_name)) if self.timezone_name else day.astimezone()
            except (ValueError, TypeError):
                raise GoogleAccessError('start_date must be YYYY-MM-DD') from None
        if not academic:
            if args.get('start_date'):
                end_day = datetime.strptime(args['start_date'], '%Y-%m-%d') + timedelta(days=days)
                end = end_day.replace(tzinfo=ZoneInfo(self.timezone_name)) if self.timezone_name else end_day.astimezone()
            else:
                end = start + timedelta(days=days)
        rows, errors, truncated = [], [], False
        queried_calendars = []
        query = args.get('query') or ''
        if not isinstance(query, str) or len(query) > 500:
            raise GoogleAccessError('query must be a short string')
        if academic and query:
            raise GoogleAccessError('academic search filters locally; Google text query must be empty')
        # Unqualified calendar reads use connected slots. An explicit all/both
        # request still reports a missing slot, preserving partial-failure truth.
        selected = (self._selected(args['account']) if args.get('account') else
                    (self.resolve_account(service='calendar'),))
        if not selected:
            raise GoogleAccessError('No Google accounts are connected. Run: hanni google login')
        for account in selected:
            try:
                record = self._record(account)
                calendar_ids = record.get('calendar_ids', ['primary'])
                if not isinstance(calendar_ids, list) or not 1 <= len(calendar_ids) <= 5 or not all(isinstance(c, str) and c for c in calendar_ids):
                    raise GoogleAccessError('Invalid selected calendars; reconnect the account.')
                for calendar_id in calendar_ids:
                    queried_calendars.append({'account': account, 'calendar_id': calendar_id})
                    params = {'timeMin': start.isoformat(), 'timeMax': end.isoformat(),
                              'singleEvents': 'true', 'orderBy': 'startTime', 'showDeleted': 'false',
                              'maxResults': 250 if academic else 100}
                    if query:
                        params['q'] = query
                    # Bounded pagination: never silently claim completeness beyond the cap.
                    for _ in range(4 if academic else 3):
                        result = self._get(account, '/calendar/v3/calendars/' + quote(calendar_id, safe='') + '/events', params)
                        for event in result.get('items', []):
                            if event.get('status') == 'cancelled':
                                continue
                            beginning = event.get('start', {})
                            all_day = 'date' in beginning
                            raw = beginning.get('dateTime') or beginning.get('date')
                            if not raw:
                                continue
                            moment = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                            if moment.tzinfo is None:
                                moment = moment.replace(tzinfo=ZoneInfo(result.get('timeZone') or 'UTC'))
                            if next_only and moment < now:
                                continue
                            rows.append({'account': account, 'email': record['email'], 'calendar_id': calendar_id,
                                         'id': _text(event.get('id'), 500), 'summary': _text(event.get('summary'), 300),
                                         'start': beginning, 'end': event.get('end', {}), 'all_day': all_day,
                                         'start_local': moment.astimezone(ZoneInfo(self.timezone_name)).isoformat() if self.timezone_name else moment.astimezone().isoformat(),
                                         'start_utc': moment.astimezone(timezone.utc).isoformat(),
                                         'location': _text(event.get('location'), 400),
                                         'description': _text(event.get('description'), 1500)})
                        token = result.get('nextPageToken')
                        if not token:
                            break
                        params['pageToken'] = token
                    else:
                        truncated = True
            except (GoogleAccessError, ValueError, KeyError) as exc:
                errors.append({'account': account, 'error': str(exc) if isinstance(exc, GoogleAccessError)
                               else 'Unsupported or invalid Google calendar event data',
                               'code': exc.code if isinstance(exc, GoogleAccessError) else 'invalid_response'})
        rows.sort(key=lambda row: (row['start_utc'], row['account'], row['id']))
        match_details = None
        if academic:
            from hanni.tools.calendar_search import rank_academic_events
            rows, match_details = rank_academic_events(rows, academic, course)
        availability = None
        if args.get('availability_at') or args.get('availability_start'):
            try:
                def clock(value):
                    hour, minute = (int(part) for part in str(value).split(':'))
                    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                        raise ValueError
                    return start.replace(hour=hour, minute=minute)
                if not args.get('start_date') or days != 1:
                    raise ValueError
                point = clock(args['availability_at']) if args.get('availability_at') else None
                interval_start = clock(args['availability_start']) if args.get('availability_start') else None
                interval_end = clock(args['availability_end']) if args.get('availability_end') else None
                if interval_start and (not interval_end or interval_start >= interval_end):
                    raise ValueError
            except (TypeError, ValueError):
                raise GoogleAccessError('availability requires valid HH:MM times and one resolved date') from None
            overlapping = []
            for row in rows:
                beginning = row['start'].get('dateTime') or row['start'].get('date')
                ending = row['end'].get('dateTime') or row['end'].get('date')
                if not beginning or not ending:
                    continue
                first = datetime.fromisoformat(beginning.replace('Z', '+00:00'))
                last = datetime.fromisoformat(ending.replace('Z', '+00:00'))
                zone = ZoneInfo(self.timezone_name) if self.timezone_name else start.tzinfo
                if first.tzinfo is None: first = first.replace(tzinfo=zone)
                if last.tzinfo is None: last = last.replace(tzinfo=zone)
                if ((point is not None and first <= point < last)
                        or (interval_start is not None and interval_start < last and interval_end > first)):
                    overlapping.append(row)
            availability = {'at': point.isoformat() if point else None,
                            'start': interval_start.isoformat() if interval_start else None,
                            'end': interval_end.isoformat() if interval_end else None,
                            'busy': bool(overlapping),
                            'conflicting_event_ids': [row['id'] for row in overlapping],
                            'verified': not (errors or truncated or len(rows) > limit)}
        result_limit = (1 if academic and args.get('first_only') and
                        not match_details['ambiguous_course'] else limit)
        result = {'events': rows[:result_limit], 'errors': errors, 'partial': bool(errors),
                  'truncated': truncated or (not academic and len(rows) > limit), 'fetched_at': now.isoformat(),
                  'window_start': start.isoformat(), 'window_end': end.isoformat(),
                  'resolved_date': str(args.get('start_date') or start.date()),
                  'timezone': self.timezone_name or str(start.tzinfo),
                  'calendar_id': queried_calendars[0]['calendar_id'] if len(queried_calendars) == 1 else None,
                  'queried_calendars': queried_calendars,
                  'time_min': start.isoformat(), 'time_max': end.isoformat(),
                  'event_count': len(rows), 'availability': availability}
        if academic:
            result.update({'academic_concept': academic, 'course': course,
                           'account': args.get('account') or 'connected',
                           'first_only': bool(args.get('first_only')),
                           'temporal_source': args.get('temporal_source'),
                           'followup_context_used': bool(args.get('followup_context_used')),
                           'matched_count': len(rows), **match_details})
        if next_only:
            result['event'] = rows[0] if rows else None
            result['events'] = rows[:1]
            local_zone = ZoneInfo(self.timezone_name) if self.timezone_name else now.astimezone().tzinfo
            result['current_local_time'] = now.astimezone(local_zone).isoformat()
            if rows:
                event_start = datetime.fromisoformat(rows[0]['start_utc'])
                result['event_start_local'] = rows[0]['start_local']
                result['minutes_until_start'] = max(0, round((event_start - now).total_seconds() / 60))
            else:
                result['event_start_local'] = None
                result['minutes_until_start'] = None
        return result


def _message_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,200}', value):
        raise GoogleAccessError('Use the exact message ID from gmail.search')
    return value


def _headers(payload):
    return {str(row.get('name', '')).lower(): _text(row.get('value'), 1000)
            for row in payload.get('headers', [])[:100]
            if str(row.get('name', '')).lower() in {'subject', 'from', 'to', 'date'}}


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}: self.hidden += 1
        if tag in {'p', 'br', 'div'}: self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in {'script', 'style'}: self.hidden = max(0, self.hidden - 1)
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def _body(payload):
    queue, plain, html = [(payload, 0)], [], []
    visited = 0
    while queue and visited < 40:
        part, depth = queue.pop(0); visited += 1
        if depth > 10 or part.get('filename'): continue
        encoded = part.get('body', {}).get('data')
        if encoded and isinstance(encoded, str):
            try:
                decoded = base64.urlsafe_b64decode(encoded[:100000] + '=' * (-len(encoded[:100000]) % 4)).decode('utf-8', errors='replace')
            except (ValueError, TypeError):
                decoded = '[Unreadable body part]'
            if part.get('mimeType') == 'text/plain': plain.append(decoded)
            elif part.get('mimeType') == 'text/html': html.append(decoded)
        queue.extend((p, depth + 1) for p in part.get('parts', [])[:40] if isinstance(p, dict))
    if plain: text = '\n'.join(plain)
    else:
        parser = PlainHTML(); parser.feed('\n'.join(html)); text = ''.join(parser.parts)
    return {'text': _text(unescape(text), 10000), 'truncated': len(text) > 10000 or bool(queue),
            'untrusted_content': True}


def calendar_summary(data):
    """Speak returned evidence once, including partial failures and empty windows."""
    if data.get('academic_concept'):
        from hanni.tools.calendar_search import academic_summary
        return academic_summary(data)
    events = data.get('events', [])
    label = 'the requested period'
    if data.get('window_start'):
        try:
            first = datetime.fromisoformat(data['window_start']).strftime('%B %d').replace(' 0', ' ')
            end = datetime.fromisoformat(data['window_end'])
            last = (end - timedelta(microseconds=1)).strftime('%B %d').replace(' 0', ' ')
            label = first if first == last else f'{first} through {last}'
        except (ValueError, KeyError, TypeError):
            pass
    lines = []
    errors = data.get('errors', [])
    incomplete = bool(errors or data.get('partial') or data.get('truncated'))
    availability = data.get('availability')
    if availability is not None and availability.get('verified'):
        if availability.get('at'):
            local_time = 'at ' + datetime.fromisoformat(availability['at']).strftime('%I:%M %p').lstrip('0')
        else:
            first = datetime.fromisoformat(availability['start']).strftime('%I:%M %p').lstrip('0')
            last = datetime.fromisoformat(availability['end']).strftime('%I:%M %p').lstrip('0')
            local_time = f'from {first} to {last}'
        if availability['busy']:
            conflicts = set(availability.get('conflicting_event_ids', []))
            titles = [event.get('summary') or 'an event' for event in events if event.get('id') in conflicts]
            return f"You're busy {local_time}" + (f" with {', '.join(titles[:3])}." if titles else '.')
        return f"You're free {local_time} according to the calendars checked."
    if events:
        lines.append(f'Google Calendar for {label}:')
        for event in events[:5]:
            when = 'all day' if event.get('all_day') else 'time unavailable'
            if not event.get('all_day') and event.get('start_local'):
                try:
                    when = datetime.fromisoformat(event['start_local']).strftime('%I:%M %p on %B %d').lstrip('0')
                except (ValueError, TypeError):
                    pass
            lines.append(f"{_text(event.get('summary') or 'Untitled event', 200)}, {when} ({_text(event.get('account'), 30)}).")
        if len(events) > 5 or data.get('truncated'):
            lines.append('Showing the first returned events; there may be more.')
    elif not incomplete:
        lines.append(f'Your Google calendar is empty for {label}.')
    else:
        lines.append('No events were returned, but I could not check the full requested calendar scope.')
    if incomplete:
        lines.append('This result is incomplete.')
    for error in errors:
        lines.append(f"{_text(error.get('account'), 30)}: {_text(error.get('error'), 200)}")
    return ' '.join(lines)


def definitions(access=None):
    access = access or GoogleAccess()
    def run(name):
        def handler(args, context, request):
            try:
                if name == 'google.accounts': data = {'accounts': access.accounts()}
                elif name == 'gmail.search': data = access.mail_search(args)
                elif name == 'gmail.read': data = access.mail_read(args)
                elif name == 'google_calendar.list': data = access.calendar_list(args)
                elif name == 'google_calendar.create': data = access.create_event(args)
                else: data = access.agenda(args, next_only=name == 'google_calendar.next')
                data.setdefault('state', 'partial' if data.get('errors') or data.get('truncated') else 'verified')
                message = (calendar_summary(data) if name in {'google_calendar.agenda', 'google_calendar.next'}
                           else (f"Added '{data.get('summary') or 'event'}' to the {data.get('account')} Google Calendar."
                                 if name == 'google_calendar.create' else
                                 'Google read completed; check partial/errors and account labels.'))
                errors = data.get('errors') or []
                error = None
                # An empty, wholly transient agenda failure can be retried by
                # the original executor. Partial results, unknown failures and
                # authorization failures must never trigger this recovery.
                if name in {'google_calendar.agenda', 'google_calendar.next'} and errors and not data.get('events') and all(
                        item.get('code') in {'api_error', 'rate_limited'} for item in errors):
                    error = {'code': 'API_ERROR' if any(item['code']=='api_error' for item in errors) else 'RATE_LIMITED',
                             'retryable': True}
                return ToolResult(name, not bool(errors), message, data, error=error)
            except GoogleAccessError as exc:
                return ToolResult(name, False, str(exc), {'error': str(exc), 'state': exc.code,
                                  'outcome': ('unknown' if exc.code == 'outcome_unknown' else 'failed') if name == 'google_calendar.create' else None,
                                  'created': (None if exc.code == 'outcome_unknown' else False) if name == 'google_calendar.create' else None},
                                  error={'code': exc.code.upper(), 'message': str(exc), 'retryable': name != 'google_calendar.create' and exc.code in {'api_error', 'rate_limited'}})
        return handler
    rows = [
        ('google.accounts', 'List named Google account connections without a network request.', {}, ('google', 'accounts', 'connected')),
        ('gmail.search', 'Search mail in the default or explicitly selected Google account. Use all only for an explicit cross-account request. Returns IDs/snippets; partial errors are explicit.',
         {'account': str, 'query': str, 'limit': int}, ('gmail', 'email', 'inbox', 'unread', 'search', 'both')),
        ('gmail.read', 'Read one email body using its exact ID and named account from search; never sends or marks read.',
         {'account': str, 'id': str}, ('gmail', 'email', 'read', 'body', 'message')),
        ('google_calendar.list', 'List accessible Google calendar IDs for one named account.', {'account': str}, ('google', 'calendars', 'list')),
        ('google_calendar.agenda', 'Read Google events from the default or explicitly selected account. Use all only for an explicit cross-account request. UTC ordering, local display; read-only.',
         {'account': str, 'start_date': str, 'days': int, 'query': str, 'limit': int, 'availability_at': str,
          'availability_start': str, 'availability_end': str, 'time_min': str, 'time_max': str,
          'academic_concept': str, 'course': str, 'first_only': bool, 'temporal_source': str,
          'followup_context_used': bool}, ('google', 'calendar', 'agenda', 'events', 'schedule')),
        ('google_calendar.next', 'Read next future Google event with owner-local current time and minutes until start; compare available minutes with requested duration. Report partial failures.',
         {'account': str, 'days': int}, ('google', 'calendar', 'next', 'meeting', 'event', 'when')),
    ]
    contracts = {
        'google.accounts': {'accounts': 'array', 'state': 'string'},
        'gmail.search': {'messages': 'array', 'errors': 'array', 'partial': 'boolean',
                        'truncated': 'boolean', 'state': 'string'},
        'gmail.read': {'id': 'string', 'account': 'string', 'headers': 'object',
                      'body': 'object', 'attachments_downloaded': 'boolean', 'state': 'string'},
        'google_calendar.list': {'account': 'string', 'calendars': 'array',
                                 'truncated': 'boolean', 'state': 'string'},
        'google_calendar.agenda': {'events': 'array', 'errors': 'array', 'partial': 'boolean',
                                   'truncated': 'boolean', 'timezone': 'string', 'state': 'string'},
        'google_calendar.next': {'events': 'array', 'errors': 'array', 'partial': 'boolean',
                                 'truncated': 'boolean', 'current_local_time': 'string', 'state': 'string'},
    }
    definitions = [ToolDefinition(name, desc, 0, 0, schema, contracts[name], run(name),
                                  timeout_seconds=120, side_effect='read', retry_safe=True, tags=tags,
                                  prerequisites=('Owner connects Google accounts locally',))
                   for name, desc, schema, tags in rows]
    definitions.append(ToolDefinition(
        'google_calendar.create',
        "Create one Google Calendar event after HANNI resolves the owner's natural-language date/time to exact local values.",
        2, 2,
        {'account': str, 'calendar_id': str, 'summary': str, 'all_day': bool,
         'start': str, 'end': str, 'start_date': str, 'end_date': str, 'location': str, 'description': str},
        {'id': 'string', 'account': 'string', 'calendar_id': 'string',
         'summary': 'string', 'start': 'object', 'end': 'object',
         'created': 'boolean', 'outcome': 'string', 'state': 'string'},
        run('google_calendar.create'), timeout_seconds=120,
        side_effect='external_action', background_allowed=False,
        tags=('google', 'calendar', 'create', 'add', 'schedule', 'event', 'meeting', 'appointment'),
        aliases=('add to my calendar', 'schedule a meeting', 'create calendar event', 'book an appointment'),
        prerequisites=('Owner connects Google account with Calendar event write scope',),
        argument_constraints={'summary': {'required': True, 'nullable': False}, 'all_day': {'required': True, 'nullable': False}}
    ))
    return tuple(definitions)
