# HANNI OS desktop redesign checkpoints

All checkpoints are local. Nothing is published or pushed. Screenshots and
machine-generated evaluation evidence are under ignored `data/hanni-desktop-review/`.
Existing user data, model weights and unrelated evaluation/training files are excluded.

## Checkpoint 0: audited baseline

- Backend: 744 passed, 2 skipped, 17 subtests passed (47.19 seconds).
- Frontend: TypeScript check and production build passed.
- Browser: all five screens at 12 widths passed, no JavaScript, CSP or external HTTP errors.
- Routing: 1,131 cases, 1,129 strict passes (99.82%), average 99.59/100.
  Existing failures: Downloads-folder routing and Spotify play exposure. They are
  unchanged and outside this visual/desktop work.
- Independent baseline screenshots: `data/hanni-desktop-review/iteration-0/`.
  Baseline review is browser-only and cannot satisfy desktop acceptance.
- Production HANNI remains stopped. Test servers are temporary and isolated;
  no microphone/model session, real power request or SSH terminal launch is tested.

Exactly three actual Codex subagents are assigned:

| Agent | Ownership |
| --- | --- |
| Worker 1 | `workspace.tsx`, `style.css`, shared visual system, native desktop wrapper, build/launch files and desktop tests |
| Worker 2 | `cluster.tsx`, `cluster.css`, extracted `screens.tsx` and screen-specific styles |
| Verifier | Independent screenshot capture, rubric scores, review reports; no application implementation |
| Main | Coordination, browser harness adaptation, integration documentation, local checkpoints, final regressions |

Frontend requests retain the existing documented endpoints and token, origin,
Host, redaction and UUID safeguards. The App retains chat/history/draft and
controller handlers; screen extraction changes presentation only. Cluster
collection, power/terminal services and model/voice/routing logic are preserved.

Native framework decision: Tauri 2 was assessed first; this machine has neither
Rust/Cargo nor MSVC available. WebView2 is installed and Python 3.12 is available.
Use pywebview/WebView2 with PyInstaller as the lower-risk delivery path. Native
dependencies are isolated from the backend/model environment. The window loads
the existing loopback origin directly; no alternate tool execution bridge is added.
Closing a client must preserve a live assistant session. Explicit assistant
startup continues through the existing foreground confirmation terminal.

## Checkpoint 1: implementation and first native review

- Actual portable Windows client built with WebView2/PyInstaller; approximately
  36.2 MiB for the directory, no model weights or credentials bundled.
- One compact sidebar, extracted screens, searchable/filterable/sortable nine-node
  overview and selected-node details; existing controller-backed controls retained.
- Backend regression: 786 passed, 2 skipped, 17 subtests passed (49.26 seconds).
- Frontend check/build and five-screen browser checks at 12 widths passed.
  Updated source-export/distribution checks: 5 passed.
- Routing decisions, scores, failures and summary match the 1,131-case baseline.
  Eight unasserted email-plan start/end timestamps vary with current time; expected
  answers and benchmark files were not changed.
- A hash comparison of 144 existing backend Python files finds only `launcher.py`
  changed. Its narrow seams are `--desktop` (actual bound URL to client) and
  dashboard-only `--ready-file` (nonsecret PID/parent PID/origin/epoch ownership).
  No server security policy, controller, routing, model, voice or collector changes.
- Independent native review: Home 8.3, Conversation 8.5, Mission Control 8.3,
  Cluster 8.4, Settings 8.1; mean 8.32, AI-template mean 1.46. **FAIL**.
  Evidence: [iteration 1 report](desktop-reviews/iteration-1.md), 27 framed
  Windows captures at 1920x1080, 1440x900, 1366x768 and 900x650. Actual display
  scaling is 125% (120 DPI); initial virtualized captures were rejected.
- Next corrections: short-window information density, cluster details, compact
  home/settings/composer, clipped conversation idle mark and palette double scrolling.
  Updated dark native menu/debug setup must be independently recaptured.
- An external/user-started HANNI session appeared on port 8765 after baseline.
  It was not started, stopped or used for writes by the team. Tests remain isolated.
- Real telemetry and native tray/close/persistence checks are still pending.

## Checkpoint 2: revisions and final native acceptance

- Independent review of 27 actual native frames at the same four sizes and
  125% Windows scaling: Home 8.7, Conversation 8.8, Mission Control 8.7,
  Cluster 9.0, Settings 8.7. Overall **8.78**, AI-template **1.14**. **PASS**.
  All nine nodes fit at 1366x768; no critical visual or interaction defects remain.
  See [iteration 2 report](desktop-reviews/iteration-2.md).
- Short-window density, node details, settings actions, palette scrolling,
  conversation idle branding and native dark-menu behavior corrected.
- Native lifecycle/security: nine independent checks passed, including actual
  tray interaction, window persistence, attached-backend survival and blocked
  foreign navigation. Two deterministic startup-cancellation tests added.
- Backend regression: **788 passed, 2 skipped, 17 subtests passed** (48.81s).
  An earlier run hit WinError 10053 in the unchanged Laya-shadow unauthorized-POST
  test; the focused retry and full suite passed without application or test edits.
- Frontend check/build and all five screens at 12 browser widths passed;
  no JavaScript, CSP or external HTTP errors. Routing results remain unchanged.
- Real packaged-client telemetry check passed against an isolated dashboard-only
  monitor: local CPU/RAM and all eight active nodes rendered actual percentages;
  Yunjin remained unprobed under repair. Captures wait for rendered DOM readings,
  rather than relying on API samples alone. Client close stopped its owned monitor.
  The external model PID set was unchanged; no model/voice or node action launched.
- The final executable and frontend artifact hashes remained unchanged throughout
  the independent review. Backend baseline comparison still finds only the
  documented launcher integration changed among 144 existing Python files.
- Optional native notification delivery and a new live voice/model session were
  not exercised. They are not claimed as verified.
- This completed cycle receives a local Git checkpoint. No publication or push.

Final package, evidence, launch directions and validation scope:
[final verification](HANNI_DESKTOP_FINAL_VERIFICATION.md).
