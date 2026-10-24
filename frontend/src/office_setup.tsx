import { useId, useState } from "react";
import { usePrivateResource } from "./feature_types";
import { OfficeCloudSetup, type OfficeCloudSettings } from "./office_cloud_setup";

export type OfficeSettings = {
  folder: string;
  enable_read_tools: boolean;
  auto_connect: boolean;
};
type OfficeStatus = {
  available: boolean;
  default_folder: string;
  reason: string;
  auto_connect: boolean;
  enable_read_tools: boolean;
};

type OfficeSetupProps = {
  token: string;
  disabled: boolean;
  busy: boolean;
  onSetup: (settings: OfficeSettings) => void;
  onCancel: () => void;
};

export function OfficeSetup(props: OfficeSetupProps & { onCloudSetup: (settings: OfficeCloudSettings) => void }) {
  const [cloud, setCloud] = useState(false);
  return (
    <section aria-label="Microsoft Office setup">
      <div className="hc-mcp-actions hc-office-choice" role="group" aria-label="Office connection type">
        <button disabled={props.busy} aria-pressed={!cloud} onClick={() => setCloud(false)}>Local files</button>
        <button disabled={props.busy} aria-pressed={cloud} onClick={() => setCloud(true)}>Microsoft 365 cloud</button>
      </div>
      {cloud
        ? <OfficeCloudSetup token={props.token} disabled={props.disabled} busy={props.busy} onSetup={props.onCloudSetup} onCancel={props.onCancel} />
        : <LocalOfficeSetup {...props} />}
    </section>
  );
}

function LocalOfficeSetup({ token, disabled, busy, onSetup, onCancel }: OfficeSetupProps) {
  const status = usePrivateResource<OfficeStatus>("/api/mcp/office", token, 0);
  const [folder, setFolder] = useState<string | null>(null);
  const [read, setRead] = useState<boolean | null>(null);
  const [reconnect, setReconnect] = useState<boolean | null>(null);
  const folderHint = useId();
  const ready = status.data?.available && !status.error;
  return (
    <form className="hc-mcp-editor hc-office-setup" onSubmit={(event) => {
      event.preventDefault();
      if (ready && !disabled) onSetup({
        folder: folder ?? status.data!.default_folder,
        enable_read_tools: read ?? status.data!.enable_read_tools,
        auto_connect: reconnect ?? status.data!.auto_connect,
      });
    }}>
      <h2>Connect Microsoft Office files</h2>
      <p>Give HANNI access to a document folder on this PC. Read documents, create Word files, update Excel cells, and build PowerPoint slides.</p>
      <p className="hc-mcp-policy">This bundled connector works with saved files. No Microsoft sign-in is required. For Outlook, OneDrive, and SharePoint, choose Microsoft 365 cloud above. Unsaved Office windows are not accessible.</p>
      {(status.error || status.data?.reason) && <p className="hc-error-text" role="alert">{status.error || status.data?.reason}</p>}
      {!status.data && !status.error && <p role="status">Checking Office connector…</p>}
      <fieldset disabled={disabled || !ready}>
        <label>
          Document folder
          <input
            value={folder ?? status.data?.default_folder ?? ""}
            onChange={(event) => setFolder(event.target.value)}
            required maxLength={1000} autoComplete="off" spellCheck={false}
            aria-describedby={folderHint}
          />
        </label>
        <p id={folderHint} className="hc-mcp-hint">Paste the full folder path. HANNI creates it if needed; only files inside this folder are accessible through this connector.</p>
        <label className="hc-mcp-check">
          <input type="checkbox" checked={read ?? status.data?.enable_read_tools ?? true} onChange={(event) => setRead(event.target.checked)} />
          Enable listing and reading documents in this folder
        </label>
        <label className="hc-mcp-check">
          <input type="checkbox" checked={reconnect ?? status.data?.auto_connect ?? false} onChange={(event) => setReconnect(event.target.checked)} />
          Reconnect when HANNI starts
        </label>
        <p className="hc-mcp-policy">Creating and editing tools start disabled. Enable them individually below after connecting; HANNI’s action approval policy still applies.</p>
      </fieldset>
      <div className="hc-mcp-actions">
        <button type="submit" className="hc-mcp-primary" disabled={disabled || !ready}>{busy ? "Connecting…" : "Connect Office files"}</button>
        {!ready && <button type="button" disabled={busy} onClick={status.refresh}>Check again</button>}
        <button type="button" disabled={busy} onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
