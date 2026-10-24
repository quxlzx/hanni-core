import { useEffect, useState } from "react";
import { usePrivateResource, consumeInspection, type AgentsData } from "./feature_types";
import type { ScreenContext } from "./screens";
import type { ToolEvent } from "./types";
import { ExecutionTracePanel } from "./execution_trace";
import { NativeActivity, ActivityChevron, ActivityStatus } from "./activity_runs";
import { activityDuration, capabilityLabel } from "./activity_format";
import "./activity.css";

const views = [{ id: "runs", label: "Agent runs" }, { id: "tools", label: "Tool history" }, { id: "checks", label: "Evidence checks" }] as const;
type ActivityView = (typeof views)[number]["id"];

export function ActivityPage({ view, context: c }: { view: "agents" | "activity"; context: ScreenContext }) {
  const token = c.chat.error || c.stopping ? "" : c.chat.data?.token || "";
  const resource = usePrivateResource<AgentsData>("/api/agents", token, 2500);
  const [tab, setTab] = useState<ActivityView>("runs");
  const [search, setSearch] = useState(""), [status, setStatus] = useState("all");
  const [capabilityPage, setCapabilityPage] = useState(0), [refreshSignal, setRefreshSignal] = useState(0);
  const [inspectionNotice, setInspectionNotice] = useState("");
  const data = resource.data;
  useEffect(() => {
    if (!data) return;
    const target = consumeInspection("activity");
    if (!target) return;
    setTab("tools"); setSearch(""); setStatus("all");
    if (!data.executions.some(row => `${row.timestamp}:${row.tool}:${row.status}` === target)) {
      setInspectionNotice("This tool call is outside the recent history window. Its notification remains saved."); return;
    }
    setInspectionNotice("");
    requestAnimationFrame(() => {
      for (const element of document.querySelectorAll<HTMLDetailsElement>(".execution-record")) {
        if (element.dataset.executionKey === target) {
          element.open = true; element.scrollIntoView({ block: "center" }); element.querySelector("summary")?.focus(); break;
        }
      }
    });
  }, [data]);
  const executions = (data?.executions || []).filter(event => (status === "all" || status === event.status)
    && `${event.tool} ${capabilityLabel(event.tool)} ${event.summary || ""} ${event.source || ""} ${event.error || ""}`.toLowerCase().includes(search.trim().toLowerCase()));
  const capabilities = (data?.capabilities || []).filter(cap => cap.name.toLowerCase().includes(search.toLowerCase()));
  const currentPage = Math.min(capabilityPage, Math.max(0, Math.ceil(capabilities.length / 6) - 1));
  const refresh = () => { resource.refresh(); setRefreshSignal(value => value + 1); };
  return <div className={`activity-page ${view === "activity" ? "activity-log-page" : "activity-agents-page"}`}>
    <header className="screen-heading"><div><h1>{view === "activity" ? "Activity" : "Agents"}</h1><p>{view === "activity" ? "Follow Hanni's work, inspect tool results and check the evidence." : "Connected controllers and the capabilities available to them."}</p></div><button type="button" className="activity-refresh" disabled={!token} onClick={refresh}><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2 6M20 4v7h-7" /></svg>Refresh activity</button></header>
    {inspectionNotice && <p className="feature-error" role="status">{inspectionNotice}</p>}
    {view === "activity" && <div role="tablist" className="activity-tabs" aria-label="Activity history">{views.map((item, index) => <button type="button" role="tab" id={`activity-tab-${item.id}`} key={item.id} aria-selected={tab === item.id} aria-controls={`activity-panel-${item.id}`} tabIndex={tab === item.id ? 0 : -1} onClick={() => setTab(item.id)} onKeyDown={event => {
      const next = event.key === "ArrowRight" ? (index + 1) % views.length : event.key === "ArrowLeft" ? (index + views.length - 1) % views.length : event.key === "Home" ? 0 : event.key === "End" ? views.length - 1 : -1;
      if (next >= 0) { event.preventDefault(); setTab(views[next].id); document.getElementById(`activity-tab-${views[next].id}`)?.focus(); }
    }}>{item.label}</button>)}</div>}
    {view === "activity" && <div role="tabpanel" id="activity-panel-runs" aria-labelledby="activity-tab-runs" hidden={tab !== "runs"} tabIndex={0}><NativeActivity token={token} refreshSignal={refreshSignal} /></div>}
    {view === "activity" && <div role="tabpanel" id="activity-panel-checks" aria-labelledby="activity-tab-checks" hidden={tab !== "checks"} tabIndex={0}><ExecutionTracePanel token={token} refreshSignal={refreshSignal} /></div>}
    {view === "agents" && data?.available && <>
      <section className="controller-list" aria-label="Registered controllers">{data.agents.map(agent => <div key={agent.id}><span className="controller-mark" aria-hidden="true">h.</span><div><h2>{agent.name}</h2><p>{agent.kind} · {agent.model || "Model not reported"}</p></div><ActivityStatus state={agent.status} label={agent.status} /><small>{agent.capability_count} capabilities</small></div>)}</section>
      <div className="activity-metrics"><span><strong>{data.active_tasks.length}</strong> active or queued</span><span><strong>{data.executions.filter(event => event.status === "completed").length}</strong> completed tool calls</span><span><strong>{data.executions.filter(event => event.status === "failed").length}</strong> failed tool calls</span></div>
      {data.active_tasks.length > 0 && <section className="active-executions"><h2>Current conversation work</h2>{data.active_tasks.map(task => <div key={task.id}><strong>{task.status}</strong><span>{task.source}</span><time>{new Date(task.started_at * 1000).toLocaleTimeString()}</time></div>)}</section>}
    </>}
    <div className={view === "agents" ? "activity-columns" : ""}>
      {view === "agents" && <section className="capability-list"><div className="section-title"><h2>Available capabilities</h2><span>{capabilities.length}</span></div><label className="activity-capability-search" htmlFor="activity-capability-search">Find a capability<input id="activity-capability-search" type="search" value={search} placeholder="Search capability names" onChange={event => { setSearch(event.target.value); setCapabilityPage(0); }} /></label>{capabilities.slice(currentPage * 6, (currentPage + 1) * 6).map(cap => <div key={cap.name}><strong>{cap.name}</strong><span>Permission {cap.permission_level}</span><span>Risk {cap.risk_level}</span></div>)}{!capabilities.length && <p className="feature-empty">No matching capabilities.</p>}{capabilities.length > 6 && <nav className="capability-pagination" aria-label="Capability pages"><button className="text-link" aria-label="Previous capabilities" disabled={currentPage === 0} onClick={() => setCapabilityPage(currentPage - 1)}>Previous</button><span>{currentPage * 6 + 1}–{Math.min((currentPage + 1) * 6, capabilities.length)} of {capabilities.length}</span><button className="text-link" aria-label="Next capabilities" disabled={(currentPage + 1) * 6 >= capabilities.length} onClick={() => setCapabilityPage(currentPage + 1)}>Next</button></nav>}<p className="feature-note">Permission and risk levels are checked when a request runs.</p></section>}
      <section role={view === "activity" ? "tabpanel" : undefined} id="activity-panel-tools" aria-labelledby={view === "activity" ? "activity-tab-tools" : undefined} hidden={view === "activity" && tab !== "tools"} tabIndex={0} className="execution-list">
        <div className="activity-section-heading"><div><h2>Recent tool calls</h2><p>Individual calls recorded by Hanni's controller, including desktop controls and connected services.</p></div><span className="activity-window-note">{data?.executions.length || 0} recently loaded</span></div>
        {resource.error && <p className="feature-error" role="status">{resource.error} {data && "Showing the last loaded records."}</p>}
        <div className="activity-filters"><label className="activity-search" htmlFor="activity-tool-search">Find a tool call<input id="activity-tool-search" type="search" placeholder="Search tool names, results or sources" value={search} onChange={e => setSearch(e.target.value)} /></label><label htmlFor="activity-tool-status">Result<select id="activity-tool-status" value={status} onChange={e => setStatus(e.target.value)}><option value="all">All results</option><option value="completed">Returned successfully</option><option value="failed">Failed</option></select></label>{(search || status !== "all") && <button className="text-link" onClick={() => { setSearch(""); setStatus("all"); }}>Clear tool filters</button>}</div>
        {!data && !resource.error ? <p className="activity-empty" role="status">Loading tool history…</p> : data && !data.available ? <p className="activity-empty">{data.reason || "Tool history is unavailable in this session."}</p> : executions.length ? <><div className="activity-table-heading" aria-hidden="true"><span>Tool and result</span><span>Recorded</span><span>Run time</span><span /></div>{executions.map(event => <ToolRecord key={`${event.timestamp}-${event.id}-${event.tool}`} event={event} />)}<p className="activity-history-note">Showing {executions.length} of {data?.executions.length || 0} recent tool calls. Expand a row for its recorded result.</p></> : <div className="activity-empty"><h3>{search || status !== "all" ? "No matching tool calls" : resource.error ? "Tool history is unavailable" : "No tool calls recorded yet"}</h3><p>{search || status !== "all" ? "Try another search or clear the result filter." : resource.error ? "Refresh when the connection is available." : "Controller tool calls will appear here after they run. Native-agent tool results are also available inside Agent runs."}</p></div>}
      </section>
    </div>
  </div>;
}

