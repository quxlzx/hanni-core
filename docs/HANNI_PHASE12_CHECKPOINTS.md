# HANNI OS Phase 1 and Phase 2 checkpoints

User brief: full implementation, real delegation, milestone verification and local
checkpoints. Starting state is verified local commit `3b83267`. No push/publication.
Existing user databases, credentials, weights and unrelated root files are preserved.

## Audit checkpoint, 2026-10-09

Baseline: **788 passed, 2 skipped, 17 subtests passed**, 48.88s.
Frontend TypeScript check and production build passed. Previous independent native
acceptance is 8.78 overall, all five screens >=8.7, AI-template 1.14; these scores
describe the previous release and do not grade new Phase 1/2 features.
Backend source hashes and routing baseline are saved in ignored
`data/hanni-phase12-review/` before integration edits.

Exactly three actual subagents, resumed from the preceding implementation:

| Agent | File ownership |
| --- | --- |
| Worker 1 | `desktop/`, desktop tests, `workspace.tsx`, `style.css`, `main.tsx`, shared screen types, new Mini components, native documentation |
| Worker 2 | Cluster/screens and new feature components/styles; new `dashboard/productivity.py` and its store tests |
| Independent verifier | Verification-only harnesses/tests/reports; no application code |
| Main | Backend API integration/adapters, narrow live controls, integration tests/docs/checkpoints, packaging coordination |

Workers share the verified checkout with nonoverlapping ownership. Native builds
and GUI verification are coordinated sequentially to prevent DLL locks and
occluded captures. Milestones freeze before review and local commit.

## Verified architecture and feature gaps

- Controller: CLI keyboard/attend loops consume the existing ChatHub inbox;
  TextSession, MCP/ToolAwareSession and MemoryAwareSession retain authority.
- Capabilities: `build_default_registry`, `ToolRegistry.execute`, MCP host
  select/call, shared mutation lock, profile/confirmation/emergency-stop/audit gates.
  Mini submits to the same `/api/chat`; it has no second router or tool bridge.
- Models: existing registry/client/runtime/manager and configured local supervisor.
  No model execution or routing rewrite is authorized or needed.
- Memory: configured MemoryStore SQLite, deterministic search, provenance, keyed
  facts, verified deletion and cleanup; reuse it rather than a new memory database.
- Speech: microphone/desktop audio, VAD, FasterWhisper, relevance/wake classifier,
  existing attentive loop/TTS/barge classifier. Current telemetry publishes input
  amplitude and interaction state, not output amplitude or an application mute API.
- Desktop: already verified pywebview/WebView2/PyInstaller wrapper, tray, native
  geometry/preferences, same-origin guards and owned-monitor lifecycle. No Rust/MSVC
  toolchain exists here. Extend this supported wrapper.
- Telemetry: existing local/device model state and one-second fixed-roster SSH/
  Tailscale collector. CPU/RAM/uptime/processes supported; node GPU/storage are not.
- Activity: existing bounded/redacted tool audit and real chat queue/state. No
  independently registered autonomous agent runtime or universal cancellation API
  is wired in this repository; `jobs.py` definitions alone do not establish one.
- Tasks: existing `TodoStore` in `todos.sqlite3`, used by controller tools. Projects
  and priorities need additive workspace metadata; retain original task schema.
  `project.test` is code verification, not a personal project workspace.
- Calendar: existing GoogleAccess/Calendar capabilities and local credential vault.
  Reads require the current authorization; creates go through existing conversation
  and permission gates. Explicit refresh can cache supported events locally.
- Screen awareness: retention/exclusion configuration exists, but **no capture or
  vision pipeline is implemented or configured**. A privacy/status interface can
  report this accurately; analyzing the screen is blocked until an actual supported
  local vision capability exists. Do not fabricate capture or inference behavior.
- Notifications: existing job notifier covers its registered adapter; persistent
  notification history/preferences need an additive local store and actual event
  projection with deduplication/rate limits.

