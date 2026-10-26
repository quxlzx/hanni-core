"""Owner-only Google account setup. Secrets never enter chat or tool arguments."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading
from uuid import uuid4

from hanni.dashboard.features import RequestLedger, request_id
from hanni.hermes.state import digest
from hanni.native.model_settings import atomic_json
from hanni.tools import google_auth
from hanni.tools.google_identity import account_label, account_labels, authorized, CAPABILITY_SCOPES, preferences


def account_revision(record):
    if record is None: return 'missing'
    info = record.get('credentials', {})
    return digest([record.get('email'), record.get('calendar_ids'),
                   *(info.get(key) for key in ('client_id', 'refresh_token', 'scopes'))])


class GoogleAccounts:
    def __init__(self, features, *, client_dir=None, flow_factory=None, transport=None):
        self.features = features
        self.client_path = (Path(client_dir or features.config.paths.config_dir) / google_auth.DEFAULT_CLIENT_FILENAME
                            if features.config else None)
        self.flow_factory, self.transport = flow_factory, transport
        self.lock = threading.RLock()
        self.ledger = RequestLedger()
        self.job = None
        self.thread = None
        self.closed = False

    @property
    def vault(self):
        return self.features.registry.google_access.vault

    def client_status(self):
        try:
            if not self.client_path or not self.client_path.exists():
                return {'ready': False, 'revision': 'missing'}
            if self.client_path.is_symlink(): raise ValueError('Client path is a symlink.')
            if self.client_path.stat().st_size > 32000: raise ValueError('Client file is too large.')
            raw = self.client_path.read_bytes()
            revision = hashlib.sha256(raw).hexdigest()
            google_auth.validate_client_config(json.loads(raw.decode('utf-8-sig')))
            return {'ready': True, 'revision': revision}
        except (OSError, ValueError, UnicodeError):
            return {'ready': False, 'revision': 'invalid'}

    def public_job(self):
        return ({key: self.job[key] for key in ('id', 'account', 'state', 'message', 'error_code') if key in self.job} if self.job else None)

    def snapshot(self):
        with self.lock:
            result = {'available': False, 'client': self.client_status(), 'accounts': [], 'job': self.public_job(),
                      'default_account': None, 'next_label': 'personal', 'reason': None}
            if not self.features.config:
                return {**result, 'reason': 'Google setup requires the local HANNI configuration.'}
            missing = google_auth.dependency_error()
            if missing: return {**result, 'reason': missing}
            try:
                vault = self.vault
                rows = []
                for label in account_labels(vault):
                    record = vault.get(label)
                    if not record: continue
                    scopes = record.get('credentials', {}).get('scopes', [])
                    google_auth.validate_credentials(record.get('credentials', {}))
                    rows.append({'account': label, 'email': record['email'], 'revision': account_revision(record),
                                 'services': [key for key in CAPABILITY_SCOPES if authorized(scopes, key)]})
                default = preferences(vault).get('default_google_account')
                if default not in {row['account'] for row in rows}:
                    default = next((row['account'] for row in rows if row['account'] == 'personal'), rows[0]['account'] if rows else None)
                next_label = 'personal'
                used = {row['account'] for row in rows}
                if next_label in used: next_label = 'work'
                suffix = 2
                while next_label in used:
                    next_label = f'account{suffix}'; suffix += 1
                return {**result, 'available': not self.closed, 'accounts': rows,
                        'default_account': default, 'next_label': next_label}
            except Exception:
                return {**result, 'reason': 'Google credential storage could not be read. Check Windows Credential Manager and reconnect the account.'}

    def execute(self, body):
        if set(body) != {'id', 'operation', 'data'} or not isinstance(body['data'], dict) or not isinstance(body['operation'], str):
            raise ValueError('Expected request ID, Google operation and data.')
        key = request_id(body['id'])
        return self.ledger.execute(key, body, lambda: self._mutate(body['operation'], body['data'], key))

    def _mutate(self, operation, data, key):
        with self.lock:
            if self.closed or not self.features.config:
                raise RuntimeError('Google setup is unavailable in this session.')
            if operation not in {'open_setup', 'import_client', 'connect', 'cancel', 'disconnect', 'default'}:
                raise ValueError('Choose a supported Google account action.')
            owner = self.features.registry.context.permissions.owner
            if owner.chat_only or owner.max_auto_approve_level < 0:
                raise RuntimeError('The owner profile blocks account setup changes.')
            if operation == 'cancel':
                if set(data) != {'attempt_id'} or not self.job or data['attempt_id'] != self.job['id']:
                    raise ValueError('Refresh the current sign-in attempt before canceling.')
                if self.thread and self.thread.is_alive() and not self.job['saved']:
                    self.job['cancel'].set()
                    self.job.update(state='cancelling', message='Cancelling Google sign-in…')
                return self.snapshot()
            if self.thread and self.thread.is_alive():
                raise RuntimeError('Finish or cancel the current Google sign-in first.')
            if operation == 'open_setup':
                if data: raise ValueError('Google setup accepts no browser address.')
                import webbrowser
                if not webbrowser.open(google_auth.GOOGLE_CLIENTS_URL, new=1, autoraise=True):
                    raise RuntimeError('Could not open the system browser. Open Google Cloud → Google Auth Platform → Clients manually.')
            elif operation == 'import_client':
                if set(data) != {'document', 'expected_revision'} or not isinstance(data['document'], str) or len(data['document'].encode()) > 32000:
                    raise ValueError('Choose a Google Desktop app JSON file smaller than 32 KB.')
                if data['expected_revision'] != self.client_status()['revision']:
                    raise ValueError('The OAuth client changed. Refresh before importing again.')
                config = google_auth.validate_client_config(json.loads(data['document'].lstrip('\ufeff')))
                config = {'installed': {key: config['installed'][key] for key in ('client_id', 'client_secret', 'auth_uri', 'token_uri')}}
                if self.client_path.is_symlink(): raise ValueError('The OAuth client path must not be a symlink.')
                atomic_json(self.client_path, config)
            else:
                if operation == 'connect':
                    expected = {'account', 'scopes', 'replace', 'expected_revision'}
                else: expected = {'account', 'expected_revision'}
                if set(data) != expected: raise ValueError('Choose the expected account fields.')
                account = account_label(data['account'])
                vault = self.vault
                record = vault.get(account)
                if account_revision(record) != data['expected_revision']:
                    raise ValueError('This account changed. Refresh before trying again.')
                if operation == 'connect':
                    if (type(data['replace']) is not bool or bool(record) != data['replace']
                            or not isinstance(data['scopes'], list) or not 1 <= len(data['scopes']) <= len(CAPABILITY_SCOPES)
                            or any(not isinstance(scope, str) or scope not in CAPABILITY_SCOPES for scope in data['scopes'])):
                        raise ValueError('Choose at least one supported service; use Reconnect for an existing account.')
                    if not self.client_status()['ready']:
                        raise ValueError('Import a Google OAuth Desktop app client JSON file first.')
                    self.job = {'id': key, 'account': account, 'state': 'waiting', 'message': 'Finish Google sign-in in your system browser.',
                                'cancel': threading.Event(), 'saved': False}
                    self.thread = threading.Thread(target=self._connect, args=(self.job, data, vault, record),
                                                   name='hanni-google-sign-in', daemon=True)
                    self.thread.start()
                elif operation == 'disconnect':
                    google_auth.logout(account, vault=vault)
                    if vault.get(account) is not None: raise RuntimeError('The account was not removed from credential storage.')
                else:
                    vault.set_preference(account)
            from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult
            definition = ToolDefinition('workspace.google_accounts', 'Explicit Google account setup.', 2, 2, {}, {}, lambda *_: None)
            args = {'operation': operation}
            self.features.registry.context.audit.write(definition,
                ToolRequest(definition.name, args, confirmed=True, source='desktop-google-setup', correlation_id=key), args,
                result=ToolResult(definition.name, True, 'Google account setup action accepted.'))
            return self.snapshot()

    def _connect(self, job, data, vault, previous):
        control = self
        class GuardedVault:
            def get(self, name): return vault.get(name)
            def labels(self): return account_labels(vault)
            def set(self, name, record):
                with control.lock:
                    if control.closed or job['cancel'].is_set(): raise InterruptedError('Sign-in cancelled.')
                    if account_revision(vault.get(name)) != data['expected_revision']:
                        raise google_auth.sign_in_failure('account_changed')
                    vault.set(name, record)
                    job['saved'] = True
        def progress(phase):
            messages = {'verifying': 'Google authorization received. Checking the selected permissions…',
                        'identity': 'Verifying your Google account email…',
                        'saving': 'Saving and checking the connection in Windows Credential Manager…'}
            with control.lock:
                if not job['cancel'].is_set() and not control.closed:
                    job['message'] = messages[phase]
        try:
            from hanni.tools.google_oauth_browser import BrowserGoogleFlow
            factory = self.flow_factory or (lambda config, scopes: BrowserGoogleFlow(config, scopes, job['cancel']))
            google_auth.connect(data['account'], previous['email'] if previous else None, self.client_path,
                calendar_ids=previous.get('calendar_ids', ['primary']) if previous else None,
                replace=data['replace'], scopes=data['scopes'], vault=GuardedVault(),
                flow_factory=factory, transport=self.transport, progress=progress)
            with self.lock:
                job.update(state='connected', message='Google account connected. You can use it in HANNI.')
        except Exception as error:
            with self.lock:
                cancelled = job['cancel'].is_set() or self.closed
                failure = google_auth.sign_in_failure(getattr(error, 'code', None))
                job.update(state='cancelled' if cancelled else 'failed', message='Google sign-in cancelled. No new credentials were saved.' if cancelled else
                           str(failure), error_code='cancelled' if cancelled else failure.code)

    def close(self):
        with self.lock:
            self.closed = True
            if self.job and not self.job['saved']: self.job['cancel'].set()
        if self.thread: self.thread.join(timeout=2)
