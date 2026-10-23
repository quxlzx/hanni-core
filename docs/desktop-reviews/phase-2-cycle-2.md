# Phase 2 independent native review, cycle 2

Reviewed 2026-10-09. **Visual gate FAIL: 8.66/10 overall, Mini 8.3 below the 8.6 minimum; AI-template score 1.2/10.** All sixteen main screens meet the minimum after the bounded repairs. A real initial Mini bridge error remains visible in all four idle and four discovery sizes. Subsequent successful native controls do not erase this failed startup evidence. Whole-feature acceptance also remains partial or blocked as recorded below.

## Actual evidence and provenance

The coherent packaged Windows executable was captured as foreground Win32-framed ImageGrab pixels, not browser screenshots or mockups. All 64 main frames were independently inspected through four-frame contact sheets made from the original native frames: 1920 x 1080, 1440 x 900, 1366 x 768, and 900 x 650 physical pixels at observed Windows 120 DPI / 125%. Every main route rendered without horizontal document overflow, JavaScript errors or external WebView requests. Four compact Mini sizes were 600 x 420, 640 x 480, 782 x 528 and 900 x 650 physical pixels; all fifteen Mini/state frames were independently opened. No 150% DPI claim is made.

Evidence is under ignored `data/hanni-desktop-review/phase2-primary-cycle2/`, `phase2-mini-cycle2/`, `phase2-workspace-cycle2/`, and `phase2-lifecycle-cycle2/`. Each directory retains actual frame PNGs and machine-readable results. Main frames follow `<route>-<width>x<height>-native.png`; contact sheets are inspection aids only.

The fixture uses real isolated AppConfig, original registry permission and HTTP token/Host/Origin gates, task/project/note/link persistence, original MemoryStore, redacted execution audits and notification store. Synthetic review content is disclosed. Private CRUD is not mocked. Telemetry, device/model samples and ChatHub reply text are synthetic; voice is inactive/unbound and GoogleAccess uses an explicitly empty offline review vault. No real model, microphone, SSH, node power, terminal, provider request or application screen analysis ran in this verifier cycle. Coordinator live proofs are separate evidence and do not change this disclosure.

Reviewed SHA-256:

- Executable: `9bf90dc1438e1776369f668117d88c2a5f76a33fc6f796c4d9f41a8a7e586263`
- app.js: `0b1c60693e3a72812c8942beb39879272a56b1519f1b85f17649f26db143440c`
- style.css: `1054414a519c3262a9abde5850080c07f272c1cfbe1d1743d5cd940b326f1603`

## Exact user Section 3 rubric

These category points use the required 2/2/2/2/1/1 weights, summed directly. The earlier custom equal-weight assessments remain superseded historical results as explained in [rubric-correction.md](rubric-correction.md). This new package is independently graded, not converted from those scores.

| Surface | Typography/hierarchy /2 | Layout/density /2 | Spacing/consistency /2 | Professional identity /2 | Desktop /1 | Interaction /1 | Total /10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Home | 1.8 | 1.7 | 1.7 | 1.7 | 0.9 | 0.9 | **8.7** |
| Conversation | 1.8 | 1.7 | 1.8 | 1.7 | 0.9 | 0.9 | **8.8** |
| Voice | 1.8 | 1.7 | 1.7 | 1.7 | 0.9 | 0.9 | **8.7** |
| Planner | 1.8 | 1.6 | 1.7 | 1.7 | 0.9 | 0.9 | **8.6** |
| Tasks | 1.8 | 1.7 | 1.7 | 1.7 | 0.9 | 0.9 | **8.7** |
| Calendar | 1.8 | 1.7 | 1.7 | 1.7 | 0.9 | 0.9 | **8.7** |
| Projects | 1.8 | 1.6 | 1.7 | 1.7 | 0.9 | 0.9 | **8.6** |
| Memory | 1.8 | 1.6 | 1.7 | 1.7 | 0.9 | 0.9 | **8.6** |
| Mission Control | 1.8 | 1.7 | 1.7 | 1.7 | 0.9 | 0.9 | **8.7** |
| Models | 1.8 | 1.7 | 1.7 | 1.7 | 0.9 | 0.9 | **8.7** |
| Agents | 1.8 | 1.7 | 1.7 | 1.7 | 0.9 | 0.9 | **8.7** |
| Cluster | 1.8 | 1.8 | 1.7 | 1.7 | 0.9 | 1.0 | **8.9** |
| Activity | 1.8 | 1.7 | 1.7 | 1.7 | 0.9 | 0.9 | **8.7** |
| Screen awareness | 1.8 | 1.7 | 1.7 | 1.7 | 0.9 | 0.8 | **8.6** |
| Notifications | 1.8 | 1.6 | 1.7 | 1.7 | 0.9 | 0.9 | **8.6** |
| Settings | 1.8 | 1.6 | 1.8 | 1.7 | 0.9 | 0.9 | **8.7** |
| Mini | 1.8 | 1.6 | 1.7 | 1.7 | 1.0 | 0.5 | **8.3 FAIL** |

