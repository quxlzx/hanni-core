"""Controlled dependencies for REAL adapters; no fabricated capability results."""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
import subprocess
from urllib.parse import unquote
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from hanni.tools.google_identity import GoogleAccessError, scopes_for


class GoogleVault:
    def __init__(self, grants=('calendar.read', 'calendar.write', 'gmail.read',
                               'drive.read', 'docs.read', 'tasks.read', 'tasks.write')):
        self.records = {'personal': {'email': 'owner@example.test',
            'calendar_ids': ['primary'], 'credentials': {
                'token_uri': 'https://oauth2.googleapis.com/token',
                'scopes': list(scopes_for(grants))}}}

    def get(self, label):
        return deepcopy(self.records.get(label))

    def labels(self):
        return tuple(self.records)

    def preferences(self):
        return {'default_google_account': 'personal'}


class GoogleProvider:
    """In-memory HTTP-boundary fixture with Google-shaped data and errors.

    The real GoogleAccess/GoogleServices adapters retain their argument parsing,
    account/scope checks, timezone normalization and result contracts. No socket,
    personal credential manager or live Google destination is accessed.
    """
    def __init__(self):
        now = datetime.now(ZoneInfo('America/New_York'))
        start = (now + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
        self.events = {'event-v36': {'id': 'event-v36', 'summary': 'V36 rehearsal',
             'start': {'dateTime': start.isoformat()},
             'end': {'dateTime': (start+timedelta(hours=1)).isoformat()},
             'status': 'confirmed', 'htmlLink': 'https://calendar.google.com/fixture/event-v36'}}
        self.calls = []
        self.fail = None
        self.tasks = {'task-v36': {'id': 'task-v36', 'title': 'V36 rehearsal', 'status': 'needsAction'}}
        self.document = {'id': 'doc-v36', 'name': 'Rehearsal notes',
            'mimeType': 'application/vnd.google-apps.document',
            'modifiedTime': now.isoformat(), 'owners': [{'displayName': 'Synthetic owner'}],
            'webViewLink': 'https://docs.google.com/document/d/doc-v36/edit'}
        text = base64.urlsafe_b64encode(b'V36 rehearsal starts tomorrow at 14:00.').decode()
        self.message = {'id': 'message-v36', 'threadId': 'thread-v36',
            'snippet': 'V36 rehearsal starts tomorrow at 14:00.',
            'internalDate': str(int(now.timestamp()*1000)),
            'payload': {'mimeType': 'text/plain', 'headers': [
                {'name': 'From', 'value': 'Fixture Sender <fixture@example.test>'},
                {'name': 'To', 'value': 'owner@example.test'},
                {'name': 'Subject', 'value': 'V36 rehearsal'},
                {'name': 'Date', 'value': now.isoformat()}], 'body': {'data': text}}}

    def __call__(self, account, path, params, body=None, *, method=None):
        method = method or ('POST' if body is not None else 'GET')
        self.calls.append({'account': account, 'path': path, 'params': deepcopy(params),
                           'body': deepcopy(body), 'method': method})
        if self.fail:
            raise GoogleAccessError('Controlled provider '+self.fail, self.fail)
        if account != 'personal':
            raise GoogleAccessError('Unknown controlled account', 'not_connected')
        if path == '/calendar/v3/users/me/calendarList':
            return {'items': [{'id': 'primary', 'summary': 'V36 controlled calendar',
                               'timeZone': 'America/New_York', 'accessRole': 'owner'}]}
        if path.startswith('/calendar/v3/calendars/'):
            leaf = path.split('/events', 1)
            if len(leaf) != 2:
                raise GoogleAccessError('Unknown calendar route', 'not_found')
            if not leaf[1]:
                if method == 'POST':
                    event_id = 'created-v36-'+str(len(self.events)+1)
                    self.events[event_id] = {**deepcopy(body), 'id': event_id,
                        'status': 'confirmed', 'htmlLink': 'https://calendar.google.com/fixture/'+event_id}
                    return deepcopy(self.events[event_id])
                values = list(self.events.values())
                start, end = params.get('timeMin'), params.get('timeMax')
                if start:
                    lower = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    values = [event for event in values if _event_date(event['end']) > lower]
                if end:
                    upper = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    values = [event for event in values if _event_date(event['start']) < upper]
                return {'items': deepcopy(values[:int(params.get('maxResults', 100))])}
            event_id = unquote(leaf[1].lstrip('/'))
            if event_id not in self.events:
                raise GoogleAccessError('Controlled event not found', 'not_found')
            if method == 'DELETE':
                del self.events[event_id]
                return {}
            if method == 'PATCH':
                self.events[event_id].update(deepcopy(body))
            return deepcopy(self.events[event_id])
        if path == '/gmail/v1/users/me/messages':
            return {'messages': [{'id': 'message-v36', 'threadId': 'thread-v36'}], 'resultSizeEstimate': 1}
        if path == '/gmail/v1/users/me/messages/message-v36':
            return deepcopy(self.message)
        if path == '/gmail/v1/users/me/threads/thread-v36':
            return {'id': 'thread-v36', 'messages': [deepcopy(self.message)]}
        if path == '/drive/v3/files':
            return {'files': [deepcopy(self.document)]}
        if path == '/drive/v3/files/doc-v36':
            return deepcopy(self.document)
        if path == '/drive/v3/files/doc-v36/export':
            return 'The synthetic cobalt lighthouse rehearsal is tomorrow at 14:00.'
        if path.startswith('/tasks/v1/lists/') and '/tasks' in path:
            leaf = path.rsplit('/tasks', 1)[1].lstrip('/')
            if not leaf:
                if method == 'POST':
                    key = 'created-task-v36-'+str(len(self.tasks)+1)
                    self.tasks[key] = {**deepcopy(body), 'id': key, 'status': 'needsAction'}
                    return deepcopy(self.tasks[key])
                return {'items': deepcopy(list(self.tasks.values()))}
            if leaf not in self.tasks:
                raise GoogleAccessError('Controlled task not found', 'not_found')
            if method == 'PATCH':
                self.tasks[leaf].update(deepcopy(body))
            return deepcopy(self.tasks[leaf])
        raise GoogleAccessError('Unsupported controlled provider route: '+path, 'not_found')


def _event_date(value):
    if value.get('dateTime'):
        return datetime.fromisoformat(value['dateTime'].replace('Z', '+00:00'))
    return datetime.fromisoformat(value['date']).replace(tzinfo=ZoneInfo('America/New_York'))


def prepare_files(output, controller_pid):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    folder = root / 'fixtures'
    folder.mkdir(exist_ok=True)
    (folder / 'empty').mkdir(exist_ok=True)
    (folder / 'nested').mkdir(exist_ok=True)
    (folder / 'sample.txt').write_text('cobalt lighthouse\nrehearsal is Friday\nfinal line\n', encoding='utf-8')
    (folder / 'other.txt').write_text('cobalt lighthouse\nrehearsal is Saturday\nfinal line\n', encoding='utf-8')
    (folder / 'nested/duplicate.txt').write_bytes((folder/'sample.txt').read_bytes())
    (folder / 'data.bin').write_bytes(b'\0'*8192)
    (folder / 'delete-me.txt').write_text('Disposable controlled fixture', encoding='utf-8')
    with ZipFile(root / 'fixture.zip', 'w') as archive:
        archive.write(folder / 'sample.txt', 'sample.txt')
    project = root / 'project'
    project.mkdir(exist_ok=True)
    (project / 'test_sample.py').write_text('def test_sample():\n    assert 2 + 3 == 5\n', encoding='utf-8')
    git = root / 'git-fixture'
    git.mkdir(exist_ok=True)
    if not (git/'.git').exists():
        subprocess.run(['git', 'init', '-q', str(git)], check=True)
        (git/'fixture.txt').write_text('Synthetic campaign repository\n', encoding='utf-8')
        subprocess.run(['git', '-C', str(git), 'add', 'fixture.txt'], check=True)
        subprocess.run(['git', '-C', str(git), '-c', 'user.name=V36 Fixture',
                        '-c', 'user.email=fixture@example.test', 'commit', '-q', '-m', 'Synthetic initial record'], check=True)
    (git/'fixture.txt').write_text('Synthetic campaign repository changed\n', encoding='utf-8')
    from hanni.tools.todos import TodoStore
    todo = TodoStore(root/'state').add({'title': 'V36 synthetic readback', 'due': 'tomorrow'})
    from hanni.tools.notes import definitions
    # Seed through the original handler, not by inventing a tool response.
    definition = next(d for d in definitions(root/'state') if d.name == 'note.append')
    definition.handler({'text': 'cobalt lighthouse rehearsal is Friday'}, None, None)
    fields = {'folder': folder, 'file': folder/'sample.txt', 'other': folder/'other.txt',
        'zip': root/'fixture.zip', 'extract': root/'extracted', 'newzip': root/'new.zip',
        'copy': folder/'copied.txt', 'moved': folder/'moved.txt', 'delete': folder/'delete-me.txt',
        'newfolder': folder/'new-folder', 'written': folder/'written.txt', 'git': git,
        'project': project, 'battery': root/'battery.html', 'pid': controller_pid, 'todo': todo['id']}
    return {key: str(value) for key, value in fields.items()}
