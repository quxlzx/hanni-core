# Public workflow performance attribution

Thirty instrumented public workflow repetitions completed with independent file/arithmetic oracles: ten original text reads, ten typed-reference read-to-artifact goals and ten four-step observed-percentage/difference/artifact goals. These are repeats of exposed scripted engineering objectives, not new core or unseen planning cases. They do not enter the seven-core or eighteen-sealed completion denominators and establish no general 95% success claim.

Production Python bytes matched before/after, manifest SHA256 `5ae7bf5e40dc50642086d14a9afc5d480934ece90a6c42c9944a76c2a9369add`. Instrumentation lives only in `scripts/v3_review/measure_performance.py`; its run hash is `8d19f38291f5cd3a266cbabd429a70f4ae4d2964a1fd1ca974800299233676a9`. Raw sanitized timing rows are retained locally in `data/hanni-v3-review/performance-attribution-cycle-1/performance.json`. No production/configuration, capability definition, permission, return value or original outcome oracle was modified.

## Timing method and boundaries

Timers use `perf_counter_ns` wall intervals. Transparent instance-method wrappers call the originals and return their exact values. A Python profile callback records entry/return only for the exact original `file.read`, `file.stat` and `file.write` code objects; it neither substitutes those handlers nor changes their registry definitions. The profile and timer wrappers add overhead. The run is exploratory, sequential and instrumented on the current Windows workstation, not a quiet paired before/after benchmark.

Fixture construction, initial registry/database setup, runner startup and one warm-up per workload are excluded. Thirty measured submission-to-terminal intervals include scripted two-pass planning, automated test-owner reviews, scheduler waits, actual original handlers, verification and private persistence. No human approval wait, model load, real inference, native rendering or provider/network latency is represented. File input and checked numeric data belong to temporary local fixtures, and providers are disconnected.

P50 is the sample median. P95 is nearest-rank `ceil(0.95*n)`; with ten workflow samples this is the maximum, not a well-estimated population tail. No confidence interval, statistically meaningful regression, speedup or universal latency guarantee is inferred.

| Submission to verified terminal | n | P50 ms | P95 ms | Mean ms |
| --- | ---: | ---: | ---: | ---: |
| One original text read | 10 | 175.700 | 183.991 | 174.582 |
| Read plus managed artifact | 10 | 409.780 | 422.711 | 408.313 |
| Read, two checked analyses, artifact | 10 | 637.005 | 705.863 | 644.865 |

## Nested pipeline attribution

These intervals overlap and **must not be added**. Planning contains route/client/validation/store work. Host dispatch contains registry execution; registry execution contains original handlers, permission/audit and original verification, including additional readbacks. Begin/finish invocation and outer transactions contain checkpoint inserts. Counts reflect actual calls, including scheduler/fence checks and verification readbacks, not thirty disjoint phases.

| Measured interval | n | P50 ms | P95 ms |
| --- | ---: | ---: | ---: |
| Original host capability route, inclusive | 80 | 9.973 | 26.939 |
| Planning pipeline method, inclusive | 30 | 96.172 | 140.004 |
| Scripted client reply/serialization | 80 | 0.895 | 1.382 |
| Original host dispatch, inclusive | 50 | 32.537 | 71.641 |
| Original registry execute, inclusive | 90 | 27.231 | 53.156 |
| Original file.read handler | 30 | 0.423 | 0.685 |
| Original file.stat handler | 40 | 1.092 | 1.900 |
| Original file.write handler | 20 | 4.092 | 8.643 |
| Store begin-invocation, inclusive | 70 | 6.019 | 7.225 |
| Store finish-invocation, inclusive | 70 | 7.422 | 8.880 |
| Checkpoint serialization/INSERT, **without commit** | 660 | 0.150 | 0.229 |
| Outer transaction, inclusive | 1,806 | 0.892 | 7.223 |
| Outer enter: lock/connect/BEGIN boundary | 1,806 | 0.023 | 0.041 |
| Outer exit: commit/context cleanup boundary | 1,806 | 0.718 | 1.411 |
| Nested transaction context, inclusive | 270 | 1.881 | 4.589 |

The transaction timer preserves the original context manager and SQLite operations. Enter includes lock acquisition, connection access and BEGIN; exit includes commit and Python context/lock cleanup. They are not pure lock, SQL-engine or fsync measurements. Checkpoint INSERT timing excludes its later enclosing commit. Handler wall time includes its Python calls and disk I/O, plus profiling overhead. Hardware-cache state, OS scheduling and independent storage-device latency are not isolated.

