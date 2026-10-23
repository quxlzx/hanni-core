# Campaign 2 capability and MCP audit

The audit documents **100% of the observed current inventory: 172 built-in
capabilities and zero enabled owner MCP tools**. Counts come from fresh registry
enumeration and read-only owner discovery. Every capability has eight explicit
outcomes and preserved original-handler receipts. The independent verifier
accepted the inventory, contracts and evidence with zero integrity violations.

This is **not an unconditional campaign pass**. There are 23 unresolved
natural-language retrieval failures. All 173 guarded model-selection attempts
were blocked before inference by the existing admission policy. The repaired
source is validated, but the preserved running app still has the old PowerShell
definition; deployment acceptance remains pending its next normal restart.

## Deliverables

- [Per-capability scorecard](SCORECARD.md), [compact machine-readable scorecard](SCORECARD.json), and [complete routing metadata inventory](INVENTORY.json).
- [Independent verification report](INDEPENDENT_REVIEW.md) and [verification receipts and hashes](VERIFICATION.json).
- [MCP transport report](MCP_REPORT.md), [per-tool transport scorecard](MCP_SCORECARD.json), and [SDK evidence](MCP_EVIDENCE.json).
- [Platform implementation and repair report](PLATFORM_REPORT.md).
- [Retrieval failures](RETRIEVAL_FINDINGS.json), [guarded model outcomes](MODEL_SELECTION.json), and [unknown-tool demonstration](UNKNOWN_TOOL.json).
- [Local raw evidence manifest](EVIDENCE_MANIFEST.json), [source and preservation evidence](SOURCE_VALIDATION.json), [protocol](PROTOCOL.md), and [checkpoints](CHECKPOINTS.md).

Public scorecards omit unrelated live process/window/environment data. Complete
raw matrix receipts remain locally in
`data/campaign2-manager/final-cycle2/receipts`, with their hashes published.
Public compact scorecards are summaries, not inputs to the full-evidence checker.

## Inventory and implementation scope

The owner's existing `/api/workspace` GET independently exposed exactly the same
172 capability IDs and registry revision. Enabled external discovery contained
zero servers and tools. Lazy desktop-control adapters were absent from that
active registry and are explained in [runtime inventory](RUNTIME_INVENTORY.json).
No owner connection, credential, model configuration or background application
was modified to manufacture coverage.

| Capability family | Observed count |
|---|---:|
| Applications | 3 |
| Files | 23 |
| Media | 16 |
| Utilities | 8 |
| Desktop | 12 |
| Computer | 37 |
| Communications | 4 |
| Development | 14 |
| Productivity | 39 |
| Assistant | 5 |
| Network | 6 |
| Security | 5 |

All 172 original implementations received valid-input calls and independent
semantic or dependency readback. Their positive-test scopes were **61 safe live
reads, 44 isolated implementations, and 67 original handlers over mocked leaf
dependencies**. Writes used disposable files, SQLite stores or local mock
provider state. Exact owned child PIDs/listeners were used for process and
network tests. GUI, audio, playback, services, power and external actions were
controlled at their dependency boundary.

Mock Google credentials, transport and calendar state exercise original account,
scope, argument, provider and result handling. **No live Google API success is
claimed.** Mock hardware/provider results establish scoped implementation
behavior, not physical changes or external factual truth. File-opening and
notification readback confirms submission only; their display remains unverified.

## Eight-dimension results

| Dimension | Passed | Failed | Inapplicable | Interpretation |
|---|---:|---:|---:|---|
| Valid arguments | 172 | 0 | 0 | Original registered handler entered and succeeded in its stated scope |
| Invalid arguments | 172 | 0 | 0 | Unknown fields and wrong declared types rejected before dispatch |
| Missing parameter | 172 | 0 | 0 | Required omission rejected; otherwise actual optional/default/semantic behavior documented |
| Permission enforcement | 172 | 0 | 0 | Actor, stale-definition, stop and applicable confirmation boundaries tested |
| Dependency unavailable | 158 | 0 | 14 | Original unavailable branches tested; pure implementations have no optional dependency |
| Output contract | 172 | 0 | 0 | Actual successful names, envelopes, required fields and types validated |
| Natural-language retrieval/policy | 149 | 23 | 0 | Metadata/menu evidence only, separate from actual model selection |
| End-to-end implementation | 172 | 0 | 0 | Independent readback at the declared live/isolated/mock boundary |

These are 1,376 documented outcomes: 1,339 scoped passes, 23 retrieval failures
and 14 explicitly inapplicable dependency tests. Documentation coverage is not
model success or live-provider coverage. Missing-parameter passes for optional
schemas do not imply that all semantic requirements are encoded as required
JSON Schema fields.

