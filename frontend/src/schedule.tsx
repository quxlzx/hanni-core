import { usePrivateResource } from "./feature_types";
import { write } from "./api";
import { useRef, useState, type FormEvent } from "react";
import { AI_NEWS_PROMPT, repeatLabel, type CronJob } from "./schedule_fields";
import "./schedule.css";

type CronData = { jobs: CronJob[]; note?: string; timezone?: string };
const fmt = (job: CronJob) => new Date(job.next_run * 1000).toLocaleString([], {
  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: job.timezone,
});

export function SchedulePage({ token }: { token: string }) {
  const data = usePrivateResource<CronData>("/api/cron/jobs", token, 5000);
  const [title, setTitle] = useState(""), [prompt, setPrompt] = useState("");
  const [frequency, setFrequency] = useState("daily"), [atTime, setAtTime] = useState("09:00");
  const [zone, setZone] = useState<string | null>(null), [weekday, setWeekday] = useState(0), [minutes, setMinutes] = useState(60);
  const [busy, setBusy] = useState(false), [failure, setFailure] = useState("");
  const [saved, setSaved] = useState<CronJob | null>(null), [remove, setRemove] = useState("");
  const lock = useRef(false), pending = useRef<{ signature: string; id: string } | null>(null);
  const timezone = zone ?? data.data?.timezone ?? "UTC";

  async function create(event: FormEvent) {
    event.preventDefault();
    if (lock.current || !token) return;
    const body = { title: title.trim(), prompt: prompt.trim(), frequency, timezone,
      ...(frequency === "daily" || frequency === "weekly" ? { at_time: atTime } : {}),
      ...(frequency === "weekly" ? { weekday } : {}),
      ...(frequency === "interval" ? { interval_seconds: minutes * 60 } : {}) };
    const signature = JSON.stringify(body);
    if (!pending.current || pending.current.signature !== signature)
      pending.current = { signature, id: crypto.randomUUID() };
    lock.current = true; setBusy(true); setFailure(""); setSaved(null);
    try {
      const result = await write<CronJob & { error?: string }>("/api/cron/jobs", token, { id: pending.current.id, ...body });
      if (result.error) throw new Error(result.error);
      setSaved(result); setTitle(""); setPrompt(""); pending.current = null; data.refresh();
    } catch (error) { setFailure(error instanceof Error ? error.message : "The schedule was not confirmed. Retry to check the same request."); }
    finally { lock.current = false; setBusy(false); }
  }
  async function update(job: CronJob, action: "enable" | "disable" | "delete") {
    if (lock.current || !token) return;
    lock.current = true; setBusy(true); setFailure("");
    try {
      const result = await write<{ error?: string }>(`/api/cron/job/${job.id}/${action}`, token, {});
      if (result.error) throw new Error(result.error);
      setRemove(""); if (saved?.id === job.id && action === "delete") setSaved(null); data.refresh();
    } catch (error) { setFailure(error instanceof Error ? error.message : "Update failed. Refresh to check the current schedule."); }
    finally { lock.current = false; setBusy(false); }
  }
  return <section className="screen-section repeating-tasks">
    <div className="section-title"><h2>Repeating tasks</h2><span>Updates delivered to your conversations</span></div>
    <p className="subtle">Run a task hourly, daily, weekly, or at your own interval. Hanni must be running; missed runs catch up once after the next launch.</p>
    <form onSubmit={create} className="repeat-create" aria-label="Create repeating task">
      <div className="repeat-form-heading"><h3>New repeating task</h3>
        <button type="button" disabled={busy} onClick={() => { setTitle("Daily AI news"); setPrompt(AI_NEWS_PROMPT); setFrequency("daily"); setAtTime("09:00"); }}>Use AI news example</button></div>
      <label>Task name<input required maxLength={120} value={title} onChange={event => setTitle(event.target.value)} placeholder="Daily AI news" disabled={busy} /></label>
      <label>What should Hanni do?<textarea required rows={4} maxLength={8000} value={prompt} onChange={event => setPrompt(event.target.value)} placeholder="Search today’s AI news and summarize the key developments with sources." disabled={busy} /></label>
      <div className="repeat-fields">
        <label>Repeat<select value={frequency} onChange={event => setFrequency(event.target.value)} disabled={busy}>
          <option value="daily">Daily</option><option value="weekly">Weekly</option><option value="hourly">Hourly</option><option value="interval">Custom interval</option>
        </select></label>
        {frequency === "weekly" && <label>Day<select value={weekday} onChange={event => setWeekday(Number(event.target.value))} disabled={busy}>
          {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((day, index) => <option key={day} value={index}>{day}</option>)}
        </select></label>}
        {(frequency === "daily" || frequency === "weekly") && <label>Time<input required type="time" value={atTime} onChange={event => setAtTime(event.target.value)} disabled={busy} /></label>}
        {frequency === "interval" && <label>Every (minutes)<input required type="number" min={1} max={525600} step={1} value={minutes} onChange={event => setMinutes(Number(event.target.value))} disabled={busy} /></label>}
        <label>Timezone<input required value={timezone} onChange={event => setZone(event.target.value)} placeholder="America/Chicago" disabled={busy} /></label>
      </div>
      <p className="subtle">Results will appear in a new conversation. Read-only tools run automatically; other actions wait for your approval in Task review.</p>
      <button type="submit" disabled={busy || !token || !title.trim() || !prompt.trim()}>{busy ? "Saving…" : "Create repeating task"}</button>
    </form>
    {saved && <p className="repeat-saved" role="status">Saved <strong>{saved.title}</strong>. Next run: {fmt(saved)} ({saved.timezone}). <a href={`/?conversation=${encodeURIComponent(saved.conversation)}`}>Open conversation</a></p>}
    {(failure || data.error) && <p className="error" role="alert">{failure || data.error}</p>}
    <div className="repeat-list-heading"><h3>Saved tasks ({data.data?.jobs.length || 0})</h3><button type="button" onClick={data.refresh} disabled={busy}>Refresh tasks</button></div>
    {(data.data?.jobs || []).map(job => <article key={job.id} className="repeat-job" aria-label={job.title}>
      <header><h3>{job.title}</h3><span>{job.enabled ? "Active" : "Paused"}</span></header>
      <p>{repeatLabel(job)}</p><p className="subtle">{job.enabled ? "Next run" : "Pending slot"}: {fmt(job)} ({job.timezone})</p>
      <details><summary>Task instructions</summary><p className="repeat-prompt">{job.prompt}</p></details>
      <div className="repeat-job-actions">
        <a href={`/?conversation=${encodeURIComponent(job.conversation)}`}>Open conversation</a>
        <button type="button" disabled={busy || !token} onClick={() => update(job, job.enabled ? "disable" : "enable")}>{job.enabled ? "Pause" : "Resume"}</button>
        <button type="button" disabled={busy || !token} onClick={() => setRemove(job.id)}>Delete</button>
      </div>
      {remove === job.id && <div className="repeat-delete"><p>Delete this repeating task? Existing runs and their results stay in the conversation.</p>
        <button type="button" disabled={busy} onClick={() => setRemove("")}>Keep task</button>
        <button type="button" disabled={busy || !token} onClick={() => update(job, "delete")}>Delete schedule</button></div>}
      <small>Schedule ID: {job.id}{job.last_task_id ? ` · Last run: ${job.last_task_id}` : " · Has not run yet"}</small>
    </article>)}
    {!data.data?.jobs.length && !data.error && <p className="subtle">No repeating tasks yet. Create one above, or use <code>/schedule daily 09:00 | Your task</code> in chat.</p>}
  </section>;
}
