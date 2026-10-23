# Phase 2 independent native review, cycle 3

Reviewed 2026-10-09. **Visual gate PASS: 8.69/10 overall, every primary surface at least 8.6, AI-template appearance 1.2/10.** The genuine Mini startup failure from [cycle 2](phase-2-cycle-2.md), checkpoint `cbcf871`, is repaired and independently rechecked. This is visual/interface acceptance, not a declaration that every requested runtime feature is complete: actual screen-aware interaction remains BLOCKED and live acoustic voice verification remains PARTIAL.

## Evidence scope and artifact provenance

The final bounded change affects only Mini native-method readiness/error recovery (`mini.tsx`, `mini_bridge.ts`); main layouts, feature sources, CSS, backend and native wrapper are unchanged from the accepted sixteen-screen cycle-2 review. All **64 actual main frames** at 1920 x 1080, 1440 x 900, 1366 x 768 and compact900 x650 physical pixels are retained from `data/hanni-desktop-review/phase2-primary-cycle2/`. They were independently inspected, not regenerated or mislabeled as final-bundle captures. Original cycle-2 app.js SHA is `0b1c60693e3a72812c8942beb39879272a56b1519f1b85f17649f26db143440c`; its hash differs from the final rebuilt bundle because of the isolated Mini fix.

The final packaged executable was genuinely relaunched against the same isolated real-store fixture. **All fifteen new Mini/state frames** in `data/hanni-desktop-review/phase2-mini-cycle3/` were independently opened: four fresh initial idle sizes, four discovery sizes, initial/discovery aliases, shared conversation, expanded full Conversation, actual shortcut conflict, offline draft and post-blocked-navigation state. Initial frames precede pin/chat/shortcut-settings interactions. Windows observed120 DPI /125%, physical Mini sizes600 x420,640 x480,782 x528,900 x650. These are real native window pixels, not CDP screenshots or mockups; CDP drives DOM interactions. No untested150% DPI claim.

Final reviewed SHA-256 from `mini-results.json`:

- Executable: `9bf90dc1438e1776369f668117d88c2a5f76a33fc6f796c4d9f41a8a7e586263`
- app.js: `e2498da3a1446b52840b60000edba7d538ebe33cba72ff6f952073906e5d6dfe`
- style.css: `1054414a519c3262a9abde5850080c07f272c1cfbe1d1743d5cd940b326f1603`

Executable and CSS are byte-identical to cycle2; the wrapper serves the final local compiled bundle. Genuine cycle-2 workspace59/59, lifecycle10/10 and sixteen-route matrix results remain applicable to unchanged code. Their specific artifact provenance stays in the earlier report. No result is presented as a newly rerun unchanged check.

Fixture disclosure is unchanged: genuine original registry-gated local workspace/MemoryStore/audit/notification persistence with synthetic review record content; explicitly empty offline Google vault; synthetic telemetry/device/model samples and ChatHub reply; microphone inactive/input zero and voice runtime unbound. Verifier did not start a live model, capture audio, execute SSH/node power/terminal, access a provider or invoke application screen analysis. Independent coordinator live controller/telemetry proofs remain separately attributed.

## Exact user Section 3 weighted scores

Required category maxima are2/2/2/2/1/1, added directly to10. These scores supersede acceptance for the failed prior candidate, not its historical images or defect record. [rubric-correction.md](rubric-correction.md) explains earlier historical custom-weight mistakes; no custom-weight conversion is used here.

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
| Mini | 1.8 | 1.6 | 1.7 | 1.7 | 1.0 | 0.9 | **8.7** |

Mean of17 totals is8.6882, rounded **8.69**. Mini interaction points recover from0.5 to0.9 because initial readiness is now clean and genuine native controls/security checks succeed. Density remains1.6: compact idle/search composition is clear, but larger resized Mini has broad idle space and its smallest discovery header still sits near the sole result scrollbar. These are minor deductions, not hidden defects. Main density/spacing deductions and concrete repair observations remain as documented in cycle2. Native chrome, restrained accents/rows and lack of marketing ornaments support AI-template **1.2**. A third-party Grammarly overlay appears in some Mini captures; it was not changed or scored as HANNI.

## Actual final Mini verification

**15/15 PASS**, no defects, including the added initial-state check. Four initial native frames show Ready/Microphone idle, disabled unbound voice controls, enabled Pin/Expand, visible composer/Send and no raw bridge error or startup alert. All four discovery frames have exactly one results scroll area and visible composer/footer, with no horizontal document overflow. The actual first global shortcut focuses Mini from another foreground native application before window preference/chat interactions.

