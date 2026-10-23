# Phase 2 independent native review, cycle 1

Reviewed 2026-10-09, candidate `4b046d0`. **Corrected user-rubric visual gate FAIL: 8.63/10 overall; five screens below 8.6; AI-template score 1.2/10.** See the authoritative [rubric correction](rubric-correction.md). The originally published equal-weight 8.66/PASS assessment below is superseded historical scoring. **Whole-feature acceptance is not PASS:** screen analysis is blocked, live voice remains unverified, and notification ingestion omitted reminders beyond the first 100. Coordinator checkpoint `ddbfa2a` records the genuine notification failure before its bounded repair.

## Actual evidence and isolation

The real packaged Windows executable was driven through WebView2 CDP; screenshots are foreground Win32-framed `ImageGrab` pixels, not browser screenshots or mockups. All 64 primary frames were independently inspected through per-screen four-frame contact sheets, with full individual frames used for readable state/detail inspection. Required physical sizes were 1920 x 1080, 1440 x 900, 1366 x 768, and 900 x 650, Windows 120 DPI / 125%. Matrix checks passed with no horizontal document overflow, JavaScript errors, or external WebView requests.

Authoritative captures are in ignored `data/hanni-desktop-review/phase2-primary-cycle1-isolated/`, named `<route>-<width>x<height>-native.png`, with `capture-results.json` provenance. Contact sheets are inspection aids made only from those actual frames. The earlier `phase2-primary-cycle1/` matrix inherited connection metadata from the user's Windows Google credential vault despite an isolated data directory. No calendar Refresh or provider request occurred; the entire matrix was recaptured after injecting an explicitly empty vault through the existing GoogleAccess offline seam. No user credential was changed. The earlier disconnected disclosure is superseded by the corrected capture.

Workspace records use an actual isolated AppConfig/data directory, original DashboardServer token/Host/Origin gates, DesktopFeatures, ToolRegistry, migrated task/project/note/link store, original MemoryStore, real redacted audits and persistent notifications. Record content is explicitly synthetic review content; private CRUD responses are never mocked. Telemetry, device enumeration, model residency and ChatHub reply content are synthetic. Voice is unbound/inactive with input zero; no microphone, live model, SSH, node power, terminal, remote calendar or screen analysis ran in this review.

Reviewed SHA-256:

- Executable: `87ef933bb798f70d22dea5beb1c3d37cd79e4160e8c32d0a80bce385fbf2961a`
- app.js: `103a24149e2430a7dc677e7f28f290a12689691e7b2203ccafc0e7939779ee42`
- style.css: `134bdc47d93cbf7818950f66284fb479851a97384e52a505df9bf1bc8867c0a4`

## Superseded historical custom rubric

This original equal-weight table did not follow the user's Section 3 weights and is preserved transparently as historical assessment only. It must not be used for acceptance. The [authoritative user-rubric reassessment](rubric-correction.md) uses the actual captured pixels with the exact 2/2/2/2/1/1 categories and records the failed per-screen gate.

| Surface | Legibility | Hierarchy | Spacing | Density | Consistency | Interaction clarity | Overall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Home | 9.0 | 8.8 | 8.5 | 8.5 | 8.8 | 8.6 | **8.7** |
| Conversation | 9.0 | 9.0 | 8.8 | 8.4 | 8.9 | 8.7 | **8.8** |
| Voice | 8.9 | 8.8 | 8.4 | 8.2 | 8.7 | 8.6 | **8.6** |
| Planner | 8.9 | 8.7 | 8.3 | 8.2 | 8.8 | 8.7 | **8.6** |
| Tasks | 9.0 | 8.8 | 8.4 | 8.4 | 8.8 | 8.8 | **8.7** |
| Calendar | 8.9 | 8.7 | 8.3 | 8.1 | 8.8 | 8.8 | **8.6** |
| Projects | 8.9 | 8.7 | 8.3 | 8.2 | 8.8 | 8.7 | **8.6** |
| Memory | 8.9 | 8.7 | 8.4 | 8.2 | 8.7 | 8.7 | **8.6** |
| Mission Control | 8.9 | 8.7 | 8.3 | 8.8 | 8.8 | 8.7 | **8.7** |
| Models | 8.9 | 8.7 | 8.3 | 8.2 | 8.8 | 8.7 | **8.6** |
| Agents | 8.9 | 8.7 | 8.3 | 8.3 | 8.7 | 8.7 | **8.6** |
| Cluster | 8.9 | 8.9 | 8.8 | 9.0 | 8.8 | 9.0 | **8.9** |
| Activity | 9.0 | 8.8 | 8.4 | 8.6 | 8.8 | 8.6 | **8.7** |
| Screen awareness | 8.9 | 8.7 | 8.3 | 8.1 | 8.8 | 8.8 | **8.6** |
| Notifications | 8.9 | 8.7 | 8.3 | 8.2 | 8.7 | 8.8 | **8.6** |
| Settings | 8.9 | 8.7 | 8.6 | 8.4 | 8.8 | 8.8 | **8.7** |
| Mini | 8.9 | 8.8 | 8.3 | 8.3 | 8.7 | 8.6 | **8.6** |

