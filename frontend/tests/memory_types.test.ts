import test from "node:test";
import assert from "node:assert/strict";
import {
  currentMemory,
  correctionData,
  reviewData,
  suggestionApplyAllowed,
  MemoryRequestLedger,
  type MemoryRecord,
  type MemorySuggestion,
} from "../src/memory_types.ts";

const record: MemoryRecord = {
  id: "memory-a",
  content: "A synthetic fact",
  memory_type: "fact",
  semantic_status: "statement",
  project_id: "",
  source: "owner_explicit:synthetic",
  source_ref: "conversation:synthetic",
  created_at: "2026-10-09T15:00:00Z",
  updated_at: "2026-10-09T15:00:00Z",
  fact_key: "",
  confidence_calibrated: false,
};
const suggestion: MemorySuggestion = {
  id: "proposal-a",
  kind: "add",
  content: "Synthetic preference",
  source: "laya:synthetic",
  source_ref: "conversation:synthetic",
  target_id: "",
  target_updated_at: "",
  project_id: "",
  semantic_status: "statement",
  reason: "Explicit preference",
  uncertainty: "Unverified",
  related_ids: [],
  status: "pending",
  created_at: record.created_at,
  updated_at: record.updated_at,
};

test("a delayed detail from a different selection cannot authorize an edit", () => {
  const detail = {
    available: true,
    record,
    history: [],
    project: null,
    reason: null,
  };
  assert.equal(currentMemory(detail, "memory-b"), null);
  assert.equal(currentMemory(detail, record.id), record);
  assert.equal(currentMemory({ ...detail, available: false }, record.id), null);
});
test("correction binds exact identity/version and contains no owner authority or verified claims", () => {
  assert.deepEqual(
    correctionData(record, "Corrected fact", "project-a", "plan"),
    {
      memory_id: record.id,
      expected_updated_at: record.updated_at,
      content: "Corrected fact",
      project_id: "project-a",
      semantic_status: "plan",
    },
  );
});
test("review binds the suggestion version and separates proposed text from owner correction", () => {
  assert.deepEqual(reviewData(suggestion, "approve", "Owner edited content"), {
    suggestion_id: suggestion.id,
    expected_updated_at: suggestion.updated_at,
    action: "approve",
    edited_content: "Owner edited content",
  });
  assert.equal(suggestionApplyAllowed(suggestion), true);
  for (const kind of ["duplicate", "conflict", "stale", "related", "archive"])
    assert.equal(suggestionApplyAllowed({ ...suggestion, kind }), false);
  assert.equal(
    suggestionApplyAllowed({
      ...suggestion,
      semantic_status: "verified_outcome",
    }),
    false,
  );
  assert.equal(
    suggestionApplyAllowed({ ...suggestion, status: "approved" }),
    false,
  );
});
test("uncertain retry keeps UUID only for the identical exact action", () => {
  const ledger = new MemoryRequestLedger();
  const first = ledger.payload(
    "correct",
    correctionData(record, "Updated", "", "statement"),
  );
  const retry = ledger.payload(
    "correct",
    correctionData(record, "Updated", "", "statement"),
  );
  assert.equal(first.id, retry.id);
  assert.notEqual(
    first.id,
    ledger.payload(
      "correct",
      correctionData(record, "Changed draft", "", "statement"),
    ).id,
  );
  assert.equal(first.confirmed, true);
  ledger.clear();
  assert.notEqual(
    first.id,
    ledger.payload(
      "correct",
      correctionData(record, "Updated", "", "statement"),
    ).id,
  );
});
