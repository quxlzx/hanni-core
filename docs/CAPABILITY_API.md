# Capability search / get / call delivery

Implemented against the existing HANNI registry, three-model router and background
queue. No code was published or pushed. Restart HANNI to load the Python changes.

## What was limiting the old implementation

The repository already used semantic tool IDs and a validated ToolRegistry;
it did not need another script execution engine. However, the fast router searched
an eight-entry catalog even for known commands, discovery rebuilt/tokenized the
whole registry on each query, argument descriptors omitted useful bounds/defaults,
and router confidence did not govern resolution. Execution classes and background
eligibility were implicit. Older planning prompts also still described every
action as a TODO, despite the newer three-model admission rules.

## Current architecture

```text
Owner request → existing voice/text/browser session
  Known intent / exact ID / unambiguous cached alias
    → Qwen3 + cached schema → validate → capability.call → factual formatter
  Unresolved ID / low confidence
    → capability.search (at most 5)
    → capability.get (retrieved candidates only)
    → Qwen3 selects ID/arguments → validate → capability.call
  Compound reasoning → Phi-4 foreground action/observation loop, no TODO
  Tracked workflow → existing JobManager → Phi-4 / optional Qwen3 32B plan
    → checkpoint → capability.call → observation / verification → checkpoint
```

Established deterministic clock/calendar, memory and safety controls retain their
dedicated handlers. They do not acquire an extra model round trip. Common CPU,
GPU, app-open and volume requests still use Qwen3 classification with a compact
schema, but do not start speculative Phi-4. For other requests the existing bounded,
inference-only preflight remains available; its result is discarded on atomic
admission without waiting. Search results never execute automatically by rank.

`routing.capability_confidence_threshold` defaults to **0.85** and
`routing.capability_search_limit` to **5** (validated range 1–5). Missing confidence
is zero. A deterministic common-intent match independently supplies a validated
request; a model score is not permission. Unknown IDs and choices outside a
discovery candidate set fail closed. Unresolved low-confidence choices ask for
a clearer operation/target rather than constructing a shell fallback.

## Internal API and CLI

`registry.capabilities` owns a `CapabilityAPI` in
`src/hanni/tools/capability_api.py`:

| Operation | Implementation | Result |
| --- | --- | --- |
| `capability.search` | `api.search(query, limit=5)` | Ranked ID, description, risk, class, score only |
| `capability.get` | `api.get(id)` | Defensive copy of one cached schema |
| `capability.call` | `api.call(ToolRequest(...))` | Structured ToolResult; preserves internal confirmation/stop exceptions |
| JSON call boundary | `api.invoke({"id": id, "arguments": {...}})` | Success result or normalized error envelope |
| Exact / alias resolution | `api.resolve_id(id_or_alias)` | One registered ID or None; conflicting aliases do not resolve |

Authority flags are supplied separately by trusted host code, never accepted
inside the model-facing JSON payload. The API is internal and MCP-inspired; it
does not open a network MCP server or add a nested generic executor tool that
could hide the actual target from the workflow verification ledger.

```powershell
.\.venv\Scripts\python.exe -m hanni.cli capability-search "Which program has been hammering my disk?" --json
.\.venv\Scripts\python.exe -m hanni.cli capability-get process.top_cpu --json
.\.venv\Scripts\python.exe -m hanni.cli capability-call process.top_cpu --arg limit=5 --json
.\.venv\Scripts\python.exe -m hanni.cli capability-call audio.set_volume --arg percent=500 --json
```

The last command fails validation and does not change volume. Existing
`tool-run` scripts remain compatible and now use the same capability call facade.
`capability-search` CLI output is intentionally compact; consumers of the older
`capability.name` shape must now read `id` and retrieve full details with get.

## Metadata and migration

All **163 base capabilities** derive metadata from existing ToolDefinitions;
all original 162 IDs and executors are retained. The interactive session adds
the existing eight `jobs.*` capabilities. No setup/model-launching script is
exposed as an LLM action. Existing fixed Python/PowerShell implementations remain
behind their registered handlers. The generated
`HANNI_CAPABILITY_MATRIX.md` inventories every base ID, purpose, risk, side
effect, execution class and background eligibility.

