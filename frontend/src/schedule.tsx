// Schedule: agent cron jobs on this machine.
import { usePrivateResource } from "./feature_types";
import { write } from "./api";
import { useState } from "react";

type CronJob = {
  id: string; prompt: string; interval_seconds: number; enabled: number;
  next_run: number; last_task_id: string | null; auto_approve: string[];
};
type CronData = { jobs: CronJob[]; note?: string };

const fmt = (seconds: number) =>
  new Date(seconds * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

export function SchedulePage({ token }: { token: string }) {
  const data = usePrivateResource<CronData>("/api/cron/jobs", token, 15000);
  const [note, setNote] = useState("");
  async function toggle(job: CronJob, enable: boolean) {
    setNote("");
    try {
      await write(`/api/cron/job/${job.id}/${enable ? "enable" : "disable"}`, token, {});
      data.refresh();
    } catch (e) { setNote(e instanceof Error ? e.message : "Update failed."); }
  }
  return (
    <section className="screen-section">
      <div className="section-title"><h2>Scheduled work</h2><span>Agent cron on this machine</span></div>
      {data.error && <p className="error">Cron store unreachable: {data.error}</p>}
      {data.data?.note && <p className="subtle">{data.data.note}</p>}
      {note && <p className="error" role="alert">{note}</p>}
      {(data.data?.jobs ?? []).map((job) => (
        <div key={job.id} className="cluster-notice">
          <strong>{job.enabled ? "Active" : "Paused"}</strong>
          {" "}every {Math.round(job.interval_seconds / 60)} min · next {fmt(job.next_run)}
          <p>{job.prompt.slice(0, 240)}</p>
          {job.auto_approve.length ? (
            <p className="subtle">Pre-authorized tools: {job.auto_approve.join(", ")}</p>
          ) : <p className="subtle">Every action needs your approval.</p>}
          <div className="dialog-actions">
            <button disabled={!token} onClick={() => toggle(job, !job.enabled)}>
              {job.enabled ? "Pause" : "Resume"}
            </button>
          </div>
        </div>
      ))}
      {!(data.data?.jobs ?? []).length && !data.error && !data.data?.note && (
        <p className="subtle">No scheduled jobs yet.</p>
      )}
    </section>
  );
}
