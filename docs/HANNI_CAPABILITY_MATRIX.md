# H.A.N.N.I. Capability Matrix

Current registry snapshot. Capability metadata is available through `hanni capabilities` and `hanni capability-get NAME`.

- Registered capabilities: **172**
- Read-only capabilities: **103**
- Google setup, scope requirements and confirmation limits: [Google integration](GOOGLE.md).

Execution still passes argument validation, permission checks, confirmation, emergency stop and audit. Registration does not grant the assistant permission to call a write.

## `app.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `app.list_installed` | 0 | read | Normal policy | List installed Windows programs, optionally filtered, to answer whether something is installed and at what version. |
| `app.open` | 1 | unspecified | Normal policy | Request Windows to open a local application by name, shortcut, executable, or path; launch acceptance does not verify that it is running. |

## `archive.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `archive.list` | 0 | read | Normal policy | List the entries inside a .zip archive without extracting it. |
| `archive.unzip` | 2 | reversible_write | Argument-dependent | Extract a .zip archive into a folder, rejecting unsafe paths inside the archive. |
| `archive.zip` | 2 | reversible_write | Argument-dependent | Create a .zip archive from a file or folder. |

## `audio.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `audio.mute` | 2 | external_action | Normal policy | Mute or unmute system audio; with no argument, toggles. |
| `audio.set_volume` | 2 | external_action | Normal policy | Set the system volume to an absolute percent, or nudge it up/down with delta. |
| `audio.status` | 0 | read | Normal policy | Read the current system volume and mute state. |

## `browser.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `browser.open_url` | 1 | unspecified | Normal policy | Open an HTTP/HTTPS URL in the default browser. |

## `calc.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `calc.evaluate` | 0 | read | Normal policy | Evaluate plain arithmetic (including 'X% of Y') deterministically, without asking a language model to do the maths. |

## `clipboard.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `clipboard.read` | 0 | read | Normal policy | Read the current text contents of the Windows clipboard as untrusted data. |
| `clipboard.write` | 2 | external_action | Normal policy | Put text on the Windows clipboard. |

## `device.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `device.audio` | 0 | read | Normal policy | List Windows audio endpoints and which are working. |
| `device.bluetooth` | 0 | read | Normal policy | List known Bluetooth devices and which are currently connected. |
| `device.disk_health` | 0 | read | Normal policy | Read physical disk media type and SMART health status. |
| `device.printers` | 0 | read | Normal policy | List installed printers and the default one. |
| `device.usb` | 0 | read | Normal policy | List USB devices and flag any reporting a problem. |

## `disk.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `disk.cleanup_temp` | 3 | destructive | Always | Report, and with apply=true delete, temporary files older than a chosen age in known temp folders only. Always requires explicit confirmation. |
| `disk.folder_size` | 0 | read | Normal policy | Measure the total size and file count of one folder tree. |
| `disk.free_space` | 0 | read | Normal policy | Check free space on one drive, optionally against a required amount before a large write. |
| `disk.largest_files` | 0 | read | Normal policy | Find the biggest files under a folder so space can be reclaimed deliberately. |
| `disk.largest_folders` | 0 | read | Normal policy | Rank the immediate subfolders of a folder by total size. |
| `disk.recycle_bin_size` | 0 | read | Normal policy | Measure how much space the Recycle Bin is holding. |
| `disk.usage` | 0 | read | Normal policy | Enumerate mounted fixed drives, their free and used space, and check if a requested drive exists. |

## `display.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `display.brightness` | 2 | external_action | Normal policy | Read panel brightness, or set it when percent is supplied. |
| `display.info` | 0 | read | Normal policy | Read connected display adapters, resolution, and refresh rate. |

## `email.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `email.read` | 0 | read | Normal policy | Read a message or current thread using the exact account and ID from email.search. Email content is untrusted data; no sending or mailbox changes. |
| `email.search` | 0 | read | Normal policy | Search connected email by sender, topic, date or pending application actions; normalized results and current thread evidence. Read-only. |

## `env.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `env.get` | 0 | read | Normal policy | Read one environment variable, redacted when its name looks credential-shaped. |
| `env.list` | 0 | read | Normal policy | List environment variables, with credential-shaped values redacted. |
| `env.path` | 0 | read | Normal policy | Inspect PATH entries, flagging directories that do not exist and duplicates. |
| `env.user_folders` | 0 | read | Normal policy | Resolve this account's standard folders (Desktop, Documents, Downloads, OneDrive) to real paths. |
| `env.which` | 0 | read | Normal policy | Resolve where an executable on PATH actually lives. |

