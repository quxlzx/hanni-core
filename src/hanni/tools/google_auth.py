"""Owner-run Google sign-in helpers; never exposed as model-callable tools."""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading

from hanni.tools.google_access import (
    ACCOUNTS, SCOPES, GoogleAccess, GoogleAccessError, WindowsTokenVault,
    validate_credentials,
)

from hanni.tools.google_identity import (account_label, account_labels, scopes_for, authorized,
    CAPABILITY_SCOPES, preferences, normalized_scopes, verified_scopes)

DEFAULT_CLIENT_FILENAME = "google-oauth-client.json"
GOOGLE_CLIENTS_URL = "https://console.cloud.google.com/auth/clients"

SIGN_IN_FAILURES = {
    'scope_mismatch': 'Google returned different service permissions. Retry and approve every selected service. If old permissions remain, revoke HANNI in your Google account and try again.',
    'sign_in_timeout': 'Google sign-in timed out. Start sign-in again and finish in the browser within three minutes.',
    'network_error': 'Google authorization returned, but HANNI could not contact Google to finish verification. Check your connection, proxy or work network and retry.',
    'invalid_client': 'Google rejected the Desktop app client. Import a current Desktop app client JSON from the same Google Cloud project and retry.',
    'invalid_grant': 'Google rejected the sign-in code. Start a fresh sign-in and complete it once; check that Windows date and time are correct.',
    'access_denied': 'Google sign-in was declined or blocked. Check consent, test-user access and any Workspace administrator restrictions.',
    'offline_access_missing': 'Google did not provide offline access. Revoke HANNI in your Google account, then sign in again and approve access.',
    'identity_unavailable': 'Google authorization returned, but HANNI could not verify the account email. Check your connection and try again.',
    'account_mismatch': 'The signed-in Google account does not match the saved account. Reconnect using the original email or add another account.',
    'account_exists': 'That Google email is already connected under another account name. Use the existing connection.',
    'credential_storage': 'Google sign-in succeeded, but HANNI could not save or verify the credentials in Windows Credential Manager. Check Windows credential-storage access and retry.',
    'account_changed': 'The saved account changed during sign-in. Refresh accounts and retry; the existing connection was retained.',
    'sign_in_failed': 'Google sign-in did not complete. Check the Desktop client, browser consent and network, then try again.',
}


def sign_in_failure(code):
    code = code if isinstance(code, str) and code in SIGN_IN_FAILURES else 'sign_in_failed'
    return GoogleAccessError(SIGN_IN_FAILURES[code], code)


def _flow_error(error):
    """Classify known failures without exposing provider bodies, codes or tokens."""
    from requests.exceptions import ConnectionError, Timeout
    if isinstance(error, (ConnectionError, Timeout)): return sign_in_failure('network_error')
    if isinstance(error, TimeoutError): return sign_in_failure('sign_in_timeout')
    code = getattr(error, 'error', None)
    return sign_in_failure(code if isinstance(code, str) and code in {'invalid_client', 'invalid_grant', 'access_denied'} else 'sign_in_failed')


def dependency_error() -> str | None:
    try:
        import google.oauth2.credentials  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
        import keyring  # noqa: F401
        import requests  # noqa: F401
    except ImportError:
        return ("Google support is not installed. Run HANNI setup again, or run: "
                'python -m pip install -e ".[google]"')
    return None


def default_client_secrets(config_dir: Path) -> Path:
    return Path(config_dir) / DEFAULT_CLIENT_FILENAME


def _client_config(path: Path) -> dict:
    if not path.is_file():
        raise GoogleAccessError(f"Google OAuth Desktop app client file was not found: {path}")
    if path.stat().st_size > 32000:
        raise GoogleAccessError("OAuth client file is unexpectedly large.")
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GoogleAccessError("The Google OAuth client file is not valid JSON.") from exc
    return validate_client_config(config)


def validate_client_config(config):
    """Validate an owner-imported Desktop client without accepting other endpoints."""
    installed = config.get("installed", {}) if isinstance(config, dict) else {}
    if (not isinstance(installed, dict)
            or installed.get("auth_uri") not in {"https://accounts.google.com/o/oauth2/auth", "https://accounts.google.com/o/oauth2/v2/auth"}
            or installed.get("token_uri") != "https://oauth2.googleapis.com/token"
            or not isinstance(installed.get("client_id"), str) or not 1 <= len(installed['client_id']) <= 1000
            or not isinstance(installed.get("client_secret"), str) or not 1 <= len(installed['client_secret']) <= 1000):
        raise GoogleAccessError("Use an official Google OAuth Desktop app client JSON file.")
    return config


