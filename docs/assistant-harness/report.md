# Assistant harness verification report

Campaign date: 2026-10-23. Environment: Windows, Python 3.12.10, pytest 9.1.1,
Coverage.py 7.17.0, Node 24.21.0. Starting branch: `hanni-core-native`, commit
`70b402b0f9c803a2b42bf9162584080e4bb9b738`, with substantial existing uncommitted
work. The working tree, rather than that commit alone, is the tested source.
Unrelated changes were retained; no checkout, reset, commit, or deployment was
performed. The running assistant was not restarted during this campaign.

This report distinguishes code inspection, controlled automated evidence, and
unverified live behavior. Test results, corrected reruns and coverage tables follow below. The [run guide](testing.md) describes reproduction.

## Repository and implementation inventory

Python implements the CLI, dashboard backend, tool policy, native agent runtime,
speech, persistence, and Hermes bridge. React 19/TypeScript and Vite 7 build the
dashboard into `src/hanni/dashboard/static`. PowerShell implements Windows OS
boundaries. Native model servers are external executables. Dependencies and CLI
entry points are declared in `pyproject.toml`; npm dependencies and lockfile are
under `frontend/`. Existing pytest tests, evaluation corpora, and Node tests were
extended rather than replaced. GitHub Actions has frontend, Python test, and
distribution jobs; this campaign adds offline coverage evidence to that workflow.
CI configuration was checked locally; a remote CI run was not launched.

Status describes code capabilities, **not successful live deployment**.

| Feature | Status | Source under `src/hanni/` | Evidence and limitation |
| --- | --- | --- | --- |
| CLI and dashboard entry points | Implemented | `cli.py`, `dashboard/launcher.py`, `dashboard/server.py` | Actual CLI subprocess smoke against owned fake model HTTP server; dashboard APIs have existing HTTP tests. No interactive desktop session opened. |
| All 32 proposed slash commands | Implemented | `dashboard/commands.py`, `dashboard/work_commands.py` | Registry-driven tests plus existing command semantics and HTTP authentication tests. See command matrix below. |
| Parser aliases and quoting | Partial | `dashboard/commands.py`, `dashboard/work_commands.py` | Command names ignore case; direct API slash must be first character; UI trims. No general alias registry or shell quoting contract. Calendar `add` and jobs' default status are subcommand conveniences; reminder quoting has specific tests. |
| Action/result agent loop | Implemented | `native/loop.py`, `native/worker.py`, `native/runtime.py` | Scripted multi-round calls, actual registry effects/readbacks, errors, cancellation, retry and limits. Claims remain separate from verified receipts. |
| Model adapters | Implemented | `native/provider.py`, `native/streaming.py`, `models/client.py` | Native OpenAI-compatible JSON/SSE and legacy llama.cpp HTTP/streaming paths tested. Local/API selection is configuration, not a separate vendor-native SDK. |
| Fallback | Partial | `native/provider.py`, `native/loop.py` | Unsupported-stream fallback and bounded transient inference retry exist. No implicit alternative paid provider or model fallback is promised. |
| Reasoning and metrics | Partial | `native/loop.py`, `native/streaming.py`, `dashboard/native_chat.py` | Tests cover returned reasoning, usage and measured rate sources. Unsupported effort is rejected/omitted as appropriate. No access to hidden provider reasoning or guarantee every server supplies decode timings. |
| Local GPU preference / CPU fallback / q8 cache | Implemented configuration | `native/acceleration.py`, `native/model_settings.py`, `native/lifecycle.py` | Existing tests cover discovered devices and generated launch settings. Actual VRAM allocation, cache tensors and model loading were not exercised. |
| Context assembly and compression | Implemented | `native/compact.py`, `native/context_budget.py`, `native/memory_inject.py`, `dashboard/native_chat.py` | Budgets, task anchors, recent call/result groups, fallback summary, cancelled summaries, stable instructions and browsing history tested. Token estimates remain estimates when server counts are unavailable. |
| Persistent personal memory | Implemented | `memory/store.py`, `memory/retrieval.py`, `memory/grounded.py` | Real temporary SQLite save/dedup/search/correction/delete, reopen, cache invalidation and project scope. |
| Conversation history vs working state | Implemented | `dashboard/chat.py`, `hermes/state.py` | Separate chat and task/checkpoint stores. New chat retains memory; undo changes transcripts and expressly does not reverse tool effects. |
| Profile isolation | Partial | `memory/store.py`, `dashboard/chat.py` | Separate configured data roots and conversation ownership tested. This is not a multiuser authentication/RBAC implementation. |
| External memory / Honcho | Partial | `native/agent_tools.py` | Configured read-only registered MCP memory tool is supported and tested with controlled results. No dedicated Honcho SDK, automatic synchronization, or universally configured outage fallback was found. |
| Progressive reusable skills | Implemented | `native/skills.py`, `native/skill_store.py` | Metadata-only discovery, selective body reads, missing/invalid files, persistent revision guards and concurrent updates. Author-supplied verification prose is not independent verification. |
| Registry and permissions | Implemented | `tools/base.py`, `tools/registry.py`, `native/runtime.py` | Discovery, schemas, duplicate names, types, error receipts, confirmation and disabled/stale definitions are exercised. Retrieved instructions do not grant authority. |
| MCP configuration and execution | Implemented | `mcp/manager.py`, `mcp/runtime.py`, `mcp/adapter.py`, `dashboard/native_mcp.py`, `dashboard/mcp_hub.py` | Real SDK fixture services, discovery/reload/reconnect, duplicate identities, exact approvals, removal during calls and cleanup. No external MCP account verified. |
| Code execution / batched tool orchestration | Implemented | `native/code_execution.py`, `native/runtime.py` | Real Python subprocess/RPC, allowed schemas/tool subset, output/error capture and limits. Files and machine are shared; this is not a hostile-code sandbox. |
| Child agents and scheduler | Implemented | `native/worker.py`, `compute/scheduler.py` | Scoped tools, separate conversations, parent cancellation, bounded concurrency and foreground responsiveness. Shared filesystem remains a documented boundary; nested delegation is limited. |
| Persistent recovery and approval | Implemented | `hermes/state.py`, `reliability/execution.py` | Transactions/reopen, exact reviewed hashes, single concurrent claim, expiry/denial, queued recovery and uncertain-dispatch quarantine. Unknown effects are not silently replayed. |
| Voice, wake and interruption | Partial live validation | `dashboard/voice.py`, `speech/pipeline.py`, `speech/relevance.py`, `speech/tts.py`, `speech/live.py` | Fake wake/audio/transcript events, mode changes, stale audio and stop/mute races exercised. Microphone, recognition accuracy, speakers and audible latency unverified. `/mute` controls speech output; the separate desktop capture-pause API has different semantics. |
| Screen and clipboard | Partial | `tools/workplace.py`, `tools/content.py`, `dashboard/work_commands.py` | Explicit OS adapter fakes and policy checks; raw buffers not retained as memory. Screen path is text/OCR, not general visual question answering. No sensor activated. |
| Calendar and daily summary | Implemented | `tools/google_access.py`, `dashboard/work_commands.py`, `tools/timekeep.py` | Synthetic event read/create/edit/readback, expired auth vs unknown creation, partial outages, provenance, owner timezone and DST. No real calendar events. |
| Personal tasks and reminders | Partial | `tools/todos.py`, `tools/reminders.py`, `dashboard/work_commands.py` | Task list/add/done and persistent reminder creation/delivery/dedup/restart implemented. Reminder edit/cancel is absent from the inspected store/commands; not invented for this checklist. |
| Recurring jobs | Implemented | `native/cron.py`, `hermes/state.py` | Existing disposable-store scheduling/recovery tests; no live recurring schedules changed. |
| Search with sources | Implemented | `native/local_tools.py`, `tools/workplace.py`, `dashboard/work_commands.py` | Controlled HTML/parser and model synthesis retain source links; explicit web requests now preserve source selection. Live search not verified. |
| Hermes delegation and results | Implemented with limitation | `hermes/client.py`, `hermes/service.py`, `hermes/state.py`, `dashboard/work_commands.py` | Real client/control/job store against owned HTTP service; idempotency, cancellation, malformed responses and owning-conversation delivery. No live remote Hermes. |
| Hermes completion notification crash durability | Unclear / partial | `hermes/client.py` | Duplicate announcements are suppressed, but the announcement bookkeeping and chat insertion are not one atomic transaction. A crash between them may suppress automatic notification; durable job results remain available through `/jobs`. No crash-safe exactly-once notification claim. |
| Arbitrary provider compatibility / actual inference quality | Unverified | Provider configuration and external model server | Controlled protocol tests do not establish vendor acceptance, model quality, real context capacity or inference performance. |