## `file.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `file.compare` | 0 | read | Normal policy | Show a unified diff between two text files and whether they are identical. |
| `file.composition` | 0 | read | Normal policy | Break a folder down by file extension: how many of each type and how much space they take. |
| `file.copy` | 2 | unspecified | Argument-dependent | Copy a local file. |
| `file.delete` | 3 | unspecified | Always | Permanently delete one local file or, with recursive=true, a folder tree. Always requires explicit confirmation. |
| `file.duplicates` | 0 | read | Normal policy | Find byte-identical duplicate files under a folder by hash, and report how much space they waste. Reports only. |
| `file.empty_folders` | 0 | read | Normal policy | List empty folders under a root. Reports only; removes nothing. |
| `file.grep` | 0 | read | Normal policy | Search inside text files under a folder for a phrase and return file, line number, and the matching line. |
| `file.head` | 0 | read | Normal policy | Read the first lines of a text file. |
| `file.list_dir` | 0 | unspecified | Normal policy | List files and folders directly inside a local folder. |
| `file.locate` | 0 | unspecified | Normal policy | Locate an exact file/folder basename. With no root, checks common user locations (Downloads, Desktop, Documents, current working directory) without guessing; with root, searches recursively under it. |
| `file.mkdir` | 2 | unspecified | Argument-dependent | Create a local folder, including missing parent folders. |
| `file.move` | 2 | unspecified | Argument-dependent | Move or rename a local file or folder. |
| `file.open` | 1 | external_action | Normal policy | Open an existing file or folder with its default Windows application. |
| `file.read` | 0 | unspecified | Normal policy | Read an ordinary local text file. |
| `file.recent` | 0 | read | Normal policy | List files changed recently under a folder, newest first. |
| `file.search` | 0 | unspecified | Normal policy | Search filenames in Downloads, Documents and Desktop by default, or recursively under an explicit folder. Excludes dependency and credential paths. |
| `file.stat` | 0 | unspecified | Normal policy | Check whether a path exists and its type; optionally hash file bytes for verification. |
| `file.tail` | 0 | read | Normal policy | Read the last lines of a text file, for logs and long output. |
| `file.write` | 2 | unspecified | Argument-dependent | Create or replace a local text file. |

## `folder.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `folder.open` | 1 | external_action | Normal policy | Open an existing project directory in Windows File Explorer; never execute a file. |

## `git.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `git.branches` | 0 | read | Normal policy | List local and remote branches and identify the checked-out branch. |
| `git.diff` | 0 | read | Normal policy | Read the staged or unstaged diff of a local git repository, as a stat summary or full patch. |
| `git.log` | 0 | read | Normal policy | Read recent commits from a local git repository. |
| `git.status` | 0 | read | Normal policy | Read the branch, staged/unstaged changes, and untracked files of a local git repository. |

## `gmail.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `gmail.read` | 0 | read | Normal policy | Read one email body using its exact ID and named account from search; never sends or marks read. |
| `gmail.search` | 0 | read | Normal policy | Search mail in the default or explicitly selected Google account. Use all only for an explicit cross-account request. Returns IDs/snippets; partial errors are explicit. |

