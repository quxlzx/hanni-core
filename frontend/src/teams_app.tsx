import { useEffect, useState, type FormEvent } from "react";
import { app } from "@microsoft/teams-js";
import { ChatApp } from "./chat_app";
import { request, setTeamsSession } from "./api";
import "./teams_app.css";

const storageKey = "hanni-teams-session";
function storedSession() {
  try { return sessionStorage.getItem(storageKey) || ""; } catch { return ""; }
}
function saveSession(value: string) {
  setTeamsSession(value);
  try {
    if (value) sessionStorage.setItem(storageKey, value);
    else sessionStorage.removeItem(storageKey);
  } catch { /* The current tab can still use the in-memory session. */ }
}

export function TeamsApp() {
  const [ready, setReady] = useState(false), [connected, setConnected] = useState(false);
  const [code, setCode] = useState(""), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const [sdkError, setSdkError] = useState("");
  useEffect(() => {
    let live = true;
    const disconnected = () => { saveSession(""); setConnected(false); setError("This tab was disconnected. Restart START_TEAMS.cmd for a new pairing code."); };
    window.addEventListener("hanni:teams-disconnected", disconnected);
    async function start() {
      if (window.parent !== window) {
        try {
          await app.initialize();
          await app.notifySuccess();
        } catch {
          if (live) setSdkError("Teams could not initialize this tab. Reload it in Teams, or open the tab address in your browser to check the local connection.");
        }
      }
      const session = storedSession();
      if (session) {
        setTeamsSession(session);
        try {
          await request("/api/teams/session");
          if (live) setConnected(true);
        } catch {
          saveSession("");
        }
      }
      if (live) setReady(true);
    }
    void start();
    return () => { live = false; window.removeEventListener("hanni:teams-disconnected", disconnected); };
  }, []);
  async function connect(event: FormEvent) {
    event.preventDefault();
    if (busy || !code.trim()) return;
    setBusy(true); setError("");
    try {
      const result = await request<{ session: string }>("/api/teams/pair", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: code.trim() }),
      });
      saveSession(result.session); setCode(""); setConnected(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not connect. Check the pairing code and try again.");
    } finally { setBusy(false); }
  }
  async function disconnect() {
    if (busy) return;
    setBusy(true); setError("");
    try {
      await request("/api/teams/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      saveSession(""); setConnected(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not disconnect. Stop START_TEAMS.cmd to revoke all tab access.");
    } finally { setBusy(false); }
  }
  return (
    <div className="teams-host">
      <header className="teams-connection-bar">
        <span>HANNI in Teams · This computer</span>
        {connected && <button onClick={disconnect} disabled={busy}>{busy ? "Disconnecting…" : "Disconnect tab"}</button>}
      </header>
      {sdkError && <p className="teams-connection-error" role="alert">{sdkError}</p>}
      {connected ? <>
        {error && <p className="teams-connection-error" role="alert">{error}</p>}
        <div className="teams-content"><ChatApp /></div>
      </> : <main className="teams-pairing">
        <h1>Connect HANNI on this computer</h1>
        <p>Start HANNI, then open <code>START_TEAMS.cmd</code>. Enter the pairing code shown by that launcher to access your existing conversations, files and tasks.</p>
        <form onSubmit={connect} aria-busy={busy}>
          <label htmlFor="teams-pairing-code">Pairing code</label>
          <input id="teams-pairing-code" type="password" autoComplete="off" value={code} maxLength={100}
            disabled={!ready || busy} onChange={(event) => setCode(event.target.value)} required />
          <button type="submit" disabled={!ready || busy || !code.trim()}>{busy ? "Connecting…" : "Connect HANNI"}</button>
        </form>
        {!ready && <p role="status">Connecting to the Teams host…</p>}
        {error && <p className="teams-connection-error" role="alert">{error}</p>}
        <p className="subtle">This personal tab works on the PC running HANNI. Pairing gives it access to your assistant. Closing Teams leaves HANNI and scheduled tasks running. Use HANNI’s Notifications inbox to review task updates.</p>
      </main>}
    </div>
  );
}
