# HANNI inside Microsoft Teams

HANNI can run as a **personal Teams tab on the same Windows PC** as your assistant. It keeps the current chat interface, models, files, memories, task reviews, notifications inbox, and Tool access settings. The desktop app remains available. This is a local development/custom app; it is not an organization-wide hosted service, channel bot, or shared workspace.

## Setup from HANNI OS

Open **Settings → Integrations → Microsoft Teams**. The two connections are independent: the personal tab hosts HANNI inside Teams; the account connection lets HANNI read Teams messages from either interface.

Under **Use HANNI inside Teams**:

1. Select **Prepare Teams app**, then **Trust local certificate**. The trust button installs only this localhost development certificate for the current Windows account. No administrator elevation, machine-wide certificate authority, firewall rule, tunnel, or cloud resource is created.
2. Select **Show Teams app in folder** to reveal `HANNI-Teams.zip` in File Explorer. In a regular browser, you can also use **Download Teams app**. In Teams, go to **Apps → Manage your apps → Upload an app → Upload a custom app** and upload `HANNI-Teams.zip`. Your organization must allow custom apps.
3. Select **Start Teams tab**, then **Generate pairing code**. Open HANNI in Teams and enter the code. It works once and expires after 15 minutes. Generate another code to pair another tab; existing paired sessions remain valid.

Keep HANNI running. **Stop Teams tab** disconnects sessions hosted by this instance; restarting HANNI also stops the tab server, so start it again from Integrations. HANNI never stops an independently running `START_TEAMS.cmd` launcher or another process using port 8313. Close that launcher before starting the in-app server.

The in-app package is stored under ignored `state/teams/HANNI-Teams.zip`; the certificate and private key stay in `state/teams/tls`. Rebuild and trust the certificate again after its 30-day lifetime. No private key is included in the ZIP download.

## Connect Teams messages

Under **Read Teams messages**, expand **Set up Microsoft sign-in once**:

1. Open the linked **Microsoft Entra → App registrations** page and register an application for your organization. Enable **Authentication → Advanced settings → Allow public client flows**. Device sign-in needs no client secret or redirect URI.
2. Add Microsoft Graph **delegated** permissions: `User.Read`, `Chat.Read`, `Team.ReadBasic.All`, `Channel.ReadBasic.All`, and `ChannelMessage.Read.All`. Ask your administrator to grant consent when required by the permissions or tenant policies.
3. Copy the Application (client) ID and Directory (tenant) ID into HANNI, then select **Save Microsoft app**. A multi-tenant app can use `organizations` as its tenant. Do not paste an application secret.
4. Select **Sign in to Microsoft**, copy the displayed device code, and select **Open Microsoft sign-in**. Complete sign-in and consent in the system browser. HANNI reports the verified account when it finishes. You can cancel without saving a late sign-in result.
5. Select **Check message access** to verify the account, chat listing, and joined teams. Channel permissions are checked when reading a channel. Then ask HANNI to list your Teams chats or summarize messages in a selected chat or channel.

HANNI provides read-only `teams.chats`, `teams.teams`, `teams.channels`, `teams.chat_messages`, `teams.channel_messages`, and `teams.replies` capabilities. The native conversation receives these tools only while an account is connected. Channel roots and replies are separate reads. Results are bounded and report truncation; this is on-demand retrieval, not continuous message syncing or organization-wide search. No message sending, editing, or deletion is implemented.

The OAuth client ID and tenant are non-secret local configuration. Access and refresh tokens are saved only in Windows Credential Manager, split into bounded entries when necessary, and never sent to the model or included in Settings responses. **Disconnect account → Remove Teams connection** verifies removal of the local credential index and makes the native tools unavailable. To revoke the Microsoft consent itself, use your organization's Microsoft account controls or ask your administrator.