## `google.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `google.accounts` | 0 | read | Normal policy | List named Google account connections without a network request. |
| `google.calendar.availability` | 0 | read | Normal policy | Read Google events from the default or explicitly selected account. Use all only for an explicit cross-account request. UTC ordering, local display; read-only. |
| `google.calendar.create` | 2 | external_action | Normal policy | Create one Google Calendar event after HANNI resolves the owner's natural-language date/time to exact local values. |
| `google.calendar.delete` | 3 | destructive | Always | Delete one verified Google Calendar event ID after confirmation. |
| `google.calendar.events` | 0 | read | Normal policy | Read Google events from the default or explicitly selected account. Use all only for an explicit cross-account request. UTC ordering, local display; read-only. |
| `google.calendar.list_calendars` | 0 | read | Normal policy | List accessible Google calendar IDs for one named account. |
| `google.calendar.next` | 0 | read | Normal policy | Read next future Google event with owner-local current time and minutes until start; compare available minutes with requested duration. Report partial failures. |
| `google.calendar.read` | 0 | read | Normal policy | Read one exact Google Calendar event ID from prior results. |
| `google.calendar.update` | 2 | external_action | Argument-dependent | Update one verified Google Calendar event ID after confirmation. |
| `google.docs.read` | 0 | read | Normal policy | Read native Google Docs text using an exact Drive file ID or a uniquely matched search phrase. Multiple matches require selection. |
| `google.drive.list` | 0 | read | Normal policy | List Google Drive files, newest modified first; metadata only. |
| `google.drive.metadata` | 0 | read | Normal policy | Read metadata and web URL for an exact Google Drive file ID from prior results. |
| `google.drive.recent` | 0 | read | Normal policy | List recently modified Google Drive files or Google Docs; metadata only. |
| `google.drive.search` | 0 | read | Normal policy | Search Google Drive file names and indexed text; return metadata without downloading content. |
| `google.gmail.read` | 0 | read | Normal policy | Read one email body using its exact ID and named account from search; never sends or marks read. |
| `google.gmail.recent` | 0 | read | Normal policy | Read recent Gmail sender, subject and received-time metadata; no message body. |
| `google.gmail.search` | 0 | read | Normal policy | Search Gmail and return sender, subject and received-time metadata; no message body. |
| `google.gmail.thread` | 0 | read | Normal policy | Read messages in an exact verified Gmail thread ID. |
| `google.tasks.complete` | 2 | external_action | Argument-dependent | Mark a verified Google task ID complete after confirmation. |
| `google.tasks.create` | 2 | external_action | Normal policy | Create one explicitly requested Google task. |
| `google.tasks.list` | 0 | read | Normal policy | List incomplete Google Tasks in one task list; separate from local HANNI todos. |

## `google_calendar.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `google_calendar.agenda` | 0 | read | Normal policy | Read Google events from the default or explicitly selected account. Use all only for an explicit cross-account request. UTC ordering, local display; read-only. |
| `google_calendar.create` | 2 | external_action | Normal policy | Create one Google Calendar event after HANNI resolves the owner's natural-language date/time to exact local values. |
| `google_calendar.list` | 0 | read | Normal policy | List accessible Google calendar IDs for one named account. |
| `google_calendar.next` | 0 | read | Normal policy | Read next future Google event with owner-local current time and minutes until start; compare available minutes with requested duration. Report partial failures. |

## `gpu.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `gpu.memory` | 0 | read | Normal policy | Report per-GPU VRAM used and free, for deciding whether another model can be loaded. |
| `gpu.top_processes` | 0 | unspecified | Normal policy | Show the processes using the most GPU/VRAM right now. |

## `hanni.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `hanni.audit_tail` | 0 | read | Normal policy | Read recent entries from H.A.N.N.I.'s own tool audit log, optionally only failures or one capability. |
| `hanni.capabilities` | 0 | read | Normal policy | List H.A.N.N.I.'s own registered capabilities, or rank the ones relevant to a stated goal. Answers 'what can you do' and 'which tool would you use'. |
| `hanni.permissions` | 0 | read | Normal policy | Report the permission profile boundaries H.A.N.N.I. enforces outside the model. |
| `hanni.stop_state` | 0 | read | Normal policy | Report whether the deterministic emergency stop is currently active. |

## `id.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `id.generate` | 0 | read | Normal policy | Generate a UUID or random hex/url-safe identifier. |

## `media.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `media.next_track` | 1 | external_action | Normal policy | Skip to the next track. |
| `media.play_pause` | 1 | external_action | Normal policy | Send the play/pause media key to whatever is playing. |
| `media.previous_track` | 1 | external_action | Normal policy | Go back to the previous track. |
| `media.stop` | 1 | external_action | Normal policy | Send the stop media key. |

## `model.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `model.status` | 0 | read | Normal policy | Read HANNI's active model and endpoint health with no arguments. Report GPU placement only when HANNI owns the launch and verified offload; an external server's adapter is unknown. |

## `net.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `net.dns_lookup` | 1 | external_action | Normal policy | Resolve a hostname to IP addresses and report resolution time. |
| `net.info` | 0 | read | Normal policy | Read local network adapters, link state, and this machine's private IP addresses. Answers 'am I online' and 'what is my IP'. |
| `net.ping` | 1 | external_action | Normal policy | Measure round-trip latency and packet loss to one host. |
| `net.ports` | 0 | read | Normal policy | List local listening TCP/UDP sockets and the processes holding them. |
| `net.throughput` | 0 | read | Normal policy | Sample actual bytes in/out on this machine over a few seconds to estimate current network throughput. |
| `net.wifi` | 0 | read | Normal policy | Read the current Wi-Fi SSID, signal strength, band, and link rates. |