ToolDefinition now includes `execution_class`, `background_allowed`,
`schema_version`, `display_name`, `categories` and `argument_constraints`, in
addition to existing description, tags/aliases, input/output contracts, executor,
timeouts and confirmation policy. Existing self-contained operations default to
atomic. Background eligibility defaults to true so existing workflow primitives
remain composable; job-control capabilities explicitly remain foreground-only.
Workflow-class registrations are supported and tested, without inventing new
giant workflow handlers for existing primitives.

Example model-facing metadata (abbreviated):

```yaml
id: process.top_cpu
name: Top CPU Processes
execution_class: atomic
risk: read_only
confirmation: false
confirmation_policy: runtime profile check
background_allowed: true
schema_version: 1
arguments:
  limit:
    type: integer
    default: 5
    minimum: 1
    maximum: 20
returns:
  type: object
  properties:
    processes:
      type: array
```

The limit of 20 preserves the actual CPU implementation rather than advertising
an unsupported 50. Input types and declared defaults/ranges/enums/lengths are
used by both schema generation and registry validation. Legacy optional/null
behavior is preserved where no stricter constraint is declared. Tool-specific
requirements (for example file existence, valid targets and mutually dependent
arguments) remain in their existing deterministic validators. Output contracts
describe the existing structured data; they do not invent unavailable readings.
The `confirmation` hint cannot override the runtime profile or dynamic checks.
Timeout metadata retains existing executor timeouts; it does not promise forced
cancellation of arbitrary Python code already running.

New `process.top_disk_io` samples accessible process read/write counter deltas,
orders by bytes/second and reports unavailable samples. It is read-only, uses
bounded result counts and does not save historical activity. Process I/O counters
are not a guarantee of physical-disk attribution; the returned scope says so.

## Index, safety and jobs

Discovery reuses a per-registry inverted metadata index with weighted tokens,
aliases, vocabulary expansion, existing intent hints and verification companions.
It indexes ID, display name, description, aliases/tags, categories and argument
descriptions. Registration revisions invalidate caches, including late job/memory
registration. Exact IDs use dictionary lookup. Alias collisions are rejected.
Search is deterministic local retrieval, not an embedding model; its normalized
ranking score is not a calibrated probability. No embeddings or new dependency
were needed for the measured registry sizes.

Every call still uses ToolRegistry validation, current permissions, dynamic
confirmation, persisted emergency stop, the shared mutation lane and redacted
audit. The registry itself enforces workflow/background eligibility even through
the legacy execute entry point. Background context is runtime-owned, not a model
argument. Safe Mode is never cleared by discovery or a failed call.

Atomic calls create no AgentTask/TODO/job. Compound metadata selects the
foreground Phi-4 chain. Workflow metadata forces queue admission; the existing
JobManager sets the background execution lane on both new and restored work.
Workflow metadata applies to SIMPLE_TOOL, STANDARD and COMPLEX suggestions,
even when the router omits workflow flags. A workflow registered as
foreground-only is rejected before admission on all three routes. This closes
a follow-up review finding where a STANDARD suggestion could enter the
foreground chain and fail its execution-lane check instead of being queued.
Foreground priority, exact pending confirmations, verification debt, before/after
checkpoints and uncertain-action replay blocking remain unchanged. Job status,
get/list/recent and pause/resume/cancel/confirm are atomic runtime capabilities.

Failures at the JSON call boundary carry `error.code`, `message`, and
`retryable:false`. Codes include UNKNOWN_CAPABILITY, INVALID_ARGUMENTS,
CONFIRMATION_REQUIRED, PERMISSION_DENIED, SAFE_MODE, NOT_FOUND, TIMEOUT and
CAPABILITY_FAILED. Failed ToolResults also serialize an error object. Internal
control exceptions remain exceptions so existing approval/resume paths work.
Search/call logs include IDs, class, risk, score and timing, not private search
queries or fetched content. Existing audit redaction remains authoritative.

## Validation and measurements

Follow-up full suite: **818 passed, 30 subtests passed, no skips** in 52.94 s,
with the virtual environment on PATH. The focused API and routing run passed
all 77 tests. Wheel/source builds and distribution content checks also passed.
The API tests cover contracts, cache copies
and invalidation, alias collisions, bounded search, exact CPU bypass, discovery,
low confidence, hallucinated/out-of-candidate IDs, bad arguments, permission and
confirmation gates, Safe Mode, execution classes/background eligibility, CLI
contracts and real I/O-delta calculation with controlled counters. Existing tests
cover compound calendar reasoning, durable workflow recovery and job controls.
Capability routing: **121/121** first-rank cases. Capability safety checks passed.

