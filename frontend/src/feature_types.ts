import { useCallback, useEffect, useState } from "react";
import { request } from "./api";
import type { ToolEvent } from "./types";

export function storeInspection(screen: string, id: string) {
  try {
    sessionStorage.setItem(
      "hanni-inspect-target",
      JSON.stringify({ screen, id }),
    );
    return true;
  } catch {
    return false;
  }
}
export function consumeInspection(screen: string): string | null {
  try {
    const raw = sessionStorage.getItem("hanni-inspect-target");
    if (!raw) return null;
    const target = JSON.parse(raw);
    if (target.screen !== screen) return null;
    sessionStorage.removeItem("hanni-inspect-target");
    return typeof target.id === "string" && target.id.length <= 2000
      ? target.id
      : null;
  } catch {
    return null;
  }
}

export function usePrivateResource<T>(
  path: string,
  token: string,
  interval = 5000,
) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    setData(null);
  }, [token]);
  useEffect(() => {
    if (!token) {
      setError("Connect to the local HANNI session to view personal data.");
      return;
    }
    let live = true,
      timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const result = await request<T>(path, {
          headers: { "X-Hanni-Token": token },
          signal: AbortSignal.any([
            controller.signal,
            AbortSignal.timeout(12000),
          ]),
        });
        if (live) {
          setData(result);
          setError("");
        }
      } catch (error) {
        if (live)
          setError(
            error instanceof Error ? error.message : "Connection unavailable.",
          );
      } finally {
        if (live && interval) timer = setTimeout(poll, interval);
      }
    }
    poll();
    return () => {
      live = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [path, token, interval, revision]);
  return { data, error, refresh, setData };
}
export type TaskRecord = {
  id: string;
  title: string;
  course: string;
  due: string;
  all_day: boolean;
  status: "open" | "completed";
  priority: "low" | "normal" | "high";
  project_id: string | null;
  created_at: string;
  fingerprint: string;
};
export type ProjectRecord = {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  fingerprint: string;
};
export type NoteRecord = {
  id: string;
  project_id: string;
  title: string;
  body: string;
  created_at: string;
  updated_at: string;
  fingerprint: string;
};
export type LinkRecord = {
  id: string;
  project_id: string;
  label: string;
  target: string;
  kind: "file" | "conversation";
  created_at: string;
};
export type WorkspaceData = {
  available: boolean;
  tasks: TaskRecord[];
  projects: ProjectRecord[];
  notes: NoteRecord[];
  links: LinkRecord[];
  schema_version: number;
  reason: string | null;
};
export type CalendarData = {
  available: boolean;
  connected: boolean;
  stale: boolean;
  cached_at: string | null;
  start_date: string;
  days: number;
  events: {
    id: string;
    title: string;
    start: string;
    end: string;
    all_day: boolean;
    calendar?: string;
  }[];
  reason: string | null;
};
export type AgentsData = {
  available: boolean;
  agents: {
    id: string;
    name: string;
    kind: string;
    status: string;
    model: string;
    capability_count: number;
  }[];
  capabilities: {
    name: string;
    permission_level: number;
    risk_level: number;
  }[];
  active_tasks: {
    id: string;
    status: string;
    started_at: number;
    source: string;
  }[];
  awaiting_approvals: unknown[];
  approvals_available: boolean;
  cancellation_supported: boolean;
  executions: ToolEvent[];
  reason?: string;
  sampled_at: number;
};
export type MemoryData = {
  available: boolean;
  records: {
    id: string;
    content: string;
    memory_type: string;
    source: string;
    confidence: number;
    created_at: string;
    updated_at: string;
    fact_key: string;
    fact_value: string;
  }[];
  reason: string | null;
};
export type AwarenessData = {
  available: boolean;
  capture_active: boolean;
  reason: string;
  retention_seconds?: number;
};
export type VoiceData = {
  available: boolean;
  state: string;
  active: boolean;
  muted: boolean;
  microphone_active: boolean;
  input_level: number;
  speaking: boolean;
  processing: boolean;
  actions: Record<
    "listen" | "mute" | "unmute" | "interrupt",
    boolean | { enabled: boolean; reason?: string }
  >;
  metrics: Record<string, number | null>;
  reason: string | null;
};
export type NotificationItem = {
  id: string;
  key: string;
  category: string;
  priority: "critical" | "action_required" | "informational";
  title: string;
  message: string;
  target: { screen: string; id?: string };
  created_at: string;
  read: boolean;
  dismissed: boolean;
};
export type NotificationData = {
  available: boolean;
  items: NotificationItem[];
  preferences: { categories: Record<string, boolean> };
  reason: string | null;
};
