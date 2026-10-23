# Campaign 6 scheduling review

Scheduling controls use the original ComputeRegistry, ComputeScheduler, InferenceTransport and WorkflowService with isolated SQLite stores and disposable loopback HTTP providers. Controlled replies, context proof fixtures and resource observations are implementation inputs; they are not live model, GPU or cluster evidence.

The frozen primary corpus contains 79 cases: six in each of the eleven requested categories, plus thirteen cancellation, authority, restart and Strata protocol controls. Inputs and expectations were sealed separately before outputs. Ten separately sealed supplemental cases clarify budgets, background-first reservation and partial-workflow status; they do not change the original 79 expectations.

| Cohort | Cases | Strict pass | Nonpass | Harness errors |
| --- | ---: | ---: | ---: | ---: |
| Archived original, same final harness | 79 | 66 | 13 | 1 |
| Candidate, same final harness | 79 | 69 | 10 | 0 |
| Separate adequate-budget/status controls | 10 | 10 | 0 | 0 |

The first archived-original run scored 67/79. It remains unchanged under baseline-cycle1. Later fixture corrections explicitly assign queued background priority and wait for the main ticket before releasing occupied capacity. The comparable baseline above reruns original production with those same corrected fixtures; the initial 67-to-candidate difference cannot be attributed solely to production repairs.

| Requested category | Original strict pass | Candidate strict pass | Cases each |
| --- | ---: | ---: | ---: |
| context_too_large | 5 | 6 | 6 |
| correct_worker_selection | 6 | 6 | 6 |
| insufficient_vram | 5 | 6 | 6 |
| multiple_eligible_workers | 6 | 6 | 6 |
| network_interruption | 6 | 6 | 6 |
| parallel_tasks | 3 | 4 | 6 |
| queue_saturation | 5 | 5 | 6 |
| result_verification | 3 | 3 | 6 |
| safe_reassignment | 2 | 2 | 6 |
| supplemental_controls | 13 | 13 | 13 |
| worker_busy | 6 | 6 | 6 |
| worker_unavailable | 6 | 6 | 6 |

Candidate nonpasses: C6DEV-parallel_tasks-03, C6DEV-parallel_tasks-04, C6DEV-queue_saturation-04, C6DEV-safe_reassignment-01, C6DEV-safe_reassignment-02, C6DEV-safe_reassignment-03, C6DEV-safe_reassignment-04, C6DEV-result_verification-02, C6DEV-result_verification-04, C6DEV-result_verification-05.

Frozen short-deadline queue/retry expectations and blocked-versus-partially-completed status expectations remain visible. A correct source rejection with no artifact write does not turn a mismatched frozen status oracle into a pass. The supplemental controls are a separate denominator.

## Reproduced repairs

Independent exposed controls reproduced fresh health combined with stale remote capacity, and a larger historical context proof overriding a smaller configured allocation. The scheduler now requires a finite nonboolean resource timestamp aged zero to thirty seconds for remote admission, while preserving optional unknown local CPU resources. Known configured and reported bounds constrain verified context at selection, compatible FIFO ordering, predispatch and returned-result admission. The original probe also retains its configured/reported allocation gate. No model size, server alias or stored historical proof becomes current capacity.

Registry and transport repairs are owned and documented by the other engineering worker. Source digests below bind this scheduling evidence to its actual imported dependencies, rather than claiming that only the scheduler changed.

| Candidate dependency | SHA-256 |
| --- | --- |
| hanni.compute.scheduler | `50a2efaf60087d68434e67a2f328ecdfef817b53d09c37d16451d9993c63daf6` |
| hanni.compute.registry | `d970cbdc32e0870ed69901ef1aec51b01d2a2820b6ebab6ea0ce81f83749b1c5` |
| hanni.compute.transport | `d6f30ea100282e94eadd806ba1753e95ae7751cc58bd1aa57732140a0c0a3ff0` |
| hanni.workflows.service | `ef0d76309eb314a8ab58a1b101b45918f36b04a4bc8ec4f83a44353753b7827c` |

## Evidence scope

Candidate evidence retains 77 controlled HTTP POSTs (0 from harness-error diagnostics), durable job events and actual overlap up to 2. Observed scheduler/provider cleanup leaks: 0 in complete receipts and 0 in harness-error diagnostics. Harness errors without cleanup diagnostics: 0. These are protocol and authority checks, not inference-performance measurements.

The six workflow verification controls contain one expected positive completion and five negative analysis/transport cases. Original source readbacks, numerical evidence verification and actual isolated artifact write entries determine acceptance; model agreement never verifies a result. Completed protocol deliveries remain distinct from original VERIFIED workflow jobs.

Production/corpus modifications were prohibited during final runs; per-case dependency snapshots and original raw provider request/response traces are retained. Harness errors preserve dispatch and cleanup diagnostics. All provider sockets, scheduler threads and databases belong to disposable test roots. Owner stores, settings, model services and remote processes are unchanged.