Measured locally with `scripts/benchmark_capabilities.py --live-router`:

| Operation | Median | p95 |
| --- | ---: | ---: |
| Exact lookup, 163 capabilities | 0.0002 ms | 0.0002 ms |
| Alias lookup | 0.0008 ms | 0.0009 ms |
| Cached get | 0.0130 ms | 0.0163 ms |
| Search, 163 capabilities | 0.1474 ms | 0.2088 ms |
| Search, 1,163 capabilities | 2.5520 ms | 2.7424 ms |

The first index-building search took 4.52 ms. The scaling run added 1,000 inert
fixture definitions; no synthetic handler ran. Measurements used 100 operations
per warm case and are host/load dependent, not hard real-time guarantees.

Five repeated live Qwen3 CPU classifications all returned process.top_cpu at
confidence 0.95. Median **TTFT was 48.17 ms**, while the full structured response
took **1.03 s** median. The first request took 748 ms to first content; later
requests benefited from the model server's warm state. This meets the stated
median target for this sample, not a claim that every new prompt starts in 48 ms.

A separate live CPU read completed in **2.80 s** including classification, actual
sampling and audit. Instrumentation explicitly prohibited search and Phi-4 calls:
no task was constructed, no job enqueued and no primary model called. The new
disk sampler is also covered with controlled counter/permission fixtures. The
compound and workflow cases below use test model outputs, not claims that live
Google calendars were changed or a school workload was reorganized.

During the follow-up review, the configured local router server was unreachable,
so a new live disk-discovery check could not run. The live CPU timings above are
from the earlier successful run; discovery is covered by automated model fixtures.

## Example logs

Live CPU request (nonessential process names omitted):

```text
[Router] SIMPLE_TOOL -> process.top_cpu
[Capability] exact match process.top_cpu
[Capability] class=atomic risk=read_only call process.top_cpu
[Capability] completed process.top_cpu ok=True 739.85ms
Task created: False Workflow enqueued: False Phi-4 called: False
```

Discovery/compound/workflow traces have these forms; IDs/scores/job keys vary:

```text
[CapabilitySearch] [('process.top_disk_io', ...), ...]
[Router] SIMPLE_TOOL -> process.top_disk_io
[Capability] discovered process.top_disk_io
[Capability] class=atomic risk=read_only call process.top_disk_io

[Router] STANDARD
[Model] phi-4-14b (short action chain, no TODO)
[Capability] class=atomic risk=read_only call google_calendar.next

[Router] COMPLEX
[Queue] Enqueued job_<runtime id>
[Planner] qwen3-32b
```

The heavy-planner line appears only when that optional server is selected and
available. Primary fallback and all subsequent tool execution retain the same
queue and registry gates. No heavy model was downloaded for this update.

## Files changed

- `src/hanni/tools/capability_api.py`: new API, caches and normalized JSON call errors.
- `src/hanni/tools/base.py`: metadata, shared schema validation, revision tracking,
  error serialization and background enforcement.
- `src/hanni/tools/capabilities.py`: indexed discovery and extended descriptors.
- `src/hanni/tools/system.py`, `media.py`, `jobs.py`: I/O capability, CPU/volume
  constraints, runtime job eligibility.
- `src/hanni/agent/routing.py`, `routed_session.py`, `planner.py`: cached router
  schemas, confidence admission, bounded discovery and execution-class routing.
- `src/hanni/agent/loop.py`, `jobs.py`: capability calls and restored-job lane.
- `src/hanni/cli.py`, `config/schema.py`, `config/hanni.yaml`: CLI operations and
  validated confidence/candidate settings.
- `tests/unit/test_capability_api.py`, `test_three_model_routing.py`,
  `test_capability_planning.py`: new regressions and updated compact contracts.
- `scripts/benchmark_capabilities.py`, `capability_matrix.py`,
  `capability_routing_check.py`, `capability_safety_check.py`: measurements and
  generated metadata/routing/safety validation.
- `CLAUDE.md`, `docs/DECISIONS.md`, `docs/HANNI_CAPABILITY_MATRIX.md`, this report:
  current authorization, architectural decision and inventory.

Runtime logs live under `data/capability-api-*` and remain outside source exports.
Voice, orb/dashboard, Google connections, memory and model configuration are
preserved. To load the update, stop the old session with Ctrl+C and run
`.\START_HANNI.cmd -SkipInstall`.
