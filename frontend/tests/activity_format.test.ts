import assert from "node:assert/strict";
import test from "node:test";
import { activityDuration, capabilityLabel, conversationLink, runMatches, runSource, type ActivityRun } from "../src/activity_format.ts";

const run: ActivityRun = { id: "native-run", state: "review_required", created: 1, updated: 2,
  key: "chat-turn", request: { prompt: "Summarize quarterly results", context: { conversation_id: "default" } },
  actions: [{ id: "read", state: "fulfilled", spec: { name: "local_read_file" }, receipt: { ok: false, error: "File missing" } }] };

test("response readiness never hides a failed receipt from attention filtering", () => {
  assert.ok(runMatches(run, "", "attention"));
  assert.ok(runMatches(run, "", "ready"));
  assert.ok(!runMatches(run, "", "active"));
  const clean = { ...run, actions: [{ ...run.actions![0], receipt: { ok: true } }] };
  assert.ok(!runMatches(clean, "", "attention"));
  assert.ok(runMatches({ ...clean, state: "uncertain" }, "", "attention"));
  assert.ok(runMatches({ ...clean, state: "approval" }, "", "active"));
});

test("search finds owner requests, tool identifiers, source and run ids", () => {
  assert.ok(runMatches(run, "QUARTERLY", "all"));
  assert.ok(runMatches(run, "local_read_file", "all"));
  assert.ok(runMatches(run, "native-run", "all"));
  assert.ok(runMatches(run, " conversation ", "all"));
  assert.ok(!runMatches(run, "not present", "all"));
});

test("run origins remain distinct and conversation links accept only local ids", () => {
  assert.equal(runSource(run), "Conversation");
  assert.equal(runSource({ ...run, request: { context: { parent_task_id: "parent", conversation_id: "default" } } }), "Delegated task");
  assert.equal(runSource({ ...run, key: "cron-one", request: {} }), "Repeating task");
  assert.equal(runSource({ ...run, request: { context: { batch_id: "batch" } } }), "Training batch");
  assert.equal(conversationLink(run), "/?conversation=default#chat");
  assert.equal(conversationLink({ ...run, request: { context: { conversation_id: "https://foreign.example/" } } }), null);
  assert.equal(conversationLink({ ...run, request: { context: { conversation_id: "../private" } } }), null);
  assert.equal(conversationLink({ ...run, request: undefined }), null);
});

test("missing or invalid timings are never reported as measured zero", () => {
  for (const value of [undefined, null, NaN, Infinity, -1]) assert.equal(activityDuration(value), "Not recorded");
  assert.equal(activityDuration(0), "0 ms");
  assert.equal(activityDuration(980), "980 ms");
  assert.equal(activityDuration(1250), "1.3 s");
  assert.equal(activityDuration(125000), "2m 5s");
  assert.equal(capabilityLabel("local_read_document"), "Read a document");
  assert.equal(capabilityLabel("custom_service.deep_check"), "Custom service deep check");
});
