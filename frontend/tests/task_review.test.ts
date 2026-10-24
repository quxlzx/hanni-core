import assert from "node:assert/strict";
import test from "node:test";
import { actionState, canDecide, reviewDecision, taskState, terminalTask, type ReviewAction } from "../src/task_review.ts";

const action: ReviewAction = { id: "action-1", task: "task-1", state: "pending", expires: 200,
  review_hash: "a".repeat(64), spec: { name: "local_write_file", target: "local" },
  arguments: { path: "notes.txt", content: "exact content" } };
const task = { id: "task-1", state: "approval", actions: [action] };

test("decisions bind the exact task and reviewed action fingerprint", () => {
  assert.ok(canDecide(task, action, 100));
  assert.deepEqual(reviewDecision(task, action, "dispatching", 100), {
    state: "dispatching", task_id: "task-1", expected_hash: "a".repeat(64),
  });
  assert.equal(reviewDecision(task, action, "rejected", 100).state, "rejected");
});
test("expired, missing, mismatched and already dispatched requests cannot be decided", () => {
  for (const changed of [{ ...action, expires: 100 }, { ...action, expires: undefined },
    { ...action, expires: NaN }, { ...action, review_hash: undefined }, { ...action, review_hash: "invalid" },
    { ...action, task: "other-task" }, { ...action, state: "dispatching" },
    { ...action, state: "fulfilled" }, { ...action, spec: { ...action.spec, target: "windows" } }]) {
    assert.equal(canDecide(task, changed, 100), false);
    assert.throws(() => reviewDecision(task, changed, "dispatching", 100));
  }
  assert.ok(canDecide(task, { ...action, spec: { ...action.spec, target: "mcp" } }, 100));
});
test("terminal tasks cannot grant new execution authority", () => {
  for (const state of ["review_required", "completed", "failed", "cancelled", "interrupted", "uncertain"]) {
    assert.ok(terminalTask(state));
    assert.equal(canDecide({ ...task, state }, action, 100), false);
  }
  assert.equal(taskState("review_required"), "Response ready to review");
});
test("dispatch and model completion never imply a successful execution receipt", () => {
  assert.equal(actionState({ ...action, state: "dispatching" }, 100), "Executing · receipt pending");
  assert.equal(actionState({ ...action, state: "fulfilled", receipt: null }, 100), "Receipt needs review");
  assert.equal(actionState({ ...action, state: "fulfilled", receipt: { ok: false, error: "auth expired" } }, 100), "Tool returned an error");
  assert.equal(actionState({ ...action, state: "fulfilled", receipt: { ok: true } }, 100), "Tool returned successfully");
  assert.equal(actionState(action, 200), "Approval expired");
});
