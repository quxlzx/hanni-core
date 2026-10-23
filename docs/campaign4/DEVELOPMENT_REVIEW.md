# Campaign 4 workflow development review

The archived original engine passed 114 of 120 prospectively annotated scenarios. The candidate passed 103 of 120 using the same frozen inputs and oracles.

The main corpus contains six structurally varied scenarios in each of the twenty requested categories. It runs 102 scenarios through the original WorkflowService, WorkflowPlanner, McpHost and default ToolRegistry, and 18 through original durable store boundaries. Controlled planner replies prove contracts and execution behavior; they do not measure the installed model's goal understanding or planning quality. Those categories remain contract-only.

## Frozen evidence

Original commit: `0aede83`. The manager archived all 192 Python modules under `src/hanni` before repairs at `data/campaign4-manager/original-source/extracted/src`, including transitive policy, permission, tool and privacy dependencies. Every corrected baseline run records the actual imported package root and all source hashes before and after execution.

Main corpus SHA-256: `fa167f0a69b059c3ff6320a6d813f6eb8d6f6754447cd7648a5ef54862285db5`. Separate five-case supplement: `b4373d853007345908bc3786588ea3b1e60a6eaaf537c3856bcab5660ef298ff`. Dynamic after-projection/checkpoint fault corpus: `987c1315b59c2d60f1817b836557cbb5494bd6d019f54fd3ad2b582c7de5fe48`.

The first attempted baseline retained 102 scheduler setup errors: the harness passed a dictionary to the original WorkflowLimits.from_config object interface. The original controller had not started for those cases. That fixture error was fixed using the original WorkflowLimits constructor; all first-attempt receipts remain at `data/campaign4-development/baseline-cycle1`. A draft chat-return interface mismatch was corrected before any execution. A source audit subsequently showed that the engineer's first full archive already included the first scheduler repair. That archive and its corrected baseline-cycle2 receipts remain intermediate-source evidence. The engineer acknowledged the provenance mistake. The corrected true original baseline has zero harness errors and is preserved at `true-original-cycle3`; its five-case supplement, ten protocol probes and 65 checkpoint fault probes were also rerun in the manager's verified original package. All four complete before/after manifests are identical. See PROVENANCE_ERRATUM.md for source hashes and retained paths.

## Baseline findings and repairs

One genuine planner failure substituted a different source file from the owner's explicit request and completed. The separate boundary engineer owns its general source-binding repair and independent acceptance. The other five main-cohort failures are prospectively annotated expectations that incorrectly assumed file.read was retry-safe. Its original descriptor deliberately sets retry_safe false. Those outcomes, original oracles, 34 completion-eligible cases and 10 recovery-eligible cases remain in the score. No descriptor was changed to raise the score.

A further authoring audit found six completion-positive graphs whose default objective names only the first source, plus three intended partial and three tool-failure graphs with the same additional-source conflict. The candidate source guard correctly refuses those extra literal sources. Every affected original expectation remains frozen; new candidate nonpasses caused by this conflict are reported as such and are not regraded or excluded. Intentional wrong-source and malformed-admission cases remain separate negative controls.

A NEW twelve-case corpus at `evals/workflows/campaign4_explicit_goal_supplement.json` explicitly states all intended source paths for those original graph tests. The graph, files, controls, faults and expected outcomes are unchanged; only its new objective and evaluation identity differ. Its prospective seal is `206b3a15c9c4c02449c4919bb9687dbdc9f0a541d8150a0d08e5ccda8cf284ab`. This is exposed development authoring correction, not an unseen evaluation, score migration or replacement for the original120 denominator. Separate candidate supplement score: 12/12.

A separately sealed five-case supplement uses the genuinely retry-safe original file.stat(hash=True) handler. All five pass on the verified original engine in `true-original-supplement`: one transient timeout recovers within two invocations; repeated timeouts stop at that budget; interruption leaves a paused read; explicit resume completes within its retry budget; two actual original file.read handlers overlap while held at their declared filesystem leaf barriers. The original cohort is unchanged.

The owned reference repair addresses an independently reproduced eager math.isfinite conversion. A bounded JSON integer larger than a float raised OverflowError even for an integer or incompatible string reference. Lazy number-only validation keeps exact integer values and turns unsupported number conversion into the existing bounded type rejection. Booleans remain distinct from integers. Ten prospective direct reference/schema controls improved from 7/10 to 10/10; independent six-case baseline reproduction had three failures. Store, verification and transport-schema production behavior were not changed.

## Outcome denominators

| Measurement | Original | Candidate |
| --- | --- | --- |
| All frozen scenario assertions | 114/120 | 103/120 |
| Completion eligible: complete case assertions | 32/34 | 26/34 |
| Recovery eligible: complete case assertions | 7/10 | 7/10 |
| Cancel eligible: complete case assertions | 7/7 | 7/7 |
| Partial eligible: complete case assertions | 15/15 | 12/15 |

