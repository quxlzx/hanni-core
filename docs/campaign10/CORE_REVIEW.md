# Campaign 10 core readiness after resume

The resumed public Core adapter is ready for coordinator integration. Its current
44 focused checks pass without model requests from Core. The adapter
now calls HANNI's original configured CLI text factories, with no extra legacy M6
tool layer. Independent final acceptance remains unrun and needs a new source-bound
coordinator GO. This readiness gate does not establish model quality or full
capability coverage.

The preserved original
controlled implementation run matches 57 of 63 frozen tasks (90.48%). This is
below the fixed 95% target. The six remaining strict mismatches are incorrect
authored byte-count, error-type, or result-key expectations, retained without
regrading. One narrow production repair was later independently reproduced and
approved during resumed public smoke review: imported read responses retain
bounded attributed structured fields without being promoted to verified facts.

## Prospective tasks and original implementation

The 63 tasks contain seven genuinely different scenarios in each of nine
families: diagnostics, files, app control, local calendar, tasks, MCP, Model Lab
analysis, permissions, and recovery. They were sealed before execution:

| Artifact | SHA256 |
| --- | --- |
| `data/campaign10-core/development-v1/INPUTS.json` | `b96a75c224764b53c50c4223feaf6e173d82e7aae5b9824c9cb7c09c3450048f` |
| `data/campaign10-core/development-v1/ORACLES.json` | `150101cd83c98df8208b61dc65c14edcd208ce5eaed414f23cefa2f196257475` |

Execution never receives an oracle. It invokes the original ToolRegistry,
permission boundary, reliability verifier, audit log, DesktopFeatures,
ProductivityStore, MemoryStore, emergency-stop persistence, MCP manager and Model
Lab. Temporary directories contain all fixture files, databases and configuration.
Google uses an empty vault. Calendar cases inspect original cached-calendar
projections and local tasks; they do not demonstrate a Google integration.
Windows control cases use explicitly mocked leaf adapters while keeping original
registered handlers. The unfamiliar parts-bin MCP provider uses original
configuration-hash and tool-definition approval gates over an inert transport;
it is not a live SDK/server integration. Model Lab cases run the original
model-free routing evaluator, not a neural model or simulated benchmark result.

## Preserved executions

| Execution | Result | Evidence |
| --- | --- | --- |
| Public adapter before probes | Memory tuple error, omitted first lazy handler entry, wrong inert MCP request signature | `data/campaign10-core/interface-before-01` |
| Public adapter after probes | Original memory fixture persists; exact lazy handler binding recorded; inert provider original call returns | `data/campaign10-core/interface-after-01` |
| First controlled 63 | 50 strict matches, 13 failures; original source unchanged | `data/campaign10-core/controlled-baseline-cycle1` |
| Corrected snapshot controlled 63 | 57 strict matches, 6 failures; same inputs/oracles, original source unchanged | `data/campaign10-core/controlled-baseline-cycle2` |
| Adapter regression gate | 17 passed, zero failures | `data/campaign10-core/core-contracts-cycle3.xml` |
| Resumed configured-factory gate | 38 passed, zero failures; no model requests | `data/campaign10-core/resumed-core-contracts-cycle3.xml` |
| Resumed current public gate | 44 passed, zero failures; no model requests from Core | `data/campaign10-core/resumed-core-contracts-cycle4.xml` |
| Manager actual original controller | 63 task records, 85 actual POSTs, 35 tasks with POSTs; original actual_generated flag true in 34 tasks | `data/campaign10-manager/live-core-cycle1` |
| Offline original-oracle actual readback diagnostic | 1 strict prescribed-contract match of 63; semantic accuracy unmeasured | `data/campaign10-core/live-readback-cycle1` |

The seven-case improvement from 50 to 57 is a harness correction: the snapshot
helper tried to hash Windows' genuinely locked original Model Lab `owner.lock`.
The corrected helper records unreadable bytes as unknown, preserving the lock.
It does not release, bypass or change the original ownership mechanism. The first
seven harness errors and all first-run receipts remain intact.

The six strict mismatches remain:

| Task | Frozen expectation | Actual original evidence |
| --- | --- | --- |
| files/read-hash | 33 bytes | 34 bytes; exact text and independently computed full SHA256 match |
| app_control/no-op-foreground | Returned `ok: false` | Original handler raises `OSError`; no verified focus success |
| mcp/bounded-bin-call | `structuredContent.total` | Original adapter exposes `structured_content.total: 10` |
| mcp/empty-bin | `structuredContent.total` | Original adapter exposes `structured_content.total: 0` |
| permission/observer-copy | `ToolPermissionError` | `ConfirmationRequired`, a permission-error subclass; destination absent |
| permission/typed-confirmation | `ToolValidationError` | `ToolPermissionError`; original file bytes unchanged |

