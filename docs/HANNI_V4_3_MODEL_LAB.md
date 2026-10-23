# HANNI Model Intelligence Lab

V4.3 adds a Model Lab to the existing HANNI OS desktop. It uses the registered
models, original adaptive inference admission, existing evaluation functions
and audited desktop controls. Package version is `0.13.0`.

See [milestone checkpoints](HANNI_V4_3_CHECKPOINTS.md) and the
[independent review](v43-reviews/INDEPENDENT_REVIEW.md) for implementation,
real-run and visual verification evidence. The working model runtime,
workflow controller, MCP authorization and external process ownership remain
authoritative.

## Models and measured properties

The overview separates configured models, known installed files, observed
residency and current endpoint availability. A failed connection does not prove
that a remote model is uninstalled or unloaded. Unknown architecture, parameter
count, hardware or verified context is displayed as unknown. Configured GPU
preferences and quantization remain distinct from current observations.

Model detail combines metadata with original capability/context proofs and
V4.2 timing samples. Health and resource sampling times matter: a saved
benchmark's hardware snapshot describes that run, not current telemetry.
Recent profiles may include unscored runtime observations. These do not grant
accuracy or tool support to an unverified model.

## Implemented evaluation scopes

| Suite | What executes | Meaning of the result |
| --- | --- | --- |
| Structured JSON development | Real selected-model inference | Exact parsed JSON/type checks against fixed development expectations |
| LLM tool development | Real selected-model inference with synthetic MCP results | Original weighted/strict tool rubric, with its lexical answer checks disclosed |
| Capability retrieval development | Original deterministic router/evaluator | Retrieval and argument-resolution checks; no model inference or real tool execution |
| Verified file-read development | Real model plus the original scoped read-only MCP handler | Actual file-read verification receipt and the fixed final-token check |

Only implemented suites are offered. The file-read suite owns a fixed synthetic
fixture in private lab storage; the UI cannot supply a file path, command or
capability name. Synthetic tool scores are not actual task-completion receipts.
Model-only correctness is distinct from tool verification and end-to-end
workflow execution.

These are exposed development datasets. They are not untouched final holdouts.
The lab does not open final holdout corpora, change expected answers, rescore
results to inflate a score or publish development results as adaptive capability
or quality proofs. Existing CLI evaluation commands remain available.

## Running and reviewing a benchmark

Choose a supported suite and, for a model-required suite, an eligible registered
endpoint. The runner accepts only bounded evaluation settings. Its selected
case count and repetitions are explicit; a subset is not labeled a complete
corpus evaluation. Fixed sampling and suite/scoring conditions are recorded.

The selected model is pinned for the whole run. Model failures do not silently
fall back to another model. Original context, resource, privacy, health and
interactive-reserve checks still apply before each inference or tool operation.
A benchmark does not expand the configured context allocation or create another
GPU slot. The local primary retains its one nonpreemptive serving slot.

The runner preflights the unchanged structured-output workload against the
original conservative UTF-8 message-byte admission policy. The 400-line long
case needs more context than the current primary's configured 16K limit under
that policy. It is rejected before inference and is not recorded as an
incorrect model answer. Selecting the short case remains supported. The lab
does not truncate the long prompt to obtain a passing score.

Progress is the number of committed case results, with the current case and
run state shown separately. Pause/cancel act at a case boundary: an already
running case may finish before the control takes effect. These controls do not
kill or adopt a model server. A checkpoint can resume only with compatible
immutable dataset, scorer, selected cases, model identity and run settings.

Results Explorer shows per-case expected behavior, observed output, available
tool calls/receipts, outcome and failure evidence. Timing scope and sample
counts accompany statistics. Missing first-token, processing-rate or peak-memory
observations stay unknown. A successful HTTP request is not evidence that the
model answered correctly.

## History, export and comparison

Private SQLite storage retains run manifests and committed per-case results.
History supports search/filter and result inspection. Export uses the lab's
fixed result format and redacts sensitive evidence; it cannot write arbitrary
paths or execute commands supplied by the browser.

History filtering and pagination operate on stored runs, including runs older
than the latest page. Case evidence has separate bounded pagination. Large
exports use bounded continuation pages; incomplete exports must not be labeled
complete. Downloads retain the backend's already-redacted serialized manifest
and case JSON, preserving numeric types and their configuration/protocol/case
hashes. The browser validates protocol and ordinal continuity before completing
the file. Serialized transport pages have a 16 MiB wire bound; encoded JSON
strings are not passed through scalar evidence truncation.

