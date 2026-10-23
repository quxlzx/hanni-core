# Reliability V2 controlled development comparison

The frozen current implementation passed the independent outcome assertions for
18/18 positive development workflows, compared with 14/18 in the archived
original. Both deliberately injected transient read failures recovered with one
retry. The repeated ambiguous-action fixture issued one action attempt instead
of four. These are exposed deterministic development fixtures, not a measurement
of configured-model intelligence or unseen-language performance.

## Conditions and reproducibility

The same frozen 40 fixtures and controlled model client ran once against original
commit `791bdab`, archived at
`data/hanni-reliability-v2-review/original-source`, and once against the current
frozen source. The root coordinator reserved a quiet interval with no concurrent
full regression, live model or native GUI work. Both runs used the same
configuration, Python environment and machine. No production model, provider,
microphone, screen capture or user application was started.

File, task, note and memory checks use genuine isolated local stores. Diagnostic
measurements and application-launch boundaries use controlled handlers. Calendar
checks use the original provider adapter with an injected transport and event
ledger. MCP uses the official SDK and local stdio fixture. Original registry,
host, session and authorization paths remain in the execution pipeline.

For a fresh checkout, create the original source archive first. The comparator's
`--original-root` option can instead point to an existing `791bdab` checkout.
This workflow baseline differs from the separately isolated `ca95b05` retrieval
host baseline used below.

```powershell
New-Item -ItemType Directory -Force -Path data/hanni-reliability-v2-review | Out-Null
git archive --format=zip --output=data/hanni-reliability-v2-review/original-source.zip 791bdab
Expand-Archive -LiteralPath data/hanni-reliability-v2-review/original-source.zip `
  -DestinationPath data/hanni-reliability-v2-review/original-source
.venv\Scripts\python.exe scripts/reliability_review/compare_workflows.py `
  --output data/hanni-reliability-v2-review/workflow-comparison
```

The comparator refuses mismatched cases or changes to runtime source, runner,
workflow fixtures or SDK fixture during execution. It preserves every case and
failure, explicit true/false/not-applicable stages and recorded evidence scopes.
No holdout file was accessed. The artifacts are `comparison.json`,
`comparison.md`, `before/workflows.json` and `after/workflows.json` under the
output directory; the generated artifacts remain unchanged.

| Captured input | SHA-256 |
|---|---|
| Workflow fixtures | `3e4715bed34d74bd3613ac1bab23a6a83a46960df63215d403ca92c35dbb279e` |
| Runner | `5f8efe310ee8811275114c2722834801597e5e2be19998da1bf343b8a28b6f0d` |
| SDK fixture | `5e5a0c566fc67963fbbc75b10cedbc1fd6196d8d3a8fcabe8b24d4fc7426abc8` |
| Original runtime packages | `1c21392b39f218f85e64b9c7abdcad4dbdfcc414d96f77711be7162f7893baa9` |
| Current runtime packages | `7312c0326157d85afe8aaf0ec0a615056b5590d669314644c406dfbc40af9109` |

## Outcomes and their limits

Intervals below are 95% Wilson intervals over exposed fixtures. They describe
these counts rather than representative real-world success probabilities.

| Measure | Original | Current |
|---|---|---|
| Positive outcomes checked by fixture evidence | 14/18, 77.8% (54.8–91.0%) | 18/18, 100% (82.4–100%) |
| All strict pipeline expectations | 29/40, 72.5% (57.2–83.9%) | 40/40, 100% (91.2–100%) |
| Safe-refusal expectation handling | 7/8 (52.9–97.8%) | 8/8 (67.6–100%) |
| Expected-failure handling | 5/10 (23.7–76.3%) | 10/10 (72.2–100%) |
| Unverified-receipt handling | 3/4 (30.1–95.4%) | 4/4 (51.0–100%) |
| Injected transient-read recovery | 0/2 (0–65.8%) | 2/2 (34.2–100%) |
| Application-recorded VERIFIED positive scopes | N/A: 18/18 unrecorded | 16/18, 88.9% (67.2–96.9%) |

