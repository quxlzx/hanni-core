import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { request, useResource, write } from "./api";
import { AssistantResponse } from "./turn_details";
import { ComposerMetrics } from "./composer_metrics";
import { App as Workspace } from "./workspace";
import type { Chat, Contract, Message, Telemetry } from "./types";
import { MCPPanel } from "./mcp_panel";
import { ModelsPanel } from "./model_settings";
import { DraftFiles, FilePicker, MessageFiles, useChatFiles } from "./chat_files";
import { sameFiles } from "./attachment_files";
import {
  CommandSuggestions,
  CommandOutput,
  type CommandResult,
} from "./slash_commands";
import "./chat_shell.css";

type Conversation = {
  id: string;
  title: string;
  updated: number;
  message_count: number;
};
type Panel =
  | "chat"
  | "models"
  | "mcp"
  | "settings"
  | "tasks"
  | "memory"
  | "skills"
  | "schedule"
  | "activity";
type TabState = { selected: string; tabs: string[] };
const defaultTabs: TabState = { selected: "default", tabs: ["default"] };

function readTabs(): TabState {
  try {
    const saved = JSON.parse(localStorage.getItem("hanni-chat-tabs") || "null");
    if (
      saved &&
      Array.isArray(saved.tabs) &&
      saved.tabs.length &&
      saved.tabs.every((id: unknown) => typeof id === "string") &&
      saved.tabs.includes(saved.selected)
    )
      return { selected: saved.selected, tabs: saved.tabs.slice(0, 30) };
  } catch {
    /* Preferences are optional. History lives on the server. */
  }
  return defaultTabs;
}

export function ChatIcon({ name }: { name: string }) {
  const paths: Record<string, ReactNode> = {
    new: (
      <>
        <path d="M12 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7" />
        <path d="m15 3 6 6M10 14l-1 4 4-1L22 8l-5-5Z" />
      </>
    ),
    search: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 5 5" />
      </>
    ),
    models: (
      <>
        <path d="m12 3 9 5v9l-9 5-9-5V8Zm0 10 9-5M3 8l9 5v9M8 5l9 5" />
      </>
    ),
    mcp: (
      <>
        <path d="m8 16 8-8M7 12l-2-2a3 3 0 0 1 0-4l1-1a3 3 0 0 1 4 0l2 2M12 17l2 2a3 3 0 0 0 4 0l1-1a3 3 0 0 0 0-4l-2-2M3 21l4-4M17 7l4-4" />
      </>
    ),
    settings: (
      <>
        <path
          d="m9 3-.5 3-2 1L4 6l-2 4 2.5 2v2L2 16l2 4 2.5-1 2 1 .5 3h5l.5-3 2-1 2.5 1 2-4-2.5-2v-2l2.5-2-2-4-2.5 1-2-1-.5-3Z"
          transform="translate(0 -1) scale(1 .96)"
        />
        <circle cx="11.5" cy="11.5" r="3" />
      </>
    ),
    panel: (
      <>
        <rect x="4" y="4" width="16" height="16" rx="1" />
        <path d="M10 4v16m5-12-2 4 2 4" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    close: <path d="m7 7 10 10M7 17 17 7" />,
    arrow: <path d="M12 20V4m-6 6 6-6 6 6" />,
    copy: (
      <>
        <rect x="8" y="8" width="12" height="13" rx="2" />
        <path d="M15 8V3H3v13h5" />
      </>
    ),
    edit: (
      <>
        <path d="m16 3 5 5-12 12-6 1 1-6Z" />
        <path d="m13 6 5 5" />
      </>
    ),
    check: <path d="m5 12 4 4L20 5" />,
    tools: (
      <>
        <path d="M14 4a6 6 0 0 0-7 7L3 17a3 3 0 0 0 4 4l6-6a6 6 0 0 0 7-7l-5 4-4-4Z" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 6v6l4 2" />
      </>
    ),
    menu: <path d="M4 6h16M4 12h16M4 18h16" />,
    stop: <rect x="6" y="6" width="12" height="12" rx="1" />,
    chevron: <path d="m9 5 7 7-7 7" />,
    reasoning: (
      <>
        <path d="M9 18h6m-5 3h4M8 13a6 6 0 1 1 8 0c-1 1-1 2-1 3H9c0-1 0-2-1-3Z" />
      </>
    ),
    tokens: (
      <>
        <path d="M4 18V9m4 9V5m4 13V8m4 10V4m4 14v-6" />
      </>
    ),
    speed: (
      <>
        <path d="M4 19a9 9 0 1 1 16 0M12 13l5-5" />
        <circle cx="12" cy="13" r="1" />
      </>
    ),
  };
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.tools}
    </svg>
  );
}