The checklist's requests for every possible external write, arbitrary provider
fallback, profile security, and out-of-order callback behavior do not define
universal APIs. Tests follow the actual operations and implemented polling/state
contracts. No unsupported command, reminder mutation API, provider SDK, or
multiuser security feature was added solely to make this checklist pass.

Some checklist items remain narrower than a universal guarantee: prompt/context
budget tests do not measure provider cache hits; storage rollback/reopen tests
do not simulate every power-loss/fsync failure; retrieval budgets are not a
global memory-store capacity guarantee; polling and duplicate-result tests do
not prove every hypothetical out-of-order remote callback contract. These are
inspection/coverage limits, not passing tests for missing APIs. There is no
dedicated exhaustive live-write conformance matrix for every external service.

## Defects and minimal fixes

1. **Malformed model batches could crash or partly dispatch.** Validate the whole
   completion envelope before any proposal executes: supported text, function
   shape, bounded calls, string IDs/arguments and unique IDs. Truncated tool turns
   and tool proposals on answer-only final requests fail as provider errors.
   Malformed JSON arguments and unknown valid-string tool names still produce
   recoverable tool observations. Regression: `test_protocol_contracts.py`.
2. **Malformed SSE shapes leaked incidental exceptions.** Explicit object/array
   checks now produce useful protocol errors, while existing fragmented-call,
   cancellation and stream fallback behavior is retained. Regression: malformed
   stream cases plus existing `test_native_streaming.py`.
3. **Completed code scripts could leave child processes running.** Own the Windows
   tree in a kill-on-close job assigned before resuming the suspended parent;
   close it on ordinary completion as well as timeout/cancellation. POSIX cleans
   the owned process group on normal exit. The real-process regression proves an
   unrelated sibling survives. Windows was executed; POSIX remains unexecuted.
4. **Hermes completion could appear in the wrong conversation.** Save the owning
   conversation ID in the bounded delegation reference and route notices using
   the local stored request, rather than remote result text. Explicit monitor
   ticks prove correct conversation and duplicate suppression.
5. **Hermes malformed replies / missing token files leaked poor errors.** Require
   a JSON object response and convert missing authentication references to
   `BridgeUnavailable`. Tests use actual HTTP and temporary token files.
6. **Source selection confused web/screen/reminder requests with other tools.**
   Specific intents now retain `web.search`, `screen.read_text` and
   `reminder.create`. Read-only policy still blocks protected operations.
   Explicit namespace metadata was missing for these three existing capabilities;
   it is now supplied. Reviewed eval probes cover source choice and denials.

Red runs before those fixes recorded 16 protocol/process failures, six Hermes
failures, and seven routing failures. The initial protocol/process run also had
11 passing cases; Hermes had two passing cases. A focused combined green run
then passed 117 tests. These are independent cases/subcases, not 29 distinct
production bugs. The report's execution tables retain the exact commands and
results rather than hiding failed development runs.

## Baseline and test infrastructure corrections

The baseline ran the existing suite before production fixes: **4,806 passed,
22 failed, six skipped, 69 subtests passed** (exit 1). It took 887.31 seconds in
pytest, 889.08 seconds including the wrapper. The preliminary safety plugin was
applied to keep the campaign separate from live assistant data.

Of the 22 failures, six exposed stale evaluation counts/metadata for three
already-added capabilities; five SDK tests and ten campaign-verifier cases
attempted receipts under live `data/`. Those fixtures now own temporary roots
and close their SQLite services. One source-export failure was introduced by a
new scaffold fixture's credential-like prefix being scanned while the baseline
was still running; it was corrected to an accepted synthetic `fixture-` value.
Therefore the 22 baseline failures are not all pre-existing production defects.
Historical v1-v3 eval corpora and their assertions were retained; v4 adds probes
and a hash/byte-preservation manifest.

