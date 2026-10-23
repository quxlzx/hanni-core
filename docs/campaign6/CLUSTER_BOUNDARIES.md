# Campaign 6 cluster and SSH boundaries

The engineering baseline is the current checkout, including the intentional
Campaign 4 and 5 repairs. No owner deployment, credential store, database,
model default, or independently managed process is changed by this campaign.
Live discovery belongs to the manager. The checks in this report exercise
original components using disposable deployment files and explicitly controlled
subprocess, socket, HTTP-client, process and clock dependencies. They establish
implementation behavior, not live hardware availability or GPU performance.

Before repairs, 19 scoped source and test files were archived in
`data/campaign6-cluster/original-source/source.zip`. The manifest SHA256 is
`79db0c14027e8048d58ccd405b8e34a443e3a1271f942389a5807a8183c3b522`;
the ZIP SHA256 is
`658fe1c7b6aff54ee4c475f9471b858aa634260a6c858c7db574e74132c08df5`.
The original Git HEAD is `0aede831853b6876bc8904838a41f7b2ce8f3967`;
the archive, rather than HEAD alone, identifies the actual uncommitted baseline.

The existing cluster, credential, deployment, power, terminal, compute registry,
performance and V3.7 verifier checks passed 136/136 in 27.213 seconds. The initial
command deselected the actual owned-subprocess timeout cleanup check pending
clarification of process ownership. After the manager confirmed that cleanup of
campaign-owned local helpers is permitted, that original check separately passed
1/1 in 0.621 seconds. No owner PID was used.

The new development controls were authored before any production changes.
The final baseline has 69 controls: 26 pass, 43 fail, zero errors or skips, in
0.765 seconds. The failures establish the following boundaries:

| Boundary | Failed controls | Actual original behavior |
| --- | ---: | --- |
| Resource response shape | 9 | Non-map JSON and malformed GPU containers raise untyped exceptions. |
| RAM accounting | 6 | Contradictory capacities or invalid values survive in advertised hardware; some authorize capacity. |
| GPU accounting | 9 | Invalid total/free/utilization values survive as a selected GPU row. |
| Cached source binding | 9 | Same-ID protected target/account/port/auth-path changes reuse earlier address, tunnel, resource or credential state. |
| Current telemetry freshness | 3 | Samples aged 7, 30 and 180 seconds still appear current, including uptime and process readings. |
| Process RAM percentage | 1 | A process RAM value above 100 percent is accepted. |
| Context proof source binding | 3 | A stored synthetic context proof survives replacement of the protected SSH target/account. |
| Health/resource source binding | 3 | Earlier health and resource observations represent the replacement target. |

Controls preserve exact configured GPU UUID matching, unknown-device exclusion,
valid RAM/VRAM and caching, fresh telemetry, multicore process CPU above 100
percent, display-only name changes, strict host checks, noninteractive SSH,
verified Tailscale fallback, roster-only Tailnet projection, generic safe error
messages, pre-dispatch cancellation, request-scoped cancellation, owned-object
cleanup, heartbeat expiry, and unchanged deployment bytes. Generated
credential-shaped test values remain in memory; receipts never include them.

The first 48-control run also had three fixture teardown errors: the injected
cleanup dependency ended before the disposable transport fixture closed. That
run remains preserved. Making the fixture depend on the original monkeypatch
lifetime removed those errors without changing the 37 production failures or
11 passes. Expanded 62- and 69-control receipts are separate, never substituted
for the earlier run.

The independent verifier sealed a private 22-case scheduling set before repairs
and independently reproduced 24 exposed boundary controls on unchanged source:
4 pass, 20 fail, zero errors. Its final inputs and oracles remain private and
are not used for engineering. Production repairs require manager authorization
after this independent reproduction.

Machine-readable original evidence is
`data/campaign6-cluster/PRE_REPAIR_EVIDENCE.json`, SHA256
`2988c23739312b51a1db6a24f6f81905e4ba42e53f70e313d849b73a6b37f512`.
It contains case identifiers, outcomes, timing, XML digests, and original/current
source hashes. It deliberately excludes raw provider data and credentials.

