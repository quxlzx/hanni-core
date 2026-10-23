# HANNI V4.1 collaboration

V4.1 adds bounded model collaboration to evidence analysis in the existing V3
workflow engine. HANNI Core still owns tools, approvals, dependencies, invocation
receipts, recovery, and final outcome verification. The original primary model
and configured inference endpoints remain in place.

## Using Workflows

In **Workspace → Workflows → New goal**, choose the model analysis preference:

- **Automatic** uses collaboration only when measured paired results justify it.
- **One model** retains existing adaptive inference behavior.
- **Independent comparison** requests independent analyses from eligible models.
- **Specialist analysis** partitions declared verified sources into separate tasks
  when distinct eligible models have sufficient measured category evidence.
- **Independent review** asks a second model to inspect a first model's report.

The preference belongs to the submitted workflow. It is separate from the
autonomy mode and cannot grant tool access or expand sharing permissions. Review
the saved plan as usual. If eligible secondary models are unavailable, analysis
can retain a single-model path and record the reason.

The existing workflow detail displays participant assignments, actual states,
inference duration, output summaries, returned output, model identity,
verification, disagreements, selected result, and final evidence. Missing usage
or timing remains unmeasured. These rows are saved receipts; a closed controller
does not make historical activity live.

## Authority and privacy

Every remote dispatch still crosses the protected compute registry, endpoint
eligibility checks, and the original workflow admission guards. Recalled LAYA
memory, private files, screen data, credentials, and conversation scopes cannot
be relabeled synthetic by a model or a dashboard preference.

The current remote workers allow synthetic data only. Private workflows
therefore stay on eligible local inference unless a separately authorized
existing sharing policy permits their full context. This implementation does
not broaden those policies.

Independent model review is advisory. Agreement, confidence, model size, and
majority votes do not prove correctness. Final verification must use declared
source data, original verified tool results, and deterministic acceptance checks.
An unresolved conflict retains an unverified outcome.

The workflow verifier establishes cited observations and supported deterministic
calculations. It does not prove arbitrary code correctness, historical causes,
or free-form conclusions. Specialist source groups are checked individually and
their merged report must satisfy the original whole-step criteria. A cross-source
calculation that these groups cannot establish remains unverified. Insufficient
specialist evidence falls back to independent comparison or one eligible model.

## Bounds and measured policy

One comparison uses at most three distinct endpoints, two concurrent inference
requests, two rounds for independent review, and 8192 total admitted output
tokens. Endpoint assignments are pinned and rechecked, so a failed secondary
cannot silently turn into a duplicate opinion from another model. Individual
output and serialized participant receipts have separate retention limits within
the original workflow envelope. Raw selected output is retained once per
participant, and final result persistence retains the original size limits.

Automatic collaboration currently requires at least five identity-bound paired
evaluations, a net gain of at least two correct outcomes, and aggregate latency
no more than three times the single-model baseline in the router's task category.
Losing or insufficiently measured categories prefer single execution. Specialist
assignment additionally uses the V4 threshold of at least 20 graded category
samples and a 95% Wilson accuracy lower bound of 0.7. Model labels and parameter
counts are not role evidence.

Comparison evidence is an engineering-only, idempotent API with a bounded history
in the existing protected routing database. The UI cannot import evidence. This
validation run has not imported a category benefit or enabled automatic
collaboration.

Pause, Stop, revoked approval, timeout, and detach withdraw further admission.
Partial progress stays inside the original fenced invocation and checkpoints.
After restart, unfinished participants are marked interrupted in both the step
and invocation; the original recovery rules govern resumption. Model output
never becomes an action approval or a retry grant.

## Deployment and reruns

The packaged release is `hanni 0.11.0`. The existing controller attachment installs
the collaboration helper alongside adaptive routing; the original startup
commands and worker definitions remain valid. Rebuild desktop assets with
`npm run build` in `frontend` and use the normal HANNI startup when desired.
This implementation did not launch HANNI Core.

Validation scripts are in `scripts/v41_verification`. `sealed_protocol.py` seals
the task set before inference, `single_baseline.py` grades actual primary responses,
and `paired_live_eval.py --seal` seals the supplemental three-mode comparator
before its paired run. That comparison includes the fixed primary, original V4
sequential verified fallback, and V4.1 parallel execution with the same tasks and
oracles. It requires existing healthy endpoints, current runtime-bound capability
receipts, fresh resources, and original sharing/SSH authorization. An unavailable
resource or authentication check blocks dispatch; it is not bypassed for a score.

Use new protected output directories under ignored `data/v41-verification` for
each run. Helper sessions must retain ownership receipts and verify their own
cleanup, preserving unrelated servers. Never publish private endpoint settings,
model responses containing private context, or credentials with evidence.

## Validation

Implementation checkpoints and benchmark evidence are recorded in
[V4.1 checkpoints](HANNI_V4_1_CHECKPOINTS.md). Final regression and benchmark
acceptance are documented in the [benchmark comparison](HANNI_V4_1_BENCHMARK_COMPARISON.md)
and [independent review](v41-reviews/INDEPENDENT_REVIEW.md).

The full regression passed 1908 tests with two skips and 25 passing subtests; a
final recovery correction and late specialist integration test passed a further
104 focused checks. The independent security audit passed 29/29, the final browser
review passed 12/12, and the manual visual score was 8.8/10. The package passed
archive/source/font/privacy verification.

Real multi-model performance acceptance is blocked by fresh Athena SSH/resource
access. No benefit is demonstrated and automatic collaboration remains disabled.
The local helper was stopped; authenticated cleanup of two temporary GPU helpers
failed, so their remote shutdown remains unverified. The benchmark report includes
their ownership reconciliation procedure and the remaining expiry-guardian
installation gap. These limits are not hidden by the controlled test results.
