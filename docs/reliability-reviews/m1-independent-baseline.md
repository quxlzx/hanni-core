# Reliability & Intelligence V2: independent M1 baseline

The current frozen original source is commit `791bdab9e4921e2958c20b55fdfadb7ce44e04d6`. No production feature was edited by this verifier. The baseline is **PASS: 964 tests, 17 subtests and two skips**, with zero failures/errors in 118.810 seconds. JUnit contains 983 entries and is retained at `data/hanni-reliability-v2-review/baseline-full.xml`. `npm run check` passed. No frontend build or native GUI was started during this audit.

## Evidence boundaries and architectural findings

The live assistant uses the original CLI binding, `McpHost.route` metadata discovery/ranking and `McpToolSession` model/tool loop. `ToolRegistry` retains argument validation, profile/confirmation, emergency stop, mutation serialization and redacted audit. MCP manager adapters join this registry and retain original schema/hash identities. There is no reason to introduce a second execution pipeline.

Existing routing evaluation deliberately uses a metadata registry whose handlers/execute methods reject execution. It scores candidate menus, policy exposure and deterministic arguments. It cannot establish model selection, handler correctness, successful execution or independently verified task completion. Existing real-model evaluators also use synthetic tool responses and lexical claim checks; their environment/seams must be disclosed when cited.

`CompletionLedger` currently marks any relevant successful read as completed; calendar creation checks a returned created boolean, app completion accepts process_started, and some media actions check observed state. These statuses do not provide a general independent read-after-write guarantee. Registry timeout/retry fields exist as metadata but the handler execution method itself does not enforce those fields. The current Activity projection primarily maps tool-audit success/failure rather than a request-linked general verification lifecycle. These findings agree with Worker 2's independently reproduced development defects; no final-holdout failures are shared for development.

## All default registered capabilities

[baseline-capability-coverage.csv](baseline-capability-coverage.csv) contains all **172** capabilities registered by the original configured default registry, with domain, risk/permission, policy exposure, static test mentions and observed routing counts. Full per-case metadata is retained in `data/hanni-reliability-v2-review/baseline-metadata/capability-coverage.json`.

The historical development routing corpus has **1,131 cases**, **1,129 strict passes (99.823%)**, mean score **99.590/100**. It exposed 132 distinct default capabilities in menus. Sixty-eight capabilities have exact literal mentions in Python test source; this is only a static search signal, not proof those tests execute a handler. Model-selection, handler-execution and outcome-verification columns deliberately remain NOT_MEASURED.

The inventory does not fabricate runtime-attached desktop management or imported MCP registrations. Desktop fixed-management definitions are registered lazily, and enabled external definitions depend on the isolated manager state. A runtime snapshot must extend the matrix when those definitions are actually registered. Existing historical/synthetic inventories with other counts require scope reconciliation, not silent substitution.

## Untouched final holdout protocol

A verifier-private persistent directory contains an immutable original-HEAD git archive, 60 newly authored final cases and baseline row artifacts. Root/workers receive only this manifest and aggregate results before final source freeze. Queries, expected answers and individual failures remain sequestered; they must never be used for development, retuning, candidate threshold choices or debug examples. No expected answer may change after baseline observation. Once disclosed at final reporting, the corpus is future-contaminated and cannot be called untouched again.

- Final corpus SHA-256: `b1ccb0aa512a95f418582d7bc7814f096af6788be7da7f13e3bbd686ae433d25`.
- Original archive SHA-256: `b1ec49fe585abcc1b46e05d8b3c145e68a05f568fd16ae824cf7b2658e2d10ee`.
- Samples: **60**, including 44 tool requests and 16 no-tool/ambiguous/forbidden/unavailable cases.
- Category counts: ambiguous 4, broad_diagnostics 4, calendar 4, dynamic_mcp 4, files 4, forbidden 4, indirect_slang_typos 8, model_status 4, multi_domain 4, multiple_valid 4, no_tool 4, precise_diagnostics 8, unavailable_mcp 4.
- Exact query substring matches against existing repository evaluation JSON/JSONL content: **zero**. This check does not prove absence from external model training data or semantic similarity.
- Fixed clock: 2026-10-09 09:00:00 America/New_York.
- Original config copies and source-import identity are pinned in private artifacts.
- Original and final execution will use identical cases/oracles, configured Qwen3.5-4B-Q4_K_M, runtime settings and hardware where safe; differences must be explicitly labeled.
- Reporting uses actual denominators and Wilson 95% confidence intervals, with model/argument/outcome/latency separated.

Original-snapshot **metadata-only** holdout retrieval: menu sufficiency **28/44 (63.64%; Wilson 95% 48.87–76.22%)**; correct no-tool **11/16 (68.75%; 44.40–85.84%)**; **zero forbidden menu exposures**; mean candidate count 1.383; conservative irrelevant exposure count 49; observed retrieval P50 approximately 1.19 ms and P95 approximately 4.99 ms. These timings are a single same-process pass, not end-to-end/model latency. Independent oracle acceptable sets are conservative, so extra potentially useful evidence is counted as non-required exposure rather than a permission violation.

The private retrieval probe executes the genuine original host using non-executable metadata and one synthetic dynamic capability solely for index registration/withdrawal. It invokes no model, provider, app, microphone, node or production handler. A harness ownership correction was made before freezing the baseline artifact: registry registration snapshots definitions, so withdrawal must use the actual registered object and assert success. Case expectations remained unchanged. No metadata-only value is presented as unauthorized execution or verified task success.

## Remaining evidence and next verification steps

Actual configured-model selection, arguments and completion are **not measured by this initial metadata audit**. The original snapshot is retained so they can be measured with controlled fixtures before comparison without holding implementation work. Root will coordinate the original configured model, same hardware/config, isolated data and safe adapter fixtures. Worker 2's 30–50 development workflows need per-stage oracles and both-version replay; plausible text alone cannot pass. Real registry authorization/audit must remain active even when provider/OS adapters are mocked.

Next: independently audit workers' source changes, run their workflows with real permission boundaries, measure frozen final source on the untouched cases exactly once, compare paired outcomes and latency, and inspect genuine native Activity records after root releases GUI ownership. Final findings must distinguish original live-model inference, deterministic test clients, fixture adapters and genuinely observed backend outcomes.

The five unrelated untracked root artifacts remain untouched. No push/publish, production runtime startup or real remote action occurred. Original source and final corpus remain preserved for safe resumption; the verifier session retains their private directory reference. This M1 evidence is checkpoint-ready.

