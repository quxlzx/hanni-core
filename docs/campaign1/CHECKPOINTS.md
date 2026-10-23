# Campaign 1 checkpoints

## Baseline inventory

Baseline source commit: `227a628`. Tracked worktree was clean at campaign start;
five unrelated user files were already untracked and remain outside this work.

Read-only inventory of the original default registry found 172 capabilities:
applications 3, assistant 5, communications 4, computer 37, desktop 12,
development 14, files 23, media 16, network 6, productivity 39, security 5,
utilities 8. Full contracts include routing aliases, families, classifications,
schemas, risk, permissions, confirmations, requirements and execution metadata.
No handlers were invoked. Owner MCP SQLite inspection found zero persisted
servers and zero discovered tools; no provider connections were opened.

Canonical public inventory encoding is sorted UTF-8 JSON with a final LF:
SHA-256 `b4c6d91fa24c943ae20a6aceb55ba1e5492b522da67ac722c286a8f87c8600b8`.
The earlier private encoding omitted the final LF and used hash
`503f02001e5e522318af023004b4a76b9fc1f016d09ea55e411c7f3eaf7dcaf3`;
decoded contracts are identical.

Commands: `scripts/campaign1/manager_inventory.py` against isolated inventory
stores, and `scripts/campaign1/manager_regressions.py` against existing routing
development corpora. Private evidence lives under ignored `data/campaign1-*`.
The inventory script initially used outdated configuration attribute names;
correcting them to `max_tools_per_turn` and `max_tool_rounds` allowed the
discovery-only run to complete. No production code changed.

Corpus authoring and the independent final seal are in progress. Production
tuning and real model campaign runs have not yet started at this checkpoint.

## Existing routing baseline

The original evaluator ran without capability execution. Ten existing public
routing development corpora were captured; historical LLM holdouts were excluded.
The dialogue corpus uses its original dialogue evaluator, rather than the
single-turn JSONL loader. The first combined invocation stopped on that format
difference after capturing the main corpus; the corrected invocation completed
all ten. This changed only campaign tooling.

| Corpus | Strict passes | Cases | Additional evidence |
| --- | ---: | ---: | --- |
| Main routing | 1,129 | 1,131 | 99.82% |
| Multi-turn routing | 50 | 50 dialogues | 108/108 turns |
| Language v2 | 199 | 200 | 99.50% |
| Language v3 | 148 | 150 | 98.67% |
| Language v4 | 290 | 300 | 96.67% |
| Language v4b | 93 | 100 | 93.00% |
| False positives | 20 | 20 | 100% |
| Voice routing | 15 | 15 | 100% |
| Academic Calendar | 11 | 11 | 100% |
| Phrase probe | 29 | 30 | 96.67% |

Private reports retain every result and corpus SHA-256 under
`data/campaign1-manager/baseline-routing`. These are regression measurements,
not new-case or real-model quality evidence.

The existing `test_mcp_session`, `test_routing_benchmark`,
`test_routing_hardening`, `test_routing_safety_checkpoint`, and `test_llm_tools`
modules also completed successfully before campaign tuning. Configured quiet
output did not print a total; no exact test count is inferred. The command and
exit-code receipt are retained privately. These tests do not replace live-model
evidence.

## Independent final seal before tuning

The verifier sealed the private final protocol and oracles before any routing or
model evaluation and before engineering tuning. Seal SHA-256:
`b96221d8fe027ede7cfb1c75c059e50fa664b918cc4a4f092f08855a21174610`.
Only aggregate seal metadata was shared with the manager and engineer.

The final set specifies 256 cases, 273 owner turns, 16 multi-turn cases, 24 task
strata, and 129 distinct intended base capability IDs. Difficulty is 72 easy,
96 medium and 88 hard. Every registered definition will additionally receive
an independent controlled schema/authority audit. Final oracle content remains
private to the verifier during development.

The subsequent hash-only novelty audit compared all 273 final turn hashes
against 2,579 historical query hashes from 142 files and 330 current development
turn hashes, with zero collisions and no prompt or answer content emitted.
The seal metadata's `hashes_only_novelty_check_pending` field describes the
pre-audit state at sealing; the separate novelty receipt records completion.
Further development additions require another hash-only collision check;
the sealed final protocol must stay unchanged.

Development evaluation and architectural tuning are now permitted. Live model
campaign runs await the original-controller harness review and a bounded
development smoke test. Final evaluation has not begun.