## Live serving and context limits

The manager found Tailscale port 22 reachable on the active nodes, but fresh Tailscale authentication prevented protected hardware/model discovery. There are no authenticated current GPU/resource identities, healthy compute workers or actual generation responses. Historical context records and model labels do not establish current runtime capacity. Live 8K/16K/32K/64K/128K stages, model throughput and hardware quality remain blocked and unmeasured.

If existing workers become eligible, the manager can use original verify_context on those existing allocations: refresh exact health/runtime identity and measured resources, preserve privacy and free-slot admission, reserve output tokens inside the total allocation, submit bounded synthetic records with independently held retrieval targets, retain actual prompt usage plus exact retrieval, and record only a successful original proof. Progress to the next stage only after supported proof; never restart, grow allocations, edit deployment or change drivers to create a result. Stop at the first unavailable, failed, busy, resource or payload boundary.

The original startup growth threshold is expressed in prior prompt-token proof, while verify_context reserves output within the allocation. Therefore a literal prompt target equal to an 8K allocation cannot pass with positive output reserve and cannot satisfy the next 16K growth threshold through that allocation. The independent exposed progression finding remains separate from live testing; configured capacity must not be reported as near-limit retrieval proof. The 262,144-byte request ceiling and maximum existing allocation also remain intact.

No default model replacement, remote launch or capacity increase follows from these controlled results.

## Final transport-bound revalidation

The earlier candidate scored 68/79 using transport SHA-256 `1b435529e2553831da89cd19469bc15c633024704104be48792df296ae0d93dc`. Its raw cases and published report snapshot remain in `data/campaign6-scheduling/candidate-uniform-cycle1`. After the independently accepted captured-source/credential-authority repair, the same unchanged executor and sealed scenarios ran once against final transport `d6f30ea100282e94eadd806ba1753e95ae7751cc58bd1aa57732140a0c0a3ff0`.

Final candidate score is 69/79, with 10/10 separate supplemental controls. The one difference from the earlier 68/79 candidate is `C6DEV-parallel_tasks-06`: earlier controlled overlap was one and its overlap wait failed; final overlap was two with both returned deliveries. The parallel category changed from 3/6 to 4/6. All other category scores and all ten remaining nonpasses are unchanged. This admission/timing variation is preserved without attributing an additional scheduling benefit to the credential repair. The original 66/79 comparison and its thirteen nonpasses remain immutable.

The final focused suite passed 56/56, zero failures/errors/skips, XML `data/campaign6-scheduling/guard-final-source-uniform-cycle2.xml`. No test, corpus, expectation or helper changed between the two candidate checkpoints. The final 79-case cohort retains 77 controlled HTTP POSTs, and the ten-case supplement retains 20. No real model responses or live worker inference were collected. All final cases have full receipts; observed cleanup leaks are zero, and every imported dependency digest stayed unchanged during each case.

The ten primary nonpasses comprise two limited-parallel short-deadline delivery cases, one FIFO deadline, four short-budget reassignment cases and three partial-versus-blocked workflow status expectations. The prospective queue limit is 0.15 seconds; it includes actual HTTP and receipt overhead within the original admission budget. These remain failures against their original oracles. The six primary workflow verification controls independently have one positive artifact write and five negative cases with no artifact writes, yielding 1/1 positive completion and 5/5 negative write prevention. These scoped behavior counts do not regrade the strict status expectations.

## Commands and source provenance

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_campaign6_scheduling_contracts.py -q --junitxml=data/campaign6-scheduling/guard-final-source-uniform-cycle2.xml
.\.venv\Scripts\python.exe -m scripts.campaign6_scheduling.metrics --baseline data/campaign6-scheduling/baseline-uniform-cycle2 --candidate data/campaign6-scheduling/candidate-uniform-cycle2 --supplement data/campaign6-scheduling/supplement-candidate-uniform-cycle2
```

The original baseline prepends `data/campaign6-scheduling/original-source/extracted/src` and its parent before importing the unchanged executor; receipt paths and hashes prove actual original imports. The candidate uses held current production source. All commands, public corpus and helper digests, per-arm evidence directories, prior/current score differences and cleanup ownership are recorded in `data/campaign6-scheduling/SOURCE_READY_CYCLE2.json`. Earlier `SOURCE_READY.json` is preserved as the prior checkpoint.

The true original source archive contains 403 files and has SHA-256 `cef0de89f1943f21ed03490cefc065d5b5c681e5570d06c3b0535010e465dcc1`. Raw controlled requests/responses, durable jobs, actual workflow source readbacks and case-specific dependency snapshots are retained in each cohort directory. Separate supplemental original evidence is `supplement-baseline-uniform-cycle2`, also 10/10. No further case execution or grading changes are required for this scheduling evidence.
