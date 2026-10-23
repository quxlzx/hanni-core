# Campaign 1: core routing and response quality

Campaign complete; the untouched final evaluation does not meet the routing
acceptance targets. Required-tool recall is 71.06%, conditional native tool
selection is 94.07%, and accurate complete responses are 88/273 (32.23%). Observed
schema validity is 99.44%, unauthorized dispatches are zero, and ten existing
public routing corpora have zero casewise regressions. Baseline is `227a628`.
The sealed final ran exactly once after development tuning closed. Failed,
unavailable and source-limited cases remain in the report.

## Registry and controller scope

The original default registry contains 172 capabilities in 12 metadata families.
The complete contracts, argument types, confirmations, effects and permissions
are in [capabilities.json](../../evals/campaign1/capabilities.json). Each ID's
model wire name, routing family, classification and owner-policy eligibility are
in [routing-catalog.json](../../evals/campaign1/routing-catalog.json).

| Metadata family | Registered capabilities |
| --- | ---: |
| Applications | 3 |
| Assistant | 5 |
| Communications | 4 |
| Computer | 37 |
| Desktop | 12 |
| Development | 14 |
| Files | 23 |
| Media | 16 |
| Network | 6 |
| Productivity | 39 |
| Security | 5 |
| Utilities | 8 |
| Total | 172 |

The owner policy is read-only with 13 existing action exceptions, an eight-tool
menu and three tool rounds. It admits 132 of the 172 definitions. Ineligible
tools remain part of the inventory and denied-action tests. The persisted MCP
store was inspected read-only: zero configured servers and zero discovered
external tools. This is default-controller and persisted-discovery coverage,
not a claim that an unrelated running process has no transient registrations.

## Test independence and real inference

The Engineer authored 370 new development cases and 380 owner turns. The
independent Verifier authored and sealed 256 final cases and 273 owner turns
before tuning. Together they specify 626 cases and 653 owner turns. The final
corpus and answers were withheld from engineering. Development contains ten
real sequential conversations; final contains 16. Seeded-history menu probes
are labelled separately from those conversations.

Actual HTTP evidence covers 557 unique new cases: 481 through native controller
inference and 76 through separate diagnostic-only evaluation. Sixty-nine of the
626 planned cases have no model inference evidence. Native inference covers 496
owner turns and diagnostic-only evaluation another 77, for 573 actual model
evaluated turns. All 653 controller turns are recorded and independently reviewed.
The [model coverage matrix](MODEL_EVALUATION_COVERAGE.json) distinguishes the
authored, attempted, native, diagnostic and unavailable denominators. The claim
of more than 500 model-evaluated new cases includes those 76 diagnostics; native
controller inference alone covers 481 cases. Preflights and development repeats
are excluded from these counts.

Development spans 33 scenario families, with 318 medium and 52 hard cases and no
easy stratum. Final spans 24 task strata with 72 easy, 96 medium and 88 hard cases;
actual turns inherit those labels as 72, 96 and 105. Difficulty is author-defined,
not inferred from success. The [linguistic audit](DEVELOPMENT_COVERAGE.md) records
direct requests, paraphrases, slang, typos, ambiguity, mixed-domain, multi-tool,
no-tool, quoted-data and real follow-up coverage. Labels overlap. Only five
development turns have clear slang and three have deliberate typos; this is
limited coverage, not evidence of broad dialect or spelling robustness.

The final seal is
`b96221d8fe027ede7cfb1c75c059e50fa664b918cc4a4f092f08855a21174610`.
Hash-only novelty checks found no collisions against 2,579 historical query
hashes and all 380 frozen development turn hashes. The Engineer additionally
reviewed exact and token-overlap comparisons with public prior development
requests. These checks support independence; they do not establish originality
merely through changes of names or numbers.

The [protocol](PROTOCOL.md) specifies the original controller, adaptive model
client, registry validation, permissions, confirmation, emergency stop and
result/completion handling. The real existing server uses
`Qwen3.5-4B-Q4_K_M.gguf`, SHA-256
`25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c`,
Vulkan1, one serving slot, a 16,384-token context and disabled thinking. Its
original PID and launcher are preserved; no model was launched or replaced.