## Integration boundaries

New personal workspace writes use a fixed operation adapter through the existing
ToolRegistry validation, permissions, Safe Mode, mutation lane and audit gates.
There is no generic execution endpoint. Sensitive reads require the existing
per-launch token; all endpoints retain Host/Origin/cross-site guards. Workspace
schema changes are additive/versioned in the existing task database. Memory stays
separate, with explicit confirmed deletion and concurrency checks; corrections
continue through supported conversation commands. Native Mini APIs control only
window visibility/pinning/preferences, never system tools.

## Remaining work and resume

Phase 1: independently verify existing shell, revised cluster, actual Mini global
hotkey/secondary native window, then save its checkpoint. Phase 2: agents, persistent
workspace, screen status/actual blocker, live voice controls/state, notification
center, with feature-level validation and independent native reviews. Rebuild the
real executable only when no review client is open. Preserve truthful PARTIAL/
BLOCKED statuses where required live hardware or capabilities are absent.

## Phase 1, implementation/review cycle 1: FAIL

The actual new executable was built and inspected. Twenty primary-screen native
frames passed visual review: Home 8.7, Conversation 8.8, Mission Control 8.7,
Cluster 8.9, Settings 8.7. Mini idle and failure frames were also inspected;
Mini **8.0**, overall six-surface mean 8.63, AI-template approximately 1.1.
The per-screen minimum and functional acceptance **fail**. Previous scores are
not substituted for Mini's actual failing score.

Actual global shortcut activation from a separate foreground application,
input focus, Escape, missing-token rejection and foreign-request blocking passed.
A blocked foreign navigation clears Mini's pywebview API bridge, leaving its
controls unavailable. Pin/shared conversation expansion/hotkey conflict/offline
draft checks remain unverified; no separate pin failure is claimed from the
downstream missing bridge. Report: [Phase 1 cycle 1](desktop-reviews/phase-1-cycle-1.md).

Phase 1 files: native Mini/hotkey source/tests, Mini frontend/entry point, revised
cluster density/telemetry labels, shipped compiled assets and verification harnesses.
Focused desktop/dashboard/store checks: 102 passed. Frontend check/build passed.
Phase 2 adapters/store/new feature screens are being prepared in separate owned
files; they are not yet mounted or accepted as completed milestones.

Resume: preserve this failed-cycle checkpoint, repair canceled-navigation bridge
lifecycle, marshal pin state on the native UI thread and restore Mini when another
application owns focus. Rebuild only after GUI release, independently repeat all
remaining Mini controls and screenshots, then checkpoint the passing Phase 1.
The verifier has released GUI ownership; no review executable remains running.

## Phase 1, implementation/review cycle 2: FAIL

Canceled foreign navigation now preserves the restricted Mini bridge. Native pin
changes run on the UI thread and the global hotkey refocuses an already visible
Mini from another application. Forty-six native wrapper tests passed; the rebuilt
executable passed **all 12** independently exercised Mini controls. Foreign HTTP
requests remain blocked and both the document origin and bridge survive afterward.

The verifier inspected twenty refreshed primary frames and ten Mini/state frames.
The five primary scores remain 8.7/8.8/8.7/8.9/8.7. Mini is **8.4**, overall 8.70,
AI-template 1.1: **FAIL** against the required per-surface 8.6. Discovery has an
empty history scroll strip above a separate result scroller. Report:
[Phase 1 cycle 2](desktop-reviews/phase-1-cycle-2.md).

Resume: replace that empty strip with one flexible discovery results region,
retain the composer, rebuild and repeat independent native verification. Phase 2
routes remain unmounted until this cycle passes. Full Python preparation checks
reported 846 passed, 2 skipped and 17 subtests, with two failures under investigation:
the new voice test inherited global speaking state and an unchanged shadow-server
test hit a Windows connection abort. Neither result is presented as a passing suite.

## Phase 1, implementation/review cycle 3: PASS

