# V3 M0 independent baseline

**M0 measurement: PASS. Autonomous V3 acceptance: NOT TESTED.** Baseline is `aa50409b0002cb66b799bf6824431131b8d9d708`, captured before production edits. No new autonomous executor exists in this baseline, and passing current boundaries does not establish 95% autonomous completion.

The independent verifier read the entire V3 brief, reran the original suite without profiling, checked frontend types without rebuilding, preserved the existing forty workflow cases and oracles, and added four narrowly scoped model-runtime/cluster interface checks. No production code was edited. No model, cloud/provider request, SSH, node power action, voice capture, production assistant or actual app launch was started.

## Fresh regression and source provenance

| Check | Observed result |
|---|---|
| Original full pytest | **1,057 passed, 2 existing skipped, 17 passed subtests**; zero failures/errors |
| JUnit | `data/hanni-v3-review/baseline-full.xml`; 1,076 entries, suite time 143.030 s |
| Frontend `npm run check` | PASS (`tsc --noEmit`); no build |
| Runtime/config manifest | 171 files; SHA256 `534e106c1d8971235a281c18d6ceebf5b0f45cad56a0b09371cb46d0f66dde32` |
| Immutable original Git archive | SHA256 `9dd3417721452df68a84b773c647d2a6dbb3450075adb609ae5974abc349ba16` |
| Source archive and extracted tree | `data/hanni-v3-review/baseline-source.tar`, `original-source/` |
| Per-file hashes | `data/hanni-v3-review/baseline-manifest.json` |

The runtime manifest covers all `src/hanni` Python and repository YAML/JSON/TOML configuration, including CLI, original controller, registry, permissions, MCP and reliability code. Compiled frontend assets, lockfile, case fixture and both runners have separate hashes in the manifest. The original forty-case fixture SHA remains `3e4715bed34d74bd3613ac1bab23a6a83a46960df63215d403ca92c35dbb279e`; its runner SHA remains `5f8efe310ee8811275114c2722834801597e5e2be19998da1bf343b8a28b6f0d`. Neither original inputs nor expected answers were modified.

## Practical 44-case suite

**44/44 case assertions passed.** These are 40 exposed controlled DEVELOPMENT workflows plus four original-interface safety/status boundaries. They are not 44 completed objectives or unseen intelligence tests. Results are `data/hanni-v3-review/m0-workflows/workflows.json`, `m0-boundaries.json` and `m0-case-matrix.csv`.

The forty original workflows run through the original host/session/registry, actual authorization gates, isolated filesystem/task/note/memory stores and an official SDK MCP fixture. Their model choices are scripted. Diagnostic/app handlers and Google transport are controlled seams. Voice and screen cases assert unsupported/safe-mode boundaries; they do not prove hardware input or visual analysis.

| Original workflow category | Cases | Baseline outcome |
|---|---:|---|
| Positive objectives | 18 | **18/18 independent fixture outcomes**, but **16/18 HANNI-recorded VERIFIED scopes** |
| Expected safe refusals | 8 | 8/8 expected refusal assertions |
| Expected failures/recovery handling | 10 | 10/10 expected handling assertions |
| Explicit unverified receipts | 4 | 4/4 conservative receipt assertions |

Memory's explicit storage fast path has no observed task verification record; its stored value is independently checked. The MCP read returns the expected text through the real SDK fixture but remains HANNI-UNVERIFIED for an independent remote outcome. Therefore the baseline does **not** meet a 95% application-recorded fully verified objective target: 16/18 is 88.9%, and this small exposed fixture set is insufficient evidence for generalization. Those two records must not be silently reclassified as VERIFIED to meet a target.

Wilson 95% intervals are 82.4–100% for independent positive outcomes (18/18), 67.2–96.9% for HANNI-recorded VERIFIED scopes (16/18), and 92.0–100% for the heterogeneous 44 assertion results. The last interval describes boundary assertions, not objective completion; none proves a general 95% autonomous success rate.