## Frozen development corpus and first retrieval measurement

The engineer froze 370 individually authored cases specifying 380 owner turns
across 33 scenario families. SHA-256:
`5ec39bed6713be86a1be4d846df92f6e104bdce6cec8021562ca06c72c5e8a52`.
All 172 core IDs have a targeted request: 141 occur in required menu groups,
with the remaining 31 receiving blocked-action contracts. Authored schema and
denied-admission checks passed for all 172 definitions without handlers,
providers or models. These authoring checks are separate from the independent
authority matrix and actual controller testing.

The verifier's hash-only recheck against all 380 frozen development turns and
2,579 historical query hashes found zero final collisions. The final seal is
unchanged. Development query/turn review found zero exact or token-Jaccard
overlaps at the declared 0.80 threshold with checked public older development
queries. Predeclared controlled dependency sources cover all 172 definitions;
their SHA-256 is
`71658a249f98ff09d531a7c307d395dda1fce8409be894e362ed31f318dba2f6`.

The first original metadata-only development routing run passed 237/370 cases
(64.1%). This measures menu/disposition behavior with seeded context diagnostics,
not live-model selection, final response quality or actual sequential success.
Private evidence: `data/campaign1-engineering/retrieval-baseline-a`.

Observed development causes include negated dangerous verbs suppressing an
otherwise valid read, educational/quoted questions reaching operational routing,
broad provider terms outranking local objects, compound requests exposing only
one operation and weakly specified objects receiving irrelevant tools. Independent
reproduction precedes architectural changes. No oracle may be changed to match
observed behavior, and no permission grant may be inferred from request text.

## Development repair cycle 1: independent reproduction

The independent verifier reproduced all eight representative development
failures before any production repair. Additional freshly worded development
checks reproduced process negation, conceptual memory, quoted media and compound
security/git routing defects. Evidence is retained privately under
`data/campaign1-verifier/dev-repro-before-repair-b`.

The engineer's architectural regression suite independently preserved 15 failing
and four passing checks before repair. Scope is shared planning-text intent,
negative-constraint handling and bounded aggregation of independent observation
operations in `routing_intents.py` and `mcp/host.py`. Original allowlists,
permissions, confirmations and execution validators must remain intact. This is
an in-progress implementation checkpoint; fixes are not yet verified.

The first retrieval repair improved the frozen development score to 266/370,
with 29 improved cases and no development regression. The 19 new architectural
checks and 68 relevant existing tests passed. This is preliminary evidence,
not a final source freeze or live-model result.

Manager review identified a downstream completion-ledger problem: a single
receipt could complete a combined task whose menu contained two independent
operations. The verifier independently reproduced this for firewall/Defender,
git status/log and a semicolon-plus-CPU variant before repair, without model or
handler calls. A narrowly scoped completion-ledger repair is part of this cycle.

The independent authority audit covered all 172 definitions, including original
schema checks, chat-only and unknown-actor denial, stale authority, emergency
stop and denied-host gates. It passed 172/172 with zero handler dispatches.
This is controlled authority evidence, not real foreign-provider execution.

The original-controller harness is reviewable. Review corrected mutable input
recording, prevented original filesystem handlers from using default owner
directories, and separated diagnostic selection context, timing and counters
from controller results. A diagnostic uses the first captured original menu and
pre-turn history, without tool dispatch. Raw HTTP error bodies remain explicitly
outside the transparent recorder's coverage; error type/code/message are saved.
Live development smoke testing follows cycle verification and source stability.

## Development repair cycle 1: regression review reopened the freeze

The last preliminary development retrieval result was 286/370 (77.3%), with
49 formerly failing cases improved and no lost development passes. The relevant
141 tests passed. This measures routing metadata only, not model inference.

Manager comparison against the original ten public historical routing corpora
found 14 formerly passing cases that regressed, despite only 11 net lost passes.
The source freeze was rejected before any live inference or final evaluation.
The full suite on that earlier source finished with three failures, 2,116 passes,
two skips and 29 passing subtests in 361.71 seconds. Those failures exposed
model status being replaced by a generic process lookup; all receipts remain in
`data/campaign1-manager/cycle1-full-tests.*`.

Independent reproduction preceded repairs to model/process precedence,
first-person diagnostic and permission interpretation, and diagnostic context
across a comma. The next historical run restored every formerly passing case
and improved three others across the ten corpora. Case-level comparison, rather
than net scores, established zero regressions. A further public test exposed
later model catalog precedence for Llama and prompted removal of the premature
generic process lookup. The next source freeze still awaits verification and
test completion. The final protocol and oracles remain sealed and unchanged.

