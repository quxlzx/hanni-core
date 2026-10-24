import { useEffect, useState } from "react";
import { usePrivateResource } from "./feature_types";
import { actionState, taskState, terminalTask } from "./task_review";
import { activityDuration, capabilityLabel, conversationLink, runMatches, runSource, type ActivityRun } from "./activity_format";

type RunData = { tasks?: ActivityRun[]; error?: string };
const dateLabel = (seconds: number) => Number.isFinite(seconds) ? new Date(seconds * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "Time unavailable";
export function ActivityChevron() {
  return <svg className="activity-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="m9 5 7 7-7 7" /></svg>;
}
export function ActivityStatus({ state, label }: { state: string; label: string }) {
  return <span className={`activity-status activity-status-${state}`}><span aria-hidden="true" />{label}</span>;
}

export function NativeActivity({ token, refreshSignal }: { token: string; refreshSignal: number }) {
  const resource = usePrivateResource<RunData>("/api/bridge/tasks", token, 4000);
  const [search, setSearch] = useState(""), [filter, setFilter] = useState("all");
  useEffect(() => { if (refreshSignal) resource.refresh(); }, [refreshSignal, resource.refresh]);
  const runs = resource.data?.tasks || [];
  const filtered = runs.filter(run => runMatches(run, search, filter));
  const error = resource.error || resource.data?.error;
  return <section aria-labelledby="activity-runs-heading" className="activity-native">
    <div className="activity-section-heading"><div><h2 id="activity-runs-heading">Recent agent runs</h2><p>The requests Hanni is working on, with saved responses and tool results.</p></div><span className="activity-window-note">Latest {runs.length} recorded</span></div>
    {error && <p className="feature-error" role="status">Agent runs could not refresh. {runs.length ? "Showing the last loaded records." : "Check the agent connection or view the other activity tabs."}</p>}
    <div className="activity-filters">
      <label className="activity-search" htmlFor="activity-run-search">Find a run<input id="activity-run-search" type="search" placeholder="Search requests, tools or run IDs" value={search} onChange={e => setSearch(e.target.value)} /></label>
      <label htmlFor="activity-run-status">Status<select id="activity-run-status" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All statuses</option><option value="active">In progress or queued</option><option value="attention">Needs attention</option><option value="ready">Response ready</option><option value="cancelled">Cancelled</option></select></label>
      {(search || filter !== "all") && <button className="text-link" onClick={() => { setSearch(""); setFilter("all"); }}>Clear run filters</button>}
    </div>
    {!resource.data && !error ? <p className="activity-empty" role="status">Loading agent runs…</p> : !filtered.length ? <div className="activity-empty"><h3>{search || filter !== "all" ? "No matching runs" : error ? "Agent history is unavailable" : "Your activity will appear here"}</h3><p>{search || filter !== "all" ? "Try a different search or clear the status filter." : error ? "Use Refresh activity to try the connection again." : "Send Hanni a message or let a repeating task run. You can return here to see its progress and results."}</p></div> : <>
      <div className="activity-table-heading" aria-hidden="true"><span>Request and status</span><span>Started</span><span>Run time</span><span /></div>
      {filtered.map(run => <NativeRun key={run.id} run={run} token={token} />)}
      <p className="activity-history-note">Showing {filtered.length} of {runs.length} recently loaded runs. A response being ready does not verify tool effects.</p>
    </>}
  </section>;
}

function NativeRun({ run, token }: { run: ActivityRun; token: string }) {
  const [open, setOpen] = useState(false);
  const actions = run.actions || [];
  const issues = actions.filter(a => a.receipt?.ok === false || ["rejected", "uncertain"].includes(a.state)).length;
  const elapsed = run.result?.stats?.elapsed_seconds;
  const duration = activityDuration(typeof elapsed === "number" ? elapsed * 1000 : null);
  return <details className="activity-run" data-run-id={run.id} open={open} onToggle={e => setOpen(e.currentTarget.open)}>
    <summary>
      <div className="activity-run-main"><strong className="activity-run-title">{run.request?.prompt?.trim().slice(0, 180) || "Untitled agent run"}</strong><div className="activity-run-meta"><ActivityStatus state={run.state} label={taskState(run.state)} /><span>{runSource(run)}</span><span>{actions.length} tool {actions.length === 1 ? "request" : "requests"}</span>{issues > 0 && <span className="activity-tool-issue">{issues} tool {issues === 1 ? "issue" : "issues"}</span>}</div></div>
      <time dateTime={Number.isFinite(run.created) ? new Date(run.created * 1000).toISOString() : undefined}>{dateLabel(run.created)}</time>
      <span className="activity-duration" title="Elapsed time reported by the agent; not a measure of token generation speed">{duration}</span><ActivityChevron />
    </summary>
    {open && <NativeRunDetail id={run.id} initial={run} token={token} />}
  </details>;
}

function NativeRunDetail({ id, initial, token }: { id: string; initial: ActivityRun; token: string }) {
  const detail = usePrivateResource<ActivityRun>(`/api/bridge/task/${encodeURIComponent(id)}`, token, terminalTask(initial.state) ? 0 : 2500);
  const task = detail.data?.id === id ? detail.data : initial;
  const error = detail.error || (detail.data?.id !== id ? detail.data?.error : "");
  const link = conversationLink(task);
  const events = task.events || [];
  return <div className="activity-run-detail">
    <div className="activity-detail-heading"><h3>Run overview</h3>{link && <a className="activity-conversation-link" href={link}>Open conversation</a>}</div>
    {error && <p className="feature-error" role="status">The latest run details could not load. Showing the saved snapshot.</p>}
    <p className="activity-request">{task.request?.prompt || "The original request was not recorded."}</p>
    <dl className="activity-facts"><div><dt>Source</dt><dd>{runSource(task)}</dd></div><div><dt>Last updated</dt><dd>{dateLabel(task.updated)}</dd></div><div><dt>State</dt><dd>{taskState(task.state)}</dd></div></dl>
    {task.error && <p className="activity-error">{task.error}</p>}
    {task.result?.model_claims ? <details className="activity-disclosure"><summary>Saved response</summary><p className="activity-saved-response">{task.result.model_claims}</p></details> : !terminalTask(task.state) && <p className="activity-progress">{events.at(-1)?.text || "Waiting for the agent's next update."}</p>}
    <h3 className="activity-tools-heading">Tool activity <span>{task.actions?.length || 0}</span></h3>
    {task.actions?.length ? <ol className="activity-tool-list">{task.actions.map(action => <li key={action.id}><div className="activity-tool-heading"><strong>{capabilityLabel(action.spec.name)}</strong><span className={action.receipt?.ok === false ? "activity-error" : ""}>{actionState(action, Date.now() / 1000)}</span></div>{action.receipt?.message && <p>{action.receipt.message}</p>}{action.receipt?.error && <p className="activity-error">{typeof action.receipt.error === "string" ? action.receipt.error : JSON.stringify(action.receipt.error)}</p>}<details className="activity-disclosure"><summary>Tool arguments and receipt</summary><pre>{JSON.stringify({ tool: action.spec.name, connection: action.spec.target, arguments: action.arguments || {}, receipt: action.receipt || null }, null, 2)}</pre></details></li>)}</ol> : <p className="activity-history-note">No tool requests recorded for this run.</p>}
    {task.state === "approval" && <p className="activity-history-note">Review pending tool decisions in the original conversation.</p>}
    <details className="activity-disclosure"><summary>Progress timeline <span>{events.length} updates</span></summary><ol className="activity-progress-list">{events.map((event, index) => <li key={index}><time>{dateLabel(event.time ?? event.at ?? NaN)}</time><span>{event.text}</span></li>)}</ol></details>
    <details className="activity-disclosure"><summary>Technical details</summary><dl className="activity-facts"><div><dt>Run ID</dt><dd><code>{task.id}</code></dd></div><div><dt>Recorded state</dt><dd><code>{task.state}</code></dd></div></dl></details>
  </div>;
}
