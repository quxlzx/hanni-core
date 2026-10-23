# Current memory and LAYA architecture

Observed baseline: `b1ec1bb`. This describes inspected code and read-only
runtime evidence, rather than assuming an earlier version was deployed.

## Effective mode

**LAYA is disabled in the observed running installation.** Local durable memory
is enabled, with legacy deterministic retrieval. Enhanced project/context
retrieval is implemented but opted out by `memory.context_enabled: false`.

`laya.advisory_enabled`, `laya.retrieval_enabled` and
`laya.allow_stored_memories` are false in the configuration. The existing
launcher's `HANNI_LAYA_SHADOW_ENABLED`, `HANNI_LAYA_TRANSPORT` and
`HANNI_LAYA_ALLOW_REMOTE_TEXT` environment flags are absent. The inspected
listener inventory has the dashboard and local model but no listener on the
configured LAYA port 8766. These observations are preserved in
`data/campaign3-manager/baseline-model/RUNTIME_IDENTITY.json`; no owner memory
store was opened to obtain them.

The ordinary advisory factory always passes `quality_gate_passed=False`.
Installing a separately verified advisory client requires a trusted core call
and matching explicit configuration; an HTTP request cannot open this gate.
Even a validated client requires separate stored-memory and remote-transmission
consent. The campaign leaves these settings and gates unchanged.

## Data and authority

`MemoryStore` owns SQLite records, timestamps, source attribution, keyed facts,
project associations, semantic status, history and reviewable proposals.
`MemoryAwareSession` handles explicit owner commands and conservative stable
fact extraction, invalidates conversational context after memory changes,
and supplies retrieved data to the existing fallback session. Memories are
historical evidence, not registered tools, permissions or proof of present state.

`LocalMemoryRetriever` is the configured default. `ContextAwareRetriever`
implements optional weighted lexical recall, with live-record reads and bounded
in-memory term metadata. Its cache is not a persisted vector index. Secret
registry revisions participate in cache invalidation. `PersonalContextProvider`
combines optional project packages and distinct recall within one context budget.
`ProjectContext` resolves project identities and ambiguity, separates plans from
verified outcomes, and reads linked workflow checkpoints through the existing
workflow boundary. These optional paths are exercised in isolated tests;
they are not automatically enabled for the owner.

`TextSession` adds the memory data policy and the retrieved content to a user
message. Memory-derived turns do not enter its conversation history. Original
capability authority and runtime permission checks remain responsible for
actions. Passing stored text through this boundary does not prove that a model
will resist every injected instruction; that requires actual-response evidence.

Campaign source repairs extend current-record privacy checks across direct
session replies and retrieval, align automatic extraction with the existing
permission tier, fingerprint complete record state, and propagate configured
context budgets through fallback. The implementation rejects implicit
cross-project reassignment of identical text under the existing global unique
index; it does not introduce a database migration or claim support for duplicate
identical text in separate projects. Verification uses fresh campaign processes;
the owner's already running application is not restarted to load these repairs.

## Implemented LAYA paths

The opt-in shadow observer uses `/v1/shadow/evaluate`. Its response exposes an
acknowledgement, not predictions, and cannot rank memories or mutate them.
The separate versioned advisory endpoint exposes typed suggestions and binary
candidate relevance. The advisory client validates identities, revisions and
response fields, queues work without blocking retrieval, and caches only IDs and
labels. It can influence rankings only when its independent production gate,
retrieval flag and consent requirements all permit it.

Boundary tests use original clients, servers, queues and validators with
synthetic tokens and controlled predictors. Such tests establish protocol and
fallback behavior, not quality of a trained LAYA checkpoint. No active trained
LAYA service was available for native assisted-retrieval arm B.

## Evaluation limits

The existing local Qwen model endpoint is healthy and its file identity was
verified. Initial original guarded inference attempts were refused for
`insufficient_ram_reserve`. No resource guard was changed and no owner process
was stopped. Native tokenizer endpoints can measure synthetic context tokens
without generating an answer; those measurements remain distinct from server
generation usage. Source-grounded answer accuracy and incorrect-memory claims
remain unmeasured unless actual responses are admitted and independently scored.