The interface retains clear native chrome, restrained graphite surfaces, legible rows, distinct headings, honest empty/unavailable states and accessible primary actions. It avoids gradients, glass panels, fabricated statistics/logos/testimonials, decorative animation and repeated feature-card grids. Cluster is the strongest dense surface: nine named nodes remain visible at 1366 x 768, with SSH-verified telemetry distinguished from Tailscale-only presence and Yunjin repair status. Compact windows use intentional vertical scrolling and a collapsed navigation drawer.

Minor remaining polish: sparse Calendar/Projects/Models states have broad unused space at large sizes; Agents exposes both page and capability-list scrolling; small voice windows require scrolling to timing details; Mini's 600 x 420 discovery hint touches the result scrollbar. These are disclosed deductions, not critical blockers. Some Mini frames contain a third-party Grammarly desktop overlay; it was neither modified nor graded as HANNI design.

## Native interactions

`data/hanni-desktop-review/phase2-workspace-cycle1-verified/results.json`: **42/42 PASS**. Actual UI saves task/project/note/file-reference records; edits keep stable identity; a concurrent real API save rejects an old native editor fingerprint while retaining its draft; UUID retry returns the identical result with one task and rejects changed payload. All seven private GET routes reject a missing token with 403. Private task/note content is absent from real activity audits. Canceling project deletion and memory forget preserves records; confirmed forget removes exactly one original MemoryStore record. Notification Inspect selects the exact task and opens the exact recorded execution; Mark read, Dismiss, category preference, Clear Cancel, confirmed Clear, persistent history and no notification feedback loop all pass. A fresh store/adapter reopens persisted data; the actual executable is terminated and restarted while the isolated backend survives, and reads the same saved task ID.

Inspected native detail/dialog frames include `task-create-dialog-native.png`, `task-stale-error-native.png`, `project-populated-detail-native.png`, `memory-exact-forget-dialog-native.png`, both `notification-inspect-*-native.png`, `notifications-clear-confirmation-native.png`, and `notifications-empty-after-clear-native.png`. The native store harness's earlier failures were verification-only locator ambiguities and synchronous checkbox assumptions; the final run awaits real HTTP-backed state and passes without application changes.

`data/hanni-desktop-review/phase2-mini-cycle1/results.json`: **14/14 PASS**, including genuine global hotkey from another native foreground app, refocus of an already-open Mini, native Escape, OS shortcut conflict with old shortcut retained, free alternate shortcut, native topmost/persisted Pin, restricted five-method window bridge, unauthorized chat rejection, zero-request foreign popup/navigation guard with bridge preserved, shared-channel exactly-once submission/Expand, offline draft retention, four physical idle/discovery sizes, sole discovery scroll area and visible disabled voice actions. All 15 Mini/state frames were independently opened. Synthetic ChatHub reply success establishes shared transport, not genuine assistant inference/controller behavior.

## Milestone outcomes

Separate checkpoint-ready reports are `phase-2-1-cycle-1.md` through `phase-2-5-cycle-1.md`. No successful visual score is used to imply an unsupported feature is complete.

- 2.1: **PARTIAL** overall. Existing controller/capability/audit observation and exact execution inspection PASS; independent autonomous agents, live approval queue and cancellation are not exposed by the authoritative backend.
- 2.2: **PARTIAL** overall. Tested persistent local workspace and exact memory deletion PASS. No live authorized calendar read/write or genuine controller memory correction was exercised by this fixture.
- 2.3: **BLOCKED** for actual visual understanding; honest disabled status page PASS. No connected capture/vision pipeline exists in this repository.
- 2.4: **PARTIAL**. Disabled/unbound controls and missing-measurement reporting PASS; actual spoken wake, live capture/mute/barge-in and latency require a coordinated real voice session and spoken input. No first-audible sensor exists; wake metric measures utterance-end to wake decision, not acoustic wake onset.
- 2.5: **FAIL** for the candidate's reproduced 100-of-101 due-reminder omission. Normal-size notification native controls/persistence PASS. OS native balloon rendering was not independently observed. The coordinator is repairing the ingestion boundary after the failed-cycle checkpoint; acceptance requires a fresh affected native/API run.

Coordinator reports baseline/final candidate backend **858 passed, 2 skipped, 17 subtests** and unchanged 1131-case routing / 99.82% strict outcome. Those are coordinator-run results, not independent verifier executions. No critical rendered UI or guard defect was found. All verifier-launched native processes have exited; no externally owned process or credential was changed.
