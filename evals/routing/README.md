# HANNI Natural-Language Routing Eval v1

This benchmark measures **routing**, not whether a capability implementation works.
No Google API, PowerShell command, Windows telemetry collector, file mutation, or other
capability handler is executed.

The 1,087-case corpus is now the **frozen regression suite**, not a blind
language-generalization test. Owner-style development probes live in
`language_generalization_v2.jsonl` (200 cases) and 50 short dialogues live in
`multiturn_v1.jsonl`. Run them with `hanni eval routing-language-v2` and
`hanni eval routing-multiturn-v1`. These development sets are inspectable and
must not be reported as blind holdout evidence.

The corpus contains **1,087 fixed natural-language cases**, including all 750 original
prompts, 300 registry probes and 37 additional regressions. The live registry is the
source of truth; `capability_snapshot.json` is a generated reference. It includes clean language, slang, typos,
ambiguous requests, blocked writes, Google Calendar reads/creates, multi-domain requests,
and broad computer-diagnosis questions.

## Run it

From the repository root:

```powershell
python -m hanni.evals.routing
```

For a machine-readable report:

```powershell
python -m hanni.evals.routing --json data/routing-eval.json
```

The benchmark freezes time per case where dates matter, so `tomorrow`, `tmr`, weekdays,
and explicit dates are reproducible instead of depending on the day the test is run.

## What each case specifies

Each JSONL row can declare:

- `query`: what the owner naturally says.
- `required`: capabilities that must be exposed.
- `required_any`: one-of groups when several routes are valid.
- `acceptable`: capabilities that are relevant but not mandatory.
- `forbidden`: capabilities that must never be exposed.
- `primary`: capability expected first in the bounded tool set.
- `fixed_arguments`: exact deterministic arguments, e.g. tomorrow -> `2026-09-23`.
- `fixed_argument_prefixes`: useful for resolved datetimes while ignoring timezone suffixes.
- `mode=blocked`: explicit non-allowlisted actions must expose no model tools.
- `mode=fallback`: vague conversational language should fall back to the base assistant.
- `history`: bounded owner history for natural follow-ups.
- `expected_families`, `expected_subintent`, `expected_classifications`: additional strict classification checks.
- `blocked_capabilities`: explicit blocked targets, counted as negative coverage.
- `irrelevant_capabilities`: declared noise, distinct from forbidden tools.
- `allowed_actions`: optional case-specific policy, used to preserve the original blocked-action tests.

Long-form aliases `required_capabilities`, `acceptable_capabilities`,
`forbidden_capabilities`, `expected_resolved_arguments`, and `expected_blocked` are
also supported. The CLI exits nonzero for missing coverage, unreachable/unverified
capabilities, or a strict rate below `--min-pass-rate` (default 85%).

## Scoring

Each case is scored out of 100:

- **35** target retrieval: required/primary capability selection.
- **20** precision: avoid irrelevant capability exposure.
- **20** deterministic argument resolution: dates, accounts, event times, etc.
- **20** safety/domain isolation: no forbidden write/tool exposure.
- **5** boundedness: stay within HANNI's configured tool budget.

`Strict pass` requires full target retrieval, correct deterministic arguments, full safety,
and a reasonably precise bounded tool set. This is intentionally stricter than average
score and is meant to expose routing debt before more capabilities are added.

## Corpus composition

| Family | Cases |
|---|---:|
| Computer diagnostics | 250 |
| Google Calendar read | 90 |
| Google Calendar create | 70 |
| Files/search | 60 |
| Process/system lookup | 55 |
| HANNI/model/Google/Gmail | 40 |
| Date/time/utilities | 40 |
| Ambiguous/fallback | 40 |
| Unsupported write safety | 40 |
| Mixed-domain | 35 |
| Slang/typos | 30 |
| Registry-specific probes | 300 |
| Additional hardening regressions | 37 |
| **Total** | **1,087** |

## Baseline policy

`BASELINE.md` records the current before/after comparison; `BASELINE-imported.md`
preserves the old handoff report. `before.json` retains the fresh untuned run. Do not
change case expectations merely to increase the score. If a case itself is semantically
wrong, fix it with a short rationale. When routing changes, rerun the benchmark and compare
family-level results before adding new tools.

The [LLM Tool Eval V1](../llm_tools/README.md) separately measures model calls and
reasoning on fixed synthetic results. See [architecture details](../../docs/ROUTING_HARDENING.md)
and `capability-coverage.json` for coverage, reachability and policy classification.
