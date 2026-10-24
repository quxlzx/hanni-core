"""Owner-run Google sign-in helpers; never exposed as model-callable tools."""
from __future__ import annotations

import json
import os
from pathlib import Path

from hanni.tools.google_access import (
    ACCOUNTS, SCOPES, GoogleAccess, GoogleAccessError, WindowsTokenVault,
    validate_credentials,
)

from hanni.tools.google_identity import account_label, account_labels, scopes_for, authorized, CAPABILITY_SCOPES, preferences

DEFAULT_CLIENT_FILENAME = "google-oauth-client.json"
GOOGLE_CLIENTS_URL = "https://console.cloud.google.com/auth/clients"


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
            replace=False, vault=None, flow_factory=None, transport=None, scopes=None):
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
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow_factory = InstalledAppFlow.from_client_config
    requested_scopes = set(scopes_for(scopes))
    existing = vault.get(account)
    if existing and replace:
        validate_credentials(existing['credentials'])
        requested_scopes.update(existing['credentials']['scopes'])
    requested_scopes = tuple(sorted(requested_scopes))
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
    except Exception:
        raise GoogleAccessError('Google sign-in did not finish. Check the Desktop client, consent screen, browser and network; retry login.', 'not_connected') from None
    granted = getattr(credentials, "granted_scopes", None)
    if granted is not None and set(granted) != set(requested_scopes):
        raise GoogleAccessError("Approve the requested service scopes; broader or partial grants are not accepted.")
    validate_credentials(info)
    if set(info['scopes']) != set(requested_scopes):
        raise GoogleAccessError('The granted service scopes differ from the request; nothing was saved.')
    if not credentials.refresh_token:
        raise GoogleAccessError("Google did not provide offline access; reconnect with consent.")
    record = {"email": email or "pending", "credentials": info, "calendar_ids": calendars}
    class PendingVault:
        def get(self, label): return record if label == account else None
        def set(self, label, value): record.update(value)
    access = GoogleAccess(PendingVault(), transport=transport)
    profile = access._get(account, "/oauth2/v2/userinfo")
    actual = str(profile.get("email", "")).strip().casefold()
    if "@" not in actual:
        raise GoogleAccessError("Google sign-in succeeded, but Google did not return an account address. Nothing was saved.")
    if email and actual != email:
        raise GoogleAccessError("The signed-in address does not match --email. Nothing was saved; select the intended account.")
    for other in account_labels(vault):
        existing = vault.get(other) if other != account else None
        if existing and str(existing.get("email", "")).casefold() == actual:
            raise GoogleAccessError("That address is already connected in the other slot; select your second account.")
    record["email"] = actual
    vault.set(account, record)
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
