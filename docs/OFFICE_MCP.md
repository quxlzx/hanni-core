# Office and Microsoft 365 MCP setup

Open **MCP → Microsoft Office**. Local files and Microsoft 365 cloud are separate connections; you can keep both.

## Local files

Choose **Local files**, enter an absolute document folder, and select **Connect Office files**. The folder is created if needed. The bundled `HANNI Office files` server runs with HANNI’s Python interpreter; no Office installation or Microsoft login is needed.

Listing and reading can be enabled during setup. The six creating/editing tools start disabled. Choose **Write** and **Enable tool** for each tool you want to use. Execution still follows HANNI’s per-action approval policy. Reads return a SHA-256 file version; editing tools require that version and reject stale edits. New-document tools refuse to overwrite existing files.

Supported operations:

| Files | Operations |
| --- | --- |
| DOCX | Read, create text paragraphs, append paragraphs |
| XLSX | Read, create workbooks, write a cell range on an existing sheet |
| PPTX | Read, create title/body slides, append a slide |
| XLS, XLSM, ODT, ODS, PDF, CSV, TSV | Read only |

Use relative paths inside the selected folder. File size is limited to 8 MiB; XML archives also have expansion limits. Reading returns text, not rendered layout or images. This connector does not automate open/unsaved desktop windows, calculate Excel formulas, edit macros, or guarantee preservation of advanced document features. Formula-looking cell values are literal text unless formulas are explicitly requested. Close a document in Office if Windows reports that it is locked. Missing reader/writer dependencies can be installed by rerunning `SETUP_HANNI.cmd` and restarting HANNI.

## Microsoft 365 cloud

HANNI connects to Microsoft’s **Work IQ** MCP, rather than storing Microsoft credentials or using a custom Graph application. This can retrieve workplace context from Outlook, calendar, Teams, OneDrive, and SharePoint according to your organization’s permissions. It requires a work/school account with Work IQ enabled, administrator consent, and the applicable Microsoft billing/licensing configuration. See [Microsoft’s current requirements](https://learn.microsoft.com/microsoft-365/copilot/extensibility/work-iq/cli) and the [tenant administrator guide](https://github.com/microsoft/work-iq/blob/main/ADMIN-INSTRUCTIONS.md).

1. Install Node.js if it is not already present.
2. Open PowerShell on the same PC and Windows account that runs HANNI:

   ```powershell
   npm install -g @microsoft/workiq@1.0.1
   workiq accept-eula
   workiq auth login
   ```

   Review Microsoft’s terms before running `accept-eula`. Complete Microsoft’s interactive sign-in and your organization’s approval process. Version 1.0.1 was checked with HANNI’s SDK discovery; future versions may expose different tools.
3. Choose **Microsoft 365 cloud → Check installation**. HANNI checks PATH and the default Windows npm location. If you installed elsewhere, enter the full path to `workiq.cmd`, `workiq.exe`, or `workiq`; do not add arguments.
4. Select **Connect Microsoft 365**. This starts the installed executable with `mcp`, saves its configuration, and discovers tools. It does not run a cloud query or verify your account’s data access.
5. Review and enable tools individually. Work IQ’s `ask` can delegate work; use **Write** for open-ended/action-capable tools so that HANNI requires an execution decision. Tools remain disabled until you approve their definitions. HANNI does not auto-enable the EULA tool.

Work IQ owns sign-in and its credential cache. No tokens or passwords are entered in HANNI’s MCP configuration. If account access fails, run `workiq auth login` again, check your organization’s enablement, and retry the task. Use `workiq auth logout` in PowerShell to sign out. **Disconnect** in HANNI stops the MCP connection and pauses startup reconnect; it does not sign you out of Microsoft or revoke organizational consent.

Both setup flows reuse an existing matching connection on retry. If its settings differ, edit or remove that server before setting it up again. Removing the local connection retains your document files. The optional startup reconnect setting pins the exact saved configuration after successful discovery.
