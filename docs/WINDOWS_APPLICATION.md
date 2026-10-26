# HANNI Windows application

Run `SETUP_HANNI.cmd` once, then open **HANNI OS** from your Desktop or Start menu. `START_HANNI.cmd` and `START_HANNI_OS.cmd` open the same application. Setup builds `dist/HANNI OS/HANNI OS.exe` and creates shortcuts for the current Windows user. Keep the application folder and repository in place; the app uses the repository’s Python environment, model files, and persistent state.

The Windows application uses WebView2 to display HANNI’s existing dark interface in its own window. It starts the current native agent, scheduler, model, and interface in the background when they are not running. No browser tab or permissions terminal is required. Internal loopback endpoints remain available for the agent and UI to communicate. The app attaches to a verified existing HANNI session without starting another model or taking ownership of that session.

## Bundled inference engine

Windows x64 desktop builds include llama.cpp under `_internal/runtimes/llama.cpp`, including the CPU and Vulkan server/benchmark executables, backend DLLs, app-local Microsoft C++ runtime DLLs, upstream license, and an integrity manifest. The build also creates `dist/HANNI-OS-Windows-x64.zip` for sharing. Extract it and keep the entire `HANNI OS` application directory together. The desktop passes its own runtime location to the backend, so moving the application folder does not require adding llama.cpp to PATH or installing it with WinGet. Startup prefers a usable GPU and falls back to CPU/system RAM; Q8 K/V cache settings remain enforced.

`scripts/build_desktop.ps1` prepares the engine automatically before packaging. Downloads are pinned by release, size and SHA-256 in `desktop/llama-runtime.lock.json`. A failed checksum, unsafe archive, missing dependency, or failed executable check stops the build. To prepare only the engine, run `.venv/Scripts/python.exe scripts/prepare_llama_runtime.py --verify`. Verified downloads and the build cache can be reused offline with `scripts/build_desktop.ps1 -OfflineLlamaRuntime`. Setup's existing `-SkipLlamaInstall` option now selects this verified offline mode rather than installing a system-wide copy.

