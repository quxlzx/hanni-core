
import { useState } from "react";
import { FeatureDialog } from "./feature_ui";
import { write, request } from "./api";
import { usePrivateResource } from "./feature_types";
import "./compute.css";
import { workerStatus } from "./cluster_status";

export type ComputeJob = {
  job_id: string; workflow_id: string; step_id: string;
  worker_id: string | null; model_id: string | null; state: string;
  verification_status: string; selection_reason?: string;
  latency_ms?: number; queue_ms?: number; error?: string;
};
type Worker = {
  worker_id: string; node_id: string; label: string; gpu: string | null;
  model_id: string | null; configured_model: string | null; enabled: boolean;
  status: string; last_heartbeat: number | null;
  last_healthy_at?: number | null; consecutive_health_failures?: number;
  context_configured: number | null; context_reported: number | null;
  max_context_verified: number | null; current_jobs: number;
  queue_depth: number | null; vram_free_bytes: number | null;
  latency_ms: number | null; throughput_tps: number | null;
  concurrency: number; interactive_reserve: number;
  allowed_categories: string[]; error: string | null; start_supported: boolean;
};
type ComputeData = { available: boolean; enabled: boolean; reason: string | null; workers: Worker[]; jobs: ComputeJob[]; control_blocked_reason?: string | null };
const number = (value: number | null | undefined) => value == null ? "Unknown" : value.toLocaleString();

