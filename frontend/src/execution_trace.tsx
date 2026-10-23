import { useState } from "react";
import { usePrivateResource } from "./feature_types";
import { traceLabel, type ExecutionData } from "./execution_types";
import "./execution_trace.css";

export function ExecutionTracePanel({ token }: { token: string }) {
  const resource = usePrivateResource<ExecutionData>(
    "/api/executions?limit=50",
    token,
    2500,
  );
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
        <h2>Task outcomes</h2>
        <button className="text-link" onClick={resource.refresh}>
          Refresh task traces
        </button>
      </div>
      <p className="feature-note">
        Execution and evidence checks are recorded separately. Verification
        applies only to the stated scope.
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
            ? "Task traces could not be loaded. Refresh when the connection is available."
            : resource.data?.available === false
              ? "Task trace history is unavailable. Existing records were retained."
              : search || filter !== "all"
                ? "No task traces match this filter."
                : "No task traces recorded yet. Existing tool audit records appear below."}
        </p>
      ) : (
        tasks.map((task) => (
          <details
            className="trace-record"
            key={task.task_id}
            data-task-id={task.task_id}
          >
            <summary>
              <span className={`event-status ${task.execution_status}`}>
                {traceLabel(task.execution_status)}
              </span>
              <strong>
                {task.selected_capabilities.join(", ") || "No tool execution"}
              </strong>
              <span>{traceLabel(task.verification_status)}</span>
              <time title={new Date(task.created_at).toLocaleString()}>
                {new Date(task.created_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </time>
            </summary>
            <div className="trace-body">
              <p>{task.summary}</p>
              <dl className="trace-facts">
                <div>
                  <dt>Request ID</dt>
                  <dd>{task.request_id}</dd>
                </div>
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
                    <strong>{step.capability_id}</strong>
                    <span>{traceLabel(step.state)}</span>
                    <span>{traceLabel(step.approval)}</span>
                  </div>
                  <ol
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
                  </ol>
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