The evaluation profile is temperature 0, top-p 1 and 256 output tokens with
three tool rounds and zero model-routing fallbacks. Owner generation defaults
are temperature 0.35, top-p 0.9 and 768 output tokens. The report must not present
these bounded evaluation results as those production-generation measurements.
Original transport attempts, model calls and usage are recorded independently.

Foreign provider, power, GUI, communication and credential effects are controlled
or denied. Original pure utilities and explicitly bounded disposable file, note
and todo handlers may execute. Controlled receipts are source evidence for
synthesis tests, not evidence of real hardware or provider state. A separate
diagnostic model probe is allowed only when the native controller made zero model
calls; probes never substitute a controller answer or dispatch a tool.

## Architectural repair evidence

Production edits are confined to shared request intent, MCP menu planning,
completion bookkeeping, process-result verification and unit argument contracts.
The Engineer's [findings](ENGINEERING_FINDINGS.md)
describe independently reproduced negative-constraint, quoted-language,
educational-intent, operation-precedence, compound-menu and partial-completion
faults. Fixes use operation and context structure rather than benchmark phrase
exceptions. No production permissions, model settings or unrelated subsystem
was changed.

Development metadata checks improved from 237/370 to 287/370. These are retrieval
and disposition checks, not live-model accuracy. The first historical comparison
exposed 14 regressions and reopened the freeze. Independent context reproductions
preceded correction. The subsequent ten-corpus comparison restored every formerly
passing case and improved three others. Case-level comparison prevented those
improvements from hiding a regression.

All 172 definitions passed the independent controlled original-authority matrix,
including schema, denied actor, stale authority, emergency stop and denied-host
checks, with zero handler dispatches. This matrix does not replace measurement
of actual dispatches during live evaluation.

The second repair cycle aligns process-list verification with the original
handler's `memory_percent` field and accepts the full-word and IEC unit aliases
advertised to the model. Existing unit factors remain unchanged, including the
legacy 1,024-byte `KB` convention; the description now states that convention.
The original host rejects missing or null required conversion fields before
dispatch. Two stored historical argument-schema rows received an explicit,
audited schema-only migration. Their queries, expected results and routing
objectives remain unchanged, and unrelated contract drift is still rejected.

Clause handling now distinguishes an answer refinement from an additional
operation or observation. A same-file content request may share its read, while
an application launch followed by a PC temperature check retains both tasks.
Actual conversation history can resolve a CPU follow-up to a new top-process
measurement. An existence-only PID result still cannot supply process identity,
memory or CPU; the campaign retains that original capability limitation.

The stable full suite passes 2,261 tests and 33 subtests with two documented
skips. Ten existing public routing corpora have zero casewise regressions and
three improvements. Earlier regressions and failing suite attempts remain in
the [checkpoint log](CHECKPOINTS.md), rather than being replaced by the clean run.

## Initial development measurements

The complete initial development run used fixture version 1 and the first repair
freeze. Its results guided the second repair cycle; they are not final-source
acceptance scores. All 370 cases and 380 owner turns have raw records and an
independent semantic review matched to each receipt's SHA-256.

| Measure | Initial development result | Meaning |
| --- | ---: | --- |
| Required-tool Recall@1 | 219/318 (68.87%) | Individual required-tool groups |
| Required-tool Recall@3, @5, @8 | 249/318 (78.30%) | Individual required-tool groups |
| Tool-turn menu sufficiency | 237/306 (77.45%) | All requirements available together |
| Native selection with sufficient menu | 219/228 (96.05%) | Correct conforming proposal; excludes unavailable menus |
| Raw sent-schema validity | 291/291 (100%) | Types and required fields, not semantic correctness |
| Admitted annotated field semantics | 89/106 (83.96%) | Observed eligible argument fields |
| Explicit raw annotated field semantics | 91/107 (85.05%) | Includes raw model fields before fixed-argument merge |
| Literal frozen argument predicates | 87/135 (64.44%) | Thirty expected calls were missing |
| Native no-tool decisions | 22/22 (100%) | Frozen no-tool requests |
| Invented capability names | 0/291 (0%) | Does not measure invented answer facts |
| Annotation-inappropriate proposals | 55 | Proposed registered tools outside the request objective |
| Annotation-irrelevant menu exposures | 223 | Tools exposed outside frozen relevance annotations |
| Grounded eligible answers | 206/290 (71.03%) | Full semantic review of material claims |
| Accurate and complete answers | 175/380 (46.05%) | Unconditional task and response success |
| Unauthorized dispatch turns | 0 | Original authority enforced |

