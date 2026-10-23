# Routing language and safety checkpoint — 2026-09-24

This checkpoint changes HANNI's existing routing vocabulary and Google CLI
console output, with focused regression tests. It does not add capabilities,
change the resident Qwen configuration, execute a capability during evaluation,
or alter either locked evaluation corpus. The
source snapshot has no `.git` directory, so there is no commit to identify or
push. The saved reports and corpus locks provide the resumable record.

## Measured result

| Routing corpus | Before | After | Scope |
| --- | ---: | ---: | --- |
| Original 1,087 cases, strict pass | 99.82% | 99.82% | Complete registry benchmark |
| Fresh 30-phrase development probe, strict pass | 53.33% | 93.33% | Owner-style phrases; locked before first run |
| Probe blocked actions | 3/5 | 5/5 | Route-only; no action executed |
| Probe mixed-domain requests | 1/7 | 6/7 | Both capability families retrieved |

The main benchmark still has two Spotify cases that penalize `spotify.status`
and `spotify.launch` as irrelevant alongside `spotify.play_pause`. The probe
still has two failures: `PROBE2-013` expects `disk.free_space` for “how full is
my c drive,” although the retrieved `disk.usage` reports free/used space and
percentage full; `PROBE2-030` treats “book dinner friday 8pm” as a Calendar
creation request, though it could also mean a restaurant reservation. Neither
oracle was changed merely to increase the score. The probe CLI exits 1 because
its 30 cases do not cover all 150 registry capabilities; the pass rate and
per-case results in its JSON report remain valid. Use the 1,087-case report for
the complete coverage check.

The narrower routing changes recognize `end` on processes, `flip` on power
plans, consent questions, `fire up`/`bring up` launches, casual calendar clauses,
low GPU-memory questions, and an app-launch-then-Spotify-play request. The
restricted requests still yield no model tool menu. The new regression tests
also keep Calendar event titles such as “dinner and a movie” intact.

## Tool-loop evidence remains separate

The last completed live Qwen run remains **125/150 (83.33%)** on development
and **23/50 (46.00%)** on the locked personal-language holdout. Those runs
precede this routing change and cannot be presented as a current live score.
The configured `127.0.0.1:8080` endpoint was not listening in this session,
and this checkout does not contain the Qwen GGUF, so no new Qwen inference ran.
The current corpus audits are saved: 150 development scenarios have zero
routing/mock failures; the unchanged 50-case holdout has 21 routing/no-tool
misses, down from 22 before this checkpoint. It has no unknown capability,
missing mock, or routing-context errors. The holdout is retained as historical
evidence, not used as a tuning set.

K2 remains unavailable: the verified GGUF exists, but the installed llama.cpp
runtime does not recognize `k2-horizon`. There is no K2 task score or model
comparison. **Tool Intelligence V1 is not frozen**, and no V1.1 capability
batch has started. Production remains Qwen3.5-4B.

## Validation and artifacts

The final full suite passed: **452 passed, 1 skipped, 17 subtests passed**.
The complete 1,087-case benchmark scored 99.66 average and 99.82% strict,
with 100% strict blocked-write coverage. The 30-phrase probe scored 95.73
average and 93.33% strict. The `hanni google login/status/logout --help`
commands all worked. A real local `google status` check initially failed on a
Unicode checkmark in this Windows console; the CLI now uses ASCII labels and
the same status command exits successfully. A strict `cp1252` console test
covers login, status, and logout output with mocked OAuth. The local status
check did not contact Google, and no real login/logout was performed.

- Complete routing report: `evals/routing/results/routing_checkpoint_v4_1087.json`
- Complete capability coverage: `evals/routing/results/routing_checkpoint_v4_coverage.json`
- Fresh phrase report: `evals/routing/results/phrase_probe_v2_checkpoint_v4.json`
- Phrase corpus lock: `evals/routing/phrase_probe_v2.lock.json`
- Qwen development audit: `evals/llm_tools/results/qwen_dev150_routing_checkpoint_audit.json`
- Locked holdout audit: `evals/llm_tools/results/qwen_holdout50_routing_checkpoint_audit.json`
- Historical live Qwen reports: `evals/llm_tools/results/qwen35_4b_dev150.json` and `qwen35_4b_holdout50.json`
- Exact changed-file list and SHA-256 hashes: `evals/routing/results/routing_language_checkpoint_manifest.json`

Next: obtain a verified Windows runtime that can serve the existing K2 GGUF
through the same local tool API, run both unchanged corpora, and compare those
results with Qwen. A new, independent development set should drive any further
routing changes; the personal holdout must stay locked.
