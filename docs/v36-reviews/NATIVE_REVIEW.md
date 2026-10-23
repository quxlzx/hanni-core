# Independent native review, V3.6

This is one independent Codex reviewer applying the rubric sealed before any
candidate outputs. It is not a human panel, an accessibility certification, or
proof that the model can complete a task. Scores concern the actual native
client attached to the original isolated HANNI controller with its configured
cached Qwen supervisor. No `ReviewFixture` backend, fabricated telemetry or
model response was used.

The primary-screen mean is **8.72/10**. All 18 primary screens meet 8.6. The
reviewer's template-resemblance estimate is **1.6/10**. The separate Mini is
**8.4/10** in this Windows environment; the equal-weight mean of all 19 reviewed
views including Mini is **8.71/10**. This includes the external overlay issue
described below. These are subjective assessments, supported by actual frames
and functional observations; they do not turn blocked integrations into passes.

Each primary screen was inspected at physical outer-window sizes 1920×1080,
1440×900, 1366×768 and 900×650. Windows DPI was 120, or 125%; the measured WebView
viewport is consequently smaller than the physical window. The evidence stores
both dimensions. All screens remained navigable without horizontal document
overflow. Longer tables and settings retain deliberate vertical scrolling.

The columns below each have a maximum of two points: typography (T), layout (L),
spacing (S), identity (I), and desktop polish (P).

| Screen | T | L | S | I | P | Total | Independent reason and limit |
|---|---:|---:|---:|---:|---:|---:|---|
| Home | 1.8 | 1.8 | 1.8 | 1.7 | 1.7 | 8.8 | Useful system/workspace hierarchy and restrained status presentation remain clear at compact width; some unused space in an empty workspace. |
| Chat | 1.8 | 1.8 | 1.7 | 1.7 | 1.7 | 8.7 | Conversation and composer have clear priority and keyboard access; initial review covers empty composer and navigation, with model streaming assessed separately. |
| Voice | 1.8 | 1.7 | 1.7 | 1.7 | 1.7 | 8.6 | Legible device/state controls and honest unavailable actions; unavailable voice hardware limits interaction coverage. |
| Planner | 1.8 | 1.8 | 1.7 | 1.7 | 1.7 | 8.7 | Schedule and task information use practical density and clear selection; empty schedule stays readable. |
| Tasks | 1.8 | 1.8 | 1.8 | 1.7 | 1.7 | 8.8 | Populated task, completed state, filter, due date and create dialog work without cramped actions; cancellation preserves the record. |
| Calendar | 1.8 | 1.7 | 1.8 | 1.7 | 1.7 | 8.7 | Calendar and local deadlines are readable with explicit disconnected-provider feedback; live Google access was intentionally excluded. |
| Projects | 1.8 | 1.8 | 1.7 | 1.7 | 1.7 | 8.7 | Actual selected project and associated saved note establish information hierarchy; explicit project selection is required after creation. |
| Memory | 1.8 | 1.7 | 1.7 | 1.8 | 1.7 | 8.7 | Current record, source history, proposals, correction and deletion are distinct and inspectable; compact header leaves fewer visible rows and history may need scrolling. |
| Mission | 1.8 | 1.7 | 1.7 | 1.7 | 1.7 | 8.6 | Honest empty mission state and consistent navigation; large empty area makes this screen less useful until work exists. |
| Models | 1.8 | 1.8 | 1.7 | 1.7 | 1.7 | 8.7 | Actual configured model/state details are readable and subordinate to status; runtime switching was not performed. |
| Agents | 1.8 | 1.8 | 1.7 | 1.7 | 1.8 | 8.8 | Capability search and technical details support inspection without decorative filler; long lists scroll predictably. |
| Cluster | 1.8 | 1.8 | 1.8 | 1.8 | 1.7 | 8.9 | Real CPU/RAM history, availability and uptime form readable node rows; Yunjin's jellyfish repair state is explicit. Power/terminal execution remained blocked. |
| Activity | 1.8 | 1.8 | 1.7 | 1.7 | 1.7 | 8.7 | Time, event and status distinctions remain readable in dense content; no claim that every possible event type was generated. |
| Screen | 1.8 | 1.7 | 1.7 | 1.7 | 1.7 | 8.6 | Privacy/state text is clear and unsupported analysis is disabled; this screen is a truthful unavailable state, not working screen capture. |
| Notifications | 1.8 | 1.8 | 1.7 | 1.7 | 1.7 | 8.7 | Empty/list presentation and preference hierarchy are clear; notification delivery to real Windows was not invoked. |
| Settings | 1.8 | 1.8 | 1.7 | 1.7 | 1.7 | 8.7 | Groups, control labels and scrolling preserve readability; live security, provider and audio-device changes were excluded. |
| MCP | 1.8 | 1.8 | 1.7 | 1.8 | 1.7 | 8.8 | Catalog/server distinction and add-server dialog are inspectable; cancel makes no server write. Actual local SDK lifecycle is verified separately. |
| Workflows | 1.8 | 1.8 | 1.7 | 1.8 | 1.7 | 8.8 | Empty ledger and bounded goal dialog expose intended actions clearly; cancel produces no job. Actual planning/completion is assessed independently. |