This integration targets work or school accounts in Microsoft's global cloud. Personal Microsoft accounts are not supported by the message APIs. Tenant consent and conditional-access policies still apply; no Work IQ subscription is needed for this Graph adapter. See Microsoft's [device authorization flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code), [chat message permissions](https://learn.microsoft.com/en-us/graph/api/chat-list-messages?view=graph-rest-1.0), and [channel message permissions](https://learn.microsoft.com/en-us/graph/api/channel-list-messages?view=graph-rest-1.0).

## Setup with launch scripts

1. Run `SETUP_HANNI.cmd` if this PC is not already set up.
2. Run **`SETUP_TEAMS.cmd`**. It installs the Teams build dependencies, builds the frontend and `dist/teams/HANNI-Teams.zip`, and creates a 30-day localhost development certificate. **It trusts that certificate for your current Windows account.** No machine-wide certificate authority, firewall rule, tunnel, or cloud resource is created. Restart Teams/your browser after first certificate setup if necessary.
3. In Teams, open **Apps → Manage your apps → Upload an app → Upload a custom app**, select `dist/teams/HANNI-Teams.zip`, and add HANNI. Your work/school tenant must allow custom app uploads; an administrator may need to enable this. The package is a personal tab and requests no Graph permissions.
4. Start HANNI with `START_HANNI.cmd` and leave it running in the tray. Then run **`START_TEAMS.cmd`** and keep its launcher open.
5. Open the HANNI tab in Teams. Enter the pairing code displayed by `START_TEAMS.cmd`. The code expires after 15 minutes and authorizes one tab session. Your existing HANNI conversations then appear.

The generated package is already available after building the repository changes, but the local development certificate must be trusted before Teams can load it. To build without installing/trusting a certificate, run `.venv/Scripts/python.exe scripts/build_teams.py`. To rebuild and trust it using already-installed dependencies, run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_teams.ps1 -SkipInstall -TrustLocalCertificate`.

Before uploading, you can check the local page in Edge at `https://localhost:8313/?host=teams`. A certificate error must be fixed by setup; bypassing the browser warning does not establish Teams trust. Teams requires HTTPS and initialization of the official Teams SDK; HANNI uses the bundled SDK and the required Teams/cloud frame ancestors. See [Microsoft's tab requirements](https://learn.microsoft.com/en-us/microsoftteams/platform/tabs/how-to/tab-requirements), [local development certificates](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/debug-local), and [custom app uploads](https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/deploy-and-publish/apps-upload).

## Access and operation

The HTTPS listener binds only to `127.0.0.1:8313`. The original HANNI agent and dashboard stay at their loopback addresses. Every Teams API request needs a separate paired session; knowing the tab URL or uploading its manifest grants no access. Pairing tokens are not put in URLs, manifests, localStorage, or log files. They stay in this tab's sessionStorage, with an in-memory fallback, and expire after 12 hours or when the Teams launcher stops. No third-party cookies are required. Teams user/context values are not used as proof of identity.

Treat a pairing code like access to your personal assistant: anyone you give it to can use that session's tools and data. Select **Disconnect tab** to revoke the session, or stop the Teams launcher to revoke all sessions. Restart it for a new pairing code. To use the tab on another PC, install and run that PC's own HANNI session and repeat setup; this package cannot reach your home PC from Teams mobile or other computers.

The gateway preserves HANNI's normal token checks, task approval records, enabled MCP definitions and Tool access setting. File uploads and downloads use the paired connection. Set **Settings → Permissions → Tool access** to Read only, Ask before writes, or Full access as needed. Full access applies only to capabilities already available in your assistant; it does not connect accounts or enable disabled tools.

Use the tab's **Notifications** inbox for task results and approvals. Windows alerts still come from the HANNI desktop/tray app. This tab does not send Teams chat messages, Teams Activity feed notifications, or background bot messages. Closing Teams does not stop the agent or recurring work. Stopping `START_TEAMS.cmd` only ends the Teams connection; stop HANNI separately when desired.

## Troubleshooting and removal

- **Upload option missing:** your tenant's custom-app policy needs administrator action. A manifest cannot override it. This path targets Teams work/school custom apps.
- **Certificate error / tab will not load:** rerun setup on this PC, then restart Teams/Edge. The certificate expires after 30 days; rerun setup to replace and trust a renewed certificate. Edge/Chrome can block the localhost frame until **Local network access** is allowed for the Teams site. Open the browser's site permissions for your Teams host, allow that permission if your organization permits it, then reload. The browser verification explicitly granted this permission to its isolated synthetic Teams host; it did not disable browser protections or change your production browser settings. See [Chromium's local network access guidance](https://github.com/GoogleChrome/modern-web-guidance/blob/main/skills/modern-web-guidance/guides/security/local-network-access.md).
- **HANNI unavailable:** verify `http://127.0.0.1:8311` and start HANNI. A running Teams launcher does not start a second agent or model.
- **Pairing invalid/expired:** select **Generate pairing code** in Integrations, or restart `START_TEAMS.cmd` if using the separate launcher. Codes are single-use; failed attempts are limited per code.
- **Settings unavailable after updating:** the old dashboard process needs to be restarted to load new Python endpoints. Finish active tasks before restarting HANNI.

Remove the app from Teams to uninstall its tab. Stop `START_TEAMS.cmd` to remove its live sessions. To remove certificate trust, open `certmgr.msc` → **Trusted Root Certification Authorities → Certificates**, locate the exact **HANNI Teams localhost development** certificate installed by this repository, verify it against `state/teams/tls/localhost.pem`, and delete that certificate only. The private key and certificate stay under ignored `state/teams/tls`; neither belongs in version control.

The package, TLS/pairing/API paths, and read-only Graph adapter are verified locally with isolated account and provider fixtures. Real Microsoft sign-in, tenant consent, message access, and installation in a signed-in Teams client still need verification in your own account.
