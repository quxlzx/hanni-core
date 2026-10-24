import { useEffect, useState } from "react";
import { usePrivateResource } from "./feature_types";
import { traceLabel, type ExecutionData } from "./execution_types";
import "./execution_trace.css";
import { ActivityChevron, ActivityStatus } from "./activity_runs";
import { capabilityLabel } from "./activity_format";

export function ExecutionTracePanel({ token, refreshSignal = 0 }: { token: string; refreshSignal?: number }) {
  const resource = usePrivateResource<ExecutionData>(
    "/api/executions?limit=50",
    token,
    2500,
  );
  useEffect(() => { if (refreshSignal) resource.refresh(); }, [refreshSignal, resource.refresh]);
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState("all");
  const tasks = (resource.data?.tasks || []).filter(
    (task) =>
      (filter === "all" || task.execution_status === filter) &&
      `${task.request_id} ${task.task_id} ${task.selected_capabilities.join(" ")} ${task.source}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <section className="execution-traces" aria-label="Task execution traces">
      <div className="section-title">
        <h2>Controller evidence checks</h2>
        <span>{resource.data?.tasks.length || 0} recently loaded</span>
      </div>
      <p className="feature-note">
        See which controller outcomes were checked and what each check covers.
        Execution status and verification are recorded separately.
      </p>
      {resource.error && (
        <p role="status" className="feature-error">
          {resource.error} {resource.data && "Displayed traces may be stale."}
        </p>
      )}
      {resource.data && !resource.data.available && (
        <p className="feature-error" role="status">
          {resource.data.reason || "Execution traces are unavailable."}
        </p>
      )}
      <div className="feature-toolbar">
        <input
          aria-label="Search execution traces"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Capability, request ID or source"
        />
        <select
          aria-label="Filter task execution outcome"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        >
          <option value="all">All task outcomes</option>
          <option value="succeeded">Execution succeeded</option>
          <option value="partial">Partially completed</option>
          <option value="waiting_approval">Waiting for approval</option>
          <option value="failed">Failed</option>
          <option value="rejected">Rejected</option>
          <option value="cancelled">Cancelled</option>
          <option value="timed_out">Timed out</option>
        </select>
        <span className="subtle">{tasks.length} loaded</span>
      </div>
      {!resource.data && !resource.error ? (
        <div
          className="skeleton-group"
          role="status"
          aria-label="Loading task traces"
        >
          <span className="skeleton" />
          <span className="skeleton medium" />
        </div>
      ) : !tasks.length ? (
        <p className="feature-empty">
          {resource.error && !resource.data
            ? "Evidence checks could not be loaded. Refresh when the connection is available."
            : resource.data?.available === false
              ? "Evidence history is unavailable. Existing records were retained."
              : search || filter !== "all"
                ? "No evidence checks match this filter."
                : "No controller evidence checks recorded yet. View Agent runs for native-agent progress and tool receipts."}
        </p>
      ) : (
        tasks.map((task) => (
          <details
            className="trace-record activity-run"
            key={task.task_id}
            data-task-id={task.task_id}
          >
            <summary>
              <div className="activity-run-main">
                <strong className="activity-run-title">{task.selected_capabilities.map(capabilityLabel).join(", ") || "No tool execution"}</strong>
                <div className="activity-run-meta"><ActivityStatus state={task.execution_status} label={traceLabel(task.execution_status)} />
                  <span className="trace-verification">{task.verification_status === "UNVERIFIED" ? "Outcome not verified" : traceLabel(task.verification_status)}</span></div>
              </div>
              <time dateTime={task.created_at} title={new Date(task.created_at).toLocaleString()}>
                {new Date(task.created_at).toLocaleString([], {
                  month: "short", day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </time>
              <span className="activity-duration">{task.steps.length} {task.steps.length === 1 ? "step" : "steps"}</span>
              <ActivityChevron />
            </summary>
            <div className="trace-body">
              <p>{task.summary}</p>
              <dl className="trace-facts">
                <div>
                  <dt>Source</dt>
                  <dd>{task.source}</dd>
                </div>
                <div>
                  <dt>Retries</dt>
                  <dd>{task.retry_count}</dd>
                </div>
                <div>
                  <dt>Completed</dt>
                  <dd>
                    {task.completed_at
                      ? new Date(task.completed_at).toLocaleString()
                      : "Not completed"}
                  </dd>
                </div>
              </dl>
              {task.error_class && (
                <p className="feature-note">
                  Recorded error: {traceLabel(task.error_class)}
                </p>
              )}
              {task.truncated_steps && (
                <p className="feature-error">
                  Step details reached their limit. This task cannot be treated
                  as fully verified.
                </p>
              )}
              {task.steps.map((step) => (
                <div className="trace-step" key={step.step_id}>
                  <div className="trace-step-heading">
                    <strong>{capabilityLabel(step.capability_id)}</strong>
                    <span>{traceLabel(step.state)}</span>
                    <span>{traceLabel(step.approval)}</span>
                  </div>
                  <details className="trace-lifecycle"><summary>Step timeline</summary><ol
                    className="trace-timeline"
                    aria-label={`Lifecycle for ${step.capability_id}`}
                  >
                    {step.events.map((event, index) => (
                      <li key={`${event.timestamp}-${index}`}>
                        <span>{traceLabel(event.state)}</span>
                        <time>
                          {new Date(event.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                          })}
                        </time>
                      </li>
                    ))}
                  </ol></details>
                  {step.verification && (
                    <div className="trace-evidence">
                      <span>
                        {traceLabel(step.verification.status)} ·{" "}
                        {traceLabel(step.verification.method)}
                      </span>
                      <strong>
                        Scope: {traceLabel(step.verification.scope)}
                      </strong>
                      <span>
                        {step.verification.independent
                          ? "Separate state check"
                          : "Tool result evidence; no independent state check"}
                      </span>
                      <ul>
                        {Object.entries(step.verification.checks).map(
                          ([key, value]) => (
                            <li key={key}>
                              {traceLabel(key)}: {value ? "Yes" : "No"}
                            </li>
                          ),
                        )}
                      </ul>
                    </div>
                  )}
                  {step.error_class && (
                    <p className="feature-note">
                      {traceLabel(step.error_class)}
                      {step.superseded
                        ? " · Earlier confirmation request; a later decision is recorded."
                        : ""}
                    </p>
                  )}
                </div>
              ))}
              <details className="trace-technical">
                <summary>Trace metadata</summary>
                <p className="feature-note">
                  Private requests, arguments, tool contents and hidden
                  reasoning are not recorded.
                </p>
                <pre>
                  {JSON.stringify(
                    {
                      task_id: task.task_id,
                      request_id: task.request_id,
                      selected_capabilities: task.selected_capabilities,
                      candidate_capabilities: task.candidate_capabilities || [],
                      events: task.events,
                    },
                    null,
                    2,
                  )}
                </pre>
              </details>
            </div>
          </details>
        ))
      )}
    </section>
  );
}