def prepare_client_secrets(config_dir: Path, *, explicit: Path | None = None,
                           input_fn=input, open_url=None, output_fn=print) -> Path:
    """Import a downloaded Desktop client during the same login command.

    An OAuth client ID has to exist before Google can start a browser consent
    flow. HANNI intentionally does not borrow another application's client.
    """
    target = default_client_secrets(config_dir)
    if explicit is not None:
        path = Path(explicit).expanduser()
        _client_config(path)
        return path
    if target.is_file():
        _client_config(target)
        return target
    downloaded = []
    try:
        for candidate in (Path.home() / 'Downloads').glob('client_secret*.json'):
            try:
                _client_config(candidate)
            except GoogleAccessError:
                continue
            downloaded.append(candidate)
    except OSError:
        pass
    if len(downloaded) == 1:
        source = downloaded[0]
        output_fn('Found your downloaded Google OAuth Desktop client; importing it for HANNI.')
    else:
        source = None
    if open_url is None:
        import webbrowser
        open_url = webbrowser.open
    if source is None:
        output_fn("A Google OAuth Desktop app client is needed once. HANNI will guide you through it.")
        output_fn(f"HANNI will save it as: {target}")
        output_fn("In Google Cloud, enable the APIs you will use (Calendar, Gmail, Drive, Tasks), configure consent,")
        output_fn("then create a Desktop app OAuth client and download its JSON file.")
        output_fn(f"Opening: {GOOGLE_CLIENTS_URL}")
        open_url(GOOGLE_CLIENTS_URL)
        try:
            supplied = input_fn("Paste the path to the downloaded JSON file: ").strip().strip('"')
        except EOFError as exc:
            raise GoogleAccessError("No OAuth client was supplied. Run hanni google login in an interactive terminal after downloading the Desktop app JSON.") from exc
        if not supplied:
            raise GoogleAccessError("Google setup was cancelled. Run hanni google login when you have the Desktop app JSON file.")
        source = Path(supplied).expanduser()
    config = _client_config(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids overwriting a client installed by another process.
    try:
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(config, stream)
    except FileExistsError:
        _client_config(target)
        return target
    output_fn(f"Saved HANNI's Google client configuration to: {target}")
    return target


def connect(account, expected_email, client_secrets, *, calendar_ids=None,
            replace=False, vault=None, flow_factory=None, transport=None, scopes=None, progress=None):
    """Run browser OAuth, verify the selected account and scopes, then save the token."""
    vault = vault or WindowsTokenVault()
    account_label(account)
    if vault.get(account) is not None and not replace:
        raise GoogleAccessError("That account slot is already connected; use --replace to reconnect it explicitly.")
    email = str(expected_email or "").strip().casefold() or None
    if email is not None and ("@" not in email or len(email) > 254):
        raise GoogleAccessError("Provide a valid email address, or omit --email to choose it in Google sign-in.")
    calendars = list(dict.fromkeys(calendar_ids or ["primary"]))
    if not 1 <= len(calendars) <= 5 or not all(isinstance(c, str) and 0 < len(c) <= 500 for c in calendars):
        raise GoogleAccessError("Select 1..5 calendar IDs, each at most 500 characters.")
    path = Path(client_secrets).expanduser()
    config = _client_config(path)
    if flow_factory is None:
        missing = dependency_error()
        if missing:
            raise GoogleAccessError(missing)
        from hanni.tools.google_oauth_browser import BrowserGoogleFlow
        flow_factory = lambda config, scopes: BrowserGoogleFlow(config, scopes, threading.Event())
    requested_scopes = set(scopes_for(scopes))
    existing = vault.get(account)
    if existing and replace:
        validate_credentials(existing['credentials'])
        requested_scopes.update(existing['credentials']['scopes'])
    requested_scopes = normalized_scopes(requested_scopes)
    flow_args = dict(
        host="127.0.0.1", port=0, open_browser=True,
        authorization_prompt_message="Opening Google sign-in in your browser...",
        success_message="HANNI received authorization. You may close this tab.",
        timeout_seconds=180, access_type="offline", prompt="consent select_account",
    )
    if email:
        flow_args["login_hint"] = email
    try:
        flow = flow_factory(config, requested_scopes)
        credentials = flow.run_local_server(**flow_args)
        info = json.loads(credentials.to_json())
    except (GoogleAccessError, InterruptedError):
        raise
    except Exception as error:
        raise _flow_error(error) from None
    if progress: progress('verifying')
    granted = getattr(credentials, "granted_scopes", None)
    if granted is not None: verified_scopes(granted, requested_scopes)
    info['scopes'] = list(verified_scopes(info.get('scopes'), requested_scopes))
    validate_credentials(info)
    if not credentials.refresh_token:
        raise sign_in_failure('offline_access_missing')
    record = {"email": email or "pending", "credentials": info, "calendar_ids": calendars}
    class PendingVault:
        def get(self, label): return record if label == account else None
        def set(self, label, value): record.update(value)
    access = GoogleAccess(PendingVault(), transport=transport)
    if progress: progress('identity')
    try:
        profile = access._get(account, "/oauth2/v2/userinfo")
    except GoogleAccessError:
        raise sign_in_failure('identity_unavailable') from None
    actual = str(profile.get("email", "")).strip().casefold()
    if "@" not in actual:
        raise sign_in_failure('identity_unavailable')
    if email and actual != email:
        raise sign_in_failure('account_mismatch')
    for other in account_labels(vault):
        existing = vault.get(other) if other != account else None
        if existing and str(existing.get("email", "")).casefold() == actual:
            raise sign_in_failure('account_exists')
    record["email"] = actual
    # ID tokens are not used by HANNI; identity was verified through Google's
    # authenticated userinfo endpoint. Avoid storing this large redundant JWT.
    info.pop('id_token', None)
    record['credentials'].pop('id_token', None)
    if progress: progress('saving')
    try:
        vault.set(account, record)
        saved = vault.get(account)
        if saved != record: raise RuntimeError('Credential write could not be verified.')
    except InterruptedError:
        raise
    except GoogleAccessError as error:
        if error.code == 'account_changed': raise
        raise sign_in_failure('credential_storage') from None
    except Exception:
        raise sign_in_failure('credential_storage') from None
    return {"account": account, "email": actual, "calendar_ids": calendars,
            "connected": True, "calendar": authorized(info['scopes'], 'calendar.read'),
            "gmail": authorized(info['scopes'], 'gmail.read'),
            "services": [key for key in CAPABILITY_SCOPES if authorized(info['scopes'], key)]}


def status(*, vault=None, transport=None, verify=False):
    """Report grants separately from a current API health check; never expose secrets."""
    access = GoogleAccess(vault=vault, transport=transport)
    rows = access.accounts()
    probes = {'calendar': ('/calendar/v3/users/me/calendarList', {'maxResults': 1}),
              'gmail': ('/gmail/v1/users/me/profile', {}),
              'drive': ('/drive/v3/files', {'pageSize': 1, 'fields': 'files(id)'}),
              'docs': ('/drive/v3/files', {'pageSize': 1, 'fields': 'files(id)'}),
              'tasks': ('/tasks/v1/users/@me/lists', {'maxResults': 1})}
    for row in rows:
        row.update(gmail=False, calendar=False, services={}, token_health='not_connected',
                   last_successful_api_check=None)
        if not row['connected']:
            continue
        record = access._record(row['account'])
        scopes = record.get('credentials', {}).get('scopes', ())
        row['services'] = {name: {'read': authorized(scopes, name + '.read'),
                                  'write': name + '.write' in CAPABILITY_SCOPES and authorized(scopes, name + '.write')}
                           for name in probes}
        row['gmail'] = row['services']['gmail']['read']
        row['calendar'] = row['services']['calendar']['read']
        row['token_health'] = 'not_checked'
        row['last_successful_api_check'] = record.get('last_successful_api_check')
        row['preferences'] = preferences(access.vault)
        if verify:
            errors = []
            for name, (path, params) in probes.items():
                if not row['services'][name]['read']:
                    continue
                try:
                    access._get(row['account'], path, params)
                    row['services'][name]['api_status'] = 'verified'
                except GoogleAccessError as exc:
                    row['services'][name]['api_status'] = exc.code
                    errors.append(str(exc))
            row['token_health'] = 'verified' if not errors else 'check_failed'
            if errors: row['error'] = '; '.join(errors)
            row['last_successful_api_check'] = access._record(row['account']).get('last_successful_api_check')
    return rows


def logout(account="personal", *, vault=None):
    vault = vault or WindowsTokenVault()
    existed = vault.get(account) is not None
    vault.delete(account)
    return {"account": account, "connected": False, "local_connection_removed": existed}
