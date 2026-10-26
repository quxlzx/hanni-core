import { useRef, useState } from "react";
import { write } from "./api";
import { usePrivateResource } from "./feature_types";
import "./teams_settings.css";

type TeamsData = {
  available: boolean; reason: string | null; notice?: string;
  tab: { running: boolean; url: string; package_ready: boolean; pairing_ready: boolean;
    certificate: { ready: boolean; trusted: boolean; expires: string | null } };
  account: { configured: boolean; client_id: string; tenant: string; scopes: string[];
    profile: { displayName: string; userPrincipalName: string } | null };
  job: { id: string; state: string; message: string; user_code?: string; expires_at?: number } | null;
};
type ActionResult = TeamsData & { pairing_code?: string; expires_at?: number; package?: string };

export function TeamsSettings({ token, disabled = false }: { token: string; disabled?: boolean }) {
  const resource = usePrivateResource<TeamsData>("/api/integrations/teams", token, 5000);
  const data = resource.data;
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(""), [notice, setNotice] = useState("");
  const [client, setClient] = useState<string | null>(null), [tenant, setTenant] = useState<string | null>(null);
  const [pair, setPair] = useState<{ code: string; expires: number } | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);
  const lock = useRef(false);
  const pending = useRef<{ signature: string; id: string } | null>(null);
  const unavailable = disabled || !token || !data?.available || Boolean(resource.error);
  const blocked = unavailable || Boolean(busy);
  const signing = ["starting", "waiting"].includes(data?.job?.state || "");

  async function act(operation: string, payload: unknown = {}) {
    if (unavailable || lock.current) return;
    lock.current = true; setBusy(operation); setError(""); setNotice("");
    const signature = JSON.stringify({ operation, data: payload, token });
    const id = pending.current?.signature === signature ? pending.current.id : crypto.randomUUID();
    pending.current = { signature, id };
    try {
      const saved = await write<ActionResult>("/api/integrations/teams", token, { id, operation, data: payload });
      pending.current = null;
      if (saved.pairing_code) setPair({ code: saved.pairing_code, expires: saved.expires_at! });
      else if (saved.package) {
        const bytes = Uint8Array.from(atob(saved.package), (char) => char.charCodeAt(0));
        const url = URL.createObjectURL(new Blob([bytes], { type: "application/zip" }));
        const link = document.createElement("a"); link.href = url; link.download = "HANNI-Teams.zip";
        document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 10000);
        setNotice("Teams app package downloaded. Upload HANNI-Teams.zip in Teams.");
      } else {
        resource.setData(saved);
        setNotice(saved.notice || ({ prepare: "Teams app prepared. Trust the certificate, then download and upload the app package.",
          trust: "Local certificate trusted for your Windows account.", start: "Teams tab started. Generate a pairing code to connect it.",
          stop: "Teams tab stopped. Existing tab sessions were disconnected.", configure: "Microsoft application saved. Sign in to connect your account.",
          disconnect: "Teams credentials removed from this PC. You can also revoke consent in your Microsoft account." } as Record<string, string>)[operation] || "");
        if (["stop", "start", "prepare"].includes(operation)) setPair(null);
        if (operation === "disconnect") setDisconnecting(false);
      }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Teams setup failed. Refresh and try again."); }
    finally { lock.current = false; setBusy(""); resource.refresh(); }
  }
  async function copy(value: string) {
    try { await navigator.clipboard.writeText(value); setNotice("Code copied."); }
    catch { setError("Clipboard access was blocked. Select and copy the code shown here."); }
  }

  return <div className="teams-settings">
    <div className="teams-toolbar"><span>Tab hosting &amp; read-only messages</span><button type="button" disabled={Boolean(busy)} onClick={resource.refresh}>Refresh Teams</button></div>
    {(error || resource.error || data?.reason) && <p className="hc-error-text" role="alert">{error || resource.error || data?.reason}</p>}
    {notice && <p role="status">{notice}</p>}
    {!data && !resource.error && <p role="status">Checking Teams integration…</p>}
    {data && <>
      <section className="teams-setup-section" aria-labelledby="teams-tab-heading">
        <div className="teams-subheading"><h3 id="teams-tab-heading">Use HANNI inside Teams</h3><span>{data.tab.running ? "Running on this PC" : "Tab stopped"}</span></div>
        <p>Open your local HANNI workspace as a personal Teams tab on this Windows PC. Keep HANNI running while you use it.</p>
        <ol className="teams-setup-steps">
          <li><strong>Prepare the app</strong><p>Create the app package and a localhost certificate. Trusting it applies only to your current Windows account.</p>
            <div className="teams-actions"><button type="button" disabled={blocked || data.tab.running} onClick={() => void act("prepare")}>{busy === "prepare" ? "Preparing…" : data.tab.package_ready ? "Rebuild Teams app" : "Prepare Teams app"}</button>
              <button type="button" disabled={blocked || !data.tab.certificate.ready || data.tab.certificate.trusted} onClick={() => void act("trust")}>{data.tab.certificate.trusted ? "Certificate trusted" : busy === "trust" ? "Trusting…" : "Trust local certificate"}</button></div>
            {data.tab.certificate.expires && <p className="teams-hint">Certificate expires {new Date(data.tab.certificate.expires).toLocaleDateString()}. Rebuild it when expired.</p>}
          </li>
          <li><strong>Add HANNI to Teams</strong><p>Show the package in File Explorer, then in Teams go to Apps → Manage your apps → Upload an app → Upload a custom app. Select HANNI-Teams.zip. Your organization must allow custom apps.</p>
            <div className="teams-actions"><button type="button" disabled={blocked || !data.tab.package_ready} onClick={() => void act("show_package")}>Show Teams app in folder</button>
            <button type="button" disabled={blocked || !data.tab.package_ready} onClick={() => void act("download")}>Download Teams app</button></div><p className="teams-hint">Using HANNI in a browser? Download the ZIP there. In HANNI OS, use Show Teams app in folder.</p></li>
          <li><strong>Start and pair the tab</strong><p>Start the local tab server, open HANNI in Teams, and enter a fresh pairing code. Codes work once and expire after 15 minutes.</p>
            <div className="teams-actions"><button type="button" disabled={blocked || !data.tab.certificate.ready} onClick={() => void act(data.tab.running ? "stop" : "start")}>{busy === "start" ? "Starting…" : data.tab.running ? "Stop Teams tab" : "Start Teams tab"}</button>
              <button type="button" disabled={blocked || !data.tab.running} onClick={() => void act("pair")}>Generate pairing code</button></div>
            {pair && data.tab.running && data.tab.pairing_ready && pair.expires > Date.now() / 1000 && <div className="teams-code"><label htmlFor="teams-pair-code">Teams tab pairing code</label><input id="teams-pair-code" readOnly value={pair.code} spellCheck={false} /><button type="button" onClick={() => void copy(pair.code)}>Copy pairing code</button></div>}
          </li>
        </ol>
      </section>
      <section className="teams-setup-section" aria-labelledby="teams-messages-heading">
        <div className="teams-subheading"><h3 id="teams-messages-heading">Read Teams messages</h3><span>{data.account.profile ? "Account connected" : "Account not connected"}</span></div>
        <p>Let HANNI read your work or school chats, channel messages and thread replies when asked. This connection uses Microsoft Graph and has no message sending or editing tools.</p>
        {data.account.profile && <div className="teams-account"><strong>{data.account.profile.displayName}</strong><p>{data.account.profile.userPrincipalName}</p>
          <div className="teams-actions"><button type="button" disabled={blocked || signing} onClick={() => void act("check")}>{busy === "check" ? "Checking…" : "Check message access"}</button><button type="button" disabled={blocked} onClick={() => setDisconnecting(true)}>Disconnect account</button></div>
          {disconnecting && <div className="teams-disconnect"><p>Remove the saved Teams account from this PC?</p><div className="teams-actions"><button type="button" disabled={blocked} onClick={() => void act("disconnect")}>Remove Teams connection</button><button type="button" onClick={() => setDisconnecting(false)}>Keep connected</button></div></div>}
        </div>}
        <details className="teams-registration" open={!data.account.configured}>
          <summary>{data.account.configured ? "Microsoft app settings & permissions" : "Set up Microsoft sign-in once"}</summary>
          <p><button type="button" disabled={blocked} onClick={() => void act("open_registration")}>Open Microsoft Entra</button></p>
          <ol><li>In Microsoft Entra → App registrations, register a desktop app for your organization.</li>
            <li>Under Authentication → Advanced settings, enable <strong>Allow public client flows</strong>. No client secret or redirect URI is needed for device sign-in.</li>
            <li>Add the following Microsoft Graph <strong>delegated</strong> permissions. Ask your administrator to grant consent if required.</li></ol>
          <p className="teams-permissions">{data.account.scopes.join(" · ")}</p>
          <form onSubmit={(event) => { event.preventDefault(); void act("configure", { client_id: client ?? data.account.client_id, tenant: tenant ?? data.account.tenant }); }}>
            <label htmlFor="teams-client-id">Application (client) ID</label><input id="teams-client-id" value={client ?? data.account.client_id} onChange={(event) => setClient(event.target.value.trim())} placeholder="Paste the application ID" required maxLength={36} autoComplete="off" spellCheck={false} disabled={blocked || signing || Boolean(data.account.profile)} />
            <label htmlFor="teams-tenant-id">Directory (tenant) ID</label><input id="teams-tenant-id" value={tenant ?? data.account.tenant} onChange={(event) => setTenant(event.target.value.trim())} required maxLength={36} autoComplete="off" spellCheck={false} disabled={blocked || signing || Boolean(data.account.profile)} />
            <p className="teams-hint">Use your directory ID, or “organizations” for a multi-tenant work or school app. Disconnect before changing a connected app.</p>
            <button type="submit" disabled={blocked || signing || Boolean(data.account.profile)}>Save Microsoft app</button>
          </form>
        </details>
        <div className="teams-actions"><button type="button" disabled={blocked || signing || !data.account.configured} onClick={() => void act("connect")}>{busy === "connect" || signing ? "Waiting for Microsoft…" : data.account.profile ? "Reconnect Microsoft account" : "Sign in to Microsoft"}</button>
          {signing && <button type="button" disabled={blocked} onClick={() => void act("cancel")}>Cancel sign-in</button>}</div>
        {data.job && <div className="teams-sign-in" role="status"><p>{data.job.message}</p>{signing && data.job.user_code && <>
          <div className="teams-code"><label htmlFor="teams-device-code">Microsoft sign-in code</label><input id="teams-device-code" readOnly value={data.job.user_code} /><button type="button" onClick={() => void copy(data.job!.user_code!)}>Copy sign-in code</button></div>
          <button type="button" disabled={blocked} onClick={() => void act("open_signin")}>Open Microsoft sign-in</button>
        </>}</div>}
        <p className="teams-hint">After connecting, ask “List my Teams chats” or “Summarize recent messages in this channel.” Tokens stay in Windows Credential Manager. Your organization’s access policies still apply.</p>
      </section>
    </>}
  </div>;
}