## Current context repair and live development admission

The independent verifier passes 34/34 context observations. Engineering passes
152 focused tests, including 40 new regression cases. Current production hashes:

- `routing_intents.py`: `b117f89d008d3c7a912f3805d371537bca903c884cad0186d83f7f78a6d07b20`.
- `mcp/host.py`: `45ff3866c505b397288680b465e2b9636efc7ca7a233b63986d1f25ee4760bdc`.
- `mcp/completion.py`: `6d3aa63e881d126caadb90d06ea5fdd46ea5a22243d0ac8613f95fb0c2e6350a`.

The second full suite imported source before the last Llama fix and ended with
one Llama failure, 2,128 passes, two skips and 29 passing subtests in 359.08s.
This run is retained as a mixed implementation-cycle result, not a clean final
source run. On stable current source, the four affected public benchmark,
architecture and recorder modules subsequently pass 86 tests and four subtests
in 2.95s. Fresh `cycle1c-routing` comparison of all ten historical corpora has
zero formerly passing regressions and three improvements against the baseline.
All these are non-inference tests.

Read-only model observation reconfirmed the mapped original GGUF file, SHA-256
`25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c`,
2,707,513,696 bytes, model PID 38832 and original launcher PID 46084. Health
passed and host RAM was 81.0%. No model manager or launch occurred for this
observation. No root test or competing inference remains running.

The manager authorizes the verifier's three-case real development smoke and,
if its raw recording and boundaries are verified, the complete serial
370-case development run. Final inference remains unstarted. Model-related
development failures may reopen engineering; final prompts remain withheld.

## Live smoke and supplemental dynamic permission checks

The original-controller live development smoke completed three owner turns with
five actual model calls and zero diagnostic probes in 14.55 seconds. It reported
zero evaluation failures and unchanged pinned source. All five real HTTP payloads
used the declared alias, temperature 0, top-p 1 and 256-token cap; tool requests
disabled parallel calls. Every response supplied prompt/completion/total usage.
Calculator execution used the original pure handler; machine statistics came
from a labelled controlled dependency; the educational answer used real native
text inference with no tool. Raw receipts and cleanup identity are under
`data/campaign1-verifier/live-dev-smoke-01`.

The manager additionally exercised all 13 original dynamic-confirmation
callbacks on triggering arguments. Every unconfirmed call was denied before a
handler, and every explicitly confirmed controlled placeholder was admitted.
There were zero unauthorized or original foreign-handler dispatches. The original
schemas, policy and callbacks remained intact. Receipt:
`data/campaign1-manager/dynamic-gates-a/results.json`. This supplemental matrix
tests conditions that the earlier exhaustive denied-actor audit only retained
as callback metadata; independent reproduction follows.

The full frozen development live run is authorized and serial. Smoke repetitions
are not added to its unique-case denominator. Predictive or extra claims in a
model's answer still need semantic review even when quoted source numbers match.

## Development inference in progress: preserved new failures

The full run is `data/campaign1-verifier/live-development-01`. Its reviewed
helper identity is PID 55816/create time 1791606154.7123172. Controller source,
configuration, fixtures and evaluator remain held during collection. The
linguistic audit reports overlapping form coverage and its limitations in
[DEVELOPMENT_COVERAGE.md](DEVELOPMENT_COVERAGE.md); it did not change frozen
cases, oracles or difficulty labels.

Independent review has found real numerical, identity, unsupported-causality and
completion-response faults, along with separate controlled-dependency defects.
The predeclared `process.top_memory` source uses `memory_mb` rather than the
original verifier's `rss_mb`. That is a fixture defect, retained as failed
end-to-end evidence; it is not evidence that the model generated a malformed
argument or that a real memory query succeeded.

A distinct original contract defect was independently reproduced without model
or physical effects: `process.list` emits `memory_percent`, whereas original
`inspect_result` requires `memory_mb`, rejecting valid original handler rows.
The verifier used the original handler with bounded mocked psutil observations,
preserving both production hashes and a pre-fix receipt under
`data/campaign1-verifier/process-list-contract-before-repair`. Narrow contract
alignment is approved after collection, retaining malformed-value rejection.
The engineer's proposal is [DEVELOPMENT_REPAIR_PROPOSAL.md](DEVELOPMENT_REPAIR_PROPOSAL.md).

