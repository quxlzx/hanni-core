# Reliability and Intelligence V2: independent final evaluation

**Overall: PARTIAL.** Controlled execution reliability, original authority boundaries and native observability pass their scoped checks. **The unseen language/model quality goal is not established.** Required-tool recall and complete-menu sufficiency did not improve on the sixty sequestered cases; the once-only configured-model lexical-evidence score declined. No final failures were used for tuning or rerunning. The complete failure ledger remains in `data/hanni-reliability-v2-review/final-holdout-summary.json`.

Original source791bdab was captured/evaluated before development. Final source741a776 was frozen after the coherent full regression/native checks and evaluated once using identical case fields, oracle, original settings, controlled adapters and Windows hardware. The actual cached Qwen3.5-4B-Q4_K_M model ran through the original LlamaCppClient, TextSession/CLI controller wrapper, MCP host/session and registry. No scripted model replaced inference. Context16384, max tokens768, temperature0.35, top-p0.9, parallel1 and q8_0 KV remained fixed. Runtime reported Vulkan1 and33/33 layers offloaded. Explicit cached weights were used without downloading. Final ownedPID54364 closed; external model PID sets were empty before/after. Original ownedPID41276 had also closed.

## Distinct metrics and denominators

The60 cases include44 tool-requiring requests and16 expected-no-tool requests; required single capabilities and alternative groups total48 expected slots. Recall counts recovered slots; complete-menu sufficiency requires every requested slot/group and no forbidden exposure. It is not a model outcome.

| Metric | Original | Frozen final | Scope / 95% Wilson interval |
|---|---:|---:|---|
| Required-slot recall, configured bounded menu |32/48,66.67%|32/48,66.67%|Both52.54–78.32%; no unseen retrieval improvement|
| Complete candidate-menu sufficiency |28/44,63.64%|28/44,63.64%|Both48.87–76.22%|
| Correct metadata no-tool menu |11/16,68.75%|11/16,68.75%|Both44.40–85.84%|
| Positive full-pipeline tool selection |28/44,63.64%|28/44,63.64%|Includes retrieval failures; both48.87–76.22%|
| Actual model selection given complete menu |28/28,100%|28/28,100%|Both87.94–100%; conditional, not all44 requests|
| Negative requests with no handler execution |13/16,81.25%|12/16,75%|56.99–93.41% →50.50–89.82%|
| Model-call structural argument validation |50/50|55/55|92.87–100% →93.47–100%; original schemas, no unknown wire names|
| Independently semantic file-search arguments |2/2|2/2|Both34.24–100%; other semantic argument fields not independently measured|
| Controlled selection plus lexical evidence answer |41/60,68.33%|38/60,63.33%|55.77–78.69% →50.68–74.38%; not independently verified user-task completion|
| Unsafe/write adapter entries |0/48 actual entries|0/52 actual entries|Controlled read-only handlers behind original gates; not a universal authority guarantee|
| Forbidden metadata menu exposures |0/60|0/60|No handlers/model execute in metadata probe|
| Positive independent controlled workflow outcomes |14/18|18/18|54.79–91.00% →82.41–100%; genuine isolated state/provider fixtures|
| Safe bounded workflow read recovery |0/2|2/2|0–65.76% →34.24–100%; two exposed development cases|
| Repeated ambiguous side-effect attempts, controlled workflows |3|0|Same forty fixtures; permission violations are NOTMEASURED by this runner|

The raw all-case live selection score is41/60 original and40/60 final; its decline comes from negative-case execution, not positive28/44 or conditional28/28 selection. Three model calls were suppressed/reused in the final controller, explaining55 raw calls versus52 adapter entries; original50 versus48 differs by two. The earlier baseline48/48 semantic claim was overstated: all unexamined adapters assign a default true flag, while only2 actual file-search calls have independently checked expected terms. [The baseline report](m1-configured-model-baseline.md) explicitly records that correction without changing any oracle/input.

Recorded runtime verification is distinct from independent positive workflow outcomes: old18 records are absent, not evidence of18 failed old outcomes. Current16/18 positive workflows have VERIFIED evidence scopes, one MCP echo remains UNVERIFIED/server-reported, and explicit memory storage lacks a verification record. The eighteen independently checked positive outcomes are not forty user actions: the other22 fixtures comprise8 safe refusals,10 expected failure-handling cases and4 receipt-only cases. Literal pipeline checks29/40→40/40 include two old conservative app responses that the narrow lexical oracle falsely rejects; they are not eleven independently established old reliability failures. See [full independent workflow audit](workflow-oracle-audit.md).

## Failures retained, no post-holdout tuning

The final language/model oracle retains22 failed lexical-evidence expectations. The predominant gap is sixteen tool-requiring cases without a complete requested menu; successful conditional model choice cannot compensate for omitted capabilities. Extra menu exposure increased: mean1.383→1.433 candidates and49→52 conservative irrelevant exposures across sixty cases. There is no unseen improvement or precision gain in this sample.

Three literal evidence-score declines were independently inspected:

- FINAL-014 retrieves/selects the expected diagnostic evidence but the final answer omits the expected CPU/RAM measurements while discussing possible background-process/power-plan causes. It does not establish the requested diagnosis or cause.
- FINAL-023 correctly reports3,072MB used of8,192MB with5,120MB free. The immutable lexical pattern accepts `3072` or3GB but rejects comma formatting. This is a false negative in the fixed oracle, not a demonstrated factual answer regression. The raw38/60 remains unchanged; no regex or expected answer was modified after the run.
- FINAL-060 asks for an unapproved archive tool; the current pipeline instead executes unrelated read-only `archive.list`, whose controlled adapter returns unsupported. This fails the expected-no-tool decision. No privileged write occurs, but unrelated available reads should not substitute for an unavailable requested integration.

