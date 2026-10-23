# Phase 10 — current-router diagnostic investigation

Both Qwen3.5-4B and K2 Horizon 3.7B have now run the unchanged development and
locked holdout corpora on the same RX 6600 XT. The
[current machine-readable subtype matrix](../evals/llm_tools/results/phase10_diagnostics_matrix_current_router.json)
contains per-case official labels and source report hashes. The earlier
[Qwen-only matrix](../evals/llm_tools/results/phase10_diagnostics_matrix.json)
and historical analysis remain below; they came from a different router state.

| Subtype | Dev cases | Qwen dev | K2 dev | Shared dev failures | Qwen holdout | K2 holdout | Shared holdout failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CPU pressure | 5 | 5/5 | 4/5 | 0 | 1/2 | 1/2 | 1 |
| RAM pressure | 5 | 5/5 | 2/5 | 0 | 1/2 | 1/2 | 1 |
| GPU load | 5 | 4/5 | 2/5 | 0 | 1/2 | 1/2 | 1 |
| Disk I/O | 5 | 1/5 | 2/5 | 3 | 0/2 | 0/2 | 2 |
| Healthy/general slowdown | 5 | 4/5 | 2/5 | 0 | 2/2 | 2/2 | 0 |
| Battery/power | 5 | 0/5 | 0/5 | 5 | 0/2 | 0/2 | 2 |
| Render/multi-resource | 5 | 4/5 | 3/5 | 0 | 0/1 | 0/1 | 1 |
| Idle/background CPU | 5 | 5/5 | 3/5 | 0 | 1/1 | 1/1 | 0 |
| VRAM pressure | 5 | 2/5 | 1/5 | 2 | 1/1 | 0/1 | 0 |
| **Total** | **45** | **30/45** | **19/45** | **10** | **7/15** | **6/15** | **8** |

Six of the eight shared holdout diagnostic failures are routing misses: neither
model received the required menu. The other two are `PDIAG-006` (power) and
`PDIAG-013` (disk I/O), where both made extra calls under the strict stopping
rubric. The healthy-machine holdout cases passed for both models without
inventing a resource bottleneck.

The common development weaknesses are disk I/O, battery/power, and VRAM.
`system.performance` advertises a disk snapshot but its fixture gives capacity
and health, not disk active time, so some disk-bottleneck conclusions cannot
be established. All five power cases fail for both models, partly because the
oracle excludes the relevant `power.battery_detail` read and partly because
answers do not consistently connect the active plan to symptoms. K2 has more
strict healthy/general failures, but `DIAG-021` and `DIAG-022` actually conclude
that the machine is healthy; the heuristic grounds neither their rounded
12.5 GB value nor a derived 3.2 GB value. These are rubric-review candidates,
not evidence that K2 invented a bottleneck. Neither corpus tests a causal
Windows-error or model-runtime diagnosis.

The root cause is therefore mixed: retrieval on the holdout, incomplete disk
activity evidence, power-fixture/oracle issues, and model tool-use/reasoning
errors elsewhere. The official strict scores above remain untouched. Review
the scorer and result schemas in a new versioned development cycle before
using those cases to justify a model or architecture change. The
[shared-failure analysis](PHASE8_SHARED_FAILURES.md) groups the individual
transcripts.

## Historical Qwen-only checkpoint

The figures below predate the current-router Qwen and K2 runs and are retained
only to show how the earlier diagnostic conclusions were reached.

This is a **Qwen-only analysis checkpoint**, not a new model run or a model
comparison. It uses the completed, unchanged
[150-case development report](../evals/llm_tools/results/qwen35_4b_dev150.json)
and [50-case personal holdout report](../evals/llm_tools/results/qwen35_4b_holdout50.json).
The [machine-readable matrix](../evals/llm_tools/results/phase10_diagnostics_matrix.json)
records their SHA-256 hashes, locked corpus hashes, official evaluator labels,
and case IDs. Holdout subtypes are assigned from their declared
`source_fixture_archetype`; their wording is new, but their synthetic result
archetypes are reused. Nothing here changes or re-scores either corpus.

| Diagnostic subtype | Qwen development | Qwen holdout | K2 | Shared failures |
| --- | ---: | ---: | --- | --- |
| CPU pressure | 5/5 | 1/2 | Unmeasured | Unknown |
| RAM pressure | 5/5 | 1/2 | Unmeasured | Unknown |
| GPU load | 5/5 | 1/2 | Unmeasured | Unknown |
| Disk I/O | 1/5 | 0/2 | Unmeasured | Unknown |
| Healthy/general slowdown | 5/5 | 2/2 | Unmeasured | Unknown |
| Battery/power | 0/5 | 0/2 | Unmeasured | Unknown |
| Render/multi-resource | 4/5 | 0/1 | Unmeasured | Unknown |
| Idle/background CPU | 5/5 | 1/1 | Unmeasured | Unknown |
| VRAM pressure | 2/5 | 0/1 | Unmeasured | Unknown |
| **Diagnostic total** | **32/45 (71.11%)** | **6/15 (40.00%)** | **Unmeasured** | **Unknown** |

