# Phase 1 independent native review, cycle 3

Reviewed 2026-10-09. **Corrected user-rubric visual acceptance: PASS, 8.77/10 overall, every surface at least 8.7; AI 1.1.** The original equal-weight table below is superseded historical scoring; see [rubric correction](rubric-correction.md). **Native Mini functional checks:
PASS (13/13). Native lifecycle/security: PASS (9/9).** All six primary surfaces
meet the visual minimum. This accepts the reviewed desktop/Mini/cluster surface;
it does not claim Phase 2 completion, genuine model response or voice timing.

## Reviewed artifact

The actual packaged Windows executable ran against the isolated existing
DashboardServer and ChatHub. Telemetry/device/model-residency samples and the
reply were synthetic and explicitly disclosed. No real model, microphone,
screen analysis, remote power, terminal or SSH action ran. Global shortcuts came
from a separate benign foreground native Tk process, not a browser shortcut.

All **20 refreshed primary screenshots** in
`data/hanni-desktop-review/phase1-primary-cycle3/` and **15 Mini/state frames** in
`data/hanni-desktop-review/phase1-mini-cycle3/` were opened and independently
inspected. The original five screens were captured at physical 1920 x 1080,
1440 x 900, 1366 x 768 and 900 x 650, actual Windows 125% (120 DPI). Mini idle
and discovery were inspected at physical 782 x 528, 640 x 480, 600 x 420 and
900 x 650; additional actual shared-chat/expanded/conflict/offline/guard-recovery
states were inspected. The harness asserts native frame sizes, foreground HWND,
document overflow and composer bounds. No main-matrix JavaScript error or
external request occurred. Some later Mini frames contain an external Grammarly
desktop overlay; it was not graded as HANNI design or modified by the verifier.

SHA-256 for the reviewed artifact:

- Executable: `638e7dec6fa2c246f38a13ec9e44f9916c89b618fcfbdc26afc47871fe9879fb`
- app.js: `e06f2b627c30e6c0dbe7fe4636057e5199efa66e47e5272009c6d15a9414d509`
- style.css: `519914b078dc276de4877bfe7ebf6ad04dbc0fc78aaa118fa5b2334cac126621`

## Superseded historical custom visual rubric

The original equally weighted custom dimensions did not match the user's Section 3 weighting. They are preserved as historical observations and replaced for acceptance by the [authoritative correction](rubric-correction.md).

| Surface | Legibility | Hierarchy | Spacing | Density | Consistency | Interaction clarity | Overall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Home | 9.0 | 8.8 | 8.5 | 8.5 | 8.8 | 8.6 | **8.7** |
| Conversation | 9.0 | 9.0 | 8.8 | 8.4 | 8.9 | 8.7 | **8.8** |
| Mission Control | 8.9 | 8.7 | 8.3 | 8.8 | 8.8 | 8.7 | **8.7** |
| Cluster | 8.9 | 8.9 | 8.8 | 9.0 | 8.8 | 9.0 | **8.9** |
| Settings | 8.9 | 8.7 | 8.6 | 8.4 | 8.8 | 8.8 | **8.7** |
| Mini | 8.9 | 8.8 | 8.5 | 8.7 | 8.7 | 8.6 | **8.7** |

Overall: **8.75 / 10**. AI-template score: **1.1 / 10**. The five main screens
retain restrained, readable app layouts, honest empty states and consistent
controls. Cluster presents all nine nodes at 1366 x 768 and distinguishes
presence, verified telemetry and repair. Minor short-window scrolling and
Mission-column crowding remain below acceptance-blocking severity.

Mini now replaces history with a single useful results region during discovery.
At the smallest 600 x 420 window, the results alone scroll while input and Send
remain inside the visible viewport. The prior empty scrolling strip is gone.
The fixed typography, clear window actions and shared conversation remain
consistent across compact sizes. This closes the cycle 2 visual defect through
actual rendered evidence, not source inspection.

## Actual checks

`mini-results.json` records all 13 checks: window-only five-method bridge and no
main bridge; unauthorized chat rejection; genuine global activation/input focus;
four compact sizes; Escape; refocus already-open Mini behind another app;
native WS_EX_TOPMOST pin/unpin and preference; sole discovery scrolling and
composer bounds at four sizes; keyboard tool discovery preparing a draft with
no execution; exactly one existing ChatHub submission and expansion; actual
RegisterHotKey conflict preserving the old key and successful alternate;
offline draft/disabled Send; zero foreign popup/navigation requests with trusted
document/base URL, functioning bridge and backend health preserved afterward.

`data/hanni-desktop-review/phase1-lifecycle-cycle3/results.json` records nine
actual packaged-executable checks: launch, token rejection/no action, no main
native executor, foreign guards, maximize/minimize/restore, default close with
attached backend surviving, exact 1280 x 800 geometry/100 x 100 position restored,
native tray preference/hide/restore behavior, and Exit desktop with backend and
no-write invariants preserved. The old lifecycle harness first selected the new
Mini CDP page; main-page selection was corrected and the full check reran PASS.
This was a verification adaptation, not an app defect.

All source repairs from earlier cycles have actual native evidence. Review
fixture cleanup still emits occasional Windows connection-reset traces when a
WebView is force-closed; checks passed and no production/backend mutation was
performed. Main owns the full regression and actual controller/audio/provider
integration evidence. Synthetic ChatHub reply transport is not reported as
genuine natural-language model inference, first-audible timing or wake latency.

All launched review processes were closed and GUI ownership released. No
externally managed HANNI session was attached or stopped. This frozen cycle is
ready for the main coordinator's checkpoint. Phase 2 routes and live voice/
vision/provider capabilities require their own truthful status and verification.
