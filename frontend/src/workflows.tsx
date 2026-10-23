import { useEffect, useRef, useState, type FormEvent } from "react";
import { request } from "./api";
import { FeatureDialog } from "./feature_ui";
import { ComputeJobs } from "./compute";
import { WorkflowCollaborationView } from "./workflow_collaboration";
import { consumeInspection, usePrivateResource } from "./feature_types";
import type { Screen } from "./types";
import {
  approvalBindingCurrent,
  approvalCurrent,
  approvalPayload,
  controlEnabled,
  elapsedSinceStart,
  reviewCurrent,
  WorkflowRequestLedger,
  workflowInView,
  workflowConnected,
  workflowBoundaryNotice,
  workflowLabel,
  workflowPayload,
  type WorkflowApproval,
  type WorkflowData,
  type WorkflowDetail,
  type WorkflowMode,
  type CollaborationPattern,
  type WorkflowMutation,
  type WorkflowStep,
  type WorkflowsData,
} from "./workflow_types";
import "./workflows.css";

const timestamp = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString() : "Not recorded";
const json = (value: unknown) => JSON.stringify(value, null, 2);
const capabilityLabel = (step: WorkflowStep) =>
  step.kind === "analysis"
    ? "Evidence analysis"
    : step.capability_id || "Capability not recorded";
const actionLabels: Record<string, string> = {
  start: "Start",
  pause: "Pause",
  resume: "Resume",
  cancel: "Cancel workflow",
  revoke: "Revoke this approval",
  retry_safe: "Retry this safe step",
  approve_plan: "Approve this plan",
  approve_step: "Approve this action",
  reject: "Reject this action",
};
type Review = {
  operation: string;
  workflow: WorkflowDetail;
  approval?: WorkflowApproval;
  stepId?: string;
};