Actual model inference overhead is **NOT MEASURED by this harness**. Its scripted client returns deterministic queued JSON; the sub-millisecond client interval is not an LLM speed claim. Pure verification-exclusive cost, exclusive authorization/audit cost, model queue delay, provider HTTP latency, native perceived latency and kernel throttling remain **NOT MEASURED**. Existing report measurements have different setup/instrumentation boundaries; these values should not replace them silently or imply a paired improvement.

## Retained failed recovery appendix

The first attribution command exited 1 after all thirty timing goals passed because its same-process recovery appendix expected ordinary `file.read` to recover as a retry-safe read. The authoritative original definition has `retry_safe=False`; `file.stat` is the explicit opted-in example. The appendix's expectation was wrong, and no recovery timing was accepted before that assertion. The failed JSON remains unchanged, with `passed=false`, thirty successful timing rows and zero accepted recovery rows. The original failed-run script is also retained at `data/hanni-v3-review/performance-attribution-cycle-1/measure_performance-cycle-1.py`, matching the recorded `8d19f382...` hash. It is not reported as an entirely passing suite or an interrupted-goal completion result. Root authorized removing that unsupported appendix from the public performance-only runner; its thirty positive outcome oracles remain unchanged, and recovery belongs to the separate genuine process runner. The corrected performance-only command's later passing run is recorded separately below.

A separately authorized follow-up uses the existing genuine owned-process probe and unchanged public recovery oracles for `file.stat` and uncertain writes. No original classification is broadened and no blind case is read.

## Genuine process recovery timing follow-up

The separate `scripts/v3_review/measure_process_recovery.py` run passes **12/12** repeated boundary cases: three repeats of each original safe-read before-dispatch/after-result crash and uncertain-write before-dispatch/after-result crash. It calls the existing `service_process_probe` and reuses the original public process-test helpers/oracles. The owned child actually exits with code 73 at its durable boundary; no handler is replaced. The parent observes real lease expiry before opening the original store/controller again. These are repeated public safety tests, not twelve new unseen objectives.

| Boundary | n | P50 ms | P95 ms | Mean ms |
| --- | ---: | ---: | ---: | ---: |
| Recovery start to safe projection: original retry-safe file.stat | 6 | 31.915 | 55.939 | 35.130 |
| Recovery start to safe projection: uncertain original write | 6 | 38.611 | 42.298 | 36.875 |
| Explicit owner resume to verified safe-read goal | 6 | 1,959.062 | 2,007.503 | 1,965.371 |

The first two intervals start **after** parent fixture construction and the deliberate 1.15-second real expiry wait. They include original service start, durable owner claim/recovery, initial thread start and the first detail projection. They are not pure SQL recovery times. The process probe deliberately configures a one-second lease; the production lease policy is unchanged. Parent fixture setup is recorded separately (11.259–20.688 ms) and excluded. Child startup, pre-crash planning/execution, OS reboot, deployment and model startup are excluded. The broader observed-child-death-to-safe boundary, which includes that deliberate wait and parent setup, spans 1,184.919–1,220.741 ms for safe reads and 1,199.240–1,218.670 ms for writes. It is not a production restart SLA.

All six safe reads first become **Paused**, their crashed invocation is **Abandoned**, and they remain paused without owner input. Explicit original resume then admits one bounded second stat attempt followed by the required original read; actual evidence becomes VERIFIED and no write runs. The approximately two-second resume interval includes the original recovery retry backoff and scheduling. It must not be added to safe disposition as though automatic background completion occurred.

All six uncertain writes become **Blocked**; retained prerequisite reads remain verified, and both resume and safe-retry controls are rejected by the unchanged service. Three after-result cases retain the single actual file effect, and three before-dispatch cases retain no file effect. Original audit and independent file checks prove no replay or duplicate write in these repeated scenarios. This is successful safe disposition, **not** interrupted-write completion or a universal exactly-once guarantee. The existing suspended-owner fencing test remains separate; it was not timed here. Unauthorized-execution rate is not measured by this timing appendix.