Eight admitted field comparisons have authored sentence-punctuation limitations
and remain uncredited. The original relative-path grading-root mistake produced
41/135 literal predicate passes; correcting only the grading root yields 87/135
against the same frozen predicates and raw answers. Both versions are retained.
The 90 unavailable or unscorable grounding dimensions are not successful answers.
Among 205 incomplete or incorrect responses, primary causes are retrieval 57,
model decision-making 18, execution 69 and response synthesis 61. Controlled
dependency limitations are separately flagged on 89 turns. Multiple causes and
per-turn evidence remain available in the independent review.

Native inference issued 697 HTTP calls across 324 owner turns, using 1,005,520
prompt and 26,370 completion tokens. All calls have actual server usage. Native
tokens per inference turn have mean 3,184.85, P50 2,970 and P95 5,128.35; repeated
context is included. Controller latency over all 380 turns, including errors and
deterministic responses, is P50 1,649.58 ms and P95 3,043.01 ms. The 697 model
invocations have P50 790.66 ms and P95 1,693.82 ms. Forty streamed replies have
P50 217.88 ms and P95 498.35 ms time to first token.

There are 56 native turns with no underlying model invocation. Fifty-one received
separate, non-dispatch diagnostic inference, using 56,790 tokens; five diagnostic
attempts were blocked before HTTP by original admission. Diagnostic probes do not
improve controller selection, response accuracy or latency. A native admission
failure remains an end-to-end failure. The external model identity was preserved
at every one of the 370 case cleanups.

## Untouched final routing and argument results

All 256 final cases and 273 owner turns were collected with zero preparation
failures. The 230-file source/configuration/harness/fixture/rubric and migration
freeze stayed unchanged, verified independently before and after collection.
The once-only claim remains in force; no final failure was rerun or used to tune
production. The exact byte archive SHA-256 is
`515d8bcb989c6b66848eb35771e23665fb5c59709df78d555ac3b5e1802f8975`.

| Final measure | Result | Acceptance implication |
| --- | ---: | --- |
| Required-tool Recall@1 | 171/273 (62.64%) | Individual required-tool groups |
| Required-tool Recall@3, @5, @8 | 194/273 (71.06%) | Below the 95% recall target |
| All-turn menu sufficiency | 184/273 (67.40%) | Includes no-tool and denied dispositions |
| Tool-turn menu sufficiency | 161/238 (67.65%) | All required tools must be available |
| Native conforming selection, sufficient menu | 111/118 (94.07%) | Below 95% even on the evaluated subset |
| Native name-only selection, sufficient menu | 111/118 (94.07%) | Kept separate from protocol conformance |
| Raw sent-schema validity | 179/180 (99.44%) | Meets 98% for observed emitted proposals |
| Admitted annotated argument semantics | 38/44 (86.36%) | Does not establish 98% semantic correctness |
| Explicit raw annotated argument semantics | 40/46 (86.96%) | Before deterministic merge/defaults |
| Literal frozen argument predicates | 36/76 (47.37%) | Thirty-four expected calls are missing |
| Controller tool/disposition coverage | 140/273 (51.28%) | Receipt/disposition success, not complete answers |
| Abstention on explicit no-tool turns | 9/9 (100%) | Absence of proposals, not successful explanation |
| Invented capability names | 0/180 (0%) | Registered names only; answer facts evaluated separately |
| Annotation-inappropriate proposals | 34 | Does not imply unauthorized dispatch |
| Annotation-irrelevant menu exposures | 155 | Frozen relevance annotations |
| Outside-menu/unusable proposals | 0 | Original sent-menu identities |
| Fixed-argument conflicts / parallel-call violations | 0 / 0 | Raw proposal protocol |
| Unauthorized dispatch turns | 0 | Meets the observed safety target |
| Existing public routing casewise regressions | 0 | Ten measured corpora, three improvements |

Required-tool groups and owner turns happen to both number 273; they are distinct
denominators. Conditional model selection excludes non-inference gaps. The
tool-turn sufficient-menu denominator is 161, while only 118 native turns are
selection-evaluable. Forty-three sufficient-menu turns have zero native HTTP;
41 have a separate diagnostic admission error. Correct native selection is
supported on 111/161 (68.94%) of all sufficient-menu tool turns. A high conditional
score could not establish full model
coverage even if it met the target. The schema result measures emitted proposals,
including its one invalid proposal; it does not count missing expected calls as
correct arguments. Semantics measure only frozen annotated fields, not every
field on every registered contract.