Mini discovery now has one flexible results region, no empty history strip, and
keyboard selection remains visible. Frontend type check/build and 46 native unit
tests passed. The rebuilt executable passed **13/13** actual Mini checks and
**9/9** native lifecycle/security checks. The latter harness was corrected to
select the full application's CDP page now that two native windows exist.

The verifier opened twenty refreshed primary frames and fifteen Mini/state
frames at the required physical sizes. Home 8.7, Conversation 8.8, Mission 8.7,
Cluster 8.9, Settings 8.7 and Mini **8.7**; overall **8.75**, AI-template **1.1**.
The discovery defect is closed at all four compact sizes. Report:
[Phase 1 cycle 3](desktop-reviews/phase-1-cycle-3.md).

The source/container/native safety and visual cycle passes. Disclosed synthetic
chat replies verify transport, not live configured-model inference or spoken voice.
All review windows/processes were closed. The full Python suite after voice test
isolation passed **848 tests, 2 skipped, 17 subtests**, 56.69s; the unchanged
shadow-server test passed on rerun. Two further focused adapter regressions for
muted queue waiting and repeated model-failure cooldown also pass (47 focused).

Resume: mount the prepared Phase 2 feature screens in the shared three-area shell,
add native notification observation and Mini voice controls, publish the exact
implemented screen contract, then independently review Agents/Workspace/Screen/
Voice/Notifications and save each milestone status. Screen analysis remains
blocked by the absent capture/vision pipeline; live spoken voice remains unverified.

## Phase 2 integrated implementation candidate: verification pending

All sixteen real routes are mounted in Assistant / Workspace / Mission Control.
One coherent build is used because the shared navigation, persistence, record
inspection and notification targets depend on one another. Independent acceptance
will still be reported and checkpointed separately for milestones 2.1 through 2.5.

Implemented: actual controller/capability/audit activity, tasks/projects/notes/
links in the existing task database, authorized cached calendar, existing memory
search and exact deletion, capture-unavailable status, bound attentive-session
voice controls and scalar observations, persistent notification history and an
opt-in rate-limited native observer. Native Mini uses the same protected voice
routes; model residency remains an actual read-only projection.

Changed groups: `frontend/src/` shared shell plus feature components; native
`desktop/main.py` and `notifications.py`; new dashboard `features.py`,
`productivity.py`, `voice.py`; narrow existing API/projection, CLI observation,
memory concurrency, private audit and undated-task changes. See
[integration and recovery](HANNI_WORKSPACE_INTEGRATION.md) for justification and
limitations. Tests and verification harnesses are separate from application code.

Validation: **858 passed, 2 skipped, 17 subtests**, 54.47s. Frontend type checking
and production build passed (337.38 kB JS / 57.06 kB CSS), and the native executable
rebuilt successfully. The original five-screen browser smoke test passed all its
existing checks at twelve widths (320 through 1920), with no JavaScript, CSP or
external-request errors. The 1,131-case routing benchmark retains 99.82% strict
pass and 99.59 average with the same two baseline failures. Its eight differing
rows contain only evaluation-clock date-window timestamps, with scores/selections
unchanged. Of 144 baseline backend files, 138 remain byte-identical and the six
changes are the documented integration boundaries.

Independent native verification is running on the frozen candidate. The verifier
is using genuine protected HTTP/store writes in temporary data. Windows Credential
Manager is independent of `data_dir`; review calendar credentials are explicitly
isolated with the existing empty-vault seam. First captures inherited connection
metadata only; no Refresh or provider request occurred, and affected frames are
being replaced. This is a disclosed fixture correction, not a production defect.

Known unfinished acceptance: actual screen analysis **BLOCKED** (no capture/vision
pipeline); real spoken voice and audible-onset timing **unverified**; Mini's real
configured-model/process-tool proof is scheduled separately from synthetic reply
transport. Native optional notification delivery still needs actual package review.
No scores for new Phase 2 surfaces are claimed at this candidate checkpoint.

