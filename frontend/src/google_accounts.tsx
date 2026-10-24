import { useRef, useState, type FormEvent } from "react";
import { write } from "./api";
import { usePrivateResource } from "./feature_types";
import "./google_accounts.css";

type Account = { account: string; email: string; revision: string; services: string[] };
type GoogleData = {
  available: boolean; reason: string | null;
  client: { ready: boolean; revision: string };
  accounts: Account[]; default_account: string | null; next_label: string;
  job: { id: string; account: string; state: string; message: string } | null;
};
type Editor = { account: string; capabilities: string[]; replace: boolean; revision: string };
const services = [
  ["calendar", "Calendar"], ["gmail", "Gmail"], ["docs", "Drive & documents"], ["tasks", "Google Tasks"],
] as const;
function describeGrants(account: Account) {
  return [["calendar", "Calendar"], ["gmail", "Gmail"], ["drive", "Drive file list"], ["docs", "Documents"], ["tasks", "Tasks"]]
    .filter(([key]) => account.services.includes(`${key}.read`))
    .map(([key, label]) => `${label}: ${account.services.includes(`${key}.write`) ? "read & write" : "read only"}`).join(" · ");
}

export function GoogleAccountsSettings({ token, disabled = false }: { token: string; disabled?: boolean }) {
  const resource = usePrivateResource<GoogleData>("/api/google/accounts", token, 2000);
  const data = resource.data;
  const [editor, setEditor] = useState<Editor | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const [changingClient, setChangingClient] = useState(false), [disconnecting, setDisconnecting] = useState<string | null>(null);
  const upload = useRef<HTMLInputElement>(null), lock = useRef(false);
  const pending = useRef<{ signature: string; id: string } | null>(null);
  const signingIn = Boolean(data?.job && ["waiting", "cancelling"].includes(data.job.state));
  const unavailable = disabled || !token || !data?.available || Boolean(resource.error);
  const blocked = unavailable || busy || signingIn;
  const form: Editor = editor || { account: data?.next_label || "personal", capabilities: ["calendar.read", "gmail.read"], replace: false, revision: "missing" };
  const writes = form.capabilities.some((capability) => capability.endsWith(".write"));

  async function act(operation: string, payload: unknown, after?: () => void) {
    if (unavailable || lock.current) return;
    lock.current = true; setBusy(true); setError(""); setNotice("");
    const signature = JSON.stringify({ operation, data: payload, token });
    const id = pending.current?.signature === signature ? pending.current.id : crypto.randomUUID();
    pending.current = { signature, id };
    try {
      const saved = await write<GoogleData>("/api/google/accounts", token, { id, operation, data: payload });
      resource.setData(saved); pending.current = null; after?.();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Google setup could not be completed. Refresh and try again.");
    } finally { lock.current = false; setBusy(false); resource.refresh(); }
  }
  async function importFile(file?: File) {
    if (!file) return;
    if (!file.size || file.size > 32000) { setError("Choose the Google Desktop app JSON file, no larger than 32 KB."); return; }
    try {
      const document = await file.text();
      await act("import_client", { document, expected_revision: data?.client.revision }, () => {
        setChangingClient(false); setNotice("Google client saved. Choose your services and sign in below.");
      });
    } catch { setError("The selected file could not be read. Choose it again."); }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (blocked || !data?.client.ready) return;
    void act("connect", { account: form.account.trim(), scopes: form.capabilities, replace: form.replace, expected_revision: form.revision }, () => setEditor(null));
  }
  function toggleService(service: string, checked: boolean) {
    const capabilities = form.capabilities.filter((value) => !value.startsWith(service + "."));
    if (checked) capabilities.push(`${service}.${writes && ["calendar", "tasks"].includes(service) ? "write" : "read"}`);
    setEditor({ ...form, capabilities });
  }
  return (
    <div className="google-accounts" aria-busy={busy}>
      <div className="google-account-toolbar">
        <span>Connect Gmail, Calendar, Drive and Google Tasks.</span>
        <button type="button" className="text-link" onClick={resource.refresh} disabled={busy}>Refresh accounts</button>
      </div>
      {!data && !resource.error && <p role="status">Reading Google connections…</p>}
      {(error || resource.error || data?.reason) && <p className="error-text" role="alert">{error || resource.error || data?.reason}</p>}
      {notice && <p role="status">{notice}</p>}
      {data?.accounts.map((account) => <div className="google-account-row" key={account.account}>
        <div>
          <strong>{account.email}</strong>
          <p>{account.account}{data.default_account === account.account ? " · Default account" : ""}</p>
          <p className="subtle">{describeGrants(account)}</p>
        </div>
        <div className="google-account-actions">
          <button type="button" disabled={blocked} onClick={() => { setEditor({ account: account.account, capabilities: [...account.services], replace: true, revision: account.revision }); setError(""); }}>Reconnect</button>
          {data.default_account !== account.account && <button type="button" disabled={blocked} onClick={() => void act("default", { account: account.account, expected_revision: account.revision })}>Make default</button>}
          <button type="button" className="text-link" disabled={blocked} onClick={() => setDisconnecting(account.account)}>Disconnect</button>
        </div>
        {disconnecting === account.account && <div className="google-disconnect-confirm">
          <p>Disconnect {account.email} from HANNI? This removes its saved credentials on this PC. You can also revoke HANNI in your Google account permissions.</p>
          <button type="button" disabled={blocked} onClick={() => void act("disconnect", { account: account.account, expected_revision: account.revision }, () => { setDisconnecting(null); setEditor(null); })}>Confirm disconnect</button>
          <button type="button" className="text-link" disabled={busy} onClick={() => setDisconnecting(null)}>Keep connected</button>
        </div>}
      </div>)}
      {data?.job && <div className="google-sign-in-state" role={data.job.state === "failed" ? "alert" : "status"}>
        <p>{data.job.message}</p>
        {signingIn && <button type="button" disabled={busy || data.job.state === "cancelling"} onClick={() => void act("cancel", { attempt_id: data.job!.id })}>Cancel sign-in</button>}
      </div>}
      {data && (!data.client.ready || changingClient) && <div className="google-client-setup">
        <h3>One-time Google setup</h3>
        <p>Google requires a Desktop app OAuth client. Create one for HANNI, enable the APIs you want, and download its JSON file. If your project is in testing, add your Google email as a test user.</p>
        <div className="google-account-actions">
          <button type="button" disabled={blocked} onClick={() => void act("open_setup", {})}>Open Google setup</button>
          <button type="button" disabled={blocked} onClick={() => upload.current?.click()}>Choose client JSON</button>
          {changingClient && <button type="button" className="text-link" onClick={() => setChangingClient(false)}>Cancel</button>}
        </div>
      </div>}
      <input ref={upload} className="sr-only" type="file" accept=".json,application/json" tabIndex={-1} aria-label="Google OAuth Desktop client JSON" onChange={(event) => { void importFile(event.target.files?.[0]); event.target.value = ""; }} />
      {data?.available && (!data.accounts.length || editor) && <form className="google-account-form" onSubmit={submit}>
        <h3>{form.replace ? "Reconnect Google account" : "Add a Google account"}</h3>
        <label htmlFor="google-account-label">Account name</label>
        <input id="google-account-label" value={form.account} maxLength={32} pattern="[a-z][a-z0-9_-]{0,31}" required placeholder="personal or work" disabled={blocked || form.replace} onChange={(event) => setEditor({ ...form, account: event.target.value })} aria-describedby="google-account-label-help" />
        <p id="google-account-label-help" className="subtle">A local name for this account. Choose the email address in Google’s sign-in screen.</p>
        <fieldset disabled={blocked}>
          <legend>Services to connect</legend>
          <div className="google-service-choices">{services.map(([service, label]) => <label key={service}>
            <input type="checkbox" checked={form.capabilities.some((value) => value.startsWith(service + "."))} onChange={(event) => toggleService(service, event.target.checked)} />{label}
          </label>)}</div>
          <label className="google-write-choice"><input type="checkbox" checked={writes} disabled={!form.capabilities.some((value) => /^(calendar|tasks)\./.test(value))} onChange={(event) => setEditor({ ...form, capabilities: form.capabilities.map((value) => /^(calendar|tasks)\./.test(value) ? value.split(".")[0] + (event.target.checked ? ".write" : ".read") : value) })} />Allow calendar and task changes</label>
        </fieldset>
        <p className="subtle">Read-only by default. Gmail sends and Drive document edits are not supported. HANNI’s Tool access setting also applies to agent actions.</p>
        {form.replace && <p className="subtle">Reconnect retains existing Google grants and adds selected services. Disconnect and revoke access in Google to remove a grant.</p>}
        <div className="google-account-actions">
          <button type="submit" disabled={blocked || !data.client.ready || !form.capabilities.length}>Sign in with Google</button>
          {editor && data.accounts.length > 0 && <button type="button" className="text-link" disabled={busy} onClick={() => setEditor(null)}>Cancel</button>}
        </div>
      </form>}
      {data?.accounts.length && !editor ? <button type="button" disabled={blocked} onClick={() => setEditor({ account: data.next_label, capabilities: ["calendar.read", "gmail.read"], replace: false, revision: "missing" })}>Add Google account</button> : null}
      {data?.client.ready && !changingClient && <p className="subtle google-client-status">Google client configured. <button type="button" className="text-link" disabled={blocked} onClick={() => setChangingClient(true)}>Change client</button></p>}
      <p className="subtle">Google sign-in opens in your system browser. Account tokens are saved in Windows Credential Manager; this screen never asks for your Google password.</p>
    </div>
  );
}
