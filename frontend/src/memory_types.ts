export type MemoryRecord = {
  id: string;
  content: string;
  memory_type: string;
  semantic_status: string;
  project_id: string;
  source: string;
  source_ref: string;
  created_at: string;
  updated_at: string;
  fact_key: string;
  confidence_calibrated: false;
};
export type MemorySuggestion = {
  id: string;
  kind: string;
  content: string;
  source: string;
  source_ref: string;
  target_id: string;
  target_updated_at: string;
  project_id: string;
  semantic_status: string;
  reason: string;
  uncertainty: string;
  related_ids: string[];
  status: string;
  created_at: string;
  updated_at: string;
};
export type MemoryProject = {
  id: string;
  name: string;
  description: string;
  fingerprint: string;
  aliases: string[];
};
export type MemoryStatus = {
  mode: string;
  description: string;
  model_inference_active: boolean;
  production_retrieval_active: boolean;
  remote_memory_transmission: boolean;
  semantic_search_available: boolean;
};
export type MemoryExplorerData = {
  available: boolean;
  records: MemoryRecord[];
  projects: MemoryProject[];
  total_stored: number;
  filtered_count: number | null;
  pending_suggestions: number;
  offset: number;
  limit: number;
  has_more: boolean;
  reason: string | null;
  status: MemoryStatus;
};
export type MemoryDetailData = {
  available: boolean;
  record: MemoryRecord | null;
  history: MemoryRecord[];
  history_count?: number;
  history_offset?: number;
  history_has_more?: boolean;
  history_withheld?: number;
  project: MemoryProject | null;
  project_missing?: boolean;
  reason: string | null;
};
export type MemorySuggestionsData = {
  available: boolean;
  items: MemorySuggestion[];
  offset: number;
  limit: number;
  has_more: boolean;
  total: number;
  status: MemoryStatus;
  reason: string | null;
};
export type ProjectContextData = {
  available: boolean;
  reason: string | null;
  context: {
    project: MemoryProject;
    memories: MemoryRecord[];
    decisions: MemoryRecord[];
    plans: MemoryRecord[];
    verified_results: {
      workflow_id: string;
      step_id: string;
      summary: string;
      finished_at: string;
      source: string;
    }[];
    known_issues: {
      workflow_id: string;
      step_id: string;
      status: string;
      summary: string;
    }[];
    workflow_history: {
      workflow_id: string;
      goal: string;
      status: string;
      updated_at: string;
      revision: number;
    }[];
    workflow_links: { project_id: string; workflow_id: string }[];
    notes: {
      id: string;
      title: string;
      body: string;
      updated_at: string;
      source: string;
    }[];
    files: { id: string; label: string; target: string; kind: string }[];
    artifacts: {
      step_id: string;
      path: string | null;
      sha256: string | null;
      verified: boolean;
    }[];
    uncertainties: string[];
    context_text: string;
    context_chars: number;
    omitted_context_lines: number;
  };
};
export function currentMemory(
  data: MemoryDetailData | null,
  selectedId: string,
) {
  return data?.available && data.record?.id === selectedId ? data.record : null;
}
export function suggestionApplyAllowed(suggestion: MemorySuggestion) {
  return (
    suggestion.status === "pending" &&
    ["add", "correct"].includes(suggestion.kind) &&
    suggestion.semantic_status !== "verified_outcome"
  );
}
export function correctionData(
  record: MemoryRecord,
  content: string,
  projectId: string,
  semanticStatus: string,
) {
  return {
    memory_id: record.id,
    expected_updated_at: record.updated_at,
    content,
    project_id: projectId,
    semantic_status: semanticStatus,
  };
}
export function reviewData(
  suggestion: MemorySuggestion,
  action: "approve" | "reject" | "dismiss",
  content: string | null = null,
) {
  return {
    suggestion_id: suggestion.id,
    expected_updated_at: suggestion.updated_at,
    action,
    edited_content: content,
  };
}
export class MemoryRequestLedger {
  private pending: { binding: string; id: string } | null = null;
  payload(operation: string, data: object) {
    const binding = JSON.stringify([operation, data]);
    if (this.pending?.binding !== binding)
      this.pending = { binding, id: crypto.randomUUID() };
    return { id: this.pending!.id, operation, data, confirmed: true };
  }
  clear() {
    this.pending = null;
  }
}
