# Campaign 4: autonomous workflow reliability report

The controlled safety checks and real test-runner recovery challenge passed.
The final unchanged development corpus scored **103/120**, and the untouched
independent holdout scored **32/40**. Both retain their original expectations
and failures. The existing regression suite passed **346/346**; the new suite
passed **104/104 checks**, including two verifier subtests.

Observed controlled runs produced **zero unauthorized sensitive operations and
zero duplicate consequential writes**. This establishes the exercised
implementation behavior. Actual model goal understanding and planning quality
remain unmeasured because native admission refused inference below its RAM
reserve. Several planning and lifecycle limitations remain documented below.

Baseline: `0aede831853b6876bc8904838a41f7b2ce8f3967`.
Machine-readable evidence: [MANAGER_EVIDENCE.json](MANAGER_EVIDENCE.json),
[FINAL_HOLDOUT.json](FINAL_HOLDOUT.json),
[VERIFICATION.json](VERIFICATION.json), and the
[independent review](INDEPENDENT_REVIEW.md).

## Implementation and verification scope

The current V3 engine still uses its original `WorkflowPlanner`,
`WorkflowService`, `WorkflowStore`, capability registry, MCP host, permission
gates, compute transport and result verifiers. The planner produces a bounded
outline followed by bindings selected from routed capability menus. Trusted
code validates dependencies, arguments, typed references, policy and capability
fingerprints. A model proposal supplies no execution authority.

SQLite persists approvals, steps, invocation identities and checkpoints. A
lease and fencing generation prevent stale runners from committing results.
Only eligible safe reads can retry or execute in parallel. Writes retain exact
reviewed authority; unknown write outcomes require reconciliation. Already
admitted synchronous handlers stay visible until they return. Pause and cancel
withdraw admission for subsequent work.

Two actual engineering agents implemented the controlled scenarios and native
boundary tests. A separate actual verifier reproduced the exposed defects,
reran the public suite and owned the private holdout. The manager reviewed the
integration, pinned source provenance and ran the broad regressions.

| Evaluation | Final result | Execution scope |
| --- | --- | --- |
| Original development corpus | 103/120; zero harness errors | 102 native workflows, 18 direct store scenarios; six per requested category |
| Eligible retry/recovery/parallel supplement | 5/5 | Original safe `file.stat` retries and actual overlapping file reads |
| Explicit multi-source goal supplement | 12/12 | Separate exposed development cases; original graphs and expectations retained |
| Reference/schema controls | 10/10 | Original reference resolution and generation-schema contracts |
| Stale transition commit probes | 65/65 | Every dynamically declared store edge; stale CAS refusal and valid readback |
| Checkpoint transaction fault probes | 65/65 | Failure after projection UPDATE and before checkpoint commit; rollback and reopen |
| Independent local-analysis rerun | 10/10 | Original analysis, citations, safe file effects, timeout and controls |
| Independent untouched holdout | 32/40; zero fixture errors | Input-only independent execution and separately sealed scoring |
| Existing workflow regressions | 346/346 | 29 original test files; 61.261 seconds; zero errors/skips |
| New frozen test checks | 104/104 | Integration, contract and independent verifier checks; 40.006 seconds |

The engineering public cohort contains 119 native workflows after adding the
two separately scored supplements, plus 18 direct store scenarios. Supplement
cases do not replace original denominators. The explicit-goal supplement
reuses twelve development graphs with properly stated source objectives; it is
not an untouched evaluation. The independent forty contains two privately
authored cases per requested category, with forty distinct goal hashes and no
collision with the original development goals.

Controlled planner and analysis replies exercise protocol and execution.
They do not contribute to a semantic model score. Safe filesystem operations
execute their actual registered implementations against disposable fixtures.
No external account success is claimed.

## Requested category outcomes

| Category | Original development | Final development | Independent holdout |
| --- | ---: | ---: | ---: |
| Ambiguous prior write outcomes | 6/6 | 6/6 | 2/2 |
| Approval rejection | 6/6 | 6/6 | 2/2 |
| Backend interruption | 6/6 | 6/6 | 1/2 |
| Bounded retries | 4/6 | 4/6 | 0/2 |
| Capability availability | 6/6 | 6/6 | 1/2 |
| Checkpoint persistence | 6/6 | 6/6 | 2/2 |
| Dependency ordering | 6/6 | 5/6 | 1/2 |
| Goal understanding | 5/6 | 6/6 | 2/2 |
| Multi-step tool usage | 6/6 | 6/6 | 1/2 |
| Partial completion | 6/6 | 4/6 | 2/2 |
| Pause and resume | 6/6 | 6/6 | 2/2 |
| Permission requests | 6/6 | 6/6 | 2/2 |
| Plan generation | 6/6 | 6/6 | 2/2 |
| Recovery after restart | 4/6 | 4/6 | 1/2 |
| Safe parallel execution | 6/6 | 0/6 | 2/2 |
| Sequential execution | 6/6 | 4/6 | 2/2 |
| Step verification | 6/6 | 6/6 | 2/2 |
| Task cancellation | 6/6 | 6/6 | 2/2 |
| Worker disconnection | 5/6 | 5/6 | 1/2 |
| Workflow completion reporting | 6/6 | 5/6 | 2/2 |

