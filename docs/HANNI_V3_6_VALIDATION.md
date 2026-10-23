# HANNI V3.6 validation campaign

Development branch: `codex/hanni-v3.6-validation`. Baseline: `45cde75`.
This campaign uses exactly three logical agents: manager, engineer, and independent
verifier. Production storage, Windows credentials, personal provider data, and
the existing sealed V3.5 evaluations are outside the test fixtures.

## M0 checkpoint: baseline and inventory

The dynamically constructed default registry contains 172 definitions in 44
domains. This is an observed count, not a fixed acceptance denominator. Runtime
memory/desktop registrations and imported MCP definitions must be merged into the
final inventory with their origin. The private full manifest is
`data/v36-campaign/inventory.json`; configuration backups and dependency discovery
are beside it. All four source configuration hashes were recorded before launch.

Baseline command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=data/v36-campaign/baseline-regression.xml
```

Observed: 1,543 passed, two skipped, zero failures/errors; 211.498 seconds. This
includes the existing subprocess test suite and is not a full-system acceptance.

The engineer launched the original application controller and its configured
Qwen model in copied configuration with separate state. Native inspection uses
the actual desktop client attached to that controller. The first launch exposed
an isolation limitation: GoogleAccess lazily discovers the shared Windows
Credential Manager independently of the data directory. No provider request was
made. Further launches use an explicit empty test vault at this external seam;
Google adapter cases use synthetic accounts and a controlled provider transport.
No live Google integration is claimed.

## Campaign boundaries and frozen evaluation

Every definition needs an ordinary direct case, invalid/failure case, and actual
natural-language selection case. Responses, tool arguments, execution results,
objective verification, and outcome classification are separate fields. Model
responses are retained privately. Safe live diagnostics, real isolated file and
SQLite writes, and mocked external dependencies have separate denominators.

Engineer model cohort: 172 prospectively authored requests, sealed before the
first inference; SHA256
`94bdde3464cac94cd8e0e1dd66cbd183f78bac07463cae1251a4ab1bcf05aa9a`.
Verifier cohort: 24 independently authored unseen responses; SHA256
`907660adbf54faf891308d578c55a6194f1d51dca647b55dee83a09da44b891c`.
The latter remains unseen until final verification after repairs. Neither cohort's
expected answers or acceptance rubric may be revised in response to failures.

Classification: LIVE_PASS, ISOLATED_PASS, MOCK_PASS, MANUAL_PASS, FAIL, BLOCKED,
UNSAFE_TO_RUN. Mock success is documented separately when a consequential live
action is unsafe. Missing authentication, unavailable hardware/models, and
policy-disabled model access are explicit blockers, not successes. Unknown or
wrongly selected tools remain failures. No permanent unexplained NOT TESTED.

Budgets: one model inference server, serialized model requests, bounded model
turns and token limits, resumable evidence batches. Direct mutation cases execute
serially through the original registry and normal permission/confirmation gates.
Fixtures and results stay under ignored `data/v36-*` paths. Only synthetic,
reviewed summaries are committed; credentials and raw personal telemetry are not.

No reboot, shutdown, power state changes, personal clipboard modification,
unrelated process termination, remote writes, personal calendar edits, outgoing
messages, unrestricted shell execution, continuous screen capture, or webcam
capture. Owned test files/processes and mocked OS leaf APIs supply safe evidence
for these surfaces. Acoustic testing requires an explicit supervised participant.

## Acceptance and remaining milestones

Targets are 95% direct eligible success, 95% genuinely unseen selection, mean
response quality 9/10, 95% verified core workflows, zero unauthorized sensitive
execution or duplicate destructive action. Screens are graded individually from
actual native screenshots at four sizes and 125% scaling; overall must exceed
8.5, every primary screen at least 8.6, template appearance at most two.

M1 direct implementation coverage; M2 actual model/response coverage; M3 MCP and
Google provider fixtures; M4 memory/LAYA/workflow outcomes; M5 voice/screen privacy;
M6 desktop interactions and visual scores; M7 assigned root-cause repairs and
independent regressions; M8 final matrix/report and honest acceptance decision.

At this checkpoint, model, direct, integration, and visual batches are in
progress. No production repair or full-system acceptance is claimed. Resume by
reading the latest checkpoint and result journals under `data/v36-campaign`,
`data/v36-engineering`, and `data/v36-verification`; preserve completed valid
batches and both frozen cohorts. Five pre-existing untracked root reports/archive
files are unrelated and remain unstaged.

## M1 checkpoint: complete direct baseline and runtime desktop coverage

All 172 default definitions received ordinary actual-registry execution,
unknown-argument rejection, and a chat-only profile denial. Consequential OS
operations used leaf dependency mocks; file/task/note/git operations used real
isolated artifacts and readback. The first immutable batch recorded 129 passes,
40 failures, and three dependency blockers. Harness defects are retained and
distinguished from production failures: undersized duplicate fixtures, ambiguous
email query shape, wrong calendar availability argument shape, developer test
output assumptions, a character-count typo, timer fixture observation, service
mock target, and the mock provider's task-route parser.

Repair rechecks passed for Google output contracts, all five local todo
contracts, the user-folder object contract, and the Windows empty event-log
case. Spotify's actual missing optional volume package remains a live blocker;
its original handler additionally passed with a controlled pycaw dependency.
The actual Black and Ruff executables are unavailable in this interpreter.

The desktop's source operation sets generated another 24 lazily registered
capabilities. All 24 passed ordinary real SQLite mutations/readback, invalid
argument rejection and chat-only denial in a separate campaign. A workflow link
used a real isolated persistent workflow record, without claiming model planning
success. These tools reside in the fixed desktop registry rather than the
conversation controller registry; model access is explicitly blocked by that
architecture. The union currently contains 196 definitions before local test MCP
imports. Final inventory is regenerated from current descriptors, not this count.

Evidence: `data/v36-campaign/direct-cycle1`, `direct-harness-corrections`,
`direct-repair-cycle2`, `direct-spotify-volume-mock`, and `desktop-cycle2`.
Independent verification is required before a verified pass. Resume commands:

```powershell
.\.venv\Scripts\python.exe scripts/v36_campaign/direct.py --output data/v36-campaign/direct-new-cycle
.\.venv\Scripts\python.exe scripts/v36_campaign/desktop.py --output data/v36-campaign/desktop-new-cycle
```

## M2 checkpoint: complete actual model baseline

The sealed 172 requests completed with 331 genuine configured-model inference
requests. Of 132 requests eligible under the original conversational policy,
128 reached a model tool menu; the remaining four were handled or blocked by
earlier original-controller branches. Exact selection: 103/128; prospectively
declared equivalent-operation selection: 108/128 (84.375%). This misses the 95%
target. No difficult eligible case may be silently dropped from the final
denominator. Whole-turn latency P50: 1.665 seconds; P95: 3.874 seconds.

The engineer's initial successful execution labels are not final response-quality
acceptance. Independent review found additional false or unsupported answers,
including a wrong filename filter for content search, unknown mute status
reported as unmuted, and invented file size. Raw baseline responses and all
original scores remain immutable. Focused schema/evidence repairs and final
unseen 24-case verification remain outstanding at this checkpoint.

Evidence: `data/v36-engineering/model-outputs-v2.jsonl` and
`model-baseline-summary.json`. Do not regenerate completed baseline turns. Resume
with assigned repairs, three real-model persistent goals, local MCP integration,
and the independent final response cohort after source freeze.

## M5 supervised capture checkpoint

The owner agreed to a brief test and confirmed readiness. Original microphone,
Silero VAD and cached configured faster-whisper were warmed before capture.
The device closed automatically after 10.047 seconds: 310 chunks, zero dropped
blocks, and zero detected utterances. No raw audio or transcript was persisted.
The owner then clarified that the microphone is currently inactive. The raw
failed recognition result and a separate classification erratum are preserved;
current acoustic validation is BLOCKED, not a claim about previous functionality.

Device discovery observed 15 microphone inputs and one speech output. Screen
awareness is explicitly unavailable in the actual desktop adapter because this
repository has no registered capture/vision pipeline. Configured retention alone
does not establish screenshot expiration or vision functionality. The actual
configured Australian voice is unavailable; unrelated speech fallback behavior
and controlled logic checks must be reported separately from audible acceptance.

## M3 checkpoint: integration coverage

Twelve focused Google tests passed through the original adapters, a synthetic
credential vault and a controlled provider transport. Authentication, scope
denial, invalid dates, DST/time zones, timeouts, readback and uncertain-write
duplicate suppression were exercised. Live Google remains BLOCKED. The optional
local calendar is deferred so that this campaign preserves implemented behavior.

An actual local stdio MCP SDK server dynamically imported three approved tools.
All three original-registry valid calls and invalid-field rejections passed;
the confirmed fixture write was read back from durable storage. The actual Qwen
controller selected/executed both read tools, 2/2; the write remained blocked by
the original conversational policy. Reconnect/schema revision evidence is in
`data/v36-engineering/actual-external-mcp-cycle4`. Earlier setup failures remain
available separately. These temporary imports are inventoried separately from
the default/fixed-desktop union and must be cleaned up after verification.

## M4 checkpoint: memory and actual workflows

Independent original-registry, HTTP, file, SQLite and memory checks passed.
The combined core/memory/workflow/MCP verification suite passed 118/118 in
62.044 seconds, including real owned-process recovery and isolated outcomes.
Controlled planning/clock fixtures do not receive real-model planning credit.
LAYA's package/model is unavailable and its production gates remain disabled;
local memory evidence does not establish active LAYA retrieval.

Three prospectively sealed goals were submitted through the original persistent
workflow API and actual configured planner. Verified completions: 0/3. The
folder report used an unsupported folder-as-file step, the task plan failed
bounded planning validation, and the memory goal proposed unrelated diagnostics
and was cancelled before execution. A private GET-token omission in the observer
was corrected while retaining the original goal IDs, with no replanning.
Evidence: `data/v36-engineering/actual-workflows-cycle1`.

## M6 checkpoint: native desktop

The actual native Windows client was inspected at four physical sizes and 125%
display scaling. Final visible-frame capture: 18 primary screens, 77 frames and
163 checks; no JavaScript errors or unexpected external/unsafe requests. Separate
populated interactions passed 44 checks/11 frames. Mini passed 12 checks/six
frames, with actual DPI-clamped dimensions retained. These assertion counts
include geometry and do not represent exhaustive button coverage.

Independent primary visual mean: 8.72/10, each primary screen at least 8.6;
template estimate 1.6/10. Mini: 8.4/10, with an external Grammarly overlay limiting
small-window mouse-Send coverage. No unrelated process was hidden or terminated.
Owned screenshot capture now uses the DWM visible frame; original border-capture
and project-selection harness errors remain in their original journals.
Native evidence: `data/v36-verification/native-cycle4`, `native-cycle3`, and
`mini-cycle2`. The reviewer report is `docs/v36-reviews/NATIVE_REVIEW.md`.

Read-only final cluster observations found all eight configured nodes returning
actual SSH CPU/RAM/uptime telemetry over Tailscale; Yunjin remains under repair.
Refresh is one second with a 60-second history. Available node reboot/terminal
controls were not invoked. Live power operations remain UNSAFE_TO_RUN, and the
node's unsupported sleep action remains unavailable.

## M7 checkpoint: verified repairs and final unseen evaluation

Independently accepted backend repairs cover truthful Google/task/folder output
contracts, empty event-log handling without masking denied access, exact digital
silence rejection while retaining all nonzero PCM decoding, unknown mute state,
content-query/filename-filter semantics, measured file byte size/full SHA and
calendar creation intent/destination authority. A local note containing a date
had wrongly created a mock external event: that baseline is a critical failed
case. Novel local-storage/date tests now reject provider creation; genuine
calendar requests retain the original allowlist. No live provider/power write
occurred. Model grounding problems remain even when backend regressions pass.

The real-process verifier fixture now atomically publishes complete fsynced JSON;
five lifecycle tests and the independent publication oracle passed. Production
workflow logic and parent deadlines were not weakened.

The first candidate full regression recorded 1,603 passes, two failures and two
skips (1,607 total): an intentionally changed result-contract audit and a partial
fixture JSON publication race. Both failures are retained in
`data/v36-campaign/final-regression.xml`. A versioned schema-only audit migration
is being completed without changing frozen prompts, required tools, behavior
oracles, risks or scores; the historical v1 corpus remains intact. Root must run
the final complete regression after that source freeze.

Baseline independent quality: 8.274/10 over all 172 responses, with 46 failures,
50 blockers and 76 scoped passes. Model cohort v2 SHA256:
`7cbd5385c410281044a7af3877d866281a072b9c4baf70295c5cfc38a18a2a37`.
It amended only the owned launcher addresses before any inference; v1 remains
preserved. Final independently sealed 24 unseen cases ran once, 45 genuine
requests, unchanged source hashes. Selection: 12/16 measured menus (75%);
quality: 8.304/10 across all 24. Seven failed, three blocked, 14 scoped passes.
The other eight cases are explicitly accounted for as memory/fast-path/policy
cases, not silently excluded. Both reliability targets remain unmet.

Modified production files at this checkpoint are `speech/stt.py` and tool modules
`calendar_routing`, `content`, `envtools`, `files`, `google_access`,
`google_services`, `media`, `security`, and `todos`. Test-only process publication,
regression tests and isolated fixture support accompany them. Outstanding work:
schema audit migration, full regression, final independent direct/MCP/diagnostic
review, evidence export, owned-runtime cleanup and M8 acceptance report. Resume
from the result journals; do not rerun valid completed model batches. Preserve
original configuration, model selection, V3.5 sealed evaluations and the five
unrelated untracked root files.

## M7 second regression checkpoint

Candidate full regression cycle two: 1,632 passes, two failures, two skips;
1,636 tests, 220.543 seconds. The schema-only v2 migration passed five focused
tests with strict drift detection and unchanged v1 working-byte digest. The new
full-suite failures were both original behavioral-corpus audits: the calendar
intent guard rejected medical, social and academic scheduling requests. The
194-case original behavioral corpus and its required tools remain unchanged.

The engineer is repairing general activity-domain recognition while retaining
the storage/body authority guard. Both engineer and verifier seal fresh domain
examples before implementation; neither may patch individual benchmark phrases
or rewrite the old behavioral expectations. The 24 already-completed unseen
responses remain immutable evidence for the previous source snapshot, with any
subsequent guard addendum disclosed. Do not rerun them to raise scores.

The independent direct audit now covers all 196 records: 57 live, 76 isolated,
61 mocked passes and two dependency blockers. Its scope is retained evidence
and current schema/validation review, plus 24 separate desktop replays and 20
independent artifact readbacks. It does not claim 196 live re-enactments.
Evidence: `data/v36-verification/direct-evidence-review.json`.

Outstanding: independently accept the calendar activity repair, run final full
regression cycle three, finish diagnostic/MCP/workflow review, close owned runtime
and export M8. Resume from `final-regression-cycle2.xml`; preserve all failed
artifacts and the original frozen cohorts. No production configuration or
permission change is authorized by these test failures.

## M7 activity repair verification checkpoint

The calendar guard now recognizes general medical, social/recreation and academic
activity nouns and tutor/teaching morphology, while keeping competing local
storage and quoted/body destinations separate. Clock colons remain in intent
only when both adjacent characters are digits; numeric-leading stored bodies
cannot grant calendar authority. This is category/morphology recognition, not
complete benchmark-utterance matching. The behavioral corpus was not edited.

Engineer prospectively sealed 11 novel domain/boundary cases before implementation
(SHA256 `1d297c96c7d25379a37bf83da735fd0be75736315df837008110adae95ec6cde`).
The verifier independently sealed eight different cases
(`6191b2c91f1cbc7c12e6171b02c0afb4ba062e215c7bf8e5e1f44111d17b94fa`).
An initial tutoring omission was rejected and retained in `core-cycle5.xml`.
The same expectations plus legacy and numeric-body/clock boundaries now pass:
46/46 independent checks in `core-cycle6.xml`; 177 focused engineering checks.

Frozen actual-model results remain the previous candidate's evidence. They were
not regenerated or promoted after this parser-only addendum. Root's full final
regression cycle three is now running against the accepted final source. The
original application was relaunched at cycle seven with that source for lifecycle
health/close proof. Only campaign-owned controllers/model processes are closed.
Modified files in this repair cycle: `tools/calendar_routing.py` and the engineer
and verifier's V3.6 integration regression modules. Resume from
`final-regression-cycle3.xml`, then final independent report, integrity/cleanup
proof, export and M8 commit.

## M8 final acceptance checkpoint

Final full regression command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=data/v36-campaign/final-regression-cycle3.xml
```

