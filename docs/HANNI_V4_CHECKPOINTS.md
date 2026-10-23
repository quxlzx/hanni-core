# HANNI V4.0 implementation checkpoints

The V4.0 request is the implementation contract. The source baseline is
`32965a1` on the current working branch. Pending, authorized changes include
the local Geist Sans typography update and the October 9 reasoning-comparison
report/script; unrelated user files remain untouched. No repository push or
model download is authorized by this phase.

The team consists of the main manager/integrator, actual subagent
`v40_routing_engineer`, and actual subagent `v40_independent_verifier`.
The verifier owns independent test code and real benchmark sessions and does
not implement production code.

## M0: architecture audit

Completed architecture audit; independent baseline regression exited successfully
with two skips. The baseline output did not retain a reliable pass count; its concurrent-source
caveat is recorded in the independent review. The final frozen-source count
is recorded separately.
The original `hanni.models.registry.create_client` constructs the
configured loopback llama.cpp client. The controller's text/tool sessions and
workflow planner use that client; capability selection and tool permissions
remain separate from inference placement. `ComputeRegistry` holds protected
worker definitions and identity-bound measured context receipts.
`ComputeScheduler` owns bounded inference transport, reservations, and worker
health. The original `WorkflowService` remains the execution authority and
currently distributes only supported pure evidence analysis.

`DashboardServer` provides the existing Host/Origin/token gates and shares the
workflow and compute services. Its React interface has a Mission navigation
group and local packaged assets. The new routing view will use those existing
gates and the same capability registry for policy changes.

Existing V3.7 reports identify material limits: the requested remote IQ3_S 27B
weights are unavailable, the installed GPU model is a different quantization,
the verified GPU contexts are 32K, Strata's verified context is 8K, and complex
autonomous planning has not been established. The separate sealed reasoning
packet scored 2/6 on each GPU worker and 0/6 on Strata. These are prior evidence,
not the V4.0 unseen holdout.

The actual configured resident model is Qwen3.5 4B; the owner's existing custom
HANNI 4B file is a separate unconfigured candidate. No model was substituted.

## M1: discovery and real measurements

The independent verifier sealed a fresh holdout before inference.
The first fixed-model cohort made 32 real calls: eight tasks on each of four
configured endpoints, including six held-out tasks per endpoint. Holdout scores
were 2/6 for the resident 4B, 3/6 for each GPU worker, and 2/6 for Strata. These
small samples are not a general model ranking. JSON-object and native function-call format probes passed on all four endpoints;
unmeasured capabilities remain unknown. Near-limit counted retrieval passed at
16K locally, 32K on each GPU and 8K on Strata. The first GPU context cycle retrieved
the right values but failed its strict JSON format; a separately sealed JSON-object
profile passed. The failed cycle is preserved rather than regraded.

Holdout outcomes are excluded from the selector's profiles before its prospective
adaptive cohort. Only designated calibration or explicitly prior evidence may
inform that choice. The verifier owns all temporary serving sessions and cleanup.

The first prospective adaptive cohort passed 3/6 checks versus 2/6 for the fixed
resident model, using only two designated development tasks for routing input.
Three failed cases exhausted bounded verified inference attempts and took longer;
this does not establish a general quality or simple-task latency improvement.
The existing custom HANNI 4B candidate failed to load because a required tensor
was missing. It remains unconfigured and has not replaced the resident model.

## M2: capability and performance registry

Complete. `hanni.models.adaptive` persists identity-bound capability receipts,
category measurements and settings. Four real endpoint receipts and 32 measured
samples were imported into production only after prospective choices were sealed.
Tested contexts are 16K/32K/32K/8K. Graded accuracy remains distinct from ungraded
latency. Unknown and insufficient measurements stay explicit.

The verifier identified weak same-path weight binding. Complete file fingerprints
and runtime/context binding now invalidate evidence after ordinary file/runtime
changes. A protected configuration addition permits read-only fingerprinting in
Strata's exact existing model directory. A private pre-change backup and preserved
ACLs accompany that change. Serving targets and sharing categories were preserved.
Resume using identity-bound engineering APIs, never the desktop policy endpoint.

## M3: deterministic selection

Complete. Eligibility checks precede
Balanced/Fast/Quality/manual ranking and require exact configured identity,
authorized context categories, supported operation/format, tested context, fresh
health and bounded load. Message, schema and output budgets are accounted for.
Actual multimodal input is rejected by the current text adapter. Remote analysis
permissions never become tool-generation authority. Conservative defaults remain
when category evidence does not meet the sample/confidence threshold.
Resume by extending the existing engine and independent eligibility matrix.

## M4: measurable fallback