The matrix has 693 authorization assertions. Independent review checked 688
durable denial receipts and their zero original-handler entries. The remaining
five high-impact checks record confirmation exception labels; independent
13-callback and eight shell-gate probes separately establish their authority
boundary. No dangerous command was executed by those probes.

## Reproduced findings and repairs

Runtime repairs are limited to audited capability handlers and their descriptors.
Controller, retrieval policy, inference guards, cluster controls and MCP
production code are unchanged.

| Finding group | Reproduced defects | Result in current source |
|---|---:|---|
| Silent control no-ops | 9 | Spotify focus/volume, system volume/mute, brightness, power plan/idle, window state and minimize-all require observed state |
| Empty diagnostic certainty | 4 | Defender, firewall, pending reboot and disk health return unavailable/unknown |
| Missing battery measurements | 2 | Complete nullable unavailable payloads replace invented or missing measurements |
| Provider boolean type confusion | 3 | Only booleans and native 0/1 enums become known states; unsupported values remain unknown |
| Request/completion overclaims | 3 | File open and notification report submission; failed Black reports failure and unknown partial application |
| Arbitrary PowerShell confirmation bypass | 1 | All arbitrary code requires explicit confirmation, independent of command spelling |

The shell defect was reproduced with computed command names that bypassed the
old blacklist. A throwing pre-handler execution guard prevented every shell
execution. The fix requires permission/risk level 3 for the entire capability;
pattern matching remains explanatory. Literal, computed and ordinary arbitrary
code all deny unconfirmed dispatch. A confirmed safe `Write-Output` test still
uses the original implementation.

Independent review replayed exact archived baseline handlers for the 15 original
platform failures, then checked repaired versions. It additionally verified
39 malformed/native-provider cases, eight shell authorization probes, and five
request/formatter checks. The formatter checks include actual Black exit 123,
possible partial-write semantics, and an actual successful write with exact
readback. No real GUI or notification was used to infer visibility.

The initial full regression caught four stale claim-free synthetic schema rows
through two tests after battery output descriptors gained availability/presence.
A hash-bound metadata addendum updates only those two declared fields. Every
prompt, case ID, ordering, required tool, answer claim, argument schema, risk and
behavioral expectation is preserved. Historical v1 is untouched; strict schema
drift detection remains enabled. The independent verifier reproduced those
invariants across all 264 schema-only rows. This is metadata alignment, not
benchmark tuning.

A final consistency check reproduced a `number|null` error in the synthetic
schema-fixture generator. The helper now supports nullable unions and supplies
typed values for present optional fields. Its earlier optional string/enum null
samples were also invalid. Independent checks validate all 172 definitions and
470 output fields plus six supplemental descriptors, without invoking handlers.
The strict `audit_coverage` function and every other module function are unchanged
from baseline. This related metadata helper repair does not change corpus bytes
or any live tool, routing, model or permission behavior.

## Natural-language and model limits

Of 132 host-eligible capabilities, 109 queries supplied the required or accepted
equivalent tool, and 23 failed: **82.6% eligible menu sufficiency for this audit's
queries**. Forty other queries correctly excluded host-denied capabilities.
The 149 combined policy/retrieval passes must not be presented as model-selection
accuracy. Root cases reuse existing public diagnostic probes; the platform
cohort uses prospective wording. This is not an untouched routing benchmark.

The failed tools and exact menus are in [retrieval findings](RETRIEVAL_FINDINGS.json).
Failures include process memory/I/O questions, empty-folder/recent-file queries,
selected Google/Drive/Gmail operations and some system/desktop requests. Separate
independently worded probes confirmed wording-sensitive misses. Their handlers
exist and execute; these are retrieval limitations. No phrase-specific tuning
or sealed Campaign 1 holdout exposure was performed.

The final model sweep ran after the full pytest process exited. It attempted
original guarded selection for every built-in plus the newly imported unknown
MCP tool: **173 blocked, zero inference HTTP requests**. The existing local model
health probe succeeds. The original selector's separately recorded diagnostic
identified `insufficient_ram_reserve` on every attempt. Available RAM ranged
from 1.781 to 1.884 GiB, below the unchanged 2 GiB reserve. This diagnostic is
separate from the generic native admission error. Temperature, sampling, token
limits, model identity, privacy and resource guards were preserved.

Consequently model tool-choice accuracy, generated-argument quality, grounded
final answers, generation latency and token usage are **not measured** here.
Pre-inference refusal timing is not an inference-performance measurement. There
are no canned model answers or fabricated completion passes.

## MCP Hub and unknown capability

Actual SDK 2.2.0 stdio and Streamable HTTP tests passed **157/157**, including
128 per-tool dimension references, two discovery checks and 27 lifecycle tests.
The dynamic isolated inventory contains eight newly authored tools; these are
separate from the zero owner-enabled external tools.