Existing controls remain genuinely exercised: global refocus, Escape, actual WS_EX_TOPMOST pin/unpin and persisted preference, OS shortcut conflict retaining the old chord, available alternate shortcut, keyboard discovery preparing a draft without execution, exactly-once shared ChatHub submit/Expand, unauthorized chat rejection, allowlisted five-method Mini bridge with no main privileged bridge, honest offline Send disable/draft retention, foreign popup/location zero HTTP requests preserving trusted document/base URL and callable native bridge. Shared fixture reply proves transport only, not real controller inference. Connection-reset traces on scoped review-process teardown are fixture cleanup, with final assertions passed.

All verifier-launched GUI processes exited; Win32 process audit found no HANNI OS.exe before ownership release. Coordinator can run actual model/controller/telemetry final proof without overlapping review windows. Final full Python/routing/backend preservation results and those live captures are coordinator-owned and must be appended with exact provenance before declaring all engineering gates verified.

Final live follow-up is now independently frame-reviewed in [phase-real-controller-review.md](phase-real-controller-review.md): coordinator6/6 actual configured-model/controller checks and7/7 actual local/all-eight-node telemetry checks pass on this exact final executable/bundle. All four final native model/telemetry images were independently opened. No acoustic or screen-vision claim follows from these successful read-only runs; final full-regression results remain coordinator-owned.

## Milestone interpretation and remaining capability proof

Final milestone reports `phase-2-1-cycle-3.md` through `phase-2-5-cycle-3.md` use the user's actual acceptance criteria. Earlier reports labeled agent/workspace overall partial for unsupported optional runtime extras; that is a conservative scope interpretation, not a newly found test failure. The brief explicitly permits read-only cancellation where unsupported and optional native Windows notifications. Missing autonomous workers or unobserved optional balloons therefore do not prevent accurate existing-agent observation or center acceptance. Similarly, actual tasks/projects/supported workspace persistence across close/reopen passes the stated2.2 acceptance; untested connected-provider flows remain disclosed subfeature limits.

- **2.1 PASS** for truthful existing controller activity/capabilities/recorded permission decisions, redaction and exact execution inspection; unavailable fields remain explicit.
- **2.2 PASS** for independently verified persisted tasks/projects/supported local workspace and exact authorized MemoryStore deletion. Connected calendar provider and controller-mediated memory correction were not exercised and are not claimed verified.
- **2.3 BLOCKED** for actual backend screen-aware interaction: no connected capture/vision pipeline exists. Truthful unavailable controls/page pass interface review only.
- **2.4 PARTIAL**: truthful real state adapter/unbound controls/interface and audio regressions are available; required acoustic wake/transcription/TTS/barge-in/latency proof has not run. No first-audible response sensor exists.
- **2.5 PASS** for actual event-linked persistent center, dedupe/preferences/Inspect and repaired all101 reminders. Optional native balloon rendering remains unverified.

Visual acceptance does not make the whole Phase1+2 project complete while the required2.3 and2.4 runtime proof is blocked/partial. Preserve these limits in the final handoff; no fabricated vision or acoustic measurements.

## Coordinator regression and preservation attestation

Coordinator-run final frozen Python suite: **860 passed, 2 skipped, 17 subtests**,
57.95s. The subsequent repair changes only Mini frontend readiness, not Python;
its type/production build, two meaningful partial-injection regressions and 53
native tests passed. The existing browser harness passed all 24 checks at twelve
widths with no JavaScript/CSP/external errors. No unchanged passing suite is
represented here as newly rerun by the verifier.

The original routing benchmark retains 1,131 cases, 1,129 strict passes (99.82%)
and average 99.59, with the same two baseline failures. Eight changed rows contain
only the existing email window's evaluation-clock timestamps; selections/scores
are unchanged. Of 144 existing baseline backend files, 138 remain byte-identical;
the six narrow integration boundaries and additive modules are documented in
[the final verification](../HANNI_PHASE12_FINAL_VERIFICATION.md). No training or
expected benchmark files were modified. Final source-preservation and artifact
manifests remain under `data/hanni-phase12-review/`.

Engineering evidence is complete for the stated supported milestone scope.
Remaining vision/acoustic blockers and optional/provider unverified subflows
remain explicit, so this attestation does not declare the entire roadmap complete.
