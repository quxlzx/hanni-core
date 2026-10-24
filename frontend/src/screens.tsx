import { useEffect, useState, type ReactNode, type RefObject } from "react";
import { useResource, write } from "./api";
import type {
  Activity,
  Audio,
  Chat,
  Contract,
  Message,
  ModelState,
  Routing,
  Screen,
  Telemetry,
  ToolEvent,
} from "./types";
import "./screens.css";
import { ToolAccessSettings } from "./tool_access";

export type ScreenContext = {
  now: Date;
  dateOptions: Intl.DateTimeFormatOptions;
  greeting: string;
  state: Telemetry | null;
  meta: Contract | null;
  chat: { data: Chat | null; error: string };
  telemetry: { error: string };
  contract: { error: string; refresh: () => void };
  activity: { data: Activity | null; error: string };
  stale: boolean;
  ready: boolean;
  busy: boolean;
  stopping: boolean;
  restarting: boolean;
  sending: boolean;
  rows: Message[];
  samples: { cpu: number[]; ram: number[]; net: number[] };
  composer: ReactNode;
  navigate: (screen: Screen) => void;
  prepare: (message: string) => void;
  hasOlder: boolean;
  loadingOlder: boolean;
  loadOlder: () => void;
  logRef: RefObject<HTMLDivElement | null>;
  bottomRef: RefObject<boolean>;
  setConfirmAction: (action: "clear" | "shutdown" | "restart" | null) => void;
  deviceRevision: number;
  refreshSettings: () => void;
  inspect: boolean;
  toggleInspect: () => void;
  motion: boolean;
  toggleMotion: () => void;
  sendError: string;
};
const fmt = (value: number | null | undefined, digits = 1) =>
  typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(digits)
    : "Unavailable";
const percent = (value: number | null | undefined) =>
  value == null ? "Unavailable" : `${fmt(value)}%`;
const pretty = (file?: string) =>
  file?.replace(/[-_]Q\d.*\.gguf$/i, "").replace(/\.gguf$/i, "") ||
  "Not reported";
const modelFileName = (file?: string) => file?.split(/[\\/]/).pop();
const rate = (value: number | null | undefined) =>
  value == null
    ? "Unavailable"
    : value >= 1048576
      ? `${fmt(value / 1048576)} MiB/s`
      : `${fmt(value / 1024)} KiB/s`;