Candidate original-oracle nonpasses remain in the aggregate: WFDEV-04-01, WFDEV-05-03, WFDEV-05-05, WFDEV-06-01, WFDEV-06-02, WFDEV-06-03, WFDEV-06-04, WFDEV-06-05, WFDEV-06-06, WFDEV-11-02, WFDEV-11-03, WFDEV-12-01, WFDEV-12-02, WFDEV-16-02, WFDEV-18-04, WFDEV-18-05, WFDEV-20-05. Explicit-source goal conflicts: WFDEV-04-01, WFDEV-05-03, WFDEV-05-05, WFDEV-06-01, WFDEV-06-02, WFDEV-06-03, WFDEV-06-04, WFDEV-06-05, WFDEV-06-06, WFDEV-11-02, WFDEV-11-03, WFDEV-20-05.

Planned refusals, cancellations, pauses, waiting approvals and uncertainty are separate desired outcomes. They are not counted as successful verified completions. Direct store tests make no scheduler or model quality claim.

## Category results

| Category | Original | Candidate |
| --- | --- | --- |
| Ambiguous prior write outcomes | 6/6 | 6/6 |
| Approval rejection | 6/6 | 6/6 |
| Backend interruption | 6/6 | 6/6 |
| Bounded retries | 4/6 | 4/6 |
| Capability availability | 6/6 | 6/6 |
| Checkpoint persistence | 6/6 | 6/6 |
| Dependency ordering | 6/6 | 5/6 |
| Goal understanding | 5/6 | 6/6 |
| Multi-step tool usage | 6/6 | 6/6 |
| Partial completion | 6/6 | 4/6 |
| Pause and resume | 6/6 | 6/6 |
| Permission requests | 6/6 | 6/6 |
| Plan generation | 6/6 | 6/6 |
| Recovery after restart | 4/6 | 4/6 |
| Safe parallel execution | 6/6 | 0/6 |
| Sequential execution | 6/6 | 4/6 |
| Step verification | 6/6 | 6/6 |
| Task cancellation | 6/6 | 6/6 |
| Worker disconnection | 5/6 | 5/6 |
| Workflow completion reporting | 6/6 | 5/6 |

## Durable transitions, side effects and timing

Every one of the 65 dynamically declared workflow edges was exercised at the original store's stale compare-and-swap commit boundary. An additional prospectively sealed SQLite TEMP-trigger fault aborted the checkpoint insertion AFTER the workflow projection UPDATE but BEFORE transaction commit. All 65 rollback and close/reopen comparisons preserved the record and history exactly. These are direct store atomicity guarantees, not proof of native scheduler reachability.

The main baseline's native checkpoint traces reached 22 of 65 declared edges. The remaining edges are explicitly UNREACHED_NATIVE in the published metrics. Observed edge reachability is not automatically credited as a failure probe at that edge.

The filesystem leaf ledger records EVERY original file.write handler entry, correlation ID, durable invocation ID, logical workflow/step identity, actual effect before a post-write exception, and original reviewed or consumed authority. Setup and report writes are excluded by original handler frame and exact campaign path. The final ledger independently checks matching unexpired plan/approval hashes, owner provenance and exact supervised action review. Fixture effects in direct-store tests are reported separately from registered tool dispatch.

Original write ledger: 19 entries, 16 actual effects, 0 unauthorized entries and 0 unauthorized effects. Repeated consequential writes are checked by logical operation rather than unique receipt IDs or final overwritten content.

Original workflow submit-to-observed-stop timing: n=102, P50=125.00 ms, P95=188.00 ms. This excludes fixture setup/cleanup; injected resource admission is controlled. Nonzero clock offsets: 0. Completion and recovery subset timing and whole-fixture timing are published separately in the JSON metrics. Controlled barriers, retry backoff and failures remain included.

Candidate workflow submit-to-observed-stop timing: n=102, P50=140.00 ms, P95=234.00 ms. This excludes fixture setup/cleanup; injected resource admission is controlled. Nonzero clock offsets: 0. Completion and recovery subset timing and whole-fixture timing are published separately in the JSON metrics. Controlled barriers, retry backoff and failures remain included.

In-process detach/restart cases use fresh original service/store instances against the same disposable DB. They do not establish the requested process restart challenge. That separately implemented challenge is owned by the boundary engineer and requires two actual owned test-runner processes, persisted verification and a final report readback.

## Verification and reproducibility

Focused verification: 120 tests pass in `data/campaign4-development/focused-final.xml`: 29 new contract tests plus 91 existing workflow store, verification and transport-schema tests. Independent acceptance and the untouched private holdout are reported by the verifier; their inputs and answers were not opened by this engineer.

Run the original baseline with the archived source directory first on PYTHONPATH:

```powershell
$env:PYTHONPATH = (Resolve-Path 'data/campaign4-manager/original-source/extracted/src').Path
.\.venv\Scripts\python.exe -m scripts.campaign4.run_cohort --output data/campaign4-development/<new-original-run>
```

A candidate run uses the current production modules and a new output directory. The runner saves full source-before and source-after manifests; input and oracle files are separated before execution. Every output directory is created exclusively so a repeated run cannot overwrite earlier evidence. The corpus author refuses to overwrite different sealed bytes.

