# V3.6 engineering evidence and limits

The campaign used the current configured cached Qwen3.5-4B-Q4_K_M model through
HANNI's original controller, tool registry, MCP policy, local stores and workflow
service. One owned inference runtime served all actual model cases serially.
Native verification attached to the real Windows client. The implementation did
not change the production model, permission policy, rollout flags or user data.
The independent verifier owns acceptance scores; execution labels below are not
claims that the generated responses passed its quality rubric.

## Production repairs

| Finding | Repair | Engineering evidence | Independent acceptance |
|---|---|---|---|
| Google descriptors declared a nonexistent nested `data` field; local task/folder contracts also disagreed with their actual payloads | Correct operation-specific result metadata, preserving original payloads and gates | `repairs-cycle2.xml`, 118 focused passing tests | Verifier separately accepted original adapter/task payloads with controlled provider |
| No recent Windows event errors raised an error | Treat only PowerShell `NoMatchingEventsFound` as an empty event list; propagate denied access and other errors | Genuine PowerShell cmdlet-error tests; live Application log returned an empty list successfully | Verifier accepted distinct no-match, denial and lookalike errors |
| Cached speech decoder hallucinated “You” for digital silence | Return empty for empty or exactly all-zero PCM; any nonzero PCM still reaches the unchanged decoder | Actual cached `small.en`, CPU/int8 baseline retained; exact-zero and nonzero regression | Verifier independently reproduced baseline and confirmed empty candidate result with zero decoder calls |
| Missing mute measurement was reported as `False` | Publish `muted: null`, unknown wording and nullable contract | Unknown endpoint regression | Backend accepted; actual model still made an unsupported unmuted claim in one development rerun |
| Model confused grep content query with filename filter and reported a false absence | Describe/default actual argument semantics; expose query/filter/scan count and whether any file was searched | Distinct content/filter fixtures; no-scan result states unknown | Accepted independently with a different phrase; development model rerun found actual matching files |
| File metadata omitted size, followed by an invented response size | Return actual `stat().st_size`; folders return null; preserve full SHA and missing-path compatibility | Byte/hash/readback regression | Model byte count improved; contradictory response verification wording remains a quality failure |
| A local note containing Friday was incorrectly executed as Google Calendar creation | Require calendar destination/activity-domain intent before date parsing; retain local storage authority and ignore quoted/colon payload for creation consent | 113 relevant tests; same sealed note request now invokes no tool/provider and receives original policy denial | Independent novel local note/task/file/record and genuine calendar cases accepted |

All raw failed cases remain in ignored campaign evidence. The new calendar guard
does not authorize local note/task writes through chat: those capabilities retain
their original policy barrier. A date in stored text does not grant a provider
write. No live Google account/API or cluster mutation was tested by this harness.

The first destination guard also rejected legitimate legacy medical, social and
academic scheduling. A prospectively sealed eleven-case activity-domain cohort
reproduced six missing positive intents before the rule expansion. A documented
activity-noun taxonomy now covers those categories, including tutor/tutorial,
tuition and teaching morphology. True numeric clock colons are preserved while
numeric-leading stored-body colons cannot grant authority. The unchanged original
corpus audit and 177 focused checks pass; the independent reviewer accepted all
46 final core/domain/boundary cases after retaining its earlier tutoring rejection.
No model cohort was repeated for this compatibility addendum. The final 24 unseen
response scores describe the prior candidate and are not promoted or re-scored.

## Actual model coverage

The original dynamic manifest contained 172 capabilities. All 172 natural-language
requests were sealed before the first inference, with accepted operation aliases
declared in advance. Version 1 was retained when the isolated launcher changed;
version 2 amended only owned process/backend addresses before any output.

| Measurement | Baseline |
|---|---:|
| Sealed original capability requests attempted | 172 |
| Actual configured model inference requests | 331 |
| Capabilities eligible under original MCP policy | 132 |
| Cases with an actual model tool menu | 128 |
| Exact target capability selected | 103/128 |
| Predeclared equivalent operation selected | 108/128, 84.375% |
| Whole-turn latency, P50 / P95 | 1.665 s / 3.874 s |

The requested 95% selection threshold was not met. These numbers measure selection,
not grounded answer quality. The initial harness execution labels missed several
independently found response defects, including the grep false absence and
wrong-scope local-note provider write. The independent review must supersede
those labels when reporting response quality. Original deterministic/blocked
paths have no model-selection measurement; a separate genuine response-only
inference is retained without being counted as tool selection.

Evidence: `data/v36-engineering/sealed/model-cases-v2.json`,
`model-outputs-v2.jsonl`, `model-baseline-summary.json`. Development repair reruns
retain the same previously frozen requests and are not held-out validation.