Only three of the nine explicit no-tool turns have native model HTTP evidence;
six have no model inference. Two also expose annotation-irrelevant menu tools.
The 9/9 abstention count therefore does not prove nine successful model decisions
or useful conversational replies. Actual no-tool replies remain subject to full
answer review, including unsupported guarantees, unwanted completion warnings
and failure to answer a hypothetical question.

Final collection took 1,233.47 seconds. Native inference ran on 172 owner turns
with 399 HTTP calls; 101 turns had no native underlying-client invocation. Twenty
six of these received separate non-dispatch diagnostic HTTP inference; 75 probes
stopped before HTTP with `ModelSelectionError`. Some native deterministic and
fallback failures suppress their precise cause. These remain unknown native
causes; an explicit diagnostic admission reason is not transferred to a native
answer. All gaps remain in unconditional outcomes.

All 399 native calls have server usage: 599,373 prompt plus 15,644 completion
tokens, total 615,017. Per fully observed native inference turn, mean usage is
3,575.68 tokens, P50 2,984.5 and P95 6,140.1 (n=172). All 26 diagnostics have usage,
28,855 prompt plus 842 completion tokens, total 29,697, kept outside native
costs. Missing pre-HTTP inference is not an estimate of token demand.

The 198 post-original-authority wrapper entries comprise 84 original-handler
executions, 108 controlled dependency handlers and six explicit owned-path
boundary rejections. Wrapper entry is not physical execution. Power, GUI,
communications, SSH and foreign providers remain controlled or denied. No
unauthorized handler execution or foreign effect was observed in this bounded
campaign; these counts do not certify untested physical integrations.

Controller latency over all 273 turns, including ten recorded errors and
deterministic responses, is P50 1,398.57 ms and P95 3,382.60 ms. Native invocation
latency is P50 784.38 ms and P95 1,744.97 ms (n=399). Fixture setup/cleanup and
diagnostic overhead are separate. These are sequential measurements on a shared
existing endpoint with caches, not population latency guarantees. Postrun
read-only checks confirm the original model SHA, PID, launcher, command, owner
generation settings and healthy endpoint. All 256 case identity checks pass.

## Independent final answer review and failure causes

Every one of the 273 final replies was read against actual retained history,
frozen objectives, whole responses, returned receipts and reference evidence.
The Manager independently matched all 273 unique review rows to their raw
receipt hashes, with no missing, duplicate or extra row. Final results are:

| Response measure | Result |
| --- | ---: |
| Grounded eligible answers | 135/180 (75.00%) |
| Grounding failures | 45/180 (25.00%) |
| Unavailable/not applicable grounding | 93/273 |
| Complete task coverage | 108/273 (39.56%) |
| Accurate and complete answers | 88/273 (32.23%) |
| Explicit source/reference limitations | 53 turns |
| Authored-oracle limitations | 15 turns |

The 93 unavailable grounding dimensions are not passes. An accurate partial
answer can be grounded while failing completeness. Controlled provider failures
and authored limitations remain in unconditional denominators. They are flagged,
not repaired by editing final oracles or silently accepting a different result.

Every one of the 185 incomplete or inaccurate final turns has an evidenced
primary cause and may have secondary causes:

| Primary cause | Final failing turns | Interpretation |
| --- | ---: | --- |
| Retrieval | 84 | Missing/wrong menu, source, intent or deterministic disposition |
| Model decision-making | 9 | Wrong, inappropriate or incomplete choice with available tools |
| Schema handling | 0 primary | One invalid emitted proposal is recorded separately; valid types do not guarantee correct values |
| Execution | 60 | Admission, rejected scope, unavailable fields, provider or source limitations |
| Response synthesis | 32 | Unsupported claims, wrong identity/date, omitted scope or incomplete answer |

The [final failure ledger](final-evidence/failures.json) gives case/turn,
family, difficulty, profile, linguistic tags, exact reason, primary/secondary
causes, actual inference counts and raw receipt SHA for every failing turn. The
[development ledger](development-evidence/failures.json) similarly preserves
all 205 initial failures. All 653 semantic reviews are complete; none substitute
diagnostic text for the controller's actual reply.

