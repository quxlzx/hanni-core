import { useRef, useState } from "react";
import { write } from "./api";
import { FeatureDialog } from "./feature_ui";
import {
  usePrivateResource,
  storeInspection,
  type AwarenessData,
  type VoiceData,
  type NotificationData,
} from "./feature_types";
import { AudioSettings, type ScreenContext } from "./screens";
import type { Screen } from "./types";
import "./awareness.css";

export function ScreenAwarenessPage({
  token,
  prepare,
}: {
  token: string;
  prepare: (message: string) => void;
}) {
  const resource = usePrivateResource<AwarenessData>("/api/awareness", token);
  return (
    <div className="awareness-page screen-awareness-page">
      <header className="screen-heading">
        <div>
          <h1>Screen awareness</h1>
          <p>Capture status and saved privacy policy</p>
        </div>
        <button className="text-link" onClick={resource.refresh}>
          Refresh status
        </button>
      </header>
      {resource.error && (
        <p className="feature-error" role="status">
          {resource.error}
        </p>
      )}
      <div className="awareness-layout">
        <section className="awareness-status">
          <div>
            <h2>Current screen context</h2>
            <span>
              {resource.data?.capture_active
                ? "Active"
                : resource.data
                  ? "Inactive"
                  : "Checking"}
            </span>
          </div>
          <p>
            {!resource.data
              ? "Checking screen capture support."
              : resource.data.available
                ? "Only authorized screen context can be used for analysis."
                : "Screen capture and visual analysis are unavailable in this session. No screen image is being collected."}
          </p>
          <button
            disabled={
              !token || Boolean(resource.error) || !resource.data?.available
            }
            title={resource.data?.reason}
            onClick={() =>
              prepare(
                "What am I looking at? Use only currently authorized screen context.",
              )
            }
          >
            Analyze current screen
          </button>
          {resource.data?.reason && (
            <details className="awareness-diagnostic">
              <summary>Capability details</summary>
              <p>{resource.data.reason}</p>
            </details>
          )}
        </section>
        <section className="awareness-privacy">
          <h2>Privacy policy</h2>
          <dl>
            <div>
              <dt>Screen capture</dt>
              <dd>
                {!resource.data
                  ? "Checking"
                  : resource.data.capture_active
                    ? "Active"
                    : "Inactive"}
              </dd>
            </div>
            <div>
              <dt>Screen context</dt>
              <dd>{resource.data ? "Unavailable" : "Checking"}</dd>
            </div>
            <div>
              <dt>Configured frame retention</dt>
              <dd>
                {resource.data?.retention_seconds == null
                  ? "Not reported"
                  : `${resource.data.retention_seconds} seconds`}
              </dd>
            </div>
          </dl>
          <p className="feature-note">
            Retention is a saved policy, not an active capture session.
          </p>
        </section>
      </div>
    </div>
  );
}

