# Connect Google to HANNI

Google is optional. HANNI starts and its local tools work without a Google connection. Retrieved Google content can be included in replies from your selected inference model.

## Connect from Settings

Open **Settings → Integrations → Google accounts**. No terminal commands or Google passwords are needed in HANNI.

1. On the first connection, select **Open Google setup** and complete the Google Cloud steps below. Download the **Desktop app** client JSON, then use **Choose client JSON** to import it. This setup is shared by subsequent accounts.
2. Choose a local account name such as `personal`, `work`, or `school`. Select Calendar, Gmail, Drive & documents, or Google Tasks. Calendar and Gmail read access are selected initially. Calendar and Tasks changes require the separate **Allow calendar and task changes** option; Gmail sending and Drive document editing are unsupported.
3. Select **Sign in with Google**. Choose your email address and approve the requested services in your system browser. HANNI verifies the returned identity and grants before saving credentials in Windows Credential Manager.
4. Use **Add Google account** for another address. **Make default** changes the account used for unqualified requests; existing service-specific preferences still take priority.

**Reconnect** retains the original email address and selected calendars, keeps existing Google grants, and adds selected services. To remove a grant, disconnect locally, revoke HANNI's access in your Google account, then sign in with fewer services. **Disconnect** asks for confirmation and removes the local credentials and preferences pointing to that account; it does not revoke access at Google. The same email cannot occupy multiple local account labels.

Sign-in runs in the background. **Cancel sign-in** stops waiting for the browser and prevents a late callback from saving credentials. Leaving Settings does not cancel it; shutting down the backend does. Setup JSON goes directly to the account setup endpoint and is not added to chat or attachments. Connected rows show saved grants, not a fresh health check of each service.

The browser's return page means Google authorization was received; wait for **Google account connected** in HANNI. Settings reports permission checking, email verification, and credential saving separately. Equivalent email/OpenID scope labels are accepted, while missing or additional service permissions are rejected. Sign-in is marked connected only after Windows Credential Manager returns the saved record. Unused ID tokens are omitted from that record.

If the browser finishes but HANNI stays disconnected, read the sign-in message in Settings. A permissions mismatch requires approving all selected services, or revoking an older grant in your Google account before retrying. A network failure after consent means HANNI could not finish its calls to Google. A credential-storage failure means Windows could not save or return the connection; check Credential Manager access on that PC. Client, expired-code, wrong-account, and timeout failures have separate messages. A reconnect that fails before saving retains the existing connection.

## Google skills

Six bundled procedures load automatically for relevant requests:

| Skill | Example request |
| --- | --- |
| `google-gmail` | "Triage my Gmail and draft a reply to the project update." |
| `google-calendar` | "What's on my Google Calendar tomorrow?" |
| `google-drive` | "Find the onboarding guide in Drive." |
| `google-docs` | "Summarize my Google Doc about the launch." |
| `google-tasks` | "Show my Google Tasks." |
| `google-workday-briefing` | "Give me a morning briefing." |

The skills use the connected account and available service permissions. They
guide existing tools; they do not enable unsupported Gmail sending, Docs editing,
Sheets editing, task due-date writes, or Calendar invitations. A briefing runs on
demand unless you explicitly ask for a recurring schedule. Skill names appear in
the Skills collection and in activity when applied.

## Google Cloud setup