export function WorkflowsPage({
  token,
  navigate,
}: {
  token: string;
  navigate: (screen: Screen) => void;
}) {
  const resource = usePrivateResource<WorkflowsData>(
    "/api/workflows?limit=50",
    token,
    1000,
  );
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState("all");
  const [create, setCreate] = useState(false),
    [goal, setGoal] = useState("");
  const [mode, setMode] = useState<WorkflowMode>("assisted");
  const [collaboration, setCollaboration] =
    useState<CollaborationPattern>("auto");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const requests = useRef(new WorkflowRequestLedger());
  const alive = useRef(true),
    session = useRef(token);
  session.current = token;
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  useEffect(() => {
    setSelected(null);
    setCreate(false);
    setGoal("");
    setMode("assisted");
    setCollaboration("auto");
    setError("");
    setBusy(false);
    requests.current.reset(token);
  }, [token]);
  useEffect(() => {
    if (!resource.data) return;
    const target = consumeInspection("workflows");
    if (target) {
      setSelected(target);
      setSearch("");
      setFilter("all");
    }
  }, [resource.data]);
  const data = resource.data;
  const maxGoalChars = data?.max_goal_chars || 4000;
  const connected = workflowConnected(data, token, resource.error);
  async function execute(
    operation: string,
    payload: Record<string, unknown>,
  ): Promise<WorkflowMutation | undefined> {
    if (busy || !connected) {
      setError("Reconnect and refresh workflows before changing them.");
      return;
    }
    const ticket = requests.current.begin(operation, payload, token);
    if (!ticket) return;
    setBusy(true);
    setError("");
    const requestToken = token;
    let succeeded = false;
    try {
      const result = await request<WorkflowMutation>("/api/workflows", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Hanni-Token": requestToken,
        },
        body: JSON.stringify({ id: ticket.id, operation, data: payload }),
        signal: AbortSignal.timeout(20000),
      });
      if (
        !alive.current ||
        session.current !== requestToken ||
        !requests.current.current(ticket)
      )
        return;
      succeeded = true;
      resource.refresh();
      setRevision((value) => value + 1);
      return result;
    } catch (caught) {
      if (
        alive.current &&
        session.current === requestToken &&
        requests.current.current(ticket)
      )
        setError(
          `${caught instanceof Error ? caught.message : "Workflow request failed."} Refresh status before retrying. An identical retry keeps the same request ID.`,
        );
    } finally {
      if (
        requests.current.finish(ticket, succeeded) &&
        alive.current &&
        session.current === requestToken
      )
        setBusy(false);
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (
      !controlEnabled(data?.controls, "goal.submit", connected) ||
      !goal.trim()
    )
      return;
    const result = await execute("goal.submit", {
      goal: goal.trim(),
      mode,
      collaboration,
    });
    if (result) {
      setCreate(false);
      setGoal("");
      setSelected(result.workflow_id);
    }
  }
  const items = (data?.items || []).filter(
    (row) =>
      workflowInView(row.status, filter) &&
      `${row.goal} ${row.workflow_id}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <div className="workflows-page">
      {selected ? (
        <WorkflowDetailView
          key={`${token}:${selected}`}
          workflowId={selected}
          token={token}
          navigate={navigate}
          back={() => {
            setSelected(null);
            setError("");
          }}
          connected={connected}
          busy={busy}
          error={error}
          revision={revision}
          execute={execute}
        />
      ) : (
        <>
          <header className="screen-heading">
            <div>
              <h1>Workflows</h1>
              <p>Goals, authorized work and recorded outcomes</p>
            </div>
            <button
              disabled={
                busy ||
                !controlEnabled(data?.controls, "goal.submit", connected)
              }
              title={data?.controls["goal.submit"]?.reason || undefined}
              onClick={() => {
                setError("");
                setCreate(true);
              }}
            >
              New goal
            </button>
          </header>
          <WorkflowConnection data={data} error={resource.error} />
          {error && (
            <p className="feature-error" role="alert">
              {error}
            </p>
          )}
          <div className="feature-toolbar">
            <input
              type="search"
              aria-label="Search workflows"
              placeholder="Goal or workflow ID"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <select
              aria-label="Workflow status"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            >
              <option value="all">All workflows</option>
              <option value="active">Active</option>
              <option value="attention">Needs attention</option>
              <option value="awaiting_approval">Awaiting approval</option>
              <option value="paused">Paused</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <button className="text-link" onClick={resource.refresh}>
              Refresh workflows
            </button>
            <span className="subtle">{items.length} loaded</span>
          </div>
          {!data ? (
            resource.error ? (
              <p className="feature-empty">
                Workflow history could not be loaded. Refresh when the
                connection is available.
              </p>
            ) : (
              <div
                className="skeleton-group"
                role="status"
                aria-label="Loading workflows"
              >
                <span className="skeleton" />
                <span className="skeleton medium" />
              </div>
            )
          ) : !data.available ? (
            <p className="feature-empty">
              {data.reason || "Workflow history is unavailable."}
            </p>
          ) : items.length ? (
            <div className="workflow-list">
              <div className="workflow-list-heading">
                <span>Goal</span>
                <span>State / evidence</span>
                <span>Steps</span>
                <span>Last checkpoint</span>
              </div>
              {items.map((row) => (
                <button
                  key={row.workflow_id}
                  className="workflow-row"
                  data-workflow-id={row.workflow_id}
                  onClick={() => setSelected(row.workflow_id)}
                >
                  <span>
                    <strong>{row.goal}</strong>
                    <small>
                      {workflowLabel(row.mode)} · {row.workflow_id}
                    </small>
                  </span>
                  <span>
                    {workflowLabel(row.status)}
                    <small>{workflowLabel(row.verification_status)}</small>
                  </span>
                  <span>
                    {row.counts.verified} / {row.counts.total}
                    <small>verified steps</small>
                  </span>
                  <time>{timestamp(row.last_checkpoint_at)}</time>
                </button>
              ))}
            </div>
          ) : (
            <section className="workflow-empty">
              <h2>
                {search || filter !== "all"
                  ? "No workflows match this view"
                  : "No saved workflows"}
              </h2>
              <p>
                {search || filter !== "all"
                  ? "Change the search or status filter."
                  : "Submit a goal to create a persisted plan. Assisted mode waits for your approval before execution."}
              </p>
            </section>
          )}
        </>
      )}
      {create && (
        <FeatureDialog
          title="New workflow goal"
          busy={busy}
          onClose={() => setCreate(false)}
        >
          <form onSubmit={submit} className="workflow-goal-form">
            <label htmlFor="workflow-goal">Goal</label>
            <textarea
              id="workflow-goal"
              autoFocus
              required
              maxLength={maxGoalChars}
              rows={4}
              value={goal}
              onChange={(event) => setGoal(event.target.value)}
              placeholder="Describe the outcome and any files, dates or constraints needed."
            />
            <span className="feature-note">
              {goal.length} / {maxGoalChars} characters
            </span>
            <label htmlFor="workflow-mode">Autonomy mode</label>
            <select
              id="workflow-mode"
              value={mode}
              onChange={(event) => setMode(event.target.value as WorkflowMode)}
            >
              <option value="assisted">Assisted</option>
              <option value="supervised">Supervised</option>
              <option value="background">Background</option>
            </select>
            <p className="feature-note">
              {mode === "assisted"
                ? "Review and approve the plan before it starts. Sensitive actions need separate approval."
                : mode === "supervised"
                  ? "Authorized low-risk steps may run automatically. Sensitive actions still need your explicit approval."
                  : "Background execution requires a previously approved plan and bounded scope. This choice does not grant unrestricted tool access."}
            </p>
            <label htmlFor="workflow-collaboration">Model analysis</label>
            <select
              id="workflow-collaboration"
              value={collaboration}
              onChange={(event) =>
                setCollaboration(event.target.value as CollaborationPattern)
              }
            >
              <option value="auto">Automatic</option>
              <option value="single">One model</option>
              <option value="parallel">Independent comparison</option>
              <option value="specialists">Specialist analysis</option>
              <option value="review">Independent review</option>
            </select>
            <p className="feature-note">
              {collaboration === "auto"
                ? "Uses multiple models when measured results justify the extra work."
                : collaboration === "single"
                  ? "Uses the existing model routing for each analysis."
                  : "Uses eligible models within the existing sharing permissions. Additional analysis may take longer; unavailable models fall back to one model."}
            </p>
            <p className="feature-note">
              Plans and history are saved locally. Work continues only while the
              backend is running and the computer is awake.
            </p>
            {error && (
              <p className="feature-error" role="alert">
                {error}
              </p>
            )}
            <div className="dialog-actions">
              <button
                type="button"
                disabled={busy}
                onClick={() => setCreate(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={
                  busy ||
                  !goal.trim() ||
                  !controlEnabled(data?.controls, "goal.submit", connected)
                }
              >
                {busy ? "Submitting goal…" : "Create workflow"}
              </button>
            </div>
          </form>
        </FeatureDialog>
      )}
    </div>
  );
}

function WorkflowConnection({
  data,
  error,
}: {
  data: WorkflowsData | null;
  error: string;
}) {
  if (error)
    return (
      <p className="feature-error" role="status">
        {error}
        {data &&
          " Displayed history may be stale. Controls are unavailable until refreshed."}
      </p>
    );
  if (data?.available && (!data.runner_attached || !data.controller_attached))
    return (
      <p className="feature-error" role="status">
        {data.reason ||
          "Saved history is available. The workflow runner is not attached; work is not executing."}
      </p>
    );
  return null;
}

function WorkflowDetailView({
  workflowId,
  token,
  navigate,
  back,
  connected,
  busy,
  error,
  revision,
  execute,
}: {
  workflowId: string;
  token: string;
  navigate: (screen: Screen) => void;
  back: () => void;
  connected: boolean;
  busy: boolean;
  error: string;
  revision: number;
  execute: (
    operation: string,
    payload: Record<string, unknown>,
  ) => Promise<WorkflowMutation | undefined>;
}) {
  const resource = usePrivateResource<WorkflowData>(
    `/api/workflows/${encodeURIComponent(workflowId)}`,
    token,
    1000,
  );
  const [review, setReview] = useState<Review | null>(null);
  const [output, setOutput] = useState<{ title: string; text: string } | null>(
    null,
  );
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    resource.refresh();
  }, [revision]);
  const data = resource.data,
    workflow = data?.workflow;
  const live =
    connected &&
    workflowConnected(data, token, resource.error) &&
    workflow?.workflow_id === workflowId;
  const enabled = (operation: string, stepId?: string) =>
    !busy &&
    controlEnabled(
      stepId
        ? workflow?.steps.find((step) => step.step_id === stepId)?.controls
        : workflow?.controls,
      operation,
      live,
    );
  const pendingPlan = workflow?.approvals.find(
    (approval) =>
      approval.kind === "plan" && approvalCurrent(approval, workflow, now),
  );
  const capturedCurrent = Boolean(
    review &&
    workflow &&
    reviewCurrent(
      review.workflow,
      workflow,
      review.approval,
      review.operation,
      now,
    ),
  );
  async function confirmReview() {
    const clickTime = Date.now();
    if (
      !review ||
      !workflow ||
      !reviewCurrent(
        review.workflow,
        workflow,
        review.approval,
        review.operation,
        clickTime,
      ) ||
      !enabled(review.operation, review.stepId)
    ) {
      setNow(clickTime);
      return;
    }
    const payload = workflowPayload(
      review.workflow,
      review.operation,
      review.approval,
      review.stepId,
    );
    if (await execute(review.operation, payload)) setReview(null);
  }
  async function control(operation: string) {
    if (!workflow || !enabled(operation)) return;
    if (operation === "cancel") setReview({ operation, workflow });
    else await execute(operation, workflowPayload(workflow, operation));
  }
  if (!workflow)
    return (
      <>
        <button className="text-link" onClick={back}>
          Back to workflows
        </button>
        <header className="screen-heading">
          <div>
            <h1>Workflow</h1>
          </div>
          <button className="text-link" onClick={resource.refresh}>
            Refresh workflow
          </button>
        </header>
        {resource.error ? (
          <p className="feature-error" role="status">
            {resource.error} The workflow could not be loaded.
          </p>
        ) : data ? (
          <p className="feature-empty">
            {data.reason ||
              "This workflow is unavailable. Its notification remains in history."}
          </p>
        ) : (
          <div
            className="skeleton-group"
            role="status"
            aria-label="Loading workflow"
          >
            <span className="skeleton" />
          </div>
        )}
      </>
    );
  return (
    <div className="workflow-detail" data-workflow-id={workflow.workflow_id}>
      <div className="workflow-back-row">
        <button className="text-link" onClick={back}>
          Back to workflows
        </button>
        <button className="text-link" onClick={resource.refresh}>
          Refresh workflow
        </button>
      </div>
      <header className="screen-heading">
        <div>
          <h1>{workflow.goal.length > 180 ? "Workflow" : workflow.goal}</h1>
          <p>
            {workflowLabel(workflow.status)} · {workflowLabel(workflow.mode)} ·{" "}
            {workflowLabel(workflow.verification_status)}
          </p>
        </div>
      </header>
      {workflow.goal.length > 180 && (
        <details className="workflow-original-goal">
          <summary>Original goal</summary>
          <p>{workflow.goal}</p>
        </details>
      )}
      {resource.error && (
        <p className="feature-error" role="status">
          {resource.error} Displayed workflow may be stale. Controls are
          disabled.
        </p>
      )}
      {(!data?.runner_attached || !data.controller_attached) && (
        <p className="feature-error" role="status">
          {data?.reason ||
            "The backend runner is unavailable. This is saved history; no work is executing."}
        </p>
      )}
      {error && !review && (
        <p className="feature-error" role="alert">
          {error}
        </p>
      )}
      {workflow.error && (
        <p className="feature-error workflow-recorded-error" role="status">
          {typeof workflow.error === "string"
            ? workflow.error
            : json(workflow.error)}
        </p>
      )}
      <div className="workflow-controls">
        {["start", "pause", "resume", "cancel"]
          .filter((operation) => workflow.controls[operation])
          .map((operation) => (
            <button
              key={operation}
              disabled={!enabled(operation)}
              title={workflow.controls[operation].reason || undefined}
              onClick={() => control(operation)}
            >
              {actionLabels[operation]}
            </button>
          ))}
        {workflow.controls.approve_plan && (
          <button
            disabled={
              !enabled("approve_plan") || !workflow.plan_hash || !pendingPlan
            }
            title={workflow.controls.approve_plan.reason || undefined}
            onClick={() =>
              setReview({
                operation: "approve_plan",
                workflow,
                approval: pendingPlan,
              })
            }
          >
            Review plan approval
          </button>
        )}
      </div>
      {Object.entries(workflow.controls).some(
        ([, control]) => !control.enabled && control.reason,
      ) && (
        <details className="workflow-control-reasons">
          <summary>Control availability</summary>
          <dl>
            {Object.entries(workflow.controls)
              .filter(([, control]) => !control.enabled && control.reason)
              .map(([operation, control]) => (
                <div key={operation}>
                  <dt>{actionLabels[operation] || workflowLabel(operation)}</dt>
                  <dd>{control.reason}</dd>
                </div>
              ))}
          </dl>
        </details>
      )}
      {workflowBoundaryNotice(workflow) && (
        <p className="feature-error" role="status">
          {workflowBoundaryNotice(workflow)}
        </p>
      )}
      <ComputeJobs jobs={workflow.compute_jobs || []} />
      <div className="workflow-facts">
        <span>
          {workflow.counts.verified} / {workflow.counts.total} steps verified ·{" "}
          {workflow.counts.required} required
        </span>
        <span>
          Elapsed since start:{" "}
          {elapsedSinceStart(workflow.started_at, workflow.finished_at, now)}
        </span>
        <span>Last checkpoint: {timestamp(workflow.last_checkpoint_at)}</span>
        <span>Created: {timestamp(workflow.created_at)}</span>
        {workflow.finished_at && (
          <span>Finished: {timestamp(workflow.finished_at)}</span>
        )}
      </div>
      {(workflow.result_summary || workflow.summary) && (
        <p className="workflow-result-summary">
          {workflow.result_summary || workflow.summary}
        </p>
      )}
      <WorkflowCollaborationView steps={workflow.steps} />
      {workflow.approvals.length > 0 && (
        <section className="workflow-approvals" aria-label="Workflow approvals">
          <h2>Approvals</h2>
          {workflow.approvals.map((approval) => (
            <div
              key={approval.approval_id}
              data-approval-id={approval.approval_id}
            >
              <span>
                <strong>
                  {workflow.steps.find(
                    (step) => step.step_id === approval.step_id,
                  )?.description || "Workflow execution scope"}
                </strong>
                <small>
                  {workflowLabel(approval.state)} · Expires{" "}
                  {timestamp(approval.expires_at)}
                </small>
              </span>
              {approval.step_id && (
                <>
                  <button
                    disabled={
                      !enabled("approve_step") ||
                      !approvalCurrent(approval, workflow, now)
                    }
                    onClick={() =>
                      setReview({
                        operation: "approve_step",
                        workflow,
                        approval,
                      })
                    }
                  >
                    Review action
                  </button>
                  <button
                    className="text-link"
                    disabled={
                      !enabled("reject") ||
                      !approvalCurrent(approval, workflow, now)
                    }
                    onClick={() =>
                      setReview({ operation: "reject", workflow, approval })
                    }
                  >
                    Reject
                  </button>
                </>
              )}
              <button
                className="text-link"
                disabled={
                  !enabled("revoke") ||
                  !["pending", "approved"].includes(
                    approval.state.toLowerCase(),
                  ) ||
                  Date.parse(approval.expires_at) <= now ||
                  !approvalBindingCurrent(approval, workflow)
                }
                onClick={() =>
                  setReview({ operation: "revoke", workflow, approval })
                }
              >
                Revoke approval
              </button>
            </div>
          ))}
        </section>
      )}
      <section className="workflow-plan" aria-label="Workflow plan">
        <div className="section-title">
          <h2>Plan</h2>
          <span>
            Version {workflow.plan_version} · {workflow.steps.length} steps
          </span>
        </div>
        {!workflow.steps.length ? (
          <p className="feature-empty">
            No executable plan has been saved. Planning limitations appear in
            the recorded status.
          </p>
        ) : (
          workflow.steps.map((step) => (
            <details
              className="workflow-step"
              key={step.step_id}
              data-step-id={step.step_id}
            >
              <summary>
                <span className={`workflow-state ${step.status.toLowerCase()}`}>
                  {workflowLabel(step.status)}
                </span>
                <strong>{step.description}</strong>
                <span>
                  {step.verification
                    ? workflowLabel(step.verification.status)
                    : "Not verified"}
                </span>
              </summary>
              <div className="workflow-step-body">
                <p className="mono">{capabilityLabel(step)}</p>
                <WorkflowPolicy step={step} />
                <p>
                  Dependencies:{" "}
                  {step.dependencies.length
                    ? step.dependencies
                        .map(
                          (id) =>
                            workflow.steps.find((row) => row.step_id === id)
                              ?.description || id,
                        )
                        .join("; ")
                    : "None"}
                </p>
                <p>
                  Attempts: {step.attempts} · Started:{" "}
                  {timestamp(step.started_at)} · Finished:{" "}
                  {timestamp(step.finished_at)}
                </p>
                {step.error && (
                  <p className="feature-error">
                    {typeof step.error === "string"
                      ? step.error
                      : json(step.error)}
                  </p>
                )}
                {step.verification && (
                  <p>
                    Verification:{" "}
                    {step.verification.method || "Method not recorded"} ·{" "}
                    {step.verification.scope || "Scope not recorded"}
                    {step.verification.independent
                      ? " · Independent observation"
                      : " · Tool-reported evidence"}
                  </p>
                )}
                {step.verification?.criteria?.length ? (
                  <div className="workflow-criteria">
                    <h3>Acceptance checks</h3>
                    {step.verification.criteria.map((criterion, index) => (
                      <p key={index}>
                        <strong>{criterion.met ? "Met" : "Not met"}</strong> ·{" "}
                        {criterion.path || criterion.operator}
                        {criterion.reason && ` · ${criterion.reason}`}
                      </p>
                    ))}
                  </div>
                ) : null}
                <h3>Completion criteria</h3>
                <pre>{json(step.criteria)}</pre>
                {step.controls?.retry_safe && (
                  <button
                    className="text-link"
                    disabled={!enabled("retry_safe", step.step_id)}
                    title={step.controls.retry_safe.reason || undefined}
                    onClick={() =>
                      setReview({
                        operation: "retry_safe",
                        workflow,
                        stepId: step.step_id,
                      })
                    }
                  >
                    Retry this safe failed step
                  </button>
                )}
                <details>
                  <summary>Planned arguments</summary>
                  <pre>{json(step.planned_arguments)}</pre>
                </details>
                {step.resolved_arguments && (
                  <details>
                    <summary>Resolved arguments</summary>
                    <pre>{json(step.resolved_arguments)}</pre>
                  </details>
                )}
              </div>
            </details>
          ))
        )}
      </section>
      <section className="workflow-artifacts" aria-label="Workflow outputs">
        <h2>Results and artifacts</h2>
        {workflow.artifacts.length ? (
          workflow.artifacts.map((artifact) => (
            <div key={artifact.artifact_id}>
              <span>
                <strong>{artifact.name}</strong>
                <small>
                  {artifact.kind} · {artifact.size_bytes} bytes ·{" "}
                  {artifact.verified
                    ? "Verified artifact"
                    : "Unverified artifact"}
                </small>
                <details>
                  <summary>Artifact record</summary>
                  <p className="mono">SHA256 {artifact.sha256}</p>
                  <p>
                    {timestamp(artifact.created_at)} · Step {artifact.step_id}
                  </p>
                </details>
              </span>
              {typeof artifact.excerpt === "string" ? (
                <button
                  className="text-link"
                  onClick={() =>
                    setOutput({ title: artifact.name, text: artifact.excerpt! })
                  }
                >
                  View output
                </button>
              ) : (
                <span className="subtle">Reference only</span>
              )}
            </div>
          ))
        ) : (
          <p className="feature-note">
            No saved output artifacts. Completed calls alone do not establish a
            verified result.
          </p>
        )}
      </section>
      <details className="workflow-history">
        <summary>Checkpoints and tool activity</summary>
        <h3>Checkpoints</h3>
        {workflow.checkpoints.length ? (
          <ol>
            {workflow.checkpoints.map((checkpoint) => (
              <li key={checkpoint.checkpoint_id}>
                <time>{timestamp(checkpoint.created_at)}</time>
                <strong>{workflowLabel(checkpoint.kind)}</strong>
                <span>
                  {checkpoint.reason ||
                    (checkpoint.status
                      ? workflowLabel(checkpoint.status)
                      : checkpoint.step_id
                        ? `Step ${checkpoint.step_id}`
                        : `Checkpoint ${checkpoint.sequence}`)}
                </span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="feature-note">No checkpoints recorded.</p>
        )}
        <h3>Tool invocations</h3>
        {workflow.invocations.length ? (
          <ol>
            {workflow.invocations.map((invocation) => (
              <li key={invocation.invocation_id}>
                <time>{timestamp(invocation.started_at)}</time>
                <strong>
                  {workflow.steps.find(
                    (step) => step.step_id === invocation.step_id,
                  )?.capability_id || invocation.step_id}
                </strong>
                <span>
                  {workflowLabel(invocation.state)} · Attempt{" "}
                  {invocation.attempt} · {invocation.write ? "Action" : "Read"}
                  {invocation.finished_at &&
                    ` · Finished ${timestamp(invocation.finished_at)}`}
                </span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="feature-note">No tool invocations recorded.</p>
        )}
        <button className="text-link" onClick={() => navigate("activity")}>
          Open execution Activity
        </button>
        <h3>Scope and limits</h3>
        <pre>{json(workflow.limits)}</pre>
        <p className="mono">
          Workflow {workflow.workflow_id} · Plan{" "}
          {workflow.plan_hash || "Not saved"} · Revision {workflow.revision}
        </p>
      </details>
      {review && (
        <FeatureDialog
          title={
            review.operation === "approve_plan"
              ? "Approve this workflow plan?"
              : review.operation === "approve_step"
                ? "Approve this workflow action?"
                : `${actionLabels[review.operation]}?`
          }
          busy={busy}
          onClose={() => setReview(null)}
        >
          <p className="confirmation-copy">{review.workflow.goal}</p>
          <p className="feature-note">
            Autonomy mode: {workflowLabel(review.workflow.mode)}
          </p>
          {review.operation === "approve_plan" ? (
            <>
              <p className="feature-note">
                This approves the displayed plan and its bounded execution
                scope. Sensitive steps still require separate action approval.
              </p>
              {review.approval && (
                <p>Expires: {timestamp(review.approval.expires_at)}</p>
              )}
              <div className="workflow-review-plan">
                {review.workflow.steps.map((step) => (
                  <div key={step.step_id}>
                    <strong>{step.description}</strong>
                    <span>{capabilityLabel(step)}</span>
                    <WorkflowPolicy step={step} />
                    <p>
                      Dependencies:{" "}
                      {step.dependencies.length
                        ? step.dependencies.join(", ")
                        : "None"}
                    </p>
                    <h3>Completion criteria</h3>
                    <pre>{json(step.criteria)}</pre>
                    <h3>Planned arguments</h3>
                    <pre>{json(step.planned_arguments)}</pre>
                  </div>
                ))}
              </div>
              <h3>Execution limits</h3>
              <pre>{json(review.workflow.limits)}</pre>
            </>
          ) : review.approval ? (
            <>
              <p>
                {review.workflow.steps.find(
                  (step) => step.step_id === review.approval?.step_id,
                )?.description || "Workflow execution scope"}
              </p>
              <p>Expires: {timestamp(review.approval.expires_at)}</p>
              {review.workflow.steps
                .filter((step) => step.step_id === review.approval?.step_id)
                .map((step) => (
                  <WorkflowPolicy key={step.step_id} step={step} />
                ))}
              <pre className="workflow-approval-arguments">
                {json(
                  review.workflow.steps.find(
                    (step) => step.step_id === review.approval?.step_id,
                  )?.resolved_arguments ?? "Prepared arguments unavailable",
                )}
              </pre>
              <p className="feature-note">
                {review.operation === "revoke"
                  ? "Revoke this unused approval. Completed work is not undone; an active action may still finish."
                  : "Approval covers only this resolved action and current tool definition. Rejection does not undo completed work."}
              </p>
            </>
          ) : (
            <p className="feature-note">
              {review.operation === "cancel"
                ? "Request cancellation at a safe boundary. A noninterruptible action may continue until it returns; completed work is not undone."
                : "Only the selected step the backend identifies as safe to retry can run again. Uncertain side effects are not replayed."}
            </p>
          )}
          <details>
            <summary>Approval binding</summary>
            <pre>
              {json(
                review.approval
                  ? approvalPayload(review.workflow, review.approval)
                  : {
                      workflow_id: review.workflow.workflow_id,
                      revision: review.workflow.revision,
                      plan_hash: review.workflow.plan_hash,
                    },
              )}
            </pre>
          </details>
          {!capturedCurrent && (
            <p className="feature-error" role="alert">
              This workflow or approval changed or expired. Close this dialog
              and review the current saved state.
            </p>
          )}
          {!live && (
            <p className="feature-error" role="status">
              {resource.error ||
                data?.reason ||
                "Live workflow status is unavailable."}{" "}
              Confirmation is disabled until a fresh connection is available.
            </p>
          )}
          {busy && (
            <p className="feature-note" role="status">
              Submitting the request. Its recorded status will refresh after the
              backend responds.
            </p>
          )}
          {error && (
            <p className="feature-error" role="alert">
              {error}
            </p>
          )}
          <div className="dialog-actions">
            <button autoFocus disabled={busy} onClick={() => setReview(null)}>
              Keep reviewing
            </button>
            <button
              disabled={
                !capturedCurrent || !enabled(review.operation, review.stepId)
              }
              onClick={confirmReview}
            >
              {actionLabels[review.operation]}
            </button>
          </div>
        </FeatureDialog>
      )}
      {output && (
        <FeatureDialog
          title={`Output: ${output.title}`}
          onClose={() => setOutput(null)}
        >
          <p className="feature-note">
            Saved output excerpt from this workflow. This view does not open
            files or run tools.
          </p>
          <pre className="workflow-output-text">{output.text}</pre>
          <div className="dialog-actions">
            <button autoFocus onClick={() => setOutput(null)}>
              Close output
            </button>
          </div>
        </FeatureDialog>
      )}
    </div>
  );
}

function WorkflowPolicy({ step }: { step: WorkflowStep }) {
  return (
    <p className="workflow-policy">
      Permission level {step.permission_level} · Risk level {step.risk_level} ·{" "}
      {step.side_effect
        ? workflowLabel(step.side_effect)
        : "Effect classification not recorded"}
      {step.execution_class && ` · ${workflowLabel(step.execution_class)}`}
    </p>
  );
}