export function VoicePage({ context: c }: { context: ScreenContext }) {
  const token = c.chat.error || c.stopping ? "" : c.chat.data?.token || "";
  const resource = usePrivateResource<VoiceData>("/api/voice", token, 400);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const pending = useRef<{ action: string; id: string } | null>(null);
  const voice = resource.data;
  const available = voice !== null && voice.available && !resource.error;
  function enabled(action: keyof VoiceData["actions"]) {
    const value = voice?.actions[action];
    return Boolean(
      voice?.available &&
      !resource.error &&
      !busy &&
      token &&
      (typeof value === "boolean" ? value : value?.enabled),
    );
  }
  async function act(action: keyof VoiceData["actions"]) {
    if (!enabled(action)) return;
    if (pending.current?.action !== action)
      pending.current = { action, id: crypto.randomUUID() };
    setBusy(true);
    setError("");
    try {
      await write("/api/voice", token, pending.current);
      pending.current = null;
      resource.refresh();
    } catch (error) {
      setError(
        `${error instanceof Error ? error.message : "Voice control unavailable."} Check the current state before retrying.`,
      );
    } finally {
      setBusy(false);
    }
  }
  const metrics = [
    ["wake_to_listening_ms", "Utterance end to wake decision"],
    ["end_to_response_ms", "Utterance end to response"],
    ["first_audible_ms", "First audible response"],
    ["interrupt_ms", "Interruption"],
    ["audio_failures", "Audio processing failures"],
  ];
  return (
    <div className="awareness-page voice-page">
      <header className="screen-heading">
        <div>
          <h1>Voice &amp; audio</h1>
          <p>Existing local speech session</p>
        </div>
        <span className="voice-state-label">
          {resource.error ? "Disconnected" : voice?.state || "Checking"}
        </span>
      </header>
      {resource.error && (
        <p className="feature-error" role="status">
          {resource.error}
        </p>
      )}
      <section className="voice-controls-panel">
        <div className="voice-state-grid">
          <div>
            <span>Microphone</span>
            <strong>
              {available
                ? voice.muted
                  ? "Muted"
                  : voice.microphone_active
                    ? "Active"
                    : "Inactive"
                : "Disabled"}
            </strong>
          </div>
          <div>
            <span>Assistant</span>
            <strong>
              {available
                ? voice.speaking
                  ? "Speaking"
                  : voice.processing
                    ? "Processing"
                    : "Standby"
                : "Unavailable"}
            </strong>
          </div>
          <div>
            <span>Measured input</span>
            {available ? (
              <>
                <meter
                  min="0"
                  max="1"
                  value={Math.max(0, Math.min(1, voice.input_level))}
                  aria-label="Measured microphone amplitude"
                />
                <small>{(voice.input_level * 100).toFixed(0)}%</small>
              </>
            ) : (
              <strong>Unavailable</strong>
            )}
          </div>
        </div>
        <div className="voice-action-buttons">
          <button disabled={!enabled("listen")} onClick={() => act("listen")}>
            Listen now
          </button>
          <button
            disabled={!enabled(voice?.muted ? "unmute" : "mute")}
            onClick={() => act(voice?.muted ? "unmute" : "mute")}
          >
            {voice?.muted ? "Unmute microphone" : "Mute microphone"}
          </button>
          <button
            disabled={!enabled("interrupt")}
            onClick={() => act("interrupt")}
          >
            Interrupt response
          </button>
        </div>
        {voice?.reason && <p className="feature-note">{voice.reason}</p>}
        {error && (
          <p className="feature-error" role="alert">
            {error}
          </p>
        )}
        {available && (
          <p className="feature-note">
            Speaking reports synthesis or playback activity. Input measures
            microphone amplitude.
          </p>
        )}
      </section>
      <div className="voice-detail-grid">
        <section className="voice-device-section">
          <h2>Microphone &amp; speaker</h2>
          {c.meta?.features.audio_devices ? (
            <AudioSettings
              key={c.deviceRevision}
              token={token}
              disabled={!token}
            />
          ) : (
            <p className="feature-empty">
              Audio device controls are unavailable in this session.
            </p>
          )}
        </section>
        <section className="voice-measurements">
          <h2>Observed timing</h2>
          <dl>
            {metrics.map(([key, label]) => (
              <div key={key}>
                <dt>{label}</dt>
                <dd>
                  {voice?.metrics?.[key] == null
                    ? "Not measured"
                    : `${voice.metrics[key]}${key === "audio_failures" ? "" : " ms"}`}
                </dd>
              </div>
            ))}
          </dl>
          <p className="feature-note">
            Observed timings only; unmeasured values do not imply a successful
            test.
          </p>
        </section>
      </div>
    </div>
  );
}

