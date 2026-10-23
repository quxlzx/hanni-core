# HANNI V3.5 baseline

Audit started 2026-10-09 from repository commit `f19dd00`. Two implementation agents and a separate verifier are working on V3.5. The verifier preserved the original memory/LAYA/workflow implementations before changes; its private baseline manifest SHA-256 is `2de6e76ccc5c43f803cbc831cd0f5f26bded0d622632e4b6fa01dbc28c79c43d` (28 source, test, and documentation files).

## Existing architecture

- HANNI owns `MemoryStore`, its SQLite database, the privacy gate, and all durable writes. Schema version 2 has stable UUIDs, content/type, source, confidence, timestamps, and keyed facts. Version 1 migration is supported. Explicit correction retains a record ID but does not preserve earlier content history.
- `MemoryAwareSession` intercepts explicit remember/forget requests, announces narrowly extracted direct owner facts, and supplies bounded relevant recall to the original session. Safe Mode guards writes and suppresses shadow observation. Fingerprint changes invalidate session context and pending confirmations.
- `LocalMemoryRetriever` performs deterministic lexical retrieval, rechecks imported content against current privacy rules, and includes complete records under a character budget. It has no vector index, model reranking, or durable retrieval cache.
- Project folder aliases are keyed memory facts. HANNI OS already persists projects, notes, todos, and artifact links in `ProductivityStore`; V3.5 will retain these project identities rather than create another project database.
- V3 persistent workflows, leases, approvals, checkpoints, step verification, and private history exist. Stored plans and workflow status alone are not proof of a completed objective.
- Workspace > Memory currently lists up to 100 records, supports lexical search and confirmed deletion, and shows stored source/timestamps. The private dashboard API uses loopback, token, same-origin, profile, and stop boundaries. Stored confidence is not calibrated.

## LAYA installation and contract

The integrated shadow predictor invokes an optional `laya` runtime's `predict(state, questions)` interface. Its typed question responses cover capture, sensitivity, importance, pairwise relevance, and relationship labels. The authenticated loopback shadow endpoint returns an acknowledgement; it does not expose predictions to HANNI, retrieve production memories, or write authoritative memory.

The local Python environment has no installed `laya` runtime. No local `.env` or active process configuration identifies an enabled LAYA installation. Documentation describes an earlier remote checkpoint and SSH sidecar, but its present installation and inference behavior have not been verified. No remote memory transmission, model installation, or production startup was performed during this audit.

Historical draft challenge scores in `LAYA_SHADOW.md` remain unreviewed and uncalibrated. They are not a current quality baseline or an authorization gate. Actual LAYA model quality and inference latency are **NOT TESTED** pending a safely available installed model.

## Baseline verification

| Check | Observed result |
|---|---|
| Independent memory, shadow, and M9 integration tests | 24 passed |
| Worker memory and shadow checks | 19 passed; subset of the independent run |
| Full repository regression started before implementation | 1,396 tests and 25 subtests passed; two existing skips; no failures/errors; 207.105 seconds |
| Current-model 194-case tool development comparison | Qwen 169/194; HANNI metadata-corrected copy 113/194; separate from memory quality |
| New memory accuracy benchmark | Prospective suite being frozen by the independent verifier; no results yet |
| Genuine LAYA extraction/reranking | NOT TESTED; local optional runtime absent |

The independent verifier is preparing 240 synthetic scenarios across 15 evaluation families, split into development, validation, and untouched holdout data before evaluating the candidate. Cases, oracle hashes, sample sizes, unavailable features, and protocol differences will be recorded. Mock inference will not be described as genuine LAYA quality.

## Implementation boundaries and risks

V3.5 will add backward-compatible metadata and correction history to the existing memory store, proposal-only memory intelligence, bounded contextual retrieval, explicit associations with existing projects and verified workflow records, and a Memory Explorer with owner review. New context integration and LAYA advisory/retrieval remain explicitly disabled by default. Legacy deterministic retrieval and shadow behavior remain available.

All suggestions are untrusted data. Approval must use HANNI's owner/privacy/stop/write path with optimistic record binding. A model score cannot grant write authority. Deleted content must be removed from associated history, proposals, derived search data, and cached packages; stale proposals cannot recreate it. Plans, inferences, owner statements, and verified observations must remain distinguishable.

Remote owner-turn shadow consent does not authorize sending stored memories. A separate stored-memory and remote-memory consent boundary is required for any new inference contract. No developer address, credential, or private model path will be added to public source.

The installed-model limitation may block promotion of LAYA advisory/reranking while implementation, deterministic benchmarks, offline fallback, security tests, and UI verification continue. Production HANNI remains stopped, and Qwen remains the main model.
