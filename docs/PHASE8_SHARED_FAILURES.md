# Phase 8 — shared-failure analysis

Both models completed the same current-router development and locked holdout
runs. The [case-level intersection](../evals/llm_tools/results/shared_failures_current_router.json)
preserves each report's official failure labels and tool names; this analysis
does not re-score any case.

| Corpus | Shared failed cases | What the intersection shows |
| --- | ---: | --- |
| Development 150 | 20 | 10 diagnostics, 3 Calendar, 3 mixed-domain, 2 app/Spotify, 1 direct-system, 1 HANNI/model |
| Locked holdout 50 | 24 | 21 shared routing failures and 3 failures after a sufficient menu |

The 21 holdout routing failures are the largest shared root cause. Both models
received the same insufficient menu, so substituting a model cannot recover
the missing tool. They include eight mixed-domain requests, six diagnostics,
three app/media, two model-state, one Calendar, and one conversation request.
The current deterministic 1,087-case suite still passes 99.82% strict, which
shows that its coverage does not generalize to these locked phrases. Keep the
holdout unchanged; use a new, versioned development corpus for future router
work.

The 20 shared development failures fall into several different groups:

| Group | Cases | Evidence and likely root cause |
| --- | --- | --- |
| Disk I/O | `DIAG-016`, `018`, `020` | Models either skipped `process.top_disk_io` or interpreted a capacity/health snapshot as activity. `system.performance` advertises disk coverage but its fixture does not expose disk active time. This combines tool choice, result-schema, and fixture limitations. |
| Battery/power | `DIAG-026`–`030` | Both missed the strict oracle. `power.battery_detail` is a relevant read but is excluded from these cases' `acceptable_tools`; some answers also fail to connect Power Saver or unplugged state to symptoms. Review the oracle and causal answer separately. |
| VRAM | `DIAG-043`, `044` | One model skipped evidence or inferred too much from it; both have reasoning/grounding misses. A task ledger would not supply the missing evidence. |
| Calendar | `CAL-015`, `019`, `020` | The creation case has argument errors for both models; the next-event cases have time/reasoning failures, with K2 additionally repeating the same read. |
| HANNI's GPU | `SYS-004`, `HANNI-003`, `MIX-002` | Both tended to use `gpu.top_processes` as if it identified HANNI's assigned GPU. It does not. `model.status` is the expected source, and its present output cannot verify a GPU assignment, so the grounded answer should say that limitation. |
| Spotify/media | `APP-007`, `012` | Both chose or chained an unsuitable previous-track/playback path. Capability wording and stopping behavior deserve a focused development test. |
| Other mixed-domain | `MIX-001`, `004` | Both used tools from both required families. `MIX-001` confused the scenario's fixed “tomorrow” date; `MIX-004` misread the time until class. These are temporal/result-reasoning errors rather than a missing second subtask. |

The three shared holdout failures with a sufficient menu are `PDIAG-006`
(battery/power), `PDIAG-013` (disk I/O), and `PCAL-005` (time before an event).
The first two include stopping penalties and fixture/oracle review points; the
Calendar case is a reasoning miss. K2 alone failed many more development cases,
especially due to repeated tool calls. A shared failure does not prove an
architectural defect: compare each transcript with the actual capability
contract before changing prompts, tools, or scoring.

No shared failure demonstrates that a missing completion ledger is the primary
bottleneck. The [Phase 9 investigation](PHASE9_MIXED_DOMAIN_INVESTIGATION.md)
records that decision. The immediate next remediation work belongs in a new
versioned evaluation cycle: address the 21 router misses, clarify the disk
activity contract and fixed local date, review the power-case oracle, then run
both models against any revised development fixtures. The locked holdout scores
remain the baseline.