The final default guard is stricter than the preliminary baseline plugin. It
also blocks direct Windows credential-backend calls and handles Windows
`subprocess.Popen` audit events with a null explicit executable. That revealed
seven existing cases launching PowerShell. Their OS process boundary now returns
controlled results while retaining the actual handlers and JSON/error parsing;
no skip was added. Actual shell parsing/catch behavior is no longer claimed by
those default offline tests. The baseline's harmless shell fixtures should not
be interpreted as proof that its preliminary subprocess guard was complete.

Twelve independent calendar-routing cases also depended on a connected account
in the machine's credential backend. They now request an explicit synthetic
connected-account fixture; empty-account tests remain empty. The preliminary
baseline plugin did not guard direct backend-class credential reads, so that
baseline must not be described as proof of complete credential isolation. The
final guard replaces those reads, and the corrected routing tests run against
controlled account metadata.

During development, the new cross-process owned-port journal initially suffered
Windows append corruption. A focused run produced setup errors, not successful
integration evidence. Kernel file locking around both reads and appends corrected
the race. Temporary verifier roots exposed unclosed reliability-service handles;
those are now closed by the fixture's owning harness. Two new test expectations
were corrected: reasoning changes require idle chat, and the CLI fake response
needed an explicit smoke marker. None of these failures was hidden with broad
exception handling or a new skip.

## Remaining live and manual checks

- Real local/API inference, selected model IDs, auth, provider-specific formats,
  loaded context size, GPU offload, CPU fallback and q8 KV allocation.
- Physical microphone/wake/VAD/STT/TTS, device disconnects, audibility, barge-in
  quality, and live screen/OCR/clipboard permissions.
- Google OAuth/scopes, calendar create/edit/readback in an explicit test account,
  external memory/MCP accounts, live web search and remote Hermes connectivity.
- Interactive browser rendering/accessibility and the prior UI preferences;
  TypeScript/Node tests and the frontend build do not substitute for visual QA.
- Real Windows shell catch/error-ID behavior and Linux process-group cleanup.
- Automatic completion-notice recovery across the identified crash gap, and
  multiuser authorization if that becomes a product requirement.

No inference throughput or latency benchmark was run. Fake-clock and event
tests establish bounded behavior, not real response speed. No live messages,
calendar writes, reminder edits, production memory changes, GPU loads or service
restarts were intentionally performed in this campaign. Python guards are not a
native-process security sandbox; see the run guide's exact boundary disclosure.

<!-- GENERATED-EVIDENCE -->

## Recorded execution results

All requested full-suite cases were attempted. The full-run console result was:

```text
19 failed, 5102 passed, 6 skipped, 71 subtests passed in 1356.70s (0:22:36)
```

The full run began before the last fixture corrections. Those affected cases were then rerun against the corrected fixtures; the original full-run exit code is retained below. Counts from overlapping runs must not be added as unique tests.

| Evidence | Exit | Passed | Failed | Errors | Skipped |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline JUnit | 1 | 4805 | 21 | 0 | 6 |
| Protocol/process red | 1 | 11 | 16 | 0 | 0 |
| Hermes red | 1 | 2 | 6 | 0 | 0 |
| Routing red | 1 | 0 | 7 | 0 | 0 |
| Regression green | 0 | 117 | 0 | 0 | 0 |
| Regression confirmation | 0 | 117 | 0 | 0 | 0 |
| Focused development | 1 | 360 | 2 | 0 | 0 |
| Full coverage run | 1 | 5102 | 19 | 0 | 6 |
| Corrected fixtures | 0 | 161 | 0 | 0 | 0 |
| Exact failed-case rerun | 0 | 19 | 0 | 0 | 0 |
| Corrected smoke | 0 | 5 | 0 | 0 | 1 |
| Final source/export privacy audit | 0 | 8 | 0 | 0 | 0 |

The table uses JUnit case records. Older baseline/focused runs used the existing xUnit format, which does not preserve every pytest-subtests record the same way as console reporting; the baseline console counts above are authoritative for that run. The full runner selects legacy JUnit; its case totals match the main console totals, with the 71 passing subtests reported separately in the console. No subtest count has been added to a unique-test count.

Latest result for originally collected case IDs, after the fixture rerun: **0 unresolved failures/errors**. Unexecuted collected cases: **0** in the completed full run; skipped cases and the collection-skipped optional module are listed separately. The number of tests inside a collection-skipped module is unknown.

**295 new cases** were collected under `tests/harness/`: 231 command contracts, 26 provider/loop protocol cases, eight Hermes, eight offline-boundary, 12 state, seven routing, one process ownership, one corpus preservation, and one CLI smoke case.

### Skips and exclusions

| Test | Actual skip reason |
| --- | --- |
| `::tests.unit.test_cluster_harness_graph` | collection skipped |
| `tests.evals.test_failure_ledger::test_all_saved_development_failures_have_a_review_and_evidence` | historical local inference report is not included in this checkout |
| `tests.integration.test_entry_points.EntryPointTests::test_console_script_if_installed` | hanni not on PATH (run `pip install -e .`) |
| `tests.test_local_runtime.SafetyTests::test_web_search_live` | search unavailable (offline or rate-limited) |
| `tests.unit.test_cluster_worker_checks::test_checker_symlink_cannot_modify_an_outside_file` | Symlink creation unavailable |
| `tests.unit.test_phase3_contract_context::test_shared_contract_source_is_identical` | Separate Control Center source is unavailable; cross-project byte identity NOT TESTED. |

These skips were pre-existing environment/live-only limitations. The collection skip is the optional `langgraph.graph` dependency, which is not installed. No new skip was added to suppress a failure. The default live-search probe is blocked by the offline guard and reports its unavailable-service skip; controlled search/parser/source-provenance tests run separately. No live/hardware test was enabled. Linux, remote CI, real inference, devices and third-party account checks were not executed, and have no invented automated pass counts.

### Checks and exact commands

Working directory for commands: `C:\Projects\HANNI`. The following are literal argument vectors, avoiding shell-quoting ambiguity. Logs and full command metadata remain under `.pytest-work/assistant-harness/`. Full-run checks continued even when pytest failed.