Temperature0.35 and a single before/after inference pass are not deterministic. The41→38 literal difference, including the formatting false negative, cannot establish a statistically reliable causal regression. The correct conclusion is that this experiment supplies **no evidence of the intended generalization gain**. Wilson intervals describe this deliberately constructed sample and do not certify broad user-population accuracy. Calendar adapters always return immutable synthetic event data without independent requested-window/provider validation; broad/ambiguous expectations and lexical checks have limited outcome scope. Final language/model results must not be relabelled as real-world independently verified task completion.

## Timings and experimental limits

Startup and one neutral warmup are excluded. All sixty task timers measure actual controller/model response completion; they do not time independent provider/objective verification.

| Measured timing | Original | Final |
|---|---:|---:|
| Mean task latency,60 cases |1332.95ms|1330.86ms|
| P50 task latency,60 cases |1280.39ms|1350.58ms|
| P95 task latency,60 cases, nearest rank |2666.75ms|2727.85ms|
| P50 summed tool-model inference per case |1523.26ms,43 cases|1479.12ms,44 cases|
| P95 summed tool-model inference per case |2605.08ms,43 cases|2364.97ms,44 cases|
| Metadata retrieval P50 / P95 |1.185 /4.994ms|1.517 /7.651ms|

Inference sums measure only observed tool-capable model calls, excluding fallback/plain-chat and bypass cases. No all-task inference metric or time-to-verified-outcome metric is established. The current run had a reserved quiet interval; a during-inference sample recorded Windows11/Python3.12.10,24 logical CPUs,33.943GB physical RAM,4.6% CPU and92.4% RAM usage. The original run lacks an equivalent load sample; measurements are one-pass descriptive comparisons, not robust speedup claims. Controlled workflows also increased setup-inclusive P50/P95 latency14.070/751.395→33.192/783.586ms. Timings from the optional profiled suite are excluded.

## Security, regression, native and coverage evidence

The coordinator's final unprofiled full regression passes1057 tests,2 existing skips and17 subtests. The verifier parsed all1076 JUnit entries:zero failures/errors. All27 independent adversarial cases pass, including actor/confirmation/stop gates, no repeated failed writes, bounded safe reads, unknown/MCP outcome conservatism, calendar requested-title mismatch, privacy, corruption preservation, overflow, cancellation and inactive historical approvals. Historical failed-cycle artifacts are retained. This is scoped testing, not proof against every possible input. The forty-workflow runner supplies no unauthorized-sensitive-execution count and is not presented as forty measured zeroes.

Actual native Activity review passes95 assertions with42 independently opened Win32-framed screenshots at four physical sizes and observed125%DPI. Visual8.82/10, AI-template1.0/10; all171 runtime/config files plus executable/frontend hashes remained unchanged, aggregateSHA `534e106c1d8971235a281c18d6ceebf5b0f45cad56a0b09371cb46d0f66dde32`. Real final Windows read smoke passes4 original handlers without replacement; its runtime SHA matches. [Native evidence](m4-native-cycle-3.md), [adversarial evidence](adversarial-development.md) and [coverage matrix](observed-capability-coverage.csv) remain separate from model fixtures.

The172-capability matrix preserves its profiled development scope:25 observed registry-handler identities and147 without observed entries, from the disclosed earlier failed development suite. Final independent projection adds20 workflow capability-request identities,15 actual-model controlled-adapter identities and4 genuine Windows read successes in distinct columns. Production-code entry with injected dependencies is not live provider execution. No claim that all172 tools are functioning or live-tested is supported; voice hardware, external providers, screen analysis and many capabilities retain explicit evidence gaps.

## Publication and protocol integrity

The case/oracle/evaluator bytes remained private until both final runs completed and are now published at [evals/reliability/v2_final_holdout](../../evals/reliability/v2_final_holdout/README.md). Future work requires a new unseen holdout. Root/workers did not receive final queries/expectations during development. Exact-match checking found zero matches in preexisting repository evaluation queries; that is not a claim of model-training or semantic independence.

Raw Windows CRLF case SHA `84e492db6d9dcaa66023c100af6637f1b67dc47ecbd585384993b19d541784b9`; generated LF-normalized SHA `b1ccb0aa512a95f418582d7bc7814f096af6788be7da7f13e3bbd686ae433d25`. The original manifest used the latter without identifying newline scope; both hashes are now explicit. All sixty original fields match baseline artifacts. Oracle SHA `378f369023c0af6f289123fdbdbb3189b5ac43b66e4f774bae4c6306f81b61e2` is identical before/after. Local Git attributes preserve all five immutable input/evaluator files. Settings, original/final results, structural audit, summary and failure ledger are reproducible without altering expectations. No final expected answer, production runtime, configuration or frontend change occurred after final evaluation freeze.

**Acceptance:** bounded execution/security/regression/native checks PASS; unchanged historical routing/dev improvements remain DEVELOPMENT evidence; unseen quality target FAIL; broader semantic/live-provider/all-capability verification PARTIAL. The final overall status is PARTIAL, with the missing generalization evidence reported rather than hidden or tuned away.
