export type WorkflowMode = "assisted" | "supervised" | "background";
export type CollaborationPattern =
  "auto" | "single" | "parallel" | "specialists" | "review";
export type CollaborationVerification = {
  status: string;
  scope?: string;
  checks?: Record<string, boolean>;
};
export type CollaborationParticipant = {
  participant_id: string;
  endpoint_id: string;
  model_id: string;
  identity: string;
  assigned_task: string;
  state: string;
  latency_ms: number | null;
  output_summary: string | null;
  output: string | null;
  verification: CollaborationVerification | null;
  error: string | null;
  tokens: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  } | null;
  resource_observations?: Record<string, unknown> | null;
};
export type WorkflowCollaboration = {
  requested_pattern: CollaborationPattern;
  effective_pattern: string;
  state: string;
  reason: string;
  participants: CollaborationParticipant[];
  conflicts: { participant_ids: string[]; kind: string; resolution: string }[];
  selected_endpoint_id: string | null;
  final_verification: CollaborationVerification | null;
  total_latency_ms: number | null;
  generated_tokens: number | null;
  output_token_budget: number;
  max_rounds: number;
  input_sha256?: string;
  context_refs?: {
    step_id: string;
    result_sha256: string;
    verification_status: string;
  }[];
};
export type WorkflowControl = { enabled: boolean; reason?: string | null };
export type WorkflowControls = Record<string, WorkflowControl>;
export type WorkflowSummary = {
  workflow_id: string;
  goal: string;
  mode: WorkflowMode;
  status: string;
  revision: number;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
  started_at?: string | null;
  counts: {
    total: number;
    required: number;
    verified: number;
    unverified: number;
    failed: number;
    pending: number;
    running: number;
    blocked: number;
  };
  verification_status: string;
  last_checkpoint_at: string | null;
  summary?: string | null;
  error?: string | Record<string, unknown> | null;
  active_uninterruptible?: boolean;
  pause_requested?: boolean;
  cancel_requested?: boolean;
  controls: WorkflowControls;
};
export type WorkflowStep = {
  step_id: string;
  description: string;
  kind: "tool" | "analysis" | "artifact";
  capability_id: string | null;
  definition_hash: string | null;
  dependencies: string[];
  criteria: unknown;
  arguments: Record<string, unknown>;
  planned_arguments: Record<string, unknown>;
  resolved_arguments: Record<string, unknown> | null;
  permission_level: number;
  risk_level: number;
  side_effect: string | null;
  execution_class?: string | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  attempts: number;
  verification: {
    status: string;
    method?: string;
    scope?: string;
    independent?: boolean;
    checks?: Record<string, boolean>;
    criteria?: {
      operator: string;
      path?: string;
      met: boolean;
      reason?: string;
    }[];
  } | null;
  error: string | Record<string, unknown> | null;
  controls: WorkflowControls;
  interruptible?: boolean;
  collaboration?: WorkflowCollaboration | null;
};
export type WorkflowApproval = {
  approval_id: string;
  step_id: string | null;
  kind: string;
  state: string;
  created_at: string;
  expires_at: string;
  plan_hash: string;
  argument_hash: string | null;
  definition_hash: string | null;
};
export type WorkflowArtifact = {
  artifact_id: string;
  step_id: string;
  name: string;
  kind: string;
  size_bytes: number;
  sha256: string;
  verified: boolean;
  created_at: string;
  excerpt: string | null;
};
export type WorkflowDetail = WorkflowSummary & {
  collaboration?: CollaborationPattern;
  plan_hash: string | null;
  plan_version: number;
  limits: Record<string, unknown>;
  steps: WorkflowStep[];
  approvals: WorkflowApproval[];
  checkpoints: {
    checkpoint_id: string;
    sequence: number;
    kind: string;
    created_at: string;
    status: string | null;
    reason: string | null;
    step_id?: string;
  }[];
  invocations: {
    invocation_id: string;
    step_id: string;
    state: string;
    attempt: number;
    write: boolean;
    retry_safe: boolean;
    started_at: string;
    finished_at: string | null;
    argument_hash: string;
    definition_hash: string;
    result?: Record<string, unknown> | null;
  }[];
  artifacts: WorkflowArtifact[];
  result_summary: string | null;
  compute_jobs?: import("./compute").ComputeJob[];
};
export type WorkflowsData = {
  available: boolean;
  reason: string | null;
  runner_attached: boolean;
  controller_attached: boolean;
  sampled_at: number | null;
  max_goal_chars: number;
  items: WorkflowSummary[];
  controls: WorkflowControls;
};
export type WorkflowData = {
  available: boolean;
  reason: string | null;
  runner_attached: boolean;
  controller_attached: boolean;
  workflow: WorkflowDetail | null;
};
export type WorkflowMutation = {
  workflow_id: string;
  workflow?: WorkflowDetail;
};

