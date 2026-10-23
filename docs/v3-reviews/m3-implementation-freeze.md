# M3 implementation candidate freeze

This records the implementation candidate, not independent acceptance or final
V3 completion. The verifier's exposed service scenarios and the sealed final
planning evaluation have not been run by Worker 1. No production model, voice,
GUI, remote node, provider or user-data operation was launched for these checks.

## Execution architecture

`WorkflowService` attaches to the existing controller's registry, model client
and `McpHost`. Construction and history reads do not start a controller or model.
The two-pass planner uses the existing model `chat` interface and original routed
tool menus. The service never invokes handlers directly or adds another router.

The scheduler owns a durable SQLite lease/fence, bounded daemon workers and
metadata mutations. Its oldest-first nonterminal query is independent of the
newest 100-item history page. Admission checks foreground interaction, Stop,
the injected fresh RAM admission probe and the current lease. Missing resource
evidence blocks admission; unknown GPU data is not assumed to mean free VRAM.
The original model inference lease retains its separate model resource policy.

Assisted and background work wait for explicit plan review and Start. Background
calls preserve the original capability `background=True` gates. Owner-selected
supervised submission creates a distinct narrow scope for validated known
builtin reads and analysis. Remote imported tools do not receive this automatic
scope. Every supervised sensitive action, including a managed artifact without
an explicit plan review, waits for exact prepared-argument approval.

The approved plan hashes its actual executable steps, dependencies, fixed
arguments, tool definition bindings and criteria. Typed references accept only
declared verified predecessors and revalidate resolved JSON types and original
tool schemas. Original host fixed-account, argument, path and policy guards
remain in place before the original audited registry call.

Every invocation has a durable receipt and correlation UUID committed before
dispatch. The original registry invokes a trusted execution guard after acquiring
its mutation lane: controller generation, lease, pause/cancel, exact plan/action
expiry and revocation, tool hashes and artifact identity are checked again.
Captured-definition object identity closes replacement between host preparation
and registry admission. Stateful registrations receive opaque process-local
binding IDs; plain module functions remain stable across restart. No closure
contents or credential values are serialized into this binding.

Results are fenced before commit. Missing write receipts become uncertain and
cannot be replayed automatically. Safe builtin read retries are opt-in, limited
to one and use persisted backoff; recovery attempts count against the same
budget. An active synchronous call remains visible while cancel, pause or timeout
withdraws further admission. Stop clearing does not silently resume queued work.

V2 verification reads carry the same execution guard and captured-definition
gate. The separate outcome evaluator checks actual criteria and bounded cited
facts/calculations. Imported receipts remain unverified. Artifact byte/hash
readback does not establish analysis correctness. Required unverified results
cannot produce a completed objective.

Managed artifacts use fixed UUID directories, safe report extensions, original
file handlers and a shared physical storage budget. Existing parent links and
Windows reparse points are refused at admission and the registry guard.
Metadata retention preserves request-ID tombstones and uncertain receipts;
physical cleanup is bounded and deferred under Stop/foreground activity.
Notifications contain generic transitions rather than raw goals, arguments or
result bodies, and the in-memory notification map is bounded.

Expired/revoked scopes can request a new review through explicit resume when
remaining definitions still match and no uncertain effect exists. This creates
a new pending grant and revision; it never renews old consent automatically.
Review then Start preserves the original duration deadline. Verified completed
steps are neither re-executed nor invalidated merely because their prior
stateful handler was re-registered.

## Source boundaries

Worker 1 owns `workflows/service.py`, `store.py`, `types.py`, `planner.py`,
`policy.py`, `references.py`, package exports and narrow `mcp/host.py` workflow
preparation/authority forwarding. New engine development tests are
`tests/unit/test_workflow_service.py`.

Root owns configuration, CLI/controller/dashboard lifecycle and private APIs,
original `tools/base.py` definition/authority gates, workflow maintenance,
deterministic outcome verification and V2 verification follow-up hardening.
Worker 2 owns the genuine Workflows frontend. The independent verifier owns its
test fixtures, oracle scenarios and final sealed evaluation.

## Development evidence

The planner clients in these development tests return scripted structured model
responses. Routing, host preparation, permissions, audited execution, SQLite,
actual isolated file reads/writes, result verification and readback remain real.
These tests do not measure configured-model intelligence or general goal recall.

