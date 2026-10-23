# Browser chat and conversation history

Restart `START_HANNI.cmd -SkipInstall`, open the URL printed by the new launcher,
and choose **Conversation** in the navigation. Enter sends a message; Shift+Enter adds a line.
Browser messages do not need a wake word and their replies stay silent in chat.
Normal accepted voice commands and HANNI's replies appear there too. Ignored
background speech and microphone recordings are not added to chat history.

The same assistant session handles browser, microphone and terminal requests.
Its existing date/calendar routing, tools, memory, confirmation and emergency
stop gates apply. A browser message waits for the current foreground turn and
voice playback to finish. Requests are consumed by the original CLI loop, not
executed concurrently in HTTP threads. Browser confirmations use ordinary chat
messages such as `yes` after HANNI asks for an exact action's confirmation.
`/stop`, `/status` and `/resume` provide the existing owner safety controls.
Use **Stop HANNI** in the voice dock or Settings to exit the dashboard session.
The current response finishes, then HANNI closes its chat, telemetry, and owned
model server before the dashboard disconnects. Ctrl+C in the launcher terminal
also exits. A model server started outside this launcher remains running.

## Microphone and speaker

Open **Settings**, choose a microphone and speech output under **Microphone & speaker**,
then click **Apply audio devices**. **Refresh devices** updates the device lists
after connecting or disconnecting hardware. The microphone list comes from
Windows audio capture devices; the speaker list contains outputs available to
Windows speech. **System / configured default** and **Windows default output**
restore automatic selection. HANNI stores the choices in
`data/audio-routing.json` (under `HANNI_DATA_DIR` if set). Restart the HANNI
voice session after applying a choice; the current microphone and playback
streams keep their existing routing until then. If a saved device disappears,
the panel reports it so you can choose another.

### Discord voice call through VB-Audio Cable

For HANNI to hear and speak in a Discord call, select **Desktop audio (Windows
default output)** as HANNI's microphone and **CABLE Input (VB-Audio Virtual
Cable)** as its speaker. Restart HANNI after applying the choices. In Discord's
**Voice & Video** settings, set **Output Device** to the same physical speaker
that Windows uses as its default output, and set **Input Device** to **CABLE
Output (VB-Audio Virtual Cable)**. Discord's input test should move when HANNI
speaks; HANNI's dashboard audio meter should move when someone in the call
speaks. The desktop loopback hears all audio played on the default speaker,
including other apps.

HANNI's current voice interface treats anyone who can speak into its input as
the owner. Use a call with people you trust; they can wake HANNI and request
the same tools you can. HANNI cannot distinguish call participants by voice.

For browser chat without microphone capture, start:

```powershell
.\START_HANNI.cmd -SkipInstall -Text
```

Keep the terminal open. `-DashboardOnly` remains a monitor; its composer is
disabled because no assistant session is running. The composer also stays
disabled while models and the session start, and displays connection failures.

## History

By default, messages are saved only on this PC in
`data/dashboard-chat.sqlite3` (under `HANNI_DATA_DIR` if overridden). Page reloads
and later sessions can display them. Use **Load earlier messages** for older
entries and **Clear saved history** to erase the display archive. Clearing is
blocked while a request is queued or running. It does not undo computer actions,
erase explicitly saved memories, or reset the current conversation's short-term
context. Display history is not automatically replayed into the model: existing
memory rules and the 120-second conversational context boundary still apply.

For session-only history, put this in `.env` and restart:

```dotenv
HANNI_CHAT_HISTORY=session
```

Session-only mode does not erase a pre-existing saved archive. The archive,
runtime databases, credentials and audio remain excluded from source exports
and Git. Old terminal output from before this feature is not imported.

## Reliability and access

The service remains bound to `127.0.0.1`. Chat writes require a matching browser
origin, validated Host, per-launch request token, JSON body and bounded input.
There is no arbitrary tool/command execution endpoint. Submitted IDs are
deduplicated so a retry after a dropped HTTP response does not repeat an action.
The inbox holds at most eight waiting messages. Pending requests are never
replayed on restart; incomplete entries are marked interrupted when a new
assistant session takes ownership. History is rendered as plain text, including
any HTML-like text returned by a model or a tool.

Tests cover persistence, duplicate suppression, history paging/clear, request
validation, cross-origin rejection, and browser messages entering the voice loop
without a wake word or TTS. The browser smoke test exercises actual HTTP posts,
reply rendering, voice history, reload, clear, safe text rendering, mobile layout
and audio activity/telemetry behavior using a labeled assistant fixture.

Validation: 777 tests and 30 subtests passed. The browser smoke test passed with
no JavaScript errors, and wheel/source distribution contents were checked.

## HANNI OS desktop workspace

The current interface has Home, Conversation, Mission Control, Cluster and Settings in a
compact native Windows shell with one navigation sidebar. Context is an optional
overlay; the compact voice strip expands for details. `Ctrl+K`
opens workspace search; it searches screens, capability names and loaded history.

Read [the verified integration map](HANNI_OS.md) for current contracts, unavailable
features, build instructions and browser checks. Tool approvals continue through
the existing conversation and controller. The UI's clear-history and shutdown
dialogs only confirm those existing operations.

Restart the launcher once to load the new read-only metadata, activity and cluster routes,
then refresh the page. Subsequent frontend-only changes need a page refresh.
Loading, empty-history, unavailable-assistant and disconnected states are explicit.
A lost connection disables sending and retains the draft and loaded history.
The audio visual reflects measured input; output audio levels are not available.
Cluster rows show all nine members, availability, CPU/RAM percentages, small
histories and uptime. Search/filter/sort controls open selected-node detail
graphs and measured busiest processes. Samples still arrive every second through
the owner's existing persistent Tailscale/SSH connections. Yunjin remains under
repair with monitoring paused.
Sleep and Reboot buttons use existing SSH power permissions and an explicit
per-node confirmation. Unsupported, offline/stale and repair nodes are disabled.
Power requests respect Safe Mode and are deduplicated; unknown outcomes are
shown without automatic retries.
Each node's detail view also has an SSH Terminal button that opens Windows Terminal or a
PowerShell fallback with the member's configured SSH username. Existing Tailscale
SSH is used where available. This remains available for troubleshooting missing
telemetry; Yunjin is disabled while her address is unconfigured. Login takes place
in the native window, which remains open if HANNI stops. Terminal launch respects
Safe Mode, shutdown and the same origin/token checks as other writes.