Reproduce the current controls from the workspace with:

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest -q tests/integration/test_campaign6_cluster_boundaries.py --junitxml=data/campaign6-cluster/controlled-new-run.xml
```

The recorded baseline receipts are immutable evidence; subsequent runs use new
output paths. Live SSH authentication, hardware identity and inference claims
are reported separately by the manager, using actual admission and discovery
receipts.

The manager authorized repairs only after the verifier independently reproduced
the failures. `InferenceTransport` now projects typed, consistent RAM/GPU
measurements and keeps invalid or unavailable capacities unknown. It binds
address, tunnel, resource, authentication and runtime-file caches to the exact
protected node/account; worker port and authentication source additionally bind
the relevant caches. A changed binding closes only the old owned forwarding
object and withdraws its cached credential. Closing the disposable transport
clears retained credentials and measurement caches.

`ComputeRegistry` now includes protected remote address/account and configured
authentication source in its runtime identity. A changed source withdraws current
health, resource and context observations. Valid display-name changes preserve
the same runtime identity. Invalid or missing protected deployment also withdraws
current observations; restoring a replacement node cannot inherit the earlier
health. Durable proofs and history remain untouched and cannot authorize a
different source. The registry exposes the original `resource_sampled_at` for
the scheduling worker's separate freshness gate.

`ClusterMonitor.snapshot` clears current CPU/RAM, uptime and process claims once
the existing six-second stream stall bound expires, including future timestamps;
graph history remains intact. Interrupted streams no longer claim telemetry as
the availability source. Process RAM is bounded to 0 through 100 percent, while
multicore process CPU may exceed 100 percent.

Two follow-on failures were reproduced before repair. Explicit numeric GPU device
zero was treated as absent on the Strata single-GPU path. Because the original
resource sampler supplies UUIDs without ordinal identity, zero and string zero
now remain unknown; no index mapping is invented. Explicit UUID selection and
the genuinely unconfigured single-GPU Strata path retain their existing behavior.
Removing or malforming deployment and then restoring a changed account also
retained earlier health/resources. Clearing current observations on authority
loss repairs this path without touching durable proofs. Both failures and the
independent positive controls remain preserved.

The first repair run had 204 passes and two compatibility failures out of 206:
callers expected a registered observation mapping to remain after invalidation.
Retaining an empty mapping fixed those failures; the same 206 checks then passed
in 28.723 seconds. Later controls added exact freshness boundaries, durable-proof
byte preservation, timestamp projection, cache cleanup, unsupported GPU-index
controls and authority reintroduction. All 81 cluster development controls passed
on that repaired implementation; later request-boundary controls are separate.

The resource freshness gate exposed older scripted fixtures that advertised
capacity without a sampling timestamp. The 504-case related run remains recorded
as 471 pass / 33 fail, not a pass. The manager explicitly authorized only
timestamp metadata changes in `tests/unit/test_adaptive_model_routing.py`,
`tests/unit/test_v44_controlled_regressions.py`, and
`scripts/campaign5_intelligence/controlled.py`. They use each fixture's existing
logical clock at the measurement/observation boundary. Exact before bytes are
archived in `data/campaign6-cluster/fixture-metadata-before`; AST comparisons
verify that assertions and all behavior apart from this metadata are unchanged.
The verifier owns the same timestamp-only correction in its independent
`test_campaign5_verification.py`. Prior Campaign 5 source freezes, reports,
private cases and oracles remain historical and untouched.

The first corrected related run has 505 passes / one failure out of 506 in
69.881 seconds: a CPU-only fixture explicitly re-observed capacity after a GPU
configuration change but omitted the timestamp on that new observation. The
same approved timestamp-only correction covers that observation and its paired
missing-VRAM negative control. The full V4.4 module then passed 22/22 in 1.149
seconds. The clean cycle-2 related repeat passed **506/506**, zero errors or skips,
in **71.731 seconds**, recorded in
`data/campaign6-cluster/final-relevant-clean.xml`. This includes the 81 new cluster
controls, the 137 original cluster/compute checks, and related adaptive,
collaboration, performance, V4.4 and Campaign 5 controls. The checks overlap
earlier suites; their counts must not be added as distinct observations.

Independent cycle-2 development verification passed 38/38 in 6.201 seconds,
and its prior Campaign 5 module with corrected metadata passes 61/61 in 10.343
seconds. These are implementation checks with controlled dependencies. They
prove no live model quality, remote authentication, GPU throughput or verified
128K context. The original 8K-stage growth API compares its input-only proof to
the next stage requirement; an 8191-input-plus-one-output allocation does not
meet an 8192-input growth prerequisite. No allocation threshold or proof design
was changed. Live progressive context testing remains subject to original
authentication, resource and genuine identity/accounting admission.

The public machine-readable checkpoint is
`docs/campaign6/CLUSTER_EVIDENCE.json`, SHA256
`97d6c652c12961b26e8c3d93b149b9fa561d7c669aba3089adfa22b091837999`.
It derives every run denominator and case identifier from XML, preserves failed
cycles and exact source provenance, and records timestamp-only fixture AST
checks. Final source hashes are:

| Production source | SHA256 |
| --- | --- |
| `src/hanni/compute/transport.py` | `d6f30ea100282e94eadd806ba1753e95ae7751cc58bd1aa57732140a0c0a3ff0` |
| `src/hanni/compute/registry.py` | `d970cbdc32e0870ed69901ef1aec51b01d2a2820b6ebab6ea0ce81f83749b1c5` |
| `src/hanni/dashboard/cluster.py` | `5e935fc4849d50e3b532eb2327d488f4f48ffc13539eb61db4ce7b6bdec38ef9` |

The scheduling worker independently owns `src/hanni/compute/scheduler.py`, SHA256
`50a2efaf60087d68434e67a2f328ecdfef817b53d09c37d16451d9993c63daf6`.
That source is included in the related regression runs; its development and final
scheduling outcomes belong to its separate report. The verifier's private
once-only scheduling set remains pending and cannot guide further tuning.

After the cycle-2 checkpoint, independent tests exposed two request races before
private final execution. Changing the protected node/account after endpoint
resolution forwarded the replacement account's credential to the earlier
endpoint. Changing authority after the secure credential read also allowed a
request to proceed. Both independent controls failed on transport SHA256
`1b435529e2553831da89cd19469bc15c633024704104be48792df296ae0d93dc`,
with zero real network or SSH activity. Synthetic tokens existed only in memory;
the receipts contain boolean observations, never token values.

The authorized repair copies the input worker, captures its protected node and
source binding, and reads authentication only from that captured node. It checks
current worker/node authority after endpoint resolution, after authentication,
before HTTP dispatch and before result return. A mismatching known owned tunnel
also rejects the request. These checks preserve the existing endpoint API,
request-scoped cancellation, local synthesized supervisor compatibility and
parallel HTTP requests; no global inference lock was added. Exact before bytes
are archived in `data/campaign6-cluster/credential-race-before/source`.

A follow-on independent test then changed either the global enabled flag or the
registered worker's enabled flag during endpoint resolution. Both changes still
allowed an HTTP request; two already-disabled passive-health controls passed.
The four-case receipt preserves those two failures and two positive controls on
transport SHA256
`a4605f5efb499d3f7494cdce0bb903f8da43f9a0c54abeb2a7bae608b4976a76`.
The minimal repair captures both initial flags and rejects their change at the
same request boundaries. It keeps passive health for an initially disabled,
unchanged source. It does not duplicate scheduling privacy or model-selection
policy. Exact before bytes are archived in
`data/campaign6-cluster/authority-transition-before/source`.

On the final held source, **143/143** focused checks pass in **7.014 seconds**:
97 engineering cluster controls and 46 independent exposed controls. The
separate independent retake passes **46/46** in **6.944 seconds**, with its source
checkpoint SHA256
`b39062b678d57b850a6230bc74e7b291c82719d66dedb75bfc8c06f8f4fa69fa`.
The necessary 19-file regression repeat passes **522/522**, zero errors or skips,
in **71.737 seconds**, at
`data/campaign6-cluster/credential-final-relevant.xml`. It uses the same source
hashes listed above and includes the 97 engineering controls plus the original
and related adaptive/compute/cluster suites. The independent Campaign 6 module
is separately measured, rather than included in that 19-file denominator.
Commands, XML hashes and case identifiers are recorded in the public evidence.
Overlapping suites must not be added as unique observations.

The intermediate 170/170 credential-focused run collected the then-current
42-case independent module. Its source and receipt remain historical: it does
not certify the four enabled-transition controls subsequently added to the
independent module. The earlier 506/506 result likewise belongs to the earlier
transport source. Both are retained, alongside every failing repair cycle, in
the current evidence and historical checkpoint metadata.

The manager's two bounded live discovery rounds found all eight active roster
nodes online in Tailnet and reachable on their Tailscale SSH ports, with fresh
SSH authentication required on all eight. These are manager observations,
not independent hardware or inference passes. Yunjin remains the configured
maintenance node. No live serving, throughput, peak VRAM or context-retrieval
quality is inferred from these controlled repairs. Owner processes and model
defaults remain untouched. The source, helper and test implementation is held
after this checkpoint; final manager and independent checks follow the freeze.