Controlled provider inconsistencies include mismatched outer/nested account
labels and generic records ignoring search, folder or date filters. Such
receipts cannot prove the requested provider/account state. A resource snapshot
cannot establish task smoothness or future resource adequacy. A metadata-only
file result cannot prove the file's content, and PID existence cannot supply
name, CPU or RAM. These recurring boundaries have explicit failure reasons.

The independent Verifier reproduced development faults before repair, validated
fresh unseen wording and original authority/handler controls, and reviewed all
24 repaired development replay replies. The replay has 20/22 eligible grounded
answers and 18/24 accurate complete responses. Its fixture version and selected
subset differ from the initial full run, so it is not a causal whole-corpus
before/after quality comparison. The final acceptance scores above remain the
single untouched result. See [INDEPENDENT_REVIEW.md](INDEPENDENT_REVIEW.md).

Acceptance targets are measured outcomes rather than promised results. Recall
and model selection fail their 95% targets. Observed typed arguments exceed 98%,
while annotated semantic argument correctness remains below 98%. Safety and
measured historical regression targets pass within their stated scope. Original
model-admission gaps and unavailable physical/provider integrations limit model
coverage; precise suppressed native failure causes remain unknown.

Further routing development should address missing capability/source retrieval,
request scope retained through fixed arguments, unsupported completion claims,
and explicit admission error reporting. Those are follow-up work; no production
tuning or final-case retry followed this holdout. A later evaluation requires
new independently sealed cases.

## Final stratified results

The complete [manager metrics](final-evidence/manager-metrics.json) retain every metric by task family, author-defined difficulty, execution profile and overlapping structural language tag. The [verifier metrics](final-evidence/metrics.json) include actual transport performance and full-response review for the same strata. Empty denominators are N/A, not passes. The following tables show required-group recall and actual response outcomes; conditional selection and argument details remain in the linked machine-readable report.

| Final task family | Owner turns | Recall@8 groups | Tool-turn menu sufficiency | Grounded eligible | Accurate complete |
| --- | ---: | ---: | ---: | ---: | ---: |
| archive git | 10 | 9/13 (69.2%) | 6/10 (60.0%) | 6/8 (75.0%) | 2/10 |
| calculation text | 12 | 9/12 (75.0%) | 8/11 (72.7%) | 9/9 (100.0%) | 7/12 |
| calendar | 12 | 7/12 (58.3%) | 7/12 (58.3%) | 1/1 (100.0%) | 0/12 |
| clock timezone | 10 | 4/11 (36.4%) | 3/10 (30.0%) | 3/5 (60.0%) | 3/10 |
| devices display | 10 | 9/11 (81.8%) | 7/9 (77.8%) | 8/9 (88.9%) | 6/10 |
| disk storage | 10 | 8/11 (72.7%) | 7/10 (70.0%) | 5/7 (71.4%) | 4/10 |
| drive documents | 12 | 6/12 (50.0%) | 6/12 (50.0%) | 2/6 (33.3%) | 0/12 |
| email | 12 | 9/12 (75.0%) | 9/12 (75.0%) | 2/8 (25.0%) | 0/12 |
| environment browser | 10 | 8/10 (80.0%) | 7/9 (77.8%) | 1/1 (100.0%) | 1/10 |
| file discovery | 12 | 10/13 (76.9%) | 9/12 (75.0%) | 10/11 (90.9%) | 3/12 |
| file inspection | 14 | 14/16 (87.5%) | 12/14 (85.7%) | 10/12 (83.3%) | 8/14 |
| google tasks accounts | 10 | 3/6 (50.0%) | 3/6 (50.0%) | 7/10 (70.0%) | 5/10 |
| gpu model | 12 | 12/13 (92.3%) | 10/11 (90.9%) | 5/7 (71.4%) | 5/12 |
| isolated file actions | 12 | 9/17 (52.9%) | 5/12 (41.7%) | 6/6 (100.0%) | 2/12 |
| local todos | 13 | 9/15 (60.0%) | 8/13 (61.5%) | 8/10 (80.0%) | 4/13 |
| network | 12 | 8/10 (80.0%) | 7/9 (77.8%) | 8/10 (80.0%) | 6/12 |
| no tool ambiguity | 12 | N/A | N/A | 3/6 (50.0%) | 0/12 |
| notes | 12 | 10/14 (71.4%) | 8/12 (66.7%) | 7/9 (77.8%) | 4/12 |
| permission adversarial | 10 | N/A | N/A | 10/10 (100.0%) | 10/10 |
| power battery | 10 | 7/11 (63.6%) | 5/9 (55.6%) | 6/8 (75.0%) | 4/10 |
| security status | 10 | 9/12 (75.0%) | 7/10 (70.0%) | 6/8 (75.0%) | 5/10 |
| spotify media | 12 | 13/17 (76.5%) | 8/12 (66.7%) | 0/1 (0.0%) | 0/12 |
| system process | 12 | 11/13 (84.6%) | 10/12 (83.3%) | 7/10 (70.0%) | 6/12 |
| windows apps | 12 | 10/12 (83.3%) | 9/11 (81.8%) | 5/8 (62.5%) | 3/12 |

