# Phase 1: everyday answers and streaming voice

Status: **PARTIAL / NOT ACCEPTED**. The frozen simple-task gate is below target,
and physical speech responsiveness is **NOT TESTED**. This is an implementation
and measured text improvement, not a completed JARVIS-style voice acceptance.

## What changed

- Unambiguous, fully resolved CPU/RAM, process, disk, time and platform reads can
  use the original capability executor without an optional model-selection turn.
  Required arguments must already be bound or optional. Normal permissions,
  audit, verification, emergency stop and bounded safe-read retry still apply.
- Verified common reads use concise presentations of their typed evidence.
  Verified action receipts are deduplicated; failed or uncertain actions cannot
  become success claims. Calendar receipt uncertainty remains explicit.
- Ordinary knowledge replies receive an answer-first, one-to-three-sentence
  instruction. Complete final-answer sentences are emitted as they become
  available. Hidden thinking spans and ungrounded first-person action claims
  are withheld, including from short-term conversation history.
- Read-only typo correction reuses the existing semantic vocabulary and current
  metadata. It applies only when initial retrieval fails and does not rewrite
  literal arguments. Plain independent observation clauses receive a bounded
  menu that represents each part before adding alternatives.
- A model can request one bounded metadata rediscovery when the initial menu is
  insufficient. Reformulated text cannot resolve or authorize a new write.
  Original resolved actions and fixed arguments are retained; definitions and
  permissions are checked again at dispatch. The menu never exceeds eight tools.
- Persistent or dependent multi-action requests go to the existing workflow
  controller for a proposal/review. The conversational loop does not execute a
  saved workflow or manufacture its approvals.
- The voice adapter has bounded generation and speech queues. It speaks final
  sentences using the existing TTS backend while subsequent generation continues.
  Barge-in and dashboard interruption also work during generation. Cancellation
  clears queued speech and fences subsequent tool dispatch and stale responses.
  Generation ownership is serialized so superseded workers cannot overlap a new
  turn's execution. Recent actually dispatched sentences remain available to the
  existing echo classifier.
- Ephemeral scalar timings expose routing, admission, tool execution,
  verification, useful-answer presentation and TTS dispatch. Dispatch is explicitly
  distinguished from acoustic onset. Prompts/audio are not stored by this observer.

No configuration or default-model change was made. Existing user changes,
Control Center integration, wake behavior, voice identity, safety and privacy
settings were retained. No remote service was started/stopped or used for this
evaluation; no models were downloaded, and nothing was pushed or published.

## Actual paths inspected

Text/dashboard: `cli._run_typed` -> existing workflow/control/stop handling ->
`ChatSession` -> `MemoryAwareSession` -> `McpToolSession` -> `McpHost.route` ->
bounded schemas -> `complete_with_tools` -> original `ToolRegistry.execute` ->
verification/CompletionLedger -> guarded presentation -> dashboard updates.
The no-tool branch reaches `TextSession` and the resident client's content stream.
Memory/context and sharing policy remain below the interface. Adaptive routing
wraps inference in the actual app; the reproducible evaluation explicitly pins
the already-running configured loopback model and does not operate remote workers.
The benchmark uses a fresh conversation per case and a single client attempt; it
does not reproduce owner memory/context, dashboard polling, cold starts or every
adaptive admission/retry path.

Voice: microphone -> in-memory rolling buffer -> Silero VAD/utterance segmentation
-> faster-whisper -> `TranscriptPump` -> wake/relevance/attention bridge -> the
same conversation layers -> final-sentence response pump -> existing TTS `start`
-> existing playback handle. Owner emergency stop and barge-in are processed while
generation or playback is pending. The old path generated the entire answer
before calling TTS; the new path schedules eligible final sentences immediately.

Tool-selection completions remain non-streaming: tool arguments and their hidden
reasoning are never spoken. Action-result speech is released only after the
existing executor and verification have produced supporting evidence. An already
dispatched action cannot be rolled back by cancellation and is never silently
replayed. Pending blocking HTTP/handler work is cooperatively fenced, not forcibly
killed; it can delay the next generation until the serialized owner is released.

The utterance end currently comes from the VAD segment, including silence/padding;
it is not an independently measured last owner phoneme. No dispatch or VAD proxy
is reported as end-of-owner-speech to first audible answer.

## Baseline and measured text responsiveness

