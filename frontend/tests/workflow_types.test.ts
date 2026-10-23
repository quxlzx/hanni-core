import test from "node:test";
import assert from "node:assert/strict";
import {
  approvalCurrent,
  controlEnabled,
  elapsedSinceStart,
  reviewCurrent,
  WorkflowRequestLedger,
  workflowInView,
  workflowConnected,
  workflowBoundaryNotice,
  workflowPayload,
  type WorkflowApproval,
  type WorkflowDetail,
} from "../src/workflow_types.ts";

const now = Date.parse("2026-10-09T15:00:00Z");

test("settled pause and cancellation flags cannot imply pending work", () => {
  for (const status of [
    "paused",
    "cancelled",
    "completed",
    "partially_completed",
    "failed",
  ])
    assert.equal(
      workflowBoundaryNotice({
        status,
        pause_requested: true,
        cancel_requested: true,
      }),
      null,
    );
  assert.equal(
    workflowBoundaryNotice({
      status: "unknown_future_state",
      cancel_requested: true,
    }),
    null,
  );
});

test("pending boundary requests remain visible only for actual unsettled states", () => {
  for (const status of [
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
  ])
    assert.equal(
      workflowBoundaryNotice({ status, pause_requested: true }),
      "Pause requested. The backend will stop at a safe execution boundary.",
    );
  assert.equal(
    workflowBoundaryNotice({ status: "running", cancel_requested: true }),
    "Cancellation requested. The backend will stop at a safe execution boundary.",
  );
  assert.equal(workflowBoundaryNotice({ status: "running" }), null);
});

test("observed active noninterruptible calls retain the warning even alongside settled status", () => {
  for (const status of [
    "running",
    "paused",
    "cancelled",
    "completed",
    "failed",
  ])
    assert.match(
      workflowBoundaryNotice({ status, active_uninterruptible: true })!,
      /^An active action cannot be interrupted\./,
    );
  assert.match(
    workflowBoundaryNotice({
      status: "cancelled",
      cancel_requested: true,
      active_uninterruptible: true,
    })!,
    /^Cancellation requested\. An active action cannot be interrupted\./,
  );
  assert.match(
    workflowBoundaryNotice({
      status: "paused",
      pause_requested: true,
      active_uninterruptible: true,
    })!,
    /^Pause requested\. An active action cannot be interrupted\./,
  );
});
const approval = (
  changes: Partial<WorkflowApproval> = {},
): WorkflowApproval => ({
  approval_id: "approval_review",
  step_id: "write",
  kind: "step",
  state: "pending",
  created_at: "2026-10-09T14:59:00Z",
  expires_at: "2026-10-09T15:05:00Z",
  plan_hash: "plan-current",
  argument_hash: "arguments-current",
  definition_hash: "definition-current",
  ...changes,
});
const workflow = (changes: Partial<WorkflowDetail> = {}): WorkflowDetail => ({
  workflow_id: "wf_review",
  goal: "Save a note and check it",
  mode: "assisted",
  status: "awaiting_step_approval",
  revision: 4,
  created_at: "2026-10-09T14:55:00Z",
  updated_at: "2026-10-09T14:59:00Z",
  finished_at: null,
  counts: {
    total: 1,
    required: 1,
    verified: 0,
    unverified: 0,
    failed: 0,
    pending: 1,
    running: 0,
    blocked: 0,
  },
  verification_status: "not_started",
  last_checkpoint_at: "2026-10-09T14:59:00Z",
  controls: { approve_step: { enabled: true }, pause: { enabled: true } },
  plan_hash: "plan-current",
  plan_version: 1,
  limits: { max_retries: 1 },
  steps: [
    {
      step_id: "write",
      description: "Save a note",
      kind: "tool",
      capability_id: "note.append",
      definition_hash: "definition-current",
      dependencies: [],
      criteria: { description: "Read back the saved note" },
      arguments: { text: "Exact note" },
      planned_arguments: { text: "Exact note" },
      resolved_arguments: { text: "Exact note" },
      permission_level: 2,
      risk_level: 2,
      side_effect: "reversible_write",
      status: "awaiting_approval",
      started_at: null,
      finished_at: null,
      attempts: 0,
      verification: null,
      error: null,
      controls: {},
    },
  ],
  approvals: [approval()],
  checkpoints: [],
  invocations: [],
  artifacts: [],
  result_summary: null,
  ...changes,
});

