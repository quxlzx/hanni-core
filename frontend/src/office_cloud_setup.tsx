import { useId, useState } from "react";
import { usePrivateResource } from "./feature_types";

export type OfficeCloudSettings = { command: string; auto_connect: boolean };
const setupCommands = "npm install -g @microsoft/workiq@1.0.1\nworkiq accept-eula\nworkiq auth login";
type CloudStatus = { cloud: { command: string; installed: boolean; auto_connect: boolean } };

export function OfficeCloudSetup({ token, disabled, busy, onSetup, onCancel }: {
  token: string;
  disabled: boolean;
  busy: boolean;
  onSetup: (settings: OfficeCloudSettings) => void;
  onCancel: () => void;
}) {
  const status = usePrivateResource<CloudStatus>("/api/mcp/office", token, 0);
  const [command, setCommand] = useState<string | null>(null);
  const [reconnect, setReconnect] = useState<boolean | null>(null);
  const [copyStatus, setCopyStatus] = useState("");
  const hint = useId();
  const ready = Boolean(status.data && !status.error);
  return (
    <form className="hc-mcp-editor hc-office-setup" onSubmit={(event) => {
      event.preventDefault();
      if (ready && !disabled) onSetup({
        command: command ?? status.data!.cloud.command,
        auto_connect: reconnect ?? status.data!.cloud.auto_connect,
      });
    }}>
      <h2>Connect Microsoft 365 cloud</h2>
      <p>Use Microsoft’s Work IQ MCP to find Outlook emails, calendar meetings, Teams messages, and OneDrive or SharePoint documents.</p>
      <p className="hc-mcp-policy">Use a work or school account with Work IQ enabled by your organization. Your administrator must approve access and configure the required billing or licensing. <a href="https://learn.microsoft.com/microsoft-365/copilot/extensibility/work-iq/cli" target="_blank" rel="noreferrer">Microsoft setup requirements</a></p>
      <ol className="hc-office-steps">
        <li>
          <p>Install Work IQ and sign in from PowerShell on this PC. Review Microsoft’s terms before running the acceptance command. Microsoft handles sign-in and saves its credentials.</p>
          <pre aria-label="Microsoft 365 setup commands"><code>{setupCommands}</code></pre>
          <button type="button" disabled={busy} onClick={async () => {
            try {
              await navigator.clipboard.writeText(setupCommands);
              setCopyStatus("Setup commands copied.");
            } catch {
              setCopyStatus("Select the commands above and copy them into PowerShell.");
            }
          }}>Copy setup commands</button>
          {copyStatus && <p role="status">{copyStatus}</p>}
        </li>
        <li><p>Return here, check the executable path, and connect. This discovers tools; it does not check account access or run a Microsoft 365 query.</p></li>
      </ol>
      {status.error && <p className="hc-error-text" role="alert">{status.error}</p>}
      {!status.data && !status.error && <p role="status">Checking Work IQ installation…</p>}
      <fieldset disabled={disabled || !ready}>
        <label>
          Work IQ executable
          <input
            value={command ?? status.data?.cloud.command ?? ""}
            onChange={(event) => setCommand(event.target.value)}
            required maxLength={1000} autoComplete="off" spellCheck={false}
            placeholder="Full path to workiq.cmd or workiq.exe"
            aria-describedby={hint}
          />
        </label>
        <p id={hint} className="hc-mcp-hint">{status.data?.cloud.installed ? "Installed executable detected." : "After installing, select Check installation. For a custom install, paste the full executable path."} HANNI starts this executable with the mcp command.</p>
        <label className="hc-mcp-check">
          <input type="checkbox" checked={reconnect ?? status.data?.cloud.auto_connect ?? false} onChange={(event) => setReconnect(event.target.checked)} />
          Reconnect when HANNI starts
        </label>
        <p className="hc-mcp-policy">Cloud tools start disabled. Review each tool and choose its permission below before enabling it. Use Write for tools that can perform actions, including open-ended delegation.</p>
      </fieldset>
      <div className="hc-mcp-actions">
        <button type="submit" className="hc-mcp-primary" disabled={disabled || !ready}>{busy ? "Connecting…" : "Connect Microsoft 365"}</button>
        <button type="button" disabled={busy} onClick={status.refresh}>Check installation</button>
        <button type="button" disabled={busy} onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
