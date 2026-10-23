# Qwen development-150 failure audit

This is a review of **all 25 failures** in the saved 125/150 Qwen3.5-4B run,
not a regrade. The original result remains immutable at
`evals/llm_tools/results/language_v2_qwen_dev150_final.json` (83.33%). The
machine-readable review is `evals/llm_tools/dev150_failure_review.json`, joined
to menus, calls, synthetic results, final answers, and expectations in
`evals/llm_tools/results/dev150_failure_ledger.json`.

| Root cause | Cases | IDs |
|---|---:|---|
| Real model failure | 12 | DIAG-020, DIAG-024, DIAG-028, DIAG-029, DIAG-035, DIAG-042, DIAG-043, SYS-014, CAL-001, CAL-015, MIX-001, MIX-005 |
| Generation degeneration | 2 | DIAG-026, DIAG-027 |
| Evaluator overconstraint | 3 | DIAG-016, DIAG-018, DIAG-019 |
| Missing capability data | 3 | SYS-004, HANNI-003, MIX-002 |
| Missing time evidence | 3 | CAL-019, CAL-020, MIX-004 |
| Tool-result semantics | 1 | DIAG-030 |
| Contradictory mock fixture | 1 | APP-012 |

The three disk-I/O overconstraints require broad CPU/RAM evidence to validate
a claim about high measured process disk I/O, or penalize a relevant disk-health
check. Relaxing them requires semantic tests that still reject unsupported
physical-disk-failure claims. DIAG-035 is **not** an oracle false positive:
although Blender's high CPU usage was identified, the answer falsely called
RAM usage low while the hidden broad snapshot was at 91% RAM and 96% GPU.

The battery cases are structural. Healthy CPU/RAM do not settle a complaint
about running unplugged; the active Power saver plan must remain relevant.
DIAG-026/027 also contain visible repeated-word/digit degeneration. They must
not be counted as successful simply because early fragments contain good data.

The Calendar time cases expose a UTC `fetched_at` and an event's local start,
but not an explicit owner-local current time or time-to-event. Qwen incorrectly
used the UTC clock in one case and compared against event duration in another.
Deterministic `current_local_time` and `minutes_until_start` fields are the
appropriate tool-result improvement. CAL-015 separately submitted raw times
that conflicted with the router's fixed date/time arguments; host enforcement
prevented an actual wrong event, but argument accuracy remains a real failure.

`model.status` currently lacks reliable selected-adapter state, so the model
cannot answer which GPU hosts HANNI by interpreting an empty process list.
APP-012 is a fixture contradiction: it reports playback success while Spotify
is not running and no launch was called. The fixture must model these action
outcomes consistently before an action-completion conclusion is graded.

This audit drives changes at the evaluator, fixture, tool-result-schema, and
model-loop layers. No exact phrase rule is justified by these failures.
