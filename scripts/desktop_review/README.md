# Independent desktop review tools

These tools are verification code, not an alternative application or backend.
`fixture.py` runs the existing loopback DashboardServer with synthetic telemetry,
an in-memory ChatHub, and injected fake power/terminal/settings handlers. It does
not start voice, models, SSH collectors, or actual machine-control commands.

After the desktop executable is built, run:

```powershell
.\.venv\Scripts\python.exe scripts/desktop_review/capture_native.py --exe <path-to-HANNI-exe> --output data/hanni-desktop-review/iteration-1
```

The executable must support the documented fixture URL, attach-only, state-dir,
debug-port, and title flags. The harness attaches Playwright to the real WebView2
process solely to navigate and interact. Screenshots come from the actual
Windows window frame via PIL ImageGrab, including native titlebar controls.

The interactive Windows desktop must be at least 1920 x 1112 to accommodate the
largest window. The harness does not change system display scaling. It records
the actual system DPI and framed window dimensions in `capture-results.json`.
Required render sizes are 1920 x 1080, 1440 x 900, 1366 x 768, and 900 x 650.
Screenshots may contain personal cluster addresses and stay in ignored local
data. The review report must explicitly disclose synthetic fixtures.

The harness deliberately never grades images. The independent verifier must
open actual generated images and write justified scores with screenshot
references. A passed capture script does not mean visual acceptance. Tray
behavior, window persistence, real telemetry, production packaging, and backend
regression results require additional recorded checks.

`check_lifecycle.py --exe <path-to-HANNI-exe>` independently tests the packaged
window's maximize/minimize/restore, native menu/tray preferences, close-to-tray,
minimize-to-tray, tray restore and Exit desktop, resized geometry persistence,
attached-backend survival, missing-token rejection, lack of a privileged native
Javascript API, and blocked foreign loopback navigation/popups. It clicks actual
Windows tray-menu item bounds and records observations in
`data/hanni-desktop-review/lifecycle/results.json`. Its screenshots use actual
Win32 image capture. No production backend or machine-control operation runs.

The review process terminates only the native process it launched. The attached
fixture server is shut down by its context manager; no existing HANNI process is
stopped. Do not point the fixture workflow at a real model/voice launch command.

`capture_phase.py --exe <path> --output <ignored-directory> --screen home=.screen-home`
accepts repeated route/visible-selector pairs for the complete current screen
matrix. It captures all four physical sizes and records artifact hashes. List
every primary screen explicitly; capture success does not assign visual scores.

`check_mini.py --exe <path> --output <ignored-directory>` drives a real secondary
Mini and genuine global accelerators while a separate benign native Tk process
is foreground. It checks focus, Escape, actual always-on-top, narrow window-only
bridge, shared ChatHub transport/expansion, live RegisterHotKey conflict and
alternative, missing-token rejection, blocked foreign navigation/popups, and
offline draft retention. The reply is explicitly synthetic; actual controller
routing and voice timing need separate evidence. These new harnesses must wait
for a coordinated frozen build and GUI GO; packaging cannot overlap review.

Phase 2 `capture_phase.py` and `check_mini.py` accept `--workspace-fixture`.
`phase_fixture.py` preserves original private API/token/registry/store gates;
seeded task/project/note/link/memory content is synthetic but CRUD and audits are
real isolated operations. It explicitly uses an empty GoogleAccess offline
vault, because a temporary data directory alone does not isolate Windows
Credential Manager. Voice is unbound/inactive; no microphone opens. Private
route responses and writes are never mocked.

`check_workspace.py --exe <path> --output <ignored-directory>` performs genuine
native create/edit/complete/reopen/delete, stale-draft rejection, UUID dedupe,
exact memory deletion, notification target/read/dismiss/preferences/clear,
fresh store reopen and actual executable restart checks. `--reminder-boundary`
adds 100 actual gated due tasks to the seeded due task, then verifies all 101
reminders and repeat dedupe in the real API and native center. Run only with
exclusive GUI ownership; it never executes a real file, model, voice, provider
or remote machine action. OS balloon delivery remains separate from center
interaction acceptance.

`contact_frames.py <capture-directory>` arranges the four already captured
physical-size screenshots per route for inspection. These are viewing aids;
the individual actual framed screenshots and provenance remain authoritative.
The verifier must score using the user's exact **2/2/2/2/1/1** categories in
`docs/desktop-reviews/rubric-correction.md`, not equal custom weights or source
inspection. Historical wrong-rubric numbers remain transparently superseded.