| Stage | Passed / applicable | Scope |
|---|---:|---|
| Intent understanding | NOT MEASURED | Scripted model/structured inputs |
| Retrieval | 31/31 | Original controlled requests requiring discovery |
| Tool selection | 26/26 | Scripted model, not actual model judgment |
| Arguments | 31/31 | Fixed controlled arguments/oracles |
| Authorization | 36/36 | Case-specific original-gate assertions; no aggregate sensitive-call denominator |
| Execution expectations | 40/40 | Includes expected denial/failure, not forty successful actions |
| Independent all-kind outcome assertions | 40/40 | Positive subset is 18/18 |
| Final response assertions | 36/36 | Four voice/screen boundary responses are not graded |

Two explicit safe transient reads recover within the original bounded retry, and the ambiguous write fixture has zero duplicate side effects. Controlled setup-plus-pipeline P50 is 36.013 ms and the runner's P95 is 783.064 ms. These are descriptive single-pass timings including fixture/store/SDK setup, excluding actual model inference; no speedup claim or autonomous planning/verified-objective timing is available.

The four additional cases use public injection seams in the original `ModelManager` and `ClusterMonitor`; no competing model controller or remote executor is introduced:

- Low available RAM rejects startup, a second attempt remains in cooldown, and no launcher runs.
- An injected healthy external endpoint is leased without adoption as an owned process and without stopping it on close.
- Eight injected node samples are recorded, the repairing member is never probed, and snapshots do not expose mutable internal history.
- Probe failures leave measurements unavailable, without converting unavailable CPU/RAM into zero or invented history.

For these four interface checks, natural-language intent, retrieval, model choice, authorization, and final response are not measured. Their PASS is not added to the positive-objective denominator.

## Genuine local reads and remaining gaps

Four real original registry handlers (`time.now`, `system.stats`, `process.top_memory`, `process.top_cpu`) passed bounded read-only smoke validation on current Windows hardware; no handler was replaced. Sanitized evidence is `data/hanni-v3-review/m0-real-reads.json`, with unchanged runtime manifest before/after. Process names, raw results and user files are not exported.

No foundational unsafe failure was found in this fresh regression/practical pass. However, baseline V2 retains documented intelligence and coverage gaps: its now-public language set missed required-tool recall targets, most capabilities lack genuine OS/provider outcome evidence, turn-local duplicate suppression is not cross-process exactly-once delivery, and the existing SQLite traces are observational metadata rather than durable resumable goals/approved plans. There is no current crash-resumable DAG, bounded background workflow authorization, workflow approval expiry, dependency scheduler, or actual Workflow UI to accept. These are V3 work and require independent safety verification before autonomous acceptance.

The original reliability observer intentionally preserves unknown/corrupt storage without granting authority or replaying actions. Historical pending chat approvals do not resume as fresh authority. V3 must preserve these safeguards rather than treating a persisted observational trace as a resumable execution plan.

## Sequestered planning evaluation

Eighteen new isolated multi-step goal/oracle cases were sealed before V3 implementation. Only count and hash are disclosed to implementation agents: SHA256 `5c839ed7e406d6fbc77384be0c4698100bdbf1316d95c21ca4f95e7ffa445758`. The private case bytes remain in verifier-owned persistent storage; `data/hanni-v3-review/planning-seal-manifest.json` records the protocol. No contents are used to tune production logic. An adapter may target public engine interfaces, but frozen case/oracle content cannot be changed to match outputs. Final execution requires source freeze; unsupported interfaces remain BLOCKED/NOT TESTED. Publication, if requested, occurs only after final scoring and contaminates future development use.

The V2 final language holdout is already published and is therefore an exposed regression corpus, **not** fresh unseen evidence for V3. The practical forty-case suite is also exposed development material. Native screenshots and durable workflow crash/approval/revocation/prompt-injection/resource tests will be assessed on genuine isolated engine activity after coherent implementation freeze.
