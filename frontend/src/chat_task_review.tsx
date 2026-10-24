import { useEffect, useRef, useState } from "react";
import { write } from "./api";
import { ChatIcon } from "./chat_app";
import { actionState, canDecide, reviewDecision, taskState, terminalTask, type ReviewAction, type ReviewTask } from "./task_review";

export function ChatTaskReview({ task, token, error, refresh, openTasks }: {
  task: ReviewTask; token: string; error: string; refresh: () => void; openTasks: () => void;
}) {
  const actions = task.actions || [];
  const pending = actions.some(action => action.state === "pending") && !terminalTask(task.state);
  const [open, setOpen] = useState(pending), [busy, setBusy] = useState(false);
  const [note, setNote] = useState(""), [failure, setFailure] = useState("");
  const [now, setNow] = useState(Date.now() / 1000);
  const lock = useRef(false), seenPending = useRef("");
  const [decided, setDecided] = useState<Record<string, string>>({});
  const current = useRef({ task, token, error });
  current.current = { task, token, error };
  const pendingIds = actions.filter(action => action.state === "pending").map(action => action.id).join(",");
  useEffect(() => {
    if (pending && pendingIds !== seenPending.current) setOpen(true);
    seenPending.current = pendingIds;
    if (!pending) return;
    const timer = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(timer);
  }, [pending, pendingIds]);
  useEffect(() => {
    if (actions.some(action => decided[action.id] && action.receipt)) setNote("");
  }, [actions, decided]);

  async function decide(action: ReviewAction, state: "dispatching" | "rejected") {
    if (lock.current) return;
    const latest = current.current;
    if (!latest.token || latest.error || latest.task.id !== task.id
      || !latest.task.actions?.some(item => item.id === action.id && item.review_hash === action.review_hash)) return;
    lock.current = true; setBusy(true); setNote(""); setFailure("");
    try {
      const body = reviewDecision(latest.task, action, state, Date.now() / 1000);
      const result = await write<{ state?: string; error?: string }>(
        `/api/bridge/action/${encodeURIComponent(action.id)}`, latest.token, body);
      if (result.error) throw new Error(result.error);
      if (current.current.token !== latest.token || current.current.task.id !== task.id) return;
      if (result.state !== state) throw new Error("The decision was not confirmed. Refresh to check the task.");
      setDecided(values => ({ ...values, [action.id]: action.review_hash! }));
      setNote(state === "dispatching" ? "Approved. Waiting for the tool’s execution receipt." : "Request denied. Hanni can continue with this result.");
    } catch (error) {
      if (current.current.token === latest.token && current.current.task.id === task.id)
        setFailure(error instanceof Error ? error.message : "Decision unavailable. Refresh to check its state.");
    } finally {
      lock.current = false; setBusy(false); refresh();
    }
  }

  return <details className="hc-task-review" open={open}>
    <summary onClick={event => { event.preventDefault(); setOpen(value => !value); }}>
      <ChatIcon name="tools" />
      <strong>Task review</strong><span>{taskState(task.state)}</span>
      <ChatIcon name="chevron" />
    </summary>
    <div className="hc-task-review-body">
      <p className="hc-task-review-intro">{actions.length ? `${actions.length} tool request${actions.length === 1 ? "" : "s"} recorded.` : "No tool actions recorded for this response."}</p>
      {error && <p className="hc-error-text" role="alert">Task details could not refresh: {error}. Refresh before deciding.</p>}
      {task.error && <p className="hc-error-text">{task.error}</p>}
      <ol className="hc-task-actions" aria-label="Task tool requests">
        {actions.map(action => {
          const allowed = !!token && !error && !busy && decided[action.id] !== action.review_hash && canDecide(task, action, now);
          return <li key={action.id}>
            <div className="hc-task-action-heading"><strong>{action.spec.name.replace(/^local_/, "").replaceAll("_", " ")}</strong>
              <span>{actionState(action, now)}</span></div>
            {action.state === "pending" && !terminalTask(task.state) && <>
              {["local", "mcp"].includes(action.spec.target || "") ? <div className="hc-task-decisions">
                <button type="button" disabled={!allowed} onClick={() => decide(action, "rejected")} aria-label={`Deny ${action.spec.name}`}>Deny</button>
                <button type="button" className="hc-task-approve" disabled={!allowed} onClick={() => decide(action, "dispatching")} aria-label={`Approve ${action.spec.name}`}>Approve</button>
              </div> : <p>This action is reviewed through its connected HANNI controller.</p>}
              {action.expires != null && now >= action.expires && <p>Approval expired. This request cannot execute without a new approval request.</p>}
            </>}
            <details open={action.state === "pending" || undefined} className="hc-task-action-arguments">
              <summary>Tool and arguments</summary>
              <p><code>{action.spec.name}</code> · {action.spec.target || "Unknown connection"}</p>
              <pre>{JSON.stringify(action.arguments || {}, null, 2)}</pre>
            </details>
            {action.receipt && <div className="hc-task-receipt">
              {action.receipt.message && <p>{action.receipt.message}</p>}
              {action.receipt.error && <p className="hc-error-text">{action.receipt.error}</p>}
              <details><summary>Execution receipt</summary><pre>{JSON.stringify(action.receipt, null, 2)}</pre></details>
            </div>}
          </li>;
        })}
      </ol>
      {note && <p className="hc-task-feedback" role="status">{note}</p>}
      {failure && <p className="hc-error-text" role="alert">{failure}</p>}
      <div className="hc-task-review-footer">
        <button type="button" className="hc-text-button" onClick={refresh} disabled={busy}>Refresh task</button>
        <button type="button" className="hc-text-button" onClick={openTasks}>Open agent tools</button>
        <span title={task.id}>Task {task.id.slice(0, 8)}</span>
      </div>
    </div>
  </details>;
}
