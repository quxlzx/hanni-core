# Independent visual review: iteration 1

Reviewed 2026-10-09 by Agent 3, independently of both implementation workers.
**Visual acceptance: FAIL.** The actual desktop executable works, but density
and short-window polish need another revision. No score was supplied by a worker.

## Actual application evidence

Executable launched: `dist/HANNI OS/HANNI OS.exe`, with `--attach-only` against
an isolated loopback ReviewFixture. It created a real WinForms/WebView2 window
with caption, taskbar identity, standard window controls, and application menu.
The fixture uses synthetic telemetry, settings, chat replies, and machine-action
handlers. No live model, microphone, SSH terminal, or node power action ran.
An externally started normal HANNI session was left untouched; this review never
attached to its production port.

The verifier captured **27 actual framed Windows screenshots**, using ImageGrab
from the foreground native HWND. All five primary screens were opened and
visually inspected at all four physical window sizes:

- 1920 x 1080
- 1440 x 900
- 1366 x 768
- 900 x 650

Observed system scaling is **125%, 120 DPI**. The capture process was made PMv2
DPI aware and asserts each actual framed size matches its filename. Initial
96-DPI virtualized crops were rejected and replaced before grading. CDP was used
for navigation and interaction, never as the screenshot source.

Evidence directory: `data/hanni-desktop-review/iteration-1/`. Representative
filenames are `{home,chat,mission,cluster,settings}-1366x768-native.png`; every
other required size has the corresponding filename. Supplemental evidence:
`cluster-selected-native.png`, `cluster-confirmation-native.png`,
`command-palette-native.png`, `conversation-active-native.png`,
`home-recent-conversation-native.png`, `settings-saved-native.png`, and
`disconnected-native.png`. Machine-readable results: `capture-results.json`.

Native debug mode opened Edge DevTools during this iteration and its transient
viewport-size label appears in a few frames. The verifier selected only the
actual fixture WebView and kept the HANNI window foreground. Worker 1 has since
changed debug startup and darkened the native menu; those later changes are not
accepted on the basis of source alone and require the next native capture.

## Scores and justification

Columns follow the supplied rubric: typography /2, layout /2, spacing /2,
identity /2, native appearance /1, and interaction /1.

| Screen | Type | Layout | Spacing | Identity | Native | Interaction | Total | AI template |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Home | 1.8 | 1.5 | 1.6 | 1.8 | 0.8 | 0.8 | **8.3** | 1.8 |
| Conversation | 1.8 | 1.7 | 1.6 | 1.8 | 0.8 | 0.8 | **8.5** | 1.6 |
| Mission Control | 1.8 | 1.5 | 1.6 | 1.8 | 0.8 | 0.8 | **8.3** | 1.5 |
| Cluster | 1.8 | 1.4 | 1.8 | 1.8 | 0.8 | 0.8 | **8.4** | 1.1 |
| Settings | 1.8 | 1.4 | 1.5 | 1.8 | 0.8 | 0.8 | **8.1** | 1.3 |

Overall mean: **8.32/10**. AI-template mean: **1.46/10**.
Every primary screen remains below the minimum 8.6.

- Home: readable restrained type, useful shortcuts and truthful empty states;
  oversized nested assistant region still dominates. At 1366 x 768 the model row
  and recent activity fall below the footer. See home-1366x768-native.png and
  home-1920x1080-native.png.
- Conversation: clear user/HANNI identity, readable messages, focus and reconnect
  states, and the composer remains reachable. At 900 x 650 the idle brand is
  visibly cropped by its scroll region; the input remains overly tall. See
  chat-900x650-native.png and conversation-active-native.png.
- Mission Control: CPU/RAM/disk/model status now appear together, with honest
  missing GPU load. At 1366 x 768 network and basic GPU/model details are pushed
  below the fold by heading, summaries, and history space. See
  mission-1366x768-native.png and mission-1440x900-native.png.