function ToolRecord({ event }: { event: ToolEvent }) {
  const recorded = new Date(event.timestamp);
  const validTime = Number.isFinite(recorded.getTime());
  const summary = event.summary?.startsWith("[") ? "Result content is omitted from this activity log." : event.summary || "No result summary was recorded.";
  return <details className="execution-record activity-run" data-execution-key={`${event.timestamp}:${event.tool}:${event.status}`}>
    <summary><div className="activity-run-main"><strong className="activity-run-title">{capabilityLabel(event.tool)}</strong><div className="activity-run-meta"><ActivityStatus state={event.status} label={event.status === "completed" ? "Returned successfully" : "Failed"} /><span>{event.source || "Source not recorded"}</span></div></div><time dateTime={validTime ? recorded.toISOString() : undefined}>{validTime ? recorded.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "Time unavailable"}</time><span className="activity-duration">{activityDuration(event.duration_ms)}</span><ActivityChevron /></summary>
    <div className="execution-record-body activity-run-detail"><div className="activity-detail-heading"><h3>Recorded result</h3><ActivityStatus state={event.status} label={event.status === "completed" ? "Returned successfully" : "Failed"} /></div><p>{summary}</p>{event.error && <p className="activity-error">{event.error}</p>}<dl className="activity-facts"><div><dt>Recorded</dt><dd>{validTime ? recorded.toLocaleString() : "Not recorded"}</dd></div><div><dt>Source</dt><dd>{event.source || "Not recorded"}</dd></div><div><dt>Confirmation</dt><dd>{event.confirmed ? "Confirmation recorded" : "No confirmation flag recorded"}</dd></div></dl><details className="activity-disclosure"><summary>Technical details and arguments</summary><p className="activity-history-note">This audit does not include intermediate approval timestamps.</p><pre>{JSON.stringify({ tool: event.tool, arguments: event.arguments, duration_ms: event.duration_ms }, null, 2)}</pre></details></div>
  </details>;
}