| Step | Exit | Seconds |
| --- | ---: | ---: |
| pytest | 1 | 1358.86 |
| coverage-json | 0 | 3.109 |
| coverage-report | 0 | 2.328 |
| python-compile | 0 | 1.297 |
| frontend-types | 0 | 4.297 |
| frontend-tests | 0 | 0.313 |
| frontend-build | 0 | 6.906 |
| package-build | 1 | 0.078 |
| distribution-check | 2 | 0.094 |
| Corrected package-build | 0 | 9.36 |
| Corrected distribution-check | 0 | 0.281 |

Python wheel checks initially failed because the development environment lacked the `build` package (the repository build directory was found as a namespace instead). Installing the build tool, now included in the dev extra, resolved this environment blocker. The corrected wheel build and private-material distribution check both passed. TypeScript passed, all 37 Node tests passed with zero skipped, and the Vite build passed with its existing greater-than-500-kB bundle warning. No Python lint command is configured.

```json
[
  {
    "name": "pytest",
    "argv": [
      "C:\\Projects\\HANNI\\.venv\\Scripts\\python.exe",
      "-m",
      "coverage",
      "run",
      "--branch",
      "--source=src/hanni",
      "--data-file=C:\\Projects\\HANNI\\.pytest-work\\assistant-harness\\final\\.coverage",
      "-m",
      "pytest",
      "tests",
      "-o",
      "addopts=",
      "-o",
      "junit_family=legacy",
      "-q",
      "--tb=short",
      "--junitxml=C:\\Projects\\HANNI\\.pytest-work\\assistant-harness\\final\\pytest.xml"
    ],
    "cwd": "C:\\Projects\\HANNI",
    "exit_code": 1,
    "seconds": 1358.86
  },
  {
    "name": "coverage-json",
    "argv": [
      "C:\\Projects\\HANNI\\.venv\\Scripts\\python.exe",
      "-m",
      "coverage",
      "json",
      "--data-file=C:\\Projects\\HANNI\\.pytest-work\\assistant-harness\\final\\.coverage",
      "-o",
      "C:\\Projects\\HANNI\\.pytest-work\\assistant-harness\\final\\coverage.json"
    ],
    "cwd": "C:\\Projects\\HANNI",
    "exit_code": 0,
    "seconds": 3.109
  },
  {
    "name": "coverage-report",
    "argv": [
      "C:\\Projects\\HANNI\\.venv\\Scripts\\python.exe",
      "-m",
      "coverage",
      "report",
      "--data-file=C:\\Projects\\HANNI\\.pytest-work\\assistant-harness\\final\\.coverage"
    ],
    "cwd": "C:\\Projects\\HANNI",
    "exit_code": 0,
    "seconds": 2.328
  },
  {
    "name": "python-compile",
    "argv": [
      "C:\\Projects\\HANNI\\.venv\\Scripts\\python.exe",
      "-m",
      "compileall",
      "-q",
      "src/hanni",
      "tests"
    ],
    "cwd": "C:\\Projects\\HANNI",
    "exit_code": 0,
    "seconds": 1.297
  },
  {
    "name": "frontend-types",
    "argv": [
      "C:\\Program Files\\nodejs\\npm.CMD",
      "run",
      "check",
      "--prefix",
      "frontend"
    ],
    "cwd": "C:\\Projects\\HANNI",
    "exit_code": 0,
    "seconds": 4.297
  },
  {
    "name": "frontend-tests",
    "argv": [
      "C:\\Program Files\\nodejs\\node.EXE",
      "--test",
      "C:\\Projects\\HANNI\\frontend\\tests\\mcp_types.test.ts",
      "C:\\Projects\\HANNI\\frontend\\tests\\memory_types.test.ts",
      "C:\\Projects\\HANNI\\frontend\\tests\\mini_bridge.test.mjs",
      "C:\\Projects\\HANNI\\frontend\\tests\\workflow_types.test.ts"
    ],
    "cwd": "C:\\Projects\\HANNI",
    "exit_code": 0,
    "seconds": 0.313
  },
  {
    "name": "frontend-build",
    "argv": [
      "C:\\Program Files\\nodejs\\npm.CMD",
      "run",
      "build",
      "--prefix",
      "frontend"
    ],
    "cwd": "C:\\Projects\\HANNI",
    "exit_code": 0,
    "seconds": 6.906
  },
  {
    "name": "package-build",
    "argv": [
      "C:\\Projects\\HANNI\\.venv\\Scripts\\python.exe",
      "-m",
      "build",
      "--wheel",
      "--no-isolation",
      "--outdir",
      "C:\\Projects\\HANNI\\.pytest-work\\assistant-harness\\final\\dist"
    ],
    "cwd": "C:\\Projects\\HANNI",
    "exit_code": 1,
    "seconds": 0.078
  },
  {
    "name": "distribution-check",
    "argv": [
      "C:\\Projects\\HANNI\\.venv\\Scripts\\python.exe",
      "scripts/check_distribution.py",
      "C:\\Projects\\HANNI\\.pytest-work\\assistant-harness\\final\\dist"
    ],
    "cwd": "C:\\Projects\\HANNI",
    "exit_code": 2,
    "seconds": 0.094
  },
  {
    "name": "package-build",
    "argv": [
      "C:\\Projects\\HANNI\\.venv\\Scripts\\python.exe",
      "-m",
      "build",
      "--wheel",
      "--no-isolation",
      "--outdir",
      "C:\\Projects\\HANNI\\.pytest-work\\assistant-harness\\package-corrected\\dist"
    ],
    "cwd": "C:\\Projects\\HANNI",
    "exit_code": 0,
    "seconds": 9.36
  },
  {
    "name": "distribution-check",
    "argv": [
      "C:\\Projects\\HANNI\\.venv\\Scripts\\python.exe",
      "scripts/check_distribution.py",
      "C:\\Projects\\HANNI\\.pytest-work\\assistant-harness\\package-corrected\\dist"
    ],
    "cwd": "C:\\Projects\\HANNI",
    "exit_code": 0,
    "seconds": 0.281
  }
]
```

Baseline command (preliminary plugin; production fixes not yet applied):

```json
{
  "command": [
    "C:\\Projects\\HANNI\\.venv\\Scripts\\python.exe",
    "-m",
    "pytest",
    "-p",
    "safety_plugin",
    "-o",
    "addopts=",
    "-q",
    "--tb=short",
    "--junitxml=C:\\Projects\\HANNI\\.pytest-work\\assistant-harness\\baseline.xml"
  ],
  "exit_code": 1,
  "seconds": 889.0848758220673,
  "disclosure": "Existing suite, unchanged production implementation, safety plugin only; no live services."
}
```