## `note.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `note.append` | 2 | reversible_write | Normal policy | Append an owner-dictated note to today's plain Markdown note file. Refuses credential-shaped text. |
| `note.days` | 0 | read | Normal policy | List which days have notes and how many, to orient a search. |
| `note.list` | 0 | read | Normal policy | List the notes recorded on a given day (today by default). |
| `note.search` | 0 | read | Normal policy | Search every note file for a phrase, newest day first. |

## `notify.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `notify.toast` | 1 | external_action | Normal policy | Show a desktop notification on this machine. |

## `power.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `power.battery_detail` | 0 | read | Normal policy | Read battery percentage, charging state, and estimated time remaining. |
| `power.battery_report` | 2 | reversible_write | Normal policy | Generate the Windows battery health report to a chosen .html file. |
| `power.idle_settings` | 0 | read | Normal policy | Read how long before the screen turns off and the machine sleeps on AC power. |
| `power.plans` | 0 | read | Normal policy | Read active Windows power plan. Built-in Power saver may limit performance; a plan alone does not prove the cause of slowness. |
| `power.set_idle` | 2 | external_action | Normal policy | Set the AC-power screen-off or sleep timeout in minutes (0 means never). |
| `power.set_plan` | 2 | external_action | Normal policy | Switch the active Windows power plan by GUID or name. |

## `powershell.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `powershell.run` | 2 | unspecified | Argument-dependent | Run a local non-elevated PowerShell command and capture stdout/stderr. |

## `process.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `process.find` | 0 | read | Normal policy | Find running processes by name and report PID, memory, and how long each has run. |
| `process.inspect` | 0 | unspecified | Normal policy | Check whether an exact PID still exists. |
| `process.list` | 0 | unspecified | Normal policy | List local processes sorted by memory usage. |
| `process.stop` | 2 | unspecified | Normal policy | Stop a local non-protected process by PID. |
| `process.top_cpu` | 0 | unspecified | Normal policy | Show the applications using the most CPU right now. |
| `process.top_disk_io` | 0 | unspecified | Normal policy | Rank current process read/write I/O rates. Useful when files or apps load slowly, or disk activity seems high; this does not measure disk health or free space. |
| `process.top_memory` | 0 | unspecified | Normal policy | Show the applications using the most RAM right now. |
| `process.uptime` | 0 | read | Normal policy | Report how long a named process or PID has been running. |

## `project.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `project.format` | 2 | reversible_write | Argument-dependent | Check black formatting for a project, or with apply=true reformat files in place. |
| `project.lint` | 2 | external_action | Normal policy | Run ruff or flake8 over a project folder and report whether it is clean. |
| `project.test` | 2 | external_action | Normal policy | Verify a Python project using pytest (runner=pytest) or run a .py program and compare exact expected_stdout (runner=script). Executes project code and returns real exit status. |

## `python.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `python.env_info` | 0 | read | Normal policy | Report the active Python interpreter, whether it is a virtual environment, and installed packages. |

## `random.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `random.number` | 0 | read | Normal policy | Generate a random whole number in a range. |
| `random.pick` | 0 | read | Normal policy | Choose fairly at random between options the owner supplies. |

## `schedule.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `schedule.list_tasks` | 0 | read | Normal policy | List Windows Scheduled Tasks and their state. |

## `security.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `security.bitlocker` | 0 | read | Normal policy | Read BitLocker volume encryption status. Recovery keys are never read. |
| `security.defender` | 0 | read | Normal policy | Read Microsoft Defender real-time protection state and signature freshness. |
| `security.firewall` | 0 | read | Normal policy | Read whether each Windows Firewall profile is enabled and its default inbound action. |
| `security.pending_reboot` | 0 | read | Normal policy | Report whether Windows is waiting on a restart to finish servicing or updates. |
| `security.updates` | 0 | read | Normal policy | List recently installed Windows updates and hotfixes. |

## `service.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `service.control` | 3 | external_action | Always | Start, stop, or restart one non-protected Windows service. Always requires explicit confirmation. |
| `service.list` | 0 | read | Normal policy | List Windows services with running state and start type. |

