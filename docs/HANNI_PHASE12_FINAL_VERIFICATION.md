# HANNI OS Phase 1 + Phase 2 verification

Follow-up: the later owner-requested [cluster reboot fix](CLUSTER_REBOOT_FIX.md)
changes power authorization and confirmation copy. Scores, source manifests and
hashes in this report describe the accepted Phase 1/2 checkpoint `4a0a1ec` before
that fix; they are not a new visual review of the follow-up source.

Date: 2026-10-09. This is the current implementation and continuation record.
The source and portable native Windows application are saved locally. No remote
push or publication was performed. The complete roadmap is **not complete**:
actual screen analysis is blocked and live acoustic voice verification is partial.

Exactly three real Codex subagents were used: Worker 1 owned the desktop shell,
shared components and Mini; Worker 2 owned feature screens; the independent
Verifier captured the executable and rejected failed cycles. The coordinator
owned backend adapters, integration, preservation checks and final live proofs.

## Milestone status

| Milestone | Status | Verified scope and limits |
| --- | --- | --- |
| 1.1 Desktop redesign | PASS | Real WebView2 executable, sixteen routes, tray, window preferences, lifecycle and existing-controller connection |
| 1.2 HANNI Mini | PASS | Genuine global shortcut/refocus, pin, Escape, five restricted native methods, same ChatHub, actual configured-model RAM query and shared expanded reply |
| 1.3 Cluster v2 | PASS | Nine-member roster, compact searchable/sortable table, details/history/stale status; actual live SSH CPU/RAM for all eight active nodes; Yunjin under repair and unprobed |
| 2.1 Agent activity | PASS | Actual existing controller/capabilities/redacted audit and permission decisions; unsupported cancellation remains read-only as allowed by the brief |
| 2.2 Personal workspace | PASS | Genuine persistent tasks/projects/notes/links, exact edits/deletes, original memory search/forget, calendar cache/local deadlines, actual executable restart |
| 2.3 Screen awareness | BLOCKED | Honest privacy/status UI; no registered capture or vision pipeline exists to analyze a screen or supply authorized visual conversation context |
| 2.4 Voice experience | PARTIAL | Bound existing-session state/control adapter, actual input amplitude, device settings and audio regressions; real spoken wake/transcription/TTS/barge-in and acoustic timings unverified |
| 2.5 Notifications | PASS | Actual event-linked persistent center, exact task/execution inspection, preferences/read/dismiss/clear, all 101 due reminders with stable deduplication; optional Windows balloon appearance unverified |

Workspace PASS refers to the requested persistence acceptance criterion and
supported local flows. Connected-provider calendar read/write, controller-mediated
memory correction/addition and linked-file execution were not live verified.
These prepare requests for the original controller and retain its permissions.
No independent autonomous-agent runtime, live approval queue or universal cancel
API is invented. Missing measurements and capabilities are explicitly unavailable.

## Visual acceptance

Final Mini screenshot assessment is recorded in
[cycle 3](desktop-reviews/phase-2-cycle-3.md). The sixteen unchanged main layouts
retain their individually inspected [cycle 2](desktop-reviews/phase-2-cycle-2.md)
frames and exact weighted scores. Final visual acceptance **PASS: 8.69/10**
(unrounded 8.6882), every surface at least **8.6**, Mini **8.7**, AI-template
appearance **1.2/10**. Cycle 2 was rejected despite its 8.66 mean because Mini's
persistent raw bridge-startup error scored 8.3. The repaired package passed the
fresh fifteen-check native Mini run; all fifteen fresh Mini/state frames were
independently opened. No source-estimated score is used.

The required weights are Typography/hierarchy 2, Layout/density 2,
Spacing/consistency 2, Professional identity 2, Desktop integration 1 and
Interaction quality 1. The previous equal-weight custom assessments are
superseded by [the disclosed rubric correction](desktop-reviews/rubric-correction.md).