Other recorded runner invocations:

```text
.venv/Scripts/python.exe scripts/test_assistant_harness.py --layer smoke --output .pytest-work/assistant-harness/smoke-corrected  # exit 0
.venv/Scripts/python.exe scripts/test_assistant_harness.py --output .pytest-work/assistant-harness/resolved-failures -- --lf --lfnf=none  # exit 0, all 19 original failures now pass
.venv/Scripts/python.exe scripts/test_assistant_harness.py --output .pytest-work/assistant-harness/fixture-rerun -- -k confirmed_safe_powershell  # exit 0
.venv/Scripts/python.exe scripts/test_assistant_harness.py --output .pytest-work/assistant-harness/eventlog-probe -- -k event_log_empty_match  # exit 1, 3 failed
.venv/Scripts/python.exe scripts/test_assistant_harness.py --output .pytest-work/assistant-harness/fixture-corrections -- -k "event_log_empty_match or confirmed_safe_powershell"  # exit 0
.venv/Scripts/python.exe -m pytest tests/integration/test_reliability_verifier.py tests/integration/test_system_v36_verifier.py -o addopts= -q --tb=short --junitxml=.pytest-work/assistant-harness/reliability-targeted.xml  # exit 1, 15 failed / 58 passed
.venv/Scripts/python.exe -m pytest tests/integration/test_reliability_verifier.py tests/integration/test_system_v36_verifier.py tests/integration/test_contracts_v36_engineering.py tests/integration/test_campaign2_capability_audit.py -o addopts= -q --tb=short --junitxml=.pytest-work/assistant-harness/fixture-corrections-complete.xml  # exit 0, 161 passed
.venv/Scripts/python.exe -m pytest tests/harness/test_protocol_contracts.py tests/harness/test_process_ownership.py -o addopts= -q --tb=short --junitxml=.pytest-work/assistant-harness/red-regressions.xml  # exit 1
.venv/Scripts/python.exe -m pytest tests/harness/test_hermes_contracts.py -o addopts= -q --tb=short --junitxml=.pytest-work/assistant-harness/red-hermes.xml  # exit 1
.venv/Scripts/python.exe -m pytest tests/harness/test_routing_regressions.py -o addopts= -q --tb=short --junitxml=.pytest-work/assistant-harness/red-routing.xml  # exit 1
.venv/Scripts/python.exe -m pytest tests/harness/test_protocol_contracts.py tests/harness/test_hermes_contracts.py tests/harness/test_process_ownership.py tests/unit/test_agent_runtime.py tests/unit/test_hermes_bridge.py tests/test_native_loop.py tests/unit/test_native_streaming.py -o addopts= -q --tb=short --junitxml=.pytest-work/assistant-harness/green-regressions-confirmed.xml  # exit 0, 117 passed
.venv/Scripts/python.exe -m pytest tests/harness/test_state_contracts.py -o addopts= -q  # exit 0, 12 passed
.venv/Scripts/python.exe -m pytest tests/unit/test_source_export.py tests/unit/test_public_release_audit.py -o addopts= -q --tb=short --junitxml=.pytest-work/assistant-harness/final-source-audit.xml  # exit 0, 8 passed
.venv/Scripts/python.exe scripts/extend_harness_corpora.py  # exit 0 after correcting metadata-row handling
.venv/Scripts/python.exe -m pip install "coverage>=7.10,<8" --quiet  # exit 0
.venv/Scripts/python.exe -m pip install "build>=1.2,<2" --quiet  # exit 0
```

A probe mistakenly appended positional test paths after the runner's existing `tests` argument and began another full collection; it was interrupted with Ctrl+C (exit 1), produced no completed JUnit report, and is not counted as verification. Its exact argument vector is retained in `reliability-probe/commands.json`. Development setup-error runs and the initial smoke failure are described above; their partial results are not represented as green evidence.

### Line and branch coverage

Scope: all `src/hanni` modules, main pytest process and Python threads. No source omissions. Child-process statements, frontend JavaScript/TypeScript and native/PowerShell internals are not instrumented. Behavior of owned child processes is checked by independent receipts/assertions. Coverage.py's combined percentage counts statements and branch exits; line and branch percentages below are calculated separately.

| Scope | Lines covered / statements | Line % | Branch exits covered / total | Branch % |
| --- | ---: | ---: | ---: | ---: |
| All Python source | 28401 / 35084 | 80.95 | 9468 / 13400 | 70.66 |
| `src/hanni/dashboard/commands.py` | 288 / 324 | 88.89 | 123 / 160 | 76.88 |
| `src/hanni/dashboard/work_commands.py` | 316 / 360 | 87.78 | 118 / 154 | 76.62 |
| `src/hanni/hermes/client.py` | 357 / 583 | 61.23 | 109 / 228 | 47.81 |
| `src/hanni/hermes/state.py` | 201 / 228 | 88.16 | 73 / 104 | 70.19 |
| `src/hanni/memory/store.py` | 412 / 473 | 87.10 | 122 / 168 | 72.62 |
| `src/hanni/native/code_execution.py` | 109 / 128 | 85.16 | 20 / 32 | 62.50 |
| `src/hanni/native/compact.py` | 51 / 64 | 79.69 | 22 / 34 | 64.71 |
| `src/hanni/native/loop.py` | 274 / 289 | 94.81 | 115 / 134 | 85.82 |
| `src/hanni/native/runtime.py` | 40 / 54 | 74.07 | 6 / 10 | 60.00 |
| `src/hanni/native/streaming.py` | 69 / 78 | 88.46 | 49 / 60 | 81.67 |
| `src/hanni/tools/base.py` | 279 / 290 | 96.21 | 87 / 98 | 88.78 |

Excluded source lines reported by Coverage.py: **90** (existing inline coverage pragmas, if any; no campaign omit pattern). Detailed missing lines/arcs: `.pytest-work/assistant-harness/final/coverage.json`; full per-module report: `coverage-report.log`. Coverage describes the full run, including its failures; targeted reruns were not merged into this coverage denominator.

## Requirement traceability

Each result below is resolved from the actual JUnit case IDs, including parameterized variants. `passed` means controlled automated evidence for the stated scope. Source paths are relative to `src/hanni/`. Broader unsupported/live behavior is described in the inventory, not inferred from these passes.

