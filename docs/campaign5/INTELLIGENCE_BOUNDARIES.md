# Campaign 5 native intelligence boundary review

This audit exercises the original adaptive router, collaboration, compute
context bootstrap, and local client. All observations and provider responses
in this worker's tests are controlled dependencies. The HTTP/SSE tests use an
actual owned loopback server and the original SDK; they do not run a language
model. Actual discovery, development response comparisons, and the sealed final
evaluation belong to the manager and independent verifier.

The original current source was preserved before repair under
`data/campaign5-intelligence/original-source`. Its 36-file manifest SHA256 is
`a676946c12640634a7f96ab09c664d7b3bdf40100039830befdab46b369ed5f6`, and
the source ZIP SHA256 is
`4a6ecc26638b1e954186191eef87aa82fff5dea60305f54e1bdbb00732342163`.
HEAD was `0aede831853b6876bc8904838a41f7b2ce8f3967`; the intentional
uncommitted Campaign 4 changes were retained. The original relevant baseline
passed 285 tests in 80.098 seconds. No private final input or oracle was read.

## Before-repair evidence and changes

| Boundary | Before-repair evidence | Repair |
|---|---|---|
| Local admission cancellation | First callback could dispatch after cancellation; second could return an accepted result. Cancellation during the callback was recorded as endpoint failure. | Recheck cancellation and closed state after original admission, preserve cancelled/blocked state, and avoid a failure profile or fallback for withdrawn authority. Remote admission uses the same wrapper. |
| Returned local eligibility | Healthy inference could return a result after current health or reserve withdrawal. | Recheck original identity, privacy, context, capabilities, health and resources. Expired health uses the original probe; new-dispatch queue and concurrency conditions are excluded. |
| Invalid resource observations | Bool, negative, nonfinite, and string resource values could remain selectable. | Reject present invalid readings without turning unknown measurements into available resources. |
| Collaboration context | The declared input-context reservation was reset before assigned inference. | Preserve controller context/schema requirements through dispatch; actual payload accounting remains native. |
| Collaboration cancellation | A verifier callback could cancel while leaving selected output and a verified final result. | Check after independent verification and before publication; cancelled final results have no selected output or proof. |
| Context bootstrap authority | Original `verify_context` bypassed disabled worker/deployment, synthetic sharing, resource reserves, capacity and busy-worker gates. | Use original protected configuration and resource rules, bounded prompt/output allocation, fail-fast queued conflict checks and a native slot reservation released in `finally`. Pass original cancellation through transport and recheck authority/runtime identities before creating proof. |
| GPU device zero | Numeric GPU device zero was interpreted as CPU-only when the display label was missing. | Treat a configured device zero as requiring measured GPU reserve; genuinely absent GPU configuration remains distinct. |
| HTTP response identity | Original SSE/chat/tool responses could name a different model; late SSE mismatch was ignored. | Bind optional parser identity checks to the configured API model. Present mismatches fail without same-endpoint retries; missing model metadata preserves older-server compatibility. |
| Identity failure attribution | A rejected response from another model counted as configured-model incorrectness. | Keep identity mismatch as an endpoint error with correctness unknown, rather than publishing quality evidence about the configured model. |

The original controlled gate suite had 65 tests: 37 passed and 28 failed.
Two initial failed assertions had incorrect prospective semantics: an expired
heartbeat may be renewed through a genuine probe, and a newly saturated queue
does not invalidate completed inference. Those original assertions, helper
bytes, and failures remain under `prospective-v1`. The revised 67-test suite
has explicit healthy/unhealthy expired-probe and concurrent-load controls;
39 passed and 28 failed before repair. Collaboration had 6/8 passing controls,
bootstrap 0/13, bounded fallback 8/8, and original HTTP identity 6/9.
These are assertion counts, not independent model answers or quality scores.

Every repaired cause was independently reproduced with exposed development
controls before the corresponding source change. The independent final set
was sealed before tuning and remains verifier-owned; the manager coordinates
but cannot inspect private inputs or oracles. The first independent
postrepair run retained a GPU-zero failure; that failure was preserved before
the additional gate fix.

## Validation and provenance