1. Create or select your own [Google Cloud project](https://console.cloud.google.com/).
2. Enable **Google Calendar API**, **Gmail API**, **Google Drive API**, and **Google Tasks API** for the services you will use. Docs text uses Drive export; the Docs API is not required.
3. Configure the OAuth consent screen. If the app is in Testing, add each account as a test user. Organization administrators may need to allow the app.
4. Create an OAuth client with application type **Desktop app**, then download its JSON file. Service accounts and Web application clients are unsupported.

Use **Choose client JSON** in Settings to import the download into the ignored `config/google-oauth-client.json`. Normal `SETUP_HANNI.cmd` installs the Google dependencies. The terminal alternative below also finds a single valid `client_secret*.json` download or prompts for its path. Select another file there with `--client-secrets C:\path\client.json`.

From the repository folder in PowerShell:

```powershell
# Default: Calendar read access and account identity only.
.\.venv\Scripts\hanni.exe google login

# Add other read services to the existing connection.
.\.venv\Scripts\hanni.exe google login --replace --scopes calendar.read gmail.read drive.read docs.read tasks.read

# Connect another account with its own grants.
.\.venv\Scripts\hanni.exe google login --account school --scopes calendar.read gmail.read drive.read

.\.venv\Scripts\hanni.exe google status
.\.venv\Scripts\hanni.exe google accounts
.\.venv\Scripts\hanni.exe google status --verify
```

`status` and `accounts` inspect local metadata without network access. `status --verify` probes only authorized services. Existing credentials remain usable. `--replace` adds requested scopes to existing grants. To reduce grants, log out locally, revoke the app in Google account settings, then log in with fewer scopes.

## Named accounts and defaults

Labels such as `personal`, `school`, `work`, or `research-lab` are local to HANNI. They use 1–32 lowercase letters, digits, hyphens or underscores, beginning with a letter.

```powershell
.\.venv\Scripts\hanni.exe google use personal
.\.venv\Scripts\hanni.exe google use school --service calendar
.\.venv\Scripts\hanni.exe google use work --service drive
.\.venv\Scripts\hanni.exe google logout --account school
```

Selection order: explicit account, service preference, global default, then connected `personal` or the first connected label. Unqualified requests search one account. A disconnected preference produces an error instead of switching silently. The model cannot widen a default request to all accounts. `logout` removes local credentials; it does not revoke the grant at Google.

Examples: “what's on my school calendar,” “check my personal Gmail,” “search school Drive for syllabus.” For custom labels, say `account research-lab` or `research-lab account`.

## OAuth scopes

All suffixes below use `https://www.googleapis.com/auth/`. Every login also requests `userinfo.email` to verify account identity without Gmail access.

| CLI group | Google scope suffixes | Access |
| --- | --- | --- |
| `calendar.read` (default) | `calendar.events.readonly`, `calendar.calendarlist.readonly` | Calendar reads |
| `calendar.write` | `calendar.events`, `calendar.calendarlist.readonly` | Event read/write |
| `gmail.read` | `gmail.readonly` | Metadata, messages and threads |
| `drive.read` | `drive.metadata.readonly` | Search and file metadata |
| `docs.read` | `drive.readonly` | Native Docs text export, including Drive metadata |
| `tasks.read` | `tasks.readonly` | Tasks reads |
| `tasks.write` | `tasks` | Tasks read/write |

Google's `drive.readonly` allows reading all accessible Drive files. HANNI requests it only for `docs.read`, and its content adapter only exports native Google Docs. Unsupported scope groups are rejected. See Google's [scope definitions](https://developers.google.com/identity/protocols/oauth2/scopes).

## Capabilities and examples

| Family | Capability IDs | Behavior |
| --- | --- | --- |
| Calendar reads | `google.calendar.events`, `.next`, `.availability`, `.list_calendars`, `.read` | Resolved date windows and exact event IDs |
| Calendar writes | `google.calendar.create`, `.update`, `.delete` | Explicit creation; confirmation for updates/deletes |
| Gmail | `google.gmail.recent`, `.search`, `.read`, `.thread` | Metadata first; bodies for explicit reads |
| Drive | `google.drive.search`, `.list`, `.recent`, `.metadata` | Bounded metadata, account, IDs, owners, type, modified time, URL |
| Docs | `google.docs.read` | Exact ID or search phrase; ambiguous results require selection |
| Tasks | `google.tasks.list`, `.create`, `.complete` | Explicit Google provider, separate from local todos |

Legacy `google_calendar.*`, `gmail.*` and `email.*` IDs remain for existing routes. Calendar uses `user.timezone` in `config/hanni.yaml`, currently `America/New_York`.

- “What's on my calendar tomorrow?” / “What about Sunday?”
- “Am I free from 6 to 8?”
- “Add study session tomorrow at 6.”
- “Find emails from NVIDIA.” / “Open the newest one.”
- “Find my resume in Drive.” / “Open 1.”
- “Show me recent Google Docs.” / “Read 1.”
- “Read my HANNI design doc.” / “Summarize my research notes.”
- “What Google Tasks do I have?”
- “What about my school account?”

References retain exact IDs and accounts for 15 minutes in the current session. “Open it” asks for a result number when ambiguous. Opening Drive results returns verified metadata and a URL; it does not launch a browser or use `app.open`. “Read 1”/“summarize 1” exports a native Google Doc. Generic file searches keep the local router; say “in Drive” for Google.

## Writes

Enable Calendar writes explicitly:

```powershell
.\.venv\Scripts\hanni.exe google login --replace --scopes calendar.write
```

Calendar creation already appears in production `mcp.allowed_actions`. For spoken task creation, authorize `tasks.write` and add `google.tasks.create` to that list in `config/hanni.yaml`; then say “add finish homework to my Google Tasks.” Local todos keep their existing routes.

Calendar update/delete and task completion use exact verified IDs. The assistant session lacks an interactive confirmation flow for them and blocks them. After inspecting the item, the owner may use the existing manual CLI:

```powershell
.\.venv\Scripts\hanni.exe tool-run google.calendar.update --arg account=personal --arg id=EVENT_ID --arg summary="Study session" --confirm
.\.venv\Scripts\hanni.exe tool-run google.calendar.delete --arg account=personal --arg id=EVENT_ID --confirm
.\.venv\Scripts\hanni.exe tool-run google.tasks.complete --arg account=personal --arg id=TASK_ID --confirm
```

These require write scopes and owner permissions. Calendar changes use calendars selected during login (`--calendar primary`, or repeated `--calendar ID`). Moving an event requires both `start` and `end` as timezone-aware ISO timestamps. Review the exact item before replacing placeholders and running these real writes.

**NOT_IMPLEMENTED:** Gmail send/reply/delete/archive, Drive delete/share, and Docs editing. Sending requires a reviewed-message confirmation flow that this session does not provide. No mail-send or Drive-write scopes are requested. Named mutations such as “move my study session to 7” remain blocked; use the manual exact-ID path.

## Security and limits

- Settings sign-in uses the official Google OAuth library with PKCE, a random loopback port, state validation, and the system browser. Tokens use Windows Credential Manager, with no plaintext token fallback. Account indexes and preferences use the same vault.
- Client JSON/token filenames are gitignored. Tokens and raw Google error bodies are not printed. Audit records omit Google result content and query text.
- Adapters use fixed Google origins, no redirects, bounded timeouts and a 2 MB response cap. Authentication libraries load only when needed.
- Lists/searches are bounded and marked partial. Docs text is limited to 6,000 characters with an explicit truncation flag. PDF/Office content and Gmail attachments are not downloaded.
- Reference state retains no bodies. Tool results are untrusted data for the local model. The dashboard's existing visible chat/history policy still applies to displayed replies.
- API failure, empty results and missing permissions are distinct. Local tools continue during Google outages.

## Troubleshooting

| State | Action |
| --- | --- |
| `not_connected` / expired or revoked grant | `google login --account LABEL --replace --scopes ...` |
| `permission_denied` | Add the indicated scope; enable that API in the client project; check organization policy |
| `not_found` | Search again; the item may have moved, been deleted or belong to another account |
| `rate_limited` | Wait before retrying; narrow searches |
| `api_error` | Check network access and run `google status --verify` |
| `partial` | Narrow the date range/search; summaries cover returned evidence only |
| Wrong default account | `google use LABEL` or `google use LABEL --service SERVICE` |
| Missing dependencies | Run `SETUP_HANNI.cmd` or `.\.venv\Scripts\python.exe -m pip install -e ".[google]"` |

An OAuth grant does not prove an API is enabled. `status --verify` checks availability separately. Google consent/testing limits and Workspace administrator restrictions still apply.

Google documents the [installed-app OAuth flow](https://developers.google.com/identity/protocols/oauth2/native-app) and the official library's [Desktop application flow](https://googleapis.dev/python/google-auth-oauthlib/latest/reference/google_auth_oauthlib.flow.html). Automated tests cover the real local callback and dashboard routes with an isolated provider and credential store; live consent and access to your account require your own Google setup and sign-in.