The current source/configuration was captured before edits in
`data/phase1/baseline/`. Historical reports were not used as measured passes.
Both development runs used the same 13 live text cases twice: **26 turns before,
26 after**. An isolated data directory prevented access to owner memory/history.
Handlers were real, explicitly permitted local observations; the model was real.
No handler/model mocks were used in these latency measurements. Synthetic
provider scope is used only for metadata routing checks, with execution disabled.

Hardware: Windows 11 build 26200, Intel family 6/model 183 CPU, 24 logical CPUs,
33,943,097,344 bytes RAM. After-run local inventory reports an NVIDIA GeForce
RTX 5060 Laptop GPU with 8,151 MiB VRAM. Exact model GPU placement is **not
independently verified** because the existing external loopback server was reused.
The observed model path is the configured Qwen3.5-4B-Q4_K_M GGUF; API identity is
`supervisor`. Configured and observed context: 16,384; one slot; request temperature
0.35, top-p 0.9, max output 768; thinking disabled. Server defaults differ from
explicit request settings; the actual client overrides them. Source/config hashes
are unchanged after the held-out evaluation, and baseline/final YAML bytes match.

All values below are milliseconds, rounded. They are end-to-end/stage observations,
not tokens-per-second substitutions.

| Measurement | Before P50 / P95 | After P50 / P95 |
| --- | ---: | ---: |
| Routing, including ledger routing | 0.77 / 3.76 | 0.87 / 4.82 |
| Observable first model content, streaming calls only | 263 / 320 | 212 / 334 |
| Tool + original registry boundary | 5.92 / 1899.50 | 6.61 / 2152.63 |
| Verification observer spans | 0.024 / 0.047 | 0.029 / 0.158 |
| First complete visible answer, sentence-boundary proxy | 1195 / 3392 | 477 / 2764 |
| Total text response duration | 1197 / 3394 | 479 / 2766 |

Answer length on the matched development runs was **17.5 / 42 words** before
and **14 / 34.8 words** after (P50/P95). Sentence count stayed **1 / 2**. Held-out
answer length was **11 / 33.9 words**, with **1 / 2** sentences.

The streaming first-content sample counts differ (10 before, 8 after) because
direct checks now need no model call; blocking tool-selection token onset is not
observable and is not fabricated. Tool time includes registry verification, and
the verification observer can include nested checks; those rows are **not additive
exclusive stages**. Native after-run timings separately expose `tool_execution`
and `registry_verification`. OS process enumeration/sampling still dominates
some read tails and was not changed.

For answers that passed the independent simple-evidence checks, first useful
visible answer was **1209 / 1736 ms** before (10 passing samples) and
**198 / 2606 ms** after (14 passing samples). These are conditional cohorts of
different sizes, not a paired claim that P95 improved. The validated-answer tail
did not improve. Failed cases remain in success denominators; the overall
sentence-boundary row is not a claim of semantic correctness for every reply.

Model server queue time: **NOT MEASURED**, since the endpoint supplies no
independently observable admission timestamp. Local admission spans do not prove
server queue time. Physical STT, first audible useful answer, end of owner speech
to audible answer, full spoken duration, and physical interruption latency:
**NOT TESTED**. The saved microphone and speaker were unavailable in the current
startup environment; no replacement devices or voice were silently selected.

## Frozen held-out acceptance

Development has 20 cases; held-out has 48 separate cases. Held-out cases and
scoring were frozen before implementation. The final implementation was frozen
before evaluation and was not tuned against its failures.

- Held-out SHA256:
  `bdcde76d364301f9b920d66d3b8a3ced7ca2d92155bb51f52174ced2ea364016`
- Scoring SHA256:
  `a75723265526abc90d5371280d4e266df8494483bf61d919788c923338dd907b`

| Gate | Result | Target | Outcome |
| --- | ---: | ---: | --- |
| Initial required-tool recall, supported cases | 29/30 = 96.7% | 95% | PASS |
| Independently checked simple live tasks | 23/27 = 85.2% | 90% | FAIL |
| Ordinary live replies within three short sentences | 39/39 = 100% | 90% | PASS |
| Unauthorized/duplicate execution regressions | 359 tests + 13 subtests passed | No new violations | Controlled checks pass; live actions NOT TESTED |
| Physical voice acceptance | NOT TESTED | Live measurement | OPEN |

Independence here means a separate evaluator uses finite/bounds/schema predicates
and evidence-value/label checks, without reusing Hanni's verification function.
It does not constitute an independent human semantic-quality review. Brevity
alone does not establish useful or correct knowledge answers.