Raw evidence is retained at `data/hanni-v3-review/performance-process-recovery-cycle-2/recovery-performance.json`. Recovery harness SHA256 is `f6fd695603d94b4d285965db8e59359f0803a6c6aa365d5cea9b6dd04e569a64`. Production manifest again matches before/after `5ae7bf5e40dc50642086d14a9afc5d480934ece90a6c42c9944a76c2a9369add`. These are boundary filesystem manifests, not proof of an atomic continuous freeze or the exact Python bytecode loaded inside each child; the existing child probe records no complete runtime-bytecode manifest. Treat these measurements as public development attribution, not sealed/final-candidate quality evidence. No production/configuration/oracle changes, real model, native window, provider SDK server, SSH or user-data action were performed. Both attribution subprocesses are stopped; rerunning against a new candidate requires coordinator freeze/GO.

Reproduce against isolated public fixtures only:

```powershell
# Performance-only public goals; the historical failed appendix stays preserved.
.\.venv\Scripts\python.exe scripts/v3_review/measure_performance.py --output data/hanni-v3-review/performance-attribution-new
# Correct genuine process-boundary attribution with unchanged public oracles.
.\.venv\Scripts\python.exe scripts/v3_review/measure_process_recovery.py --output data/hanni-v3-review/performance-recovery-new
```

## Current candidate: corrected performance-only cycle 3

The corrected public runner actually passes **30/30** measured repetitions, exit 0, no errors and no recovery appendix. Raw evidence remains in `data/hanni-v3-review/performance-attribution-cycle-3/performance.json`. These are the same three exposed workload definitions and independent outcome oracles, ten measured repetitions each plus excluded warm-ups. They remain outside the seven-core/eighteen-blind completion denominators.

This run uses the candidate following production catalog checkpoint `3c5526b`. The coordinator's full regression suite was running during the initial timing windows and exited while timing proceeded. Concurrent CPU/storage load was not isolated or separately instrumented. This is **not a quiet paired benchmark**; differences from the historical cycle-1 matrix cannot establish a causal regression or improvement. The same profiling, nested/inclusive, startup exclusion and nearest-rank percentile limitations apply.

| Current candidate submission to verified terminal | n | P50 ms | P95 ms | Mean ms |
| --- | ---: | ---: | ---: | ---: |
| One original text read | 10 | 187.031 | 197.784 | 185.900 |
| Read plus managed artifact | 10 | 439.146 | 486.305 | 446.205 |
| Read, two checked analyses, artifact | 10 | 682.328 | 717.737 | 688.496 |

| Current candidate measured interval | n | P50 ms | P95 ms |
| --- | ---: | ---: | ---: |
| Original host capability route, inclusive | 80 | 10.315 | 28.733 |
| Planning pipeline method, inclusive | 30 | 105.982 | 150.716 |
| Scripted client reply/serialization | 80 | 0.931 | 1.535 |
| Original host dispatch, inclusive | 50 | 34.092 | 81.045 |
| Original registry execute, inclusive | 90 | 28.928 | 62.728 |
| Original file.read handler | 30 | 0.455 | 0.713 |
| Original file.stat handler | 40 | 1.061 | 3.990 |
| Original file.write handler | 20 | 4.547 | 7.511 |
| Store begin-invocation, inclusive | 70 | 6.181 | 7.983 |
| Store finish-invocation, inclusive | 70 | 7.557 | 9.035 |
| Checkpoint serialization/INSERT, without commit | 660 | 0.159 | 0.233 |
| Outer transaction, inclusive | 1,809 | 1.055 | 7.559 |
| Outer enter: lock/connect/BEGIN boundary | 1,809 | 0.024 | 0.044 |
| Outer exit: commit/context cleanup boundary | 1,809 | 0.800 | 1.946 |
| Nested transaction context, inclusive | 270 | 1.974 | 4.790 |

Production-Python boundary manifests match before and after at `45c869127f9a23a2f9e464fa8f5dd16bcf7cfa0fd5362d7407974a8703bc42a0`. The corrected timing script SHA256 is `713fb27e8abd4ce9a766cad26dd83abbf2c83de32ec3b81170e683828c9dbf50`. This runtime-only filesystem scope differs from the coordinator's full 199-file production/frontend/public-config freeze, raw SHA256 `ee7654867b4c0c25c6fc302d2f40240d841b57b3b803243e69f8585fd4d1b5de`; neither is a per-child loaded-bytecode proof.

The original failed cycle-1 appendix/source and passing cycle-2 genuine process-recovery evidence remain unchanged. Recovery timing was **not rerun on this later catalog candidate**; its six safe-read and six uncertain-write disposition intervals retain their earlier manifest and stated scope. The current performance-only run provides no actual inference, provider, native perceived latency, OS reboot or suspended-owner timing. No new production/configuration/outcome-oracle change or additional probe was performed while appending this report.
