# M3 implementation review

This is an implementation and controlled-development record. It does not report a final full-suite result, configured-model improvement, or sealed-holdout acceptance.

## Original execution path

The additions observe the existing `ToolRegistry.execute`, MCP host/session and completion ledger. Registry validation, actor profiles, dynamic confirmation, foreground/workflow admission, emergency stop, mutation locking and original audit remain authoritative. Verification reads use that registry with the original actor and `confirmed=False`; mutation, external and non-low-risk verification definitions are rejected before their handler runs. There is no new general executor, authorization source or approval queue.

The original registry factory attaches a shared, lazy service per data directory. Request context carries the actual chat/fixed-desktop UUID and channel without adding model arguments. Host calls forward that correlation through the existing request contract. The service observes standalone original-registry calls as well as the MCP session's existing fast paths. Direct operations outside those wrappers, such as the memory session's explicit local remember short circuit, are not invented as registry executions.

## Recovery and duplicate prevention

One extra automatic read attempt requires explicit built-in `retry_safe=True`, existing retry allowance, effective low-risk read classification, a known transient error and authoritative `retryable=True`. Historical `side_effect=None` metadata is preserved for file.stat, system.stats and process.top_memory; their permission/risk-zero classification supplies the effective read boundary. Imported capabilities cannot opt into this retry from server metadata. Each attempt re-enters the original gates. Failed read keys are retained within the turn so another model round cannot restart their retry budget.

Random attempt-group UUIDs and attempt ordinals connect an actual retry. Aggregation supersedes a failure only when a later successful observation belongs to the same group. A successful same-capability call with different arguments cannot erase a prior failed scope. These IDs contain no argument hashes or values.

Writes are recorded as attempted before calling the original host. Exact effective-argument replay is blocked even after failure. An unsuccessful or unverified action additionally blocks further calls to that capability in the same turn, including changed arguments. Successful distinct-argument actions remain subject to the original policy. These are turn-local controls; they do not establish cross-process exactly-once delivery or universal semantic equivalence of successful calls. An ambiguous provider write is never automatically repeated.

## Evidence and reporting

Execution status and evidence status are separate. Defined checks cover current numeric resource snapshots, process lists, an exact launched process, actual file existence/content, saved task/note fields and a created calendar resource. Process existence does not prove a visible window. Read snapshots do not establish historical trends, causal explanations or live-model understanding. Unsupported writes and server-reported success/partial/verified flags do not establish outcome evidence.

Windows file verification follows the original Path.write_text newline semantics. Copy/move verification resolves an existing destination directory to its actual child path through authorized file.stat, rather than accepting an arbitrary result path or verifying the directory alone. Local task due verification uses the original parse_when normalization, including local timezone semantics.

Calendar receipts require identifier, requested title and schedule matches. Full created-resource verification additionally requires an authorized original provider read matching those fields. Agenda recovery preserves authoritative per-scope error codes: only an empty result whose failures are all transient can expose a retryable aggregate error. Partial returned events, authorization failures and unknown errors do not trigger that recovery.

Failed or malformed reads cannot retain a model's unsupported success claim. Failed checks receive a contextual failure sentence. Successful imported read text remains available as bounded, redacted, quoted server-reported data with explicit lack of independent verification; its recorded status remains UNVERIFIED. This preserves actual original SDK echo/schema/wire behavior without adopting server assertions as fact.

## Confirmation and storage

The legacy ToolAwareSession retains its original in-memory pending request and explicit yes/cancel behavior. Only that live originating session owns active confirmation. Actual confirmation resumes the trace, and actual cancel/close records cancellation without running the action. A stored waiting record after restart is historical approval-unavailable, retaining prior events and lacking an invented completion timestamp. It cannot resume or authorize execution. Modern MCP confirmation rejection is not presented as a resumable queue.

The local SQLite trace store opens lazily and stores constructed metadata only: request/task/step identifiers, capability names, timestamps, fixed summaries, gate outcomes, error classes, retry metadata and scoped boolean checks. It excludes prompts, hidden reasoning, arguments/results, personal file paths, calendar bodies and credentials. JSON task projections accompany append-only retained events. Bounds are 1,000 persisted tasks, 50,000 retained events, 128 live tasks and 64 detailed steps per task. Overflow preserves omitted-step/failure metadata so a later unrecorded failure cannot yield a fully verified task.

Corrupt/unsupported files are preserved and reported unavailable. Storage failure does not replay an action. Existing local account filesystem access remains the boundary; this is neither encrypted storage nor protection from a privileged user modifying the database. Existing private chat/tool audit stores are separate. Original handler/transport timeouts remain authoritative; the observer does not forcibly terminate arbitrary synchronous Python handlers.

## Activity inspection

Activity adds a token-protected read-only execution history and details beside the original audit history. It exposes actual selected capabilities separately from candidate menus, outcome versus evidence, timestamps, authorization, retries, phases and method/scope checks. Root owns the original Host/Origin/fetch-site/token gateway and the bounded execution projection. Initial fetch failure, disconnected/stale history, loading and genuinely empty states are distinct. This is inspection of recorded execution, not a tool runner or invented autonomous-agent manager.

## Controlled development evidence and limits

The retained development cycles live under `data/hanni-reliability-v2-review/workflows-after-cycle-1` through `workflows-after-cycle-8`. Their successive pipeline-expectation counts are 29, 33, 34, 36, 37, 38, 39 and 40 of 40. Earlier cycles preserve actual defects and harness seam/oracle corrections; these evolving development runs are not a valid before/after comparison. The final frozen runner and cases are used unchanged for the independently coordinated original/current paired replay.

The final runner retains all eight stage fields as boolean/null. Intent is null because scripted choices cannot measure language understanding. Positive fixtures, safe refusals, expected failures and unverified receipts have separate categories. Outcomes use validated controlled measurements or real isolated file/SQLite/provider-ledger state, rather than handler entry. Final answers require actual fixture facts or bounded failure/receipt wording. Recorded verification is separate from independent fixture outcome and absent original-version trace fields remain unmeasured.

The deterministic client includes actual returned text evidence generically on both source versions. It is not the configured local model. Application fixtures simulate receipts/process outcomes rather than launching Windows applications. Calendar state checks compare the provider resource with the resolved plan, not an independently frozen-clock interpretation of tomorrow at 15:00. Task/note/delete cases use exact original structured boundary requests, so their language-planning stages are not scored. Voice/screen checks exercise current unavailable/stop/privacy boundaries without audio capture or screen analysis. An unknown MCP write is rejected by the original policy before its configured delayed provider would execute; it is not a measured remote timeout.

Fixture SHA256: `3e4715bed34d74bd3613ac1bab23a6a83a46960df63215d403ca92c35dbb279e`.

Frozen runner SHA256: `5f8efe310ee8811275114c2722834801597e5e2be19998da1bf343b8a28b6f0d`.

The most recent focused execution/adversarial/original-session run passed 69 cases. The preceding original SDK controller/schema/wire plus Google run passed 38 cases; the later combined run retained one owned incomplete-title test fixture failure, corrected to a valid requested title and rechecked by the 69-case run. Final full regression, paired metrics and untouched holdout results belong to their independent reports and are not inferred here.