- Cluster: practical table, real status distinctions, visible percentages,
  member identity, sorting/filtering controls, and Yunjin repair semantics. All
  nine nodes fit at 1920 x 1080, but Yunjin is below the fold at 1440 x 900 and
  only six full rows fit at 1366 x 768. Selected-node headers consume unnecessary
  height before measurements/processes/controls. See cluster-1366x768-native.png,
  cluster-1440x900-native.png, and cluster-selected-native.png.
- Settings: clear section labels, genuine devices/model controls and policy
  projection. Audio controls plus oversized refresh/help gaps consume most of a
  short window; audio/model apply actions do not fit together at 1366 x 768.
  See settings-1366x768-native.png and settings-900x650-native.png.

Common strengths: a single compact sidebar, recognizable `h.` identity, readable
native scaling, subdued color, no gradients/glows/fake proof, slim voice status,
honest unknown values, and working controller-backed interactions. Native
appearance loses points for the bright menu strip against a dark application.
Interaction polish loses points for nested command-palette scrollbars and short
window spacing. These are observed defects, not a lack of functioning backend.

## Required corrections

| Screen | Severity | Screenshot evidence | Correction | Owner |
|---|---|---|---|---|
| Cluster overview | High | cluster-1366x768-native.png; cluster-1440x900-native.png | Add short-height compact overview: tighter heading/count/filter regions and shorter rows. Preserve status semantics and readable values; move secondary addresses/GiB details to selected-node view or concise inline text. All nine should be assessable on a typical 1366 x 768 desktop at observed 125% scaling. | Worker 2 |
| Cluster details | Medium | cluster-selected-native.png | Combine redundant Cluster/node headings, Back action and identity; reduce facts/graph height so processes and meaningful controls appear without excessive scrolling. | Worker 2 |
| Home | Medium | home-1366x768-native.png | Reduce assistant box/composer and vertical gaps so computer summary and meaningful recent content appear earlier. | Worker 2 |
| Mission Control | Medium | mission-1366x768-native.png | Tighten short-height heading/summary/history spacing; bring graphics and model basics above fold. Remove duplicated estimated-memory note. | Worker 2 |
| Settings | Medium | settings-1366x768-native.png | Reduce audio/model section whitespace and refresh/help gaps; improve access to both apply actions on short windows. Replace browser-specific audio copy with voice-session wording. | Worker 2 |
| Conversation idle | Medium | chat-900x650-native.png | Prevent clipped idle brand in short scroll region; reduce empty-state min-height or omit decorative brand on short windows. | Worker 2 |
| Command palette | Medium | command-palette-native.png | Keep one results scroll region; prevent outer dialog and inner list from showing simultaneous vertical scrollbars. | Worker 1 |
| Native shell | Medium | all native frames | Match application menu to dark shell and remove automatic visible DevTools from review debug startup. Changes need recapture. | Worker 1 |

No critical functional defect was found in the captured flows. High visual
priority is Cluster information density. Corrections were sent directly to
the responsible workers and main coordinator before this report.

## Actual checks

Capture harness passed: native executable/backend connection, five-screen
navigation at all required dimensions without document horizontal overflow,
node detail, power confirmation cancellation with no write, Ctrl+K/Escape,
ChatHub submission and displayed synthetic response, exactly two token-protected
synthetic settings writes, disconnection/recovery with draft preservation, and
native minimize/restore. The inspected disconnected frame correctly disables
sending and retains existing messages/draft. No captured app JavaScript, CSP,
or external HTTP request errors occurred.

Native maximize, tray behavior, preferences, clean close and attached-backend
survival still require the separate lifecycle check after Worker 1's debug fix.
Real measured telemetry and full backend regression are coordinator-owned checks.
The baseline regression was 744 passed, 2 skipped, 17 subtests; routing1129/1131.
Passing this synthetic native capture does not imply those final checks passed.
