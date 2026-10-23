# M3 bounded boundary repairs: implementation freeze

This candidate repairs independently exposed failures recorded before changes at checkpoints `0ef77dc` (task code-hash drift and incorrect ISO due date), `3d4fb08` (actual two-provider parallel admission), `a80c52b` (foreground admission between model passes), and `89597e8` (root-owned default-argument capture binding). The original public goals, capability bindings, oracles and sealed eighteen planning cases were not changed. No real model, native window, production store, provider account or node was started.

## Changes

`workflows/policy.py` replaces marshal serialization with a typed semantic code encoding. Public unquickened bytecode, recursively typed constant values/nested code, names, argument counts, variables, flags and exception tables are hashed; source locations and mutable marshal reference/intern flags are excluded. Closure/instance/default capture values are never serialized. Original registry-owned binding UUIDs, full schema/policy/external hashes, and the original exact captured-definition object gate remain authoritative. Runtime warmup/interning and the genuine original task add/get/complete sequence now preserve definition hashes. Semantic constant replacement and stateful re-registration still invalidate consent. Root independently extended the registration UUID predicate to default and keyword-default captures.

`tools/whenparse.py` admits exact ISO dates and date-times before natural-language clock matching. It preserves explicit dates, seconds, microseconds and UTC offsets/Z without converting to another zone or inventing one. Invalid dates, clocks, offsets and malformed ISO timestamp tails fail explicitly. Existing natural-language phrases and `YYYY-MM-DD at 3pm` still use their original parser. A real isolated TodoStore add/get retains the reviewed future offset-bearing due date exactly.

Parallel admission now uses `parallel_read_safe`, separately from `is_read`. Only original trusted registry reads whose capability metadata identifies a known local family may use parallel read slots. External-definition hashes, `mcp.*`, provider-source metadata and unknown extension families independently deny that optimization. Such reads use an exclusive `serial_read` worker slot, including exclusion against new planning work; their original read classification, permission checks, consent and invocation write flag remain unchanged. Actual original local handlers overlap under a barrier; a provider-marked original read does not overlap another read or start an extra planning inference. The unchanged one-session and two-session SDK tests also pass.

`WorkflowPlanner` accepts an optional trusted admission callback, invoked immediately before each original client call. The attached Service callback rechecks generation/owner fence, Stop, foreground interaction, actual resource admission, owner pause/cancel and planning time budget. The coordination lock is released before synchronous inference. Once an interrupted model call returns, cancelled/paused planning is recorded truthfully instead of being labelled active. No second inference is admitted after foreground, Stop, owner pause/cancel or unavailable resource changes.

## Verification evidence

These are overlapping engineering cohorts, not additive counts or autonomous-model success rates:

| Retained artifact under `data/hanni-v3-review/` | Result |
| --- | --- |
| `m3-identity-iso-development-cycle-1.xml` | 80/80 PASS |
| `m3-parallel-development-cycle-1.xml` | 7/8 PASS; own test used nonexistent receipt key `write_effect`; actual persisted key is `write` |
| `m3-repair-identity-iso-parallel-cycle-2.xml` | 109/109 PASS |
| `m3-admission-identity-iso-cycle-1.xml` | 31/32 PASS; own Stop fixture used the wrong original trip signature |
| `m3-bounded-repairs-development-cycle-2.xml` | 197/197 PASS |
| `m3-scheduler-final-freeze.xml` | 57/57 PASS, after final exclusive-slot admission change |
| `m3-original-binding-dates-final-freeze.xml` | 142/142 PASS, fresh process with root default-capture binding change |

The final cohorts include the unchanged independent 27 Service cases, actual SDK parallel tests, callable/registry guards, original planner cases, task/date/calendar regressions and new focused semantic-identity/ISO/admission checks. Structured planning clients and controlled resource probes are disclosed engineering seams; original registry, host, local handlers, durable service, approvals and SDK transports remain real. Independent reruns and final holdout acceptance are still pending at this implementation freeze.

## Frozen source SHA-256

| Path | SHA-256 |
| --- | --- |
| `src/hanni/workflows/policy.py` | `2c40295e207cdb2e1cc7d385aacaca65e4ee232d338782c030c15a31f945e9f6` |
| `src/hanni/tools/whenparse.py` | `0a868599fc43c9df8adbf299fd259426ea4a10a75e644b33f2d4902029871688` |
| `src/hanni/workflows/service.py` | `014852ffd20abab79914598757a81c7cabcb47d791d54078975b97b936eab520` |
| `src/hanni/workflows/planner.py` | `1496743697ac6916ad492734f6d0f285116ebce8cc78129b7db1a2a02b83ac26` |
| `src/hanni/tools/base.py` (root-owned) | `8747c93b2dd7707c3eea3aff05815f9045639b0613c53faedbdc3a5b71a35b9f` |

Worker1 changes are limited to the four production paths above, `test_workflow_semantic_identity.py`, `test_whenparse_iso.py`, `test_workflow_parallel_read.py`, `test_workflow_planning_admission.py`, and this report. Host routing, store, public test fixtures and evaluation inputs remain frozen.