Resume: complete independent native screen/interaction reviews, repair any actual
defects and rebuild only after GUI release; run the isolated existing-controller
Mini query and real telemetry check, then save per-milestone status and final handoff.

## Phase 2, notification implementation/review cycle 1: FAIL

The verifier's actual native matrix captured 64 frames without layout, JavaScript
or external-request failures. Genuine registry/store/HTTP-backed workspace checks
passed **42/42**, including restarting the executable with the same saved task ID,
fresh adapter/store reopen, stale edit/draft retention, exact UUID retries, private
GET rejection, exact task/audit inspection and persisted notification actions.
Final Mini controls passed **14/14**, with inactive voice controls explicitly disabled.
Image grading and separate milestone reports remain pending; capture success is
not a visual score.

Main reproduced a real notification defect with a new boundary regression: 101
valid due tasks yield only 100 reminders because the adapter truncates the source
list before ingestion. Milestone 2.5 cannot pass with this omission. The failing
test is preserved at this checkpoint; no expected value was relaxed.

Resume: ingest all bounded source events in batches of at most 100, retaining
deduplication, rate limits and the 1,000-entry history cap. Rerun the regression and
affected native notification/workspace checks, obtain final independent image
scores, then checkpoint the next cycle. Verifier GUI ownership has been released.

## Corrected visual acceptance checkpoint: Phase 2 FAIL

Coordinator review caught a real scoring-method error: earlier Phase 1/2 tables
used six equal-weight custom dimensions instead of the user's exact weighted
rubric. The original published scores above are historical and **superseded** as
acceptance scores. Source, actual captured pixels and functional checks remain
valid. The verifier independently reassessed those actual frames using Typography/
hierarchy 2, Layout/density 2, Spacing/consistency 2, Identity 2, Desktop 1 and
Interaction 1; no score conversion was used to force a pass. Authoritative report:
[rubric correction](desktop-reviews/rubric-correction.md).

Corrected Phase 1 cycle 3: **PASS, 8.77**, all six surfaces at least 8.7, AI 1.1.
Corrected Phase 2 cycle 1: **FAIL, 8.63**, AI 1.2. Its mean exceeds 8.5, but Voice
8.5, Calendar 8.5, Models 8.5, Agents 8.5 and Screen 8.4 miss the 8.6 per-screen
minimum. Mini is 8.7; the other ten screens are 8.6 or better. Detailed deductions
are grounded in actual four-size screenshots, not source estimation.

The 101-reminder omission is now repaired through bounded ingestion batches;
47 affected tests passed and the complete suite passed **859 tests, 2 skipped,
17 subtests**, 56.68s. Native reminder review after repair is still pending. Mini's
real configured local model/controller proof separately passed **6/6**: actual
`process.top_memory`, one submission, shared expanded reply, attached-controller
survival and owned-model shutdown with external model PID sets unchanged. A
verification-script cleanup argument error was fixed before its successful rerun;
the first attempt is not counted as passing.

Remaining functionality statuses: observed-controller/audit interface implemented,
full agent runtime unavailable; local workspace persistence/deletion verified,
provider/controller correction flows pending; screen analysis blocked; spoken
voice timings unverified; notification native balloon visibility unverified.

Resume: Worker 1 repairs actual Models composition and avoids reading long chat
history for native token-only requests via the existing sparse history cursor.
Worker 2 repairs Voice/Calendar/Agents/Screen density and useful supported actions,
without inventing runtime or screen data. Freeze, type/build/test/package, repeat
independent weighted native review and notification checks, then checkpoint each
milestone. Full task acceptance remains incomplete while documented blockers persist.

## Phase 2, implementation/review cycle 2: FAIL