Overall is the arithmetic mean of these seventeen surface totals, **8.6647**, rounded **8.66**. All sixteen main screens meet their threshold; Mini prevents overall acceptance. AI-template appearance remains **1.2/10**: restrained graphite, useful rows, no gradient/card-grid marketing ornaments, fabricated endorsement or decorative animation. Typography/native chrome remain consistent; small windows intentionally use outer scrolling. Planner/Projects/Memory retain sparse default states and occasional explanatory prose, explaining density deductions.

The five repaired main surfaces earn higher density points from actual pixel changes: Voice keeps status/devices/timings together at 1366 x 768; Calendar presents one disconnected explanation plus actual local dated tasks; Models uses one combined observed/configured model row, aligned fields and supported Refresh/detail/Mission navigation; Agents replaces nested capability scrolling with genuine six-item pagination; Screen awareness groups one truthful unavailable status with privacy/detail context. Its visual improvement is not proof of a capture/vision pipeline.

## Failed native Mini startup

**Severity: major startup interaction/diagnostic presentation. Owner: Worker 1.** `phase2-mini-cycle2/mini-idle-{600x420,640x480,782x528,900x650}-native.png` and all four `mini-discovery-*-native.png` visibly retain raw `ae(...).get_state is not a function` above the composer. The bridge is callable by the time the harness inspects it, but the initial UI error remains until a later action clears it. Four idle captures therefore are not healthy initial state. Later shared-channel, conflict and guarded-navigation frames do not contain this error and their functional checks remain valid.

Required bounded repair: wait for the actual native method to become callable before the initial state read, recover readiness without leaving a stale raw JavaScript error, preserve real failed-call reporting and the restricted bridge. Add an actual initial-frame regression before user interactions. The verification harness now records this error separately while continuing remaining controls; earlier fourteen successful checks did not assert absence of a stale initial error. No failed image was replaced or silently relabeled. Some Mini frames contain an unrelated Grammarly overlay; it was not changed or graded as HANNI.

## Genuine native/API checks

- Primary matrix: **64/64 capture checks PASS**, sixteen routes, four sizes, but automated layout success is not a visual grade.
- Mini: **14/14 existing functional checks PASS**, including global hotkey/refocus from another native foreground process, Escape, actual WS_EX_TOPMOST pin/persistence, conflict preservation/free alternative, five-method bridge, shared exactly-once ChatHub transport/Expand, guarded zero-request foreign navigation and retained offline draft. **Independent initial-state review FAIL**, as above; fixture reply transport does not prove real inference.
- Workspace: **59/59 PASS**, genuine authorized CRUD, exact task deletion with Cancel/confirm, stale draft rejection/retention, UUID retry identity, project notes/file references, exact original MemoryStore forget, notification execution/task Inspect, read/dismiss/preferences/Clear/dedupe, actual executable restart and fresh store persistence. The real temporary HTTP server is shut down for the final disconnected Save; draft remains and real store is unchanged.
- Repaired boundary: **all 101 actual due-task reminders** appear through real API and native Reminders count; repeated reads preserve IDs without duplicates. One seeded due task plus 100 real registry-gated test task creates, no mocked private writes. `notifications-101-reminder-boundary-native.png` independently opened.
- Genuine new view controls: six real Agent capabilities change with Next/Previous without inner overflow; local Calendar task link selects the exact stored task; unified Model details/Refresh/Mission navigation are exercised.
- Native lifecycle/security: **10/10 PASS**, maximize/minimize/restore, actual tray preference/hide/restore/Exit, persisted geometry, tokenless write 403, no main-window privileged bridge, blocked foreign popup/location with zero requests, default attached close leaves backend alive and never invokes write handlers.

Minimum probe requested 640 x 480 physical pixels at observed 125%; Windows enforced **800 x 600**, native content **626 x 420 CSS**. Actual `minimum-main-native.png` shows header, content, footer and Stop HANNI, and measured bounds place them within the viewport. This establishes the observed supported minimum, not forced 640 x 480 or untested 150% DPI coverage.

Independently opened new detail evidence includes the 101-reminder frame, exact delete dialog, actual-backend disconnected draft, real Agent pagination, unified Model details, and minimum native frame. Machine-readable checks retain every assertion. All verifier-launched native processes exited and GUI ownership was released to the coordinator. Final regression/live-controller proof for this package remains coordinator-owned and must be reported separately.

## Milestone acceptance limits

Separate reports `phase-2-1-cycle-2.md` through `phase-2-5-cycle-2.md` are checkpoint-ready. Observed agent/audit UI, persistent local workspace, unavailable Screen page, inactive Voice page and repaired notification center each meet their visual threshold. Actual independent agent runtime/approval/cancel, connected calendar provider/controller memory correction, live vision and acoustic voice tests remain unavailable or unverified. The Mini startup defect additionally blocks final whole-desktop acceptance.