Corrected-snapshot whole-case latency is P50 147.13 ms and P95 291.54 ms (63
measurements). It includes fixture setup, original dispatch, readback and file
snapshots, and excludes service cleanup. Individual action latency is retained
separately. These are controlled service timings, not model latency.

## Actual-controller scope and limitations

The preserved manager live run uses the existing configured model with original admission
and resource guards, no new model runtime, and isolated stores. No prescribed
development action is substituted for a model decision. A legitimate original
controller shortcut can produce a service result or refusal with zero model
POSTs. The original collector's zero-POST `NOT_RUN` label is not proof that no
controller work occurred. The observer's 35 tasks with POSTs and the original
34 actual_generated flags are retained as different measurements.

That 63-request cohort used the earlier helper stack: MemoryAwareSession around
ToolAwareSession around MCP/Text. The actual current CLI text factory does not add
that legacy ToolAwareSession layer. Those genuine 85 HTTP requests remain valid
evidence of their measured helper-stack variant; they do not certify identical
configured-launcher behavior. No replacement model cohort has been run by Core.

The offline one-of-63 diagnostic is not a semantic accuracy estimate. Many
development natural-language requests omit their fixture's path. Literal
controlled sensor values differ from live hardware readings. MCP setup actions
were not executed as hidden prerequisites in the actual run. Desktop and Model
Lab actions are not automatically exposed through the current model menu.
The scorer maps only chronological exact-name actual calls to prescribed action
IDs; missing outputs remain missing. It never manufactures desktop results,
provider approvals, a plan, a response, or an extra tool call.

Actual source-call review found clipboard.read and startup.list proposals outside
the intended fixture task, five app.open proposals, and ui.focus_window. The
observed clipboard, startup and app calls failed with PermissionError and no
result payload; focus failed with LookupError. No successful clipboard read,
application launch or focus effect is evidenced by those envelopes. Before
resuming actual model execution, the manager must retain its tightened original
filesystem scope and explicit OS/clipboard leaf isolation rather than relying on
incidental subprocess refusal. No real clipboard contents were inspected or
published by this worker.

## Shared input-only adapter

`scripts.campaign10_core.harness.run_case(case, owned_root, ...)` accepts either
the core category/query/setup envelope or the shared family/user_turns/fixtures
envelope. Actual user turns remain sequential on the same original session.
The adapter calls `hanni.cli._wrap_mcp_session` and `_wrap_memory_session`, using
their real MCP and memory configuration gates and configured retriever. It adds
no M6 ToolAwareSession. A scoped environment override disables shadow startup for
this isolated process and restores its previous value after construction.
Non-owner shared turns are explicitly unsupported by the original foreground
owner interface; the adapter does not invent role elevation.

A genuine client requires the coordinator's already-created adaptive engine to
be installed under the exact isolated data root. Otherwise the adapter refuses
before the original factory can create a second compute/model owner. The factory
retains its normal original monitor and resource policy when the coordinator
provides that engine. Original nested-session cleanup detaches only the registered
controller and closes its owned reliability services. The result records actual
layer classes, configuration gates, source hashes and closure status.

An original workflow facade is attached only when a dashboard runtime hub matches
this isolated root. The receipt separately records facade presence and actual
controller attachment. Core does not manufacture that prerequisite or treat its
absence as a working persistent-goal interface. The factory evidence covers the
text-wrapper layer, rather than the entire CLI command loop or native ChatHub.

The opt-in `attach_dashboard_facades(state, telemetry=None)` helper now provides
the original MCPHub and WorkflowHub over owned stores and the original manager.
It refuses to replace an existing process-local runtime. Its Telemetry is the
original class: unstarted measurements remain unknown and the original workflow
resource probe refuses admission. The coordinator can start that exact original
Telemetry under its inference GO. Original environment cleanup detaches the
controller, closes both facades and closes adopted telemetry. No compute worker,
CLI command loop, natural-language goal submission, generated plan or native
window is created or claimed by this helper.

Basic projects, tasks and memories are seeded through original stores with
dynamic IDs recorded separately in `fixture_setup`. An explicitly supplied
`mcp` fixture may request only the fixed inert parts-bin configuration, exact
connection approval and original tool approval. Arbitrary provider configuration
is unsupported. Cross-system operations outside this core adapter return explicit
NotImplementedError; the Systems adapter owns their original services.