test("server controls require a connected runner and an explicit enabled boolean", () => {
  assert.equal(controlEnabled(workflow().controls, "approve_step", true), true);
  assert.equal(
    controlEnabled(workflow().controls, "approve_step", false),
    false,
  );
  assert.equal(controlEnabled(workflow().controls, "cancel", true), false);
  assert.equal(controlEnabled(undefined, "start", true), false);
  assert.equal(
    controlEnabled(
      { start: { enabled: false, reason: "Runner unavailable" } },
      "start",
      true,
    ),
    false,
  );
});

test("private mutations require both a live original controller and runner, fresh history and the current token", () => {
  const data = {
    available: true,
    runner_attached: true,
    controller_attached: true,
  };
  assert.equal(workflowConnected(data, "current-token"), true);
  assert.equal(workflowConnected(data, ""), false);
  assert.equal(
    workflowConnected(data, "current-token", "Endpoint unavailable"),
    false,
  );
  for (const field of ["available", "runner_attached", "controller_attached"])
    assert.equal(
      workflowConnected({ ...data, [field]: false }, "current-token"),
      false,
    );
  assert.equal(workflowConnected(null, "current-token"), false);
});

test("approval review expires at the exact boundary and rejects missing or invalid timestamps", () => {
  assert.equal(approvalCurrent(approval(), workflow(), now), true);
  for (const expires_at of [
    "invalid",
    "",
    new Date(now).toISOString(),
    new Date(now - 1).toISOString(),
  ]) {
    const record = approval({ expires_at });
    assert.equal(
      approvalCurrent(record, workflow({ approvals: [record] }), now),
      false,
    );
  }
});

test("changes to plan, arguments, tool definition, identity or approval state invalidate a captured action", () => {
  const captured = approval();
  for (const changes of [
    { plan_hash: "changed" },
    { argument_hash: "changed" },
    { definition_hash: "changed" },
    { approval_id: "other" },
    { step_id: "other" },
    { state: "consumed" },
  ])
    assert.equal(
      approvalCurrent(
        captured,
        workflow({ approvals: [approval(changes)] }),
        now,
      ),
      false,
    );
  assert.equal(
    approvalCurrent(captured, workflow({ plan_hash: "changed" }), now),
    false,
  );
  const changed = workflow();
  changed.steps[0].definition_hash = "new-definition";
  assert.equal(approvalCurrent(captured, changed, now), false);
  const unresolved = workflow();
  unresolved.steps[0].resolved_arguments = null;
  assert.equal(approvalCurrent(captured, unresolved, now), false);
});

test("a polling revision change never silently rebinds an open approval dialog", () => {
  const captured = workflow();
  assert.equal(
    reviewCurrent(captured, workflow(), approval(), "approve_step", now),
    true,
  );
  assert.equal(
    reviewCurrent(
      captured,
      workflow({ revision: 5 }),
      approval(),
      "approve_step",
      now,
    ),
    false,
  );
  assert.equal(
    reviewCurrent(
      captured,
      workflow({ workflow_id: "wf_other" }),
      approval(),
      "approve_step",
      now,
    ),
    false,
  );
  assert.equal(
    reviewCurrent(
      captured,
      workflow({ plan_hash: "new-plan" }),
      undefined,
      "approve_plan",
      now,
    ),
    false,
  );
});