The frozen corpus has an authoring limitation: six expected groups refer to
unsupported names (`system.info`, `battery.status`/`power.status`), while the
current registry uses `system.os_info` and `system.battery`/`power.battery_detail`.
Those six cases are disclosed and excluded only from **supported recall**. The
three live system cases remain failures in simple-task scoring; they were not
renamed or removed after the freeze. Battery cases are routing-only. Six action
cases are also routing-only, not live action-success measurements.

Remaining simple failures:

- `h-time-2`: “today's calendar date” retrieved Google agenda instead of local
  date. The local-only evaluator refused that provider; no Google request ran.
- `h-system-1`, `h-system-2`, `h-system-3`: frozen unsupported expected names.
  Actual routing also sent an installed-RAM question to a usage snapshot, so the
  inventory/usage distinction needs a new development cycle. OS reads outside
  the seven-handler live allowlist were refused rather than executed.

The final held-out run had 39 live replies. First complete visible answer was
**643 / 3254 ms**, total text duration **645 / 3255 ms**. Passing simple answers
had first useful visible latency **1415 / 4083 ms** (23 samples). Multi-resource
process checks still have long tails. The evaluator also refuses unlisted pure
calculator handlers; arithmetic failures in that constrained environment are
not evidence that the production calculator is unavailable. No failed tool
request silently falls back to an ungrounded model answer.

Rediscovery safety/behavior was checked with controlled model doubles. The
supported recall figure above is initial-menu recall, not a manufactured
post-rediscovery model-selection pass rate. Live rediscovery effectiveness and
live actions require separate future coverage.

## Reproduction

From the repository root with its existing Python environment:

```powershell
.\.venv\Scripts\python.exe scripts/phase1_eval.py --output data/phase1/routing-reproduction.json
.\.venv\Scripts\python.exe scripts/phase1_eval.py --live --repeats 2 --output data/phase1/development-reproduction.json
.\.venv\Scripts\python.exe scripts/phase1_eval.py --cases evals/phase1/heldout.json --live --output data/phase1/heldout-reproduction.json
```

The loopback model must already be running with the configured identity. The
script refuses an identity mismatch and does not start/download a model. Do not
use reproduction failures to tune against this held-out set. Repeated live runs
can vary with OS load and model sampling; the first frozen final run is the
acceptance result, not the best of multiple runs.

The exported review archive includes `phase1_evidence/baseline/src`, configuration
and manifests. To measure that captured implementation in an extracted project:

```powershell
.\.venv\Scripts\python.exe scripts/phase1_eval.py --source-root phase1_evidence/baseline/src --live --repeats 2 --output data/phase1/baseline-reproduction.json
```

Run all focused engineering checks with `powershell -NoProfile -File scripts/check_phase1.ps1`.

Focused suites: `test_phase1_response`, `test_orchestrator`, `test_model_client`,
`test_attention`, `test_barge_in`, `test_tools`, `test_reliability_execution`,
`test_mcp`, `test_mcp_session`, `test_campaign1_routing_regressions`,
`test_voice_interruption`, `test_desktop_voice`, speech buffer/pipeline and safety
suites; plus MCP Hub registry/API/manager and workflow readback/registry/planner.
The two runs passed 253 and 106 tests respectively, plus 13 subtests. These are
controlled engineering tests, not physical speech evidence.

Private raw measurements remain in `data/phase1/`; source export includes only
the aggregate summary/manifests, not owner data, transcripts, credentials,
audio, model weights or raw process observations. Restart Hanni's local backend
to load source changes when appropriate; the running deployment was not restarted
or represented as updated by this evaluation.

## Phase 2 handoff

1. Start a new development cycle for date-versus-agenda and installed-versus-used
   memory/inventory semantics. Retain this frozen failure ledger. Author a new
   independent held-out set using current registered capability identifiers.
2. Expand independently checked factual answer quality and bounded rediscovery
   coverage; include authorized, reversible live actions only after explicit
   authorization and maintain duplicate/uncertain-write checks.
3. Test the configured voice on owner-selected working devices. Measure actual
   owner speech end and acoustic onset separately from VAD end, generation,
   synthesis dispatch and playback scheduling. Report P50/P95 and sample counts.
4. Investigate process enumeration and multi-resource tails with exclusive phase
   timing and a real model admission/queue signal. Do not hide missing queue data
   behind throughput or combine overlapping verification spans.
5. Validate barge-in while a non-streaming model request/handler is blocked,
   cancellation before first speech, echo across sentence transitions, emergency
   stop, stale queue rejection, wake identity and actual audible continuity.
6. Re-evaluate all acceptance gates. Phase 1 remains unaccepted until the simple
   success and required physical-voice gates have valid passing evidence.