export function workflowLabel(value: string) {
  return value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (letter) => letter.toUpperCase());
}
export function workflowBoundaryNotice(
  workflow: Pick<
    WorkflowSummary,
    "status" | "pause_requested" | "cancel_requested" | "active_uninterruptible"
  >,
): string | null {
  const request = workflow.cancel_requested
    ? "Cancellation requested. "
    : workflow.pause_requested
      ? "Pause requested. "
      : "";
  if (workflow.active_uninterruptible)
    return `${request}An active action cannot be interrupted. Its outcome remains pending until the backend records it.`;
  if (
    !request ||
    ![
      "submitted",
      "planning",
      "awaiting_plan_approval",
      "ready",
      "running",
      "awaiting_step_approval",
      "verifying",
      "retrying",
      "recovering",
      "blocked",
    ].includes(workflow.status.toLowerCase())
  )
    return null;
  return `${request}The backend will stop at a safe execution boundary.`;
}
export function elapsedSinceStart(
  start: string | null | undefined,
  finish: string | null | undefined,
  now = Date.now(),
) {
  if (!start) return "Not started";
  const first = Date.parse(start),
    last = finish ? Date.parse(finish) : now;
  if (!Number.isFinite(first) || !Number.isFinite(last) || last < first)
    return "Unavailable";
  const seconds = Math.floor((last - first) / 1000);
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}
export function controlEnabled(
  controls: WorkflowControls | undefined,
  operation: string,
  connected: boolean,
) {
  return connected && controls?.[operation]?.enabled === true;
}
export function workflowConnected(
  data:
    | Pick<
        WorkflowsData,
        "available" | "runner_attached" | "controller_attached"
      >
    | null
    | undefined,
  token: string,
  error = "",
) {
  return Boolean(
    token &&
    data?.available &&
    data.runner_attached &&
    data.controller_attached &&
    !error,
  );
}
export function approvalCurrent(
  approval: WorkflowApproval,
  workflow: WorkflowDetail,
  now = Date.now(),
) {
  return (
    approval.state.toLowerCase() === "pending" &&
    approval.plan_hash === workflow.plan_hash &&
    Number.isFinite(Date.parse(approval.expires_at)) &&
    Date.parse(approval.expires_at) > now &&
    (!approval.step_id ||
      workflow.steps.some(
        (step) =>
          step.step_id === approval.step_id &&
          step.definition_hash === approval.definition_hash &&
          step.resolved_arguments != null,
      )) &&
    workflow.approvals.some(
      (current) =>
        current.approval_id === approval.approval_id &&
        current.state.toLowerCase() === "pending" &&
        current.step_id === approval.step_id &&
        current.plan_hash === approval.plan_hash &&
        current.argument_hash === approval.argument_hash &&
        current.definition_hash === approval.definition_hash &&
        current.expires_at === approval.expires_at,
    )
  );
}
export function approvalBindingCurrent(
  approval: WorkflowApproval,
  workflow: WorkflowDetail,
) {
  return (
    approval.plan_hash === workflow.plan_hash &&
    workflow.approvals.some(
      (current) =>
        current.approval_id === approval.approval_id &&
        current.state === approval.state &&
        current.step_id === approval.step_id &&
        current.plan_hash === approval.plan_hash &&
        current.argument_hash === approval.argument_hash &&
        current.definition_hash === approval.definition_hash &&
        current.expires_at === approval.expires_at,
    )
  );
}
export function approvalPayload(
  workflow: WorkflowDetail,
  approval: WorkflowApproval,
) {
  return {
    workflow_id: workflow.workflow_id,
    expected_revision: workflow.revision,
    approval_id: approval.approval_id,
    step_id: approval.step_id,
    plan_hash: approval.plan_hash,
    argument_hash: approval.argument_hash,
    definition_hash: approval.definition_hash,
  };
}
export function workflowPayload(
  workflow: WorkflowDetail,
  operation: string,
  approval?: WorkflowApproval,
  stepId?: string,
) {
  const base = {
    workflow_id: workflow.workflow_id,
    expected_revision: workflow.revision,
  };
  if (operation === "approve_step" || operation === "reject") {
    if (!approval?.step_id)
      throw new Error("Review the exact pending action approval first.");
    return approvalPayload(workflow, approval);
  }
  if (operation === "revoke") {
    if (!approval) throw new Error("Select the approval to revoke.");
    return { ...base, approval_id: approval.approval_id };
  }
  if (operation === "retry_safe") {
    if (!stepId) throw new Error("Select the safe failed step to retry.");
    return { ...base, step_id: stepId };
  }
  if (operation === "start" || operation === "approve_plan") {
    if (!workflow.plan_hash) throw new Error("Review a saved plan first.");
    return { ...base, plan_hash: workflow.plan_hash };
  }
  if (!["pause", "resume", "cancel"].includes(operation))
    throw new Error("Unsupported workflow operation.");
  return base;
}
export function workflowInView(status: string, filter: string) {
  if (filter === "all") return true;
  if (filter === "active")
    return [
      "submitted",
      "planning",
      "ready",
      "running",
      "verifying",
      "retrying",
      "recovering",
    ].includes(status);
  if (filter === "attention")
    return [
      "awaiting_plan_approval",
      "awaiting_step_approval",
      "blocked",
      "partially_completed",
    ].includes(status);
  if (filter === "awaiting_approval")
    return ["awaiting_plan_approval", "awaiting_step_approval"].includes(
      status,
    );
  return status === filter;
}

