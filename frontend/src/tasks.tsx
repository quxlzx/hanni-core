// Tasks: native-bridge task list, approvals, and direct submission.
import { useState, type FormEvent, type ReactNode } from "react";
import { usePrivateResource } from "./feature_types";
import { write } from "./api";

function lineNodes(line: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g;
  let last = 0, m: RegExpExecArray | null, k = 0;
  while ((m = re.exec(line))) {
    if (m.index > last) parts.push(line.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) parts.push(<b key={k++}>{tok.slice(2, -2)}</b>);
    else if (tok.startsWith("`")) parts.push(<code key={k++}>{tok.slice(1, -1)}</code>);
    else {
      const lm = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/.exec(tok);
      if (lm) parts.push(<a key={k++} href={lm[2]} target="_blank" rel="noopener noreferrer">{lm[1]}</a>);
      else parts.push(tok);
    }
    last = m.index + tok.length;
  }
  if (last < line.length) parts.push(line.slice(last));
  return parts;
}

function MdText({ text }: { text: string }) {
  const lines = text.split("\n");
  return <>{lines.map((line, i) => (
    <span key={i}>{lineNodes(line)}{i < lines.length - 1 ? <br /> : null}</span>
  ))}</>;
}

type BridgeTask = {
  id: string; key: string | null; state: string; created: number;
  updated: number; error?: string | null;
};
type BridgeTasks = { tasks: BridgeTask[]; error?: string };
type BridgeAction = {
  id: string; state: string; created: number; expires: number;
  spec: { name: string; target: string };
  arguments: Record<string, unknown>;
};
type BridgeTaskDetail = BridgeTask & {
  request?: { prompt?: string };
  actions?: BridgeAction[];
  events?: { text: string; at: number }[];
  result?: { model_claims?: string; receipts?: { ok: boolean; message?: string; error?: string; approved_by?: string }[] };
};

const fmt = (seconds: number) =>
  new Date(seconds * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

export function TasksPage({ token }: { token: string }) {
  const list = usePrivateResource<BridgeTasks>("/api/bridge/tasks", token, 4000);
  const [selected, setSelected] = useState<string | null>(null);
  const detail = usePrivateResource<BridgeTaskDetail>(
    selected ? `/api/bridge/task/${selected}` : "/api/bridge/tasks", token, 3000);
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  async function act(actionId: string, body: unknown) {
    setBusy(true); setNote("");
    try {
      await write(`/api/bridge/action/${actionId}`, token, body);
      list.refresh(); detail.refresh();
    } catch (e) { setNote(e instanceof Error ? e.message : "Action failed."); }
    finally { setBusy(false); }
  }

  async function approve(actionId: string) {
    await write(`/api/bridge/action/${actionId}`, token, { state: "dispatching" }).catch(() => {});
    await act(actionId, { state: "fulfilled",
      receipt: { ok: true, message: "approved in Hanni OS", data: {} } });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!prompt.trim() || busy) return;
    setBusy(true); setNote("");
    try {
      await write("/api/bridge/submit", token, {
        key: crypto.randomUUID(),
        task: { prompt: prompt.trim(), windows_tools: [], origin: "hanni", context: {} },
      });
      setPrompt(""); list.refresh();
    } catch (e) { setNote(e instanceof Error ? e.message : "Submit failed."); }
    finally { setBusy(false); }
  }

  const tasks = list.data?.tasks ?? [];
  const pending = tasks.filter((t) => ["queued", "running", "approval"].includes(t.state));
  const done = tasks.filter((t) => !["queued", "running", "approval"].includes(t.state));
  const actions = (selected && detail.data?.id === selected ? detail.data.actions : []) ?? [];

  return (
    <div className="screen-grid">
      <section className="screen-section">
        <div className="section-title"><h2>Native tasks</h2><span>Bridge approvals and submissions</span></div>
        {list.error && <p className="error">Bridge unreachable: {list.error}</p>}
        {list.data?.error && <p className="error">{list.data.error}</p>}
        <h3 className="nav-group">Awaiting you ({pending.length})</h3>
        {pending.length ? pending.map((t) => (
          <button key={t.id} className={`task-row ${selected === t.id ? "selected" : ""}`}
            onClick={() => setSelected(t.id)}>
            <strong>{t.state}</strong><span>{fmt(t.created)}</span>
          </button>
        )) : <p className="subtle">Nothing waiting. Approvals appear here when a task requests a capability.</p>}
        <h3 className="nav-group">Recent ({done.length})</h3>
        {done.slice(0, 12).map((t) => (
          <button key={t.id} className={`task-row ${selected === t.id ? "selected" : ""}`}
            onClick={() => setSelected(t.id)}>
            <strong>{t.state}</strong><span>{fmt(t.updated)}</span>
          </button>
        ))}
      </section>
      <section className="screen-section">
        <div className="section-title"><h2>{selected ? "Task detail" : "Submit a task"}</h2></div>
        {selected && detail.data?.id === selected ? (
          <>
            <p className="subtle">{detail.data.request?.prompt?.slice(0, 400) || "No prompt recorded."}</p>
            {actions.filter((a) => a.state === "pending").map((a) => (
              <div key={a.id} className="cluster-notice" role="alert">
                <strong>{a.spec.name}</strong> ({a.spec.target}) requests approval
                <pre>{JSON.stringify(a.arguments, null, 2).slice(0, 600)}</pre>
                <div className="dialog-actions">
                  <button className="danger-button" disabled={busy}
                    onClick={() => act(a.id, { state: "rejected", receipt: { ok: false, error: "rejected in Hanni OS" } })}>
                    Deny
                  </button>
                  <button disabled={busy} onClick={() => approve(a.id)}>Approve</button>
                </div>
              </div>
            ))}
            {detail.data.result?.receipts?.length ? (
              <p className="subtle">{detail.data.result.receipts.length} receipt(s):{" "}
                {detail.data.result.receipts.map((r) => r.ok ? `ok${r.approved_by ? ` (${r.approved_by})` : ""}` : r.error || "failed").join(", ")}</p>
            ) : null}
            {detail.data.result?.model_claims ? <p className="md-text"><MdText text={detail.data.result.model_claims.slice(0, 2000)} /></p> : null}
            {detail.data.events?.length ? (
              <details><summary>Events</summary>
                {detail.data.events.slice(-12).map((e, i) => <p key={i} className="subtle">{e.text}</p>)}
              </details>
            ) : null}
          </>
        ) : (
          <form className="composer" onSubmit={submit}>
            <label htmlFor="task-prompt" className="sr-only">Task prompt</label>
            <textarea id="task-prompt" value={prompt} rows={4} maxLength={4000}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Ask the native brain to do something with its tools…" />
            <div className="composer-bottom">
              <span>Runs on the native bridge with local tools under your approval.</span>
              <button type="submit" disabled={busy || !prompt.trim()}>Submit task</button>
            </div>
          </form>
        )}
        {note && <p className="error" role="alert">{note}</p>}
      </section>
    </div>
  );
}
