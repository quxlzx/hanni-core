# Campaign 4 checkpoints

## Initial baseline and prospective seal

- Original production baseline: `0aede83`.
- Original regression suite: 346 passed, zero failures/errors/skips, 29 test
  files; JUnit duration 59.479 seconds. Raw command, log and XML are under
  ignored `data/campaign4-manager/`.
- Boundary baseline: twenty of twenty-two native checks passed. Two newly
  reproduced development failures concern pause/cancel at persisted
  pre-dispatch admission: the handler is not entered, but exception handling
  replaces the requested control outcome with `blocked`. Independent
  reproduction is required before production repair.
- Untouched independent set sealed before tuning: forty cases, exactly two
  in each requested category. Inputs and answers remain private and separate.
  Cases SHA-256: `a931a16a4c01b4fe19f183be68367d11d68c16641212164e962fc580557e7cf2`.
  Oracles SHA-256: `bde5a797735e3a051f8927c3244fc99023360ab018d6cb43af3cccb5168cf764`.
- Six new prospectively annotated native-model planning attempts were refused
  by original model admission, with zero generation HTTP requests. Available
  RAM was approximately 1.05–1.35 GB; semantic goal/plan accuracy is unmeasured.
  The existing model, configuration and owner processes were preserved.

Actual engineering agents own the development corpus/store verification and
native service boundary/restart tests respectively. A separate actual verifier
owns private independent cases and repair reproduction. Direct-store probes
will remain separate from native scheduler coverage. No production repair had
been made at this checkpoint.

## Control repair and independent verification

The verifier independently reproduced pause/cancel at pre-dispatch against
original source, with zero handler entries. The service-only repair preserves
requested control settlement after retaining the receipt. Native boundary
checks improved from 20/22 to 22/22; the unchanged independent comparison
improved from 1/3 to 3/3. Synchronous parallel calls remained visible until
return in subsequent boundary checks.

Review then exposed a continuation gap: `paused` plus a still-valid scope could
resume or explicitly retry a safe read despite a separate uncertain write.
Independent probes demonstrated an actual subsequent managed write in each
case. The second service repair requires all dispatched/uncertain invocations
to be reconciled before resume or retry, and applies the same gate to UI
controls. Native checks passed 27/27; independent continuation comparisons
passed 2/2 with zero subsequent writes. Evidence retains both pre-fix and
post-fix source hashes.

## Corrected archived-original development baseline

The prospective development corpus contains 120 cases, six per category;
SHA-256 `fa167f0a69b059c3ff6320a6d813f6eb8d6f6754447cd7648a5ef54862285db5`.
All 192 original HANNI Python modules were archived before production repairs.
After correcting fixture contract errors, the archived original engine scored
114/120 with zero harness errors: 102 native scheduler scenarios and eighteen
direct-store scenarios. All 65 dynamically enumerated allowed store edges
passed separate stale-CAS rollback and valid-transition readback probes.

Six original-oracle failures remain recorded. One is an objective-retention
failure involving substituted source data. Five assume retry/recovery for
`file.read`, whose actual registered metadata declares it not retry-safe.
Those five are descriptor eligibility/oracle conflicts, not evidence for
enabling prohibited retries. They are not silently regraded. New eligible
retry/recovery and parallel-overlap supplements will be sealed before running.

Baseline eligible outcome denominators were preserved: completion 32/34,
recovery 7/10, cancellation 7/7 and partial completion 15/15. The baseline
write ledger recorded nineteen handler entries and sixteen actual effects,
with zero unauthorized entries/effects and zero duplicate consequential writes.
Early fixture failures and the Windows launcher-PID assumption error remain
retained separately from corrected native-engine results.

## Provenance correction and extended verification

The manager's source-origin audit found that the development engineer's archive
contained the first service repair. Its old traces remain immutable and are
identified as intermediate snapshots in `PROVENANCE_ERRATUM.md`. Development,
eligible retry/recovery supplements, protocol probes and transition faults were
rerun against the manager's genuine pre-edit archive. Imported package paths
and all 192 source hashes were pinned before/after, including original service
SHA-256 `4bd6e5f0cdcc1659523329bfcba96fe1d61c0d386e27942b835dbba4669fe9a2`.
Corrected true-baseline scores were still 114/120, 5/5 eligible supplements,
7/10 protocol controls and 65/65 after-projection transaction rollback probes.
No original oracle changed.

The reference repair changes only type matching: a large bounded JSON integer
is no longer converted to float for unrelated type checks. Protocol controls
improved from 7/10 to 10/10; independent controls improved from 3/6 to 6/6.
Boolean/integer distinction and finite-number rejection remain intact.

Independent original-source objective probes scored 1/3. Both substituted
plans were explicitly reviewed, so these are objective-retention failures,
not unauthorized reads. Planner source consistency now blocks substitutions
before handlers run while preserving valid original paths and verified typed
references. Independent unchanged objective probes improved to 3/3. A new
continuation false rejection was corrected through general path/clause syntax,
with additional prospective controls rather than a phrase-specific override.

Ten new native local-analysis probes scored 8/10 against the genuinely original
service and 10/10 after the control repair. These exercise cited calculations,
report save/readback, false citations, malformed/oversized/nonfinite outputs,
timeout and in-flight pause/cancel. Controlled model replies establish engine
contracts; actual semantic model quality remains unmeasured. Earlier manager
analysis runs that accidentally selected current or intermediate source remain
retained and are excluded from original-baseline claims.