| Requirement | Source | Actual test ID / parameter family | Latest result |
| --- | --- | --- | --- |
| CLI entry point | `cli.py` | `tests.harness.test_entrypoint_smoke::test_cli_chat_subprocess_uses_fake_provider_without_model_or_devices` | 1 passed |
| Direct answer, one tool, invalid arguments/name, iteration bound | `native/loop.py` | `tests.test_native_loop (8 case records)` | 8 passed |
| Whole provider batch validates before effects | `native/loop.py` | `test_invalid_call_envelope_blocks_the_entire_batch_before_effects (6 case records)` | 6 passed |
| Unsupported content is a provider failure | `native/loop.py` | `test_invalid_assistant_content_returns_provider_failure_without_escaping (4 case records)` | 4 passed |
| Call IDs unique and paired | `native/loop.py` | `tests.harness.test_protocol_contracts::test_multiple_rounds_and_multi_call_turn_keep_ids_results_and_order` | 1 passed |
| Truncated proposals cannot execute | `native/loop.py` | `tests.harness.test_protocol_contracts::test_length_truncated_tool_turn_is_not_an_execution_authorization` | 1 passed |
| Transient failures bounded | `native/loop.py` | `test_transient_failures_have_a_fixed_retry_budget (7 case records)` | 7 passed |
| Completed writes not replayed on provider retry | `native/loop.py` | `tests.unit.test_agent_runtime::test_transient_provider_failure_does_not_reexecute_write` | 1 passed |
| Corrected tool action after schema failure | `native/runtime.py` | `tests.harness.test_protocol_contracts::test_tool_failure_can_be_corrected_without_inventing_success` | 1 passed |
| Cancellation between calls | `native/loop.py` | `tests.unit.test_agent_runtime::test_cancellation_between_calls_keeps_pairs_and_skips_second_effect` | 1 passed |
| Time budget ends without extra generation | `native/loop.py` | `tests.harness.test_protocol_contracts::test_time_budget_does_not_request_an_extra_final_generation` | 1 passed |
| Malformed streams yield protocol errors | `native/streaming.py` | `test_malformed_streams_fail_as_protocol_errors (4 case records)` | 4 passed |
| Fragmented streaming arguments | `native/streaming.py` | `tests.unit.test_native_streaming::test_fragmented_tool_arguments_are_not_executed_until_the_stream_finishes` | 1 passed |
| Explicit unsupported-stream fallback only | `native/provider.py` | `tests.unit.test_native_streaming::test_provider_falls_back_only_when_streaming_is_explicitly_unsupported` | 1 passed |
| Provider auth and usage | `native/provider.py` | `tests.unit.test_native_streaming::test_provider_streams_with_auth_and_preserves_usage` | 1 passed |
| Legacy llama HTTP/SSE adapter | `models/client.py` | `tests.unit.test_model_client.LlamaCppClientTests (7 case records)` | 7 passed |
| Reasoning requires supported effort | `dashboard/commands.py` | `tests.unit.test_chat_commands::test_reasoning_requires_advertised_support_and_applies_per_model` | 1 passed |
| Late generation cannot overwrite cancellation | `native/streaming.py` | `tests.unit.test_native_streaming::test_progress_keeps_events_and_cannot_overwrite_a_cancelled_task` | 1 passed |
| Schema and handler errors | `tools/base.py` | `tests.unit.test_agent_runtime::test_registry_validates_before_dispatch_and_contains_handler_errors` | 1 passed |
| MCP invalid arguments rejected before SDK | `mcp/adapter.py` | `test_invalid_arguments_never_reach_sdk (16 case records)` | 16 passed |
| MCP lifecycle and connection recovery | `mcp/manager.py` | `tests.integration.test_campaign2_mcp_lifecycle::test_connection_failure_returns_no_tools_then_recovers_after_owned_review` | 1 passed |
| MCP reload exact hash and disabled servers | `dashboard/work_commands.py` | `tests.unit.test_work_commands::test_mcp_reload_reconnects_enabled_servers_with_exact_config_hash_and_keeps_disabled` | 1 passed |
| MCP stale definitions and approvals | `mcp/runtime.py` | `test_definition_refresh_revokes_old_approval_and_stale_menu (2 case records)` | 2 passed |
| MCP cancellation suppresses stale result | `mcp/runtime.py` | `test_removal_during_active_call_cancels_and_never_admits_result (2 case records)` | 2 passed |
| MCP ownership cleanup | `mcp/runtime.py` | `test_owned_stdio_process_is_cleaned_but_external_http_process_is_not_adopted (2 case records)` | 2 passed |
| Read concurrency does not grant unreviewed parallelism | `tools/base.py` | `tests.integration.test_workflow_imported_parallel_verifier::test_owner_classified_external_reads_do_not_infer_safe_local_parallelism` | 1 passed |
| Exact reviewed approval hash | `dashboard/work_commands.py` | `tests.unit.test_work_commands::test_approval_detects_change_after_display_and_inside_atomic_backend_decision` | 1 passed |
| Approval expiry and denial | `hermes/state.py` | `tests.unit.test_hermes_bridge::test_approval_expiry_and_rejection_reach_boundary` | 1 passed |
| One concurrent approval claim | `hermes/state.py` | `tests.harness.test_state_contracts::test_concurrent_approval_claims_allow_only_one_dispatch` | 1 passed |
| Code RPC real process and scope | `native/code_execution.py` | `tests.unit.test_agent_runtime::test_real_subprocess_cannot_bypass_scope_or_schema` | 1 passed |
| Code output capture | `native/code_execution.py` | `tests.unit.test_agent_runtime::test_real_subprocess_tool_rpc_filters_intermediate_output` | 1 passed |
| Timeout does not execute deferred approval | `native/code_execution.py` | `tests.unit.test_agent_runtime::test_script_timeout_rejects_unapproved_rpc_instead_of_executing_later` | 1 passed |
| Normal completion reaps owned descendants only | `native/code_execution.py` | `tests.harness.test_process_ownership::test_script_completion_reaps_owned_descendants_and_preserves_unrelated_process` | 1 passed |
| Context groups, goal and bounds | `native/compact.py` | `tests.unit.test_agent_runtime::test_compaction_preserves_goal_tool_groups_and_stays_bounded` | 1 passed |
| Oversized task rejects before inference | `native/context_budget.py` | `tests.unit.test_agent_runtime::test_uncompactable_task_fails_before_provider_call` | 1 passed |
| Summary failure retains active task | `native/compact.py` | `tests.harness.test_state_contracts::test_compaction_fallback_retains_request_constraints_and_paired_recent_results` | 1 passed |
| Cancelled compression discarded | `dashboard/commands.py` | `tests.unit.test_chat_commands::test_stop_is_not_blocked_by_summarization_and_discards_cancelled_summary` | 1 passed |
| Personal memory persists and deduplicates | `memory/store.py` | `tests.unit.test_memory.MemoryStoreTests::test_remember_deduplicates_exact_memory` | 1 passed |
| Memory deletion scope vs history/backups | `memory/store.py` | `tests.harness.test_state_contracts::test_memory_deletion_does_not_claim_to_erase_history_or_backups` | 1 passed |
| Profile roots isolated | `memory/store.py` | `tests.harness.test_state_contracts::test_separate_profile_roots_do_not_share_personal_records` | 1 passed |
| Correction/deletion invalidates retrieval | `memory/retrieval.py` | `tests.unit.test_memory_context_v35::test_correction_and_deletion_cannot_use_cached_old_context` | 1 passed |
| Contradictory/stale records excluded | `memory/grounded.py` | `test_epistemic_candidates_are_not_owner_preferences (8 case records)` | 8 passed |
| External memory uses approved read-only provider | `native/agent_tools.py` | `tests.unit.test_agent_runtime::test_external_memory_requires_configured_read_only_registered_tool` | 1 passed |
| Skill metadata/on-demand body | `native/skills.py` | `tests.harness.test_state_contracts::test_skill_metadata_does_not_load_unselected_procedure_bodies` | 1 passed |
| Invalid/missing skill files | `native/skills.py` | `tests.harness.test_state_contracts::test_invalid_skill_yaml_and_missing_reference_are_explicit` | 1 passed |
| Concurrent skill revision protection | `native/skill_store.py` | `tests.harness.test_state_contracts::test_concurrent_skill_corrections_cannot_overwrite_an_unseen_revision` | 1 passed |
| Atomic action/event rollback | `hermes/state.py` | `tests.harness.test_state_contracts::test_task_transaction_rolls_back_actions_and_events_together` | 1 passed |
| Corrupt DB preserved | `hermes/state.py` | `tests.harness.test_state_contracts::test_corrupt_task_database_is_reported_not_silently_recreated` | 1 passed |
| Restart quarantines unknown effects | `hermes/state.py` | `tests.unit.test_agent_runtime::test_restart_preserves_queued_work_and_quarantines_unacknowledged_dispatch` | 1 passed |
| Wake events use actual classifier | `speech/relevance.py` | `tests.unit.test_voice_mode_notifications::test_original_wake_and_disengage_router_generate_mode_alerts` | 1 passed |
| VAD/transcript pipeline | `speech/pipeline.py` | `tests.unit.test_speech_pipeline.SpeechPipelineTests::test_process_chunk_yields_transcript_after_vad_end` | 1 passed |
| Empty transcript not retained | `speech/pipeline.py` | `tests.unit.test_speech_pipeline.SpeechPipelineTests::test_empty_stt_result_is_not_buffered` | 1 passed |
| Speech mute independent of mic/generation | `dashboard/voice.py` | `tests.unit.test_chat_commands::test_voice_mute_does_not_pause_microphone_or_cancel_generation` | 1 passed |
| Old audio cannot reappear after mute | `speech/live.py` | `tests.unit.test_desktop_voice::test_inflight_old_pump_result_is_discarded_after_mute_resume` | 1 passed |
| Explicit screen/clipboard reads | `dashboard/work_commands.py` | `test_screen_and_clipboard_are_explicit_read_only_and_raw_text_is_not_retained (2 case records)` | 2 passed |
| Calendar write ack vs uncertain readback | `tools/google_access.py` | `tests.unit.test_work_commands::test_calendar_write_acknowledged_but_readback_failure_never_promises_no_event` | 1 passed |
| DST ambiguous/nonexistent wall times | `tools/reminders.py` | `test_dst_ambiguous_and_nonexistent_reminder_times_are_not_guessed (2 case records)` | 2 passed |
| Reminder durable dedup/delivery | `tools/reminders.py` | `tests.unit.test_work_commands::test_reminders_return_schedule_and_id_and_deliver_once_after_restart` | 1 passed |
| Tasks real records and idempotency | `dashboard/work_commands.py` | `tests.unit.test_work_commands::test_tasks_add_list_done_are_real_persistent_records_and_retries_do_not_duplicate` | 1 passed |
| Daily summary sources | `dashboard/work_commands.py` | `tests.unit.test_work_commands::test_today_combines_real_tasks_and_reminders_with_calendar_and_deadlines` | 1 passed |
| Partial calendar outage distinguished | `tools/google_access.py` | `tests.unit.test_google_access::test_calendar_empty_result_and_partial_failure_have_distinct_spoken_answers` | 1 passed |
| Search references retained | `dashboard/work_commands.py` | `tests.unit.test_work_commands::test_search_synthesizes_only_from_returned_sources_and_always_returns_real_links` | 1 passed |
| Explicit web source preserved | `tools/routing_intents.py` | `test_explicit_web_research_does_not_read_local_battery_telemetry (2 case records)` | 2 passed |
| Hermes bounded context and job ID | `dashboard/work_commands.py` | `tests.unit.test_work_commands::test_hermes_receives_only_bounded_current_conversation_context_and_returns_owned_job` | 1 passed |
| Hermes owning-conversation completion | `hermes/client.py` | `tests.harness.test_hermes_contracts::test_background_completion_reaches_owning_conversation_and_is_not_duplicated` | 1 passed |
| Hermes duplicate request recovery | `hermes/client.py` | `tests.harness.test_hermes_contracts::test_reconnect_same_request_recovers_acknowledgment_without_duplicate_job` | 1 passed |
| Cancel before Hermes submission | `hermes/client.py` | `tests.harness.test_hermes_contracts::test_cancellation_before_submission_reaches_real_control_without_remote_job` | 1 passed |
| Hermes malformed replies | `hermes/client.py` | `test_malformed_bridge_top_level_response_is_a_protocol_error (4 case records)` | 4 passed |
| Missing authentication honest | `hermes/client.py` | `tests.harness.test_hermes_contracts::test_missing_authentication_reference_is_honest_unavailability_not_path_exception` | 1 passed |
| Child context/tool isolation | `native/worker.py` | `tests.unit.test_agent_runtime::test_child_has_separate_context_and_inherits_only_scoped_tools` | 1 passed |
| Foreground remains available | `native/worker.py` | `tests.unit.test_agent_runtime::test_background_approval_does_not_block_foreground_worker` | 1 passed |
| Concurrent tabs do not leak context | `dashboard/chat.py` | `tests.unit.test_chat_conversations::test_native_chat_never_injects_another_tabs_history` | 1 passed |
| Queue ordering | `compute/scheduler.py` | `tests.integration.test_performance_v42_verifier::test_queue_optimization_preserves_same_worker_fifo` | 1 passed |
| Owned shutdown | `dashboard/server.py` | `tests.integration.test_campaign8_ui_backend::test_owned_shutdown_reaches_original_event_and_chat_lifecycle_only` | 1 passed |
| Credentials redacted from logs | `logs/redaction.py` | `tests.integration.test_campaign9_api_security::test_registered_synthetic_secret_not_in_logs` | 1 passed |
| Retrieved metadata stays inert | `mcp/host.py` | `tests.unit.test_workflow_model_context::test_untrusted_metadata_stays_in_data_message_and_cannot_change_output_contract` | 1 passed |
| Configuration precedence | `config/loader.py` | `tests.unit.test_config.ConfigLoaderTests::test_env_log_level_override` | 1 passed |
| GPU/CPU q8 launch configuration | `native/acceleration.py` | `test_gpu_preference_and_cpu_fallback_always_keep_q8 (3 case records)` | 3 passed |
| Default no external/live network | `tests/support/hanni_test_guard.py` | `tests.harness.test_offline_guard::test_external_tcp_is_blocked_before_connecting` | 1 passed |
| Default no live production DB | `tests/support/hanni_test_guard.py` | `test_production_storage_is_unavailable_even_when_application_defaults_are_wrong (3 case records)` | 3 passed |
| Offline child inheritance | `tests/support/sitecustomize.py` | `tests.harness.test_offline_guard::test_python_child_inherits_the_offline_guard` | 1 passed |
| Historic eval corpus preserved | `evals/llm_tools/capability_coverage_v4_migration.json` | `tests.harness.test_corpus_extension::test_v4_only_appends_existing_workplace_tool_probes_to_unchanged_v3` | 1 passed |

