"""Bounded Drive, Docs and Tasks adapters and canonical Google capabilities."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from urllib.parse import quote, urlsplit

from .base import ToolDefinition, ToolResult
from .google_access import GoogleAccess, GoogleAccessError, _text, _limit, _message_id
from .email_provider import EmailProviderError

DOC_MIME = 'application/vnd.google-apps.document'
FILE_FIELDS = 'id,name,mimeType,modifiedTime,owners(displayName,emailAddress),webViewLink'
NOT_IMPLEMENTED = {
    'google.gmail.send': 'The assistant session has no reviewed-message confirmation flow; sending and replies remain disabled.',
    'google.gmail.reply': 'Replies require a reviewed-message confirmation flow, which is not implemented.',
    'google.gmail.delete': 'Mailbox mutations are disabled by the existing email policy.',
    'google.gmail.archive': 'Mailbox mutations are disabled by the existing email policy.',
    'google.drive.delete': 'Drive deletion is not implemented in this read-first integration.',
    'google.drive.share': 'Sharing changes are not implemented.',
    'google.docs.write': 'Document editing is not implemented.',
}


def object_id(value):
    return _message_id(value)


def file_row(row, account):
    file_id = object_id(row.get('id'))
    link = str(row.get('webViewLink') or '')
    url = urlsplit(link)
    if url.scheme != 'https' or url.hostname not in {'drive.google.com', 'docs.google.com'}:
        link = 'https://drive.google.com/file/d/' + file_id + '/view'
    return {'id': file_id, 'name': _text(row.get('name'), 300),
            'type': _text(row.get('mimeType'), 150), 'modified_time': _text(row.get('modifiedTime'), 60),
            'account': account, 'owners': [{'name': _text(owner.get('displayName'), 200),
                                           'email': _text(owner.get('emailAddress'), 254)}
                                         for owner in row.get('owners', [])[:5]], 'web_url': link}


class GoogleServices:
    def __init__(self, access):
        self.access = access

    def drive(self, args, operation):
        account = self.access.resolve_account(args.get('account'), 'docs' if args.get('docs_only') else 'drive')
        limit = _limit(args.get('limit'))
        if operation == 'metadata':
            file_id = object_id(args.get('id'))
            raw = self.access._get(account, '/drive/v3/files/' + file_id, {'fields': FILE_FIELDS})
            if raw.get('id') != file_id: raise GoogleAccessError('Google returned a different file than requested.')
            rows, truncated = [raw], False
        else:
            query = args.get('query') or ''
            if not isinstance(query, str) or len(query) > 300:
                raise GoogleAccessError('Drive search text must be at most 300 characters.', 'invalid_arguments')
            clauses = ["trashed = false", "mimeType != 'application/vnd.google-apps.folder'"]
            if query:
                escaped = query.replace('\\', '\\\\').replace("'", "\\'")
                clauses.append("(name contains '" + escaped + "' or fullText contains '" + escaped + "')")
            if args.get('docs_only'):
                clauses.append("mimeType = '" + DOC_MIME + "'")
            raw = self.access._get(account, '/drive/v3/files',
                {'q': ' and '.join(clauses), 'pageSize': limit, 'spaces': 'drive',
                 'orderBy': 'modifiedTime desc', 'fields': 'nextPageToken,files(' + FILE_FIELDS + ')'})
            rows, truncated = raw.get('files', []), bool(raw.get('nextPageToken'))
        files = [file_row(row, account) for row in rows[:limit]]
        return {'files': files, 'account': account, 'truncated': truncated,
                'state': 'partial' if truncated else 'verified' if files else 'not_found'}

    def docs_read(self, args):
        account = self.access.resolve_account(args.get('account'), 'docs')
        if not args.get('id'):
            if not args.get('query'):
                raise GoogleAccessError('Provide a document ID or a document search phrase.', 'invalid_arguments')
            matches = self.drive({'account': account, 'query': args['query'], 'docs_only': True, 'limit': 10}, 'search')
            if len(matches['files']) != 1 or matches['truncated']:
                return {**matches, 'needs_selection': bool(matches['files'])}
            file_id = matches['files'][0]['id']
        else:
            file_id = object_id(args.get('id'))
        metadata = self.drive({'account': account, 'id': file_id}, 'metadata')['files'][0]
        if metadata['type'] != DOC_MIME:
            raise GoogleAccessError('Content reading currently supports native Google Docs only.', 'not_implemented')
        content = self.access._request(account, '/drive/v3/files/' + file_id + '/export',
                                       params={'mimeType': 'text/plain'}, text_response=True)
        if not isinstance(content, str): raise GoogleAccessError('Google returned invalid document content.')
        return {'files': [metadata], 'account': account, 'content': _text(content, 6000),
                'truncated': len(content) > 6000, 'state': 'partial' if len(content) > 6000 else 'verified'}

    def tasks(self, args, operation):
        account = self.access.resolve_account(args.get('account'), 'tasks')
        tasklist = args.get('tasklist_id') or '@default'
        if tasklist != '@default': object_id(tasklist)
        path = '/tasks/v1/lists/' + quote(tasklist, safe='') + '/tasks'
        if operation == 'list':
            raw = self.access._get(account, path, {'maxResults': _limit(args.get('limit')),
                'showCompleted': 'false', 'showHidden': 'false', 'showDeleted': 'false'})
            rows = raw.get('items', [])
            truncated = bool(raw.get('nextPageToken'))
        elif operation == 'create':
            title = _text(args.get('title'), 500).strip()
            if not title: raise GoogleAccessError('A Google task title is required.', 'invalid_arguments')
            raw = self.access._post(account, path, {'title': title})
            rows, truncated = [raw], False
        else:
            task_id = object_id(args.get('id'))
            raw = self.access._get(account, path + '/' + task_id)
            if raw.get('id') != task_id: raise GoogleAccessError('Google did not verify the source task.')
            raw = self.access._request(account, path + '/' + task_id, method='PATCH', body={'status': 'completed'})
            if raw.get('status') != 'completed': raise GoogleAccessError('Google did not confirm task completion.')
            rows, truncated = [raw], False
        tasks = [{'id': object_id(row.get('id')), 'title': _text(row.get('title'), 500),
                  'status': _text(row.get('status'), 40), 'due': _text(row.get('due'), 60),
                  'account': account, 'tasklist_id': tasklist} for row in rows[:30]]
        return {'tasks': tasks, 'provider': 'google', 'account': account, 'tasklist_id': tasklist,
                'truncated': truncated, 'state': 'partial' if truncated else 'verified' if tasks else 'not_found'}

    def calendar_item(self, args, operation):
        account = self.access.resolve_account(args.get('account'), 'calendar')
        calendar = args.get('calendar_id') or 'primary'
        if not isinstance(calendar, str) or not calendar or len(calendar) > 500:
            raise GoogleAccessError('An exact calendar ID is required.', 'invalid_arguments')
        if calendar not in self.access._record(account).get('calendar_ids', ['primary']):
            raise GoogleAccessError('Select this calendar during Google login before changing it.', 'permission_denied')
        event_id = object_id(args.get('id'))
        path = '/calendar/v3/calendars/' + quote(calendar, safe='') + '/events/' + event_id
        source = self.access._get(account, path)
        if source.get('id') != event_id: raise GoogleAccessError('Google did not verify the source event.')
        if operation == 'read':
            return {'events': [{'id': event_id, 'account': account, 'calendar_id': calendar,
                    'summary': _text(source.get('summary'), 300), 'start': source.get('start'),
                    'end': source.get('end'), 'description': _text(source.get('description'), 1500)}],
                    'account': account, 'calendar_id': calendar, 'state': 'verified'}
        if operation == 'delete':
            self.access._request(account, path, method='DELETE')
            return {'id': event_id, 'account': account, 'calendar_id': calendar, 'deleted': True, 'state': 'verified'}
        body = {}
        if args.get('summary'): body['summary'] = _text(args['summary'], 300)
        if args.get('start') or args.get('end'):
            try:
                start, end = (datetime.fromisoformat(args[key]) for key in ('start', 'end'))
                if start.tzinfo is None or end.tzinfo is None or end <= start: raise ValueError()
            except (KeyError, ValueError, TypeError):
                raise GoogleAccessError('Updating time requires exact, timezone-aware start and end timestamps.', 'invalid_arguments') from None
            body.update(start={'dateTime': start.isoformat()}, end={'dateTime': end.isoformat()})
        if not body: raise GoogleAccessError('Provide a new summary or exact start and end.', 'invalid_arguments')
        raw = self.access._request(account, path, method='PATCH', body=body)
        if raw.get('id') != event_id: raise GoogleAccessError('Google did not confirm the event update.')
        return {'id': event_id, 'account': account, 'calendar_id': calendar, 'updated': True,
                'summary': _text(raw.get('summary'), 300), 'start': raw.get('start'), 'end': raw.get('end'), 'state': 'verified'}


def definitions(access=None):
    access = access or GoogleAccess()
    services = GoogleServices(access)
    def run(name, operation):
        def handler(args, context, request):
            try:
                if name.startswith('google.drive.'): data = services.drive(args, operation)
                elif name == 'google.docs.read': data = services.docs_read(args)
                elif name.startswith('google.tasks.'): data = services.tasks(args, operation)
                elif name.startswith('google.calendar.'): data = services.calendar_item(args, operation)
                elif name == 'google.gmail.thread':
                    from .email_provider import GmailEmailProvider
                    account = access.resolve_account(args.get('account'), 'gmail')
                    rows = GmailEmailProvider(access).thread(account, object_id(args.get('id')))
                    data = {'messages': [row.to_dict() for row in rows], 'account': account, 'state': 'verified'}
                else:
                    data = access.mail_search({**args, 'query': args.get('query') or 'in:inbox'})
                    for row in data['messages']: row.pop('snippet', None)
                    data['state'] = 'partial' if data.get('partial') or data.get('truncated') else 'verified' if data['messages'] else 'not_found'
                rows = data.get('files') or data.get('tasks') or data.get('events') or data.get('messages') or []
                message = ' '.join(f"{i}. {_text(row.get('name') or row.get('title') or row.get('summary') or row.get('subject'), 300)}" for i, row in enumerate(rows[:10], 1))
                if 'content' in data: message = 'Read the Google Doc; its text is in content.' if data['content'] else 'This Google Doc is empty.'
                if data.get('needs_selection'): message += ' Which result number should I read?'
                if name == 'google.drive.metadata' and rows:
                    message += ' ' + rows[0]['web_url']
                if operation in {'create', 'complete', 'update', 'delete'}:
                    message = {'create': 'Created the Google task.', 'complete': 'Marked the Google task complete.',
                               'update': 'Updated the Google Calendar event.', 'delete': 'Deleted the Google Calendar event.'}[operation]
                if data.get('errors'): message = 'Google lookup was incomplete. ' + message
                elif not message: message = 'No matching Google items were returned.'
                if data.get('truncated'): message += ' This result is incomplete; narrow the request for more detail.'
                return ToolResult(name, not bool(data.get('errors')), message, data)
            except GoogleAccessError as exc:
                return ToolResult(name, False, str(exc), {'state': exc.code}, error={'code': exc.code.upper(), 'message': str(exc), 'retryable': exc.code in {'api_error', 'rate_limited'}})
            except EmailProviderError as exc:
                state = {'AUTH_EXPIRED': 'not_connected', 'EMAIL_NOT_CONNECTED': 'not_connected',
                         'PERMISSION_DENIED': 'permission_denied', 'RATE_LIMITED': 'rate_limited'}.get(exc.code, 'api_error')
                return ToolResult(name, False, str(exc), {'state': state}, error={'code': state.upper(), 'message': str(exc), 'retryable': state in {'api_error', 'rate_limited'}})
            except (ValueError, TypeError, KeyError, AttributeError):
                message = 'Google returned an invalid response; this request could not be verified.'
                return ToolResult(name, False, message, {'state': 'api_error'}, error={'code': 'API_ERROR', 'message': message, 'retryable': True})
        return handler
    specs = [
        ('google.drive.search', 'Search Google Drive file names and indexed text; return metadata without downloading content.', {'account': str, 'query': str, 'limit': int, 'docs_only': bool}),
        ('google.drive.list', 'List Google Drive files, newest modified first; metadata only.', {'account': str, 'limit': int, 'docs_only': bool}),
        ('google.drive.recent', 'List recently modified Google Drive files or Google Docs; metadata only.', {'account': str, 'limit': int, 'docs_only': bool}),
        ('google.drive.metadata', 'Read metadata and web URL for an exact Google Drive file ID from prior results.', {'account': str, 'id': str}),
        ('google.docs.read', 'Read native Google Docs text using an exact Drive file ID or a uniquely matched search phrase. Multiple matches require selection.', {'account': str, 'id': str, 'query': str}),
        ('google.tasks.list', 'List incomplete Google Tasks in one task list; separate from local HANNI todos.', {'account': str, 'tasklist_id': str, 'limit': int}),
        ('google.tasks.create', 'Create one explicitly requested Google task.', {'account': str, 'tasklist_id': str, 'title': str}),
        ('google.tasks.complete', 'Mark a verified Google task ID complete after confirmation.', {'account': str, 'tasklist_id': str, 'id': str}),
        ('google.calendar.read', 'Read one exact Google Calendar event ID from prior results.', {'account': str, 'calendar_id': str, 'id': str}),
        ('google.calendar.update', 'Update one verified Google Calendar event ID after confirmation.', {'account': str, 'calendar_id': str, 'id': str, 'summary': str, 'start': str, 'end': str}),
        ('google.calendar.delete', 'Delete one verified Google Calendar event ID after confirmation.', {'account': str, 'calendar_id': str, 'id': str}),
        ('google.gmail.recent', 'Read recent Gmail sender, subject and received-time metadata; no message body.', {'account': str, 'limit': int}),
        ('google.gmail.search', 'Search Gmail and return sender, subject and received-time metadata; no message body.', {'account': str, 'query': str, 'limit': int}),
        ('google.gmail.thread', 'Read messages in an exact verified Gmail thread ID.', {'account': str, 'id': str}),
    ]
    result = []
    for name, description, schema in specs:
        operation = name.rsplit('.', 1)[1]
        write = operation in {'create', 'complete', 'update', 'delete'}
        confirm = operation in {'complete', 'update', 'delete'}
        if name.startswith('google.drive.') or name == 'google.docs.read':
            contract = {'files': 'array', 'account': 'string', 'truncated': 'boolean', 'state': 'string'}
        elif name.startswith('google.tasks.'):
            contract = {'tasks': 'array', 'account': 'string', 'tasklist_id': 'string',
                        'provider': 'string', 'truncated': 'boolean', 'state': 'string'}
        elif name == 'google.calendar.read':
            contract = {'events': 'array', 'account': 'string', 'calendar_id': 'string', 'state': 'string'}
        elif name.startswith('google.calendar.'):
            contract = {'id': 'string', 'account': 'string', 'calendar_id': 'string', 'state': 'string',
                        'deleted' if operation == 'delete' else 'updated': 'boolean'}
        elif name == 'google.gmail.thread':
            contract = {'messages': 'array', 'account': 'string', 'state': 'string'}
        else:
            contract = {'messages': 'array', 'errors': 'array', 'partial': 'boolean',
                        'truncated': 'boolean', 'state': 'string'}
        result.append(ToolDefinition(name, description, 2 if write else 0, 3 if operation == 'delete' else 2 if write else 0,
            schema, contract, run(name, operation), timeout_seconds=120,
            side_effect='destructive' if operation == 'delete' else 'external_action' if write else 'read',
            requires_confirmation_if=(lambda args: 'Review the exact Google item and changes before confirming.') if confirm else None,
            background_allowed=not write, tags=tuple(name.split('.')), prerequisites=('Google OAuth for this service',)))
    # Preserve legacy IDs for existing integrations while offering canonical names.
    from .google_access import definitions as legacy_definitions
    aliases = {'google_calendar.agenda': ('google.calendar.events', 'google.calendar.availability'),
               'google_calendar.next': ('google.calendar.next',), 'google_calendar.create': ('google.calendar.create',),
               'google_calendar.list': ('google.calendar.list_calendars',), 'gmail.read': ('google.gmail.read',)}
    for definition in legacy_definitions(access):
        for alias in aliases.get(definition.name, ()):
            def forward(args, context, request, original=definition, name=alias):
                if name == 'google.calendar.availability' and not any(args.get(key) for key in ('availability_at', 'availability_start')):
                    return ToolResult(name, False, 'Specify a resolved time or interval for availability.', {'state': 'invalid_arguments'}, error={'code': 'INVALID_ARGUMENTS', 'retryable': False})
                response = original.handler(args, context, request)
                return replace(response, name=name)
            result.append(replace(definition, name=alias, handler=forward))
    return tuple(result)
