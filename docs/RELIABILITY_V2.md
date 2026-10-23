# HANNI Reliability & Intelligence V2

This change extends the original HANNI capability registry, MCP host and conversation session. It retains the configured local model, approved MCP connections, permissions, confirmation, emergency stop, memory and voice boundaries. It adds no cloud dependency or general desktop execution endpoint.

## Retrieval

The capability index uses weighted BM25 on registered names, descriptions, aliases, categories and argument descriptions, plus bounded vocabulary correction for typos. Confidence and score margins determine how many relevant candidates to expose within the configured ceiling. Scores measure metadata evidence; they are not probabilities or pretrained semantic embeddings. The development audit found no sufficient gain from a latent-SVD alternative to justify adding it.

The original host still resolves safety, actions, dates and fixed arguments. Generic retrieval supplies eligible alternatives for unresolved or weak read menus. Eligibility is checked before candidate selection. The registry revision invalidates the index when definitions are registered or withdrawn. Imported tools retain their IDs, schemas and approved definition hashes; their descriptions cannot grant permissions or retry authority.

## Execution and verification

`hanni.reliability` observes the existing registry and session. The default factory shares a lazy service per resolved data directory. Chat and voice adapters attach the actual conversation UUID through a context scope; the model client receives no new request-ID argument. Fixed desktop mutations preserve their existing UUID-bound deduplication and attach that UUID to their execution records.

A task records request, planning, execution, tool completion, verification and reporting events. Denials, failures, timeouts and cancellation retain separate execution outcomes. An execution succeeding and its outcome being verified are separate fields. Candidate menus, actual capability calls and evidence scopes must be assessed separately.

- A read can verify its returned snapshot, which does not establish historical trends or causes.
- Application launch can provide a launch receipt or an observed process. Process existence does not prove a visible application window.
- Calendar creation requires a returned identifier and matching schedule. A receipt alone supports partial verification; an authorized provider read must also match the requested title to confirm the created resource.
- File changes use authorized read-after-write existence/content checks where supported.
- External MCP responses are untrusted acknowledgements. A server's success or `verified` assertion is not independent outcome verification. Read data can be quoted as the external server's response while retaining an unverified outcome.
- Unsupported action checks remain unverified. Verification never grants permission to another capability.

Verification reads pass through the same original registry, actor profile, emergency stop and authorization gates. They cannot inherit action confirmation or execute a mutation. An unavailable check does not cause the action to be repeated.

## Recovery

The MCP conversation blocks repeated attempts at the same write with the same effective arguments during that turn, including failed or ambiguous attempts. This is in-session duplicate prevention, not a cross-process exactly-once delivery guarantee. After a transport timeout, a write can have an unknown outcome; inspect the destination before issuing a new request.

At most one additional automatic retry per effective call in a turn requires all of: explicit built-in `retry_safe` metadata, an original low-risk read, a known transient error marked retryable, and existing retry allowance. Random attempt-group IDs connect an actual retry to its original attempt; another successful call with different arguments cannot erase that failure. Imported capabilities, writes, destructive operations, invalid arguments, authorization failures and cancellation are not automatically retried. Successful reads retain the original per-turn duplicate guard. Existing transport and handler timeouts remain authoritative; this observer does not forcibly terminate arbitrary Python handlers after advisory timeout metadata.

## Activity inspection and local storage

Open **Activity** in HANNI OS to inspect execution records alongside existing audit history. Expand a task for request/task IDs, capability steps, timestamps, authorization decisions, retries, lifecycle events and verification methods/scopes. The authenticated read-only endpoint is `GET /api/executions?limit=50`, with a limit of 1–100. It uses the original Host, Origin, fetch-site and current dashboard-token checks.

The trace store is `<data_dir>/logs/execution_traces.sqlite3`. Discovery and an empty history request do not create it. It retains at most 1,000 tasks and 50,000 lifecycle events; the in-memory projection retains 128 tasks. It stores constructed metadata and fixed summaries, excluding raw prompts, tool arguments/results, personal file paths, calendar contents, credentials and hidden reasoning. Existing private chat and tool-audit stores remain separate.

Corrupt or unsupported trace storage is preserved and reported unavailable. A trace-store failure does not repeat a tool, change authorization or turn an unverified outcome into success. Inspection is local and uses the account's existing filesystem access; traces are not a shared-account security boundary.

Approval is active only in its original live session. A historical pending record is displayed as unavailable after restart; stored traces cannot resume or authorize an action. Trace bounds also retain the fact of an omitted failure, rather than presenting a truncated task as fully verified.

## Evaluation and resumption

[Architecture audit](RELIABILITY_V2_ARCHITECTURE.md) and [milestone checkpoints](RELIABILITY_V2_CHECKPOINTS.md) document the baseline and implementation sequence. The baseline default registry has 172 capabilities; runtime desktop definitions and imported capabilities are counted only when actually registered. Static test references, retrieval, actual model selection, handler execution and outcome verification are separate coverage measures.

Historical routing/model-tool cases and new controlled workflows are development evidence. The independent verifier owns a separate sealed 60-case final holdout, pinned before development. Final cases are evaluated only after source freeze, without tuning against the final results. Actual configured-model runs are reported separately from deterministic test clients and controlled provider/OS adapters. No metadata-only score or plausible response is counted as successful handler execution.

The paired 40-workflow suite uses a declared test-only write-enabled profile, controlled OS/provider adapters and real isolated files/local stores. It does not change the application's default observe-first policy. Scripted tool choices do not measure language understanding. Positive outcomes, expected refusals, expected failures and unverified receipts have separate denominators; independent fixture outcome checks are reported separately from the application's recorded evidence scopes.

For local regression checks, use `.\.venv\Scripts\python.exe -m pytest` from the repository and `npm run check` from `frontend`. Workflow, coverage, benchmark and independent review commands/results are recorded in the checkpoints as their milestones are accepted. This document describes the implementation contract; final acceptance and measured limitations require the independent report.

The [final comparison](RELIABILITY_V2_REPORT.md) records **PARTIAL** acceptance: controlled execution/security/native checks pass, but the unchanged unseen recall misses its target. The immutable final cases/evaluators were published after evaluation and require a fresh holdout for future development.