export function reviewCurrent(
  captured: WorkflowDetail,
  current: WorkflowDetail,
  approval?: WorkflowApproval,
  operation = "",
  now = Date.now(),
) {
  return (
    captured.workflow_id === current.workflow_id &&
    captured.revision === current.revision &&
    captured.plan_hash === current.plan_hash &&
    (!approval ||
      (operation === "revoke"
        ? ["pending", "approved"].includes(approval.state.toLowerCase()) &&
          Date.parse(approval.expires_at) > now &&
          approvalBindingCurrent(approval, current)
        : approvalCurrent(approval, current, now)))
  );
}

export type WorkflowRequestTicket = {
  id: string;
  token: string;
  signature: string;
};
export class WorkflowRequestLedger {
  private token = "";
  private pending: WorkflowRequestTicket | null = null;
  private active: WorkflowRequestTicket | null = null;

  reset(token: string) {
    this.token = token;
    this.pending = null;
    this.active = null;
  }
  begin(
    operation: string,
    data: Record<string, unknown>,
    token: string,
    createId = () => crypto.randomUUID(),
  ): WorkflowRequestTicket | null {
    if (token !== this.token) this.reset(token);
    if (this.active || !token) return null;
    const signature = JSON.stringify([operation, data]);
    if (this.pending?.signature !== signature)
      this.pending = { id: createId(), token, signature };
    this.active = this.pending;
    return this.active;
  }
  current(ticket: WorkflowRequestTicket) {
    return this.active === ticket && this.token === ticket.token;
  }
  finish(ticket: WorkflowRequestTicket, succeeded: boolean) {
    if (!this.current(ticket)) return false;
    this.active = null;
    if (succeeded) this.pending = null;
    return true;
  }
}