Observed 1,667 passed, two skipped, zero failures/errors; 1,669 tests in 222.574
seconds. The skips concern the absent historical local-inference report and an
optional console entry point absent from PATH. The accepted production source
was tested. A test-only portability change moved the byte-identical sealed
calendar addendum into the repository; its final module separately passed 46/46
in 3.83 seconds. Guard source SHA256:
`675a3c571eca3ea04021e6515ee1d90b6979c694b0d2533a327833b509d3b25a`.

The original sealed mechanical core suite is 16/16 scoped PASS, with all 16 IDs
mapped in `data/v36-verification/core-workflow-review.json`. Actual model-planned
goals remain 0/3, zero invocations; they do not replace that original denominator.
Final unseen objective accounting is 13 requested data/actions plus one passing
firewall-denial guard (14 scoped behaviors), not 14 requested actions. Its
classification erratum preserves the original artifact and all scores/oracles.
Actual selection remains 12/16 measured menus (75%), quality 8.304/10; the cohort
was not repeated after the later activity-parser addendum.

All 196 observed default/private-desktop definitions are independently accounted
for, with A execution, B selection, arguments, response quality and live limits
separate. Direct outcomes: 57 LIVE_PASS, 76 ISOLATED_PASS, 61 MOCK_PASS, two
BLOCKED. Fixed desktop diagnostics: 24 real response-only generations, B blocked
for missing chat authority. Three actual temporary SDK imports have their own
complete schema/outcome manifest: three direct scoped passes, two readable model
selections and one policy-blocked model write. Production/runtime snapshots and
lazy private registrations are explicitly distinguished.

