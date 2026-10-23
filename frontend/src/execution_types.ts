export type Verification = {
  status: string;
  method: string;
  scope: string;
  independent: boolean;
  checks: Record<string, boolean>;
};
export type TraceEvent = { state: string; timestamp: string };
export type ExecutionStep = {
  step_id: string;
  capability_id: string;
  state: string;
  started_at: string;
  completed_at: string | null;
  attempts: number;
  approval: string;
  verification: Verification | null;
  error_class: string | null;
  events: TraceEvent[];
  superseded?: boolean;
};
export type ExecutionTask = {
  request_id: string;
  task_id: string;
  source: string;
  created_at: string;
  completed_at: string | null;
  state: string;
  execution_status: string;
  verification_status: string;
  selected_capabilities: string[];
  candidate_capabilities?: string[];
  summary: string;
  error_class: string | null;
  retry_count: number;
  steps: ExecutionStep[];
  events: TraceEvent[];
  truncated_steps?: boolean;
};
export type ExecutionData = {
  available: boolean;
  tasks: ExecutionTask[];
  reason: string | null;
};
export function traceLabel(value: string) {
  return value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (letter) => letter.toUpperCase());
}
