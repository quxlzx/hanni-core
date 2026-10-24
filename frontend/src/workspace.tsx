import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { request, useResource, write } from "./api";
import { ActivityPage } from "./activity";
import { MemoryPage } from "./memory";
import { SkillsPage } from "./skills";
import { TasksPage } from "./tasks";
import { SchedulePage } from "./schedule";
import { NotificationsPage } from "./awareness";
import { consumeInspection } from "./feature_types";
import {
  HomeScreen,
  ConversationScreen,
  MissionScreen,
  SettingsScreen,
  type ScreenContext,
} from "./screens";
import type {
  Activity,
  Chat,
  Contract,
  Message,
  Screen,
  Telemetry,
  ToolEvent,
} from "./types";

type VisibleScreen = Exclude<Screen, "planner" | "workflows" | "calendar" | "projects" | "screen" | "voice">;
type NavigationArea = "Assistant" | "Mission" | "Hermes";
const screens: Record<
  VisibleScreen,
  { label: string; group: NavigationArea; description: string }
> = {
  home: {
    label: "Home",
    group: "Assistant",
    description: "Your local assistant.",
  },
  chat: {
    label: "Conversation",
    group: "Assistant",
    description: "One conversation, across text and voice.",
  },
  memory: {
    label: "Memory",
    group: "Assistant",
    description: "What HANNI remembers and suggests.",
  },
  skills: {
    label: "Skills",
    group: "Assistant",
    description: "Learned procedures matched to each task.",
  },
  mission: {
    label: "Mission Control",
    group: "Mission",
    description: "Resource use and model activity.",
  },
  agents: {
    label: "Agents",
    group: "Mission",
    description: "Registered capabilities and observed activity.",
  },
  tasks: {
    label: "Tasks",
    group: "Mission",
    description: "Native task approvals and submissions.",
  },
  schedule: {
    label: "Schedule",
    group: "Mission",
    description: "Agent cron jobs on this machine.",
  },
  activity: {
    label: "Activity",
    group: "Mission",
    description: "Recorded tool runs and approvals.",
  },
  notifications: {
    label: "Notifications",
    group: "Mission",
    description: "Recorded events and reminders.",
  },
  settings: {
    label: "Settings",
    group: "Mission",
    description: "Local configuration.",
  },
};
const fmt = (n: number | null | undefined, d = 1) =>
  typeof n === "number" && Number.isFinite(n) ? n.toFixed(d) : "Unavailable";
const percent = (n: number | null | undefined) =>
  typeof n === "number" && Number.isFinite(n) ? `${fmt(n)}%` : "Unavailable";
const pretty = (file?: string) =>
  file?.replace(/[-_]Q\d.*\.gguf$/i, "").replace(/\.gguf$/i, "") ||
  "No model reported";
const rate = (n: number | null | undefined) =>
  n == null
    ? "Unavailable"
    : n >= 1048576
      ? `${fmt(n / 1048576)} MiB/s`
      : `${fmt(n / 1024)} KiB/s`;
function readScreen(): VisibleScreen {
  const key = location.hash.slice(1);
  return Object.hasOwn(screens, key) ? (key as VisibleScreen) : "home";
}