export function NotificationsPage({
  token,
  navigate,
}: {
  token: string;
  navigate: (screen: Screen) => void;
}) {
  const resource = usePrivateResource<NotificationData>(
    "/api/notifications",
    token,
    2500,
  );
  const [filter, setFilter] = useState("unread"),
    [category, setCategory] = useState("all"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [clear, setClear] = useState(false);
  const pending = useRef<{ signature: string; id: string } | null>(null);
  const data = resource.data;
  const writeBlocked =
    busy || !token || Boolean(resource.error) || !data?.available;
  async function execute(operation: string, payload: unknown) {
    if (writeBlocked) {
      setError("Reconnect and refresh notifications before changing them.");
      return false;
    }
    const signature = JSON.stringify([operation, payload]);
    if (pending.current?.signature !== signature)
      pending.current = { signature, id: crypto.randomUUID() };
    setBusy(true);
    setError("");
    try {
      await write("/api/notifications", token, {
        id: pending.current.id,
        operation,
        data: payload,
        confirmed: true,
      });
      pending.current = null;
      resource.refresh();
      return true;
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Notification action failed.",
      );
      return false;
    } finally {
      setBusy(false);
    }
  }
  const items = (data?.items || [])
    .filter(
      (item) =>
        (filter === "history" || !item.dismissed) &&
        (filter !== "unread" || !item.read) &&
        (category === "all" || item.category === category),
    )
    .sort((a, b) => a.category.localeCompare(b.category));
  return (
    <div className="awareness-page">
      <header className="screen-heading">
        <div>
          <h1>Notifications</h1>
          <p>Recorded events from this local workspace</p>
        </div>
        <button
          className="text-link"
          disabled={
            writeBlocked || !data?.items.some((item) => !item.dismissed)
          }
          onClick={() => {
            pending.current = null;
            setClear(true);
          }}
        >
          Clear all
        </button>
      </header>
      {resource.error && (
        <p className="feature-error" role="status">
          {resource.error}
        </p>
      )}
      {error && !clear && (
        <p className="feature-error" role="alert">
          {error}
        </p>
      )}
      <div className="feature-toolbar">
        <select
          aria-label="Notification state"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        >
          <option value="unread">Unread</option>
          <option value="all">All current</option>
          <option value="history">History</option>
        </select>
        <select
          aria-label="Notification category"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        >
          <option value="all">All categories</option>
          {Object.keys(data?.preferences.categories || {}).map((key) => (
            <option key={key} value={key}>
              {key}
            </option>
          ))}
        </select>
        <button className="text-link" onClick={resource.refresh}>
          Refresh notifications
        </button>
      </div>
      {!data ? (
        <div
          className="skeleton-group"
          role="status"
          aria-label="Loading notifications"
        >
          <span className="skeleton" />
        </div>
      ) : !data.available ? (
        <p className="feature-empty">
          {data.reason || "Notifications unavailable."}
        </p>
      ) : items.length ? (
        <div className="notification-list">
          {items.map((item, index) => (
            <div key={item.id} className="notification-group-item">
              {(index === 0 || items[index - 1].category !== item.category) && (
                <h2 className="notification-group-heading">
                  {item.category}{" "}
                  <span>
                    {
                      items.filter((row) => row.category === item.category)
                        .length
                    }
                  </span>
                </h2>
              )}
              <article
                className={`${item.read ? "read" : "unread"} ${item.priority}`}
              >
                <header>
                  <span>{item.category}</span>
                  <strong>{item.title}</strong>
                  <time>{new Date(item.created_at).toLocaleString()}</time>
                </header>
                <p>{item.message}</p>
                <div>
                  <button
                    className="text-link"
                    disabled={writeBlocked}
                    onClick={async () => {
                      if (
                        await execute("notification.read", {
                          notification_id: item.id,
                        })
                      ) {
                        const allowed = [
                          "home",
                          "chat",
                          "mission",
                          "models",
                          "cluster",
                          "settings",
                          "tasks",
                          "planner",
                          "projects",
                          "memory",
                          "agents",
                          "activity",
                          "calendar",
                          "voice",
                          "screen",
                          "notifications",
                          "workflows",
                        ];
                        if (
                          item.target.id &&
                          !storeInspection(item.target.screen, item.target.id)
                        ) {
                          setError(
                            "The related event target could not be retained. Open its screen directly.",
                          );
                          return;
                        }
                        if (allowed.includes(item.target.screen))
                          navigate(item.target.screen as Screen);
                      }
                    }}
                  >
                    Inspect event
                  </button>
                  {!item.read && (
                    <button
                      className="text-link"
                      disabled={writeBlocked}
                      onClick={() =>
                        execute("notification.read", {
                          notification_id: item.id,
                        })
                      }
                    >
                      Mark read
                    </button>
                  )}
                  {!item.dismissed && (
                    <button
                      className="text-link"
                      disabled={writeBlocked}
                      onClick={() =>
                        execute("notification.dismiss", {
                          notification_id: item.id,
                        })
                      }
                    >
                      Dismiss
                    </button>
                  )}
                </div>
              </article>
            </div>
          ))}
        </div>
      ) : (
        <p className="feature-empty">
          No notifications in this view. Only recorded events appear here.
        </p>
      )}
      <details className="notification-preferences">
        <summary>Notification preferences</summary>
        <p className="feature-note">
          Choose which categories are recorded. Windows alerts can be turned on
          or off from the HANNI system tray menu using Desktop notifications.
        </p>
        {Object.entries(data?.preferences.categories || {}).map(
          ([key, value]) => (
            <label key={key}>
              <input
                type="checkbox"
                checked={value}
                disabled={busy || !token || Boolean(resource.error)}
                onChange={(event) =>
                  execute("notification.preferences", {
                    categories: { [key]: event.target.checked },
                  })
                }
              />
              {key}
            </label>
          ),
        )}
      </details>
      <p className="feature-note">
        Inspect opens the related record. Review agent approvals in Tasks &amp;
        approvals; reading or dismissing a notification never approves an action.
      </p>
      {clear && (
        <FeatureDialog
          title="Clear current notifications?"
          busy={busy}
          onClose={() => setClear(false)}
        >
          <p className="confirmation-copy">
            Current notifications are marked read and dismissed. Their history
            remains available.
          </p>
          {error && (
            <p className="feature-error" role="alert">
              {error}
            </p>
          )}
          <div className="dialog-actions">
            <button autoFocus disabled={busy} onClick={() => setClear(false)}>
              Cancel
            </button>
            <button
              disabled={writeBlocked}
              onClick={async () => {
                if (await execute("notification.clear", {})) setClear(false);
              }}
            >
              Clear notifications
            </button>
          </div>
        </FeatureDialog>
      )}
    </div>
  );
}
