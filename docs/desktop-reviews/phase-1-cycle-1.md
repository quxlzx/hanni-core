# Phase 1 independent native review, cycle 1

Scoring-method correction: numeric scores in this historical failed cycle used a custom equal-weight rubric, not the user's required weighting, and are superseded for acceptance. The actual bridge-availability failure remains FAIL. See [authoritative rubric correction](rubric-correction.md).

Reviewed 2026-10-09. **Functional acceptance: FAIL. Visual acceptance across all
primary surfaces: FAIL.** The original five screens retain acceptable quality;
the new Mini needs correction and another actual native review.

## Evidence and scope

The actual packaged `dist/HANNI OS/HANNI OS.exe` ran against the existing
DashboardServer and ChatHub in an isolated temporary ReviewFixture. Telemetry,
audio-device data and configured model residency were explicitly synthetic.
No real voice/model, screen analysis, SSH, terminal or power action ran.

Main-window evidence is `data/hanni-desktop-review/phase1-primary/`:
20 foreground Win32 framed screenshots, all independently opened and inspected.
All five screens were captured at physical 1920 x 1080, 1440 x 900, 1366 x 768
and 900 x 650. Actual Windows scaling is 125% (120 DPI). The harness asserts
frame sizes and no document horizontal overflow, and records the executable and
shipped asset SHA-256 values in `capture-results.json`. No JavaScript errors or
foreign requests occurred during this main-screen capture matrix.

Mini evidence is `data/hanni-desktop-review/phase1-mini/` and the confirmation
run `phase1-mini-confirm/`. Actual floating Mini size was 782 x 528 physical
pixels at 125%; it was reviewed at its native compact size rather than stretched
to monitor-sized layouts. `mini-idle-native.png` and
`mini-pin-failure-native.png` were independently opened. A separate benign
native Tk process provided a genuinely different foreground application for
global shortcut testing; its HWND process ancestry was verified. An initial
harness exact-PID assertion was corrected for the Windows venv redirector and
is not an application defect.

## Scores from inspected pixels

Scoring weighs legibility, hierarchy, spacing, information density, consistency
and interaction clarity. Functional failures remain separate from averages.

| Surface | Score / 10 | Evidence and assessment |
| --- | ---: | --- |
| Home | 8.7 | Clear composer and restrained two-column real-purpose content; honest empty states. Some lower activity content scrolls on short windows, with controls usable. |
| Conversation | 8.8 | Readable width, clear empty state, persistent composer and tool disclosure; small layout preserves the conversation hierarchy. |
| Mission Control | 8.7 | Aligned resource figures and paired history graphs; unavailable GPU metrics labeled honestly. Dense short layout is readable, with minor crowding between diagnostic and model columns. |
| Cluster | 8.9 | Compact aligned table, accurate presence versus SSH distinction, repair state and missing metrics; all nine nodes visible at 1366 x 768. Small window intentionally scrolls. |
| Settings | 8.7 | Predictable labeled native-like controls, grouped apply/refresh actions and readable policy projection. Vertical scrolling remains necessary for lower settings. |
| Mini | 8.0 | Initial typography and hierarchy are coherent, but observed raw implementation error plus offline/bridge failure makes the interaction unclear. Only initial and failing native states were available; active/shared/offline-draft states remain unverified. |

Overall across these six surfaces: **8.63 / 10**; original five-screen mean:
**8.76 / 10**. AI-template score: **1.1 / 10**. Mini is below the required 8.6,
and functional defects prevent acceptance regardless of the overall average.

## Actual checks passed

- Native main and secondary Mini creation; main has no exposed native bridge,
  while Mini exposes exactly five window-only methods.
- Mini POST chat without token rejected 403; no queued message or write handler
  was invoked. Nonallowlisted shortcut input was rejected.
- Foreign loopback popup and direct navigation dispatched zero HTTP requests,
  left the expected Mini URL and did not create another WebView page.
- Genuine Ctrl+Shift+Space from the other foreground application opened Mini,
  made its actual HWND foreground and focused its input.
- Actual keyboard Escape hid Mini while the attached fixture backend survived.

## Defects and remaining tests

| Severity | Surface | Observed evidence | Required fix / owner |
| --- | --- | --- | --- |
| High | Mini bridge availability | After the blocked foreign-navigation sequence, Pin did not set WS_EX_TOPMOST within 15 seconds. Confirmation frame shows `Ce(...).get_state is not a function`, Pin remains unpressed, and an asynchronous get_state probe times out. | Worker 1: preserve/recover trusted Mini bridge after canceled navigation, then independently verify Pin. Do not infer the precise root cause solely from the missing native style. |
| Not isolated | Mini Pin | Native extended style was 327680, without WS_EX_TOPMOST; no persisted window preference was produced in the failing run. The bridge failure occurred first, so this does not independently prove a native Pin implementation defect. | Worker 1: retest both directions with a healthy bridge; any UI-thread hardening requires actual native verification. |
| Pending | Mini foreground shortcut | Worker 1 independently identified logical visibility toggle that may dismiss an already-open Mini behind another app. This scenario has not yet been independently executed. | Add native open-Mini -> other-app -> hotkey refocus test in the next cycle; source reasoning alone is not a graded functional result. |

The failing Pin step prevented later shared submission/expansion, real OS hotkey
conflict/alternative and deliberate offline-draft checks. These remain NOT
VERIFIED. Voice controls/timing and Phase 2 screens are outside this frozen build
and are not counted complete. Initial controller/Desktop/Mini/Productivity
focused checks were reported passing by the main coordinator (102 tests), with
47 further focused privacy/permissions/HTTP/speech checks passing; final full
regression remains the main coordinator's responsibility.

The verifier terminated only the exact launched confirmation review process
after evidence collection stalled; all native review processes and the separate
foreground helper were then closed. The fixture context cleaned up its backend.
No externally managed production session was attached or stopped. GUI ownership
is released for checkpoint and bounded repairs. A new executable must be frozen,
recaptured and independently rechecked before this milestone can pass.
