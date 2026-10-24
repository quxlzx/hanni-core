export type TaskReceipt = {
  ok?: boolean;
  message?: string;
  error?: string;
  error_code?: string;
  effects?: string;
  data?: unknown;
  [key: string]: unknown;
};
export type ReviewAction = {
  id: string;
  task?: string;
  state: string;
  created?: number;
  expires?: number;
  review_hash?: string;
  spec: { name: string; target?: string };
  arguments?: Record<string, unknown>;
  receipt?: TaskReceipt | null;
};
export type ReviewTask = {
  id: string;
  state: string;
  actions?: ReviewAction[];
  error?: string;
};
export const terminalTask = (state: string) =>
  ["completed", "review_required", "failed", "cancelled", "interrupted", "uncertain"].includes(state);

export function taskState(state: string): string {
  return ({ queued: "Queued", running: "In progress", approval: "Awaiting approval",
    review_required: "Response ready to review", completed: "Completed", failed: "Failed",
    cancelled: "Cancelled", interrupted: "Interrupted", uncertain: "Outcome uncertain" } as Record<string, string>)[state] || "Status unavailable";
}

export function actionState(action: ReviewAction, now: number): string {
  if (action.state === "pending") return action.expires != null && now >= action.expires ? "Approval expired" : "Awaiting approval";
  if (action.state === "dispatching") return "Executing · receipt pending";
  if (action.state === "rejected") return "Denied";
  if (action.state === "uncertain") return "Outcome uncertain";
  if (action.state === "fulfilled") return action.receipt?.ok === true ? "Tool returned successfully"
    : action.receipt?.ok === false ? "Tool returned an error" : "Receipt needs review";
  return "Status unavailable";
}

export function canDecide(task: ReviewTask, action: ReviewAction, now: number): boolean {
  return !terminalTask(task.state) && action.task === task.id && action.state === "pending"
    && typeof action.expires === "number" && Number.isFinite(action.expires) && now < action.expires
    && typeof action.review_hash === "string" && /^[0-9a-f]{64}$/.test(action.review_hash)
    && ["local", "mcp"].includes(action.spec.target || "");
}

export function reviewDecision(task: ReviewTask, action: ReviewAction, state: "dispatching" | "rejected", now: number) {
  if (!canDecide(task, action, now)) throw new Error("This request is no longer available for approval. Refresh the task.");
  return { state, task_id: task.id, expected_hash: action.review_hash! };
}