One development request had no real inference because the original adaptive
admission ledger excluded the local model for `insufficient_ram_reserve` at an
estimated 5,688 context tokens. The native request and separate diagnostic were
both blocked. This remains a failed request with missing inference telemetry.
Resource safeguards remain original; missing usage is never reported as zero.
No final case has been evaluated or exposed to engineering.

## Complete development collection and cycle 2 admission

The complete first live development collection finished 370 cases and 380 owner
turns in 1,846.56 seconds, with zero case-preparation failures and unchanged held
source. There were 697 native model HTTP calls and 51 separate diagnostic HTTP
calls, each with reported usage. The manager independently counted 1,031,890
native tokens, 56,790 diagnostic tokens, 303 post-authority dispatch receipts and
370/370 preserved external identities. Controller-turn latency, including all
380 turns, was P50 1,649.58ms and P95 3,043.01ms. These preliminary raw aggregates
do not assert routing or semantic acceptance. Underlying-client calls are
separate from adaptive admission attempts that ended before HTTP.

The independent verifier reviewed the full 380 response/source transcripts.
The manager also independently checked four completed receipts: unsupported
video-export headroom, an incorrectly attributed process, a mismatched time-zone
source, and an exact correct SHA digest. Numeric word matching and result
verification status do not establish response entailment. Final review follows
the pre-final [semantic rubric](SEMANTIC_RUBRIC.md).

Independent fresh pre-fix dependent/history observations passed 7/14 and failed
7/14 without inference or handlers. An independent reversed-order dynamic gate
matrix passed all 13 original callbacks with zero unauthorized or foreign
dispatches. Failed private proof-writing attempts are preserved as harness
errors, rather than reported as production failures.

After raw collection closed and all live calls finished, the manager released
the development freeze for cycle 2. Engineering's prepared 100 tests first ran
on the unchanged source: 37 failed and 63 passed, with no errors or skips. The
failures include 14 dependent/context cases, five process metric cases, and 18
unit aliases/schema cases. Pre-fix XML is retained under
`data/campaign1-engineering/cycle2-before.xml`.

The approved repair scope adds narrowly related original process-result
verification and unit argument contract alignment to shared routing/context
and completion bookkeeping. Generic dependency fixtures may receive a separately
versioned contract correction, preserving their original bytes and first-run
failures. Model, permissions, resource admission, session answer substitution and
unrelated subsystems remain outside this repair. The final corpus is still
untested and withheld from engineering.

## Cycle 2 independent review reopened the production freeze

The first cycle 2 relevant suite passed 191 tests. Current contract validation
passed all 172 definitions and frozen development metadata improved from
286/370 to 287/370. The independent structural dependent/history check passed
14/14, but its broad PID-details expectation was found to exceed the original
`process.inspect` result contract: PID existence supplies neither name nor
memory. This limitation is retained rather than called full completion.

Ten historical corpora exposed one formerly passing regression: a launch plus
an explicit PC temperature read lost its second tool. Independently worded
launch/read and PID-plus-GPU controls reproduced three failures out of ten;
same-file contents and same-PID existence controls passed. The repair must
preserve new positive operations and sources rather than treat every occurrence
of a demonstrative as a redundant response refinement.

A clean full suite on the held cycle 2 source finished with two failures,
2,246 passes, two skips and 33 passing subtests in 363.13 seconds. Both failures
were strict stored argument-schema drift checks for the planned `unit.convert`
contract change. The original failing output is
`data/campaign1-manager/cycle2-full-tests.log` and its XML. The manager reopened
the freeze only after the suite closed, authorizing the reproduced clause
boundary repair and the repository's narrow stored unit-schema migration.
Historical queries, answer objectives and required tools must remain unchanged;
unplanned schema drift detection must stay strict.

The manager preserved public baseline inventory metadata and refreshed the
current 172 contracts. The new canonical contract SHA is
`0a1dffed7a6b47ac50402e64e6de90e69a5d9915d44043452a8d842a8417ec8b`.
Live replays and final execution remain pending complete repair verification.

## Stable cycle 2b: clean broad verification

The refrozen patch passed 200 focused checks, all 172 contract checks, and
287/370 frozen development metadata cases with no lost development pass.
The fresh full suite then passed 2,261 tests and 33 subtests in 360.79 seconds,
with two skips. Evidence: `data/campaign1-manager/cycle2b-full-tests.*`.
Ten original public routing corpora independently restored every formerly
passing case and improved three, with zero casewise regressions. This is a
stable-source full run, unlike earlier failing or mixed-source checkpoints.

