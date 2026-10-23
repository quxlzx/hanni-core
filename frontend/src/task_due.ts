import type { TaskRecord } from "./feature_types";

/** Preserve the original store's explicit date-only versus timed distinction. */
export function taskDuePayload(task: Pick<TaskRecord, "due" | "all_day">) {
  return task.due
    ? task.all_day
      ? task.due.slice(0, 10)
      : task.due
    : null;
}
