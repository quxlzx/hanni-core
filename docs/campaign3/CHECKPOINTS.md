# Campaign 3 checkpoints

## Baseline inspection and original regression checks

- Starting revision: `b1ec1bb2a11d539adc97d0a3f740637da9f94df5`.
- Actual engineering workers: `/root/v36_engineer`, `/root/v44_engineer`.
  Independent verifier: `/root/v44_verifier`.
- The original 14 memory/LAYA/project test files passed: **156 tests**, zero
  failures or skips, 24.831 seconds. Evidence:
  `data/campaign3-manager/baseline-regressions.xml`.
- Original guarded model diagnostics attempted one synthetic request through
  each of A (legacy) and D (optional deterministic context): two blocked
  attempts, **zero actual inference HTTP requests**. The original selector's
  separate post-refusal inspection reported `insufficient_ram_reserve`.
  Evidence: `data/campaign3-manager/baseline-model/`.
- Read-only runtime identity: healthy existing model listener PID 38832,
  launcher PID 46084; no configured LAYA-port listener. The launcher's three
  whitelisted LAYA environment flags were absent. Configured LAYA advisory,
  retrieval and stored-memory permission were false; deterministic project
  context was false. No owner memory database was opened by these probes.
- The model file SHA-256 remained
  `25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c`.
- No production source repair occurred in this baseline cycle. Synthetic
  development and private independent holdout authoring are in progress.

## Independent holdout seal

The verifier sealed **120 independently authored scenarios**, exactly six in
each of the 20 requested categories, before any production tuning. There are
120 final queries, 12 explicit warm retrievals and 36 scenarios with lifecycle
operations. Inputs and answer oracles remain private to the verifier; only the
seal receipt is available to engineers and manager.

- Inputs SHA-256:
  `5464dd334fac7b8d8811fbf02c5ba25384c7ca794b075b91341314f956814d53`.
- Oracles SHA-256:
  `9e69a5098a583c5da6ea501a8f6deb0e1ac3b815ee5cefd916b266f356a2d8f6`.
- Protocol SHA-256:
  `225638d97d1a0b1c74139c87f16320bc9a2a26eb55caa897381b0376f6d2d7d2`.
- Authorship SHA-256:
  `d4fe290f244ba9c9995ecabe96d06179a48e8d758f707deaba7e4905a78f875c`.

Before this seal, the original boundary suite recorded 107 tests: 94 passed
and 13 failed, with all ten owned production source hashes unchanged.
Evidence: `data/campaign3-boundaries/baseline-02/`. The earlier 58-test run is
retained separately, including one corrected tuple/list harness assumption;
that assumption is not counted as a production defect. Production repairs
were authorized only after the seal and baseline checks completed.

## Development repair cycles

The frozen public development corpus contains **320 scenarios**, sixteen per
category, with 193 positive queries, 202 relevant IDs and 127 negative queries.
Its byte digest is
`4d0b33856ea6f406b673458c9c72b1185cd4a1794d391abddfb00e77746fcece`.
The complete original source archive produced 187/320 passing legacy scenarios
and 223/320 passing optional context scenarios. Cycle 1 produced 228/320 and
245/320 respectively, with no previously passing scenario regression. These
counts require every scenario assertion; they are not model-answer scores.
Recall remained below target, as recorded in `DEVELOPMENT_REVIEW.md` and
`evals/memory/campaign3_development_results_cycle1.json`.

The expanded original boundary run, `data/campaign3-boundaries/baseline-03`,
recorded **120 tests: 100 passed and 20 failed**, with unchanged source hashes.
Independent exposed-development reproductions validated the first repairs:
32/32 session/transport controls, 25/25 retrieval controls and 7/7 project
identity controls. Twelve prohibited synthetic mutations before repair were
denied afterward. Later fresh automatic-capture probes found two additional
low-tier unauthorized writes; all nine tier controls passed after repair.
Suites overlap and these counts must not be summed as distinct test coverage.

The initial malformed-row fixture hit SQLite's CHECK constraint in seven cases.
Those were harness failures, not product failures. The corrected isolated import
fixture retained 37 cases: five passed and 32 product checks failed (21 invalid
row reads, nine budget checks and two low-tier automatic captures). The repaired
37-case suite passed. The verifier separately reproduced and validated eighteen
malformed-row/factory/outage/Safe Mode controls. Original model exceptions remain
outside the new memory-read guard.

