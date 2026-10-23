# Phase 1 independent native review, cycle 2

Scoring-method correction: numeric scores in this historical failed cycle used a custom equal-weight rubric, not the user's required weighting, and are superseded for acceptance. The actual double-scroll/blank-strip Mini discovery defect remains FAIL. See [authoritative rubric correction](rubric-correction.md).

Reviewed 2026-10-09. **Mini native functional checks: PASS (12/12).
Visual acceptance: FAIL**, because Mini scores 8.4 against the required 8.6
minimum. No critical functional or security defect remains in the tested scope.

## Actual artifact and evidence

The rebuilt Windows executable ran against an isolated DashboardServer and the
existing ChatHub. Synthetic telemetry, audio-device rows and reply are disclosed;
no model, microphone, node power, terminal or vision operation ran. A separate
benign native Tk application supplied a different foreground process for actual
Windows accelerator tests. This is transport/window verification, not proof of
live assistant routing or voice latency.

All 20 refreshed primary frames in
`data/hanni-desktop-review/phase1-primary-cycle2/` were independently opened:
five screens at physical 1920 x 1080, 1440 x 900, 1366 x 768 and 900 x 650,
actual 125% (120 DPI) Windows scaling. Capture assertions passed, with zero
JavaScript errors, foreign requests or horizontal document overflow. Artifact
hashes are in `capture-results.json`.

Ten Mini/state frames in `data/hanni-desktop-review/phase1-mini-cycle2/` were
independently opened: idle at 782 x 528, 640 x 480, 600 x 420 and 900 x 650
physical pixels, discovery, shared conversation, expanded full conversation,
actual shortcut conflict, offline draft and post-canceled-navigation health.
These are real compact secondary-window captures, not enlarged monitor mockups.
Later frames include an external Grammarly desktop overlay near the composer;
it was not graded as HANNI design and no external application was altered.

## Measured native behavior

All twelve harness checks passed:

- Main exposes no native bridge; Mini exposes exactly get_state, dismiss, pin,
  expand and configure_hotkey, with no machine/tool executor.
- Unauthorized Mini chat POST is rejected 403 and nonallowlisted shortcut input
  is rejected without execution.
- Genuine Ctrl+Shift+Space opens/focuses Mini and its input from the separate
  foreground process.
- Mini renders at all four compact physical sizes without document overflow.
- Actual keyboard Escape hides Mini while the attached backend survives.
- The shortcut refocuses an already-open Mini behind another application.
- Pin sets actual WS_EX_TOPMOST and the persisted preference; unpin clears it.
- Keyboard file/app discovery prepares a request, with no queued chat or action
  until Send.
- Exactly one submitted message enters existing ChatHub; synthetic reply and
  expansion appear in the same full conversation.
- Reserving the alternate OS hotkey causes a visible real conflict, keeps the
  prior registration active, and a later free alternative activates Mini.
- Assistant offline disables Send while retaining the draft.
- Foreign popup/navigation dispatches zero requests and preserves trusted
  document/base URL, working bridge and backend status afterward.

The prior navigation/bridge availability defect is therefore closed by actual
native evidence. Pin was independently tested before navigation in this cycle.
The previous failure was not used as proof of an isolated Pin implementation
bug. Fixture cleanup emitted two Windows connection-reset traces when the
review executable was force-closed; no failed check or write resulted.

## Independent scores

The rubric covers legibility, hierarchy, spacing, information density,
consistency and interaction clarity, assessed from actual pixels.

| Surface | Score / 10 | Assessment |
| --- | ---: | --- |
| Home | 8.7 | Clear composer and useful restrained sections; honest emptiness. |
| Conversation | 8.8 | Readable history and usable persistent composer across sizes. |
| Mission Control | 8.7 | Aligned figures/history and honest missing diagnostics; minor short-layout crowding. |
| Cluster | 8.9 | Dense aligned nine-node overview, presence/SSH distinction and repair state; all nodes visible at 1366 x 768. |
| Settings | 8.7 | Predictable grouped controls with clear labels and manageable vertical scrolling. |
| Mini | 8.4 | Healthy window controls and coherent typography, but command discovery has an empty independently scrolling history strip above another scrolling result area. |

Overall: **8.70 / 10**; AI-template score **1.1 / 10**. The overall target is met,
but the per-primary-screen minimum is not. This is a visual rejection, not a
renewed functional/security rejection.

## Remaining visual defect

**Medium, Mini discovery:** `mini-tool-discovery-native.png` shows a collapsed
empty history area with its own scrollbar above the separately scrolling tool
results. This wastes vertical room and creates an unclear keyboard/scroll
surface in the launcher's core discovery state. Worker 1 owns the bounded fix:
replace or hide history while command discovery is active, retain one useful
results scroll area and the composer. Do not alter ChatHub/controller behavior.

Main reported 46 native unit tests and combined 90 desktop/store/feature/voice
checks passing before this build; 45 further focused privacy/store/voice checks
also passed. Final regression and genuinely live controller/audio checks remain
the main coordinator's responsibility. Phase 2 UI is not mounted in this build
and receives no acceptance here.

All review native/helper processes are closed; Cim inspection showed no
HANNI OS.exe. GUI ownership is released for the next checkpoint and bounded
visual repair. Another actual Mini capture and independent inspection is needed
before this milestone passes its visual gate.