Memory fixture references resolve against actual seeded project IDs before the
original store receives them. Duplicate fixture/action bindings and malformed
fixture approval flags fail before fixture effects. Unhandled fixture declarations
are retained in `fixture_prerequisites` as `NOT_APPLIED`, rather than silently
credited as initialized. Optional `on_prepared_turns(task_id, turns)` exposes the
resolved ordinary turns after setup and before session construction; the manager
uses it to bind the genuine request budget without seeing oracle values.

Shared direct registry contracts preserve the caller profile and exact supplied
confirmation type. Shared desktop calls cannot convert a non-owner into the
original owner-bound API. Actual foreground turns never apply a `confirmed` field
to model-generated tool requests: the original pending-request flow remains
authoritative, with this distinction recorded per turn. An explicit configured
inert MCP fixture still needs the manager's targeted isolation guard to admit
that exact reviewed fixture tool; it does not justify opening arbitrary providers.

All raw dimensions use the fixed protocol's NOT_MEASURED until separately graded:
intent, retrieved_context, tools, arguments, authorization, execution,
outcome_verification, final_response, latency and recovery. Controlled handler
provenance and argument receipts do not prove natural-language model selection.
Observer counts survive a controller exception; they remain counts of observed
requests, with actual wire response evidence owned by the manager.

## Resumed public smoke finding and repair

The coordinator's separately sealed five-task smoke collected eight real local
POSTs in `data/campaign10-manager/resumed-controller-smoke-cycle1/execution`.
Core did not run additional inference. Its memory follow-up supplied the stored
owner-explicit release-channel fact even with enhanced context disabled. The
model refused to assert current configuration from that historical statement;
this is not a missing-retrieval defect and memory settings/source remain unchanged.
A public original-memory boundary control independently retains the fact,
source and `current_state_verified: false` in transmitted model messages.

The imported parts-bin call returned schema-validated structured records and the
actual model answered the count, but original `_guard_answer` discarded those
fields because external results are unverified. The independent verifier replayed
the captured model reply and real result to reproduce that omission before repair.
Only `src/hanni/mcp/session.py` changed: successful unverified reads quote a bounded,
key-aware redacted structured-data excerpt. UTF-8 output is capped at the smaller
of configured tool-result bytes and 8,192, with explicit truncation. Credential
fields, known secret values/keys and token patterns remain withheld. Instructions
inside returned JSON remain labeled untrusted data. External verification status,
independence, action outcome safeguards and permissions stay unchanged.

Public causal before XMLs preserve three omission failures. After controls verify
returned fields, malicious-data labeling, synthetic credential redaction, bounded
excerpt disclosure and unchanged action refusal. Independent after replay retains
the actual seven-washer result with UNVERIFIED/non-independent status, and six
independent security/bounds controls pass. This is a narrow response-grounding
repair, not provider verification or a semantic benchmark score.

## Capability coverage and historical comparison

The corrected controlled run dynamically observes a union of 179 registered IDs:
the current 172 default capabilities plus seven lazy workspace or synthetic
external IDs. It enters 35 distinct actual registered handler IDs. This is not
179 fully tested capabilities or 100% current coverage. The per-definition
`CAPABILITY_COVERAGE.json` records untested IDs explicitly. Legacy exhaustive C2
contract receipts remain historical, not fresh C10 semantic coverage.

C1's independently reviewed actual-response score remains 88/273 (32.23%). C2
independently verified 172 original implementation contracts, while its final
173 guarded model attempts made zero HTTP requests. C9's security repairs and
causal before/after controls remain separate security evidence. None of these
denominators is directly comparable with C10's 63 controlled implementation
tasks or a future untouched final model cohort. No accuracy improvement is
claimed by merging these scopes.

## Resume and source hold

Only the approved MCP fallback production file was modified by Core. All owned tests and commands have
closed. The prior `data/campaign10-core/SOURCE_READY.json` remains unchanged.
The resumed checkpoint is `data/campaign10-core/resumed-readiness-cycle2/SOURCE_READY.json`;
it pins the current helper/test/report files, original production sources and
unchanged prospective inputs/oracles. Source archives and earlier receipts remain
intact. The resumed test cycle2 retained two test-author attribute errors
(`context_retriever` instead of the actual `retriever`); cycle3 corrected that
public test seam and passed all 38 checks, without changing production or scores.
The current combined Core gate passes all 44 checks. The initial readiness-cycle1
metadata publication error (an older JSON artifact had a UTF-8 BOM) is retained
separately; it did not execute services or inference.

Root owns the remaining collector integration and inference admission. Freeze
the final shared adapters before the independent 45-case single-use final.
Preserve missing workflow attachments, non-owner interface limitations, unhandled
fixture declarations and unavailable provider/hardware requirements in the strict
denominator. Do not rewrite development expectations, promote controlled
dependencies to live, inspect private inputs, or start extra generation.