Independent migration review verified exactly two schema-only row changes,
unchanged prompts/objectives/results/tool annotations, and continued rejection
of unplanned schema, risk and result-field drift. Twelve original unit handler
and validator controls passed. Generic v2 seams and scorer measurement boundaries
received independent tests before actual development replays.

The original relative-path argument grading file is retained. Correcting the
grading root, while preserving every frozen predicate and raw response, raised
literal predicate passes from 41 to 87 out of 135. Thirty predicates had no
expected tool call; 105 had admitted arguments. Separate semantic identity
checks pass 89/106 admitted fields and 91/107 explicit raw fields; eight authored
sentence-punctuation limitations remain uncredited. All 291 eligible raw tool
proposals satisfy the actual sent schema. These distinct measures cannot be
combined into a blanket claim of correct arguments.

The manager independently matched all 380 semantic review records to their
actual raw receipt hashes, with no missing, duplicate or unexpected reviews.
The initial development run has 206/290 grounded eligible responses, 84 grounding
failures and 90 unavailable/unscorable grounding dimensions. Accurate complete
responses are 175/380. Every one of the other 205 turns retains a primary failure
category; controlled source limitations are explicitly flagged on 89 turns.
These are initial v1 development outcomes, not final-source or final acceptance.

A fresh model-file hash still matches the original GGUF/PID/launcher. Host RAM
was elevated after tests. The original external model remains protected from
manager eviction; actual adaptive admission requires at least 2GiB available
RAM and 256MiB free VRAM. The existing guard decides admission during quiet serial
development replays. No memory guard, owner process, server cache, model or
configuration was changed to improve acceptance. The final corpus is unclaimed.

## Actual cycle 2b development replay review

The quiet preflight used one development case, two native HTTP calls and no
diagnostic probe. The independently chosen replay then collected 18 existing
development cases and 20 turns. Four newly authored boundary cases stopped
before inference because their forbidden-tool annotations contained nonexistent
IDs. Those four preparation failures and their original protocol are preserved.
A separately versioned correction changed only the invalid prohibition IDs;
the same requests and objectives collected four more turns without preparation
failures. This is a verifier authoring mistake, not a production failure.

Across the 22 actually collected cases and 24 turns there are 58 native HTTP
calls, zero diagnostic calls and 28 post-authority handler dispatches. Every
case cleanup preserves the original external server and launcher. Full review
finds 20/22 grounded eligible replies, 19/24 complete task coverage and 18/24
accurate, complete responses. The original unit, time, process-list verification
and actual CPU-history fixes have real reply/receipt evidence. Two factual
failures remain: invented file contents following `file.stat` without a content
read, and general task smoothness inferred from one resource snapshot. Existence
only PID details, remaining-video-memory wording and generic media/action
acknowledgments retain their incomplete outcomes.

The Manager independently verifies all 24 unique review rows against the
matching actual raw receipt SHA-256 and case/turn identity. Evidence:
`data/campaign1-verifier/development-replay-v2-review.json` and
`data/campaign1-manager/replay-v2-review-integrity.json`. The replay uses corrected
generic dependency version 2, so its aggregate improvement is not presented as
an identical-fixture before/after experiment. Preflight, repeats and corrected
annotation attempts do not enlarge the 626 main development/final case count.
Production tuning is closed before the untouched final evaluation.

## Untouched final gate and once-only claim

All 29 final harness boundary checks passed before the final claim. The Verifier
archived 230 exact production/config/harness/fixture/rubric and schema-migration
files. Archive SHA-256:
`515d8bcb989c6b66848eb35771e23665fb5c59709df78d555ac3b5e1802f8975`.
The Manager independently checked every archived member and every current file
against the proof, without opening final queries or answers. Source version 2
retains SHA `29bc6a44986dd5b46dc8432d2eb7199e0588970f42f7f47d1b767f3acab2c50a`;
the original final seal is unchanged. Evidence:
`data/campaign1-manager/final-freeze-integrity.json`.

The whole final started in `data/campaign1-verifier/live-final-01` with a durable
global execution claim, a fresh private Python cache prefix, all 256 cases and
273 owner turns, no selection filters and no retries. Original PID, launcher,
creation times, command hash, health and available-capacity resource guards were
checked before launch. No new model, foreign helper or full assistant startup
was authorized. The Verifier owns the serial CLI and original server remains
externally owned. Acceptance remains pending complete collection and independent
review; source changes or resource failures are retained as failures or untested
cases rather than bypassed.