Goal understanding and plan generation above are controlled protocol categories.
They establish no actual model semantic accuracy. Multi-source authoring
conflicts affect the original safe-parallel category; the separate explicit
source supplement and actual read-overlap controls verify supported execution.

## Reproduced defects and repairs

| Cause | Reproduced behavior | Repair and independent evidence |
| --- | --- | --- |
| Execution/control settlement | A guard correctly refused a handler after pause/cancel, but exception handling replaced the requested state with BLOCKED | `service.py` retains the invocation outcome and settles the existing owner control. Native checks improved 20/22 to 22/22; unchanged independent controls improved 1/3 to 3/3. |
| Uncertain outcome handling | A still-valid scope allowed resume or a safe retry past another uncertain write, admitting a separate managed write | Continuation now requires no dispatched or uncertain invocation, in both API mutation and displayed controls. Independent resume/retry reproductions now reject continuation with zero subsequent writes; native service checks pass 27/27. |
| Planning/objective consistency | A generated outline or binding substituted another local source and completed after review | `planner.py` checks prepared literal local read sources against explicit normalized owner paths. Independent controls improve 1/3 to 3/3: exact source succeeds, both substitutions stop before dispatch. |
| Schema/reference handling | Eager finite-number checks converted a large valid integer to float even for another requested type, raising OverflowError | `references.py` checks only the requested kind. Exact integers remain intact; unsupported number conversion receives the existing typed error. Prospective controls improve 7/10 to 10/10; independent controls improve 3/6 to 6/6. |

The source substitutions had explicit review of the substituted plan. They
demonstrate lost objective consistency rather than unauthorized reads. The
repair rejects a mismatch and retains the original permission system. It
does not rewrite model arguments or insert benchmark answers.

The path checks cover quoted and unquoted paths with spaces, normalized
relative paths, multiple sources, isolated UNC syntax, filenames with
conjunctions, following prose and verified artifact references. Their scope is
bounded literal source consistency, not full natural-language entailment.
Quoting disambiguates unusual or extensionless paths followed by prose.

Parser regressions exposed during development were fixed using general syntax
boundaries and prospectively recorded controls. Earlier failed attempts,
fixture mistakes and intermediate code snapshots remain retained. See the
[boundary review](BOUNDARY_REVIEW.md) and
[architecture inspection](ARCHITECTURE.md).

## Completion, recovery and control metrics

These fractions use prospectively annotated eligible subsets. A correct
refusal, pause, waiting approval or uncertain result is not a completed
workflow. Whole-case assertions and expected stopping states are retained in
the detailed metrics.

| Metric | Original engine with final helpers | Final unchanged development set | Independent holdout |
| --- | --- | --- | --- |
| Whole-case pass | 114/120 (95.0%) | 103/120 (85.8%) | 32/40 (80.0%) |
| Expected verified completion | 32/34 (94.1%) | 26/34 (76.5%) | 11/15 (73.3%) |
| Expected successful recovery | 7/10 (70.0%) | 7/10 (70.0%) | 1/2 completed owned restarts (50.0%) |
| Cancellation correctness | 7/7 | 7/7 | 2/2 stopping states, with individual control assertions |
| Partial completion accuracy | 15/15 | 12/15 | Both partial-completion category cases pass |
| Persisted checkpoint sequence | 102/102 | 102/102 | Dedicated reopened readbacks 2/2 |
| Unauthorized write effects | 0 | 0 | 0 |
| Duplicate consequential writes | 0 | 0 | 0 |

Separate eligible safe-read cases achieve three of three expected completions
and two of two recovery outcomes. The explicit-goal supplement achieves six
of six expected completions and three of three partial outcomes. Those results
do not promote failed original cases.

Across the engineering run's 119 native workflows, the original file-write
ledger records **19 handler entries, 16 actual effects, zero unauthorized
entries/effects and zero duplicated logical writes**. All 119 checkpoint
sequences pass. The independent holdout records **46 original handler entries,
51 native invocations, 16 sensitive dispatches and 16 actual write effects**;
unauthorized dispatches/effects and duplicate consequential writes are zero.

Effect identity uses the stable workflow/step operation, durable invocation and
actual effect before any post-write failure. Unique invocation IDs or matching
final file contents alone are not accepted as duplicate-write proof. Authority
checks bind the reviewed plan, exact approval, capability definition, expiry
and original execution provenance. Setup writes and fixture-only direct store
effects are excluded from registered tool counts.

