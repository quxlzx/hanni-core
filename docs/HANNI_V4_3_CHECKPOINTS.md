# HANNI V4.3 implementation checkpoints

Source baseline: `a62d0c3` (`codex/hanni-v3.7-distributed`). Package target:
`0.13.0`. Exactly three actual agents participate: the manager, implementation
engineer and independent verifier. The verifier does not edit production code.
Private run and verification artifacts stay under ignored `data/` paths.

## M0: repository and benchmark audit

The tracked tree was clean at the start. The existing V4.2 committed checkpoint
records 1,963 passing tests, two documented skips and 25 passing subtests. That
is prior regression evidence, not a new V4.3 test run. The five unrelated root
patch/benchmark files remain untouched.

Existing components identified:

- `hanni.evals.llm_tools`: real model inference with exclusively synthetic MCP
  results, per-case evidence, scoring, checkpoint reports and resume checks.
- `hanni.evals.routing`: deterministic capability retrieval/scoring without
  model inference or tool execution.
- `hanni.evals.comparison`: comparison requires compatible corpus, routed menus,
  prompts, evaluator, time zone, ordered cases and inference settings.
- `AdaptiveModelEngine`: registered endpoint identities, current eligibility,
  privacy/resource admission, measured quality profiles, bounded placement and
  original client/compute dispatch.
- V4.1 collaboration: original bounded specialist/review execution and outcome
  receipts; V4.2 adds bounded numeric timing/resource observations.
- `DashboardServer`, private token-gated APIs, audited desktop controls and the
  existing Models/Model routing screens with local Geist typography.
- `ModelManager`: original serving configuration, leases, local ownership,
  resource sampling and external-process boundaries.

The lab will adapt implemented existing evaluation functions, not invoke shell
commands from the UI. Model selection is pinned for each benchmark without
changing the global routing policy or silently substituting a different model.
Run manifests bind dataset, scorer, model identity, configuration, settings and
ordered cases. Per-case checkpoints support honest boundary pause/cancel and
validated resume. The original execution/authorization path remains decisive.

Only implemented development suites will be exposed. Synthetic tool results,
model-only checks, real verified tools and workflow completion must retain
distinct meanings. Exposed development cases are not untouched holdouts; final
holdout contents will not be opened or tuned against. Runs do not automatically
grant adaptive quality or capability proofs.

The previously verified primary is Qwen3.5-4B-Q4_K_M, Vulkan1, one slot, 16K,
q8_0 KV. Existing weights will be reused without downloads. Current remote
serving/resource access must be rechecked before any new claim. Historical
Athena helper cleanup is unknown; external Strata ownership remains intact.

## Milestone state

| Milestone | State |
| --- | --- |
| M0 repository and benchmark audit | Complete; integrated architecture agreed |
| M1 model inventory and metadata | Complete; fresh primary identity verified and remote unknowns retained |
| M2 benchmark execution integration | Complete; four adapters independently executed with genuine case-boundary controls |
| M3 results storage and inspection | Complete; real persistence, resume, export and evidence hashes verified |
| M4 model comparison | Complete; matching and differing actual workloads checked; remote model bakeoff unavailable |
| M5 adaptive routing insights | Complete; original selector integrated without development proof upgrades |
| M6 visual refinement | Complete; genuine native screenshots scored 9.0/10, AI-template appearance 1.3/10 |
| M7 functional and independent verification | Complete; 2,035 tests and 25 subtests passed, two documented skips; package and exact owned-helper cleanup verified |

The manager owns integration, milestone evidence, final regression and package
checks. The engineer owns backend/frontend implementation and focused tests.
The verifier owns independent tests, actual model/API runs, screenshots and
`docs/v43-reviews/INDEPENDENT_REVIEW.md`. Checkpoints will record measured results
and actual blockers. No automatic commit or GitHub publication is part of this
implementation.

## M1–M5: first implementation and verification cycle

The integrated implementation uses the original endpoint registry and shared
model admission, fixed audited dashboard controls, durable SQLite case
checkpoints and the existing evaluation functions. Four offered development
suites distinguish deterministic retrieval, real model JSON output, real model
inference with synthetic MCP results, and actual scoped read-only file execution.
The desktop now has inventory/detail, runner, result evidence, comparison,
history and original routing insights surfaces. TypeScript checking passed.

