import { useEffect, useState } from "react";
import {
  usePrivateResource,
  consumeInspection,
  type AgentsData,
} from "./feature_types";
import type { ScreenContext } from "./screens";
import "./activity.css";
import { ExecutionTracePanel } from "./execution_trace";

export function ActivityPage({
  view,
  context: c,
}: {
  view: "agents" | "activity";
  context: ScreenContext;
}) {
  const resource = usePrivateResource<AgentsData>(
    "/api/agents",
    c.chat.error ? "" : c.chat.data?.token || "",
    2500,
  );
  const [search, setSearch] = useState(""),
    [status, setStatus] = useState("all");
  const [capabilityPage, setCapabilityPage] = useState(0);
  const data = resource.data;
  const [inspectionNotice, setInspectionNotice] = useState("");
  useEffect(() => {
    if (!data) return;
    const target = consumeInspection("activity");
    if (!target) return;
    setSearch("");
    setStatus("all");
    const event = data.executions.find(
      (row) => `${row.timestamp}:${row.tool}:${row.status}` === target,
    );
    if (!event) {
      setInspectionNotice(
        "This execution is outside the loaded audit window. The notification remains in history.",
      );
      return;
    }
    setInspectionNotice("");
    requestAnimationFrame(() => {
      for (const element of document.querySelectorAll<HTMLDetailsElement>(
        ".execution-record",
      )) {
        if (element.dataset.executionKey === target) {
          element.open = true;
          element.scrollIntoView({ block: "center" });
          element.querySelector("summary")?.focus();
          break;
        }
      }
    });
  }, [data]);
  const executions = (data?.executions || []).filter(
    (event) =>
      (status === "all" || status === event.status) &&
      `${event.tool} ${event.summary || ""}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const capabilities = (data?.capabilities || []).filter((cap) =>
    cap.name.toLowerCase().includes(search.toLowerCase()),
  );
  const capabilityPageSize = 6;
  const lastCapabilityPage = Math.max(
    0,
    Math.ceil(capabilities.length / capabilityPageSize) - 1,
  );
  const currentCapabilityPage = Math.min(capabilityPage, lastCapabilityPage);
  const visibleCapabilities = capabilities.slice(
    currentCapabilityPage * capabilityPageSize,
    (currentCapabilityPage + 1) * capabilityPageSize,
  );
  return (
    <div className="activity-page">
      <header className="screen-heading">
        <div>
          <h1>{view === "agents" ? "Agents" : "Activity"}</h1>
          <p>Controller capabilities and recorded executions</p>
        </div>
        <button className="text-link" onClick={resource.refresh}>
          Refresh activity
        </button>
      </header>
      {resource.error && (
        <p className="feature-error" role="status">
          {resource.error} {data && "Displayed records may be stale."}
        </p>
      )}
      {inspectionNotice && (
        <p className="feature-error" role="status">
          {inspectionNotice}
        </p>
      )}
      {!data ? (
        <div
          className="skeleton-group"
          role="status"
          aria-label="Loading activity"
        >
          <span className="skeleton" />
          <span className="skeleton medium" />
        </div>
      ) : !data.available ? (
        <p className="feature-empty">
          {data.reason || "Activity is unavailable in this session."}
        </p>
      ) : (
        <>
          {view === "agents" && (
            <>
              <section
                className="controller-list"
                aria-label="Registered controllers"
              >
                {data.agents.map((agent) => (
                  <div key={agent.id}>
                    <span className="controller-mark" aria-hidden="true">
                      h.
                    </span>
                    <div>
                      <h2>{agent.name}</h2>
                      <p>
                        {agent.kind} · {agent.model || "Model not reported"}
                      </p>
                    </div>
                    <span>{agent.status}</span>
                    <small>{agent.capability_count} capabilities</small>
                  </div>
                ))}
              </section>
              <div className="activity-metrics">
                <span>
                  <strong>{data.active_tasks.length}</strong> active or queued
                </span>
                <span>
                  <strong>
                    {
                      data.executions.filter(
                        (event) => event.status === "completed",
                      ).length
                    }
                  </strong>{" "}
                  completed in history
                </span>
                <span>
                  <strong>
                    {
                      data.executions.filter(
                        (event) => event.status === "failed",
                      ).length
                    }
                  </strong>{" "}
                  failed in history
                </span>
                <span>
                  Approval queue:{" "}
                  {data.approvals_available
                    ? data.awaiting_approvals.length
                    : "Not exposed"}
                </span>
              </div>
              <p className="feature-note">
                This panel shows HANNI's conversation controller. Inspect
                persistent workflow execution and approvals in Workflows.
              </p>
              {data.active_tasks.length > 0 && (
                <section className="active-executions">
                  <h2>Current work</h2>
                  {data.active_tasks.map((task) => (
                    <div key={task.id}>
                      <strong>{task.status}</strong>
                      <span>{task.source}</span>
                      <time>
                        {new Date(task.started_at * 1000).toLocaleTimeString()}
                      </time>
                    </div>
                  ))}
                  <p className="feature-note">
                    Work status is read-only. Use the Voice panel to interrupt
                    supported voice responses.
                  </p>
                </section>
              )}
            </>
          )}
          <div className="feature-toolbar">
            <input
              type="search"
              aria-label="Search activity and capabilities"
              placeholder="Search capability or execution"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setCapabilityPage(0);
              }}
            />
            <select
              aria-label="Filter execution status"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="all">All executions</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <div className={view === "agents" ? "activity-columns" : ""}>
            {view === "agents" && (
              <section className="capability-list">
                <div className="section-title">
                  <h2>Available capabilities</h2>
                  <span>{capabilities.length}</span>
                </div>
                {capabilities.length ? (
                  visibleCapabilities.map((cap) => (
                    <div key={cap.name}>
                      <strong>{cap.name}</strong>
                      <span>Permission {cap.permission_level}</span>
                      <span>Risk {cap.risk_level}</span>
                    </div>
                  ))
                ) : (
                  <p className="feature-empty">No matching capabilities.</p>
                )}
                {capabilities.length > capabilityPageSize && (
                  <nav
                    className="capability-pagination"
                    aria-label="Capability pages"
                  >
                    <button
                      className="text-link"
                      aria-label="Previous capabilities"
                      disabled={currentCapabilityPage === 0}
                      onClick={() =>
                        setCapabilityPage(currentCapabilityPage - 1)
                      }
                    >
                      Previous
                    </button>
                    <span>
                      {currentCapabilityPage * capabilityPageSize + 1}–
                      {Math.min(
                        (currentCapabilityPage + 1) * capabilityPageSize,
                        capabilities.length,
                      )}{" "}
                      of {capabilities.length}
                    </span>
                    <button
                      className="text-link"
                      aria-label="Next capabilities"
                      disabled={currentCapabilityPage === lastCapabilityPage}
                      onClick={() =>
                        setCapabilityPage(currentCapabilityPage + 1)
                      }
                    >
                      Next
                    </button>
                  </nav>
                )}
                <p className="feature-note">
                  Permission and risk levels are checked when a request runs.
                </p>
              </section>
            )}
            <section className="execution-list">
              {view === "activity" && (
                <ExecutionTracePanel
                  token={c.chat.error ? "" : c.chat.data?.token || ""}
                />
              )}
              <div className="section-title">
                <h2>Execution history</h2>
                <span>Loaded audit window</span>
              </div>
              {executions.length ? (
                executions.map((event) => (
                  <details
                    className="execution-record"
                    data-execution-key={`${event.timestamp}:${event.tool}:${event.status}`}
                    key={`${event.timestamp}-${event.id}-${event.tool}`}
                  >
                    <summary>
                      <span className={`event-status ${event.status}`}>
                        {event.status}
                      </span>
                      <strong>{event.tool}</strong>
                      <time title={new Date(event.timestamp).toLocaleString()}>
                        {new Date(event.timestamp).toLocaleString([], {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </time>
                      <span>
                        {event.duration_ms == null
                          ? "Duration unavailable"
                          : `${event.duration_ms.toFixed(0)} ms`}
                      </span>
                    </summary>
                    <div className="execution-record-body">
                      <dl>
                        <div>
                          <dt>Recorded</dt>
                          <dd>{new Date(event.timestamp).toLocaleString()}</dd>
                        </div>
                        <div>
                          <dt>Selected capability</dt>
                          <dd>{event.tool}</dd>
                        </div>
                        <div>
                          <dt>Confirmation</dt>
                          <dd>
                            {event.confirmed
                              ? "Confirmation recorded"
                              : "No confirmation flag recorded"}
                          </dd>
                        </div>
                        <div>
                          <dt>Result</dt>
                          <dd>{event.summary || "No summary recorded"}</dd>
                        </div>
                        <div>
                          <dt>Source</dt>
                          <dd>{event.source || "Not reported"}</dd>
                        </div>
                      </dl>
                      {event.error && <p className="error">{event.error}</p>}
                      <p className="feature-note">
                        Request correlation and intermediate approval timestamps
                        are not recorded in this audit.
                      </p>
                      <details>
                        <summary>Technical details</summary>
                        <pre>{JSON.stringify(event.arguments, null, 2)}</pre>
                      </details>
                    </div>
                  </details>
                ))
              ) : (
                <p className="feature-empty">
                  {search || status !== "all"
                    ? "No executions match this filter."
                    : "No tool executions recorded yet."}
                </p>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