test("plan review binds the pending plan record and expires without requiring a resolved action", () => {
  const plan = approval({
    kind: "plan",
    step_id: null,
    argument_hash: null,
    definition_hash: null,
  });
  const current = workflow({ approvals: [plan] });
  assert.equal(
    reviewCurrent(current, current, plan, "approve_plan", now),
    true,
  );
  assert.equal(
    reviewCurrent(
      current,
      current,
      plan,
      "approve_plan",
      Date.parse(plan.expires_at),
    ),
    false,
  );
  assert.equal(
    reviewCurrent(
      current,
      workflow({ approvals: [approval({ ...plan, state: "approved" })] }),
      plan,
      "approve_plan",
      now,
    ),
    false,
  );
  assert.deepEqual(workflowPayload(current, "approve_plan", plan), {
    workflow_id: "wf_review",
    expected_revision: 4,
    plan_hash: "plan-current",
  });
});

test("revocation reviews one unused approval and cannot approve consumed or expired grants", () => {
  const approved = approval({ state: "approved" });
  const current = workflow({ approvals: [approved] });
  assert.equal(reviewCurrent(current, current, approved, "revoke", now), true);
  assert.equal(
    reviewCurrent(
      current,
      workflow({ approvals: [approval({ state: "consumed" })] }),
      approved,
      "revoke",
      now,
    ),
    false,
  );
  assert.equal(
    reviewCurrent(
      current,
      current,
      approved,
      "revoke",
      Date.parse(approved.expires_at),
    ),
    false,
  );
  assert.deepEqual(workflowPayload(current, "revoke", approved), {
    workflow_id: "wf_review",
    expected_revision: 4,
    approval_id: "approval_review",
  });
});

test("step approvals transmit exact captured bindings without granting arbitrary arguments or capabilities", () => {
  const expected = {
    workflow_id: "wf_review",
    expected_revision: 4,
    approval_id: "approval_review",
    step_id: "write",
    plan_hash: "plan-current",
    argument_hash: "arguments-current",
    definition_hash: "definition-current",
  };
  assert.deepEqual(
    workflowPayload(workflow(), "approve_step", approval()),
    expected,
  );
  assert.deepEqual(workflowPayload(workflow(), "reject", approval()), expected);
  assert.throws(
    () => workflowPayload(workflow(), "approve_step"),
    /exact pending action/,
  );
  assert.throws(
    () =>
      workflowPayload(
        workflow(),
        "approve_step",
        approval({ step_id: null, kind: "plan" }),
      ),
    /exact pending action/,
  );
});

test("start and plan approval bind the current saved plan while fixed controls retain revision checks", () => {
  for (const operation of ["start", "approve_plan"]) {
    assert.deepEqual(workflowPayload(workflow(), operation), {
      workflow_id: "wf_review",
      expected_revision: 4,
      plan_hash: "plan-current",
    });
    assert.throws(
      () => workflowPayload(workflow({ plan_hash: null }), operation),
      /saved plan/,
    );
  }
  for (const operation of ["pause", "resume", "cancel"])
    assert.deepEqual(workflowPayload(workflow(), operation), {
      workflow_id: "wf_review",
      expected_revision: 4,
    });
  assert.throws(
    () => workflowPayload(workflow(), "execute_arbitrary_tool"),
    /Unsupported/,
  );
});

test("safe retries are bound to the selected failed step rather than the whole workflow", () => {
  assert.deepEqual(
    workflowPayload(workflow(), "retry_safe", undefined, "failed-read"),
    { workflow_id: "wf_review", expected_revision: 4, step_id: "failed-read" },
  );
  assert.throws(
    () => workflowPayload(workflow(), "retry_safe"),
    /Select the safe failed step/,
  );
});