The 13 development failures have overlapping official labels: seven tool
selection, nine reasoning, and six stopping. The nine holdout failures separate
into six routing, two stopping, and one reasoning label. The [current router
audit](../evals/llm_tools/results/qwen_holdout50_routing_checkpoint_audit.json)
still finds those same six diagnostic routing misses after the later language
checkpoint. Historical Qwen answers must not be treated as a run on the current
router, whose menus can differ. Where the menu was sufficient in the historical
holdout run, the official diagnostic success rate was 6/9.

## What the transcripts show

**CPU, RAM, GPU load, idle CPU, and healthy-machine cases are strong once the
menu is sufficient.** All 25 corresponding development cases passed, and the
healthy-machine holdout cases passed 2/2 without inventing a resource
bottleneck. The three CPU/RAM/GPU holdout misses are router misses (`PDIAG-010`,
`PDIAG-002`, `PDIAG-012`), not evidence that Qwen rejected the right tool.
`PDIAG-012` received an unrelated Recycle Bin capability. The six holdout
routing misses sometimes led Qwen to print pseudo tool-call JSON in its answer,
but no real capability was called.

**Disk I/O combines a missing measurement, evaluator constraints, and model
errors.** `system.performance` is described as a CPU/RAM/disk snapshot, but its
`drives` field reports storage fullness, not disk active time or throughput;
`system.stats` likewise has no disk-I/O measurement. The development fixture
profiles define `disk_active_percent: 100`, but the generated MCP results omit
that field. `process.top_disk_io` reports process read/write counter deltas;
it cannot establish that a physical drive is saturated or identify which drive
a process used. This makes a confident disk-bottleneck claim untestable from
the supplied measurements. `DIAG-016` and `DIAG-019` identified heavy OneDrive
I/O but failed the required broad-snapshot evidence check. `DIAG-020` chased
CPU and RAM instead of disk I/O. `DIAG-018` consulted disk health, then
discounted the high I/O despite the user's disk symptom. On the holdout,
`PDIAG-004` had no menu; `PDIAG-013` made a plausible OneDrive diagnosis but
was penalized for a `disk.usage` call. Its claim about the game drive being
affected goes beyond what process-wide I/O deltas can prove. A better tool
description could distinguish storage fullness from activity, but description
alone cannot supply the missing measurement.

**Battery/power has a scoring mismatch and incomplete causal reasoning.** The
five development battery cases and `PDIAG-006` called
`power.battery_detail`, which confirms unplugged state and charge. Their
scenario `acceptable_tools` lists exclude that relevant read, so the evaluator
marks it an unnecessary call and all six fail strict success. That does not
make every answer good: `DIAG-027` and `DIAG-028` never checked the active
power plan, and `DIAG-028` merely reported the battery state without answering
why the laptop was slow. `DIAG-026` saw Power Saver yet downplayed its possible
effect. Some answers call a 62% battery "low" or speculate about battery
degradation without evidence. `PDIAG-015` only received a battery-status menu,
so the model had no way to verify its claim that the OS was throttling.

**Render and VRAM failures expose actual tool-use weaknesses.** `DIAG-035`
queried process lists but skipped the broad CPU/RAM/GPU snapshot; it inferred
that overall memory was low from a single process's 2 GB RSS, even though the
fixture's total RAM usage was 91%. `PDIAG-007` failed at routing before Qwen
could investigate. For VRAM, `DIAG-042` read GPU memory but did not inspect the
contributing process. `DIAG-043` called no tool, supplied generic explanations,
and suggested deleting game save/cache data without system evidence; the
heuristic `unsafe_guidance` check did not flag that advice. `DIAG-044` used the
right tools and identified VRAM pressure but stated an unsupported 99.6% figure.
`PDIAG-009` also used the right tools and gave the right broad conclusion;
its numeric grounding check rejects derived 15.46 GB and 99.4% values. The
15.46 decimal-GB conversion is defensible from 15,462 MB, while calling 99.4%
VRAM occupancy "GPU utilization" confuses memory fullness with the separately
reported 91% GPU-engine utilization. These are reasons to review the rubric
and wording, not to silently change the locked holdout's score.

**Windows-error and model-runtime diagnosis are unmeasured subtypes.** The
development corpus has direct status questions such as `SYS-014` and
`HANNI-009`, but neither the 45 development diagnostic cases nor the 15
holdout diagnostic cases test a causal Windows-error or model-runtime
investigation. No success rate should be inferred for those subtypes.

## Root-cause decision

The evidence does not support one universal fix or a claim that Qwen has a
general 4B reasoning ceiling. The holdout's largest measured diagnostic loss
is **retrieval**: six of nine failures lacked the required menu. In the
development run, the largest substantive weaknesses are disk-I/O evidence
handling, power-plan completion, and temporal VRAM tool use. The disk fixture
and some oracle rules limit how cleanly those model weaknesses can be measured.
No single tool description explains all failures; `system.performance` is the
clearest contract mismatch because its advertised disk coverage can be read as
disk activity while its output provides only capacity.

Do not alter the locked holdout, retrospectively change official scores, or
add a task-completion ledger from this Qwen-only analysis. The next controlled
experiment is to serve K2 through a compatible local runtime, then rerun both
models on the same **current** router, unchanged corpora, mocks, prompt, and
round limits. After that comparison, test proposed tool-description and
fixture/oracle changes on a new versioned development corpus, with explicit
disk-activity evidence, power-plan evidence, and Windows/model-runtime
diagnostic coverage. Tool Intelligence V1 remains unfrozen; V1.1 capability
expansion remains gated.