const time = (value: number) =>
  new Date(value * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

export function HomeScreen({ context: c }: { context: ScreenContext }) {
  const recent = c.rows
    .filter((row) => row.role === "user")
    .slice(-5)
    .reverse();
  const resources = c.state?.resources;
  return (
    <div className="home-page">
      <header className="screen-heading">
        <div>
          <h1>
            {c.greeting}
            <span>.</span>
          </h1>
          <p>{c.now.toLocaleDateString("en-US", c.dateOptions)}</p>
        </div>
        <span className="screen-caption">Local assistant</span>
      </header>
      <section className="home-assistant" aria-label="Ask HANNI">
        <div className="section-title">
          <h2>Ask HANNI</h2>
          <span>
            {c.ready ? "Ready for a conversation" : "Conversation unavailable"}
          </span>
        </div>
        {c.composer}
        <div className="quick-prompts">
          {c.meta?.capabilities.some((cap) =>
            cap.name.includes("calendar"),
          ) && (
            <button onClick={() => c.prepare("What's on my calendar today?")}>
              Today's calendar
            </button>
          )}
          {c.meta?.capabilities.some(
            (cap) => cap.name === "process.top_memory",
          ) && (
            <button
              onClick={() =>
                c.prepare("What's using the most memory on my computer?")
              }
            >
              Check memory usage
            </button>
          )}
        </div>
      </section>
      <div className="home-columns">
        <section className="screen-section">
          <div className="section-title">
            <h2>Recent conversation</h2>
            <button className="text-link" onClick={() => c.navigate("chat")}>
              Open conversation
            </button>
          </div>
          {recent.length ? (
            <div className="recent-message-list">
              {recent.map((row) => (
                <button
                  key={row.id}
                  onClick={() => {
                    c.navigate("chat");
                    setTimeout(
                      () =>
                        document
                          .getElementById(`message-${row.id}`)
                          ?.scrollIntoView({ block: "center" }),
                      30,
                    );
                  }}
                >
                  <span>{row.content}</span>
                  <time>{time(row.created)}</time>
                </button>
              ))}
            </div>
          ) : (
            <Empty
              title={
                c.chat.error
                  ? "Conversation unavailable"
                  : "No conversation yet"
              }
            >
              {c.chat.error
                ? "Reconnecting to the local session. Your draft stays here."
                : "Start with a question. Text and voice history appear here."}
            </Empty>
          )}
        </section>
        <section className="screen-section">
          <div className="section-title">
            <h2>This computer</h2>
            <button className="text-link" onClick={() => c.navigate("mission")}>
              Inspect
            </button>
          </div>
          <Facts
            items={[
              ["Processor", percent(resources?.cpu_percent)],
              [
                "Memory",
                resources
                  ? `${fmt(resources.ram_used_gb)} / ${fmt(resources.ram_total_gb)} GiB`
                  : "Unavailable",
              ],
              [
                "Assistant",
                c.telemetry.error
                  ? "Unavailable"
                  : c.state?.model_status || "Checking",
              ],
              [
                "Model",
                <span title={c.meta?.models[0]?.name || c.state?.model?.file}>
                  {pretty(
                    modelFileName(
                      c.meta?.models[0]?.name || c.state?.model?.file,
                    ),
                  )}
                </span>,
              ],
            ]}
          />
          {c.stale && (
            <p className="subtle stale-notice">
              {c.state?.sampled_at
                ? "Last reported values. Waiting for fresh telemetry."
                : "Waiting for the first hardware sample."}
            </p>
          )}
        </section>
      </div>
      <section className="screen-section home-activity">
        <div className="section-title">
          <h2>Recent activity</h2>
          <span>Recorded tool executions</span>
        </div>
        <ToolActivity data={c.activity.data} error={c.activity.error} compact />
      </section>
    </div>
  );
}

export function ConversationScreen({ context: c }: { context: ScreenContext }) {
  return (
    <section className="conversation">
      <div className="conversation-heading">
        <div>
          <h1>Conversation</h1>
          <p className="subtle">
            {c.chat.data?.saved
              ? "History saved on this PC"
              : "Session history"}{" "}
            · Text replies stay silent
          </p>
          {c.state?.model_detail && <p className="error" role="status">{c.state.model_detail}</p>}
        </div>
        <button
          id="chat-clear"
          className="text-link"
          disabled={
            !c.ready || c.busy || Boolean(c.chat.data?.queued) || c.sending
          }
          onClick={() => c.setConfirmAction("clear")}
        >
          Clear history
        </button>
      </div>
      <div
        id="chat-messages"
        className="message-log"
        ref={c.logRef}
        role="log"
        aria-label="Conversation history"
        aria-live="polite"
        aria-relevant="additions text"
        onScroll={() => {
          const el = c.logRef.current;
          if (el)
            c.bottomRef.current =
              el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
      >
        {c.hasOlder && (
          <button
            id="chat-older"
            className="earlier"
            disabled={c.loadingOlder}
            onClick={c.loadOlder}
          >
            {c.loadingOlder
              ? "Loading earlier messages"
              : "Load earlier messages"}
          </button>
        )}
        {!c.chat.data && !c.chat.error ? (
          <Skeleton />
        ) : c.rows.length ? (
          c.rows.map((row) => (
            <article
              id={`message-${row.id}`}
              key={row.id}
              className={`chat-message ${row.role === "user" ? "user" : "assistant"}`}
              aria-busy={row.status === "working"}
            >
              <header>
                <span className="message-avatar" aria-hidden="true">
                  {row.role === "user" ? "Y" : "h."}
                </span>
                <strong>{row.role === "user" ? "You" : "HANNI"}</strong>
                <span>
                  {time(row.created)} ·{" "}
                  {row.channel === "browser"
                    ? "Chat"
                    : row.channel === "voice"
                      ? "Voice"
                      : "Terminal"}
                </span>
                {row.status === "interrupted" && (
                  <small className="error">Interrupted</small>
                )}
                {row.status === "queued" && <small>Queued</small>}
              </header>
              {row.status === "working" && !row.content ? (
                <Skeleton />
              ) : (
                <p>{row.content || "No response was recorded."}</p>
              )}
            </article>
          ))
        ) : (
          <div className="conversation-empty">
            <span className="conversation-mark" aria-hidden="true">
              h.
            </span>
            <h2>
              {c.stopping
                ? "Session stopped"
                : c.chat.error
                  ? "Connection unavailable"
                  : c.ready
                    ? "Start a conversation"
                    : "Assistant is not ready"}
            </h2>
            <p>
              {c.stopping
                ? "This session is stopping. Saved history remains available."
                : c.chat.error
                  ? "Start HANNI or check the launcher terminal. Reconnection is automatic."
                  : c.ready
                    ? "Type a question below. Your voice and text history share this space."
                    : "Inspect model status or start the assistant before sending. Your systems remain available to inspect."}
            </p>
          </div>
        )}
      </div>
      <details className="conversation-activity">
        <summary>
          Tool activity <span>Session audit</span>
        </summary>
        <ToolActivity data={c.activity.data} error={c.activity.error} compact />
      </details>
      <div className="conversation-composer">
        {c.composer}
        <div className="chat-session-state" role="status">
          {c.stopping
            ? "Session stopping"
            : c.chat.error
              ? "Disconnected. Sending is disabled."
              : c.busy
                ? "HANNI is responding"
                : c.chat.data?.queued
                  ? `${c.chat.data.queued} messages queued`
                  : c.ready
                    ? "Ready when you are"
                    : "Assistant is not ready"}
        </div>
      </div>
    </section>
  );
}

export function MissionScreen({ context: c }: { context: ScreenContext }) {
  const resources = c.state?.resources;
  const models = Object.entries(c.state?.model_residency || {});
  return (
    <div className="mission-page">
      <header className="screen-heading">
        <div>
          <h1>Mission Control</h1>
          <p>This computer</p>
        </div>
        <span className={`sample-status ${c.stale ? "warning" : ""}`}>
          {c.stale
            ? "Awaiting fresh readings"
            : `Sampled ${new Date(c.state!.sampled_at! * 1000).toLocaleTimeString()}`}
        </span>
      </header>
      <div className="mission-metrics">
        <div>
          <span>CPU</span>
          <strong id="cpu">{percent(resources?.cpu_percent)}</strong>
        </div>
        <div>
          <span>Memory</span>
          <strong id="ram">{percent(resources?.ram_percent)}</strong>
          <small>
            {resources
              ? `${fmt(resources.ram_used_gb)} / ${fmt(resources.ram_total_gb)} GiB`
              : "No reading"}
          </small>
        </div>
        <div>
          <span>System drive</span>
          <strong>{percent(c.state?.disk?.percent)}</strong>
          <small>
            {c.state?.disk
              ? `${fmt(c.state.disk.used_gb, 0)} / ${fmt(c.state.disk.total_gb, 0)} GiB`
              : "No reading"}
          </small>
        </div>
        <div>
          <span>Model status</span>
          <strong className="mission-model-state">
            {c.telemetry.error
              ? "Unavailable"
              : c.state?.model_status || "Checking"}
          </strong>
          <small>
            {c.chat.error
              ? "Queue unavailable"
              : c.chat.data
                ? `${c.chat.data.queued} queued`
                : "Queue checking"}
          </small>
        </div>
      </div>
      {c.stale && (
        <p className="stale-notice subtle">
          Readings below are last reported values, not current measurements.
        </p>
      )}
      <div className="mission-charts">
        <section>
          <div className="section-title">
            <h2>Processor</h2>
            <span>0–100% · Observed samples</span>
          </div>
          {c.samples.cpu.length ? (
            <Spark
              values={c.samples.cpu}
              ceiling={100}
              label="Recent measured CPU usage, from 0 to 100 percent"
            />
          ) : (
            <Empty title="CPU history pending">
              History fills from observed local samples.
            </Empty>
          )}
        </section>
        <section>
          <div className="section-title">
            <h2>Memory</h2>
            <span>0–100% · Observed samples</span>
          </div>
          {c.samples.ram.length ? (
            <Spark
              values={c.samples.ram}
              ceiling={100}
              label="Recent measured RAM usage, from 0 to 100 percent"
            />
          ) : (
            <Empty title="Memory history pending">
              History fills from observed local samples.
            </Empty>
          )}
        </section>
      </div>
      <div className="mission-columns">
        <section className="screen-section">
          <div className="section-title">
            <h2>Graphics</h2>
            <span>{resources?.gpu_note || "Device readings"}</span>
          </div>
          {!resources?.gpus.length ? (
            <Empty title="GPU telemetry unavailable">
              No supported sensor readings have arrived.
            </Empty>
          ) : (
            resources.gpus.map((gpu, index) => (
              <div className="gpu-row" key={`${gpu.name}-${index}`}>
                <div>
                  <h3>{gpu.name}</h3>
                  <span className="subtle">
                    {fmt(gpu.memory_used_mb / 1024)} /{" "}
                    {fmt(gpu.memory_total_mb / 1024)} GiB VRAM
                  </span>
                </div>
                <meter
                  min="0"
                  max={gpu.memory_total_mb || 1}
                  value={gpu.memory_used_mb}
                  aria-label={`${gpu.name} VRAM usage`}
                />
                <div>
                  <span>{percent(gpu.utilization_percent)} load</span>
                  <small>
                    {gpu.temperature_c == null
                      ? "Temperature unavailable"
                      : `${fmt(gpu.temperature_c, 0)} °C`}
                  </small>
                </div>
              </div>
            ))
          )}
          <div className="section-title network-title">
            <h2>Network</h2>
            <span>All local interfaces</span>
          </div>
          <div className="network-readings">
            <div>
              <span>Receive</span>
              <strong>{rate(c.state?.network?.receive_bps)}</strong>
            </div>
            <div>
              <span>Send</span>
              <strong>{rate(c.state?.network?.send_bps)}</strong>
            </div>
          </div>
        </section>
        <section className="screen-section">
          <div className="section-title">
            <h2>Inference models</h2>
            <span>Residency</span>
          </div>
          {models.length ? (
            models.map(([id, model]) => (
              <ModelRow key={id} id={id} model={model} />
            ))
          ) : c.meta?.models.length ? (
            c.meta.models.map((model) => (
              <div className="model-row" key={model.id}>
                <div>
                  <h3 title={model.name}>
                    {pretty(modelFileName(model.name))}
                  </h3>
                  <p>{model.role} · Configured</p>
                </div>
                <span className="subtle">Residency not reported</span>
              </div>
            ))
          ) : (
            <Empty title="Model information unavailable">
              No configured model was returned.
            </Empty>
          )}
          <Facts
            items={[
              [
                "Background jobs",
                c.telemetry.error
                  ? "Unavailable"
                  : (c.state?.interaction?.active_background_jobs ??
                    "Unavailable"),
              ],
              ]}
          />
        </section>
      </div>
      <section className="screen-section">
        <div className="section-title">
          <h2>Execution activity</h2>
          <span>Recorded tool executions</span>
        </div>
        <ToolActivity data={c.activity.data} error={c.activity.error} compact />
      </section>
    </div>
  );
}

export function SettingsScreen({ context: c }: { context: ScreenContext }) {
  const policies = c.meta?.policies;
  return (
    <div className="settings-page">
      <header className="screen-heading">
        <div>
          <h1>Workspace settings</h1>
          <p>Local devices, controller policy and session</p>
        </div>
        <button className="text-link" onClick={c.refreshSettings}>
          Refresh settings
        </button>
      </header>
      <nav className="settings-jumps" aria-label="Settings sections">
        <a
          href="#integration-settings"
          onClick={(event) => {
            event.preventDefault();
            document
              .getElementById("integration-settings")
              ?.scrollIntoView({ block: "start" });
          }}
        >
          Integrations
        </a>
        <a
          href="#audio-settings"
          onClick={(event) => {
            event.preventDefault();
            document
              .getElementById("audio-settings")
              ?.scrollIntoView({ block: "start" });
          }}
        >
          Audio
        </a>
        <a
          href="#model-settings"
          onClick={(event) => {
            event.preventDefault();
            document
              .getElementById("model-settings")
              ?.scrollIntoView({ block: "start" });
          }}
        >
          Model routing
        </a>
        <a
          href="#policy-settings"
          onClick={(event) => {
            event.preventDefault();
            document
              .getElementById("policy-settings")
              ?.scrollIntoView({ block: "start" });
          }}
        >
          Permissions
        </a>
        <a
          href="#session-settings"
          onClick={(event) => {
            event.preventDefault();
            document
              .getElementById("session-settings")
              ?.scrollIntoView({ block: "start" });
          }}
        >
          Session
        </a>
      </nav>
      <section id="integration-settings" className="settings-section">
        <div>
          <h2>Integrations</h2>
          <p>External tools managed through HANNI.</p>
        </div>
      </section>
      <section id="audio-settings" className="settings-section">
        <div>
          <h2>Microphone &amp; speaker</h2>
          <p>Local voice session devices.</p>
        </div>
        {c.meta?.features.audio_devices ? (
          <AudioSettings
            key={`audio-${c.deviceRevision}`}
            token={c.chat.data?.token || ""}
            disabled={Boolean(c.chat.error) || c.stopping}
          />
        ) : (
          <Empty title="Audio settings unavailable">
            This session did not expose audio controls.
          </Empty>
        )}
      </section>
      <section id="model-settings" className="settings-section">
        <div>
          <h2>Model routing</h2>
          <p>GPU used when the model starts.</p>
        </div>
        {c.meta?.features.gpu_routing ? (
          <GpuSettings
            key={`gpu-${c.deviceRevision}`}
            token={c.chat.data?.token || ""}
            disabled={Boolean(c.chat.error) || c.stopping}
          />
        ) : (
          <Empty title="GPU routing unavailable">
            This session did not expose routing configuration.
          </Empty>
        )}
      </section>
      <section id="policy-settings" className="settings-section">
        <div>
          <h2>Tool access</h2>
          <p>Choose what the agent can do.</p>
        </div>
        <ToolAccessSettings token={c.chat.data?.token || ""} disabled={Boolean(c.chat.error) || c.stopping} />
      </section>
      <section className="settings-section">
        <div>
          <h2>Privacy &amp; permissions</h2>
          <p>Enforced by HANNI's controller.</p>
        </div>
        <div>
          {!c.meta ? (
            c.contract.error ? (
              <Empty title="Policies unavailable">
                Could not read the workspace contract.
              </Empty>
            ) : (
              <Skeleton />
            )
          ) : policies ? (
            <>
              <Facts
                items={[
                  [
                    "Controller policy",
                    policies.observe_first
                      ? "Observe-first with allowed actions"
                      : "Controller policy",
                  ],
                  [
                    "Owner auto-approval",
                    `Through level ${policies.owner_auto_approve_level}`,
                  ],
                  ["Dangerous actions", "Explicit confirmation required"],
                  ["Memory", policies.memory_enabled ? "Enabled" : "Disabled"],
                  [
                    "Memory retrieval",
                    policies.memory_retrieval ? "Enabled" : "Disabled",
                  ],
                  [
                    "Memory extraction",
                    policies.memory_extraction ? "Enabled" : "Disabled",
                  ],
                  ["Time zone", c.meta.timezone || "Not reported"],
                ]}
              />
              <details className="allowed-actions">
                <summary>
                  Configured allowed actions ({policies.allowed_actions.length})
                </summary>
                <ul>
                  {policies.allowed_actions.map((name) => (
                    <li key={name}>{name}</li>
                  ))}
                </ul>
              </details>
              <p className="subtle">
                These base policies come from HANNI's configuration. Agent Tool access is selected above.
              </p>
            </>
          ) : (
            <Empty title="Policies unavailable">
              Configuration metadata was not exposed.
            </Empty>
          )}
        </div>
      </section>
      <section className="settings-section">
        <div>
          <h2>Interface</h2>
          <p>Preferences saved on this computer.</p>
        </div>
        <div>
          <Facts
            items={[
              ["Appearance", "Dark"],
              [
                "Context inspector",
                <button className="text-link" onClick={c.toggleInspect}>
                  {c.inspect ? "Hide inspector" : "Show inspector"}
                </button>,
              ],
              [
                "Voice visual",
                <button
                  id="motion"
                  className="text-link"
                  aria-pressed={!c.motion}
                  onClick={c.toggleMotion}
                >
                  {c.motion ? "Pause visual" : "Resume visual"}
                </button>,
              ],
            ]}
          />
          <p className="subtle">
            Reduced motion starts the visual paused. Voice activity is measured
            by the local voice session.
          </p>
        </div>
      </section>
      <section id="session-settings" className="settings-section">
        <div>
          <h2>Session controls</h2>
          <p>Close the window to leave HANNI running.</p>
        </div>
        <div>
          <p className="subtle">
            Restart HANNI reloads the assistant and its configured models, then
            reconnects this page. Saved history and settings are retained.
          </p>
          <p className="subtle">
            Stop HANNI ends the launcher session and the model server it owns.
            Externally managed models stay running. Keep the launch terminal
            available for confirmations.
          </p>
          <button
            id="restart"
            disabled={
              !c.chat.data?.token || Boolean(c.chat.error) || c.stopping || !c.meta?.features.restart
            }
            onClick={() => c.setConfirmAction("restart")}
          >
            {c.restarting ? "Restarting HANNI" : "Restart HANNI"}
          </button>
          <button
            id="shutdown"
            className="danger-button"
            disabled={
              !c.chat.data?.token || Boolean(c.chat.error) || c.stopping
            }
            onClick={() => c.setConfirmAction("shutdown")}
          >
            {c.stopping && !c.restarting ? "Stopping HANNI" : "Stop HANNI"}
          </button>
          <p className="error" role="alert">
            {c.sendError}
          </p>
        </div>
      </section>
    </div>
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
export function Facts({ items }: { items: [string, ReactNode][] }) {
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
export function ToolActivity({
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
function ModelRow({ id, model }: { id: string; model: ModelState }) {
  return (
    <div className="model-row">
      <div>
        <h3 title={model.model}>{pretty(modelFileName(model.model))}</h3>
        <p>
          {model.role} · {id}
        </p>
      </div>
      <span className="model-status">{model.state}</span>
      <span>
        {model.process_ram_mb == null
          ? "RAM unavailable"
          : `${fmt(model.process_ram_mb / 1024)} GiB RAM`}
        <small>
          {model.device || "Device not reported"} ·{" "}
          {model.active_inferences ?? 0} active
        </small>
      </span>
    </div>
  );
}
export function AudioSettings({
  token,
  disabled,
}: {
  token: string;
  disabled: boolean;
}) {
  const resource = useResource<Audio>("/api/audio-devices", 0),
    [input, setInput] = useState("default"),
    [output, setOutput] = useState("default"),
    [saving, setSaving] = useState(false),
    [status, setStatus] = useState("");
  useEffect(() => {
    if (resource.data) {
      setInput(resource.data.input_id);
      setOutput(resource.data.output_id);
    }
  }, [resource.data]);
  async function save() {
    setSaving(true);
    setStatus("");
    try {
      const data = await write<Audio>("/api/audio-devices", token, {
        input_id: input,
        output_id: output,
      });
      resource.setData(data);
      setStatus(
        "Audio choices saved. Restart the voice session to apply them.",
      );
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Could not save devices.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="settings-fields">
      {resource.error ? (
        <Empty title="Audio devices unavailable">{resource.error}</Empty>
      ) : !resource.data ? (
        <Skeleton />
      ) : (
        <>
          <label htmlFor="microphone-device">Microphone</label>
          <select
            id="microphone-device"
            value={input}
            disabled={saving}
            onChange={(e) => setInput(e.target.value)}
          >
            <option value="default">System / configured default</option>
            {resource.data.inputs.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} · {d.hostapi}
              </option>
            ))}
            {resource.data.input_id !== "default" &&
              !resource.data.inputs.some(
                (d) => d.id === resource.data!.input_id,
              ) && (
                <option value={resource.data.input_id}>
                  Saved microphone · unavailable
                </option>
              )}
          </select>
          <label htmlFor="speaker-device">Speech output</label>
          <select
            id="speaker-device"
            value={output}
            disabled={saving}
            onChange={(e) => setOutput(e.target.value)}
          >
            <option value="default">Windows default output</option>
            {resource.data.outputs.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
            {resource.data.output_id !== "default" &&
              !resource.data.outputs.some(
                (d) => d.id === resource.data!.output_id,
              ) && (
                <option value={resource.data.output_id}>
                  Saved speaker · unavailable
                </option>
              )}
          </select>
          {(resource.data.input_error || resource.data.output_error) && (
            <p className="warning">
              {resource.data.input_error} {resource.data.output_error}
            </p>
          )}
        </>
      )}
      <div className="settings-actions">
        {resource.data && !resource.error && (
          <button
            id="audio-apply"
            disabled={!token || disabled || saving}
            onClick={save}
          >
            Apply audio devices
          </button>
        )}
        <button
          id="audio-refresh"
          className="text-link"
          disabled={saving}
          onClick={resource.refresh}
        >
          Refresh devices
        </button>
      </div>
      <p className="subtle" role="status">
        {status || "Changes apply when the voice session restarts."}
      </p>
    </div>
  );
}
function GpuSettings({
  token,
  disabled,
}: {
  token: string;
  disabled: boolean;
}) {
  const resource = useResource<Routing>("/api/gpu-routing", 0),
    [value, setValue] = useState("auto"),
    [saving, setSaving] = useState(false),
    [status, setStatus] = useState("");
  useEffect(() => {
    if (resource.data)
      setValue(
        resource.data.mode === "manual"
          ? resource.data.requested_device_id || "auto"
          : "auto",
      );
  }, [resource.data]);
  async function save() {
    setSaving(true);
    setStatus("");
    try {
      const data = await write<Routing>(
        "/api/gpu-routing",
        token,
        value === "auto"
          ? { mode: "auto" }
          : { mode: "manual", device_id: value },
      );
      resource.setData(data);
      setStatus(
        "Routing saved. Restart the model to move an already loaded model.",
      );
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Could not save routing.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="settings-fields">
      {resource.error ? (
        <Empty title="GPU routing unavailable">{resource.error}</Empty>
      ) : !resource.data ? (
        <Skeleton />
      ) : (
        <>
          <label htmlFor="gpu-route">Model GPU</label>
          <select
            id="gpu-route"
            value={value}
            disabled={saving || !resource.data.devices.length}
            onChange={(e) => setValue(e.target.value)}
          >
            <option value="auto">
              Automatic · smallest suitable 8 GB+ GPU
            </option>
            {resource.data.devices.map((d) => (
              <option value={d.id} key={d.id}>
                {d.name} · {fmt(d.total_mb / 1024)} GiB
              </option>
            ))}
            {value !== "auto" &&
              !resource.data.devices.some((d) => d.id === value) && (
                <option value={value}>Saved device · unavailable</option>
              )}
          </select>
          <p className="subtle">
            {resource.data.error ||
              `Selected: ${resource.data.selected_device_name || "No usable GPU"}. ${resource.data.restart_required ? "A model restart is required." : "Used on the next model start."}`}
          </p>
        </>
      )}
      <div className="settings-actions">
        {resource.data && !resource.error && (
          <button
            id="gpu-apply"
            disabled={
              !token || disabled || saving || !resource.data.devices.length
            }
            onClick={save}
          >
            Apply GPU routing
          </button>
        )}
        <button
          className="text-link"
          disabled={saving}
          onClick={resource.refresh}
        >
          Refresh GPUs
        </button>
      </div>
      {status && (
        <p className="subtle" role="status">
          {status}
        </p>
      )}
    </div>
  );
}