Independent fixture checks initially found an evidence-digest mismatch after
redaction. The engineer corrected storage and public export hashing; the
independent fixture cycle then passed all 36 initial checks. An expanded audit
subsequently passed 59 of 60 checks, with the remaining missing-corpus admission
error under correction. These are controlled fixture observations, not model
quality or live performance scores.

Manager review required process-level storage ownership, immutable case and
behavior fingerprints, unknown residency for failed remote observations,
optional-storage failure isolation, explicit percentile/sample metadata and
original context preflight. The unchanged 400-line development prompt exceeds
the primary endpoint's original conservative 16K admission bound; the short
case remains valid. Server-side history navigation and truthful bounded exports
are being refined before final acceptance. The independent real model and
native desktop campaigns have not yet run at this checkpoint.

## M1–M5: source freeze checkpoint

The engineer completed the reviewed backend and desktop changes, preserving the
original model/router/controller. The focused regression passed **63 tests in
27.56 seconds**: eight dedicated lab tests, 45 independent backend cases and ten
existing routing/dashboard cases. The frontend's **37 tests passed**, and the
final TypeScript/Vite build produced the served desktop assets. Evidence is
under ignored `data/v43-engineering/focused-tests.txt`.

History now searches and paginates stored runs beyond the latest 100. Large
exports preserve the initially captured committed prefix, validate successive
page identities/ordinals and refuse incomplete downloads. Model labels separate
weight filenames from API aliases. Model detail links recent saved evidence.
An independent browser fixture review passed **six checks**, including oldest
history access among 122 disclosed fixture runs and responsive layouts at
1440, 900 and 640 pixels. These are browser/display fixtures, not the required
native screenshots or live model evidence.

At this checkpoint production source is frozen for the independent real model
and native Windows campaigns. The manager defers the full repository regression
until that campaign's quiet measurement interval ends. M6/M7 acceptance remains
pending; the implementation checkpoint alone does not claim final completion.

A final targeted correction made history search include the displayed weight
filename as well as the API alias; its extended existing test passed. The
verifier was notified of the source/scorer fingerprint change before live
execution. A separately running original HANNI desktop subsequently occupied
the primary model port. Its model process is external to this campaign and
must remain running. Verification may reuse it through the original manager
only after fresh identity/configuration checks, with shared-server timing
limitations disclosed and a private current-source test dashboard.

## M1–M5: independent live API checkpoint

The original transport and manager verified the existing primary's full cached
weight SHA256 and Vulkan1/16K/q8_0/one-slot settings. The manager recognized it
as external (`entry.process is None`): no model process was adopted or launched.
The verifier opened a separate private current-source dashboard/controller and
ran **18 independent API checks**, all passing. Its five persisted runs contain
**27 cases and 28 actual model turns**:

- Two identical short structured workloads: five repetitions each, 10/10 exact
  JSON results. They exercise genuine pause/resume and cancel/resume boundaries.
- Five actual original scoped `file.read` cases: 5/5 `VERIFIED` receipts and
  correct final tokens.
- Two real-model/synthetic-MCP tool cases: 2/2 strict passes, mean original
  heuristic score 97.5/100. These are not actual tool-completion claims.
- Ten deterministic retrieval cases: 10/10 passes with no model inference.

The verifier recomputed exported evidence hashes and scores, checked persisted
ordinal coverage/progress, accepted matching completed conditions and rejected
mixed-suite comparability. It verified the original long-context refusal before
dispatch or scoring. No development quality/capability proofs were published.
Remote model access remains unavailable; actual cross-model superiority and
competitive speed claims are not established by repeated primary runs. Native
desktop interaction/review and the full regression remain pending at this
checkpoint.

## M1: accepted inventory checkpoint

Original registry and health observations distinguish configured, installed,
loaded and currently available endpoints. Full primary weight identity and
critical original serving settings were freshly verified. The isolated native
review shows its configured primary; a separate protected deployment check
found all three configured Athena/Strata workers unavailable. Unknown metadata
remains unknown. No unavailable worker received an invented score.

## M2: accepted execution checkpoint