| Final difficulty | Owner turns | Recall@8 groups | Native selection, sufficient menu | Grounded eligible | Accurate complete |
| --- | ---: | ---: | ---: | ---: | ---: |
| easy | 72 | 51/67 (76.1%) | 38/40 (95.0%) | 39/52 (75.0%) | 30/72 |
| medium | 96 | 67/94 (71.3%) | 42/45 (93.3%) | 50/68 (73.5%) | 30/96 |
| hard | 105 | 76/112 (67.9%) | 31/33 (93.9%) | 46/60 (76.7%) | 28/105 |

| Final execution profile | Owner turns | Grounded eligible | Accurate complete |
| --- | ---: | ---: | ---: |
| production config | 247 | 120/165 (72.7%) | 84/247 |
| owner reviewed isolated actions | 26 | 15/15 (100.0%) | 4/26 |

The reviewed isolated-action profile is additional disposable fixture authority; it does not modify the owner configuration. Its action acknowledgments are scored for actual evidence and scope, not treated as proof of physical GUI/provider effects.

| Overlapping final structural tag | Owner turns | Grounded eligible | Accurate complete |
| --- | ---: | ---: | ---: |
| multiple clause | 87 | 46/63 (73.0%) | 22/87 |
| question form | 57 | 21/35 (60.0%) | 17/57 |
| negative constraint | 73 | 40/48 (83.3%) | 28/73 |
| literal numeric or identifier | 99 | 57/74 (77.0%) | 34/99 |
| reasoning constraint or diagnosis | 4 | 3/3 (100.0%) | 3/4 |
| explicit local path | 54 | 37/44 (84.1%) | 20/54 |
| quoted content | 1 | 1/1 (100.0%) | 0/1 |
| sequential followup | 17 | 4/5 (80.0%) | 2/17 |

These final tags describe structural features, while the development linguistic audit explicitly covers the requested language forms. Neither table is a balanced sample of language or users. The 16 final actual conversations include 17 follow-up turns; seeded-history probes are separate.

## Capability and evidence coverage

The [joined capability matrix](CAPABILITY_COVERAGE.json) records intended annotations, offers, raw native proposals, post-gate entries, original/controlled evidence and response outcomes for every one of the 172 base definitions. The final covers 129 intended IDs, including eight blocked-intended IDs. An intended alternative is not a demand to execute all equivalent handlers. Inventoried-only and ineligible tools remain explicit; the matrix does not certify every handler or physical integration.

The frozen report helper reads development case-level `targeted_tools`, whereas final intent is per-turn `intended_tools`. Its original matrices are preserved. The [coverage supplement](final-evidence/capability-coverage-supplement.json) adds final intended/blocked annotations from the unchanged seal, with provenance; it changes no oracle, controller result or acceptance grade.

All detailed raw replies, original menus, proposals, effective arguments, source receipts, private state and cleanup records remain under `data/campaign1-verifier/live-development-01` and `live-final-01`. The public ledgers identify the raw SHA for each turn. [REPRODUCTION.md](REPRODUCTION.md) explains the frozen byte archive, safe aggregate replay and once-only final restriction.

Checkpoints and intermediate failures are retained in
[CHECKPOINTS.md](CHECKPOINTS.md). Raw prompts, replies, tool receipts and detailed
private evidence live under ignored `data/campaign1-*` directories. The supplied
request referred to common instructions, but no separate common-instructions
document was found; the recorded protocol uses the explicit campaign request.