No owner database, configuration, default model, remote node, desktop process or device was modified. All stores, tool effects and service threads are campaign owned. Actual model quality, untouched final acceptance and comprehensive native transition failure coverage require their separate evidence; controlled contract passes do not establish them.

## Final frozen execution evidence

All five candidate cohorts used identical before/after manifests: 192 current production modules, 13 imported controlled-helper sources, and the four default configuration source hashes. Their manifests match across all five runs. The manager freeze manifest remains unchanged; its SHA-256 is `f7f3ef6ca9a9772223b0a3dd2a0947826e4f7b942f43a5bce53e2c36eda42e49`. No source, harness, test, protocol, or prospective corpus changed after GO. Public supplemental metrics are in `evals/workflows/campaign4_additional_results.json`; dynamic scope coverage is in `evals/workflows/campaign4_transition_coverage.json`.

| Final suite | Passed | Meaning | Raw evidence |
| --- | --- | --- | --- |
| Original frozen corpus | 103/120 | Original expectations retained, including all 17 nonpasses | `data/campaign4-development/candidate-final` |
| Retry and parallel supplement | 5/5 | Eligible hash retries/recovery and two real read handlers overlapping | `data/campaign4-development/candidate-supplement-final` |
| Explicit-goal supplement | 12/12 | New exposed goals, separate from the original score | `data/campaign4-development/candidate-explicit-final` |
| Reference and transport protocols | 10/10 | Original reference/schema implementation, direct contracts | `data/campaign4-development/candidate-protocol-final` |
| Projection/checkpoint aborts | 65/65 | Direct original SQLite rollback and exact close/reopen readback | `data/campaign4-development/candidate-transition-faults-final` |

The main final run recorded 18 original file.write entries and 15 actual effects. The explicit-goal supplement recorded one entry and one effect; the five-case supplement performed no writes. Across these 119 native scheduler scenarios there were zero unauthorized write entries, zero unauthorized write effects, and zero logical operations with duplicate consequential effects. The eighteen direct-store scenarios remain outside those registered-handler authority claims. All 137 public scenario executions had zero harness errors. Persisted checkpoint sequences were monotonic in 119/119 native cases, which is a narrower claim than arbitrary crash recovery. Native main-corpus traces still reached 22/65 declared edges; the other 43 remain explicitly unreached.

Completion-eligible main workflows retain their 34-case denominator: submit-to-observed-outcome P50 156 ms and P95 297 ms, including original-oracle refusals. Recovery-eligible main cases retain their 10-case denominator, of which six native scheduler cases have this duration measurement: P50 140.5 ms and P95 156 ms. The retry supplement includes durable backoff: completion subset n=3, P50 2250 ms and P95 2281 ms; recovery subset n=2, P50 1203 ms and P95 2250 ms. The explicit-goal completion subset n=6 has P50 242 ms and P95 281 ms. No fixture clock was advanced in these final cohorts. These are controlled stress-run times, not a claim about production or live-model latency.

A supplemental comparability run reexecuted the exact manager-archived original with the final frozen helpers. It reproduced 114/120 main cases, 5/5 retry/parallel cases, 7/10 protocols and 65/65 transaction faults, with unchanged original failure identities and zero scenario harness errors. Those four before/after manifests record the exact original service hash `4bd6e5f0cdcc1659523329bfcba96fe1d61c0d386e27942b835dbba4669fe9a2`, original reference hash `f1da6727d0c5b3e54d6ac76aa8854a8731b915053dfcac794e7cf66ca2faab3a`, and identical controlled-helper hashes to the candidate. New raw paths are `true-original-final-helpers`, `true-original-supplement-final-helpers`, `true-original-protocol-final-helpers` and `true-original-faults-final-helpers` under `data/campaign4-development`. Earlier original and intermediate-source artifacts remain intact. This additional original timing has n=102, P50 125 ms and P95 203 ms; it is separately labeled rather than replacing the first corrected baseline timing.

The bounded owned runner processes exited normally after their original services, worker threads and disposable stores were closed. This engineer launched no owner backend, model runtime or remote process. The boundary engineer's actual two-process restart proof and verifier's final private acceptance remain separate evidence.

The final commands were:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
.\.venv\Scripts\python.exe -m scripts.campaign4.run_cohort --output data/campaign4-development/candidate-final
.\.venv\Scripts\python.exe -m scripts.campaign4.run_cohort --corpus evals/workflows/campaign4_supplemental.json --output data/campaign4-development/candidate-supplement-final
.\.venv\Scripts\python.exe -m scripts.campaign4.run_cohort --corpus evals/workflows/campaign4_explicit_goal_supplement.json --output data/campaign4-development/candidate-explicit-final
.\.venv\Scripts\python.exe -m scripts.campaign4.protocol_probes data/campaign4-development/candidate-protocol-final
.\.venv\Scripts\python.exe -m scripts.campaign4.transition_faults data/campaign4-development/candidate-transition-faults-final
```