Windows x64 setup obtains checksum-pinned Microsoft C++ DLLs from Microsoft's redistributable, unpacks them with Windows' built-in cabinet utility, and places them beside the inference executable. The installer/MSIs are never run: no administrator elevation, system DLL installation or machine-wide registry change is needed. Builders must have redistribution rights under their Microsoft Software License Terms; see [Microsoft's deployment guidance](https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files). A CPU runtime check must pass; missing Vulkan drivers produce a CPU-fallback warning rather than failing setup.

The engine bundle does not include GGUF model weights, your accounts, saved conversations, or other private state. `SETUP_HANNI.cmd` installs the repository's Python backend and downloads the small MiniCPM 2B starter model when needed, saving a 64K launch configuration. Existing local models and API selections are retained. Python 3.12+ and WebView2 are still required by this application version.

## Automatic setup and Windows sign-in

For a GitHub source ZIP, use File Explorer's **Extract All** before running setup. Choose a permanent folder such as `C:\HANNI`, open the extracted repository folder, and run `SETUP_HANNI.cmd` alongside `scripts`, `src`, and `pyproject.toml`. Double-clicking the command inside the ZIP can extract only that file into a temporary preview, leaving its PowerShell script unavailable. An incomplete copy now stops with extraction instructions before invoking PowerShell.

Run the updated `SETUP_HANNI.cmd` once on each PC. Setup prepares the runtime, validates a runnable CPU server and benchmark, prepares a local model, launches HANNI and waits for the assistant to report ready. It then installs Desktop/Start menu shortcuts and a **current-user Startup folder** shortcut, using the full executable path, repository argument and working directory. This needs no administrator account or scheduled task. HANNI-owned shortcuts from older installations are updated to this installation, including copied shortcuts with stale targets; shortcuts owned by another application are retained.

An already-open desktop is reused while its model/runtime are repaired. If it is disconnected and has no running backend, setup starts an assistant owned by that desktop's lifetime and waits for reconnection. First launch can also prepare a missing runtime automatically. Engine selection tests both `llama-server` and `llama-bench`, and failures include the executable/Windows exit code instead of only “No runnable binary.”

Setup records `%LOCALAPPDATA%/HANNI OS/setup.log`; desktop/model startup logs are in that same app folder and the repository's `state` directory. If a work laptop still blocks the verified CPU executable, use the specific error with IT. Setup does not bypass application control, download restrictions, or Windows startup settings disabled by your organization.

Optional setup switches: `-NoStartup` skips creating a sign-in entry, `-NoLaunch` prepares without launching, `-SkipDesktop` prepares the backend only, and `-Offline` requires already-cached runtime/model files (Python dependencies must also be available). Models already chosen by the owner are preserved. Keep the repository/application in place after setup; removing or moving it can break shortcuts.

To update the engine, review a new official release, update both archive checksums and the matching license checksum in the lock file, then rebuild and verify CPU/GPU startup. Existing development `binaries` folders and PATH/WinGet installs remain compatibility fallbacks, after the app-local runtime.

The saved model/provider selection is retained. First startup can take a few minutes while a local model loads or is benchmarked. If startup fails, right-click the HANNI OS tray icon and choose **Start Assistant** to retry. Desktop and assistant startup logs are under `%LOCALAPPDATA%/HANNI OS`; model and agent logs remain in the repository.

Each agent task receives the detected execution OS and workspace, including scheduled runs and delegated tasks. Local instructions use Windows paths and PowerShell syntax. The agent's `local_terminal` tool launches executables directly rather than opening a shell; file tools and Python handle filesystem work. Explicit remote Linux targets retain their own command syntax. Windows command arguments preserve backslashes and quoted paths.

## Notifications and background operation

Press **F11** to toggle fullscreen and **Escape** to leave it. The system tray menu also has **Fullscreen (F11)**. Leaving fullscreen restores your previous window size or maximized state; fullscreen does not replace your saved window geometry.

Select **Notifications** in the sidebar to see unread alerts, inspect the related task, mark an alert read, dismiss it, or view history. The unread count updates automatically. Native task completion, scheduled task results, pending action approvals, failures, and existing reminders use the same durable notification center. Inspecting or dismissing an alert never approves a tool action.

Right-click the **HANNI OS** system tray icon for:

- **Open HANNI OS** and **Notifications**.
- **Desktop notifications**, which controls Windows alerts independently of recording notifications in the app.
- **Send test notification** to check Windows delivery when desktop notifications are enabled.
- **Listening mode notifications**, a separate voice status preference.
- **Close to tray** and **Minimize to tray**.
- **Exit desktop**, which ends the app and services it owns.

Close to tray and desktop notifications default to enabled for new installations; saved preferences are preserved. The window can be closed while work continues in the tray. Use **Exit desktop** to stop it completely. If HANNI was already running before the app attached, exiting the app leaves that independently launched session running.

Windows alerts show event titles, rather than private prompts, document contents, or task output. Alerts are deduplicated and limited to three per minute. Windows notification settings or Do Not Disturb can suppress their display. The in-app notification history remains available. Category recording preferences are in **Notifications → Notification preferences**; muted events are not replayed when a category is re-enabled.

## Building and troubleshooting

For an optional personal tab inside Microsoft Teams on the same PC, see [Microsoft Teams setup](MICROSOFT_TEAMS.md). The Teams tab reuses the running assistant and its notifications inbox; Windows alerts remain available through this desktop app.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_desktop.ps1
```

The build uses an isolated `build/desktop-venv` environment. `-SkipFrontend` uses the already-built UI assets; `-NoShortcuts` builds without installing shortcuts. `scripts/install_desktop_shortcuts.ps1` can recreate shortcuts after the build. On an existing backend-only setup, first launching `START_HANNI.cmd` builds the missing desktop client automatically. Microsoft Edge WebView2 Runtime is required.

`scripts/start_desktop.ps1 -Dev` runs the source client using the desktop environment. `-AttachOnly` connects without starting services. `-Url http://127.0.0.1:PORT` selects another loopback instance. `START_BRAIN.cmd` retains the explicit terminal/browser workflow for development and portable headless use. The app does not change API keys, models, Office/MCP connections, memories, conversations, or recurring schedules.