The broader repaired relevant suite passed 356 tests in 111.133 seconds. It
includes the original 285-test selection, collaboration, performance and lab
baseline plus compute-registry, native-client, workflow-collaboration and V3.7
compute checks. A subsequent narrow identity-attribution branch repair is
covered by the final focused run and independent checks. The earlier integrated
focused suite passed 157 tests in 25.681 seconds. Final source hashes and actual
XML node counts are published in `INTELLIGENCE_EVIDENCE.json`. The final
focused run passed 235 tests in 35.616 seconds, including the 53 independent
controls (independently rerun in 9.709 seconds). There are 76 shared test node
IDs between the 356-test broader run and the 235-test final focused run. The
285-test original baseline is a subset of the broader run. Separate HTTP and
intermediate focused receipts overlap these suites and must not be added as
new independent successes. `INTELLIGENCE_CHECKPOINT.json` pins the four final
production hashes and the reporting scope.

These receipts certify the production boundaries and helper versions exercised
at the time of each run. Final task-measurement contracts are being finalized
separately by the verifier; this checkpoint does not claim matching hashes or
complete validation of those later helpers.

The final focused command was:

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest -q tests/integration/test_campaign5_intelligence.py tests/integration/test_campaign5_intelligence_bootstrap.py tests/integration/test_campaign5_intelligence_collaboration.py tests/integration/test_campaign5_intelligence_fallback.py tests/integration/test_campaign5_intelligence_http_identity.py tests/integration/test_campaign5_verification.py tests/unit/test_adaptive_model_routing.py tests/unit/test_model_client.py tests/unit/test_compute_registry.py --junitxml=data/campaign5-intelligence/cycle2-final-focused.xml
```

The unchanged original baseline command was:

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest -q tests/unit/test_adaptive_model_routing.py tests/unit/test_model_collaboration.py tests/unit/test_model_performance.py tests/unit/test_compute_performance.py tests/unit/test_model_lab.py tests/integration/test_adaptive_v40_verifier.py tests/integration/test_collaboration_v41_verifier.py tests/integration/test_performance_v42_verifier.py tests/integration/test_model_lab_v43_verifier.py --junitxml=data/campaign5-intelligence/baseline-regressions.xml
```

The broader repaired command was:

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest -q tests/unit/test_adaptive_model_routing.py tests/unit/test_model_collaboration.py tests/unit/test_model_performance.py tests/unit/test_compute_performance.py tests/unit/test_model_lab.py tests/unit/test_compute_registry.py tests/unit/test_model_client.py tests/unit/test_workflow_collaboration.py tests/integration/test_adaptive_v40_verifier.py tests/integration/test_collaboration_v41_verifier.py tests/integration/test_performance_v42_verifier.py tests/integration/test_model_lab_v43_verifier.py tests/integration/test_compute_v37_verifier.py --junitxml=data/campaign5-intelligence/cycle2-relevant-b.xml
```

Both commands exited zero. The raw logs preserve the actual executed commands'
test results; the public evidence includes individual XML test node IDs and
receipt hashes. No additional broad rerun was needed after the separately
reproduced identity-attribution change because its affected adaptive/client
paths are in the final focused suite.

The old Anthropic cached-token unit fixture supplied no health timestamp,
reported allocation, or resources method. Only its synthetic metadata was
updated, including an 8448-token allocation for the unchanged 8192-token prompt
target and 256-token output allowance. Existing token-accounting assertions
remain unchanged. Production guards were preserved.

`cycle2-relevant` was a collection failure caused by a nonexistent file path,
with zero tests; it is not a pass. The corrected `cycle2-relevant-b` is the
356-test result. `cycle1-focused-b` retained three client identity failures from
the still-original client loaded before its authorized repair. Raw receipts
for failed cycles remain intact.

## Native integration limits

An isolated `AdaptiveModelEngine` must use the original configuration and an
isolated original compute registry. Synthetic inputs must declare synthetic
privacy through a trusted `ModelRequest`; text cannot grant permissions.
Configured or reported context is an upper bound, not a capability proof.
Identity-bound genuine proof imports or actual near-limit accounting and
exact retrieval remain necessary. A real bootstrap must pass the repaired
original resource/admission gates and must never borrow an owner inference
slot or create proof after cancellation/runtime replacement.

Remote native tool or vision inference remains unsupported. The existing
legacy supervisor path is explicitly unverified; retaining it does not upgrade
its capabilities. Native monitoring may maintain genuine health for long
inference, and expired leases are probed rather than backdated or extended.
Structured schemas and deployment/privacy constraints retain their existing
authority. No model, service, default, owner configuration, database, or
external account was changed.

At manager discovery the resident endpoint was healthy but below the original
RAM reserve, and all three registered workers were unhealthy. This worker
does not claim live model improvement, successful cluster comparison, or a
replacement recommendation from controlled tests. Independent real-response
results must substantiate any such claim; blocked tasks remain unexecuted.