The 40 pipeline passes include refusals, failed checks and receipt-only handling;
they are not 40 completed positive tasks. The positive outcome metric checks
actual fixture facts, file contents/state, local persistence or provider/SDK
ledgers rather than plausible model prose. It still does not establish real
OS/application/provider outcomes beyond the controlled boundary.

The original has no recorded verification for any of its 18 positive cases.
The generated artifact's zero recorded VERIFIED count means missing
instrumentation, not zero verified original outcomes. Current evidence records
16 VERIFIED scopes, one UNVERIFIED external MCP response and no application trace
for the memory wrapper. The fixture independently observes the memory SQLite
fact and actual SDK echo response. Neither observation grants the external tool
independent real-world verification; its final reply remains explicitly attributed
to the server.

There are 11 strict pipeline improvements and no regressions. Independent review
identified two lexical false negatives in the original `app-missing` and
`app-permission-denied` final-answer checks: both original replies already said
the action could not be verified. Their improved specificity is not evidence of
fixing an original false-success claim. The exact raw 29/40 and 40/40 artifacts
are retained, and no oracle or case was changed after the paired run.

The four positive gains are file-path retrieval, approved MCP operation retrieval,
calendar read recovery and diagnostic read recovery. Current recovery ledgers
show exactly one extra read attempt in each recovery fixture. The original
ambiguous repeat-action fixture records four launch-boundary attempts, versus
one currently: three observed repeated side effects become zero. This is a
controlled deduplication test, not a guarantee about every real side effect.

Unauthorized sensitive-execution totals are **not measured** by this runner:
both reports have 0/40 cases exposing that aggregate field. Owner-profile stage
checks and existing gate regressions must not be presented as a measured zero
unauthorized-execution rate. Intent understanding is also not measured because
the client chooses scripted tools. No final holdout or real-model score is
included in this report.

## Stage evidence and latency

| Applicable stage | Original | Current |
|---|---:|---:|
| Intent understanding | Not measured | Not measured |
| Retrieval | 29/31 | 31/31 |
| Scripted tool selection | 24/26 | 26/26 |
| Observed arguments | 30/30 | 31/31 |
| Applicable authorization checks | 35/35 | 36/36 |
| Execution expectations | 38/40 | 40/40 |
| Outcome expectations, including safe failures | 35/40 | 40/40 |
| Strict final-answer expectations | 25/36 | 36/36 |

Different denominators reflect not-applicable or unobserved stages, not removed
cases. Four fixed voice/screen boundary checks have no generated final answer.

| Setup plus controlled controller/execution latency | Original | Current |
|---|---:|---:|
| P50 | 14.070 ms | 33.192 ms |
| P95 | 751.395 ms | 783.586 ms |

Paired per-case latency deltas have P50 +17.307 ms and P95 +34.004 ms. Percentiles
use linear interpolation. These timings include setup, stores, traces and local
SDK startup; they exclude model inference, voice latency and actual application
startup. The reliability evidence adds measurable overhead in this replay.

## Historical retrieval compatibility

The separate metadata-only retrieval comparison uses the original M1 host from
`ca95b05`, the same current registry and original fixture-owner timezones. Three
warm passes precede five interleaved measurement passes. The complete audit
checks extra unmocked tools and resolved arguments as well as required recall.

| Existing development check | Original M1 | Current |
|---|---:|---:|
| Historical routing cases passing | 1129/1131 | 1129/1131 |
| Complete historical scenario audit | 194/194 | 194/194 |
| Complete capability/schema corpus audit | 264/264 | 264/264 |
| Registered built-ins / model-facing capabilities | 172 / 132 | 172 / 132 |

Historical mean routing score changes from 99.5904 to 99.5727 because of additional
allowed candidate exposure. The explicitly development unfamiliar corpus improves
required-tool recall from 23/35 to 31/35; no-tool decisions remain 4/5. The generic
framing-word repair restored complete old-corpus compatibility but lost one
development recall case from an earlier candidate. It does not meet the proposed
95% unseen-recall target. See [Tool Intelligence V2](TOOL_RETRIEVAL_V2.md) for the
retrieval method, microbenchmarks and limitations.