The five previously failing main screens were repaired without changing their
capability or permission contracts. Models now combines matching configured and
resident records; Voice uses compact actual state and measured input; Calendar
includes genuine local task deadlines; Agents paginates actual capabilities;
Screen keeps unavailable capture explicit and technical details expandable.
Native identity/notification requests use the existing sparse chat cursor so
large conversation history cannot overflow a token-only read. Due-task ingestion
now processes all bounded entries in batches of 100.

Validation on this frozen source: **860 passed, 2 skipped, 17 subtests**, 57.95s;
frontend type check/build and native packaging passed; all 24 original browser
checks passed across twelve widths. Independent native review captured 64 main
frames, passed **59/59** genuine workspace checks (including 101 reminders,
deduplication and restart persistence), **14/14** Mini control checks, and
**10/10** lifecycle checks. At observed 125% Windows scaling the requested 640 by
480 minimum probe was correctly constrained to 800 by 600 physical pixels; the
header, main content, footer and Stop HANNI remained visible.

The exact weighted screenshot review nevertheless **FAILS**: all sixteen main
routes are at least 8.6, but Mini is **8.3**. The overall mean is **8.66**, AI
appearance **1.2**; passing the mean does not waive the per-screen minimum. Actual
idle/discovery captures expose a raw `get_state is not a function` startup error
that remains after native controls become available. React observes the injected
API object before its five methods are callable; a successful later poll does
not clear that error. Later native-control success does not invalidate this
visible startup defect.

Changed groups: scoped feature components/styles, shared Models refresh,
`desktop/main.py` sparse identity reads, notification batching and regressions,
compiled frontend, native review/controller/telemetry harness improvements.
Detailed independent evidence: `docs/desktop-reviews/phase-2-cycle-2.md` and
`data/hanni-desktop-review/phase2-mini-cycle2/mini-idle-*-native.png`.

Resume: wait for all five Mini API methods before calling native controls; keep
recoverable window-status errors separate from conversation errors and clear
them on a successful status read. Add a partial-injection readiness regression,
build/package, and independently repeat all four Mini screenshot sizes plus
native interactions. Preserve the accepted main-route evidence. Then rerun the
real configured-model/controller and eight-node telemetry proof on the corrected
artifact and save per-milestone statuses. Screen analysis remains blocked by the
absent backend pipeline; spoken voice remains unverified.

## Phase 2, implementation/review cycle 3: visual PASS

Cycle 2 is preserved at `cbcf871`, including its failed Mini frames. The bounded
repair changes only `frontend/src/mini.tsx`, adds `mini_bridge.ts` and two meaningful
readiness regressions, and rebuilds the production JavaScript. Mini waits until
all five native methods are callable; successful reads clear only recoverable
window-status errors, preserving conversation/voice failures. Native capabilities
and permissions are unchanged. The corrected portable application rebuilt in
8.8 seconds. Type/build, the two readiness regressions and 53 native tests passed.

Independent cycle 3 acceptance: **8.69/10**, all seventeen surfaces **at least
8.6**, Mini **8.7**, AI appearance **1.2**. The exact 2/2/2/2/1/1 user rubric is
used. All fifteen new Mini/state frames were opened and **15/15** native Mini
checks passed, including initial healthy state before interactions. The sixteen
unchanged main surfaces retain their independently inspected 64 cycle 2 frames,
with prior bundle provenance explicitly disclosed. No failed frame was overwritten.
See `docs/desktop-reviews/phase-2-cycle-3.md` and its five milestone reports.

Final coherent-artifact live proofs: **6/6** original configured-model/controller
checks passed, including real `process.top_memory`, one Mini submission, the same
expanded local-model reply and ownership-preserving close/shutdown. **7/7** real
telemetry checks passed with native percentages for all eight active nodes,
Yunjin unprobed under repair, and graceful owned-monitor cleanup. The independent
verifier opened all four final live-proof frames. External model PID sets remained
unchanged. No microphone, provider write, node power or terminal was invoked.

