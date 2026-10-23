# Phase 9 — mixed-domain completion investigation

Qwen and K2 each passed 6/10 development mixed-domain cases and 2/10 locked
holdout cases. The equal percentages conceal different cases and causes. The
same deterministic router failed eight of the ten holdout mixed-domain
requests for both models; the two with sufficient menus passed for both.
That is a retrieval problem, not evidence for a model-side completion ledger.

Three development failures are shared:

| Case | Calls from both models | Why the task failed |
| --- | --- | --- |
| `MIX-001`: “what do i have tomorrow and how much ram am i using” | `google_calendar.agenda`, `system.stats` | Both covered both domains but passed September 25 for a scenario anchored on September 23, whose “tomorrow” is September 24. HANNI's fixed date override kept execution synthetic and corrected the effective argument, but the models interpreted the returned event as the wrong day. K2 repeated Calendar unnecessarily. |
| `MIX-002`: “open spotify and tell me what gpu hanni is on” | `spotify.launch`, `gpu.top_processes` | Both opened the synthetic Spotify state, then used a process list to infer HANNI's GPU. The process list cannot identify HANNI's assigned adapter; `model.status` also does not currently verify that assignment, so the grounded answer should state the limitation. |
| `MIX-004`: time until next class plus RAM consumer | `google_calendar.next`, `process.top_memory` | Both obtained the requested domains but gave the wrong time-to-class conclusion. K2 made an extra `system.stats` call. |

The nonshared cases point the same way. Qwen failed `MIX-005` by using a CPU
process snapshot instead of the broad system status that K2 used successfully.
K2 failed `MIX-003` after an extra call while Qwen passed. The corpus has no
shared development failure where both models simply forgot an outstanding
subtask after completing the first.

**Decision: do not add a task-completion ledger in Phase 9.** It would add
state and another completion rule without addressing the measured dominant
failures: missing holdout menus, wrong tool semantics, fixed-date confusion,
and time arithmetic. Keep the current bounded MCP loop and frozen router.
A ledger can be reconsidered only after a new versioned experiment shows
repeated omission of a second subtask with both required capabilities present
and otherwise correct tool results. The locked holdout remains unchanged.
