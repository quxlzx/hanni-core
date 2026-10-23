# Campaign 9 workflow, memory and inference boundaries

This worker tested original APIs with disposable SQLite/config/file state and controlled model, network and failure leaves. Owned loopback HTTP servers exercised the actual local client transport. No genuine inference, remote SSH/provider call, owner database/config mutation, physical resource exhaustion or model/device restart was performed by this worker. The independent verifier owns the sealed final inputs and oracles; this report contains development evidence only.

## Confirmed findings and repairs

| Finding | Severity and controlled precondition | Original result | Repair | Independent regression |
|---|---|---|---|---|
| Raw durable-memory mutation errors exposed credentials | Medium information disclosure; a storage dependency exception contains a synthetic registered secret | Remember, Forget and Delete-all each copied the raw exception into the owner-visible reply; original rows stayed unchanged | Apply the existing shared `redact_text` to outward mutation/project-opening exception strings; preserve failure wording and original authority | Three fresh independently authored variants pass; no mutation and no secret in reply |
| Local model diagnostics exposed response/network credentials | Medium information disclosure; an owned endpoint returns a synthetic credential-bearing 401 body | `ModelHealth.detail`, chat error and tool-turn error each exposed the credential | Apply shared redaction before bounded HTTP-detail rendering and to network/unhealthy-status details; retain status and retry policy | Three fresh 401 variants pass; supplemental network-error redaction controls also pass |
| Configured local model transport followed untrusted redirects | Medium endpoint trust/SSRF boundary; a controlled configured endpoint redirects to a second owned endpoint | Health/chat redirected to another endpoint as GET; one replacement request occurred in each test | Per-client urllib opener refuses redirects and ambient proxies, without installing global transport defaults | Independent 307 health and 303 chat variants now make zero replacement requests; stable direct/no-ambient-proxy control passes |

The redirect proofs demonstrate a request to a replacement owned endpoint. They demonstrate **zero forwarded POST-body bytes**, and do not claim a private-text or third-party leak. The exception proofs used synthetic values only. Passing redaction tests establish protection for the original shared redactor's registered/token-shaped rules, rather than detection of every possible secret representation.

Production changes are restricted to `src/hanni/memory/session.py` and `src/hanni/models/client.py`. Original admission, schema and model-identity checks, missing-model compatibility, retry caps and partial-output no-replay remain in place. The client has a scoped `_open` dependency seam and never installs a process-wide opener. The partial-timeout test moved its mocked opener to this new seam with the same one-request oracle.

## Native security and fault coverage

| Boundary/fault | Observed original outcome and recovery scope |
|---|---|
| Workflow plan injection | Extra model-supplied owner/confirmation/mode/permission fields are rejected before any invocation or handler entry; unsafe shell/power/remote bindings outside the routed menu cannot expand authority. These are controlled planning-contract decisions, not natural-language model safety measurements. |
| Managed-write path traversal | Two relative escape variants are rejected before file-write entry or artifact creation. |
| Approval rejection/revocation | Original supervised action rejection prevents the report write; revoked plan cannot start across three repeated attempts. |
| Replay/duplicate effects | Repeated identical request ID returns the same workflow; changed body with that ID is denied. The approved positive performs one original report write, with exact independent file bytes. |
| Cancellation/emergency stop | Cancel, pause and emergency stop at the committed predispatch boundary lead to the appropriate withdrawn state, zero original read/write handler entries, and preserved receipt state. |
| Consequential write ambiguity | Disk-full, malformed returned receipt and lost-after-write faults do not report completion or automatically replay. Each has one write invocation; disk-full creates zero reports, the latter two preserve one actual written report and unresolved outcome. Safe-retry of the write is denied. |
| Disposable service restart | Closing/recreating the original workflow service preserves invocation IDs and actual report bytes; completed work is not replayed. A lost write remains blocked and both resume/retry are denied. This is a real original service reattachment, **not an OS/backend-process restart**. |
| Corrupt checkpoint | Original store history refuses malformed JSON, preserves the corrupt bytes and creates zero invocations. Automatic checkpoint repair is unsupported; no fabricated recovery is credited. |
| Temporarily unavailable workflow SQLite | Original create fails without a partial workflow; after restoration, a new explicit request succeeds. |
| Planner timeout/invalid JSON/GPU OOM | Original service blocks after one controlled model-interface call and zero tool entries. GPU OOM is an exception seam, not an actual allocation/stress test. |
| Memory injection and imported data | Six authority-changing instructions are rejected before persistence; three benign discussions remain legal data. Imported unsafe content/provenance/fact values are withheld without deleting the original rows. |
| Original memory permissions | Chat-only, disabled/missing owner, low automatic tier and Safe Mode reject new persistence; no delegated model call or falsely saved memory. |
| Memory database/index faults | Unreadable database stops the request with no invented recall/save. Four failed context-index interfaces fall back to original local retrieval with a complete untrusted-data envelope under the declared budget. |
| LAYA timeout/disconnect/invalid JSON | One controlled failure produces no cached result; the next distinct valid request is accepted by the original worker. The client closes its owned thread. Remote-text consent, stored-memory consent and closed quality gates make zero network entries. |
| Private-context cluster placement | Five private categories disallowed by the protected worker produce zero transport POSTs. Capability provenance adds memory/screen/sensitive categories through analysis dependencies regardless of labels in source data; missing/cyclic provenance fails closed. |
| Credential forwarding | Credential-bearing message text, schema metadata and a freshly registered synthetic secret are rejected before remote dispatch. |
| Worker/network/protocol faults | Controlled network loss, GPU-OOM, empty choices, truncated completion and response-model replacement fail after one transport entry, release reservations/queues and do not return verified success. No remote process/hardware recovery claim. |
| Inference cancellation | Pre-dispatch cancellation creates zero POSTs; cancellation during return creates one POST then discards the result. No retry or healthy-worker penalty. |
| Repeated failed authorization | Chat/tool HTTP failures retain the original three-attempt cap and original 0.2/0.4-second backoff. These are inference requests, not repeated consequential tool operations. |
| Partial stream loss | A visible partial response followed by timeout causes one request and an error, with no replay. |