Scores are intentionally close because these screens share the same consistent
desktop shell. The differences reflect actual density, useful hierarchy and
populated evidence. The dark theme is the theme actually exercised; no untested
theme receives credit. The member emojis are explicitly owner requested cluster
identifiers. There are no invented testimonials, trusted-company logos, gradient
headlines, anonymous feature-card triplets or promotional statistics in the
inspected interface.

Evidence is retained locally in `data/v36-verification/native-cycle1/results.json`
(163 assertions, 77 frames), `native-cycle2/results.json` (70 assertions, 29
frames, stopped at a test-harness assumption), and `native-cycle3/results.json`
(44 assertions, 11 frames, all passed). Assertions include geometry and frame
checks: **163 does not mean 163 distinct functional controls**. Native cycle
three provides read-after-write evidence for a synthetic project, project note,
task creation/completion, derived memory proposal, exact approval, correction
and confirmed deletion. It also exercises palette/Escape, inspector toggling,
navigation, capability search, and safe cancellation of MCP/workflow dialogs.
Unavailable analysis and voice controls remain disabled. Reboot was disabled in
the earlier cycle-three snapshot; the manager's final read-only cycle-five
cluster observation reports HANNI reboot and terminal available, with sleep
disabled by node configuration. Available remote power and terminal actions
remain **UNSAFE_TO_RUN/uninvoked** in this campaign. No reboot dialog, remote
power operation or SSH terminal success is claimed.

Cycle two's native harness initially assumed a newly saved project became
selected automatically. It correctly created the project, then waited for a note
control on the wrong selection. The failed original artifact is retained. The
repair explicitly selects the existing project through the real UI and resumes
without duplicating it; this was a harness correction, not a production fix.

Cycle one's capture helper used the outer `GetWindowRect`; Windows can expose
several transparent resize-border pixels from the underlying repository window.
No underlying content was used to score HANNI. The helper was hardened to the
owned window's `DwmGetWindowAttribute(EXTENDED_FRAME_BOUNDS)` and refuses invalid
or occluded capture bounds. Later images use only its visible frame. Raw initial
images stay local and are not published. The full acceptance recapture is
`data/v36-verification/native-cycle4/results.json`: 163 checks and 77 visible-frame
captures passed against the final original cycle-five backend, including all 18
primary screens at all four sizes. Its primary image references are listed in
`data/v36-verification/native-scores.json`.

The original isolated-data configuration did not isolate Google's global
Windows credential vault: Calendar initially showed Connected. The reviewer
did not refresh Google or invoke provider tools. This finding was rejected as
insufficient test isolation. The engineer closed only the owned original
controller/model and relaunched through the documented `GoogleAccess` dependency
seam with an explicit empty vault. Calendar then reports disconnected and its
Refresh action returns specific connection feedback while retaining local
deadlines. The original finding and corrected-run evidence are both retained;
no emails, tokens or real provider requests were exported.

Mini was separately exercised through the actual native bridge and real Windows
global shortcut. Twelve checks and six frames passed in
`data/v36-verification/mini-cycle2/results.json`: shortcut registration,
Ctrl+Shift+Space opening, pin/unpin, isolated preference persistence, capability
search and Escape dismissal. The first Mini run used an incorrect expected
button label; its failed raw artifact is retained and the correct existing label
was used on rerun. Requested 420×320 and 520×380 sizes are clamped by the native
minimum at 125% scaling; the captured metadata's actual dimensions are
authoritative. A real external Grammarly floating overlay covers part of the
focused Mini textarea/Send corner at small widths. No unrelated process was
stopped or hidden. This environmental interference lowers Mini polish and limits
mouse-Send acceptance; it is not a fabricated HANNI control or proven HANNI layout
defect. The larger Mini remains clear. No assistant message was submitted by the
Mini geometry/control campaign.

All owned native review processes were closed. The engineer owns shared backend
and model lifecycle. Provider OAuth, remote node writes, native power changes,
audio output, private screen capture and unrelated process manipulation were
excluded. Tray action execution, every settings mutation and all unavailable
integration controls have not been exhaustively exercised and remain partial
functional coverage.

Reviewed source identities: `app.js` SHA-256
`7eaede8ff987b5e1a8b233aa0e0c7382e9a9586fca9618aee33b39d998dce9d2`,
`style.css` `d021496f25414013738661a07111fc8008a596c803ad56f0202cfb3edea31e1b`,
and native executable
`9bf90dc1438e1776369f668117d88c2a5f76a33fc6f796c4d9f41a8a7e586263`.
These hashes matched before and after the captures. The primary visual gate
passes for the 18 reviewed primary screens. A requirement that applies the same
8.6 minimum to Mini would remain unmet in this environment; no primary screen
was reclassified to improve the score. The system reliability acceptance is
separate and may remain PARTIAL.