All sixteen main routes were captured and independently inspected at 1920 by
1080, 1440 by 900, 1366 by 768 and 900 by 650 physical pixels. Mini was separately
captured at four compact sizes. Observed Windows scaling was 125%, not 150%.
The minimum request of 640 by 480 was correctly constrained to 800 by 600 physical
pixels; actual header/content/footer/Stop HANNI remained visible. Small windows
use normal outer scrolling. See [actual before/after PNGs](desktop-reviews/phase12-before-after.md).

## Tests and real application evidence

| Check | Result |
| --- | --- |
| Baseline Python suite | 788 passed, 2 skipped, 17 subtests |
| Final backend/Python suite | 860 passed, 2 skipped, 17 subtests; 57.95s |
| Frontend type check and production build | PASS; rebuilt again after the bounded Mini readiness repair |
| Mini partial native-API injection regressions | 2 passed; absent/incomplete methods are not called, real native failure can recover |
| Native tests after Mini repair | 53 passed |
| Original browser regression harness | All 24 checks PASS across twelve widths, 320 through 1920; no JS/CSP/external-request errors |
| Genuine native workspace integration | 59/59 PASS; actual protected writes, stale-draft retention, exact UUIDs, restart persistence and 101 reminders |
| Native lifecycle/security | 10/10 PASS; tray, geometry, minimize/maximize/restore, same-origin guards and ownership-preserving close |
| Final native Mini | 15/15 PASS; initial clean state plus original fourteen native-control/transport checks |
| Final real configured-model/controller | 6/6 PASS; original local model, actual process-memory tool, one submitted message, same expanded answer and owned cleanup |
| Final real local/cluster telemetry | 7/7 PASS; actual native CPU/RAM readings for all eight active nodes and repair-state exclusion |
| Existing routing benchmark | 1,131 cases; 1,129 strict passes (99.82%), average 99.59; unchanged baseline failures |

The full Python suite predates only the final frontend Mini readiness patch; no
Python application source changed afterward. Its native tests, type/build and
fresh actual Mini/controller/telemetry checks cover that final change. Testing
does not stand in for missing live voice or screen-analysis evidence.

The genuine workspace run covers private GET rejection, stale editor retention,
same UUID/different-payload rejection, completion/reopen/delete with Cancel and
confirmation, original MemoryStore exact forget, notes/project links, exact
notification task/audit navigation, no notification feedback loop, preferences,
Clear confirmation, disconnected Save retaining the draft, and actual app restart.
One seeded due task and 100 registry-gated task creates produced all 101 reminders;
repeat reads preserved the same IDs.

The real controller proof used the original launcher with the configured cached
local model. Mini asked what was using RAM, executed only the existing read-only
`process.top_memory`, displayed a real model reply and expanded the same reply
into Conversation. Closing an attached app preserved its controller. The original
shutdown then cleaned only that isolated controller/model; external model PID
sets were unchanged. No microphone or speech playback was started by this test.

The final telemetry proof used an isolated dashboard-only owned monitor and the
unchanged fixed SSH/Tailscale collector. Hanni, Wonyoung, Haerin, Chaewon, Minju,
Wonhee, Jeongyeon and Karina all returned actual resource samples rendered as
native percentages. Yunjin has the requested jellyfish and maintenance state,
with no probe or fabricated measurement. The owned monitor shut down gracefully;
external model processes were preserved. No power button or terminal was invoked.

Machine-readable evidence remains locally under:

- `data/hanni-desktop-review/phase2-primary-cycle2/`: all 64 main native frames.
- `data/hanni-desktop-review/phase2-workspace-cycle2/`: genuine persistence/action evidence and results.
- `data/hanni-desktop-review/phase2-lifecycle-cycle2/`: ten actual lifecycle checks and minimum frame.
- `data/hanni-desktop-review/phase2-mini-cycle3/`: final Mini frames, checks and artifact hashes.
- `data/hanni-phase12-review/live-controller-final/`: six actual checks and two native reply frames.
- `data/hanni-phase12-review/live-telemetry-final/`: seven actual checks and two live telemetry frames.
- `data/hanni-phase12-review/browser-final/`: original browser regression results.
- `data/hanni-phase12-review/`: baseline/final routing, coverage and backend-source manifests.

