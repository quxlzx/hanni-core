"""Owner-only guided Teams tab and Microsoft Graph account setup."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import threading
import time

from hanni.dashboard.features import RequestLedger, request_id
from hanni.tools.teams_access import TeamsError, SCOPES
from hanni.native.model_settings import atomic_json


class TeamsControls:
    def __init__(self, server, *, origin='https://localhost:8313'):
        self.server = server
        self.root = Path(server.features.root) / 'teams' if server.features.root else None
        self.lock = threading.RLock()
        self.ledger = RequestLedger()
        self.gateway = self.gateway_thread = self.auth_thread = self.job = None
        self.closed = False
        self.origin = origin

    @property
    def access(self):
        return self.server.features.registry.teams_access

    def certificate_status(self):
        result = {'ready': False, 'trusted': False, 'expires': None}
        if not self.root: return result
        cert = self.root / 'tls/localhost.pem'
        if not cert.is_file() or not (self.root / 'tls/localhost.key').is_file(): return result
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives.serialization import Encoding
            certificate = x509.load_pem_x509_certificate(cert.read_bytes())
            result.update(ready=certificate.not_valid_after_utc > datetime.now(timezone.utc),
                          expires=certificate.not_valid_after_utc.isoformat())
            if os.name == 'nt':
                der = certificate.public_bytes(Encoding.DER)
                result['trusted'] = any(raw == der for raw, encoding, trust in ssl.enum_certificates('ROOT'))
        except (ImportError, OSError, ValueError): pass
        return result

    def snapshot(self):
        with self.lock:
            config = profile = None
            reason = None
            available = bool(self.root and not self.closed)
            if available:
                try:
                    config = self.access.config()
                    record = self.access.vault.get() if config else None
                    profile = record.get('profile') if record else None
                except Exception:
                    reason = 'Teams credentials could not be read. Check Windows Credential Manager or disconnect and reconnect.'
            gateway = self.gateway
            pairing_ready = bool(gateway and gateway.pairing_expires > time.monotonic())
            return {'available': available, 'reason': reason,
                'tab': {'running': gateway is not None, 'url': self.origin + '/?host=teams',
                        'package_ready': bool(self.root and (self.root / 'HANNI-Teams.zip').is_file()),
                        'certificate': self.certificate_status(), 'pairing_ready': pairing_ready},
                'account': {'configured': bool(config), 'client_id': config['client_id'] if config else '',
                            'tenant': config['tenant'] if config else 'organizations', 'profile': profile,
                            'scopes': list(SCOPES)},
                'job': ({key: self.job.get(key) for key in ('id', 'state', 'message', 'user_code', 'expires_at')} if self.job else None)}

    def execute(self, body):
        if set(body) != {'id', 'operation', 'data'} or not isinstance(body['data'], dict) or not isinstance(body['operation'], str):
            raise ValueError('Expected a request ID, Teams operation and data.')
        key = request_id(body['id'])
        def perform():
            result = self._execute(body['operation'], body['data'], key)
            from hanni.tools.base import ToolDefinition, ToolRequest, ToolResult
            definition = ToolDefinition('teams.desktop_setup', 'Owner used Teams integration settings.',
                2, 2, {'operation': str}, {}, lambda *_: None, side_effect='reversible_write')
            arguments = {'operation': body['operation']}
            self.server.features.registry.context.audit.write(definition,
                ToolRequest(definition.name, arguments, confirmed=True, source='desktop-settings', correlation_id=key),
                arguments, result=ToolResult(definition.name, True, 'Teams integration setting completed.'))
            return result
        return self.ledger.execute(key, body, perform)

    def _execute(self, operation, data, key):
        with self.lock:
            if not self.root or self.closed: raise RuntimeError('Teams integration requires the local HANNI configuration.')
            owner = self.server.features.registry.context.permissions.owner
            if owner.chat_only or owner.max_auto_approve_level < 0: raise RuntimeError('The owner profile blocks integration setup changes.')
            allowed = {'prepare', 'download', 'show_package', 'open_registration', 'open_signin', 'trust', 'start', 'stop', 'pair', 'configure', 'connect', 'cancel', 'disconnect', 'check'}
            if operation not in allowed: raise ValueError('Choose a supported Teams action.')
            if operation != 'configure' and data: raise ValueError('This Teams action takes no additional fields.')
            if operation == 'configure':
                if self.auth_thread and self.auth_thread.is_alive(): raise RuntimeError('Cancel sign-in before changing the Microsoft application.')
                config = self.access.validate_config(data)
                with self.access.lock:
                    previous = self.access.config()
                    if previous != config:
                        if previous and self.access.vault.get():
                            raise ValueError('Disconnect the Teams account before changing its Microsoft app settings.')
                        self.access.vault.delete()
                        atomic_json(self.access.path, config)
            elif operation == 'prepare':
                if self.gateway: raise RuntimeError('Stop the Teams tab before rebuilding its certificate and package.')
                from hanni.teams.package import build_package, local_certificate
                build_package(self.origin, self.root / 'HANNI-Teams.zip')
                local_certificate(self.root / 'tls')
            elif operation == 'download':
                path = self.root / 'HANNI-Teams.zip'
                if not path.is_file(): raise ValueError('Prepare the Teams app first.')
                if path.stat().st_size > 1_000_000: raise ValueError('The Teams package is unexpectedly large. Prepare it again.')
                return {'package': base64.b64encode(path.read_bytes()).decode('ascii')}
            elif operation == 'show_package':
                if os.name != 'nt': raise ValueError('Use Download Teams app to save the package on this platform.')
                path = self.root / 'HANNI-Teams.zip'
                if not path.is_file(): raise ValueError('Prepare the Teams app first.')
                subprocess.Popen(['explorer.exe', '/select,', str(path.resolve())],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW)
            elif operation in {'open_registration', 'open_signin'}:
                import webbrowser
                if operation == 'open_signin':
                    if not self.job or self.job['state'] != 'waiting' or not self.job.get('user_code'):
                        raise ValueError('Start Microsoft sign-in to get a code first.')
                    url = 'https://microsoft.com/devicelogin'
                else:
                    url = 'https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade'
                if not webbrowser.open(url, new=1, autoraise=True):
                    raise RuntimeError('Could not open the system browser. Open Microsoft Entra or microsoft.com/devicelogin manually.')
            elif operation == 'trust':
                if os.name != 'nt': raise ValueError('Local certificate trust is supported on Windows. See the Teams setup guide for other platforms.')
                if not self.certificate_status()['ready']: raise ValueError('Prepare the Teams app first to create a valid local certificate.')
                result = subprocess.run(['certutil.exe', '-user', '-addstore', 'Root', str(self.root / 'tls/localhost.pem')],
                    capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode or not self.certificate_status()['trusted']:
                    raise RuntimeError('Windows did not trust the local certificate. Check your organization’s certificate policy, then retry.')
            elif operation == 'start':
                if not self.gateway:
                    if not self.certificate_status()['ready']: raise ValueError('Prepare the Teams app before starting the tab.')
                    from hanni.teams.server import TeamsServer
                    try:
                        gateway = TeamsServer(self.origin, f'http://127.0.0.1:{self.server.server_port}',
                            self.root / 'tls/localhost.pem', self.root / 'tls/localhost.key')
                    except OSError:
                        raise RuntimeError('Port 8313 is already in use. If START_TEAMS is running, close that launcher and retry. HANNI will not stop another process.') from None
                    self.gateway = gateway
                    self.gateway_thread = threading.Thread(target=gateway.serve_forever, name='hanni-teams-tab', daemon=True)
                    self.gateway_thread.start()
            elif operation == 'stop': self._stop_gateway()
            elif operation == 'pair':
                if not self.gateway: raise ValueError('Start the Teams tab first.')
                with self.gateway.lock:
                    self.gateway.pairing_code = secrets.token_urlsafe(24)
                    self.gateway.pairing_expires = time.monotonic() + 900
                    self.gateway.failed_pairings = 0
                    return {'pairing_code': self.gateway.pairing_code, 'expires_at': time.time() + 900}
            elif operation == 'connect':
                if self.auth_thread and self.auth_thread.is_alive(): raise RuntimeError('A Microsoft sign-in is already running.')
                config = self.access.config()
                if not config: raise ValueError('Save your Microsoft app registration first.')
                self.job = {'id': key, 'state': 'starting', 'message': 'Requesting a Microsoft sign-in code…', 'cancel': threading.Event()}
                self.auth_thread = threading.Thread(target=self._sign_in, args=(self.job, config), daemon=True, name='hanni-teams-sign-in')
                self.auth_thread.start()
            elif operation == 'cancel':
                if self.job:
                    self.job['cancel'].set()
                    self.job.update(state='cancelled', message='Microsoft sign-in cancelled.', user_code=None)
            elif operation == 'disconnect':
                if self.job: self.job['cancel'].set()
                with self.access.lock: self.access.vault.delete()
                self.job = None
            elif operation == 'check':
                profile = self.access.profile()
                self.access.get('/me/chats', {'$top': 1})
                self.access.get('/me/joinedTeams')
                with self.access.lock:
                    record = self.access.vault.get(); record['profile'] = profile; self.access.vault.set(record)
                return {**self.snapshot(), 'notice': 'Account, chats and joined teams verified. Channel access is checked when a channel is read.'}
            return self.snapshot()

    def _sign_in(self, job, config):
        try:
            status, flow = self.access.oauth('devicecode', {'scope': ' '.join((*SCOPES, 'offline_access'))}, config)
            if status != 200 or not isinstance(flow.get('device_code'), str) or not isinstance(flow.get('user_code'), str):
                raise TeamsError('Microsoft could not start sign-in. Check the client ID, tenant, and “Allow public client flows” in the app registration.')
            interval = max(5, min(int(flow.get('interval', 5)), 60))
            expires = time.monotonic() + min(max(int(flow.get('expires_in', 900)), 0), 900)
            with self.lock:
                if job['cancel'].is_set() or self.closed: return
                job.update(state='waiting', user_code=flow['user_code'][:40], expires_at=time.time() + expires - time.monotonic(),
                           message='Open Microsoft sign-in, enter this code, then approve the listed read permissions.')
            while not job['cancel'].wait(interval):
                if time.monotonic() >= expires: raise TeamsError('Microsoft sign-in expired. Select Sign in to try again.')
                status, data = self.access.oauth('token', {'grant_type': 'urn:ietf:params:oauth:grant-type:device_code', 'device_code': flow['device_code']}, config)
                if status == 200:
                    record = self.access.token_record(data)
                    record['profile'] = self.access.profile(record['access_token'])
                    with self.lock:
                        if job['cancel'].is_set() or self.closed: return
                        with self.access.lock: self.access.vault.set(record)
                        job.update(state='connected', message='Microsoft Teams account connected with read-only permissions.', user_code=None)
                    return
                error = data.get('error')
                if error == 'authorization_pending': continue
                if error == 'slow_down': interval += 5; continue
                if error == 'authorization_declined': raise TeamsError('Microsoft sign-in was declined. No connection was saved.')
                raise TeamsError('Microsoft sign-in failed or your organization blocked access. Check delegated permissions and administrator consent, then retry.')
        except Exception as exc:
            with self.lock:
                if not job['cancel'].is_set() and not self.closed:
                    job.update(state='failed', message=str(exc) if isinstance(exc, TeamsError) else 'Microsoft sign-in could not finish. Check the connection and Windows credential storage, then retry.', user_code=None)

    def _stop_gateway(self):
        if self.gateway:
            self.gateway.shutdown(); self.gateway.server_close()
            if self.gateway_thread: self.gateway_thread.join(3)
            self.gateway = self.gateway_thread = None

    def close(self):
        with self.lock:
            self.closed = True
            if self.job: self.job['cancel'].set()
            self._stop_gateway()
