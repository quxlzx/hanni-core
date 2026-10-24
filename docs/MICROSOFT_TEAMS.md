# HANNI inside Microsoft Teams

HANNI can run as a **personal Teams tab on the same Windows PC** as your assistant. It keeps the current chat interface, models, files, memories, task reviews, notifications inbox, and Tool access settings. The desktop app remains available. This is a local development/custom app; it is not an organization-wide hosted service, channel bot, or shared workspace.

## Setup

1. Run `SETUP_HANNI.cmd` if this PC is not already set up.
2. Run **`SETUP_TEAMS.cmd`**. It installs the optional Teams build dependencies, builds the frontend and `dist/teams/HANNI-Teams.zip`, and creates a 30-day localhost development certificate. **It trusts that certificate for your current Windows account.** No machine-wide certificate authority, firewall rule, tunnel, or cloud resource is created. Restart Teams/your browser after first certificate setup if necessary.
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
- **Pairing invalid/expired:** restart `START_TEAMS.cmd` and use its new code. Codes are single-use; failed attempts are limited per launch.
- **Settings unavailable after updating:** the old dashboard process needs to be restarted to load new Python endpoints. Finish active tasks before restarting HANNI.

Remove the app from Teams to uninstall its tab. Stop `START_TEAMS.cmd` to remove its live sessions. To remove certificate trust, open `certmgr.msc` → **Trusted Root Certification Authorities → Certificates**, locate the exact **HANNI Teams localhost development** certificate installed by this repository, verify it against `state/teams/tls/localhost.pem`, and delete that certificate only. The private key and certificate stay under ignored `state/teams/tls`; neither belongs in version control.

The package and TLS/pairing/API paths are verified locally. A signed-in Microsoft Teams client and your tenant's custom-app policy still need installation verification in your own account.