### All registered slash commands

Every row below has seven real router cases: valid semantics, uppercase/trailing whitespace, missing arguments, Unicode data/error, embedded NUL rejection, oversize rejection, and behavior during active work. The direct API also has six parser-rejection cases and a catalog/help consistency test. Parameterized IDs are in `tests.harness.test_command_registry`; the semantic ID is `test_valid_command_selects_handler_and_changes_observable_state[COMMAND]`.

| Command | Implementation source | Actual semantic test suffix | All seven cases |
| --- | --- | --- | --- |
| `/help` | `dashboard/commands.py` | `...[help]` | 7 passed |
| `/new` | `dashboard/commands.py` | `...[new]` | 7 passed |
| `/history` | `dashboard/commands.py` | `...[history]` | 7 passed |
| `/resume` | `dashboard/commands.py` | `...[resume]` | 7 passed |
| `/retry` | `dashboard/commands.py` | `...[retry]` | 7 passed |
| `/undo` | `dashboard/commands.py` | `...[undo]` | 7 passed |
| `/stop` | `dashboard/commands.py` | `...[stop]` | 7 passed |
| `/status` | `dashboard/commands.py` | `...[status]` | 7 passed |
| `/context` | `dashboard/commands.py` | `...[context]` | 7 passed |
| `/compress` | `dashboard/commands.py` | `...[compress]` | 7 passed |
| `/model` | `dashboard/commands.py` | `...[model]` | 7 passed |
| `/reasoning` | `dashboard/commands.py` | `...[reasoning]` | 7 passed |
| `/voice` | `dashboard/commands.py` | `...[voice]` | 7 passed |
| `/wake` | `dashboard/commands.py` | `...[wake]` | 7 passed |
| `/mute` | `dashboard/commands.py` | `...[mute]` | 7 passed |
| `/memory` | `dashboard/commands.py` | `...[memory]` | 7 passed |
| `/remember` | `dashboard/commands.py` | `...[remember]` | 7 passed |
| `/forget` | `dashboard/commands.py` | `...[forget]` | 7 passed |
| `/tools` | `dashboard/commands.py` | `...[tools]` | 7 passed |
| `/connections` | `dashboard/commands.py` | `...[connections]` | 7 passed |
| `/today` | `dashboard/work_commands.py` | `...[today]` | 7 passed |
| `/calendar` | `dashboard/work_commands.py` | `...[calendar]` | 7 passed |
| `/remind` | `dashboard/work_commands.py` | `...[remind]` | 7 passed |
| `/tasks` | `dashboard/work_commands.py` | `...[tasks]` | 7 passed |
| `/search` | `dashboard/work_commands.py` | `...[search]` | 7 passed |
| `/screen` | `dashboard/work_commands.py` | `...[screen]` | 7 passed |
| `/clipboard` | `dashboard/work_commands.py` | `...[clipboard]` | 7 passed |
| `/hermes` | `dashboard/work_commands.py` | `...[hermes]` | 7 passed |
| `/jobs` | `dashboard/work_commands.py` | `...[jobs]` | 7 passed |
| `/approve` | `dashboard/work_commands.py` | `...[approve]` | 7 passed |
| `/deny` | `dashboard/work_commands.py` | `...[deny]` | 7 passed |
| `/reload-mcp` | `dashboard/work_commands.py` | `...[reload-mcp]` | 7 passed |

No registered slash command from the proposed list is missing. Reminder cancellation/editing, universal aliases/quoting, multiuser RBAC and arbitrary vendor adapters remain absent/partial as described above. Command coverage does not grant those capabilities.

### Evidence integrity

The summary below is committed as `evidence.json`; detailed logs, JUnit and Coverage.py output remain local ignored artifacts. File hashes identify the tested regression sources and retained evidence, rather than claiming the entire uncommitted repository is reproducible from HEAD alone.