Independent primary native mean 8.722; all 19 views including Mini 8.705; Mini
8.4 and template estimate 1.6 are retained with limitations. Original private
outputs and all rejected/failed cycles remain under `data/v36-*`. Public summaries,
196-row readable matrix, response components, failure ledger, temporary MCP
manifest and 72-frame primary screenshot index live under `docs/v36`.

Final original runtime cycle seven passed health/registry/config isolation checks
and authenticated shutdown; all seven controller/model cycles and SDK fixture
closed with exact owned PIDs absent. No user process was killed. All four source
configuration hashes are unchanged; historical v1 working bytes match their
pre-migration hash, with existing Windows/Git newline normalization disclosed.
The five pre-existing unrelated untracked root files remain preserved/unstaged.

Final disposition: PARTIAL. Reproduced backend defects are independently repaired,
and scoped mechanical/primary visual gates pass. Model selection, response
grounding and autonomous goals fail the requested intelligence acceptance.
Acoustic tests are blocked by the inactive owner microphone; configured voice,
vision/LAYA availability, live Google and consequential node controls remain
explicitly unverified/blocked/unsafe as appropriate. There is no pending owner
action. Continue future development from the current candidate and preserved
failure ledger; improve general model/planning behavior and obtain fresh sealed
evaluation rather than rerun or change the completed cohorts.
