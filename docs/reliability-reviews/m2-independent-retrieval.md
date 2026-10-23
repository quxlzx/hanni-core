# Independent M2 retrieval review

**PASS for the bounded M2 development implementation and authority checks.** This is not final unseen-language or end-to-end acceptance. The private final holdout was not run against development source.

The verifier read the new index, host integration, development comparison runner and tests, then independently ran the comparison and original MCP-controller authority cases. The focused suite passed **24 tests, zero skips/failures/errors**, in 29.284 seconds: new retrieval tests plus thirteen genuine stdio/HTTP original-controller MCP cases. Evidence: `data/hanni-reliability-v2-review/retrieval-authority-check.xml`.

## Independently reproduced development measurements

| Development corpus | Samples | Before | After |
|---|---|---|---|
| New unfamiliar tool requests, menu sufficiency | 35 | 23/35, 65.71% | 32/35, 91.43% |
| Same corpus no-tool requests | 5 | 4/5, 80% | 4/5, 80% |
| Historical model-tool scenarios | 194: 166 positive, 28 no-tool | All menus/no-tool checks pass | All menus/no-tool checks pass |
| Historical capability probes | 264 positive | All menu checks pass | All menu checks pass |
| Historical routing | 1,131 | 1,129 strict passes | 1,129 strict passes |
| Historical routing mean score | 1,131 | 99.5904/100 | 99.5551/100 |

These are metadata-only checks. They execute neither local models nor production handlers. Historical corpora and the newly exposed forty-case corpus are development evidence and must not be presented as independent generalization. The mean historical score drops slightly despite unchanged strict pass count because of additional allowable menu exposure; that tradeoff is retained rather than concealed.

The runner performs three warm passes then five interleaved measured passes, alternating before/after order. In the unfamiliar development corpus, P50 retrieval was **0.918 ms before / 1.023 ms after**, P95 **4.210 / 4.438 ms**, mean menu count **0.90 / 1.25**, and mean serialized schema characters **284.25 / 391.625**. Each latency distribution contains 200 measured menu evaluations over forty cases, not 200 independent language samples. Its P95 convention uses the runner's sorted index and is explicitly distinct from nearest-rank end-to-end inference percentiles.

The original comparison host is loaded from M1 commit ca95b05. The verifier separately confirmed its source bytes equal original commit 791bdab. The same current metadata registry is intentionally shared between versions, so this comparison isolates the host/index change rather than representing a full old application replay. Legacy retrieval dependencies were not modified by the retrieval worker. The runner restores original-host isolation when the existing scorer reconstructs a host; it does not silently score a new host as baseline.

## Source and security assessment

The new ranker uses weighted BM25 over registered metadata, bounded vocabulary-derived typo correction and generic relevance/margin thresholds. No query-to-tool mapping, benchmark ID switch, final-case override, model retraining, mandatory provider or downloaded embedding service was introduced. Existing safety/date/action resolvers remain authoritative.

Eligibility is applied before generic candidate selection; the broadening path is read-only and cannot grant action or dynamic confirmation authority. Registry revisions invalidate the index and eligible cache. Full schemas/definition hashes remain untouched, and call-time registry policy still denies unavailable or changed capabilities. Metadata bounds and frequency caps limit external repetition; imported descriptions remain untrusted data and cannot enable retries, bypass approvals or override the original permission gates.

The focused genuine MCP cases additionally pass actual stdio and Streamable HTTP original-controller execution, unchanged approvals/hash revocation, exact external identities, schema validation, forbidden write/SafeMode gates, long-name collisions, credential-reflection rejection and actual tools/list_changed invalidation. Deterministic model selection in those tests is disclosed; this is authority/protocol evidence rather than real model inference.

Retained artifacts: `data/hanni-reliability-v2-review/m2-development/controlled-before-after.json` and `source-sha256.json`. The original routing corpus hash remains `7de84ea58f8b5ff28510193f9061df3b009c83b540c95c2b10b98155539406b2`; its expected answers were unchanged.

The development gains support this bounded architecture, but do not establish the aspirational 95% unseen recall or 95% workflow-completion goals. Those require final frozen source, the sequestered independent cases and genuine controlled outcome oracles. No final-holdout failure or expected query was revealed for tuning.

