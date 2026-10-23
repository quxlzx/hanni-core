# HANNI V3.5 configuration and operation

V3.5 uses the existing HANNI memory SQLite database, workspace project identities, controller, model sessions and workflow services. No model weights, credentials, training data or cloud dependency are added. Existing schema v1/v2 records migrate additively to v3, retaining their IDs, content, source and original timestamps. Production HANNI was kept stopped during implementation and verification; these instructions do not start it automatically.

## Memory Explorer

On the next normal HANNI OS launch, open **Workspace > Memory**. Stored memories, the review queue and project context read persisted records. Empty, offline and missing-source states are explicit. Keyword search is local; semantic/vector search is unavailable in this implementation. Stored confidence is not displayed as a calibrated probability.

Select a record to inspect its source and correction history. Correction and deletion bind the displayed record version; refresh after a concurrent edit. Deletion removes that record, its history and associated suggestion copies. The review queue allows approval with optional owner edits, rejection and dismissal. Relationship/conflict/staleness suggestions identify a question for review and do not automatically choose truth, merge records or archive old data.

**Analyze statement** creates conservative local-rule proposals from explicit reusable owner statements. **Consolidate** scans a bounded set of approved records for relationship/staleness proposals. Both label their local-rule origin and leave authoritative memories unchanged until an eligible proposal is explicitly approved. These controls work without LAYA inference. Legacy direct owner-fact extraction remains governed by the existing `memory.extraction_enabled` setting and announces saved facts.

Project context uses existing project IDs. Owner aliases and explicit workflow links require confirmation against the current project version. A plan, owner completion claim or project status is not a verified outcome. Verified receipts must satisfy the original workflow's execution/evidence/result checks. Context inspection and continuation recall do not execute or resume a workflow; original workflow approvals remain required.

## Optional deterministic context

The shipped settings in `config/hanni.yaml` keep the existing memory retrieval path active and the new contextual path disabled:

```yaml
memory:
  enabled: true
  extraction_enabled: true
  retrieval_enabled: true
  search_limit: 8
  max_context_chars: 4000
  min_relevance_score: 25
  context_enabled: false
  max_context_tokens: 4000
```

An owner can explicitly set `memory.context_enabled: true` in their selected configuration and restart their normal session to evaluate the deterministic context path. This selects live, bounded source records and project packages for the original model pipeline. It asks for project selection when a continuation is ambiguous. Current owner instructions take precedence, retrieved data cannot grant tool authority, and model-derived context turns are not retained in conversation history.

The context budget applies to the combined project and general-memory text. `max_context_tokens` is a conservative UTF-8 byte bound, not an exact tokenizer count; `max_context_chars` and the record limit also apply. Hypothetical, inferred, question and temporary records are excluded from active context. Optional project or inference failures fall back to deterministic local retrieval. Consult [the verified report](HANNI_V3_5_REPORT.md) before interpreting this opt-in as a quality improvement.

## LAYA rollout gates

Legacy shadow observation retains its existing opt-in environment/SSH setup and acknowledgement-only endpoint; see [LAYA shadow setup](LAYA_SHADOW.md). Owner-turn shadow consent does not authorize transmitting stored memories.

New `laya.advisory_enabled` and `laya.retrieval_enabled` default to `false`. `allow_stored_memories`, `allow_remote_text` and `allow_remote_memories` also default to `false` and represent separate consent boundaries. Local advisory inference still requires explicit stored-memory permission for ranking. SSH-forwarded advisory inference additionally requires remote text and remote memory permission. Safe Mode suppresses optional inference/transmission while retaining the original local read path.

The optional server exposes `/v1/advisory/evaluate` only with `--enable-advisory`; the original shadow endpoint remains unchanged. A compatible separately installed predictor must support the original training-time `predict(state, questions)` contract. The server binds loopback, authenticates with a private token, limits payload/concurrency, serializes the shared predictor and has no authoritative memory write path. Keep tokens outside source and frontend code; retain the existing private authenticated SSH/loopback safeguards.

**Configuration enablement is insufficient to activate advisory inference.** The ordinary controller factory keeps an independent model-quality gate closed. A future trusted controller binding through `hanni.laya.runtime.install_advisory` must match the configured transport/endpoint and supply a separately verified enabled client and private token. That binding is not an HTTP operation or a user-supplied authority flag. This delivery does not claim to verify or deploy a working LAYA checkpoint, and it installs no such binding.

Actual model extraction/relevance/calibration, comparable retrieval improvement, security, latency and backend compatibility must be independently verified before promotion. If quality is worse or unavailable, keep deterministic retrieval and leave advisory/reranking disabled. The Explorer reports actual runtime state; requesting a missing or ungated service displays unavailable rather than healthy.

## Verification and rollback

Run the source regression suite with `python -m pytest`. Build the desktop assets with `npm run build` in `frontend`; typed control tests use `node --experimental-strip-types --test tests/memory_types.test.ts`. These commands do not constitute an actual-model LAYA quality benchmark.

The public development retrieval runner is:

```text
python -m hanni.evals.memory_intelligence --output data/memory-development.json --repeats 3
```

It exclusively accepts synthetic development cases, refuses validation/holdout partitions and creates a new output file rather than overwriting previous results. Its A arm is the current v3 store with original lexical retrieval; it is separate from the verifier's archived pre-V3.5 baseline. Reports distinguish source-ID correctness from generated factual accuracy and byte bounds from measured tokens.

The [independent report](v35-reviews/HANNI_V3_5_INDEPENDENT_REVIEW.md) describes the sealed 240-case evaluation, prospective model cohort, source/corpus hashes, screenshots and unavailable gates. The [reproducible corpus and runners](../evals/memory_intelligence_v35/README.md) preserve original synthetic cases and baseline bytes. Do not tune against the now-public scored holdout and then reuse it as untouched validation. The actual-model runner requires the matching existing local weights explicitly, owns an isolated loopback runtime and refuses replacing an existing model manager. Reruns are reproductions, not replacements for the retained once-only failed acceptance results. See [checkpoints](HANNI_V3_5_CHECKPOINTS.md) for safe resumption.

To disable experimental context, set `memory.context_enabled: false` and restart the normal session. Leave all LAYA advisory/retrieval flags false to retain the existing deterministic path. Do not downgrade the migrated database to older code without a compatible migration or restoring an owner-managed pre-migration backup: metadata, correction history and proposals are additive schema v3 data. The original model selection and workflow engine are unchanged.