Native tokenizer evidence measured all **708 archived baseline contexts**,
including explicit warm queries: 354 per arm, with no unavailable measurements.
This is tokenizer evidence rather than model generation or server token usage.
Two additional guarded model diagnostics were also blocked without generation
HTTP calls. Raw receipts are under `data/campaign3-manager/baseline-tokens` and
`data/campaign3-manager/tokenizer-diagnostic`. No final holdout was consulted
during any repair cycle.

## Final integrated development verification

The manager's combined memory, LAYA, project, new campaign, controller and
permission regressions passed **463 tests**, with zero failures, errors or skips
in 48.979 seconds. Evidence:
`data/campaign3-manager/final-regressions-02.xml`. The first invocation used an
incorrect new test filename and collected no tests; its harness error is retained
in `data/campaign3-manager/final-regressions-collection-error.json`.

The boundary worker's final full suite passed 330 checks in 26.826 seconds,
with unchanged owned and dependency hashes. The verifier independently passed
19 integration tests and the nested original boundary groups, including finite
confidence validation, project metadata quarantine and late project-record
changes. These suites overlap the manager's regression run. Public Python
source was checked for canonical LF endings before the final source archive.

## Source freeze and final holdout authorization

After all exposed-development repairs and the final source-uniform 640-arm
development receipts, the manager used the verifier's exact `freeze()` adapter
to archive **223 source/config/harness files**. Proof:
`data/campaign3-manager/final-freeze/proof.json`; archive SHA-256:
`6d6f5e6861852222e831a936824355ed1bd301e0ca2127a169972fa90f44def9`.
Both engineering agents and the verifier held source/scripts/tests unchanged.
The manager then explicitly authorized the once-only sealed 120-case final
evaluation. Report and summary publication may proceed; source tuning may not
use this holdout's results.

## Once-only independent final results

The verifier completed all **240 arm executions** for 120 sealed scenarios,
with zero fixture-level execution errors and unchanged source hashes. Legacy
Recall@5 was 42/94 (44.68%); optional deterministic context Recall@5 was 57/94
(60.64%). The original project resolver diagnostic scored 12/18 (66.67%) in
both arms. Relevant-memory and project-identification targets were not met.
Supported deterministic checks passed in 58/120 and 71/120 cases respectively,
with actual response/action dimensions still unmeasured. No source tuning or
holdout retries followed these results. Evidence remains under
`data/campaign3-verifier/final-01`; the public independent report provides
aggregate grades without exposing private oracles.

## Final native model and tokenizer evidence

The manager selected twenty public development diagnostics across seven
categories before inference, then attempted A and D using the original local
session and resource admission. All **40 final attempts were blocked**, with
zero generation HTTP calls and unchanged synthetic stores. The original
selector's separate post-refusal inspection reported insufficient RAM reserve
in all forty cases. Model, launcher and file identity matched the baseline;
source hashes stayed unchanged. Original two diagnostic pairs plus this cohort
total 44 blocked attempts, not 44 model responses. B remains disabled and no
actual LAYA model call was made.

Final native tokenizer measurement covered all 708 development contexts:
354 per arm, zero unavailable. Mean actual retrieval-context tokens were
143.19 for legacy and 127.39 for optional context. The native formatter also
measured actual injected memory in model attempts; no generation usage is
invented. `MANAGER_EVIDENCE.json` retains source, XML, model and tokenizer
receipt references and hashes. The final report records unmet and blocked
targets. The running owner application was not restarted. At validation
closeout, the changes had not yet been committed.

The independent final integrity audit matched all 240 receipt commitments,
all 223 archived/current source files and all four sealed artifacts. Actual
native tokenizer measurement of 264 retained private holdout contexts succeeded
without retrieval re-execution or model generation. Per-arm means were
145.86/146.64 tokens, maxima 590/506, with 76/60 empty contexts.
`FINAL_HOLDOUT.json` and `VERIFICATION.json` retain the public aggregate and
private-evidence digests. One original oracle contradicts its own exclusion and
required-returned-status annotations; its literal failure is retained without
regrading and does not alter recall/project metrics. The holdout's explicit
cache-authority comparison and two final advisory fault paths are unexercised;
the final report does not claim coverage for them.
The final documentation audit additionally identifies three empty-context
whole-record checks per arm as unexercised for populated serialization. Their
literal outcomes remain recorded; no regrading or source changes followed.
