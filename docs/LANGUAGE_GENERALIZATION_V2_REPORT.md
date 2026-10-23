# Language Generalization V2 checkpoint

Status: **Tool Intelligence V1 NOT READY TO FREEZE**. This report is updated
from saved, reproducible benchmark artifacts. The production model remains
Qwen3.5-4B Q4_K_M; no capability batch was added.

## Evidence boundaries

The 1,087-case routing suite is a frozen regression set. The 200-case
Language Generalization V2 set and 50-dialogue set are **development** corpora,
not blind holdouts. Holdout V1 is historical regression evidence. A blind
Holdout V2 has not been created: the development model run and coverage gate
must be reviewed first, and the corpus must then be locked before inference.
The Qwen tool evaluation runs the actual local model against exclusively
synthetic MCP results. No capability handler is executed.

The owner timezone remains `America/Chicago`, matching the explicit current
configuration and the prior owner decision. Corpus timestamps are fixed per
case; production timezone was not rewritten to match fixture dates.

## Routing

| Suite | Cases | Strict success | Average score | Role |
|---|---:|---:|---:|---|
| Frozen regression | 1,087 | 99.82% | 99.64/100 | Backward compatibility |
| Language Generalization V2 | 200 | 100.00% | 99.28/100 | Inspectable development |
| Multi-turn V1 | 50 dialogues, 108 turns | 100.00% dialogue | 100.00% turn | Inspectable development |
| Sanitized voice regression | 15 | 100.00% | 96.89/100 | Inspectable development |

The V2 development corpus has 100.00% required-tool recall, 100.00% mixed-domain
family recall, and 0.00% no-tool false positives. Ten Calendar cases pin exact
resolved dates, event titles, and start/end times. These are **tuned development
figures** and do not establish unseen-language generalization. The frozen suite
still has two Spotify precision misses. Results are in
`evals/routing/results/`.

Language changes add context-bound app/media concepts, generic media controls,
bounded clause splitting, short-turn target inheritance through the existing
120-second session history, and conservative clarification on ambiguous bare
commands. Permission checks and action allowlists still live in MCP/registry.
The optional `hanni eval routing-debug` command shows deterministic normalized
text, clauses, families, menu, and fixed arguments without model reasoning or
tool execution.

## Historical Holdout V1

The earlier live Qwen result was 25/50 (50.00%). The current rerun passed
**21/50 (42.00%)**, average score 63.90/100, tool selection 58.00%, arguments
96.00%, and reasoning 48.00%. Of 29 failed cases, 12 missed the expected MCP
menu and 17 failed after receiving a valid menu. The routing/mock audit found
no missing mock implementations. This is a measured regression against the
earlier run, although the router and mock baseline changed between runs. This
corpus is historical regression material, not a blind freeze gate; its
individual phrases were not used as tuning cases.

## Live model and personality

The first live Qwen development run on this milestone passed 123/150 (82.00%).
After correcting the menu and mock fallback, the final run passed **125/150
(83.33%)**, average score 90.83/100. Tool-selection accuracy was 90.67%,
argument accuracy 97.33%, reasoning accuracy 88.00%, average 1.31 calls and
3,064.51 ms per case. Hallucinated-tool and unsupported-claim *heuristic flags*
were both 0.00%; transcript review is still needed for semantic certainty.
Qwen ran at the configured Q4_K_M quantization with a 16K context.

| Family | Task success |
|---|---:|
| Diagnostics | 71.11% |
| Direct system | 90.00% |
| Calendar | 80.00% |
| Applications/Spotify | 93.33% |
| Files/search | 100.00% |
| HANNI/model | 90.00% |
| Mixed domain | 60.00% |
| Conversation | 100.00% |
| Safety | 100.00% |

The final development run had **zero routing failures**. All 25 failed cases
received the expected menu; 14 had model tool-selection failures, 20 reasoning
failures, 9 stopping failures, and 3 argument failures (categories overlap).
The concentration is diagnostics (13 failures) and mixed-domain (4 failures).
The router score cannot substitute for task success through Qwen tool calls.
See `evals/llm_tools/results/language_v2_failure_analysis.json` for case IDs.