function IconButton({
  label,
  icon,
  onClick,
  disabled = false,
}: {
  label: string;
  icon: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className="hc-icon"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
    >
      <ChatIcon name={icon} />
    </button>
  );
}

function ChatMessage({
  row,
  token,
  edit,
  openTasks,
}: {
  row: Message;
  token: string;
  edit: (value: string) => void;
  openTasks: () => void;
}) {
  const [copied, setCopied] = useState(false),
    [error, setError] = useState("");
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (copyTimer.current) clearTimeout(copyTimer.current);
    },
    [],
  );
  async function copy() {
    try {
      await navigator.clipboard.writeText(row.content);
      setCopied(true);
      setError("");
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(false), 1800);
    } catch {
      setError("Clipboard unavailable. Select the message text to copy it.");
    }
  }
  return (
    <article
      className={`hc-message ${row.role === "user" ? "hc-user" : "hc-assistant"}`}
      aria-label={`${row.role === "user" ? "You" : "HANNI"}, ${new Date(row.created * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`}
    >
      {row.role === "user" ? (
        <>
          <MessageFiles files={row.attachments || []} token={token} conversation={row.conversation || "default"} />
          <p className="hc-user-text">{row.content}</p>
        </>
      ) : (
        <AssistantResponse row={row} token={token} openTasks={openTasks} />
      )}
      {row.status !== "complete" && row.status !== "working" && (
        <p
          className={`hc-message-state ${row.status === "interrupted" ? "hc-error-text" : ""}`}
        >
          {row.status === "queued"
            ? "Queued"
            : row.status === "working"
              ? "Working"
              : "Response interrupted"}
        </p>
      )}
      {row.status !== "working" && (
        <div className="hc-message-actions">
          <IconButton
            label={copied ? "Copied" : "Copy message"}
            icon={copied ? "check" : "copy"}
            onClick={copy}
          />
          {row.role === "user" && (
            <IconButton
              label="Edit in composer"
              icon="edit"
              onClick={() => edit(row.content)}
            />
          )}
          {row.role !== "user" && (
            <span>
              HANNI <span aria-hidden="true">·</span>{" "}
              {new Date(row.created * 1000).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          )}
        </div>
      )}
      {error && (
        <p role="status" className="hc-error-text">
          {error}
        </p>
      )}
    </article>
  );
}