A second lab process can inspect the store without taking ownership
of another process's active benchmark. Corrupt, linked or unavailable optional
lab storage disables lab controls while preserving existing evidence and the
rest of the dashboard.

Comparisons require matching suite, dataset, selected cases, scoring and run
conditions, with incomplete/incompatible runs explained. Model identities,
configuration and hardware are visible tradeoffs. Different hardware may make
speed measurements informative without establishing a model-quality advantage.
The interface does not automatically declare a winner from one score or a
single timing observation.

Routing insights show the original selector's policy, recent decisions,
selection reasons, excluded endpoints, capability/context evidence and V4.2
performance history. Lab results remain separate from validated routing proofs.
V4.1 collaboration receipts retain their original execution/verification scope;
the lab does not relabel them as newly executed benchmark runs.

## Integration and limits

`hanni.evals.model_lab` adapts existing suites and stores lab runs.
`hanni.dashboard.model_lab` exposes fixed audited controls through the original
`ToolRegistry`. `DashboardServer` provides the private token-gated API. No
frontend shell execution, arbitrary endpoint URL, dataset path or expected
answer is accepted.

Missing development corpora disable their suites with a reason. Repo-independent
installations should retain the original development dataset files when those
suites are wanted. Existing model weights and primary configuration are not
replaced or downloaded by this implementation.

An already running dashboard server needs a normal HANNI restart to load Python
backend changes. Verification preserves pre-existing assistant/model processes
and uses a separate private dashboard built from the current source.

Fresh remote model/resource access is required for live remote comparisons.
An unavailable configured worker remains visible with unknown current
properties. Historical metadata, browser fixtures and earlier reports cannot
substitute for a current model run. Broader model context limits require their
own actual inference checks; V4.3 does not infer 128K support from a name.

## Verification evidence

The independent live API campaign passed 18 checks across five persisted runs:
ten exact short JSON results, five actual `VERIFIED` file reads, two strict
passes under the original synthetic-tool heuristic rubric (mean 97.5/100), and
ten deterministic retrieval passes. It checked real pause/cancel/resume,
persisted ordinal coverage, exported hashes and comparable conditions. These
27 cases are limited development coverage, not a full model-quality evaluation.

Two additional native UI starts each produced three genuine short structured
responses. Combined evidence contains seven persisted runs, 33 cases and 34
actual model turns. The native Windows/WebView2 interaction campaign passed
14 checks; final client-only screenshots, the independent visual rubric and
cleanup receipt are recorded in the linked independent review.

The separate independent fixture suite passed 63 cases: 45 backend and 18 HTTP
checks. Six browser/display-fixture checks cover older history and responsive
layouts; fixture values do not represent live model measurements. Frontend
tests passed 41 checks. The final post-correction repository regression passed
**2,035 tests and 25 subtests**, with two documented skips, in **397.05 seconds**.
The separately retained initial pre-correction regression passed 2,033 tests
and 25 subtests in 402.88 seconds. The skips
are an absent historical private inference report and the `hanni` console
script not being on PATH in this environment.

Release `0.13.0` was built without downloads. Verification matched all 196
packaged source/static files against the workspace, confirmed the current
README and local Geist license/assets, and imported 12 runtime modules directly
from the wheel. The final wheel SHA256 is
`f1e6791e465c976bf0c84bd5c36d374d2d53634194e7c00867ab2f77d2c4e0bb`.
Private evidence remains under ignored `data/v43-verification`
and `data/v43-manager`. Screenshots and the readable independent report are
under `docs/v43-reviews`.

Independent native review scored **9.0/10**, with AI-template appearance
**1.3/10**. Final native export and every saved API export passed case,
configuration and protocol hash checks after the serialization correction.
All owned review helpers closed; the manager independently reconciled closure
and preservation of the external original HANNI application and model process.

The primary model was an already running external original HANNI process,
freshly verified through original transport/manager identity and configuration
checks. Timings describe a shared server and do not establish competitive
performance. Remote workers were unavailable during this campaign; no actual
cross-model winner is claimed. Pre-existing assistant/model ownership is
preserved.