function LegacyComputeWorkers({ token, nodeId }: { token: string; nodeId?: string }) {
  const resource = usePrivateResource<ComputeData>("/api/compute", token, 3000);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [review, setReview] = useState<Worker | null>(null);
  const data = resource.data;
  const rows = (data?.workers || []).filter(row => !nodeId || row.node_id === nodeId);
  async function refreshWorkers() {
    try { await request("/api/compute?refresh=1", { headers: { "X-Hanni-Token": token } }); resource.refresh(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Compute refresh failed."); }
  }
  async function control(worker: Worker, operation: string, values: Record<string, unknown>) {
    if (pending || resource.error || !token) return;
    setPending(worker.worker_id); setError("");
    try {
      await write("/api/compute", token, { id: crypto.randomUUID(), worker_id: worker.worker_id, operation, data: values, confirmed: operation === "start" });
      resource.refresh();
      setReview(null);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Compute request failed."); }
    finally { setPending(null); }
  }
  return <section className="compute-section" aria-label="Distributed inference workers">
    <header className="compute-heading"><div><h2>Compute workers</h2><p>{data?.enabled ? "Controller-managed inference" : "Distributed inference is disabled"}</p></div><button onClick={refreshWorkers}>Refresh workers</button></header>
    {(resource.error || error || data?.reason || data?.control_blocked_reason) && <p role="status" className="error">{resource.error || error || data?.reason || data?.control_blocked_reason}</p>}
    {!data && !resource.error && <p className="subtle">Reading the private compute registry…</p>}
    {data && !rows.length && <div className="compute-empty"><h3>{nodeId ? "No inference workers registered for this node" : "No inference workers registered"}</h3><p>Add a verified endpoint in the local compute deployment. Missing hardware and context measurements remain unknown.</p></div>}
    {rows.map(worker => <article className="compute-worker" key={worker.worker_id}>
      <header><div><h3>{worker.label}</h3><p>{worker.node_id.toUpperCase()} · {worker.gpu || "Device not measured"}</p></div><strong>{workerStatus(worker, Date.now() / 1000, !!resource.error)}</strong></header>
      <dl className="compute-fields">
        <div><dt>Loaded model</dt><dd>{worker.model_id || "Not reported"}</dd></div>
        <div><dt>Verified context</dt><dd>{worker.max_context_verified == null ? "Unverified" : `${number(worker.max_context_verified)} tokens`}</dd></div>
        <div><dt>Active / limit</dt><dd>{worker.current_jobs} / {worker.concurrency}</dd></div>
        <div><dt>Server queue</dt><dd>{number(worker.queue_depth)}</dd></div>
        <div><dt>Free VRAM</dt><dd>{worker.vram_free_bytes == null ? "Unknown" : `${(worker.vram_free_bytes / 1024 ** 3).toFixed(2)} GiB`}</dd></div>
        <div><dt>Last request</dt><dd>{worker.latency_ms == null ? "Not measured" : `${worker.latency_ms.toFixed(0)} ms`}</dd></div>
      </dl>
      <details><summary>Limits, trust and diagnostics</summary><dl className="compute-fields">
        <div><dt>Configured context</dt><dd>{number(worker.context_configured)}</dd></div>
        <div><dt>Server-reported context</dt><dd>{number(worker.context_reported)}</dd></div>
        <div><dt>Allowed context</dt><dd>{worker.allowed_categories?.join(", ") || "No private forwarding allowed"}</dd></div>
        <div><dt>Interactive reserve</dt><dd>{worker.interactive_reserve}</dd></div>
        <div><dt>Heartbeat</dt><dd>{worker.last_heartbeat == null ? "Not received" : new Date(worker.last_heartbeat * 1000).toLocaleTimeString()}</dd></div>
        <div><dt>Current health check</dt><dd>{worker.status}</dd></div>
        <div><dt>Completion throughput</dt><dd>{worker.throughput_tps == null ? "Not measured" : `${worker.throughput_tps.toFixed(2)} tokens/s`}</dd></div>
      </dl>{worker.error && <p className="error">{worker.error}</p>}</details>
      <footer className="compute-controls">
        <button disabled={!!pending || !!resource.error || !!data?.control_blocked_reason} onClick={() => control(worker, "configure", { enabled: !worker.enabled })}>{worker.enabled ? "Disable worker" : "Enable worker"}</button>
        <label>Concurrency<select aria-label={`${worker.label} concurrency`} value={worker.concurrency} disabled={!!pending || !!resource.error || !!data?.control_blocked_reason} onChange={event => control(worker, "configure", { concurrency: Number(event.target.value) })}>{[1, 2, 3, 4].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
        {worker.start_supported && <button disabled={!!pending || !!resource.error || !!data?.control_blocked_reason || worker.status === "healthy"} onClick={() => setReview(worker)}>Start authorized server</button>}
      </footer>
    </article>)}
    {review && <FeatureDialog title={`Start ${review.label}?`} onClose={() => setReview(null)}><p>This starts the configured model on {review.node_id}. It reserves compute capacity and remains limited by the protected deployment.</p><div className="dialog-actions"><button onClick={() => setReview(null)}>Cancel</button><button disabled={!!pending} onClick={() => control(review, "start", {})}>Confirm server startup</button></div></FeatureDialog>}
  </section>;
}

export function ComputeJobs({ jobs }: { jobs: ComputeJob[] }) {
  if (!jobs.length) return null;
  return <section className="compute-section" aria-label="Distributed workflow execution"><header className="compute-heading"><div><h2>Distributed execution</h2><p>Assignments and verification from the original controller</p></div></header>{jobs.map(job => <article className="compute-job" key={job.job_id}><header><strong>{job.step_id}</strong><span>{job.state}</span></header><p>{job.worker_id || "Awaiting worker"} · {job.model_id || "Model unknown"}</p><dl className="compute-fields"><div><dt>Verification</dt><dd>{job.verification_status}</dd></div><div><dt>Queue delay</dt><dd>{job.queue_ms == null ? "Unknown" : `${job.queue_ms.toFixed(0)} ms`}</dd></div><div><dt>Execution</dt><dd>{job.latency_ms == null ? "Unknown" : `${job.latency_ms.toFixed(0)} ms`}</dd></div></dl>{job.selection_reason && <details><summary>Why this worker</summary><p>{job.selection_reason}</p></details>}{job.error && <p className="error">{job.error}</p>}</article>)}</section>;
}

export function ComputeWorkers({token,nodeId}:{token:string;nodeId?:string}) {
  if(nodeId && !["hanni","wonyoung"].includes(nodeId)) return <LegacyComputeWorkers token={token} nodeId={nodeId}/>;
  return <><details><summary>Workflow worker limits and scheduling</summary><LegacyComputeWorkers token={token} nodeId={nodeId}/></details></>;
}