## `spotify.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `spotify.focus` | 1 | external_action | Normal policy | Bring the Spotify window to the foreground. |
| `spotify.launch` | 1 | external_action | Normal policy | Open the Spotify desktop client if it is not already running. |
| `spotify.next` | 1 | external_action | Normal policy | Skip to the next Spotify track and report what started. |
| `spotify.open_uri` | 1 | external_action | Normal policy | Open an exact spotify: URI (track, album, playlist, artist, show, episode) in the local client. |
| `spotify.play_pause` | 1 | external_action | Normal policy | Toggle Spotify playback once: playing becomes paused and paused becomes playing. Read spotify.status first when the current state is unknown; this does not select a song. |
| `spotify.previous` | 1 | external_action | Normal policy | Go back to the previous Spotify track and report what started. |
| `spotify.search` | 1 | external_action | Normal policy | Open a Spotify search for a plain-text query in the desktop client. Does not start playback by itself. |
| `spotify.status` | 0 | read | Normal policy | Read what the local Spotify client is playing right now, from its own window title. |
| `spotify.volume` | 2 | external_action | Normal policy | Read or set Spotify's own application volume, separate from system volume. |

## `startup.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `startup.list` | 0 | read | Normal policy | List the programs configured to launch when Windows starts. |

## `system.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `system.battery` | 0 | unspecified | Normal policy | Read the laptop battery percentage and charging state. |
| `system.event_errors` | 0 | read | Normal policy | Read recent error and critical entries from the Windows System or Application event log. |
| `system.os_info` | 0 | read | Normal policy | Read the Windows edition, build, CPU count, hostname, and Python version. |
| `system.performance` | 0 | read | Normal policy | Current CPU/RAM, storage capacity, battery and top-memory snapshot. Healthy here does not rule out disk I/O, GPU load, or a power-plan limit. |
| `system.stats` | 0 | unspecified | Normal policy | Read local CPU, RAM and GPU usage/temperature for available adapters. Backend-dependent GPU readings may be unavailable; this is not per-process memory. |
| `system.uptime` | 0 | read | Normal policy | Report how long this machine has been running since boot. |

## `text.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `text.hash` | 0 | read | Normal policy | Compute a sha256/sha512/sha1/md5 digest of a string, for comparing or fingerprinting content. |
| `text.normalize` | 0 | read | Normal policy | Reshape a string: slug, upper, lower, title case, accent stripping, or whitespace collapse. |
| `text.stats` | 0 | read | Normal policy | Count words, characters, sentences, and estimated reading time for a block of text. |

## `time.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `time.convert` | 0 | read | Normal policy | Convert a time between IANA timezones. |
| `time.elapsed` | 0 | read | Normal policy | Report how long ago (or how far ahead) an ISO timestamp is. |
| `time.now` | 0 | read | Normal policy | Read the OS clock. Omit timezone for local time; accepts IANA zones or Eastern/Central/Mountain/Pacific. kind=date with day_offset=1 resolves tomorrow, -1 yesterday. |

## `timer.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `timer.set` | 1 | external_action | Normal policy | Set a short ephemeral timer that raises a desktop notification when it fires. |

## `todo.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `todo.add` | 2 | reversible_write | Normal policy | Save a named assignment or task with its due date locally; exact duplicates return the existing ID. No Google sync. |
| `todo.complete` | 2 | reversible_write | Normal policy | Mark one task completed by its exact ID; read back with todo.get. |
| `todo.due` | 0 | read | Normal policy | List open tasks due in the next N calendar days, including overdue work. |
| `todo.get` | 0 | read | Normal policy | Read back one local task by exact ID to verify its saved fields. |
| `todo.list` | 0 | read | Normal policy | List saved tasks, optionally by course and status; defaults to open. |

## `ui.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `ui.active_window` | 0 | unspecified | Normal policy | Read the current foreground Windows window title and process. |
| `ui.close_window` | 2 | external_action | Argument-dependent | Politely close windows matching a title substring with WM_CLOSE, never a forced process kill. |
| `ui.focus_window` | 1 | unspecified | Normal policy | Focus a visible window by title substring. |
| `ui.list_windows` | 0 | unspecified | Normal policy | List visible top-level Windows windows. |
| `ui.minimize_all` | 1 | external_action | Normal policy | Minimize every visible window to show the desktop. |
| `ui.window_state` | 1 | external_action | Normal policy | Minimize, restore, or maximize windows whose title contains a substring. |
| `ui.windows_detailed` | 0 | read | Normal policy | List visible windows with their owning process, PID, and minimized state. |

## `unit.*`

| Capability | Risk level | Side effect | Confirmation | Description |
| --- | --- | --- | --- | --- |
| `unit.convert` | 0 | read | Normal policy | Convert between units of length, mass, data, time, speed, or temperature. |