Verifier fixtures disclose synthetic chat/telemetry/provider/device data and an
inactive voice session, while CRUD uses genuine stores and registry/HTTP gates.
The separate live model/telemetry proofs do not change that fixture disclosure.
Selected unchanged native PNGs are committed with the before/after report.

## Backend preservation and package

Of 144 existing baseline backend files, **138 remain byte-identical**. The six
modified existing files are `cli.py`, dashboard `gateway.py`/`server.py`, memory
`store.py`, and tools `audit.py`/`todos.py`. They contain the documented voice
observation binding, protected projections, atomic stale-memory deletion, private
audit redaction and undated-task compatibility boundary. Additive workspace/voice/
notification adapters are documented in [integration and recovery](HANNI_WORKSPACE_INTEGRATION.md).
The original routing/model/audio/SSH owners and tool authorization remain intact.

Routing keeps the same baseline failures, `REGISTRY-folder.open-2` and
`REGISTRY-spotify.play_pause-1`. Eight differing benchmark rows contain only
evaluation-clock timestamps in the existing default 90-day email window; their
decisions and scores are unchanged. No expected benchmark, training or unrelated
evaluation files were changed to conceal a failure.

The portable application is `dist/HANNI OS/HANNI OS.exe` with its `_internal`
directory, **37,964,519 bytes** in total. Models, private credentials and speech
weights are not embedded. The wrapper uses the installed WebView2 runtime and
existing Python controller because the assessed environment lacks a usable
Rust/MSVC build stack for Tauri. The executable and frontend are separate
artifacts: the existing backend serves the repository's production frontend.

Final SHA-256:

- Executable: `9bf90dc1438e1776369f668117d88c2a5f76a33fc6f796c4d9f41a8a7e586263`
- `app.js`: `e2498da3a1446b52840b60000edba7d538ebe33cba72ff6f952073906e5d6dfe`
- `style.css`: `1054414a519c3262a9abde5850080c07f272c1cfbe1d1743d5cd940b326f1603`

Launch `START_HANNI_OS.cmd` for the native workspace; it attaches to a verified
existing controller or starts a dashboard-only monitor without model/microphone.
Launch `START_HANNI.cmd` for the existing assistant session. **Ctrl+Shift+Space**
opens Mini. Keep the portable directory together and pass `--repo-root` when
launching it from elsewhere. [Desktop setup](HANNI_DESKTOP.md) contains installation,
build, CLI, startup/shutdown and preferences instructions.

## Precise continuation

1. Screen awareness: implement an actual supported local capture/vision capability
   through the authoritative registry/controller, with explicit capture consent,
   exclusions, 120-second expiry, no implicit storage/upload and authorized context
   handoff. Only then enable Analyze and verify the real visual response. Current
   privacy configuration is not a working capture or vision pipeline.
2. Voice: coordinate spoken input through the original attentive session. Verify
   wake, listening, transcription, response, audible TTS, interruption/barge-in and
   return to standby. Instrument actual audible onset before claiming first-audio
   timing; existing wake timing means end of utterance to wake classification.
   Preserve the current input pipeline and emergency-stop gates. No human response
   was supplied to the pending live-voice test question during this run.
3. Optional/provider verification: exercise an authorized connected calendar read
   and confirmed write, real controller memory correction and file-link tool flow,
   and optional Windows notification visibility. Automated adapters do not prove
   those external or acoustic behaviors.

Resume from [the saved checkpoints](HANNI_PHASE12_CHECKPOINTS.md), keeping current
source, migration data, failed-cycle screenshots and exact benchmark expectations.
Repeat affected tests and independent native review when those remaining features
are implemented. Visual acceptance alone cannot mark the full roadmap complete.

Final implementation/visual acceptance checkpoint: `fb6b3cb`. Independent
milestone checkpoints: 2.1 `40a8b65`, 2.2 `5bc1af7`, 2.3 `4c82368`, 2.4 `9e21bc4`,
2.5 `b2af986`. The immediately following documentation checkpoint records this
handoff and committed actual screenshots. User's unrelated ZIP and evaluation
files remain untouched and untracked; no application source changes remain pending.
