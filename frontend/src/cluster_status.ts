import type { ClusterNode } from "./types";

const labels: Record<ClusterNode["status"], string> = {
  checking: "Checking", online: "Online", reachable: "Reachable",
  offline: "Offline", unreachable: "Unreachable", repair: "Under repair",
};

export function nodeStatus(node: ClusterNode, now: number, disconnected: boolean) {
  const checked = node.availability_checked_at ?? node.checked_at;
  const stale = !node.maintenance && (disconnected || (checked == null
    ? node.status !== "checking" : now - checked > (node.availability_stale_seconds ?? 25)));
  return {
    stale,
    label: stale ? "Status stale" : node.status === "checking" && node.last_online_at != null
      ? "Rechecking" : labels[node.status],
    kind: stale ? "stale" : node.status,
  };
}

export function nodeReadings(node: ClusterNode, now: number, disconnected: boolean, ttl = 6) {
  const stale = disconnected || node.telemetry_stale === true ||
    node.sampled_at == null || now - node.sampled_at > ttl;
  return { stale, metrics: stale ? null : node.metrics };
}

export function workerStatus(worker: {
  enabled: boolean; status: string; last_healthy_at?: number | null;
  last_heartbeat: number | null; consecutive_health_failures?: number;
}, now: number, disconnected: boolean) {
  if (!worker.enabled) return "Disabled";
  if (disconnected) return "Status unavailable";
  if (worker.status === "healthy") return worker.last_heartbeat != null &&
    now - worker.last_heartbeat >= 0 && now - worker.last_heartbeat <= 30 ? "Healthy" : "Status stale";
  if (worker.status === "unhealthy") {
    const recent = worker.last_healthy_at != null && now - worker.last_healthy_at <= 30;
    return recent && worker.consecutive_health_failures === 1 ? "Rechecking" : "Unavailable";
  }
  return worker.last_heartbeat == null ? "Not checked" : "Status stale";
}
