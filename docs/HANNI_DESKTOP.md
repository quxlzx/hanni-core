# HANNI OS desktop

HANNI OS now runs in a native Windows application window using the installed
Microsoft Edge WebView2 runtime. It includes one compact navigation sidebar,
eighteen screens across Assistant, Workspace and Mission Control, HANNI Mini,
and a small expandable voice status footer. The assistant controller, voice loop, approvals, model
runtime, and cluster collector remain the original HANNI services.

The sidebar has three areas. **Assistant** contains Home, Conversation, and
Voice. **Workspace** contains Planner, Tasks, Calendar, Projects, Memory, and Workflows.
**Mission** contains Mission Control, Models, Agents, Cluster, Activity, and
Screen awareness. Settings and Notifications remain available in the footer.
Selecting an area expands its routes; opening a screen also selects its area.
Settings includes the MCP Hub. Workflows shows private persisted goals, plan and
action reviews, execution controls, checkpoints and verified outputs. See
[workflow setup and limits](WORKFLOWS_V3.md).
The Models screen reads actual residency and configuration. It does not invent
model switching controls that the backend does not provide.

Cluster Reboot uses the requested `systemctl -i reboot` through the existing
SSH authorization, with password-backed sudo stored in Windows Credential Manager
when needed. The confirmation describes the blocker override. See
[reboot setup and verification](CLUSTER_REBOOT_FIX.md), including the current
Tailscale fresh-sign-in requirement and how to replace a node's password securely.

## HANNI Mini

Press **Ctrl+Shift+Space** from another application, or choose **Open HANNI Mini**
in the Application or tray menu. Mini is a separate floating WebView2 window,
sharing the full workspace's conversation and existing chat controller. Enter
sends a message, Shift+Enter adds a line, and Escape hides Mini. **Expand** opens
the shared conversation in the full workspace. Hiding Mini does not stop HANNI.

**Pin** keeps Mini above other windows. The Shortcut menu offers four supported
global shortcuts. If another application owns a shortcut, HANNI keeps the
previous working shortcut and shows the conflict; the tray menu remains usable.
Windows `RegisterHotKey` handles only the selected accelerator, without a
keyboard hook or key recording. Closing the desktop releases its registration.
Pin and shortcut choices persist with the other native window preferences.

Type `/` to discover registered file and app capabilities. Selecting a capability
prepares a message for the original controller; permissions and confirmations
still apply there. Mini shows actual microphone, speaking, and response state.
Opening Mini does not start the model, activate a microphone, or perform a tool
action. An offline assistant leaves the message draft available.

Mini's Listen, Mute/Unmute, and Stop speech buttons use the authenticated voice
API for the existing running voice session. Availability comes from that
session's registered callbacks. A dashboard-only monitor, or a session started
before voice controls were added, shows unavailable controls. Opening Mini
never starts voice capture; Listen requires an explicit click.

The secondary window exposes five native methods: window state, dismiss, pin,
expand, and supported shortcut configuration. These methods accept no command,
file path, tool name, or arbitrary JavaScript. They reject calls outside the
exact local Mini URL. The primary workspace exposes no native bridge. Both
WebViews reject foreign navigation, popups, and requests before dispatch.

## Desktop notifications

Enable **Desktop notifications** in the tray menu to receive native notifications
when Windows supports them. Delivery reads the same protected notification
history as the Notifications screen. Initial history is not replayed. New
unread events respect category preferences, are deduplicated, and are limited
to three deliveries per minute; critical events receive priority within each
poll. Native messages contain the already-redacted event title only, never
conversation content, event details, or an approval action. Disabling and
reenabling delivery does not replay older notifications.

Use the Notifications screen to inspect the recorded event, follow its related
screen, mark it read, dismiss it, or manage category preferences. Any related
permission or approval still belongs to the existing controller.

Project conversation links open the exact saved message. The workspace loads a
bounded history page if needed and checks the conversation epoch before merging
it. Deleted or unavailable messages show a clear explanation. File links prepare
requests for existing tools instead of introducing native file execution.