function Icon({ name }: { name: string }) {
  const paths: Record<string, ReactNode> = {
    home: (
      <>
        <path d="m3 10 9-7 9 7" />
        <path d="M5 9v11h5v-6h4v6h5V9" />
      </>
    ),
    chat: <path d="M4 4h16v12H9l-5 4V4Z" />,
    mission: (
      <>
        <path d="M3 16h4l3-9 4 12 3-7h4" />
        <path d="M3 4h18M3 22h18" />
      </>
    ),
    cluster: (
      <>
        <rect x="3" y="3" width="6" height="6" rx="1" />
        <rect x="15" y="3" width="6" height="6" rx="1" />
        <rect x="9" y="15" width="6" height="6" rx="1" />
        <path d="M6 9v3h12V9M12 12v3" />
      </>
    ),
    settings: (
      <>
        <path d="M4 6h16M4 12h16M4 18h16" />
        <path d="M9 3v6M16 9v6M8 15v6" />
      </>
    ),
    search: (
      <>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 5 5" />
      </>
    ),
    panel: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M15 4v16" />
      </>
    ),
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  };
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.chat}
    </svg>
  );
}
function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function Skeleton() {
  return (
    <div className="skeleton-group" role="status" aria-label="Loading">
      <span className="skeleton short" />
      <span className="skeleton" />
      <span className="skeleton medium" />
    </div>
  );
}
function Facts({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="facts">
      {items.map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
function Spark({
  values,
  label,
  ceiling,
}: {
  values: number[];
  label: string;
  ceiling?: number;
}) {
  const max = ceiling ?? Math.max(1, ...values),
    points = values
      .map(
        (n, i) =>
          `${(i * 320) / Math.max(1, values.length - 1)},${52 - (n / max) * 44}`,
      )
      .join(" ");
  return (
    <svg
      className="spark"
      viewBox="0 0 320 60"
      preserveAspectRatio="none"
      role="img"
      aria-label={label}
    >
      <path d="M0 56H320M0 28H320" className="chart-grid" />
      {values.length > 1 && <polyline points={points} />}
    </svg>
  );
}
function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      className={title === "Search HANNI" ? "command-palette" : undefined}
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      <div className="dialog-heading">
        <h2>{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <Icon name="close" />
        </button>
      </div>
      {children}
    </dialog>
  );
}
function ToolActivity({
  data,
  error,
  compact = false,
}: {
  data: Activity | null;
  error: string;
  compact?: boolean;
}) {
  if (error)
    return (
      <Empty title="Activity unavailable">
        The local audit could not be reached. We will reconnect automatically.
      </Empty>
    );
  if (!data) return <Skeleton />;
  if (!data.available || !data.events.length)
    return (
      <Empty
        title={data.available ? "No tool activity yet" : "Activity unavailable"}
      >
        {data.reason ||
          "Tool activity appears here after HANNI executes a capability."}
      </Empty>
    );
  return (
    <div className="tool-events">
      {data.events.slice(0, compact ? 4 : 30).map((row: ToolEvent) => (
        <details key={`${row.timestamp}-${row.id}-${row.tool}`}>
          <summary>
            <div>
              <span className={`event-status ${row.status}`}>{row.status}</span>
              <strong>{row.tool}</strong>
              <small>
                {new Date(row.timestamp).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}{" "}
                ·{" "}
                {row.duration_ms == null
                  ? "Duration unavailable"
                  : `${fmt(row.duration_ms, 0)} ms`}
              </small>
            </div>
          </summary>
          <div className="event-detail">
            <p>{row.summary || "No result summary was recorded."}</p>
            {row.error && <p className="error">{row.error}</p>}
            <span className="field-label">Recorded arguments</span>
            <pre>{JSON.stringify(row.arguments, null, 2)}</pre>
            <p className="subtle">
              {row.confirmed
                ? "Confirmation recorded"
                : "No confirmation flag recorded"}{" "}
              · {row.source || "Source unavailable"}
            </p>
          </div>
        </details>
      ))}
    </div>
  );
}
function VoiceOrb({
  state,
  offline,
  paused,
}: {
  state: Telemetry | null;
  offline: boolean;
  paused: boolean;
}) {
  const ref = useRef<HTMLCanvasElement>(null),
    frozen = useRef(0);
  const input = offline
    ? 0
    : Math.min(1, Math.max(0, state?.activity?.input_level || 0));
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    if (!paused) frozen.current = input;
    const level = paused ? frozen.current : input,
      dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = 84 * dpr;
    canvas.height = 84 * dpr;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, 84, 84);
    for (let i = 0; i < 3; i++) {
      ctx.strokeStyle = offline ? "#697280" : i === 1 ? "#a4c2e9" : "#607492";
      ctx.lineWidth = i === 1 ? 1.4 : 0.8;
      ctx.beginPath();
      ctx.ellipse(
        42,
        42,
        22 + level * 7 - i * 3,
        23 + level * 4,
        (i * Math.PI) / 3,
        0,
        Math.PI * 2,
      );
      ctx.stroke();
    }
    ctx.fillStyle = offline ? "#697280" : "#a4c2e9";
    ctx.fillRect(40, 40, 4, 4);
  }, [input, offline, paused]);
  return (
    <canvas
      ref={ref}
      className="voice-orb"
      width="84"
      height="84"
      role="img"
      aria-label="Voice indicator. Shape responds only to measured microphone level."
    />
  );
}

