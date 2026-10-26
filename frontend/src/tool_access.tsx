import { useRef, useState } from "react";
import { write } from "./api";
import { usePrivateResource } from "./feature_types";
import "./tool_access.css";

type Mode = "configured" | "read_only" | "ask" | "full";
type Access = { available: boolean; mode?: Mode; revision?: string; error?: string | null; reason?: string | null };
const labels: Record<Mode, string> = {
  configured: "Existing permissions",
  read_only: "Read only",
  ask: "Ask before writes",
  full: "Full access (read & write)",
};
const descriptions: Record<Mode, string> = {
  configured: "Keep existing task approvals, schedule permissions and MCP action reviews.",
  read_only: "Read files, search and inspect information. Block writes, terminal commands and code execution. Task progress and read-only delegation remain available.",
  ask: "Read automatically. Review and approve each write, terminal command or code execution in Task review.",
  full: "Allow the agent to read, write, run commands and use enabled MCP tools without individual action reviews.",
};

export function ToolAccessSettings({ token, disabled = false }: { token: string; disabled?: boolean }) {
  const resource = usePrivateResource<Access>("/api/tool-access", token, 5000);
  const [draft, setDraft] = useState<{ mode: Mode; revision: string } | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const lock = useRef(false);
  const pending = useRef<{ signature: string; id: string } | null>(null);
  const data = resource.data;
  const mode = draft?.mode || data?.mode || "configured";
  const stale = Boolean(draft && draft.revision !== data?.revision);
  const unavailable = disabled || !token || !data?.available || Boolean(resource.error);
  const autoApprove = mode === "full";
  function choose(next: Mode) {
    setDraft({ mode: next, revision: data?.revision || "" });
    setError(""); setNotice("");
  }
  async function save() {
    if (unavailable || busy || !draft || stale || lock.current) return;
    lock.current = true;
    setBusy(true); setError(""); setNotice("");
    const payload = { mode: draft.mode, expected_revision: draft.revision };
    const signature = JSON.stringify({ ...payload, token });
    const id = pending.current?.signature === signature ? pending.current.id : crypto.randomUUID();
    pending.current = { signature, id };
    try {
      const saved = await write<Access>("/api/tool-access", token, { id, ...payload });
      resource.setData(saved); setDraft(null); pending.current = null;
      setNotice(`${labels[payload.mode]} saved. Applies before the next tool starts; actions already running are not undone.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Tool access could not be saved. Refresh and try again.");
    } finally {
      lock.current = false; setBusy(false); resource.refresh();
    }
  }
  return (
    <div className="settings-fields" aria-busy={busy}>
      <div className="tool-auto-approve">
        <div className="tool-auto-heading">
          <div><h3>Auto-approve</h3><p>Run enabled agent tools without individual action reviews.</p></div>
          <button type="button" role="switch" aria-label="Auto-approve tool actions" aria-checked={autoApprove}
            aria-describedby="tool-auto-description" className="tool-auto-toggle" disabled={unavailable || busy}
            onClick={() => choose(autoApprove ? "ask" : "full")}>
            <span className="tool-auto-track" aria-hidden="true"><span /></span><span>{autoApprove ? "On" : "Off"}</span>
          </button>
        </div>
        <p id="tool-auto-description">On selects Full access for file writes, terminal commands, code execution and enabled MCP tools. Off selects Ask before writes; reads remain automatic. Existing permissions can still contain task-specific approvals.</p>
        {data?.mode && <p className="tool-auto-current" role="status">Saved policy: <strong>{labels[data.mode]}</strong>{data.mode === "full" ? " · Auto-approve is on." : ""}</p>}
        {draft && <p className="tool-auto-pending">Select Save tool access to apply this selection. Waiting tool requests will use the saved policy.</p>}
      </div>
      <label htmlFor="agent-tool-access">Tool access</label>
      <select id="agent-tool-access" value={mode} disabled={unavailable || busy}
        aria-describedby="agent-tool-access-description"
        onChange={(event) => choose(event.target.value as Mode)}>
        {(Object.keys(labels) as Mode[]).map((value) => <option key={value} value={value}>{labels[value]}</option>)}
      </select>
      <p id="agent-tool-access-description" className="subtle">{descriptions[mode]}</p>
      <p className="subtle">Applies to agent chat, scheduled tasks and delegated work. Disabled tools stay disabled, and file boundaries and connection permissions still apply. Direct app controls remain available.</p>
      {(!data && !resource.error) && <p role="status">Reading tool access…</p>}
      {(error || resource.error || data?.error) && <p className="error-text" role="alert">{error || resource.error || data?.error}</p>}
      {data?.reason && <p className="subtle">{data.reason}</p>}
      {stale && <p role="alert">Tool access changed elsewhere. Reset your selection to load the current setting.</p>}
      {notice && <p role="status">{notice}</p>}
      <div className="settings-actions">
        <button id="tool-access-apply" onClick={save} disabled={unavailable || busy || !draft || stale || (mode === data?.mode && !data?.error)}>
          {busy ? "Saving…" : "Save tool access"}
        </button>
        {draft && <button className="text-link" disabled={busy} onClick={() => { setDraft(null); setError(""); resource.refresh(); }}>Reset selection</button>}
      </div>
    </div>
  );
}
