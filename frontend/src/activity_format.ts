import type { ReviewTask } from "./task_review";

export type ActivityRun = ReviewTask & {
  key?: string | null;
  created: number;
  updated: number;
  request?: { prompt?: string; context?: { conversation_id?: string; parent_task_id?: string; scheduled_job_id?: string; batch_id?: string } };
  events?: { time?: number; at?: number; text: string }[];
  result?: { model_claims?: string; stats?: { elapsed_seconds?: number | null } | null; activity?: { phase?: string; tool?: string } | null } | null;
};

export function capabilityLabel(value: string): string {
  const names: Record<string, string> = {
    local_read_file: "Read a file", local_read_document: "Read a document", local_list_dir: "List files",
    local_search_files: "Find files", local_write_file: "Write a file", local_terminal: "Run a command",
    local_python: "Run Python", web_search: "Search the web", web_fetch: "Read a web page",
    system_info: "Check system information", skill_read: "Read a skill", skill_save: "Save a skill",
    skill_propose: "Propose a skill", session_search: "Search conversation history", history_search: "Search conversation history",
    memory_search: "Search memory", working_state: "Update working notes", delegate_task: "Delegate a task",
    agent_job: "Check a background task", schedule_task: "Create a repeating task", scheduled_tasks: "Manage repeating tasks",
    "time.now": "Check the time", "google_calendar.list_events": "Read calendar events",
    "workspace.google_accounts": "Manage Google accounts", "workspace.tool_access": "Change tool access",
  };
  return names[value] || value.replace(/^local_/, "").replace(/[._-]+/g, " ").replace(/^./, letter => letter.toUpperCase());
}

export function activityDuration(milliseconds: number | null | undefined): string {
  if (typeof milliseconds !== "number" || !Number.isFinite(milliseconds) || milliseconds < 0) return "Not recorded";
  if (milliseconds < 1000) return `${Math.round(milliseconds)} ms`;
  if (milliseconds < 60000) return `${Number((milliseconds / 1000).toFixed(1))} s`;
  const seconds = Math.round(milliseconds / 1000);
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

export function runSource(run: ActivityRun): string {
  const context = run.request?.context;
  if (context?.parent_task_id) return "Delegated task";
  if (context?.scheduled_job_id || run.key?.startsWith("cron-")) return "Repeating task";
  if (context?.batch_id) return "Training batch";
  if (context?.conversation_id || run.key?.startsWith("chat-")) return "Conversation";
  return "Background task";
}

export function runMatches(run: ActivityRun, search: string, filter: string): boolean {
  const state = run.state;
  const active = ["queued", "running", "approval"].includes(state);
  const attention = ["approval", "failed", "interrupted", "uncertain"].includes(state)
    || (run.actions || []).some(action => action.receipt?.ok === false || ["rejected", "uncertain"].includes(action.state));
  if (filter === "active" && !active || filter === "attention" && !attention
      || filter === "ready" && !["review_required", "completed"].includes(state)
      || filter === "cancelled" && state !== "cancelled") return false;
  return [run.id, run.request?.prompt, runSource(run), run.error, ...(run.actions || []).map(a => a.spec.name)]
    .join(" ").toLowerCase().includes(search.trim().toLowerCase());
}

export function conversationLink(run: ActivityRun): string | null {
  const id = run.request?.context?.conversation_id;
  return typeof id === "string" && /^[a-z0-9-]{1,64}$/i.test(id) ? `/?conversation=${encodeURIComponent(id)}#chat` : null;
}