All 24 additional operations in the actual private desktop registry also received
sealed, genuine Qwen response-only inquiries, recorded in
`private-desktop-inquiries-cycle1/{sealed-cases.json,results.jsonl}`. They retain
explicit BLOCKED model-selection status because the normal chat controller has
no authority/menu for that separate owner-only registry. No private tool was
imported into chat, no handler ran, and denial text is not a completed desktop
operation. The manager and independent verifier separately tested the actual
fixed desktop operations directly. The three imported local SDK capabilities
have their own manifest and actual model scenarios below.

## Versioned schema-only audit migration

The historical `evals/llm_tools/capability_coverage_v1.jsonl` remains byte-for-byte
unchanged, SHA-256
`70468c1c186ef69b6f065120ea548f6698dc39dc2676e0afa98c10d178930833`.
The default metadata audit now uses the explicit v2 corpus. All 264 prompts,
required tools, argument/claim expectations, IDs, risk and behavioral oracles
remain unchanged. Its migration manifest records 59 cases with schema-only
metadata changes caused by independently reproduced contract repairs. One
separately approved addendum provides a schema-only `file.grep` fixture for a
new supplemental read-only menu in `COV-FILE-SEARCH-01`; the original required
`file.search` expectation is unchanged. Strict drift detection remains active.
Five coverage/invariance tests pass; the initial failed migration check is
retained. This migration changes no actual model cohort or quality score.

## Original persistent workflows

Three sealed goals were submitted once through the original authenticated
workflow API, using the original resident client and planner. Original model
inputs, outputs, schemas and latency were recorded without modifying results.

| Goal | Actual result |
|---|---|
| Analyze isolated text folder and prepare managed report | Planning blocked: treated the folder as a file and could not bind a supported required capability |
| Create/read/complete/verify isolated local task | Invalid bounded model plan; no verified completion |
| Retrieve synthetic project memory and prepare report | Proposed unrelated model/system diagnostics instead of saved memory; proposal cancelled before execution |

Verified completions: **0/3**. Scheduler unit/integration successes are not evidence
that Qwen completed these goals. The first observation harness omitted the private
GET token; its failures were retained and observations resumed with the same
already-submitted workflow IDs, without replanning. Evidence:
`actual-workflows-cycle1/{sealed-goals.json,results.jsonl,results-auth-resumed.jsonl}`
and `application-cycle4/actual-controller-model.jsonl`.

## Local MCP, providers and hardware

An actual stdio MCP SDK server provided three dynamically discovered tools with
full schemas. The real manager imported them into the original registry after
explicit scoped fixture approval. All three valid calls succeeded; unknown-field
calls were rejected before server dispatch. The confirmed create operation was
read back from durable test-owned storage. Qwen selected and executed both read
tools through the original controller, **2/2**. Its write tool remained blocked by
the unchanged model-facing policy; response-only inference is distinguished from
selection. Earlier test-server API/classification setup failures remain preserved
and happened before any model inference. Evidence:
`actual-external-mcp-cycle4/{inventory.json,sealed-cases.json,results.jsonl}`.

Google tests used the original GoogleAccess/services adapters with a controlled
provider dependency, synthetic vault and real response parsing. The focused suite
covered calendar discovery/agenda/next/create+readback, aliases, timezone/date/DST
handling, missing authentication, missing scopes, provider timeout and duplicate
uncertain-write suppression. Final dedicated suite: 12 passing tests. Live Google
operations remain BLOCKED; a synthetic provider pass is not live integration proof.

Initial native account discovery exposed a global Windows Credential Manager
boundary despite temporary local data. The controlled launcher now binds an
explicitly empty vault before original controller/desktop imports. Initial raw
evidence and `application-cycle1/isolation-erratum.json` retain that finding.

Actual installed voice/device discovery found 15 input devices and two Windows
English voices. Generated digital silence traversed real cached VAD/STT without
recording a microphone or playing a speaker. The manager owns the later bounded
supervised microphone test and its owner-inactive classification. Continuous
capture, webcam/screen pipeline and unavailable vision inference were not invented.
Default LAYA rollout gates and experimental behavior remain unchanged.

The engineer owns only campaign launch/model lifecycle. All seven launcher cycles
closed their exact owned original controller/model. The final accepted source was
launched again in cycle 7 after independent acceptance; actual chat/model health,
registry, telemetry, workflow and empty-vault calendar checks passed with no model
inference. Production config hashes and isolated copies matched. Original
authenticated shutdown returned exit 0; exact controller 35060/model 53284 were
absent and the owned endpoint closed. Source/config hashes remained unchanged.
Proof: `application-cycle7/lifecycle.json`. No user process was killed.
Raw outputs, device inventories, synthetic stores and
screenshots remain under ignored `data/`; this document contains no tokens,
account identities or personal content.