Final preserved Python source passed **860 tests, 2 skipped, 17 subtests**, 57.95s;
only the frontend readiness patch followed this full suite. Native workspace
**59/59**, lifecycle **10/10**, original browser **24/24** at twelve widths and
all 101 reminders retain valid evidence. Existing routing remains 1,129/1,131
strict passes, 99.82%, average 99.59, with the same two baseline failures. Of 144
original backend files, 138 remain byte-identical; six integration boundaries are
documented. No training/expected evaluation files were changed.

Milestone acceptance is now assessed against the actual brief rather than extra
runtime requirements: **1.1/1.2/1.3/2.1/2.2/2.5 PASS**, **2.3 BLOCKED** (no capture/
vision backend), **2.4 PARTIAL** (live spoken/acoustic verification absent). The
brief allows read-only unsupported agent cancellation and optional native balloons;
their absence does not invalidate accurate observed activity or event-linked center
acceptance. Connected-provider calendar/controller correction/file flows and OS
balloon appearance remain explicitly unverified. This criterion correction is
not a new feature or proof of those subflows.

Final artifact SHA-256 and source-preservation manifests are retained under
`data/hanni-phase12-review/`. The portable directory contains no model weights;
the executable remains `dist/HANNI OS/HANNI OS.exe` with its `_internal` directory.
Actual selected before/after PNGs are copied unchanged into
`docs/desktop-reviews/images/`. Final setup, precise limitations and continuation:
`docs/HANNI_PHASE12_FINAL_VERIFICATION.md`.

Resume from these saved implementations. Add an authoritative local capture/vision
pipeline before enabling Analyze, and coordinate the original voice session with
spoken wake/TTS/barge-in plus actual audible-onset measurement. Preserve data,
permission gates and recorded benchmark expectations. The whole roadmap is not
complete while those required milestones remain blocked/partial.

## Owner-requested cluster reboot repair

Reboot now uses the requested `/usr/bin/systemctl -i reboot`, with existing
authorized root access or non-root sudo. The supplied credential is saved for
the eight active nodes in Windows Credential Manager, scoped by data directory
and roster identity, wrapped/redacted in memory and delivered only over SSH
stdin. No password is committed or returned to the browser. Sleep retains its
existing command. Confirmation, fixed roster/action gates, Safe Mode, fresh
telemetry, authorization expiry and UUID reservation/deduplication remain intact.

Modified source: `dashboard/cluster_power.py`, new `cluster_credentials.py`,
the collector's precise Tailscale sign-in diagnostic, Cluster confirmation copy
and compiled frontend. New meaningful regressions verify credential isolation,
private stdin, readonly exact sudo policy, root override, concurrent dispatch,
missing credentials and safe preauthentication failure reporting.

Validation: frontend type/build PASS; focused cluster tests **75 PASS**; final
full suite **882 passed, 2 skipped, 17 subtests**, 55.40s; original browser
regression **24/24 PASS** at twelve widths with no JS/CSP/external errors.
All eight secure credential records are present, and a scan confirmed the actual
password is absent from source/tests/docs changes. Earlier full875 tests preceded
the final diagnostic/root/list-policy refinements and are superseded by882.

Live verification **BLOCKED** by Tailscale's additional SSH authentication check
on all eight nodes (exit255); root/ordinary accounts both require sign-in. Only
readonly identity/policy checks ran, with no reboot/suspend dispatched. No tailnet
policy or host-key verification was bypassed. No fresh sign-in response arrived
during this repair. The real password therefore remains unverified remotely,
despite verified secure local storage and automated execution-path tests.

Resume: complete Tailscale sign-in through each needed node's SSH Terminal,
restart the dashboard/controller to load Python changes, refresh the native UI,
and wait for fresh telemetry/authorization. Verify the readonly sudo policy,
then perform a user-confirmed reboot when intended. Setup, password rotation
and exact retained evidence: `docs/CLUSTER_REBOOT_FIX.md`. The earlier full
Phase1/2 scores describe their accepted artifact and are not newly assigned
visual scores to this follow-up.