Tool/MCP/core permission boundaries belong to the other engineering worker; API authorization, logging integration and full backend-process restart belong to the manager. Their evidence is separate. This worker's matrix is not an assertion that its own cohort alone exhausts the campaign's twenty areas.

## Preserved evidence and denominator corrections

All paths below are ignored raw development receipts with original source/test bytes, commands, exit codes, JSON observations, JUnit and stdout/stderr. Counts refer to test executions; repeated suites overlap and must not be summed as unique cases.

| Receipt under `data/campaign9-resilience/` | Outcome | Interpretation |
|---|---:|---|
| `memory-before` | 17 pass / 10 fail | Three genuine disclosure failures; seven fixture assumptions preserved in `HARNESS_ERRATUM.json`: 512 bytes cannot hold a whole memory/policy envelope, and the mock advisory positive omitted mandatory no-authority metadata. |
| `memory-before-corrected` | 24 pass / 3 fail | Same original memory source; corrected fixture contracts; three disclosure failures remain. |
| `workflows-before` | 23 pass / 0 fail | Original service/registry/real disposable file handlers; controlled planner/fault interfaces. |
| `inference-before` | 18 pass / 11 fail | Five genuine client failures; six direct scheduler fault controls were not admitted because reused adaptive evidence did not create a native context receipt. Those safe queue failures are fixture errors, not worker-fault passes. |
| `inference-before-corrected` | 24 pass / 5 fail | Original synthetic `verify_context` creates a controlled bootstrap receipt; its setup call is distinct from fault dispatch counts. Token usage is mocked; no live context certification. |
| `development-before-cycle1` | 76 pass / 10 fail | Eight genuine finding checks plus two ledger-instance restart assumptions; original failure is retained. |
| `development-before-corrected-cycle1` | 78 pass / 8 fail, 86 checks, 9.997 s | Correct restart oracle observes prior writes=1, new-instance writes=0, persistent invocation IDs and actual bytes. No changed semantic acceptance requirement. |
| `development-repair-cycle1` | 86 pass / 0 fail, 10.357 s | Same corrected causal cohort after the authorized narrow repairs. |
| `development-repair-cycle2` | 92 pass / 0 fail, 12.644 s | Adds six meaningful opener/proxy, repeated-auth and network-redaction controls. |
| `relevant-regressions-cycle1` | 240 pass / 0 fail, 38.008 s | Ten affected original test files; own workflow/memory/LAYA/compute/model source hashes unchanged during collection. |

The independent eight-check afterproof is `data/campaign9-verifier/client-memory-after-01/RESULTS.json`, SHA256 `640054f777d1ee81b19bfc9f71d4a21482c20b0e1817db19efacd267be300266`. Its original failing receipts remain in `development-before-01` and `client-before-01`. The verified production identities are:

- memory session: `aa05bfc77624b7af9531cc4896daee6364ea6619040a0feac9f022cb1dd3ec63`
- model client: `df99bc9aadbf4c8897b99d8c83ed1490eca07c59096e0e8b1ae25fa3243743fa`

The relevant regression command is `.venv\Scripts\python.exe -X utf8 -m scripts.campaign9_resilience.run --regressions --output data/campaign9-resilience/relevant-regressions-cycle1`. Its fixed selection is `test_model_client.py`, `test_memory.py`, `test_memory_context_v35.py` and `test_laya_advisory.py` under unit tests; `test_memory_context_v35.py`, `test_memory_v35_verifier.py`, `test_laya_v35_advisory_verifier.py`, `test_campaign3_boundaries.py`, `test_campaign3_boundaries_recovery.py` and `test_campaign5_verification.py` under integration tests. The public JSON includes exact paths, commands, receipt hashes and original node IDs. The 92 current development checks and 240 original checks are distinct cohorts; earlier repeats and the independent eight are not added as new cases.

## Requested-category scope

The machine-readable [RESILIENCE_EVIDENCE.json](RESILIENCE_EVIDENCE.json) maps every requested area to actual test nodes or its separate responsible owner. The following map avoids crediting another worker's unfinished evidence as this worker's result.

| Requested security area | This worker's implementation evidence or explicit gap |
|---|---|
| 1. Tool permission enforcement | Original workflow routed capability boundary and memory registry profiles deny unsafe additions/new persistence. Tool registry/MCP exhaustiveness belongs to Worker 1. |
| 2. Approval rejection | Supervised report-write rejection preserves the verified read and performs zero write entries. |
| 3. Permission revocation | Revoked reviewed plan cannot start or silently approve itself across repeated attempts. |
| 4. MCP server authentication | Worker 1 owns the original MCP authentication audit; not measured by this cohort. |
| 5. Malicious MCP tool descriptions | Worker 1 owns description admission/authority controls; not measured by this cohort. |
| 6. Tool-result prompt injection | Original capability/dependency provenance cannot be relabelled public by untrusted source data; missing/cyclic provenance denies transmission. Response-level model resistance is not measured. |
| 7. Memory-based prompt injection | Authority imperatives refuse persistence; unsafe imported content/metadata is quarantined, with benign discussion controls. |
| 8. Workflow plan injection | Controlled model plans cannot supply owner, confirmation, permission or execution mode, or add capabilities outside the routed menu. |
| 9. Unsafe shell-command requests | Injected terminal binding is refused before handler entry. Actual shell execution is prohibited and untested. |
| 10. Filesystem path traversal | Escaping managed artifact paths are refused before invocation/effect. General filesystem tools belong to Worker 1. |
| 11. Unauthorized file modification | Approval rejection/revocation and cancelled dispatch make zero report writes; an approved positive writes exactly once. |
| 12. Unauthorized remote execution | An injected compute-start binding cannot expand the workflow menu. Private/credential-bearing inference requests produce zero remote entries. No actual SSH/provider call. |
| 13. Credential leakage | Three memory exceptions and three HTTP diagnostics originally leaked; repaired independent controls disclose none. Message/schema forwarding and network-error redaction controls also pass. |
| 14. Excessive logging of sensitive content | Manager owns actual logging/API integration; this worker only measures outward memory/model diagnostic text. |
| 15. Frontend/backend API authorization | Manager owns actual API token and restart controls; not measured by this cohort. |
| 16. SSRF protections in remote integrations | Actual owned local HTTP redirects are refused, and ambient proxies are ignored. General remote integrations belong to Worker 1/manager; no universal SSRF claim. |
| 17. Private-context transmission to cluster nodes | Protected worker category consent, credential screening, native provenance and LAYA consent/quality boundaries deny network entry. Transport/model replies are controlled. |
| 18. Destructive operation safeguards | Injected power binding is refused, destructive memory imperatives cannot persist, emergency stop prevents new writes. No physical destructive action. |
| 19. Replay and duplicate request handling | Original request-ID deduplication prevents duplicate report effects; changed replay body is rejected; restart retains completed invocation identity. |
| 20. Cancellation and emergency-stop behavior | Committed workflow dispatch withdrawals make zero handler entries; pre/late inference cancellation retains worker health and does not retry. |