test("filters use actual persisted lifecycle states and separate attention from active execution", () => {
  for (const state of [
    "submitted",
    "planning",
    "ready",
    "running",
    "verifying",
    "retrying",
    "recovering",
  ])
    assert.equal(workflowInView(state, "active"), true);
  for (const state of [
    "awaiting_plan_approval",
    "awaiting_step_approval",
    "blocked",
    "partially_completed",
  ])
    assert.equal(workflowInView(state, "attention"), true);
  assert.equal(workflowInView("paused", "active"), false);
  assert.equal(workflowInView("paused", "paused"), true);
  assert.equal(workflowInView("completed", "attention"), false);
  assert.equal(workflowInView("completed", "all"), true);
  assert.equal(
    workflowInView("awaiting_step_approval", "awaiting_approval"),
    true,
  );
  assert.equal(
    workflowInView("awaiting_plan_approval", "awaiting_approval"),
    true,
  );
  assert.equal(workflowInView("blocked", "awaiting_approval"), false);
});

test("elapsed time uses recorded boundaries, includes pauses and rejects invalid or backwards clocks", () => {
  const start = "2026-10-09T14:00:00Z";
  assert.equal(elapsedSinceStart(start, null, now), "1h 0m");
  assert.equal(elapsedSinceStart(start, "2026-10-09T14:01:05Z", now), "1m 5s");
  assert.equal(elapsedSinceStart(start, "2026-10-09T14:00:02Z", now), "2s");
  assert.equal(elapsedSinceStart(null, null, now), "Not started");
  assert.equal(elapsedSinceStart("invalid", null, now), "Unavailable");
  assert.equal(
    elapsedSinceStart(start, "2026-10-09T13:59:00Z", now),
    "Unavailable",
  );
});

test("duplicate clicks share a synchronous pending lock and cannot create parallel requests", () => {
  const ledger = new WorkflowRequestLedger();
  const first = ledger.begin(
    "goal.submit",
    { goal: "Check RAM", mode: "assisted" },
    "token",
    () => "request-1",
  );
  assert.ok(first);
  assert.equal(
    ledger.begin(
      "goal.submit",
      { goal: "Check RAM", mode: "assisted" },
      "token",
      () => "request-2",
    ),
    null,
  );
  assert.equal(ledger.current(first), true);
  assert.equal(ledger.finish(first, true), true);
  assert.equal(ledger.current(first), false);
});

test("an ambiguous failed request reuses its UUID only for an identical explicit retry", () => {
  const ledger = new WorkflowRequestLedger();
  const first = ledger.begin(
    "cancel",
    { workflow_id: "wf_review", expected_revision: 4 },
    "token",
    () => "request-1",
  )!;
  ledger.finish(first, false);
  const retry = ledger.begin(
    "cancel",
    { workflow_id: "wf_review", expected_revision: 4 },
    "token",
    () => "request-2",
  )!;
  assert.equal(retry.id, first.id);
  ledger.finish(retry, false);
  const changed = ledger.begin(
    "cancel",
    { workflow_id: "wf_review", expected_revision: 5 },
    "token",
    () => "request-3",
  )!;
  assert.equal(changed.id, "request-3");
});

test("successful completion clears UUID reuse for a later distinct user action", () => {
  const ledger = new WorkflowRequestLedger();
  const first = ledger.begin("pause", {}, "token", () => "request-1")!;
  ledger.finish(first, true);
  assert.equal(
    ledger.begin("pause", {}, "token", () => "request-2")?.id,
    "request-2",
  );
});

test("token rotation rejects late responses and cannot clear the new session's active request", () => {
  const ledger = new WorkflowRequestLedger();
  const old = ledger.begin(
    "goal.submit",
    { goal: "Private goal" },
    "old-token",
    () => "old-id",
  )!;
  ledger.reset("new-token");
  const current = ledger.begin(
    "goal.submit",
    { goal: "New goal" },
    "new-token",
    () => "new-id",
  )!;
  assert.equal(ledger.current(old), false);
  assert.equal(ledger.finish(old, true), false);
  assert.equal(ledger.current(current), true);
  assert.equal(ledger.finish(current, true), true);
  assert.equal(
    ledger.begin("goal.submit", {}, "", () => "invalid"),
    null,
  );
});
