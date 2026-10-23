import { useEffect, useRef, useState } from "react";
import { useResource, write } from "./api";
import type { Chat, Contract, Telemetry } from "./types";
import { usePrivateResource, type VoiceData } from "./feature_types";
import {
  getMiniControls,
  readMiniWindowState,
  type MiniControls,
  type WindowState,
} from "./mini_bridge";
import "./mini.css";

declare global {
  interface Window {
    pywebview?: { api?: Partial<MiniControls> };
  }
}

export function Mini() {
  const chat = useResource<Chat>("/api/chat", 600);
  const telemetry = useResource<Telemetry>("/api/state", 500);
  const contract = useResource<Contract>("/api/workspace", 30000);
  const token = !chat.error ? chat.data?.token || "" : "";
  const voice = usePrivateResource<VoiceData>("/api/voice", token, 700);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [windowError, setWindowError] = useState("");
  const [voiceSending, setVoiceSending] = useState(false);
  const voicePending = useRef<{
    id: string;
    action: "listen" | "mute" | "unmute" | "interrupt";
  } | null>(null);
  const [native, setNative] = useState<WindowState | null>(null);
  const [preferences, setPreferences] = useState(false);
  const [selection, setSelection] = useState(0);
  const input = useRef<HTMLTextAreaElement>(null);
  const history = useRef<HTMLDivElement>(null);
  const results = useRef<HTMLElement>(null);
  const pending = useRef<{ id: string; message: string } | null>(null);
  const epoch = useRef<string | null>(null);
  const bridge = () => getMiniControls(window.pywebview?.api);
  const ready = Boolean(chat.data?.ready && !chat.error);
  const state = telemetry.data;
  const fresh = Boolean(
    state?.sampled_at &&
    !telemetry.error &&
    !state.error &&
    Date.now() / 1000 - state.sampled_at < 20,
  );
  const speaking = fresh && Boolean(state?.activity.speaking);
  const listening = fresh && Boolean(state?.activity.microphone_active);
  const working = Boolean(
    chat.data?.busy || (fresh && state?.interaction?.response_in_progress),
  );
  const voiceLabel = !fresh
    ? "Voice unavailable"
    : speaking
      ? "Speaking"
      : listening
        ? "Listening"
        : "Microphone idle";
  const commandMode = draft.startsWith("/");
  function voiceEnabled(action: "listen" | "mute" | "unmute" | "interrupt") {
    const enabled = voice.data?.actions[action];
    return Boolean(
      voice.data?.available &&
      !voice.error &&
      token &&
      !voiceSending &&
      (typeof enabled === "boolean" ? enabled : enabled?.enabled),
    );
  }
  async function controlVoice(
    action: "listen" | "mute" | "unmute" | "interrupt",
  ) {
    if (!voiceEnabled(action)) return;
    if (!voicePending.current || voicePending.current.action !== action)
      voicePending.current = { id: crypto.randomUUID(), action };
    setVoiceSending(true);
    setError("");
    try {
      await write("/api/voice", token, voicePending.current);
      voicePending.current = null;
      voice.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Voice action unavailable.");
      voice.refresh();
    } finally {
      setVoiceSending(false);
    }
  }
  const capabilities = (contract.data?.capabilities ?? [])
    .filter(
      (item) =>
        /file|app|open|search|directory|read|write|path/i.test(item.name) &&
        item.name.toLowerCase().includes(draft.slice(1).toLowerCase().trim()),
    )
    .slice(0, 6);

  useEffect(() => {
    async function refresh() {
      try {
        const state = await readMiniWindowState(window.pywebview?.api);
        if (!state) return;
        setNative(state);
        setWindowError("");
      } catch {
        setWindowError("Window controls are unavailable. Try reopening Mini.");
      }
    }
    const timer = setInterval(refresh, 2000);
    window.addEventListener("pywebviewready", refresh);
    refresh();
    input.current?.focus();
    return () => {
      clearInterval(timer);
      window.removeEventListener("pywebviewready", refresh);
    };
  }, []);
  useEffect(() => {
    setSelection(0);
  }, [draft]);
  useEffect(() => {
    if (commandMode && !preferences)
      results.current
        ?.querySelector(".selected")
        ?.scrollIntoView({ block: "nearest" });
  }, [selection, commandMode, preferences, capabilities.length]);
  useEffect(() => {
    if (
      chat.data?.epoch &&
      epoch.current &&
      epoch.current !== chat.data.epoch
    ) {
      pending.current = null;
      voicePending.current = null;
    }
    if (chat.data?.epoch) epoch.current = chat.data.epoch;
    if (history.current)
      history.current.scrollTop = history.current.scrollHeight;
  }, [chat.data?.epoch, chat.data?.messages.length]);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setPreferences(false);
        bridge()?.dismiss();
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [preferences]);

  async function controls(action: () => Promise<WindowState | boolean>) {
    try {
      const result = await action();
      if (typeof result !== "boolean") setNative(result);
      setWindowError("");
    } catch {
      setWindowError("Window controls are unavailable. Try reopening Mini.");
    }
  }
  function prepare(name: string) {
    setDraft(`Help me use ${name}: `);
    input.current?.focus();
  }
  async function submit() {
    const message = draft.trim();
    if (!message || !ready || sending || commandMode) return;
    if (!pending.current || pending.current.message !== message)
      pending.current = { id: crypto.randomUUID(), message };
    setSending(true);
    setError("");
    try {
      await write("/api/chat", chat.data!.token, pending.current);
      setDraft((value) => (value.trim() === message ? "" : value));
      pending.current = null;
      chat.refresh();
    } catch (e) {
      setError(
        `${e instanceof Error ? e.message : "Message could not be sent."} Your draft is saved here. Check the conversation before retrying.`,
      );
      chat.refresh();
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mini-shell">
      <header className="mini-header">
        <span className="mini-identity pywebview-drag-region">
          <strong>h.</strong> HANNI Mini
        </span>
        <span className="mini-drag pywebview-drag-region" aria-hidden="true" />
        <button
          disabled={!native}
          aria-pressed={native?.pinned ?? false}
          onClick={() =>
            bridge() && controls(() => bridge()!.pin(!native?.pinned))
          }
          title="Keep Mini above other windows"
        >
          {native?.pinned ? "Pinned" : "Pin"}
        </button>
        <button
          disabled={!native}
          onClick={() => bridge() && controls(() => bridge()!.expand())}
          title="Open this conversation in HANNI OS"
        >
          Expand
        </button>
        <button
          className="mini-dismiss"
          disabled={!native}
          onClick={() => bridge()?.dismiss()}
          aria-label="Dismiss Mini"
        >
          ×
        </button>
      </header>
      <div className="mini-status">
        <span>
          {ready ? (working ? "Working" : "Ready") : "Assistant offline"}
        </span>
        <span className="mini-voice">
          <span className="mini-meter" aria-hidden="true">
            <i
              style={{
                width: `${fresh && listening ? Math.max(0, Math.min(100, (state?.activity.input_level ?? 0) * 100)) : 0}%`,
              }}
            />
          </span>
          {voiceLabel}
        </span>
        <button
          onClick={() => setPreferences(!preferences)}
          aria-expanded={preferences}
        >
          Shortcut
        </button>
      </div>
      <div className="mini-voice-actions" aria-label="Voice controls">
        <button
          disabled={!voiceEnabled("listen")}
          onClick={() => controlVoice("listen")}
          title="Listen using the existing voice session"
        >
          Listen
        </button>
        <button
          disabled={!voiceEnabled(voice.data?.muted ? "unmute" : "mute")}
          onClick={() => controlVoice(voice.data?.muted ? "unmute" : "mute")}
        >
          {voice.data?.muted ? "Unmute" : "Mute"}
        </button>
        <button
          disabled={!voiceEnabled("interrupt")}
          onClick={() => controlVoice("interrupt")}
          title="Interrupt speech through the existing voice session"
        >
          Stop speech
        </button>
        <span>
          {voice.error
            ? "Voice controls unavailable"
            : voice.data?.available
              ? voice.data.state
              : "Voice session not active"}
        </span>
      </div>
      {preferences ? (
        <section className="mini-preferences" aria-label="Mini preferences">
          <label>
            Global shortcut
            <select
              disabled={!native}
              value={native?.shortcut ?? ""}
              onChange={(event) =>
                bridge() &&
                controls(() => bridge()!.configure_hotkey(event.target.value))
              }
            >
              <option value="" disabled>
                Choose shortcut
              </option>
              {native?.choices.map((choice) => (
                <option key={choice}>{choice}</option>
              ))}
            </select>
          </label>
          <p>
            {native?.error ||
              "Press the shortcut from any application. Escape dismisses Mini. Pin keeps this window above other windows."}
          </p>
          {!native && (
            <p>
              Global shortcuts and window controls are available in the Windows
              desktop application.
            </p>
          )}
        </section>
      ) : commandMode ? null : (
        <div
          className="mini-history"
          ref={history}
          role="log"
          aria-label="Shared conversation"
          aria-live="polite"
        >
          {chat.data?.messages.length ? (
            chat.data.messages.slice(-12).map((message) => (
              <article
                className={`mini-message ${message.role === "user" ? "from-user" : ""}`}
                key={message.id}
              >
                <div>
                  {message.role === "user"
                    ? "You"
                    : message.role === "assistant"
                      ? "HANNI"
                      : message.role}
                  <span>
                    {message.status === "complete" ? "" : message.status}
                  </span>
                </div>
                <p>{message.content}</p>
              </article>
            ))
          ) : (
            <div className="mini-empty">
              <strong>What’s on your mind?</strong>
              <p>
                Ask HANNI, or type / to find registered file and app tools. Your
                conversation is shared with the full workspace.
              </p>
              {!ready && (
                <p>
                  The assistant is offline. Start it from the desktop
                  Application menu.
                </p>
              )}
            </div>
          )}
        </div>
      )}
      {commandMode && !preferences && (
        <section
          className="mini-capabilities"
          ref={results}
          aria-label="Registered file and app tools"
        >
          <div>
            Prepare a request <small>Existing permissions apply</small>
          </div>
          {capabilities.length ? (
            capabilities.map((item, index) => (
              <button
                key={item.name}
                className={index === selection ? "selected" : ""}
                onClick={() => prepare(item.name)}
              >
                <span>{item.name.replaceAll("_", " ")}</span>
                <small>Permission level {item.permission_level}</small>
              </button>
            ))
          ) : (
            <p>
              {contract.error
                ? "Tool discovery unavailable."
                : "No matching registered file or app tools."}
            </p>
          )}
        </section>
      )}
      {(error || chat.error) && (
        <p className="mini-error" role="alert">
          {error || chat.error}
        </p>
      )}
      {windowError && (
        <p className="mini-error" role="alert">
          {windowError}
        </p>
      )}
      <form
        className="mini-composer"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <textarea
          data-mini-input
          ref={input}
          aria-label="Message HANNI"
          value={draft}
          maxLength={4000}
          rows={2}
          placeholder="Ask HANNI, or / for tools"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.nativeEvent.isComposing) return;
            if (
              commandMode &&
              capabilities.length &&
              ["ArrowDown", "ArrowUp"].includes(event.key)
            ) {
              event.preventDefault();
              setSelection(
                (value) =>
                  (value +
                    (event.key === "ArrowDown" ? 1 : capabilities.length - 1)) %
                  capabilities.length,
              );
            } else if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              commandMode && capabilities.length
                ? prepare(
                    capabilities[Math.min(selection, capabilities.length - 1)]
                      .name,
                  )
                : submit();
            }
          }}
        />
        <button
          type="submit"
          disabled={!ready || sending || !draft.trim() || commandMode}
        >
          {sending ? "Sending" : "Send"}
        </button>
      </form>
      <footer className="mini-footer">
        <span>Enter to send · Shift+Enter for a new line</span>
        <span>{native?.shortcut ?? "Windows desktop"}</span>
      </footer>
    </div>
  );
}