## Whole final collection completed

The once-only collection finished all 256 planned cases and 273 owner turns in
1,233.47 seconds with zero preparation failures. Source hashes remain unchanged.
There are 399 native HTTP calls across 172 owner turns and 26 separately recorded
diagnostic calls. All 425 HTTP calls have actual usage. Another 75 diagnostic
attempts stop before HTTP with `ModelSelectionError`; the corresponding generic
native failures do not always reveal the same precise cause and retain unknown
native cause rather than inheriting a diagnostic explanation.

Native usage is 599,373 prompt plus 15,644 completion tokens, total 615,017.
Diagnostic usage is 28,855 plus 842, total 29,697. Native tokens per fully
observed inference turn are mean 3,575.68, P50 2,984.5 and P95 6,140.1 (n=172).
Controller latency includes all 273 turns and ten recorded controller errors:
P50 1,398.57 ms, P95 3,382.60 ms. The 399 native model invocations have P50
784.38 ms and P95 1,744.97 ms. These costs do not represent successful completion
or population latency guarantees.

The run records 198 post-authority handler dispatches and preserves the external
server identity at all 256 cleanups. A fresh read-only postrun hash independently
matches the original 2,707,513,696-byte GGUF, server PID, launcher, creation times
and command SHA; original client health remains true. No owner model/cache,
configuration, memory guard or foreign process was changed. Evidence:
`data/campaign1-manager/live-final-collected-metrics.json` and
`data/campaign1-manager/model-after-final.json`.

Complete independent semantic review and final acceptance remain pending at this
collection checkpoint. No further final inference or retries are permitted.

## Final verification and acceptance closeout

Independent review now covers every one of the 273 final turns. The Manager
checks all 273 unique raw/review hashes, all 230 final source files, actual HTTP
case counts and five independently read final response/receipt examples.
Semantic review SHA-256:
`46a656f7d6fcc6bbfd3ef2ec6bbf4206a4cbdc4dba81acb6e251a5aca143319e`.
The exact owned final CLI has exited; all 256 cleanup receipts are closed and
the original model/launcher identities remain unchanged. The first cleanup
observer used a different command encoding; that failed comparison remains
preserved beside the corrected comparison using the frozen provenance encoding.

Final required-group recall at K=8 is 194/273 (71.06%), tool-menu sufficiency
161/238 (67.65%), conditional native selection 111/118 (94.07%), and raw
sent-schema validity 179/180 (99.44%). Annotated admitted semantics are 38/44
(86.36%). Forty-three sufficient-menu tool turns have no native HTTP, so
selection support across every sufficient-menu tool turn is 111/161 (68.94%).
Explicit no-tool decisions pass 9/9; invented names, fixed-argument conflicts,
outside-menu names and unauthorized dispatch turns are zero. Thirty-four native
proposals are annotation-inappropriate and 155 menu entries are annotation-
irrelevant. These are distinct from authority violations.

Grounded answers pass 135/180 (75.00%); 45 fail grounding and 93 have unavailable
or not-applicable grounding. Complete task coverage is 108/273, and complete,
accurate answers 88/273 (32.23%). All 185 failures have a primary cause:
retrieval 84, model decision 9, execution 60 and response synthesis 32. Source
limitations are explicit on 53 turns and authored-oracle limitations on 15;
neither class is silently credited. Semantic argument checks do not inherit the
typed-schema passing score.

Actual inference independently covers 557 new cases: 481 native controller and
76 separately labelled diagnostic-only cases. The 626 main cases have 653
recorded/reviewed turns; 69 cases lack any model HTTP evidence. Preflight,
replays and annotation corrections do not enlarge the new-case count. Final
post-authority wrapper entries split into 84 original executions, 108 controlled
dependency handlers and six owned-path rejections; wrapper entry does not prove
physical execution.

The frozen report helper's final intent-field mismatch is preserved. A separate
source-hashed annotation supplement accounts for all 172 base definitions,
129 final intended IDs and eight blocked-intended IDs; no source, final oracle
or acceptance rule changed. Reports and supplements are in `docs/campaign1/`.
Recall and selection acceptance targets are unmet. Observed schema validity,
bounded authority and ten-corpus regression targets pass within their stated
scope. Final tuning and retries remain closed, and no unrelated subsystem was
modified.