export function App({ embeddedScreen, onPrepare, onNavigate }: { embeddedScreen?: VisibleScreen; onPrepare?: (value: string) => void; onNavigate?: (screen: Screen) => boolean } = {}) {
  const [screen, setScreen] = useState<VisibleScreen>(() => embeddedScreen || readScreen()),
    [sideOpen, setSideOpen] = useState(false);
  const [navigationArea, setNavigationArea] = useState<NavigationArea>(
    () => screens[readScreen()].group,
  );
  const [inspect, setInspect] = useState(() => {
    if (innerWidth <= 1100) return false;
    try {
      return localStorage.getItem("hanni-inspector") === "open";
    } catch {
      return false;
    }
  });
  const [voiceExpanded, setVoiceExpanded] = useState(false);
  const [palette, setPalette] = useState(false),
    [search, setSearch] = useState(""),
    [notice, setNotice] = useState(false);
  const [confirmAction, setConfirmAction] = useState<
    "clear" | "shutdown" | "restart" | null
  >(null),
    [stopping, setStopping] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const restartEpoch = useRef<string | null>(null);
  const [draft, setDraft] = useState(""),
    [sending, setSending] = useState(false),
    [sendError, setSendError] = useState("");
  const [older, setOlder] = useState<Message[]>([]),
    [hasOlder, setHasOlder] = useState(false),
    [loadingOlder, setLoadingOlder] = useState(false);
  const [motion, setMotion] = useState(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
    try {
      return localStorage.getItem("hanni-voice-visual") !== "paused";
    } catch {
      return true;
    }
  });
  const [now, setNow] = useState(new Date()),
    [samples, setSamples] = useState<{
      cpu: number[];
      ram: number[];
      net: number[];
    }>({ cpu: [], ram: [], net: [] });
  const pending = useRef<{ id: string; message: string } | null>(null),
    lastSample = useRef<number | null>(null),
    lastEpoch = useRef("");
  const linkedMessage = useRef<number | null>(null);
  const chat = useResource<Chat>("/api/chat", 600),
    telemetry = useResource<Telemetry>("/api/state", 400);
  const contract = useResource<Contract>("/api/workspace", 30000),
    activity = useResource<Activity>("/api/activity", 2500);
  const [deviceRevision, setDeviceRevision] = useState(0);
  const featureToken = !chat.error && !stopping ? chat.data?.token || "" : "";
  const logRef = useRef<HTMLDivElement>(null),
    inputRef = useRef<HTMLTextAreaElement>(null),
    paletteRef = useRef<HTMLInputElement>(null);
  const state = telemetry.data,
    meta = contract.data;
  const ready = Boolean(chat.data?.ready && !chat.error && !stopping);
  const stale = Boolean(
    telemetry.error ||
    state?.error ||
    !state?.sampled_at ||
    now.getTime() / 1000 - state.sampled_at > 20,
  );
  const busy = Boolean(
    (!chat.error && chat.data?.busy) ||
    (!stale && state?.interaction?.response_in_progress),
  );
  const speaking = Boolean(
    !stale && (state?.activity?.speaking || state?.interaction?.tts_speaking),
  );
  const voice = telemetry.error
    ? "Offline"
    : stale
      ? "Unavailable"
      : speaking
        ? "Speaking"
        : busy
          ? "Processing"
          : state?.activity?.microphone_active
            ? "Listening"
            : "Standby";
  const models = Object.entries(state?.model_residency || {});
  const selectedModel = meta?.models[0];
  const rows = [
    ...new Map(
      [...older, ...(chat.data?.messages || [])].map((row) => [row.id, row]),
    ).values(),
  ].sort((a, b) => a.id - b.id);
  const can = (feature: string) => meta?.features[feature] === true;
  function navigate(requested: Screen) {
    if (embeddedScreen && onNavigate?.(requested)) return;
    const target = Object.hasOwn(screens, requested) ? requested as VisibleScreen : "home";
    setScreen(target);
    setNavigationArea(screens[target].group);
    if (!embeddedScreen) location.hash = target;
    setSideOpen(false);
    setPalette(false);
    setNotice(false);
    if (innerWidth <= 1100) setInspect(false);
  }
  function prepare(message: string) {
    if (onPrepare) { onPrepare(message); return; }
    setDraft(message);
    navigate("chat");
    setTimeout(() => inputRef.current?.focus(), 0);
  }
  useEffect(() => {
    const onHash = () => {
      const next = readScreen();
      setScreen(next);
      setNavigationArea(screens[next].group);
    };
    if (!embeddedScreen) window.addEventListener("hashchange", onHash);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setInspect(false);
        setVoiceExpanded(false);
        setSideOpen(false);
        setNotice(false);
      }
      if (!embeddedScreen && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette((v) => !v);
        setSearch("");
      }
    };
    window.addEventListener("keydown", onKey);
    const onResize = () => {
      if (innerWidth <= 1100) setInspect(false);
    };
    window.addEventListener("resize", onResize);
    const timer = setInterval(() => setNow(new Date()), 1000);
    const preference = matchMedia("(prefers-reduced-motion: reduce)"),
      onMotion = (e: MediaQueryListEvent) => {
        if (e.matches) setMotion(false);
      };
    preference.addEventListener("change", onMotion);
    return () => {
      window.removeEventListener("hashchange", onHash);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onResize);
      clearInterval(timer);
      preference.removeEventListener("change", onMotion);
    };
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem("hanni-inspector", inspect ? "open" : "closed");
    } catch {
      /* Browser storage is optional; keep the session preference. */
    }
  }, [inspect]);
  useEffect(() => {
    try {
      localStorage.setItem("hanni-voice-visual", motion ? "active" : "paused");
    } catch {
      /* Preferences remain available for this session without browser storage. */
    }
  }, [motion]);
  useEffect(() => {
    if (palette) paletteRef.current?.focus();
  }, [palette]);
  useEffect(() => {
    if (chat.data && lastEpoch.current !== chat.data.epoch) {
      lastEpoch.current = chat.data.epoch;
      setOlder([]);
      setHasOlder(chat.data.has_more);
      if (restartEpoch.current && restartEpoch.current !== chat.data.epoch) {
        restartEpoch.current = null;
        setRestarting(false);
        setStopping(false);
        contract.refresh();
        telemetry.refresh();
      }
    } else if (chat.data && !older.length) setHasOlder(chat.data.has_more);
  }, [chat.data]);
  useEffect(() => {
    if (!stale && state?.resources && state.sampled_at !== lastSample.current) {
      lastSample.current = state.sampled_at;
      setSamples((v) => ({
        cpu: [...v.cpu, state.resources!.cpu_percent].slice(-60),
        ram: [...v.ram, state.resources!.ram_percent].slice(-60),
        net:
          state.network?.receive_bps == null
            ? v.net
            : [...v.net, state.network.receive_bps].slice(-60),
      }));
    }
  }, [state, stale]);
  const bottomRef = useRef(true);
  useEffect(() => {
    if (bottomRef.current && !loadingOlder && logRef.current)
      logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [chat.data?.messages, screen]);
  useEffect(() => {
    if (screen !== "chat" || !chat.data) return;
    const raw = consumeInspection("chat");
    if (raw === null) return;
    const id = Number(raw);
    if (
      !/^[1-9]\d*$/.test(raw) ||
      !Number.isSafeInteger(id) ||
      id >= Number.MAX_SAFE_INTEGER
    ) {
      setSendError("This conversation link is invalid.");
      return;
    }
    bottomRef.current = false;
    setSendError("");
    linkedMessage.current = id;
    const current = rows.some((row) => row.id === id);
    if (current) {
      requestAnimationFrame(() => {
        document
          .getElementById(`message-${id}`)
          ?.scrollIntoView({ block: "center" });
        linkedMessage.current = null;
      });
      return;
    }
    const expectedEpoch = chat.data.epoch;
    const controller = new AbortController();
    setLoadingOlder(true);
    request<Chat>(`/api/chat?before=${id + 1}`, {
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]),
    })
      .then((data) => {
        if (
          data.epoch !== expectedEpoch ||
          lastEpoch.current !== expectedEpoch ||
          !data.messages.some((row) => row.id === id)
        ) {
          linkedMessage.current = null;
          setSendError(
            "This linked message is no longer available in the current conversation.",
          );
          return;
        }
        setOlder((value) => [...data.messages, ...value]);
        if (!older.length) setHasOlder(data.has_more);
      })
      .catch((error) => {
        linkedMessage.current = null;
        if (!controller.signal.aborted)
          setSendError(
            error instanceof Error
              ? error.message
              : "Linked conversation history is unavailable.",
          );
      })
      .finally(() => setLoadingOlder(false));
    return () => {
      controller.abort();
      linkedMessage.current = null;
    };
  }, [screen, chat.data?.epoch]);
  useEffect(() => {
    if (screen !== "chat" || linkedMessage.current === null) return;
    const id = linkedMessage.current;
    requestAnimationFrame(() => {
      const element = document.getElementById(`message-${id}`);
      if (element) {
        element.scrollIntoView({ block: "center" });
        linkedMessage.current = null;
      }
    });
  }, [older, screen]);
  async function submit(e?: FormEvent) {
    e?.preventDefault();
    const message = draft.trim();
    if (!message || !ready || sending) return;
    if (!pending.current || pending.current.message !== message)
      pending.current = { id: crypto.randomUUID(), message };
    setSending(true);
    setSendError("");
    try {
      await write("/api/chat", chat.data!.token, pending.current);
      setDraft((v) => (v.trim() === message ? "" : v));
      pending.current = null;
      bottomRef.current = true;
      navigate("chat");
      chat.refresh();
    } catch (e) {
      setSendError(
        `${e instanceof Error ? e.message : "Request failed."} Your draft is retained. Check history before retrying.`,
      );
    } finally {
      setSending(false);
    }
  }
  async function loadOlder() {
    if (!rows.length || loadingOlder) return;
    setLoadingOlder(true);
    setSendError("");
    const element = logRef.current,
      height = element?.scrollHeight || 0,
      top = element?.scrollTop || 0;
    try {
      const data = await request<Chat>(`/api/chat?before=${rows[0].id}`);
      if (data.epoch === chat.data?.epoch) {
        setOlder((v) => [...data.messages, ...v]);
        setHasOlder(data.has_more);
        requestAnimationFrame(() => {
          if (element) element.scrollTop = top + element.scrollHeight - height;
        });
      }
    } catch (e) {
      setSendError(
        e instanceof Error ? e.message : "Earlier history unavailable.",
      );
    } finally {
      setLoadingOlder(false);
    }
  }
  async function confirm() {
    if (!chat.data?.token || chat.error) return;
    const action = confirmAction;
    setConfirmAction(null);
    setSendError("");
    try {
      if (action === "clear") {
        await write("/api/chat/clear", chat.data.token, {});
        setOlder([]);
        setHasOlder(false);
        chat.refresh();
      }
      if (action === "shutdown") {
        setStopping(true);
        await write("/api/shutdown", chat.data.token, {});
      }
      if (action === "restart") {
        restartEpoch.current = chat.data.epoch;
        setRestarting(true);
        setStopping(true);
        await write("/api/restart", chat.data.token, {});
      }
    } catch (e) {
      if (action === "shutdown") setStopping(false);
      if (action === "restart") {
        restartEpoch.current = null;
        setRestarting(false);
        setStopping(false);
      }
      setSendError(e instanceof Error ? e.message : "Request failed.");
    }
  }
  const resources = state?.resources;
  const dateOptions: Intl.DateTimeFormatOptions = {
    weekday: "long",
    month: "long",
    day: "numeric",
    ...(meta?.timezone ? { timeZone: meta.timezone } : {}),
  };
  const localHour = Number(
    new Intl.DateTimeFormat("en-GB", {
      hour: "numeric",
      hourCycle: "h23",
      ...(meta?.timezone ? { timeZone: meta.timezone } : {}),
    }).format(now),
  );
  const greeting =
    localHour < 12
      ? "Good morning"
      : localHour < 18
        ? "Good afternoon"
        : "Good evening";
  const failed = activity.error
    ? []
    : activity.data?.events.filter((event) => event.status === "failed") || [];
  const connection = telemetry.error
    ? "Disconnected"
    : stale
      ? "Waiting for telemetry"
      : "Connected";
  const matchedScreens = Object.entries(screens).filter(([key, value]) =>
    `${key} ${value.label}`.toLowerCase().includes(search.toLowerCase()),
  );
  const matchedCapabilities = (meta?.capabilities || [])
    .filter((item) => item.name.toLowerCase().includes(search.toLowerCase()))
    .slice(0, 8);
  const matchedMessages = search.trim()
    ? rows
        .filter((row) =>
          row.content.toLowerCase().includes(search.toLowerCase()),
        )
        .slice(-5)
    : [];
  const composer = (
    <form className="composer" onSubmit={submit}>
      <label htmlFor="chat-input" className="sr-only">
        Message HANNI
      </label>
      <textarea
        ref={inputRef}
        id="chat-input"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        disabled={!ready}
        maxLength={4000}
        rows={2}
        placeholder={
          ready
            ? "Ask HANNI anything…"
            : stopping
              ? restarting ? "HANNI is restarting. This page will reconnect." : "This session is stopping."
              : chat.error
                ? "Connection unavailable. Your draft stays here."
                : !chat.data
                  ? "Checking assistant availability."
                  : "Assistant is not ready. Inspect model status."
        }
        aria-describedby="chat-help chat-error"
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            submit();
          }
        }}
      />
      <div className="composer-bottom">
        <span id="chat-help">
          {stopping
            ? restarting ? "HANNI is restarting. This page will reconnect." : "This session is stopping."
            : chat.error
              ? "Connection lost. Draft kept."
              : ready
                ? "Enter to send · Shift+Enter for a new line"
                : "Start HANNI to enable conversation."}
        </span>
        <span className="char-count">{draft.length} / 4000</span>
        <button
          id="chat-send"
          className="send-button"
          type="submit"
          disabled={!ready || sending || !draft.trim()}
          aria-label="Send message"
        >
          <Icon name="arrow" />
        </button>
      </div>
      <p id="chat-error" role="alert" className="error">
        {sendError}
      </p>
    </form>
  );

  const screenContext: ScreenContext = {
    now,
    dateOptions,
    greeting,
    state,
    meta,
    chat,
    telemetry,
    contract,
    activity,
    stale,
    ready,
    busy,
    stopping,
    restarting,
    sending,
    rows,
    samples,
    composer,
    navigate,
    prepare,
    hasOlder,
    loadingOlder,
    loadOlder,
    logRef,
    bottomRef,
    setConfirmAction,
    deviceRevision,
    refreshSettings: () => {
      setDeviceRevision((v) => v + 1);
      contract.refresh();
    },
    inspect,
    toggleInspect: () => setInspect((v) => !v),
    motion,
    toggleMotion: () => setMotion((v) => !v),
    sendError,
  };

  return (
    <div
      className={`app-shell ${embeddedScreen ? "chat-embedded" : ""} ${inspect ? "with-inspector" : ""} ${sideOpen ? "navigation-open" : ""}`}
    >
      <a
        className="skip-link"
        href="#main-content"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Skip to assistant
      </a>
      <aside className="workspace-sidebar" aria-label="Assistant navigation">
        <div className="workspace-brand">
          <button
            className="rail-brand"
            onClick={() => navigate("home")}
            aria-label="HANNI home"
          >
            h<span>.</span>
          </button>
          <div>
            <strong>HANNI OS</strong>
            <span>Local assistant</span>
          </div>
          <button
            className="mobile-close icon-button"
            aria-label="Close navigation"
            onClick={() => setSideOpen(false)}
          >
            <Icon name="close" />
          </button>
        </div>
        <nav className="workspace-nav" aria-label="Primary navigation">
          {(["Assistant", "Mission"] as NavigationArea[]).map(
            (area) => (
              <div className="navigation-area" key={area}>
                <button
                  className="area-button"
                  aria-expanded={navigationArea === area}
                  aria-controls={`navigation-${area.toLowerCase()}`}
                  onClick={() => setNavigationArea(area)}
                >
                  {area}
                  <span aria-hidden="true">
                    {navigationArea === area ? "−" : "+"}
                  </span>
                </button>
                {navigationArea === area && (
                  <div
                    className="area-routes"
                    id={`navigation-${area.toLowerCase()}`}
                  >
                    {(Object.keys(screens) as VisibleScreen[])
                      .filter(
                        (key) =>
                          screens[key].group === area &&
                          key !== "settings" &&
                          key !== "notifications",
                      )
                      .map((key) => (
                        <button
                          key={key}
                          className={`nav-item ${screen === key ? "selected" : ""}`}
                          aria-label={screens[key].label}
                          aria-current={screen === key ? "page" : undefined}
                          onClick={() => navigate(key)}
                        >
                          <span>{screens[key].label}</span>
                        </button>
                      ))}
                  </div>
                )}
              </div>
            ),
          )}
        </nav>
        {navigationArea === "Assistant" && (
          <div className="sidebar-session">
            <span className="nav-group">Recent messages</span>
            <div className="recent-conversations">
              {rows
                .filter((row) => row.role === "user")
                .slice(-4)
                .reverse()
                .map((row) => (
                  <button
                    key={row.id}
                    title={row.content}
                    onClick={() => {
                      navigate("chat");
                      setTimeout(
                        () =>
                          document
                            .getElementById(`message-${row.id}`)
                            ?.scrollIntoView({ block: "center" }),
                        30,
                      );
                    }}
                  >
                    {row.content}
                  </button>
                ))}
              {!rows.some((row) => row.role === "user") && (
                <p className="subtle">No messages yet</p>
              )}
            </div>
          </div>
        )}
        <div className="sidebar-footer">
          <button
            className={`nav-item ${screen === "notifications" ? "selected" : ""}`}
            aria-label="Notifications"
            aria-current={screen === "notifications" ? "page" : undefined}
            onClick={() => navigate("notifications")}
          >
            <span>Notifications</span>
          </button>
          <button
            className={`nav-item ${screen === "settings" ? "selected" : ""}`}
            aria-label="Settings"
            aria-current={
              screen === "settings" ? "page" : undefined
            }
            onClick={() => navigate("settings")}
          >
            <Icon name="settings" />
            <span>Settings</span>
          </button>
          <div className="sidebar-local">
            <span
              className={`status-dot ${connection === "Connected" ? "online" : ""}`}
            />
            <span>This computer</span>
            <small>Local</small>
          </div>
        </div>
      </aside>
      <header className="topbar">
        <button
          className="mobile-menu icon-button"
          aria-label="Open navigation"
          onClick={() => setSideOpen((v) => !v)}
        >
          <Icon name="menu" />
        </button>
        <div className="breadcrumb">
          <span>{screens[screen].group}</span>
          <span className="separator">/</span>
          <strong>{screens[screen].label}</strong>
        </div>
        <div className="topbar-actions">
          <button
            className="search-trigger"
            aria-label="Search HANNI"
            onClick={() => {
              setPalette(true);
              setSearch("");
            }}
          >
            <Icon name="search" />
            <span>Search HANNI</span>
            <kbd>Ctrl K</kbd>
          </button>
          <button
            className="connection"
            onClick={() => setNotice((v) => !v)}
            aria-expanded={notice}
          >
            {connection}
            {failed.length > 0 ? ` · ${failed.length} alerts` : ""}
          </button>
          <button
            className="icon-button"
            aria-label={inspect ? "Hide inspector" : "Show inspector"}
            title={inspect ? "Hide inspector" : "Show inspector"}
            aria-pressed={inspect}
            onClick={() => setInspect((v) => !v)}
          >
            <Icon name="panel" />
          </button>
        </div>
      </header>
      {notice && (
        <div className="notification-panel">
          <h3>Workspace status</h3>
          <p>
            {stopping
              ? restarting ? "HANNI is restarting. Reconnection is automatic." : "HANNI is stopping."
              : connection === "Connected"
                ? "Connected to the local HANNI service."
                : "Waiting for the local service. Reconnection is automatic."}
          </p>
          {failed.length ? (
            failed.slice(0, 4).map((row) => (
              <p key={`${row.timestamp}-${row.id}`} className="error">
                {row.tool}: execution failed.
              </p>
            ))
          ) : (
            <p className="subtle">
              No tool failures in the loaded activity window.
            </p>
          )}
          {activity.error && (
            <p className="error">Tool activity is currently unavailable.</p>
          )}
        </div>
      )}
      <main
        id="main-content"
        className={`main-content screen-${screen}`}
        tabIndex={-1}
      >
        {screen === "home" && <HomeScreen context={screenContext} />}
        {screen === "chat" && <ConversationScreen context={screenContext} />}
        {screen === "mission" && <MissionScreen context={screenContext} />}
        {screen === "memory" && (
          <MemoryPage token={featureToken} prepare={prepare} navigate={navigate} />
        )}
        {screen === "skills" && <SkillsPage token={featureToken} />}
        {screen === "tasks" && <TasksPage token={featureToken} />}
        {screen === "schedule" && <SchedulePage token={featureToken} />}
        {(screen === "agents" || screen === "activity") && (
          <ActivityPage view={screen} context={screenContext} />
        )}
        {screen === "notifications" && (
          <NotificationsPage token={featureToken} navigate={navigate} />
        )}
        {screen === "settings" && <SettingsScreen context={screenContext} />}
      </main>
      {inspect && (
        <aside className="inspector" aria-label="Context inspector">
          <div className="inspector-heading">
            <h2>Context</h2>
            <button
              className="icon-button"
              aria-label="Hide inspector"
              onClick={() => setInspect(false)}
            >
              <Icon name="close" />
            </button>
          </div>
          <section>
            <span className="field-label">Assistant</span>
            <h3>{pretty(selectedModel?.name || state?.model?.file)}</h3>
            <p>
              {telemetry.error
                ? "Status unavailable"
                : state?.model_status || "Checking connection"}
            </p>
            <Facts
              items={[
                [
                  "Context",
                  state?.model?.context?.toLocaleString() || "Unavailable",
                ],
                ["Quantization", state?.model?.quantization || "Unavailable"],
                [
                  "Inferences",
                  telemetry.error
                    ? "Unavailable"
                    : models.length
                      ? models.reduce(
                          (n, [, m]) => n + (m.active_inferences || 0),
                          0,
                        )
                      : "Unavailable",
                ],
                [
                  "Queue",
                  chat.error
                    ? "Unavailable"
                    : (chat.data?.queued ?? "Checking"),
                ],
              ]}
            />
          </section>
          <section>
            <span className="field-label">Control state</span>
            <h3
              className={state?.safe_mode || telemetry.error ? "warning" : ""}
            >
              {telemetry.error || state?.safe_mode == null
                ? "Safety state unavailable"
                : state.safe_mode
                  ? "Safe Mode"
                  : "Controller gates active"}
            </h3>
            <p>
              {state?.safe_mode
                ? "Computer actions are blocked."
                : "Permission and confirmation policies remain in HANNI."}
            </p>
            <button className="text-link" onClick={() => navigate("settings")}>
              Review settings <Icon name="arrow" />
            </button>
          </section>
          <section>
            <span className="field-label">Tool activity</span>
            <ToolActivity data={activity.data} error={activity.error} compact />
            <p className="inspector-note">
              Recent tool executions from this session. Expand an entry for its
              recorded details.
            </p>
          </section>
          <section className="availability">
            <span className="field-label">Connections</span>
            <Facts
              items={[
                ["Local service", connection],
                [
                  "Registered capabilities",
                  meta?.capabilities.length ?? "Checking",
                ],
                ["Agents", can("agents") ? "Available" : "Unavailable"],
              ]}
            />
          </section>
        </aside>
      )}
      <div
        className={`voice-dock ${voiceExpanded ? "expanded" : ""}`}
        aria-label="Voice controls"
      >
        <button
          className="voice-toggle"
          aria-label={
            voiceExpanded ? "Hide voice details" : "Show voice details"
          }
          aria-expanded={voiceExpanded}
          onClick={() => setVoiceExpanded((v) => !v)}
        >
          <VoiceOrb state={state} offline={stale} paused={!motion} />
          <strong>{voice}</strong>
          <span>Voice</span>
          <small>{voiceExpanded ? "Close" : "Details"}</small>
        </button>
        <div className="voice-status-copy">
          {stale
            ? "Voice status unavailable"
            : speaking
              ? "Speech activity"
              : state?.activity?.microphone_active
                ? "Say “Hanni” to begin"
                : "Microphone inactive"}
        </div>
        {voiceExpanded && (
          <div className="voice-detail-panel">
            <div>
              <h3>Voice session</h3>
              <button
                className="icon-button"
                aria-label="Close voice details"
                onClick={() => setVoiceExpanded(false)}
              >
                <Icon name="close" />
              </button>
            </div>
            <p>
              {stale
                ? "Voice status is unavailable until a current sample is reported."
                : speaking
                  ? "Local speech synthesis or playback activity. Output levels are unavailable."
                  : state?.activity?.microphone_active
                    ? "Say “Hanni” to start. “That’s all” returns to standby."
                    : "Start the assistant to enable the existing voice session."}
            </p>
            <label>
              Microphone amplitude
              <meter
                min="0"
                max="1"
                value={stale ? 0 : state?.activity?.input_level || 0}
                aria-label="Measured microphone amplitude"
              />
            </label>
            <button
              className="text-link"
              aria-label={motion ? "Pause voice visual" : "Resume voice visual"}
              aria-pressed={!motion}
              onClick={() => setMotion((v) => !v)}
            >
              {motion ? "Pause voice visual" : "Resume voice visual"}
            </button>
            <button
              className="text-link"
              onClick={() => {
                setVoiceExpanded(false);
                navigate("voice");
              }}
            >
              Voice controls
            </button>
            <button
              className="text-link"
              onClick={() => {
                setVoiceExpanded(false);
                navigate("settings");
                setTimeout(
                  () =>
                    document.getElementById("audio-settings")?.scrollIntoView(),
                  30,
                );
              }}
            >
              Audio settings
            </button>
          </div>
        )}
        <button
          className="dock-stop"
          disabled={!chat.data?.token || Boolean(chat.error) || stopping}
          onClick={() => setConfirmAction("shutdown")}
        >
          Stop HANNI
        </button>
      </div>
      {palette && (
        <Modal title="Search HANNI" onClose={() => setPalette(false)}>
          <label htmlFor="workspace-search" className="sr-only">
            Search screens, capabilities, or loaded messages
          </label>
          <input
            ref={paletteRef}
            id="workspace-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Screens, capabilities, conversation…"
          />
          <div className="command-results">
            {matchedScreens.map(([key, value]) => (
              <button key={key} onClick={() => navigate(key as Screen)}>
                <span>{value.label}</span>
                <small>Open workspace</small>
              </button>
            ))}
            {matchedMessages.map((row) => (
              <button
                key={`message-${row.id}`}
                onClick={() => {
                  navigate("chat");
                  setTimeout(
                    () =>
                      document
                        .getElementById(`message-${row.id}`)
                        ?.scrollIntoView({ block: "center" }),
                    50,
                  );
                }}
              >
                <span>{row.content.slice(0, 90)}</span>
                <small>Loaded message</small>
              </button>
            ))}
            {matchedCapabilities.map((item) => (
              <button
                key={item.name}
                onClick={() =>
                  prepare(
                    `Tell me about the ${item.name} capability and what permission it needs.`,
                  )
                }
              >
                <span>{item.name}</span>
                <small>Prepare a question</small>
              </button>
            ))}
            {!matchedScreens.length &&
              !matchedCapabilities.length &&
              !matchedMessages.length && (
                <Empty title="No matches">
                  Try a screen name or a registered capability. Only loaded
                  conversation history is searched.
                </Empty>
              )}
          </div>
          <p className="dialog-footer">
            Esc to dismiss. Capability selections prepare a draft; Send submits
            it.
          </p>
        </Modal>
      )}
      {confirmAction && (
        <Modal
          title={
            confirmAction === "clear"
              ? "Clear conversation history?"
              : confirmAction === "restart"
                ? "Restart HANNI?"
              : "Stop HANNI?"
          }
          onClose={() => setConfirmAction(null)}
        >
          <p className="confirmation-copy">
            {confirmAction === "clear"
              ? "This clears saved display history on this PC. It does not undo actions, erase saved memories, or reset the current conversation context."
              : confirmAction === "restart"
                ? "HANNI will finish the current response, reload the assistant and its configured models, then reconnect this page. Saved history, memories and device settings are retained. Externally managed models stay running."
                : "The current response finishes before shutdown. HANNI stops the model server this session started; an externally managed server stays running."}
          </p>
          <div className="dialog-actions">
            <button autoFocus onClick={() => setConfirmAction(null)}>
              Cancel
            </button>
            <button
              className="danger-button"
              disabled={Boolean(chat.error)}
              onClick={confirm}
            >
              {confirmAction === "clear" ? "Clear history" : confirmAction === "restart" ? "Restart HANNI" : "Stop HANNI"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