An independently authored real process-restart challenge completed five
verified steps with six invocations, including one controlled safe-read worker
failure. It retained the first verified read's original invocation identity,
required explicit resume, performed exactly one report write, and passed
fourteen independent audit checks. A checker assumption about Windows newline
serialization remains recorded separately from the corrected text/artifact
verification.

## Source readiness and final corpus audit

The final boundary candidate passes 66 checks: 54 new service/source/compute
checks and twelve existing model-context checks. Eight compute checks use real
owned loopback HTTP connections and original compute components; their response
content is controlled, not live model inference. Fresh owned-runner challenges
verify five completed steps with six invocations and no completed-step replay.
Separate before-effect and after-effect process crashes retain an uncertain
write and refuse continuation. All six helper identities have exited.

The manager repeated the 346 existing regressions successfully before the final
parser adjustment; another whole-source frozen run is required. Six additional
native model planning attempts remain resource-blocked, with zero generation
HTTP calls. Separate original-selector inspection excludes the configured
choices solely for insufficient RAM reserve: available RAM was approximately
1.66-1.70 GB, below the original 2 GiB reserve. Model and launcher identity and
health stayed unchanged. Twelve total attempted planning diagnostics do not
establish actual goal understanding or plan quality.

The corpus audit exposed additional original authoring conflicts: twelve
intended multi-source execution graphs name only the first read source in their
goal. Three other multi-source rows intentionally test invalid admission. The
original 120 cases and their scoring denominators remain unchanged. A separate
new exposed development supplement names both sources explicitly; it is not an
untouched test set and cannot replace the original scores. The source guard is
not weakened to admit the malformed positive plans.

## Whole-source frozen implementation cycle

The final freeze pins 288 implementation, configuration, helper, regression-test
and prospective-input files. Manifest SHA-256:
`f7f3ef6ca9a9772223b0a3dd2a0947826e4f7b942f43a5bce53e2c36eda42e49`.
Archive SHA-256:
`09de198ca6101c7cc1699464f1d1242d1fb0ed31ead88aa5c5524951cb17bf08`.
Derived scores and documentation other than the protocol are outside this
freeze so reports can be published without changing tested inputs or code.

The manager's frozen regression run passes 346/346 existing tests across 29
files in 61.261 seconds, with no failures, errors or skips. The frozen new suite
passes 104/104 checks, including the verifier's two uncertain-write subtests,
in 40.006 seconds. All source hashes remain unchanged.

Engineering and independent public reruns agree exactly: unchanged original
corpus 103/120; eligible retry/recovery/parallel supplement 5/5; explicitly
named multi-source supplement 12/12; reference/schema controls 10/10; dynamic
checkpoint rollback faults 65/65; local-analysis supplement 10/10. All have zero
harness errors. Five original descriptor/oracle conflicts and twelve original
goal/plan authoring conflicts remain scored failures; none is regraded.

An additional frozen-source native planning round makes eighteen total
attempts across the same six prospective goals, with zero generation HTTP
calls. Final available RAM is 1,721,548,800-1,833,721,856 bytes; the sole native
selector exclusion remains `insufficient_ram_reserve`. Model and parent
process identities, health, memory/LAYA settings and model generation defaults
match the initial baseline. No reserve bypass, owner process interruption or
configuration change occurred.

The independent restart challenge again passes fourteen audit checks under
the exact final freeze. The once-only forty-case holdout has executed without
fixture errors: 32/40 whole-case pass, 11/15 expected verified completions,
1/2 expected completed restart recoveries, 2/2 cancellations and 2/2 checkpoint
readbacks. Its sixteen observed sensitive dispatches and sixteen consequential
write effects have zero unauthorized operations and zero duplicate effects.
Code, inputs and oracles remain unchanged. Eight failures stay in the score;
the independent final report records their classifications without repair or
holdout-driven tuning.

## Final independent review and repository closeout

Independent manual review checks forty of forty raw receipt hashes and all
sixteen invocation/authority-bound original effects. Four failed expectations
conflict with the non-retry-safe read descriptor; four remaining stopping,
menu or input-boundary limitations remain reported. No grade is promoted.
Fifteen original effect hashes persist; one declared pre-verification tamper
correctly becomes UNVERIFIED. Successful cancellation has zero later original
handler entries. All fourteen exact final/challenge helper identities and
their receipt-identified launchers have exited.

The final helper-compatible original rerun reproduces the same 114/120 score,
5/5 eligible supplement, 7/10 reference controls and 65/65 transaction faults.
It pins the true archived original package plus the same thirteen public helper
files used for the candidate. The final report uses this comparable run's
native duration P50 125 ms/P95 203 ms; earlier timing receipts remain retained.

All 288 frozen implementation/input/configuration hashes remain unchanged.
An isolated temporary Git index checks all 57 task files with a clean cached
whitespace check and exact-byte JSON corpus comparison. The actual repository
index is unchanged; private raw evidence and unrelated owner files are excluded.
Reports document partial acceptance, rather than a complete production or
model-quality pass. No commit or owner deployment has occurred.
