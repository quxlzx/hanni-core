export type CronJob = {
  id: string; title: string; prompt: string; interval_seconds: number; enabled: number;
  next_run: number; last_task_id: string | null; auto_approve: string[];
  cadence: "interval" | "daily" | "weekly"; at_time: string; timezone: string; weekday: number;
  conversation: string; next_run_local: string; delivery: string;
};
export function repeatLabel(job: Pick<CronJob, "cadence" | "at_time" | "weekday" | "interval_seconds" | "timezone">): string {
  if (job.cadence === "daily") return `Daily at ${job.at_time} · ${job.timezone}`;
  if (job.cadence === "weekly") return `Every ${["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][job.weekday]} at ${job.at_time} · ${job.timezone}`;
  const minutes = job.interval_seconds / 60;
  return minutes % 1440 === 0 ? `Every ${minutes / 1440} day(s)`
    : minutes % 60 === 0 ? `Every ${minutes / 60} hour(s)` : `Every ${minutes} minute(s)`;
}
export const AI_NEWS_PROMPT = "Search current sources for the most important AI news from the past 24 hours. Summarize five developments with source links and publication dates. Distinguish confirmed announcements from speculation. If live sources are unavailable, report that limitation rather than inventing news. Return the digest in this conversation.";