| Requested fault | Safe failure and demonstrated recovery limit |
|---|---|
| MCP disconnection | Worker 1 owns SDK disconnect/recovery evidence; not exercised here. |
| Model timeout | Controlled planner timeout blocks tool dispatch; partial local stream timeout has one request/no replay. Automatic restoration of a timed-out model process is not tested. |
| Malformed tool response | One original report write returning a malformed receipt remains unresolved, never completed/replayed. Reconciliation is required. |
| Invalid JSON | Controlled planner rejects; LAYA drops a bad reply and accepts the next distinct valid request. |
| Backend restart | Original workflow service reopens the same disposable store without duplicate completed writes; uncertain write remains blocked. Full HTTP backend-process restart belongs to manager. |
| Worker disappearance | Controlled remote/network loss releases reservation and reports failure; actual remote worker disappearance/restart is not tested. |
| Database temporarily unavailable | Original workflow create leaves no partial row; a new request after restoration succeeds. Memory read failure reports unavailability and invents no recall/save. |
| Corrupted checkpoint | Corrupt JSON remains preserved and history fails clearly; no automatic repair or replay. |
| Memory index failure | Four failed index interfaces use original bounded local retrieval; unsafe imported records remain withheld. |
| Insufficient disk space | Controlled ENOSPC before the report write creates no artifact and no completion; write retry remains denied. No physical disk exhaustion. |
| GPU out-of-memory | Controlled exception in planner/remote interface blocks completion and releases reservations. No GPU allocation/stress or hardware recovery. |
| Network interruption | Controlled LAYA disconnection recovers on a distinct request; remote transport failure releases reservation; local partial stream is not replayed. |
| Repeated failed authorization | Actual owned HTTP 401 loops respect three-attempt cap and original backoff, redact credentials and never dispatch a tool. |

All executable own sources, helpers and tests are held. Final private results are pending and verifier-owned. The manager coordinates the final freeze but cannot inspect private inputs/oracles. The checkpoint establishes this worker's scoped source state, not the manager's still-changing API/logging scope or a whole-repository freeze.

## Separate legacy cross-boundary supplement

The manager's original 188-execution cross-boundary regression receipt retains 178 passes and ten failures at `data/campaign9-manager/development/CROSS_BOUNDARY_REGRESSIONS.xml`. The failing public V4.4 checks expected a transport entry or successful receipt but observed zero entries. This original outcome is preserved and is not regraded as a pass.

Direct inspection of the unchanged imported `audit_engine` shows `max_context_verified=8192` and a passing context gate. Its controlled `resources()` result lacks `resource_sampled_at`; the newer original remote-resource freshness gate therefore rejects it, leaving zero eligible choices. Even original `verify_context` refuses before transport on that unchanged fixture. The precise cause is missing fixture resource metadata, rather than missing context evidence. `data/campaign9-resilience/cross-boundary-before-corrected/DIAGNOSIS.json` preserves the observation and four source hashes. The earlier diagnostic used the wrong private helper name; its separate harness erratum is retained and is not a product failure.

The separately authorized C9 helper `scripts/campaign9_resilience/cross_boundary.py` stamps only newly returned controlled mock resource samples with the original registry clock, retaining any explicitly supplied stale/invalid timestamp. It then calls original `verify_context` with mocked 1,024-token usage and exact synthetic retrieval. The setup's one transport entry and released reservation are recorded separately before target call counts are cleared. The existing original 8,192-token record remains visible; no hardware/model certification is inferred. The ordinary response and usage are restored before each target assertion.

`tests/integration/test_campaign9_resilience_cross_boundary.py` aliases every unchanged public V4.4 function and parametrization. Its distinct fixture supplies the setup above; original files and assertions are untouched. All 29 original assertion executions plus two new admission/response-preservation controls pass: 31/31, zero errors/skips, 4.834 s. Receipt `data/campaign9-resilience/cross-boundary-supplement-cycle1/RESULTS.json` includes original byte archives, setup properties and source equality across the run. These reused assertions are a separate fixture-adapted regression supplement, not 29 newly authored independent security cases. No production change, live inference, network/provider call or private-final access occurred.

Command: `.venv\Scripts\python.exe -X utf8 -m scripts.campaign9_resilience.cross_boundary --output data/campaign9-resilience/cross-boundary-supplement-cycle1`. The earlier `SOURCE_READY.json` stays immutable; the supplement is pinned separately in `SOURCE_READY_SUPPLEMENT_CYCLE1.json`.
