# Independent visual review: iteration 0

Reviewed by the independent verification agent on 2026-10-09. This is a baseline
review of the existing rendered browser application, not native desktop acceptance.

## Evidence and scope

The verifier ran `scripts/check_hanni_os_browser.py` against an isolated ephemeral
DashboardServer with synthetic telemetry, in-memory conversation state, and fake
power/terminal handlers. No real power request, terminal, model, voice session, or
cluster connection was started. Five screenshots were captured at 1600 x 1000:
`data/hanni-desktop-review/iteration-0/{home,chat,mission,cluster,settings}-desktop.png`.
All five were opened and visually inspected. The harness also passed navigation,
dialogs, safe text rendering, reconnect/draft preservation, and layout checks at
1920, 1600, 1440, 1280, 1100, 960, 840, 720, 600, 440, 390, and 320px widths.
No JavaScript, CSP, or external HTTP request errors were reported.

Native capture feasibility was independently checked using PIL ImageGrab: an
interactive Windows desktop at 1920 x 1200 is available. The initial unaware
Python process reported virtualized 96 DPI; the subsequent native review correctly
measured actual 120 DPI / 125% after enabling PMv2 capture awareness. Win32 window
automation and Playwright are installed. No native HANNI window exists in this
baseline; a wrapper/executable is still required. Desktop session screenshot is
local diagnostic evidence only, because it also contains unrelated application
content.

## Scores

The rubric columns are typography /2, layout /2, spacing /2, identity /2,
native appearance /1, and interaction polish /1. Native appearance is zero
because the baseline runs in an ordinary browser, not a native HANNI application.

| Screen | Type | Layout | Spacing | Identity | Native | Interaction | Total | AI template |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Home | 1.4 | 0.9 | 1.3 | 1.4 | 0.0 | 0.8 | 5.8 | 4.0 |
| Conversation | 1.5 | 1.2 | 1.4 | 1.5 | 0.0 | 0.8 | 6.4 | 3.0 |
| Mission Control | 1.5 | 1.2 | 1.4 | 1.5 | 0.0 | 0.8 | 6.4 | 3.0 |
| Cluster | 1.4 | 0.6 | 1.2 | 1.3 | 0.0 | 0.8 | 5.3 | 5.0 |
| Settings | 1.5 | 1.1 | 1.4 | 1.5 | 0.0 | 0.8 | 6.3 | 2.5 |

Overall arithmetic mean: **6.04/10**. Mean AI-template appearance: **3.5/10**.
Visual acceptance: **FAIL**. Native package inspection: **PENDING**.
Backend regression baseline reported by the main coordinator: **744 passed,
2 skipped, 17 subtests**. Routing evaluation baseline: **1129/1131**. These are
coordinator-run checks; this verifier independently ran the browser smoke and
inspected the screenshots.

## Concrete observations and corrective ownership

| Screen | Severity | Evidence | Defect and recommended correction | Owner |
|---|---|---|---|---|
| All | High | All five desktop screenshots | A 60px icon rail, 220px navigation, and 300px default inspector consume 580px of a 1600px screen. Collapse to one compact navigation region and make context optional. | Worker 1 |
| All | Medium | All five desktop screenshots | Global voice strip takes about 82px and supporting labels are often too small. Reduce voice strip and raise supporting type to readable desktop sizes. | Worker 1 |
| Home | Medium | home-desktop.png | A large greeting, promotional subtitle, and oversized nested composer dominate above the fold. Use compact greeting and actionable conversation entry; replace unsupported planner filler with existing useful activity. | Worker 2 |
| Conversation | Medium | chat-desktop.png | Idle brand and heading consume a large empty hero while the composer is oversized. Give conversation content a readable centered width and compact composer with useful idle actions. | Worker 2 |
| Mission Control | High | mission-desktop.png | CPU/RAM/disk consume around 100px each for one value and thin graph; model/activity rows fall below the voice footer. Put essential performance and model state in a compact above-fold overview. | Worker 2 |
| Cluster | High | cluster-desktop.png | Only about two of nine nodes fit in 1000px height; two large empty graphs repeat for nodes with no samples. Use compact sortable/filterable node table with honest unknown readings and selected-node detail graphs. | Worker 2 |
| Settings | Medium | settings-desktop.png | Privacy summary takes almost 450px before devices; audio/model settings require scrolling. Use sections and tighter two-column settings rows while preserving actual controls. | Worker 2 |

Existing strengths to retain: restrained dark base, recognizable `h.` brand,
honest missing readings, clear repair state, native confirmation dialog semantics,
functional token-protected writes, draft preservation, plain-text chat rendering,
and no decorative stock assets or gradient marketing language.

## Next independent review

Capture the real native executable at 1920 x 1080, 1440 x 900, 1366 x 768, and a
smaller resized window. Inspect actual window controls, tray/close behavior,
navigation, selected-node details, dialogs, idle and disconnected states.
Browser screenshots may guide revisions but cannot satisfy final native review.
Acceptance requires every primary screen >=8.6, overall >8.5, AI-template <=2,
no critical defects, and coordinator-confirmed regression checks.