Complete. Pure inference retries are
bounded and recheck admission, privacy and identity. Invalid output and externally
rejected answers trigger retries; confidence claims do not. Native/local callbacks
inherit their admitted output limit. No inference replay occurs after a visible
streaming chunk, and no side-effecting tool operation is repeated. Independent
controlled budget, uncertain-write and privacy tests pass.
Resume through original compute queue and controller admission callbacks.

## M5: original controller and workflows

Complete. The original model client,
TextSession/McpToolSession, WorkflowPlanner and verified analysis paths share
adaptive placement without replacing capability selection or execution authority.
Cold local startup does not wait for full remote model fingerprints. Live original
controller CPU/RAM and synthetic-file tasks passed in both fixed/adaptive arms:
4/4 correct tool selections and verified receipts. Legacy CLI streaming and
comparison-profile compatibility checks passed after realistic discovery fixtures
and equivalent policy defaults were updated. Conservative byte admission can
still reject some token-compatible small-context inputs; no approximate token
proof was substituted. Resume with the existing model/controller ownership rules.

## M6: interface checkpoint

The Mission navigation now includes Model Routing, with endpoints, tested contexts,
capabilities, measured category profiles, policy/manual preference controls, decision
reasons and fallback history. Correctness uses graded-sample counts, independently
of total latency measurements. Unknown limits and measurements remain explicit.
Geist Sans and offline font packaging are preserved.

The new API uses the original token/Host/Origin gates and capability registry.
Ten focused HTTP/control tests pass, including missing/wrong tokens, cross-origin
requests, UUID dedupe/collision, forbidden capability/privacy fields, Safe Mode,
and shared-engine ownership. The existing 30 dashboard/gateway checks also passed.
Explicit refresh requests wake bounded background probes and return immediately.
Independent headless Edge screenshot review passed at 1440x900, 900x650 and
640x700, scored 8.8/10, and found no horizontal overflow or JavaScript errors.
The rich screenshot telemetry was an explicitly synthetic fixture; policy POSTs
used the actual isolated API. An error-recovery issue was fixed and the final
nine browser interaction checks pass. These are headless checks, not native GUI
claims. The bundled Geist font loaded successfully.

## M7: final independent verification

The independent verifier reports 73/73 controlled tests and 9/9 browser checks
passing. A fresh strong-identity regression recheck of the same sealed holdout
retains 3/6 adaptive versus 2/6 fixed; it is explicitly a repeat, not newly unseen.
All temporary model sessions were closed. Original Strata PID/port and three
original file hashes were verified intact. The final frozen-production-source
regression passed 1,840 tests, with two skips and 25 passing subtests in 280.88
seconds. Three independent supplemental tests were added after full-suite
collection and passed in the separate 73/73 run; these counts are not summed.
The resource-history audit persists known admission headroom/load observations,
keeps unknown values null and preserves all 32 production benchmark rows.
Completed/partial streaming is ungraded telemetry, and cancellation never replays.
TypeScript/assets build and wheel/archive import checks pass, including the compute
module, routing assets and offline font/license. Packaged sources match the tree.

The final receipts are `data/v40-manager/final-regression.xml`,
`data/v40-manager/final-verification.json`, the independent controlled-cycle10
receipt, and browser-cycle7. See [independent review](v40-reviews/INDEPENDENT_REVIEW.md)
and [security/regression gate](HANNI_V4_SECURITY_REGRESSION.md). No automatic commit
or push was performed. Deployment limitations remain explicit in the benchmark
report; they are not missing implementation work.

## Milestone state

| Milestone | State | Resume point |
| --- | --- | --- |
| M0 audit and baseline | Complete | Baseline passed with disclosed concurrent-source/count limits |
| M1 discovery and benchmarks | Complete with disclosed deployment limits | 4B/GPUs/Strata measured; requested custom file cannot load, GPU IQ3_S absent |
| M2 capability/performance registry | Complete | 4 current receipts and 32 measured samples published after sealing |
| M3 deterministic adaptive selection | Complete | Independent eligibility suite passes; preserve conservative ranking |
| M4 measurable fallback | Complete | Independent retry, privacy, streaming and callback budget checks pass |
| M5 original controller/workflows | Complete | Original live controller tasks and CLI compatibility passed |
| M6 routing visibility | Complete | Private API and independent 9/9 browser checks pass; screenshots exceed 8.5/10 |
| M7 independent verification | Complete with reported operating limits | Frozen-source suite, independent checks, package and cleanup gates passed |

## Continuation rules

Inspect this checkpoint and current diffs before resuming. Keep private endpoint
definitions, credentials, user context, and raw benchmark evidence under ignored
protected data storage. Do not reuse the previous packet as an unseen holdout.
Unknown tool, vision, context, memory, queue or quality measurements must remain
unknown. Policy and manual override never grant data-sharing or tool authority.
Only the verifier starts/stops real benchmark model sessions, with owned-process
receipts and bounded cleanup. Never stop an unrelated existing process.
