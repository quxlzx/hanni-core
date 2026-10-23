# Phases 11–15 checkpoint — 2026-09-24

## Phase 11: Tool Intelligence V1 freeze gate

**Decision: NOT YET.** The deterministic router's saved 1,087-case development
regression is 99.66 average / 99.82% strict. The unchanged live model reports
show Qwen3.5-4B at 123/150 (82%) development task success and 25/50 (50%) on
the locked personal-language holdout. K2 Horizon 3.7B scored 89/150 (59.33%)
and 23/50 (46%) on those same corpora. Qwen remains the production model.
Both models had zero hallucinated MCP tools in these synthetic runs, and safety
cases passed, but 21 of the 50 holdout requests had insufficient retrieved
menus. Qwen diagnostics passed 30/45 development cases and 7/15 holdout cases;
mixed-domain requests passed 6/10 and 2/10. These results miss the roadmap's
approximate development, holdout, diagnostic, and mixed-domain gates by too much
to justify a freeze. The [model bake-off](MODEL_BAKEOFF_QWEN_VS_K2.md),
[shared-failure analysis](PHASE8_SHARED_FAILURES.md), and
[diagnostic matrix](PHASE10_DIAGNOSTICS_INVESTIGATION.md) contain the saved
evidence. The locked holdout remains unchanged and must not become a tuning set.

No `TOOL_INTELLIGENCE_V1_FREEZE.md` is created: that filename is reserved for a
positive decision with new supporting measurements.

## Phase 12: V1.1 capability expansion

**Deferred by the Phase 11 gate.** No Calendar, media, development, LocalForge,
server, LMS, state-engine, or history capabilities were added. The existing
Google Calendar integration remains the only calendar provider. Revisit one
small batch after a valid freeze decision and the roadmap's per-capability tests
and evaluation coverage are prepared.

## Phase 13: Capability metadata standard

All 150 active registry definitions now receive consistent descriptive fields
through `CapabilityDescriptor` and `capability.get`: `name`, `family`,
`subfamily`, `description`, `risk`, `state`, `source`, `requires`, `permission`,
`read_write_class`, `priority`, and `introduced_version`. The domain mapping
lives in `src/hanni/tools/capability_metadata.py`. It groups the current
namespace prefixes into 12 major domains without renaming any capability.
Unmapped runtime extensions remain discoverable under one `extensions` domain;
the test suite verifies that every built-in namespace is explicitly mapped.

`state=production` means registered in the active catalog; it does **not** mean
the frozen V1 quality gate passed. `introduced_version=legacy_untracked` is an
honest marker because the existing registry did not record per-capability
release history. `priority=0` is reserved metadata and does not affect routing.
The new five-value `risk` class is exposed as `metadata_risk` by
`capability.get` to preserve the existing model-facing `risk` contract, which
uses the older read/write/external/destructive vocabulary. Neither field grants
permission; the registry still decides from validated arguments, actor profile,
dynamic confirmation, and Safe Mode. Tests cover metadata completeness for
the full registered inventory.

## Phase 14: Registry scaling rule

Keep major domains coarse and subfamilies specific. A new namespace must be
mapped deliberately; it must not silently become another top-level domain.
The current router and eight-tool MCP ceiling are unchanged. The 150-capability
inventory and routing regression are measured; **500 and 1,000 capability
scaling are design targets, not measured claims**. Before a future batch grows
the catalog, benchmark retrieval latency and menu quality with the larger
registry, and require small menus across mixed-domain and ambiguous requests.

## Phase 15: Avoid broad execution as a model fallback

No generic shell, database, or network request capability was added. The
existing `powershell.run` is a broad legacy manual capability. It is now
unavailable from the resident model's MCP host even if an action allowlist or
non-read-only MCP mode is configured; its MCP call path denies execution before
reaching the PowerShell handler. The existing manual CLI path remains subject to
ToolRegistry validation, permission, dynamic confirmation, Safe Mode, and audit.
This does not claim to sandbox arbitrary PowerShell arguments. The older direct
voice/CLI paths remain separate; a future retirement of this legacy capability
requires its own migration review. New assistant features should use narrow
typed capabilities, with argument-aware policy for target, side effects, working
directory, network destination, privilege, and destructive potential whenever
generic execution is genuinely needed.

## Next freeze attempt

Collect a new, independent owner-language **development** set; correct
demonstrated menu failures using general domain semantics rather than copied
holdout phrases; fix the disk/power evidence and oracle mismatches identified in
Phase 10; then rerun routing and Qwen live development evaluation. Use a **fresh
blind holdout** for the next freeze decision. Keep the old locked holdout as an
unchanged historical measurement, not a target for optimization.

## Validation and saved artifacts

- Full pytest suite: 456 collected, 455 passed, 1 skipped because the console
  executable was not on that process's PATH. The two entry-point integration
  tests then passed with `.venv/Scripts` on PATH.
- Routing: [1,087-case report](../evals/routing/results/routing_phase11_15_1087.json)
  remains 99.66 average / 99.82% strict, with the same two Spotify menu
  overexposure misses. [Coverage](../evals/routing/results/routing_phase11_15_coverage.json)
  remains 150/150 registered capabilities, none missing or unverified.
- Development corpus: [audit](../evals/llm_tools/results/phase11_15_dev_audit.json)
  passed 150 scenarios with zero routing/mock errors.
- Locked holdout: [audit](../evals/llm_tools/results/phase11_15_holdout_audit.json)
  reports the same 21 insufficient-menu cases; its nonzero audit exit is
  expected and is not hidden.
- The local model API at `127.0.0.1:8080` was unavailable at this checkpoint.
  No new live Qwen or K2 result is claimed. Phase 11 uses the saved same-router
  live reports linked above; this metadata change did not alter their prompts,
  fixtures, or selected menus. Production model configuration remains Qwen.
- This source snapshot has no root `.git` metadata, so a commit/status hash
  cannot be provided. No push or publication was performed.