Native implementation references: [Windows RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey),
[pywebview window API](https://pywebview.flowrl.com/api/), and
[WebView2 request interception](https://learn.microsoft.com/en-us/microsoft-edge/webview2/how-to/webresourcerequested).

## Launch

- `START_HANNI_OS.cmd` opens the desktop workspace. If HANNI is already running
  on the selected loopback port, it attaches after checking the workspace contract.
  If the port is free and the repository's `.venv` is present, it starts only a
  local dashboard monitor. This does not start a model or microphone.
- `START_HANNI.cmd` starts the existing assistant session and its desktop window.
  Keep its foreground terminal open for permissions and voice controls.
- **Application → Start Assistant** (also in the tray menu) explicitly starts
  the existing foreground launcher. If the desktop owns a monitor, it first
  stops only that monitor. It does not duplicate an already attached session.
- `START_HANNI.cmd -NoBrowser` is the existing terminal-only launch option.
  `scripts\start_dashboard.ps1` can still be invoked directly for browser use.
- For workflow execution without voice capture or terminal input, start
  `.\.venv\Scripts\python.exe -m hanni.dashboard.launcher --workflow-only --no-browser`,
  then attach the desktop from another terminal with `START_HANNI_OS.cmd -AttachOnly`. The backend uses
  the original controller and configured model; an attached window can close
  while it keeps running. A dashboard-only monitor shows saved workflow history
  and controller availability.

The built executable is `dist\HANNI OS\HANNI OS.exe`. Keep its `_internal` folder
beside it. It is a portable application directory, not a browser shortcut. It
can be launched directly, pinned to Start or the taskbar, or used through the
included commands. No installer or administrator access is required. The package
is unsigned; Windows may identify it as an application from an unknown publisher.

From outside the repository, pass its location explicitly:

```powershell
& 'C:\path\HANNI OS\HANNI OS.exe' --repo-root 'C:\Projects\HANNI_NEGATIVE_SIGNALS_LLM_FINAL_ROUTING'
```

To attach to a different already-running session:

```powershell
& '.\dist\HANNI OS\HANNI OS.exe' --url http://127.0.0.1:8765 --attach-only
```

Only HTTP loopback root URLs with an explicit port are accepted. The native
window does not allow navigation to remote pages, file URLs, or popup windows.
An occupied port belonging to an unverified service is never replaced or used.

## Window, tray, and lifecycle

The standard Windows caption provides resize, maximize, minimize, taskbar, and
Alt+Tab behavior. The manifest requests Per Monitor V2 DPI awareness. The native
caption and application icon keep the `h.` identity. **Application → Exit desktop**
always closes the desktop.

The tray menu supports **Open HANNI OS**, **Start Assistant**, **Close to tray**,
**Minimize to tray**, **Desktop notifications**, and **Exit desktop**. Both tray
preferences are off by default. Notifications are optional and use the Windows
system tray notification facility when available. They report local connection
changes; they do not send remote telemetry.

Closing the desktop leaves an attached assistant or externally managed backend
running. The desktop stops only a dashboard-only process it launched itself,
using the existing shutdown API and then cleaning up its owned process if needed.
Its ownership handshake checks the launched process PID (or the Windows Python
redirector's one-hop parent PID), actual bound loopback origin, and ChatHub epoch.
The per-launch token is kept only in memory. A service that replaces the original
monitor never receives its own token in a shutdown request.

**Stop HANNI** in the interface remains the existing explicit controller shutdown
action and confirmation. It is different from closing the desktop window.

Window dimensions, position, maximized state, tray choices, and notifications
are saved locally in `%LOCALAPPDATA%\HANNI OS\window.json`. Browser preferences
and UI state are stored in `%LOCALAPPDATA%\HANNI OS\webview`. These files do not
contain SSH keys or request tokens. Native connection diagnostics are in
`desktop.log`; owned dashboard output is in `monitor.log`. A single native window
uses that profile at a time. Existing conversation data remains in HANNI's
configured data directory.

## Develop and build

The repository's Python environment and Node frontend tooling must already be
set up. Desktop dependencies are pinned in `desktop\requirements.txt` and install
into the separate ignored `build\desktop-venv` environment. The native client
does not import or package the speech stack, model files, GGUF weights, or private
configuration. Normal application use needs no Internet connection.

```powershell
# Production frontend and portable Windows executable.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build_desktop.ps1

# Native development window against the normal loopback service.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start_desktop.ps1 -Dev -AttachOnly

# Existing frontend and backend checks.
npm run check --prefix frontend
npm run build --prefix frontend
.\.venv\Scripts\python.exe -m pytest
```

`build_desktop.ps1 -SkipInstall -SkipFrontend` rebuilds only the already prepared
native wrapper. Close the desktop before rebuilding its portable directory;
the separate assistant session can remain running. The build refuses to replace
files used by a running packaged client. Rebuild the frontend whenever React or CSS files change because
the desktop loads the compiled bundle served by the existing backend.

The icon is a repository-native geometric `h.` asset built by
`desktop\create_icon.py`. PyInstaller uses `desktop\HANNI OS.spec`, the explicit
DPI manifest, version information, and the isolated dependency environment.
Copy the whole portable directory when distributing the client. Runtime backend
and model configuration still come from the existing HANNI repository.

## Why WebView2 instead of Tauri 2

Tauri 2 was assessed first, but this Windows environment has no Rust toolchain or
MSVC compiler on its executable path. Adopting it would add a second native build
stack and sidecar packaging work around the already functioning Python lifecycle.
pywebview uses the installed WebView2 runtime and normal Windows window controls;
PyInstaller produces the real executable directly from a small isolated client.
This preserves the existing same-origin API without adding a privileged JavaScript
bridge or weakening Host, Origin, request-token, loopback, or controller checks.
The tradeoff is a larger portable directory than a minimal Tauri client and a
dependency on the installed WebView2 runtime.

The implementation follows the primary documentation for
[pywebview's native API](https://pywebview.flowrl.com/api/),
[its PyInstaller packaging guidance](https://pywebview.flowrl.com/guide/freezing.html),
and [pystray's Windows tray and notifications](https://pystray.readthedocs.io/en/latest/usage.html).

## Independent verification

The native review harness accepts a packaged executable, attaches it only to an
isolated synthetic local server, interacts through a local WebView2 debug port,
and captures the actual framed Win32 window. It does not start a live assistant,
microphone, model, SSH terminal, or node power action. The optional `--debug-port`
flag is solely for local verification; normal launches do not expose that port.
Review evidence and independently assigned scores are recorded separately in
`docs\desktop-reviews` and `data\hanni-desktop-review`.

The original five-screen release's historical review is retained in
[its verification report](HANNI_DESKTOP_FINAL_VERIFICATION.md). Current Phase 1 +
Phase 2 results use the user's exact weighted rubric and distinguish visual
acceptance from functional limitations. See
[current verification](HANNI_PHASE12_FINAL_VERIFICATION.md),
[actual before/after screenshots](desktop-reviews/phase12-before-after.md), and
[checkpoint history](HANNI_PHASE12_CHECKPOINTS.md). Screen analysis remains
blocked by the missing capture/vision pipeline; live acoustic voice verification
remains partial. Neither limitation is concealed by an unavailable status screen.