Seven genuinely completed runs contain 33 durable cases and 34 original model
turns. Five starts used the integrated API and two used the native Start button.
The four offered suites executed within their stated scopes. Pause/cancel stop
at an actual committed case boundary; compatible resume retained unique
ordinals. Original privacy, resource and context admission remained decisive.

## M3: accepted storage and export checkpoint

A distinct original HTTP server reopened all seven runs and 33 cases with zero
new inference. Public case hashes, configuration hashes and protocol hashes
were independently checked. Final native disk auditing exposed a real export
defect: JavaScript parse/stringify changed integer-valued Python floats while
retaining their evidence hashes. Acceptance was held for a correction.

The correction transports already-redacted server-serialized manifests and
case JSON as bounded pages. The frontend validates protocol and ordinal order
but appends those original strings to the download. It preserves float types,
escaped content and complete nested objects without changing saved evidence or
scores. A new current-source server reopened the same records; every hash in
all seven API exports passed. Actual native cycle 11 downloaded five saved
cases and independently passed every case/configuration/protocol hash check,
with no new model dispatch.

## M4: accepted comparison checkpoint

Matching completed structured workloads compared with explicit equal dataset,
selection, scorer, settings and protocol conditions. Different suites were
marked noncomparable. Original P50/P95 conventions, sample denominators and
absolute units remain visible. Shared primary timings cannot establish a
competitive model winner; unavailable remote workers remain a real limitation.

## M5: accepted routing checkpoint

The lab reuses the original adaptive routing screen, eligibility reasons and
V4.2 performance observations. Development results did not publish model
quality, capability or context proofs, change the primary model or alter global
routing configuration. Original V4.1 collaboration stays in its existing
workflow and outcome receipt system.

## M6: accepted native visual checkpoint

The independent verifier inspected genuine Windows Forms/WebView2 screenshots
at outer window sizes 1440x900, 1366x768 and 900x650 (125% DPI). Exact foreground
client-surface captures exclude unrelated desktop pixels. Native cycle 11
passed all 14 interaction checks, including the corrected actual disk export.
The rubric scored typography 1.9, hierarchy 1.8, density 1.7, professional design
1.8 and interactions 1.8: **9.0/10**, above 8.5. AI-template appearance was
**1.3/10**. Concrete evidence and deductions are in
`docs/v43-reviews/INDEPENDENT_REVIEW.md`.

## M7: correction and final source-freeze checkpoint

Before the native export defect was found, the initial full regression passed
2,033 tests and 25 subtests with two documented skips in 402.88 seconds. Its
XML evidence is retained separately; it does not certify the later correction.

After the correction, 71 focused backend checks, all 41 frontend tests and the
production build passed. The verifier independently passed 63 service/HTTP
checks, including float-preserving transport and late-secret policy coverage.
The final current-source full regression passed **2,035 tests and 25 subtests**
with **two documented skips** in **397.05 seconds**. Its distinct cycle-2 XML
report is `data/v43-manager/final-regression-cycle2.xml`. The skips are an
absent historical private inference report and the `hanni` console script not
being on PATH in this environment. No failures or errors were reported.
The rebuilt 0.13.0 wheel passes byte comparison for all 196 packaged source and
static files and 12 direct archive imports. Its SHA256 is
`f1e6791e465c976bf0c84bd5c36d374d2d53634194e7c00867ab2f77d2c4e0bb`;
the private package check is `data/v43-manager/release-cycle2/package-check.json`.

The verifier closed both owned bounded helpers, all native review clients and
the distinct persistence server. The manager independently reconciled final
helper PID/create-time absence, empty temporary dashboard listeners and the
unchanged original HANNI launcher/model identities. The manager also recomputed
all case/configuration/protocol hashes directly from the genuine five-case
native disk download. Closure and export receipts are retained privately under
`data/v43-manager`. Final review source hashes and all eight local screenshot
hashes match the independent evidence summary.

M0 through M7 are complete for the implemented scopes. A normal HANNI restart
is needed for an already running old backend to load these changes. The
pre-existing application was preserved. Remote comparisons remain unavailable;
no winner, broad quality claim or context proof is inferred from these limited
shared-runtime development runs. No commit, push or GitHub publication was
performed.
