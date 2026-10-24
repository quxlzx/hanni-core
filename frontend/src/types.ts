export type Screen =
  | "home"
  | "chat"
  | "voice"
  | "planner"
  | "workflows"
  | "tasks"
  | "calendar"
  | "projects"
  | "memory"
  | "mission"
  | "agents"
  | "activity"
  | "screen"
  | "notifications"
  | "schedule"
  | "skills"
  | "settings";
export type ClusterPoint = {
  at: number;
  cpu: number | null;
  ram: number | null;
};
export type ClusterNode = {
  id: string;
  name: string;
  emoji: string;
  lan_ip: string | null;
  tailscale_ip: string | null;
  username: string | null;
  maintenance: boolean;
  status:
    "checking" | "online" | "reachable" | "offline" | "unreachable" | "repair";
  message: string | null;
  checked_at: number | null;
  availability_checked_at?: number | null;
  availability_stale_seconds?: number;
  telemetry_stale?: boolean;
  sampled_at: number | null;
  last_online_at: number | null;
  address: string | null;
  connection: "tailscale" | "lan" | null;
  availability_source: string | null;
  tailscale_online: boolean | null;
  os: string | null;
  metrics: {
    cpu_percent: number;
    ram_percent: number;
    ram_used_bytes: number;
    ram_total_bytes: number;
  } | null;
  uptime_seconds: number | null;
  processes:
    { name: string; cpu_percent: number; ram_percent: number }[] | null;
  history: ClusterPoint[];
  power?: {
    actions: Record<
      "sleep" | "reboot",
      { enabled: boolean; reason: string | null }
    >;
    last_operation: PowerOperation | null;
  };
  terminal?: { enabled: boolean; reason: string | null };
};
export type PowerOperation = {
  id: string;
  node: string;
  action: "sleep" | "reboot";
  requested_at: number;
  status: "sending" | "accepted" | "failed" | "unknown";
  message: string;
};
export type Cluster = {
  refresh_seconds: number;
  telemetry_stale_seconds?: number;
  history_seconds: number;
  checked_at: number | null;
  tailscale_state: string;
  nodes: ClusterNode[];
};
export type Message = {
  attachments?: import("./attachment_files").Attachment[];
  id: number;
  turn: string;
  role: string;
  content: string;
  channel: string;
  status: string;
  created: number;
  conversation?: string;
  task_id?: string | null;
};
export type Chat = {
  pending_attachments?: import("./attachment_files").Attachment[];
  conversation_id?: string | null;
  messages: Message[];
  ready: boolean;
  busy: boolean;
  queued: number;
  token: string;
  epoch: string;
  saved: boolean;
  has_more: boolean;
};
export type GPU = {
  name: string;
  memory_total_mb: number;
  memory_used_mb: number;
  utilization_percent: number | null;
  temperature_c: number | null;
};
export type ModelState = {
  model: string;
  role: string;
  endpoint: string;
  state: string;
  resident: boolean;
  device: string | null;
  active_inferences: number;
  process_ram_mb: number | null;
  context: number;
  pinned: boolean;
};
export type Telemetry = {
  sampled_at: number | null;
  error: string | null;
  model_status: string;
  model_detail?: string | null;
  safe_mode: boolean | null;
  model: { file: string; quantization: string; context: number; context_verified?: boolean };
  model_residency: Record<string, ModelState>;
  resources: {
    cpu_percent: number;
    ram_percent: number;
    ram_used_gb: number;
    ram_total_gb: number;
    gpus: GPU[];
    gpu_note: string | null;
  } | null;
  disk?: { percent: number; used_gb: number; total_gb: number };
  network?: { receive_bps: number | null; send_bps: number | null };
  uptime_seconds?: number;
  battery?: { percent: number; plugged: boolean } | null;
  activity: {
    input_level: number;
    microphone_active: boolean;
    speaking: boolean;
  };
  interaction?: {
    response_in_progress: boolean;
    tts_speaking: boolean;
    voice_engaged: boolean;
    active_background_jobs: number;
  };
};
export type Contract = {
  version: number;
  transport: string;
  screens: Screen[];
  features: Record<string, boolean>;
  timezone: string | null;
  models: {
    id: string;
    name: string;
    role: string;
    context: number;
    quantization: string;
  }[];
  capabilities: {
    name: string;
    permission_level: number;
    risk_level: number;
  }[];
  policies: {
    observe_first: boolean;
    allowed_actions: string[];
    memory_enabled: boolean;
    memory_retrieval: boolean;
    memory_extraction: boolean;
    owner_auto_approve_level: number;
    dangerous_actions_require_confirmation: boolean;
  } | null;
};
export type ToolEvent = {
  id: number;
  timestamp: string;
  tool: string;
  status: string;
  confirmed: boolean;
  duration_ms: number | null;
  arguments: Record<string, unknown>;
  summary: string | null;
  error: string | null;
  source: string | null;
};
export type Activity = {
  available: boolean;
  events: ToolEvent[];
  reason: string | null;
};
export type Audio = {
  inputs: { id: string; name: string; hostapi: string }[];
  outputs: { id: string; name: string }[];
  input_id: string;
  output_id: string;
  input_error: string | null;
  output_error: string | null;
};
export type Routing = {
  mode: string;
  requested_device_id?: string;
  devices: {
    id: string;
    name: string;
    total_mb: number;
    auto_eligible: boolean;
  }[];
  selected_device_id: string | null;
  selected_device_name: string | null;
  current_device_id: string | null;
  restart_required: boolean;
  error?: string;
};