Personality V1 is a short, configurable suffix to the existing safety and
grounding prompt. Its 80-case synthetic corpus and paired A/B runner save
responses for human review. A stratified 20-case live Qwen A/B completed with
40 successful model calls and no endpoint errors. The neutral baseline averaged
15.7 words and 1,088.3 ms; Personality V1 averaged 19.2 words and 1,319.2 ms.
The simple customer-service phrase detector flagged 0 baseline replies and 1
personality reply; neither side triggered its identity-overreach detector.
These are style proxies, not a personality score or task-success measurement.
The numeric proxy flagged three replies on each side, including correctly
converted 24-hour calendar times, so those flags require manual review.
In the `PV1-076` follow-up, **both** prompts claimed Spotify had resumed even
though the fixture contained only the prior pause result. That unsupported
action claim is a real grounding limitation of this prompt-only comparison;
the A/B does not prove personality is safer or more accurate. Manual review
also found a made-up account of HANNI's day, an unsupported CPU-to-RAM causal
claim, and a 2 PM event described as being tonight. The baseline made similar
errors on those fixtures, so these are shared prompt/evidence problems rather
than evidence that the style suffix alone caused them. The personality suffix
is enabled but remains explicitly provisional.

## Capability and performance audit

All 150 registry capabilities expose required metadata and JSON object input
schemas. Every existing capability has at least two routing regression probes;
the regression policy blocks future additions without two routing probes and
two LLM scenarios. Existing LLM coverage is incomplete: 17/150 capabilities
have at least two required-tool scenarios, 24 have one, and 109 have none.
That gap remains a freeze limitation; no filler cases were added to conceal it.

Across 1,000 deterministic routes over the 200-case corpus, mean routing time
was 1.449 ms, p95 4.610 ms; isolated host startup took 68.87 ms. Python
`tracemalloc` peak was 422.2 KiB at startup and 2,044.6 KiB over the full
measurement, excluding native/model/OS allocations.

## Safety and future work

The new evaluations route through isolated hosts or inject synthetic evidence;
they cannot launch apps, alter files, access Google, or call shell/process
capabilities. The production Qwen model and allowlist remain unchanged.
`.gitignore` excludes OAuth clients, tokens, runtime data, and model files while
explicitly allowing the new sanitized corpus files. No push or publish occurred.

Post-freeze State Engine, historical-state, and proactive designs are in
`docs/POST_FREEZE_DESIGNS.md`. The conditional V1.1 Google Calendar,
development-environment, and LocalForge batches remain unimplemented until a
measured V1 freeze. The blind Holdout V2 must be created and run only after
development stabilizes, its hash is recorded, and no further tuning is planned.

## Phase decision and next step

Phases 1–16, 19–22, and 27–36 have runnable code, evaluations, or documented
audits/designs. The Phase 7 fuzzy fallback was investigated but no character
similarity matcher was enabled: the existing high-evidence lexical fallback and
abstention avoid speculative tool menus. Phase 11E uses existing bounded ASR
normalization and session context; no raw audio or new wake alias was added.
Phase 22 enforces the two-case rule for *new* capabilities, while legacy LLM
coverage remains incomplete. Phase 20 contains sanitized voice development
cases; automatic real-conversation capture remains disabled.

The freeze gate is **not met**: Qwen development success is 83.33% versus the
85% target, diagnostics and mixed-domain are weak, the historical V1 holdout
still has 12 routing misses, and existing LLM coverage is thin. Therefore
Phases 17–18 (new blind V2 holdout), Phase 23 (freeze artifact), and conditional
Phases 24–26 (V1.1 capability batches) are intentionally not executed. Phase 37
is completed by the saved checkpoint, tests, benchmark artifacts, and hashes.
The
next step is a general, development-only Qwen diagnostics/mixed-domain fix,
followed by a fresh full development run; only after the gate is credible
should a new 60-case holdout be generated, hashed, locked, and run once.