## Preserved failures and remaining limitations

The original baseline scored 114/120. One genuine source-substitution failure
now passes. The final public score also retains seventeen failed cases:

- Five original expectations require retry or recovery from `file.read`, whose
  actual registered descriptor says `retry_safe=False`. That descriptor and
  those original scores are unchanged. Eligible `file.stat` cases verify the
  supported retry behavior separately.
- Twelve original goals name only the first file while the generated test plan
  reads additional files. The source-consistency guard now refuses them. Their
  original goals, oracles and denominators stay unchanged. Twelve separate
  explicit-goal cases pass with the same graphs, fixtures, faults and expected
  outcomes.

All failed public IDs and assertions are recorded in
[MANAGER_EVIDENCE.json](MANAGER_EVIDENCE.json) and the
[development review](DEVELOPMENT_REVIEW.md). Engineering and independent
public reruns agree on every failed ID/assertion, outcome count, category score,
eligible ratio, write ledger and checkpoint sequence. Timing varies by run.

The once-only independent forty retains **all eight failed grades**. Its
automatic classifications and manual scope analysis are separate. Independent
review identifies four expectations conflicting with original non-retry-safe
`file.read`, including a restart-state expectation. The other four expose
stopping or planning limitations: a capability withdrawn after review leaving READY, a typed
generated-readback candidate-menu limitation, a conservative boundary for an
implicitly generated source, and persisted RUNNING after controller detachment
with verified progress. These outcomes do not establish successful completion;
no unsafe operation occurred. The independent report documents their remaining
scope without changing answers, promoting grades or tuning against the holdout.

Actual model goal understanding and plan quality are **blocked/unmeasured**.
Three rounds of the same six prospective native planning diagnostics made
eighteen attempts, with **zero generation HTTP requests and zero actual plans**.
The final round uses the frozen implementation. Available RAM was
1,721,548,800-1,833,721,856 bytes, below the original 2 GiB reserve. Separate
native selector inspection excludes the configured local supervisor solely for
`insufficient_ram_reserve`. Model/parent identities, health, memory/LAYA
settings and generation defaults match the original baseline. No reserve was
bypassed and no owner process was stopped to manufacture a model pass.

Physical cluster availability, SSH recovery, hardware failures, arbitrary
filesystem corruption, every possible disk/fsync crash and owner deployment
recovery are outside the established evidence. The campaign restarts only its
own test helpers.

## Real checkpoint/restart challenge

The final special challenge runs original local file operations across two
real, owned Python processes. The first process verifies a source read. An
original hash worker then encounters a controlled one-time timeout; the engine
persists its retry checkpoint. The process exits with code 83 during committed
backoff. A new process opens the same isolated database, waits for actual lease
expiry, acquires a higher fence, observes PAUSED and explicitly resumes.

The remaining hash retry, read, report write and report readback complete:
**five verified steps and six durable invocations**. The already verified first
read keeps exactly one invocation and its original identity. Recovery makes
zero new planning calls. The report passes original independent readback;
SHA-256 is `519ba1c3965ab413b3fd141811f325a2d5051ea81602020c8b98fedfeb839317`.
The boundary challenge completes in 2.908 seconds. The independent verifier
reruns it under the exact freeze and passes fourteen report/checkpoint/identity
audit checks.

Separate actual process crashes bracket a write's outcome:

| Crash boundary | Recovered result |
| --- | --- |
| Invocation durable, handler not entered | Completed source read remains verified; write remains uncertain; report absent; no replay |
| Original write returned, result not committed | Report exists but remains unverified; write remains uncertain; no replay |

Both refuse continuation. PID, parent relationship, creation time, lease fence,
invocation identities and tool audit evidence are retained. The final holdout
also contains six actual owned restart cases. Helper closure is independently
checked; Windows and unrelated user processes are not restarted.

## Fault coverage and timings

The transition inventory is generated from the current `TRANSITIONS` map;
there is no hardcoded expected count. All **65 declared store edges** receive
a stale CAS refusal probe and a separate SQLite fault after projection UPDATE
but before checkpoint insertion/commit. Persistent record/history comparisons
and close/reopen readback verify rollback. Valid transition commits are also
checked.

The main native scheduler traces reach **22/65 edges**; **43 remain explicitly
unreached natively**. A reached edge is not automatically counted as a fault
probe. Direct store tests do not prove exhaustive native scheduler reachability.
The [coverage matrix](../../evals/workflows/campaign4_transition_coverage.json)
records both kinds of evidence separately.

Native boundary injections additionally cover planning/resource admission,
definition/scope invalidation, committed pre-dispatch controls, original
read/write/hash failures, post-effect/pre-result crashes, partial verification,
active parallel withdrawal, transport failure and lease-expiry recovery.

