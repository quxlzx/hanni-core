# Campaign 6 independent verification

The independent exposed-development checks pass 46/46 on the held repaired
source. This includes the credential-binding race found before final freeze
and the enabled-transition guard, with original failures preserved.
Actual SSH authentication and hardware/model serving remain blocked. This is
an implementation result with controlled dependencies; it does not establish
working distributed GPU inference or verified large-context capacity.

The verifier sealed 22 new private scheduling cases at
2026-10-10T10:33:52.226124+00:00, before production repairs. Each of the eleven
requested scheduling families has two cases. Private inputs, author code and
oracles are separate from execution and are not shared with engineering.
After the manager's explicit source freeze and quiet-run authorization, the
complete sealed final ran once: 19/22 strict passes, zero harness errors, ten
controlled HTTP requests and complete owned cleanup. The private claim is
closed. No case, oracle or grade was changed or retried.

| Private seal | SHA256 |
| --- | --- |
| Inputs | `77672a471be52e1dadc7e4d8593856f569dd9cc594c6921bf24ed7d9e73dd18e` |
| Oracles | `bfb1f432a4833b9d3a27508e2a5aa812c39d4d021fc18f50d1fce94900ad4fc2` |
| Protocol | `96e71356ac1c48ba6acf6c62df50148f2e425fe8349d4bee7abb46582412f23c` |
| Seal receipt | `08e8991550b3b0d21a95b365350ec7b8a3ce840b9836303e6a454a44ed9dc200` |

The baseline is the actual current checkout, preserving earlier uncommitted
Campaign 4 and 5 changes. The manager's pre-edit discovery archive contains
the four original files used for the independent failure proofs. Its archive
SHA256 is `6126acba8bbadcad3bb248131a016989090d3f687fc6cc0d4f2afc1ca62c51d9`.
The verifier's `data/campaign6-verifier/SOURCE_READY_CYCLE3.json` identifies these
original bytes and the repaired source, test XML and public helper hashes.

The corrected original 24-case boundary run had four passes and twenty
failures, with zero harness errors. It independently reproduced malformed
resource exceptions, internally contradictory RAM/GPU measurements, reuse of
address/resource/auth caches after protected target changes, expired cluster
readings displayed as current, process RAM above 100 percent, stale capacity
admission after a fresh heartbeat, and context/health proofs surviving a
protected SSH target or account change. Positive controls preserved valid UUID
capacity, an unknown GPU's exclusion, fresh metrics, multicore process CPU
above 100 percent, and display-only identity changes.

Additional exposed tests independently proved that retained context proof
could override a smaller configured allocation. The original scheduler both
selected such a worker and sent an actual owned-loopback HTTP request exceeding
the allocation. Another control proved that explicit Strata GPU index zero
fell through to the implicit single-GPU association despite absent ordinal
evidence. Both are repaired, with the no-device Strata single-GPU positive
control retained. The exposed suite first passed 35/35, zero errors/skips,
in 6.702 seconds (`exposed-cycle2-corrected.xml`). Its original HTTP transport
and original file-read/cited-report verifier controls test truthful acceptance
and rejection, queue cleanup and observed concurrent requests. A further
independent pair then proved that missing/malformed protected deployment
followed by restoration under a different account could retain earlier healthy
capacity. Clearing current observations on authority loss repaired both
failures; an identical valid reload still preserves current observations. The
updated suite passed 38/38 with zero failures/errors/skips
(`independent-final-development.xml`). Durable proofs remain unchanged.

Before final freeze, two independent request-boundary controls proved a further
credential-binding defect on transport SHA256
`1b435529e2553831da89cd19469bc15c633024704104be48792df296ae0d93dc`.
If the protected account/address changed after endpoint selection, the original
request forwarded the replacement account's credential to the previous
endpoint. A change during credential reading also allowed dispatch under
withdrawn authority. Both controls failed without harness errors
(`credential-race-before.xml`), using random synthetic credentials retained
only in memory and controlled HTTP leaves; no actual SSH or network ran.
The candidate captures one protected worker/node binding and rechecks it at
endpoint, authentication, dispatch and response boundaries. Two additional
independent controls confirm that a stable response remains accepted and a
response after source withdrawal is discarded (`credential-result-candidate.xml`).
This pair ran on the repaired candidate and is not another pre-fix proof.
The original failures remain immutable. The complete updated suite passes
46/46 with zero failures/errors/skips in 6.944 seconds on transport SHA256
`d6f30ea100282e94eadd806ba1753e95ae7751cc58bd1aa57732140a0c0a3ff0`
(`independent-final-development-cycle3.xml`). The later private final ran
against these held bytes after the complete source freeze.
Four further controls isolate enabled-state semantics: changing the original
global or worker enabled flag from true to false during endpoint preparation
still dispatched on the first candidate, whereas passive health of an
already-disabled global/worker configuration correctly remained allowed
(`authority-transition-before.xml`: two failures, two passes, zero errors).
The authorized follow-on guard compares captured initial flags with current
flags. Both transition negatives and both unchanged disabled-health positives
pass in that updated full suite. The guard preserves unchanged passive health
and does not duplicate scheduler privacy/model policies.

The new mandatory remote sampling timestamp exposed older controlled fixture
metadata omissions. With manager authorization, one bootstrap wrapper in
`test_campaign5_verification.py` now supplies the original isolated registry
clock. Every original withdrawal value, assertion and oracle is unchanged.
Exact before bytes are archived; the current 61-case revalidation passes
(`c5-timestamp-fixture-revalidation.xml`). Campaign 5 private inputs, final
results, archives and seals are unchanged. This is current Campaign 6 fixture
migration, rather than another Campaign 5 final run.