export function ChatApp() {
  const [session, setSession] = useState<TabState>(readTabs);
  const [mobile, setMobile] = useState(
    () => matchMedia("(max-width: 760px)").matches,
  );
  const [panel, setPanel] = useState<Panel>("chat"),
    [sidebarOpen, setSidebarOpen] = useState(false),
    [collapsed, setCollapsed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false),
    [search, setSearch] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({}),
    [sending, setSending] = useState(false),
    [creating, setCreating] = useState(false),
    [sendError, setSendError] = useState("");
  const [showLatest, setShowLatest] = useState(false);
  const [commandOutput, setCommandOutput] = useState<
    Record<string, { command: string; result: CommandResult }>
  >({});
  const [commandBusy, setCommandBusy] = useState(false);
  const [older, setOlder] = useState<{
      id: string;
      epoch: string;
      messages: Message[];
      hasMore: boolean;
    }>({ id: "", epoch: "", messages: [], hasMore: false }),
    [loadingOlder, setLoadingOlder] = useState(false);
  const pending = useRef<Record<string, { id: string; message: string; attachments?: string[] }>>({});
  const [draggingFiles, setDraggingFiles] = useState(false);
  const dragDepth = useRef(0);
  const input = useRef<HTMLTextAreaElement>(null),
    log = useRef<HTMLDivElement>(null),
    nearBottom = useRef(true),
    searchDialog = useRef<HTMLDialogElement>(null);
  const chat = useResource<Chat>(
    `/api/chat?conversation=${encodeURIComponent(session.selected)}`,
    700,
  );
  const list = useResource<{ conversations: Conversation[] }>(
    "/api/chat/conversations",
    2000,
  );
  const telemetry = useResource<Telemetry>("/api/state", 3000),
    contract = useResource<Contract>("/api/workspace", 30000);
  const conversations = list.data?.conversations || [];
  const selected = session.selected,
    draft = drafts[selected] || "";
  const data = chat.data?.conversation_id === selected ? chat.data : null;
  const token = !chat.error ? chat.data?.token || "" : "";
  const attached = useChatFiles(selected, token);
  const attachmentsAvailable = Boolean(contract.data?.features.attachments);
  useEffect(() => {
    if (data?.pending_attachments) attached.restore(selected, data.pending_attachments);
  }, [data?.pending_attachments, selected]);
  const ready = Boolean(data?.ready && !chat.error);
  const rows = [
    ...new Map(
      [
        ...(older.id === selected && older.epoch === data?.epoch
          ? older.messages
          : []),
        ...(data?.messages || []),
      ].map((row) => [row.id, row]),
    ).values(),
  ].sort((a, b) => a.id - b.id);
  const busyRow = rows.find((row) => row.status === "working" && row.task_id);
  const error =
    sendError || chat.error || (!ready && telemetry.data?.model_detail) || "";
  const lastRow = rows.at(-1);

  useEffect(() => {
    const query = matchMedia("(max-width: 760px)");
    const resize = () => {
      setMobile(query.matches);
      setSidebarOpen(false);
    };
    query.addEventListener("change", resize);
    return () => query.removeEventListener("change", resize);
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem("hanni-chat-tabs", JSON.stringify(session));
    } catch {
      /* Server history remains available. */
    }
    nearBottom.current = true;
    setShowLatest(false);
  }, [session]);
  useEffect(() => {
    if (!list.data) return;
    const ids = new Set(conversations.map((item) => item.id));
    // Keep newly created tabs until the next list refresh has observed them.
    if (!ids.has(selected) && !creating && chat.error) setSession(defaultTabs);
  }, [list.data, chat.error, creating, selected]);
  useEffect(() => {
    if (panel === "chat" && nearBottom.current && log.current)
      log.current.scrollTop = log.current.scrollHeight;
  }, [panel, selected, lastRow?.id, lastRow?.content]);
  useEffect(() => {
    const node = log.current;
    if (
      panel !== "chat" ||
      lastRow?.status !== "working" ||
      !node?.firstElementChild
    )
      return;
    const observer = new ResizeObserver(() => {
      if (nearBottom.current) node.scrollTop = node.scrollHeight;
    });
    observer.observe(node.firstElementChild);
    return () => observer.disconnect();
  }, [panel, selected, lastRow?.status]);
  useEffect(() => {
    if (!input.current) return;
    input.current.style.height = "auto";
    input.current.style.height = `${Math.min(input.current.scrollHeight, 200)}px`;
  }, [draft, panel]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen((value) => !value);
      }
      if (event.key === "Escape") {
        setSidebarOpen(false);
        setSearchOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  useEffect(() => {
    if (searchOpen) searchDialog.current?.showModal();
  }, [searchOpen]);

  function showPanel(value: Panel) {
    setPanel(value);
    setSidebarOpen(false);
    requestAnimationFrame(() => document.getElementById("hc-main")?.focus());
  }
  function openChat(id: string) {
    setSession((current) => ({
      selected: id,
      tabs: current.tabs.includes(id)
        ? current.tabs
        : [...current.tabs.slice(-29), id],
    }));
    setSendError("");
    setPanel("chat");
    setSearchOpen(false);
    setSidebarOpen(false);
    requestAnimationFrame(() => input.current?.focus());
  }
  async function newChat() {
    if (creating || !token) return;
    setCreating(true);
    setSendError("");
    try {
      const id = crypto.randomUUID();
      await write("/api/chat/conversations", token, { id });
      list.setData((current) => ({
        conversations: [
          {
            id,
            title: "New chat",
            updated: Date.now() / 1000,
            message_count: 0,
          },
          ...(current?.conversations || []),
        ],
      }));
      openChat(id);
      list.refresh();
    } catch (caught) {
      setSendError(
        caught instanceof Error
          ? caught.message
          : "Could not create a conversation.",
      );
    } finally {
      setCreating(false);
    }
  }
  function closeTab(id: string) {
    if (session.tabs.length === 1) {
      showPanel("chat");
      return;
    }
    setSession((current) => {
      const tabs = current.tabs.filter((tab) => tab !== id);
      return {
        tabs,
        selected:
          current.selected === id
            ? tabs[Math.max(0, current.tabs.indexOf(id) - 1)]
            : current.selected,
      };
    });
    setSendError("");
  }
  function editDraft(value: string) {
    setDrafts((current) => ({ ...current, [selected]: value }));
    input.current?.focus();
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    const message = draft.trim() || (attached.files.length ? "Please review the attached files." : "");
    if (message.startsWith("/")) {
      if (attached.files.length && message.toLowerCase() !== "/stop") {
        setSendError("Send files with a regular message. Slash commands do not accept files.");
        return;
      }
      await runCommand(message);
      return;
    }
    if (!message || !ready || sending || !attached.ready) return;
    const conversation = selected;
    const fileIds = attached.ids;
    const prior = pending.current[conversation];
    const turn =
      prior?.message === message && sameFiles(prior.attachments, fileIds)
        ? prior : { id: crypto.randomUUID(), message, attachments: fileIds };
    pending.current[conversation] = turn;
    setSending(true);
    setSendError("");
    nearBottom.current = true;
    try {
      await write("/api/chat", token, { ...turn, conversation });
      delete pending.current[conversation];
      attached.clear(conversation, fileIds);
      setDrafts((current) =>
        (current[conversation] || "").trim() === draft.trim()
          ? { ...current, [conversation]: "" }
          : current,
      );
      chat.refresh();
      list.refresh();
    } catch (caught) {
      setSendError(
        caught instanceof Error
          ? caught.message
          : "Message was not confirmed. Retry to check the same request.",
      );
    } finally {
      setSending(false);
      input.current?.focus();
    }
  }
  async function runCommand(message: string) {
    const stopping = message.toLowerCase() === "/stop";
    if (!token || (commandBusy && !stopping)) return;
    const conversation = selected;
    const prior = pending.current[conversation];
    const turn =
      prior?.message === message && !prior.attachments?.length ? prior : { id: crypto.randomUUID(), message };
    pending.current[conversation] = turn;
    if (!stopping) setCommandBusy(true);
    setSendError("");
    try {
      if (stopping) window.speechSynthesis?.cancel();
      let result = await write<CommandResult>("/api/chat/command", token, {
        id: turn.id,
        command: message,
        conversation,
      });
      delete pending.current[conversation];
      setDrafts((current) =>
        current[conversation]?.trim() === message
          ? { ...current, [conversation]: "" }
          : current,
      );
      const display = (value: CommandResult) =>
        setCommandOutput((current) => ({
          ...current,
          [value.conversation || conversation]: {
            command: message,
            result: value,
          },
        }));
      display(result);
      while (result.pending && result.id) {
        await new Promise((resolve) => setTimeout(resolve, 700));
        result = await request<CommandResult>(
          `/api/chat/command?id=${encodeURIComponent(result.id)}`,
          { headers: { "X-Hanni-Token": token } },
        );
        // /stop keeps its own result visible while compression winds down.
        setCommandOutput((current) =>
          current[conversation]?.command === message
            ? { ...current, [conversation]: { command: message, result } }
            : current,
        );
      }
      if (result.conversation) openChat(result.conversation);
      if (result.reset_history)
        setOlder({ id: "", epoch: "", messages: [], hasMore: false });
      chat.refresh();
      list.refresh();
    } catch (caught) {
      setSendError(
        caught instanceof Error
          ? caught.message
          : "Command result was not confirmed. Retry to check the same request.",
      );
    } finally {
      if (!stopping) setCommandBusy(false);
      input.current?.focus();
    }
  }
  async function loadOlder() {
    if (!rows.length || loadingOlder || !data) return;
    setLoadingOlder(true);
    const conversation = selected,
      epoch = data.epoch;
    const before = rows[0].id,
      node = log.current,
      height = node?.scrollHeight || 0;
    try {
      const page = await request<Chat>(
        `/api/chat?conversation=${encodeURIComponent(conversation)}&before=${before}`,
      );
      if (page.epoch !== epoch) return;
      setOlder((current) => ({
        id: conversation,
        epoch,
        hasMore: page.has_more,
        messages: [
          ...page.messages,
          ...(current.id === conversation && current.epoch === epoch
            ? current.messages
            : []),
        ],
      }));
      requestAnimationFrame(() => {
        if (node) node.scrollTop += node.scrollHeight - height;
      });
    } catch (caught) {
      setSendError(
        caught instanceof Error
          ? caught.message
          : "Earlier messages unavailable.",
      );
    } finally {
      setLoadingOlder(false);
    }
  }
  async function stopResponse() {
    await runCommand("/stop");
  }
  const hasOlder =
    older.id === selected &&
    older.epoch === data?.epoch &&
    older.messages.length
      ? older.hasMore
      : Boolean(data?.has_more);
  const modelSource =
    telemetry.data?.model.file ||
    contract.data?.models[0]?.name ||
    "Local model";
  const modelName = modelSource
    .split(/[\\/]/)
    .at(-1)!
    .replace(/\.gguf$/i, "");
  const nav = [
    { id: "models", label: "Models" },
    { id: "mcp", label: "MCP" },
    { id: "settings", label: "Settings" },
  ] as const;

  return (
    <div
      className={`hc-shell ${collapsed ? "hc-collapsed" : ""} ${sidebarOpen ? "hc-sidebar-open" : ""}`}
    >
      <a className="skip-link" href="#hc-main">
        Skip to conversation
      </a>
      {sidebarOpen && (
        <button
          className="hc-scrim"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <aside
        className="hc-sidebar"
        aria-label="Main navigation"
        inert={mobile && !sidebarOpen}
      >
        <div className="hc-brand-row">
          <button
            className="hc-logo"
            title="HANNI"
            aria-label="HANNI — open conversation"
            onClick={() => showPanel("chat")}
          >
            h<span>.</span>
          </button>
          <IconButton
            label="Collapse sidebar"
            icon="panel"
            onClick={() => {
              setCollapsed(true);
              setSidebarOpen(false);
            }}
          />
        </div>
        <nav className="hc-nav">
          <button onClick={newChat} disabled={creating || !token}>
            <ChatIcon name="new" />
            {creating ? "Creating chat…" : "New chat"}
          </button>
          <button
            onClick={() => {
              setSearch("");
              setSearchOpen(true);
            }}
            aria-keyshortcuts="Control+k Meta+k"
          >
            <ChatIcon name="search" />
            Search<kbd aria-hidden="true">Ctrl K</kbd>
          </button>
          {nav.map((item) => (
            <button
              key={item.id}
              aria-current={panel === item.id ? "page" : undefined}
              onClick={() => showPanel(item.id)}
            >
              <ChatIcon name={item.id} />
              {item.label}
            </button>
          ))}
        </nav>
        <div className="hc-recents">
          <h2>Recent conversations</h2>
          {list.error && (
            <p className="hc-error-text" role="status">
              History unavailable. <button onClick={list.refresh}>Retry</button>
            </p>
          )}
          {!list.data && !list.error && (
            <p className="hc-muted">Loading conversations…</p>
          )}
          <div>
            {conversations.map((item) => (
              <button
                className={
                  item.id === selected && panel === "chat" ? "is-selected" : ""
                }
                aria-current={
                  item.id === selected && panel === "chat" ? "page" : undefined
                }
                key={item.id}
                title={item.title}
                onClick={() => openChat(item.id)}
              >
                {item.title}
              </button>
            ))}
          </div>
        </div>
        <details className="hc-agent-nav">
          <summary>
            <ChatIcon name="tools" />
            Agent tools
          </summary>
          <nav aria-label="Agent tools">
            {(
              [
                ["tasks", "Tasks & approvals"],
                ["memory", "Memory"],
                ["skills", "Skills"],
                ["schedule", "Schedule"],
                ["activity", "Activity"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                onClick={() => showPanel(id)}
                aria-current={panel === id ? "page" : undefined}
              >
                {label}
              </button>
            ))}
          </nav>
        </details>
        <p className="hc-connection" role="status">
          <span className={ready ? "is-ready" : ""} />
          {chat.error
            ? "Reconnecting…"
            : ready
              ? "Local · Connected"
              : "Connecting to model…"}
        </p>
      </aside>
      <div className="hc-stage">
        <header className="hc-tabbar">
          <div className="hc-menu-button">
            <IconButton
              label="Open sidebar"
              icon="panel"
              onClick={() => {
                setCollapsed(false);
                setSidebarOpen((value) => !value);
              }}
            />
          </div>
          <nav className="hc-tabs" aria-label="Open conversations">
            {session.tabs.map((id) => (
              <div
                className={`hc-tab ${id === selected && panel === "chat" ? "is-selected" : ""}`}
                key={id}
              >
                <button
                  title={
                    conversations.find((item) => item.id === id)?.title ||
                    "New chat"
                  }
                  aria-current={
                    id === selected && panel === "chat" ? "page" : undefined
                  }
                  onClick={() => openChat(id)}
                >
                  {conversations.find((item) => item.id === id)?.title ||
                    "New chat"}
                </button>
                {session.tabs.length > 1 && (
                  <IconButton
                    label={`Close ${conversations.find((item) => item.id === id)?.title || "chat"} tab`}
                    icon="close"
                    onClick={() => closeTab(id)}
                  />
                )}
              </div>
            ))}
          </nav>
          <IconButton
            label="New chat tab"
            icon="plus"
            disabled={creating || !token}
            onClick={newChat}
          />
          {panel !== "chat" && (
            <span className="hc-panel-label">
              {panel === "mcp"
                ? "MCP"
                : panel.charAt(0).toUpperCase() + panel.slice(1)}
            </span>
          )}
        </header>
        <main
          id="hc-main"
          className={`hc-main ${panel === "chat" ? "" : "hc-panel-main"}`}
          tabIndex={-1}
          onDragOver={event => {
            if (panel === "chat" && event.dataTransfer.types.includes("Files")) event.preventDefault();
          }}
          onDrop={event => {
            if (panel !== "chat" || !event.dataTransfer.types.includes("Files")) return;
            event.preventDefault();
            if (attachmentsAvailable && token && !sending) attached.add(event.dataTransfer.files);
          }}
        >
          {panel === "chat" ? (
            <>
              <div
                className="hc-log"
                ref={log}
                onScroll={() => {
                  const node = log.current;
                  if (node) {
                    nearBottom.current =
                      node.scrollHeight - node.scrollTop - node.clientHeight <
                      100;
                    setShowLatest(!nearBottom.current);
                  }
                }}
              >
                <div
                  className="hc-transcript"
                  role="log"
                  aria-label="Conversation"
                  aria-live="polite"
                  aria-relevant="additions text"
                >
                  {hasOlder && (
                    <button
                      className="hc-load-older"
                      disabled={loadingOlder}
                      onClick={loadOlder}
                    >
                      {loadingOlder ? "Loading…" : "Load earlier messages"}
                    </button>
                  )}
                  {!data && !chat.error && (
                    <p className="hc-loading" role="status">
                      Loading conversation…
                    </p>
                  )}
                  {data && !rows.length && (
                    <div className="hc-empty">
                      <div className="hc-welcome-logo" aria-hidden="true">
                        h.
                      </div>
                      <h1>What can I help with?</h1>
                      <p>Ask a question or give HANNI a task.</p>
                    </div>
                  )}
                  {rows.map((row) => (
                    <ChatMessage
                      key={row.id}
                      row={row}
                      token={token}
                      edit={editDraft}
                      openTasks={() => showPanel("tasks")}
                    />
                  ))}
                </div>
              </div>
              <div className="hc-composer-area">
                {commandOutput[selected] && (
                  <CommandOutput
                    {...commandOutput[selected]}
                    dismiss={() =>
                      setCommandOutput((current) => {
                        const next = { ...current };
                        delete next[selected];
                        return next;
                      })
                    }
                    resume={openChat}
                  />
                )}
                {showLatest && (
                  <button
                    type="button"
                    className="hc-jump-latest"
                    aria-label="Jump to latest message"
                    title="Jump to latest message"
                    onClick={() => {
                      if (log.current)
                        log.current.scrollTop = log.current.scrollHeight;
                      nearBottom.current = true;
                      setShowLatest(false);
                    }}
                  >
                    <ChatIcon name="arrow" />
                  </button>
                )}
                {error && (
                  <div className="hc-error" role="alert">
                    <div>
                      <strong>
                        {sendError
                          ? "Request needs attention"
                          : "Connection unavailable"}
                      </strong>
                      <p>{error}</p>
                    </div>
                    <button
                      onClick={() => {
                        setSendError("");
                        chat.refresh();
                        telemetry.refresh();
                      }}
                    >
                      Retry
                    </button>
                  </div>
                )}
                <form className={`hc-composer ${draggingFiles ? "hc-file-dragging" : ""}`} onSubmit={submit}
                  onDragEnter={event => {
                    if (!event.dataTransfer.types.includes("Files") || !attachmentsAvailable || !token || sending) return;
                    event.preventDefault(); dragDepth.current += 1; setDraggingFiles(true);
                  }}
                  onDragOver={event => {
                    if (event.dataTransfer.types.includes("Files")) { event.preventDefault(); event.dataTransfer.dropEffect = attachmentsAvailable && !sending ? "copy" : "none"; }
                  }}
                  onDragLeave={event => {
                    event.preventDefault(); dragDepth.current = Math.max(0, dragDepth.current - 1);
                    if (!dragDepth.current) setDraggingFiles(false);
                  }}
                  onDrop={event => {
                    if (!event.dataTransfer.types.includes("Files")) return;
                    event.preventDefault(); event.stopPropagation(); dragDepth.current = 0; setDraggingFiles(false);
                    if (attachmentsAvailable && token && !sending) attached.add(event.dataTransfer.files);
                  }}>
                  {draggingFiles && <div className="hc-file-drop-hint" role="status">Drop files to attach</div>}
                  <DraftFiles state={attached} disabled={sending} />
                  <CommandSuggestions
                    draft={draft}
                    token={token}
                    choose={(value) => {
                      editDraft(value);
                      input.current?.focus();
                    }}
                  />
                  <label className="sr-only" htmlFor="hc-message">
                    Message HANNI
                  </label>
                  <textarea
                    ref={input}
                    id="hc-message"
                    rows={2}
                    maxLength={4000}
                    value={draft}
                    placeholder="Type a message…"
                    onChange={(event) => editDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (
                        event.key === "Enter" &&
                        !event.shiftKey &&
                        !event.nativeEvent.isComposing
                      ) {
                        event.preventDefault();
                        event.currentTarget.form?.requestSubmit();
                      }
                    }}
                  />
                  <div className="hc-composer-toolbar">
                    <FilePicker disabled={!token || sending || !attachmentsAvailable || attached.files.length >= 5} add={attached.add} />
                    <details className="hc-composer-options">
                      <summary
                        aria-label="Conversation actions"
                        title="Conversation actions"
                      >
                        <ChatIcon name="plus" />
                      </summary>
                      <div>
                        <button
                          type="button"
                          onClick={newChat}
                          disabled={creating || !token}
                        >
                          New conversation
                        </button>
                        <button
                          type="button"
                          onClick={() => showPanel("tasks")}
                        >
                          Tasks &amp; approvals
                        </button>
                        <button
                          type="button"
                          onClick={() => showPanel("skills")}
                        >
                          Browse skills
                        </button>
                      </div>
                    </details>
                    <div className="hc-composer-end">
                      {draft.length > 3600 && (
                        <span className="hc-muted">{draft.length}/4000</span>
                      )}
                      <button
                        type="button"
                        className="hc-model-chip"
                        title="View model"
                        onClick={() => showPanel("models")}
                      >
                        <ChatIcon name="models" />
                        <span>{modelName}</span>
                      </button>
                      {(busyRow || commandBusy) &&
                      !draft.trim().startsWith("/") ? (
                        <IconButton
                          label="Stop response"
                          icon="stop"
                          onClick={stopResponse}
                        />
                      ) : (
                        <button
                          type="submit"
                          className="hc-send"
                          aria-label="Send message"
                          title="Send message"
                          disabled={
                            (!ready && !draft.trim().startsWith("/")) ||
                            !token ||
                            sending ||
                            (commandBusy &&
                              draft.trim().toLowerCase() !== "/stop") ||
                            (!draft.trim() && !attached.files.length) ||
                            (!attached.ready && draft.trim().toLowerCase() !== "/stop") ||
                            ((data?.queued || 0) >= 8 &&
                              !draft.trim().startsWith("/"))
                          }
                        >
                          <ChatIcon name="arrow" />
                        </button>
                      )}
                    </div>
                  </div>
                </form>
                <ComposerMetrics
                  row={rows.filter((row) => row.role === "assistant").at(-1)}
                  token={token}
                  model={telemetry.data?.model}
                />
                <p className="hc-composer-note">
                  {attached.files.length && !attached.ready ? "Finish or remove file uploads before sending." : commandBusy
                    ? "Running command… /stop cancels the response and compression."
                    : sending
                      ? "Sending…"
                      : data?.queued
                        ? `${data.queued} message${data.queued === 1 ? "" : "s"} queued`
                        : attached.files.length ? "Files are sent to the selected model. Long text may be excerpted." : "Shift + Enter for a new line"}
                </p>
              </div>
            </>
          ) : panel === "models" ? (
            <ModelsPanel telemetry={telemetry} token={token} />
          ) : panel === "mcp" ? (
            <MCPPanel token={token} />
          ) : (
            <Workspace
              key={panel}
              embeddedScreen={panel}
              onPrepare={(value) => {
                setDrafts((current) => ({ ...current, [selected]: value }));
                showPanel("chat");
                requestAnimationFrame(() => input.current?.focus());
              }}
            />
          )}
        </main>
      </div>
      {searchOpen && (
        <dialog
          ref={searchDialog}
          className="hc-search"
          aria-labelledby="hc-search-title"
          onCancel={(event) => {
            event.preventDefault();
            setSearchOpen(false);
          }}
          onClick={(event) => {
            if (event.target === event.currentTarget) setSearchOpen(false);
          }}
        >
          <header>
            <h2 id="hc-search-title">Search conversations</h2>
            <IconButton
              label="Close search"
              icon="close"
              onClick={() => setSearchOpen(false)}
            />
          </header>
          <label className="sr-only" htmlFor="hc-search-input">
            Search by conversation title
          </label>
          <input
            autoFocus
            id="hc-search-input"
            placeholder="Search by title…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <div className="hc-search-results">
            {conversations
              .filter((item) =>
                item.title
                  .toLocaleLowerCase()
                  .includes(search.toLocaleLowerCase()),
              )
              .map((item) => (
                <button key={item.id} onClick={() => openChat(item.id)}>
                  <ChatIcon name="clock" />
                  <span>{item.title}</span>
                  <time>
                    {new Date(item.updated * 1000).toLocaleDateString()}
                  </time>
                </button>
              ))}
            {conversations.every(
              (item) =>
                !item.title
                  .toLocaleLowerCase()
                  .includes(search.toLocaleLowerCase()),
            ) && <p>No matching conversations.</p>}
          </div>
        </dialog>
      )}
    </div>
  );
}