Eight compute cases execute original `ComputeRegistry`, `ComputeScheduler`
and `InferenceTransport` against owned HTTP servers, with ten actual POST
requests. Socket disconnect, real HTTP timeout, bounded reassignment, enabled
and disabled fallback, false citations and late pause/cancel responses are
verified. Responses and worker resource fields are controlled fixtures, so
these results measure transport and authority behavior rather than live model
quality or physical worker performance.

| Timing population | n | P50 | P95 |
| --- | ---: | ---: | ---: |
| Original workflow submit to observed stop, final helpers | 102 | 125 ms | 203 ms |
| Final development workflow submit to observed stop | 102 | 140 ms | 234 ms |
| Final expected-completion subset, including failed expectations | 34 | 156 ms | 297 ms |
| Final native recovery subset | 6 | 140.5 ms | 156 ms |
| Eligible safe-read supplement | 5 | 2,234 ms | 2,281 ms |
| Explicit-goal supplement | 12 | 203.5 ms | 281 ms |
| Independent holdout whole case including fixture/process overhead | 40 | 344 ms | 2,734 ms |

Submit-to-stop timing excludes fixture setup/cleanup and includes intentional
barriers, failures and retry backoff. No nonzero clock offsets occur in these
public cohorts. Recovery's original eligible denominator is ten; only six have
native workflow timing, with direct store scenarios reported separately. The
holdout timing includes fixture and subprocess orchestration and is not
comparable to native submit-to-stop timing. Some final suites ran concurrently;
these controlled durations are not a model-speed or production latency claim.

## Reproduction and evidence provenance

The exact final freeze contains **288 files**, including all 192 HANNI Python
modules, configuration YAML, prospective inputs, public harnesses, transitive
fixture helpers and existing/new workflow tests. Derived reports are excluded.

- Manifest SHA-256: `f7f3ef6ca9a9772223b0a3dd2a0947826e4f7b942f43a5bce53e2c36eda42e49`.
- Archive SHA-256: `09de198ca6101c7cc1699464f1d1242d1fb0ed31ead88aa5c5524951cb17bf08`.
- Independent case seal: `a931a16a4c01b4fe19f183be68367d11d68c16641212164e962fc580557e7cf2`.
- Independent oracle seal: `bde5a797735e3a051f8927c3244fc99023360ab018d6cb43af3cccb5168cf764`.

The holdout was sealed before tuning, executed once after explicit source
freeze, and scored separately. Inputs/oracles and all code/configuration pins
remain unchanged. Private requests and answers were not inspected by engineers
or the manager. No holdout-driven repair or rerun occurred.

An initial development archive was mistakenly labelled original despite
containing the first service repair. The manager detected this by comparing
exact source hashes. That archive and its receipts remain intermediate evidence.
Authoritative baseline runs use the manager's pre-edit archive, pinned imported
package path and all 192 hashes, including original service SHA-256
`4bd6e5f0cdcc1659523329bfcba96fe1d61c0d386e27942b835dbba4669fe9a2`.
The final helper-compatible original rerun reproduces 114/120, 5/5, 7/10 and
65/65. See [PROVENANCE_ERRATUM.md](PROVENANCE_ERRATUM.md).

Run public evaluations into fresh owned output directories:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.campaign4.run_cohort --output data/campaign4-development/reproduce-main
.\.venv\Scripts\python.exe -X utf8 -m scripts.campaign4.run_cohort --corpus evals/workflows/campaign4_supplemental.json --output data/campaign4-development/reproduce-eligible
.\.venv\Scripts\python.exe -X utf8 -m scripts.campaign4.run_cohort --corpus evals/workflows/campaign4_explicit_goal_supplement.json --output data/campaign4-development/reproduce-explicit
.\.venv\Scripts\python.exe -X utf8 -m scripts.campaign4_boundaries.restart_challenge --output data/campaign4-boundaries/reproduce-restart
.\.venv\Scripts\python.exe -X utf8 scripts/campaign4_manager/run_regressions.py --output data/campaign4-manager/reproduce-regressions
```

The sealed final holdout has an exclusive once-only claim and is not a rerun
command. Read-only raw receipts, full source manifests, failure grades and
process audits remain in the ignored `data/campaign4-*` directories. Public
reports contain hashes and aggregate outcomes. All original failed attempts
remain retained. [CHECKPOINTS.md](CHECKPOINTS.md) records completed cycles.

Production edits are limited to workflow `service.py`, `planner.py` and
`references.py`. New tests, campaign scripts, reports and exact-byte corpus
attributes support this validation. Store, result verification, transport,
configuration and unrelated HANNI subsystems retain original production bytes.
All scenarios use isolated databases and disposable fixtures. Owner memories,
workflow data, accounts, remote nodes and unrelated untracked files remain
untouched. Changes have not been committed or deployed.