Failures in the verifier's first proof-call signature, a missing acceptance
criterion field and short public HTTP/barrier timing assumptions remain in
their predecessor artifacts. They are harness limitations rather than product
defects. The generic barrier now observes the declared overlap within a bounded
two-second deadline. Separate public adequacy tests use a one-second queue;
sealed private budgets and expected outcomes remain unchanged.

Independent live confirmation used the original strict SSH/Tailscale path for
Hanni and Wonyoung, with at most two concurrent probes and twelve-second
command deadlines. Both LAN TCP checks timed out; both Tailscale TCP checks
connected. The original SSH failures explicitly requested a fresh check.
Neither node authenticated, and host verification did not complete. No
hardware, GPU assignment, loaded model, inference throughput, latency, peak
VRAM or current context capacity was measured. Only sanitized evidence flags
and stderr hashes are retained; login URLs and raw stderr are discarded.
The protected deployment/context bytes and original connection source remained
unchanged (`live-confirmation-01/RESULTS.json`).

The manager separately observed eight active Tailnet peers and a repair node,
three configured workers and zero authenticated/healthy workers. Snapshot
model/context fields may originate from historical retained proofs; they are
not a fresh loaded-model or verified-capacity observation. Protected-source
identity changes safely invalidate incompatible historical proofs without
rewriting owner proof files or replacing them with controlled evidence.

One exposed capability limitation remains unresolved: with total allocation
8192 and the required minimum one output token, an actual prompt proof can be
at most 8191, but the original launch-growth preflight requires prompt proof
at least 8192 before increasing to 16384. A controlled original preflight
reproduced this rejection with one occupancy-check leaf and zero launches
(`progressive-growth-before/RESULT.json`). Prompt proof and total allocation
must remain distinct. The current campaign does not claim progressive context
serving or alter this threshold, start services, or grow owner allocations.

A fresh independent process/listener receipt confirms that the existing model
and launcher PID, creation time, parent and command hashes match the manager's
baseline; listeners and models.yaml are unchanged. The resident health endpoint
is healthy, which does not establish resource admission or context proof
(`runtime-before-final/RESULT.json`). The verifier did not launch/restart HANNI,
change any owner database/configuration, or dispatch model generation.

The final source archive contains 489 files. The verifier checked each current
file and archived member, archive membership, source membership and protected
owner configuration before every case and after the run. The manifest SHA256
is `bf6b2d88f3cf4c3454291090870f009916c90e0bd3307ec4f1b0013da6041316`;
the archive SHA256 is
`41fbbdcdadca66ada33569431eb85f1b2d25395cf17b16dcfcd8aeb1a0e37579`.
A fresh private Python cache was used. Source and private seal remain unchanged.
The machine-readable [final holdout](FINAL_HOLDOUT.json) identifies exact raw,
grade, closure and freeze evidence without publishing private answers.
The [verification receipt](VERIFICATION.json) binds independent artifacts,
source readiness, runtime preservation and the accepted manager report hash.

| Scheduling family | Strict final passes |
| --- | ---: |
| Correct worker selection | 1/2 |
| Worker unavailable | 2/2 |
| Worker busy | 2/2 |
| Context too large | 2/2 |
| Insufficient VRAM | 2/2 |
| Multiple eligible workers | 2/2 |
| Parallel tasks | 1/2 |
| Queue saturation | 2/2 |
| Safe reassignment | 1/2 |
| Network interruption | 2/2 |
| Result verification | 2/2 |

Three strict nonpasses remain. Manual explanations are separate from the frozen
automatic grades and do not promote any result:

| Case | Independent manual classification |
| --- | --- |
| C6F-02 | Authored ranking expectation conflicts with the original active-slot penalty; the original policy prefers the idle eligible worker. No untrusted worker was selected. |
| C6F-14 | One serialized request completed; the other remained blocked after the sealed 0.2-second queue budget. Only one controlled HTTP request was dispatched. |
| C6F-17 | The first controlled endpoint disconnected; the common sealed queue budget expired before reassignment. One attempt and one controlled request were retained, with no second dispatch. |

These timing observations establish bounded rejection, not proof of reliable
delivery within the short budget. No additional run or final-oracle tuning was
performed. All 22 cases close their providers, scheduler and original registry;
all owned reservations, waiters and in-flight bookkeeping release. The
preexisting fixture reservation in the queue-full case remains unchanged
rather than being erased by cleanup. The two result-verification cases use an
actual original read of an owned file and the original cited-report verifier:
one supported calculation is VERIFIED, and the unsupported claim is FAILED.
These controls do not establish real model quality or a distributed workflow's
physical execution.

The final public development revalidation is 69/79 with 79 complete receipts
and zero harness errors; its separate adequate-budget supplement is 10/10.
The earlier 68/79 run with one overlap harness error remains intact. The extra
parallel-overlap pass is timing/admission variation, not evidence of benefit
from the credential repair. The independent 46 checks, engineering 97 checks,
related 522 regressions and 56 scheduling contracts overlap and must not be
summed as unique tests.

A final independent read-only runtime receipt again confirms original model
and launcher identity, listeners and model configuration, with a healthy
resident endpoint and zero generation requests
(`runtime-after-final/RESULT.json`). The protected source/archive check also
still passes. Hardware and model-quality acceptance remains BLOCKED by actual
SSH authentication; scheduling acceptance remains PARTIAL at 19/22. Native
throughput, P50/P95 inference latency, peak VRAM and live workflow success stay
unmeasured. No claim of live distributed inference or progressive context
serving is made.