Verified behavior covers initialization and paginated discovery, exact schema
preservation, explicit classifications, enable/disable, dynamic registry/cache
updates, real `tools/call`, definition-change approval revocation, notifications,
duplicate names, connection failures, timeouts, removal during calls, stale
cached handlers, cleanup and malicious description containment. Stdio recovered
on its existing session. HTTP timeout withdrew adapters and required an explicit
approved reconnect. Neither path silently replayed timed-out work.

The unknown `quartz.inspect_flux_band` was absent during initial router
development. Actual discovery supplied its schema and its original menu entry
without code changes or retraining. Declared safe fixture arguments traversed
both transports and returned typed controlled data; the independent verifier
used different input. The final original registry call returned AX-17, narrow,
0.42. Its external response verification stays `UNVERIFIED`.

**Real model-driven use and grounded response synthesis for the new capability
remain blocked.** SDK discovery/call success cannot substitute for that proof.
Malicious-description tests establish deterministic host authority, not a broad
model prompt-injection evaluation.

## Regression and independent verification

- Final dynamic matrix: all 172 capabilities with retained original handlers;
  source and definition hashes match fresh independent inventory.
- Frozen platform validation: 270 platform checks and 109 relevant existing
  checks passed. Root repair/metadata focused validation: 25 passed.
- Final nullable-fixture and strict coverage follow-up: 29 passed, including
  exhaustive current output-descriptor generation.
- Independent test suite: 42 passed, with additional standalone typed-provider,
  action-claim, contract, schema-addendum and source-preservation evidence.
- MCP protocol suite: 157 passed; independent fresh SDK checks and public
  receipt-reference crosschecks passed.
- Full repository regression: **2,752 passed, 3 failed, 2 skipped, 33 subtests
  passed**, in 462.68 seconds. The two stale-fixture failures were then corrected
  and all five strict migration/coverage checks passed.
- The remaining existing CLI streaming test was reproduced independently of
  the suite and fails the original resource admission guard. Its controlled
  endpoint is healthy, but it has no admitted completion. CLI/adaptive source
  was not changed to hide this environment limitation.

The full regression is therefore not reported as green. Targeted corrective
verification and the retained initial failures are both available. Previous
harness errors, including an ignored Black specimen under the gitignored data
directory, are preserved as inconclusive or harness failures rather than passes
or product defects. The actual formatter proof used an owned OS-temp directory.

## Acceptance disposition

| Requested condition | Disposition |
|---|---|
| 100% current inventory coverage and documented outcomes | Met: all dynamically discovered IDs, all eight outcomes |
| Safely executable original implementation tests | Met within explicit live/isolated/mock scopes |
| No known permission bypasses | Repaired and verified in current source; preserved active app still loads the old shell gate, so deployment condition is pending |
| No executable tools stale after removal | Met in actual SDK removal/timeout/revocation checks and independent cached-handler tests |
| No false success claims | Reproduced source overclaims repaired; unavailable, mock, request-only and blocked outcomes remain explicit |
| Natural-language model selection for every capability | Blocked; retrieval failures separately documented |
| Unknown tool discovered and used without retraining | Discovery and original SDK calls verified; actual model use blocked |
| Live Google verification | Not attempted; Google is unconfigured and mocked only |
| Fully green regression | Not met: existing real-resource CLI admission failure remains |

The owner app/model processes retain their prior identities. No owner process,
node, calendar, setting or external account was changed. Campaign-owned helpers,
listeners and SDK children are cleaned up. No commit or deployment was made.

## Reproduction

From the repository root, use fresh output folders:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/campaign2/capability_audit.py --output data/campaign2-repeat/capabilities
.venv/Scripts/python.exe -X utf8 -m pytest tests/integration/test_campaign2_mcp_matrix.py tests/integration/test_campaign2_mcp_lifecycle.py
.venv/Scripts/python.exe -X utf8 scripts/campaign2/model_selection_audit.py --scorecard data/campaign2-repeat/capabilities/SCORECARD.json --output data/campaign2-repeat/model
.venv/Scripts/python.exe -X utf8 -m scripts.campaign2_verification.inventory --output data/campaign2-repeat/independent
.venv/Scripts/python.exe -X utf8 -m scripts.campaign2_verification.scorecard --inventory data/campaign2-repeat/independent/inventory.json --scorecard data/campaign2-repeat/capabilities/SCORECARD.json --output data/campaign2-repeat/claims.json
.venv/Scripts/python.exe -X utf8 -m pytest
```

Actual Ruff/Black positive cases used an isolated checker interpreter at
`data/campaign2-manager/checker-env/Scripts/python.exe`, with the owner's
interpreter/environment unchanged. When that optional checker is absent,
dependency failure must remain documented, not converted into a pass.
Do not rerun the already-applied metadata addendum over its archived evidence.