The first combined 65-check execution had one genuine implementation failure:
the scheduler settled a pending safe retry before its durable backoff elapsed.
The fix waits for eligible delayed reads without changing routing thresholds or
test expectations. That initial run is preserved in session tool output; it did
not write a JUnit artifact.

Recorded development artifacts under `data/hanni-v3-review`:

| Artifact | Executed tests | Failures | Meaning |
| --- | ---: | ---: | --- |
| `m3-development-cycle-1.xml` | 150 | 0 | Early coherent engine/store/planner/binding/outcome checks |
| `m3-development-cycle-2.xml` | 150 | 0 | Persisted correlation and UI projection alignment |
| `m3-development-final.xml` | 154 | 0 | Three actual mode distinctions included |
| `m3-development-freeze.xml` | 157 | 1 | Development Stop test used positional arguments for a keyword-only API |
| `m3-development-freeze-cycle-2.xml` | 157 | 0 | Correct API invocation, fresh-review recovery and Stop behavior |
| `m3-service-freeze.xml` | 16 | 0 | Last original model-entry generation/admission guard checked |

These rows are overlapping test runs, not additive counts or independent
workflow success rates. The 16 service checks include positive isolated reads,
real typed-reference artifact preservation, one safe read recovery, request
deduplication, stale/cold controls, real noninterruptible cancellation, mode
boundaries, storage refusal, revocation, changed handlers and explicit Stop
resumption. They are not a claim that 16 multi-step objectives were completed.

The most recent combined command was:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_workflow_service.py tests/unit/test_workflow_store.py tests/unit/test_workflow_planner.py tests/unit/test_workflow_registry_guard.py tests/unit/test_workflow_verification.py tests/integration/test_workflow_store_verifier.py tests/integration/test_workflow_planner_verifier.py tests/integration/test_workflow_callable_guard_verifier.py tests/integration/test_workflow_outcome_verifier.py -q --tb=short --junitxml=data/hanni-v3-review/m3-development-freeze-cycle-2.xml
```

After the final model-entry guard, all 16 service checks passed again. Final
independent review must evaluate that exact frozen candidate, rather than assume
that the earlier combined artifact included the final tiny change.

## Freeze hashes (SHA-256)

| File | Hash |
| --- | --- |
| `src/hanni/workflows/service.py` | `6d38c295d8ff3e9f91c3ecf2c6deb47cfbb47d4fb6548a31be5c124520231f3f` |
| `src/hanni/workflows/store.py` | `053d36cd26f90d9f0eb805735f59c0d2cdabd8a66ea70faefa29d0498aa40308` |
| `src/hanni/workflows/types.py` | `f9a0e63a4ae34455bb1ae1453a10351d153e0a0bf519777d576316084c0cab77` |
| `src/hanni/workflows/planner.py` | `d1db2420a5b5acf4e3a95ff882b2f53465d42aa40b29ea6f7cd5a7d1926e67f5` |
| `src/hanni/workflows/policy.py` | `38880282859de22c47ceb429b055f31d889cc181ed1e95657a692fe2df37617d` |
| `src/hanni/mcp/host.py` | `0b9ac7396844f7d9717f81c8a25c6654ab562cf4fb300b702e363a48f1b07c99` |
| `src/hanni/tools/base.py` | `a73cb521220ff306fb562a0c85151c23ef6338b74d869d9982a8c3abaf5af2ea` |
| `src/hanni/reliability/verification.py` | `b50e14242bf9e9a2195ddfeebb859ca7df65ba7d6ba616e5a13144a0c642b54c` |
| `src/hanni/workflows/verification.py` | `02baa196250b26619e22aeac0d30ec5221beeaaa09f3d773eb8b4230bbeaae5f` |
| `tests/unit/test_workflow_service.py` | `767948ebafe394ada1f58de43e2a02bae6c60c531d0a572570b935df6142a298` |

## Remaining verification and limits

Independent exposed service/crash/security tests, browser/native lifecycle,
configured-model planning and the sealed final evaluation remain pending at
this freeze. No final quality or visual acceptance score is inferred here.

Synchronous handlers cannot be forcibly interrupted safely. Uncertain writes
require human investigation and are not exposed through a replay/reconciliation
shortcut. Changed unfinished stateful definitions require a new goal/plan,
rather than silently rebinding an old approval. Factual report verification is
limited to cited observations and supported deterministic calculations; it does
not prove free-form causal conclusions. Arbitrary shell commands, generated
script launch, production source/config changes, new model downloads and
autonomous cluster execution remain outside this implementation's authority.
