# H.A.N.N.I. Decision Record

Concise record of resolved specification conflicts and implementation choices.
Each entry states the decision, the reason, and what would change it. New
entries are appended; existing entries are amended only with owner approval.

Sources of truth: `HANNI_MASTER_SPEC.md` (long-term architecture) and
`HANNI_V1_IMPLEMENTATION_PLAN.md` (current scope). Where they conflict, the
conflict is recorded here before code follows either.

---

## D-0001 - Spec file names inside the repository

**Decision.** The Master Spec (delivered as `HANNI_PROJECT_PROMPT_v3.md`) is
committed as `docs/HANNI_MASTER_SPEC.md`; the V1 plan as
`docs/HANNI_V1_IMPLEMENTATION_PLAN.md`. `CLAUDE.md` references these paths.

**Why.** `CLAUDE.md` named a `HANNI_MASTER_SPEC.md` that did not exist. One
canonical location removes ambiguity for every future session.

## D-0002 - Repository layout

**Decision.** The V1 plan's layout (§20) is used: Core in `src/hanni/`, the
Daily PC node in `node/windows/`. The node directory is installed as the
`hanni_node` package (pyproject `package-dir` mapping) so both roles ship in
one wheel with two console entry points, `hanni-core` and `hanni-node`. A small
`src/hanni/config/` package (schemas, loader, secrets) and `src/hanni/logs/`
package are added to the V1 tree; they are plumbing, not new architecture.

**Why.** The Master Spec sketches a flat `hanni/` tree; the newer V1 plan is
more specific and keeps the node physically separate from the Core, which
matches the "Discord/Node are interfaces, not the core" principle. Shared
schemas (events, protocol) live in `hanni.core` and are imported by the node.

## D-0003 - Retry budget

**Decision.** One configuration key, `recovery.max_attempts` (default `3`),
meaning total attempts including the first. The Master Spec's rule that a
retry after two failures must change plan or tool is implemented by the
Supervisor loop in Milestone 9.

**Why.** The Master Spec says "retry up to 2 times"; the V1 plan says "3 total
attempts". These are the same budget described differently; a single
configured number avoids two constants drifting apart.

## D-0004 - Permission levels under High Autonomy Owner Mode

**Decision.** The Master Spec's four levels are kept. The owner profile
auto-approves Levels 0-2. Level 3 (bulk/permanent deletion, disk formatting,
security or credential changes, elevated/admin execution, money, external
publishing, factory reset) always requires explicit confirmation. Both rules
are enforced in code (`hanni.config.schema`): a config that marks Level 3
auto-approvable or a profile above Level 2 is rejected at load time.

**Why.** The Master Spec's "Level 2 requires confirmation" predates the
locked High Autonomy decision; the V1 plan (§11) makes Levels 0-2 automatic
for the owner. Elevated privileges are explicitly listed as dangerous in the
Master Spec, so admin execution stays at Level 3.

## D-0005 - Who may trip and clear the emergency stop

**Decision.** Anyone (any Discord user, the local machine, internal watchdogs)
may *trip* the stop. Only the authenticated owner or the local machine may
*clear* it. Both rules live in `hanni.core.shutdown` and `hanni.core.identity`
and involve no LLM.

**Why.** The specs restrict clearing, not tripping. Stopping is always the safe
direction; refusing a stop because the requester was not verified would be the
wrong failure mode for a safety mechanism.

## D-0006 - Secrets policy

**Decision.** Secrets come only from the environment, optionally seeded from a
git-ignored `.env` (real environment wins). YAML files are scanned at load and
rejected if any secret-like key (`token`, `secret`, `password`, `api_key`,
`private_key`) holds a string value. Loaded secret values are registered with
the log redaction layer; error messages and health reports name secrets, never
values.

**Why.** Master Spec "Secrets Management" and V1 §24. Enforcing the rule at
load time makes an accidental paste into YAML fail loudly instead of silently
working.

## D-0007 - Milestone 0 schema implementation: stdlib now, pydantic in M1

**Decision.** Milestone 0 uses stdlib dataclasses with explicit validation for
configuration and event schemas, and `unittest`-style tests (which pytest also
collects). pydantic v2 is introduced in Milestone 1 alongside the model client,
where typed tool-argument and API schemas begin. `hanni.config.schema` and
`hanni.core.events` are the only modules that change.

**Why.** The build environment had no PyPI access, so pydantic and pytest could
not be exercised. Shipping validated schemas that were actually run beats
shipping untested pydantic models. The dependency list in `pyproject.toml`
stays honest about what is required today.

## D-0008 - Shared emergency-stop state file per machine

**Decision.** Both roles honour one state file, `<data_dir>/emergency_stop.json`.
A stop tripped from either CLI on a machine puts every H.A.N.N.I. process on
that machine into Safe Mode; the state survives restarts; an unreadable file
fails safe (treated as tripped). The V1 channel name `#hanni-agent-work` is used
where the Master Spec says `#hanni-agent-tasks`.

**Why.** On a single development machine running both roles, a stop must stop
everything. Persisting the state prevents a crash-restart from silently
resuming automation, which the Master Spec's "Safe Mode until the owner
explicitly says to resume" requires.

## D-0009 - V1 collapsed to a single Windows laptop

**Decision.** V1 runs entirely on one Windows laptop (V1 plan §1). The
two-machine split (Server PC "Core" + Daily PC "Node"), Discord, and the
Core <-> Node network protocol are deferred to a later version (V1 plan §22;
Master Spec §35-36). The revised plan was delivered as
`HANNI_V1_IMPLEMENTATION_PLAN_SINGLE_PC.md`; per D-0001 it is committed as
`docs/HANNI_V1_IMPLEMENTATION_PLAN.md`. Consequences:

* `node/windows/` (the `hanni_node` package), `hanni.discord`,
  `hanni.networking`, `hanni.database` (SQLite lives under `hanni.memory` in
  the V1 plan §19 layout) and the second console entry point are removed.
  There is one entry point, `hanni`. The last two-PC state is tagged
  `m0-two-pc-architecture` (commit cbec9f6); nothing is parked in the working
  tree.
* `NodeRole` is removed. Secrets, the health check, and logging no longer vary
  by role. `HANNI_NODE_ID` is kept as an optional machine label in logs
  (default: the hostname) because Master Spec §36 may later add machines.
* Models carry no `node` placement key; every model runs on this laptop.
  `models.yaml` starts with the Supervisor and the on-demand vision model only
  (V1 plan §5). Router/coder specialists return with Milestones 3/10 if they
  prove useful; Milestone 1 settles the exact model files for the RTX 5060.
* Event names follow V1 plan §18 (plus `SYSTEM_ALERT` from Master Spec §32 and
  `EMERGENCY_STOP_CLEARED` so resume is observable). `DISCORD_MESSAGE`,
  `NODE_CONNECTED`, `NODE_DISCONNECTED` are removed. `Event.source` names the
  component that emitted the event, not a machine.
* Supersedes D-0002 (layout) and D-0008 (shared state file "per machine, both
  roles"; Discord channel names). One machine, one process family; the
  emergency-stop state-file semantics are unchanged. D-0005 stands; "any
  Discord user" now reads "any actor, including the LLM and unverified voice".

**Why.** The owner simplified V1 so the project reaches a working voice
assistant quickly (V1 plan: Purpose). Keeping role plumbing "just in case"
would be the speculative infrastructure Master Spec §42.15 forbids, and the
old role-specific secrets made the Milestone 0 health check fail on the laptop.

**What would change it.** A later version that adds the server PC or Discord
re-adds an interface adapter and, if needed, model placement. Core APIs stay
text-in / event-out so those are additions, not rewrites.

## D-0010 - Owner identity and secrets in V1

**Decision.** In V1 the owner is whoever operates the laptop. Every local
interface (microphone, terminal, future hotkey) is treated as owner-operated;
speaker identification is explicitly out of scope (V1 plan §22). The `Actor`
model keeps three kinds - `owner`, `local-machine`, `internal` - and the
emergency-stop rule from D-0005: anyone may trip, only `owner` or
`local-machine` may clear. The LLM is an `internal` actor: it can trip a stop
but never clear one, and its claims about who is speaking are never an input
to authorization (Master Spec §37).

`HANNI_OWNER_DISCORD_USER_ID`, `HANNI_DISCORD_BOT_TOKEN` and `HANNI_NODE_SECRET`
are removed, so V1 requires no secrets and runs without a `.env` file. The
environment-only secrets machinery (`hanni.config.secrets`, rejection of
secret-like keys in YAML, log redaction of loaded values) is kept with an
empty registry so any future, owner-approved integration is handled the same
way.

**Why.** A Discord user ID was the root of authorization only because Discord
was the interface. Removing the interface removes the identity; it does not
weaken the boundary, which lives in code, not in the model.

## D-0011 - Milestone 1 Supervisor/runtime baseline

**Decision.** The first local Supervisor is the official `Qwen/Qwen3-8B-GGUF`
`Q4_K_M` quantization served by llama.cpp on `127.0.0.1:8080`. The API alias is
`supervisor`; H.A.N.N.I. talks to llama.cpp through its local OpenAI-compatible
`/v1/chat/completions` streaming endpoint and checks `/v1/health`. Initial
context is 8,192 tokens, all practical layers are requested on GPU (`-ngl 99`),
and Qwen3 thinking is disabled for the default interactive path. Model identity,
generation parameters, endpoint, and launch metadata stay in `models.yaml`.

**Why.** The laptop's RTX 5060 Laptop GPU has 8 GB VRAM. The official Q4_K_M
GGUF is about 5 GB, which is a sensible first fit while preserving room for
runtime/KV-cache overhead. An 8K context is intentionally conservative; measure
real VRAM use and latency before increasing it. H.A.N.N.I. is voice-first, so
low first-token latency matters more than enabling extended reasoning on every
utterance. Later agent milestones may enable thinking selectively or route hard
work to a specialist.

**Runtime boundary.** llama.cpp is a separate local process. H.A.N.N.I. Core
depends on a small streaming model-client interface, not on llama.cpp internals.
This keeps future runtimes replaceable. Model endpoints are schema-enforced to
loopback hosts in V1 so a configuration typo cannot silently turn the local-first
assistant into a cloud client.

**What would change it.** Real benchmarks on the owner's laptop showing a better
quantization/context tradeoff, or a materially better local model, may change the
configured model without changing H.A.N.N.I. Core.

## D-0012 - Milestone 1 resource monitoring

**Decision.** Use `psutil` for CPU/RAM telemetry and the installed NVIDIA
`nvidia-smi` executable for GPU utilization, temperature, and VRAM. Missing GPU
telemetry is reported but does not crash H.A.N.N.I.

**Why.** This provides useful resource visibility without adding a CUDA Python
binding or coupling the core to NVIDIA libraries. More sophisticated scheduling
belongs to later delegation milestones.

## D-0013 - Milestone 2 local speech baseline

**Decision.** Milestone 2 uses `sounddevice` for local PCM16 microphone capture,
Silero VAD for speech segmentation, and `faster-whisper` for local STT. The
capture format is 16 kHz mono with 512-sample (~32 ms) blocks. The first STT
baseline is `small.en` on **CPU int8**, beam size 1. Silero runs in ONNX mode on
CPU. All settings are configuration under `hanni.yaml:speech`.

Raw microphone chunks and ordinary transcript records live only in in-memory
rolling buffers. Their constructors independently enforce the Master Spec's
120-second ceiling even if configuration validation were bypassed. No raw audio
or transcript text is written to normal logs or event payloads by the speech
pipeline.

**Why.** The laptop has only ~8 GB VRAM and the Qwen3-8B Supervisor already
uses most of the useful GPU budget. Keeping always-on VAD/STT on CPU prevents
voice capture from fighting the Supervisor for VRAM and makes it possible to
run both at once. The i7-14650HX is sufficient for an initial faster-whisper
CPU baseline; real latency measurements may justify another model/compute
placement later.

**Scope boundary.** Milestone 2 transcribes detected utterances but does not
classify whether they are addressed to H.A.N.N.I. Wake-name/follow-up relevance
belongs to Milestone 3, and TTS belongs to Milestone 4.

**What would change it.** Real laptop benchmarks showing poor transcription
latency/quality may change the configured Whisper model, compute type, or
placement without changing the microphone/VAD/STT interfaces.

## D-0014 - Milestone 3 deterministic relevance and engagement

**Decision.** Always-listening relevance is a cheap deterministic boundary in
front of the Supervisor. Exact configured wake-name tokens engage H.A.N.N.I. for
20 seconds; every relevant conversational turn extends that window. The initial
aliases are `hanni`, `ani`, `hani`, `hanny`, and `hannie`. `ani` is included
because the owner's real `faster-whisper small.en` hardware tests repeatedly
transcribed spoken "Hanni" as "Ani". Matching remains token-bounded rather than
fuzzy, so words such as "animal" do not wake the assistant. Clear configured
phrases such as "never mind" disengage immediately.

When idle, ordinary background transcripts are discarded at the relevance
boundary and are **not** sent to the Supervisor. Relevant utterances produce an
`OWNER_COMMAND` event that references only the ephemeral `transcript_id`; the
raw transcript text is not copied into event/log payloads. The live `hanni
attend` path streams a text response through the existing M1 Supervisor. TTS
remains Milestone 4.

**Why.** Running the 8B Supervisor on every nearby sentence would waste latency,
power, and VRAM and would make an always-listening assistant intrusive. Exact
aliases plus a short engagement window are transparent, testable, and cheap.
The behavior can later gain a small local ambiguity classifier without changing
the relevance boundary.

**What would change it.** Real usage may justify tuning the wake aliases or
engagement duration, or adding a small local classifier for ambiguous turns.
Those remain configuration/implementation changes rather than an architecture
change.

## D-0015 - M3.1 persistent activation, filler suppression, and voice-first response style

**Decision.** Owner hardware testing changed the Milestone 3 interaction model.
The microphone/STT loop remains continuously active while H.A.N.N.I. is running,
but the Supervisor remains in standby until an exact wake alias is heard. Once
activated, H.A.N.N.I. now stays active until an explicit configured disengage
phrase is spoken; the default 20-second automatic timeout is disabled by setting
`engagement_seconds: 0`. Standby only gates Supervisor responses and does not stop
local microphone capture. Timed engagement remains supported as an optional
configuration mode for future experiments.

The `honey` alias is removed because real testing showed it wakes H.A.N.N.I. on
ordinary human conversation. Exact aliases remain deliberately conservative,
including `ani` because the owner's local Whisper baseline repeatedly transcribed
spoken "Hanni" that way.

Pure filler utterances such as `um`, `umm`, `uhh`, `hmm`, and related configured
hesitations are discarded before the Supervisor even while H.A.N.N.I. is active.
Leading filler tokens are stripped from otherwise meaningful commands rather
than discarding the whole utterance.

The Supervisor system prompt is voice-first: ordinary responses should normally
be one to three short sentences, use no Markdown or emoji, avoid repetitive
customer-service phrases, and avoid ending every turn with a question. A small
stream-safe response sanitation layer removes common Markdown/emoji artifacts so
the same output path is ready for Milestone 4 TTS.

**Why.** Real conversation contains pauses and filler sounds, and a short timeout
forced the owner to repeat the wake name during natural conversations. Persistent
activation with explicit standby is closer to the intended Jarvis-like behavior,
while filler suppression prevents accidental model turns and wasted inference.
The response-style change prevents screen-oriented chatbot formatting from being
read aloud once TTS is introduced.

**What would change it.** Real hardware use may tune exact wake aliases,
disengage phrases, or filler vocabulary. A future local wake-word detector or
speaker-aware relevance model may replace some deterministic STT matching without
changing the activate/standby state contract.

## D-0016 - M3.2 conservative `honey` STT wake fallback

**Decision.** Real microphone testing showed `faster-whisper small.en` can
consistently transcribe the spoken name "Hanni" as "Honey". The configured
`honey` fallback is therefore accepted only when it begins the utterance (for
example, `Honey, how are you?` or `Honey.`). Incidental uses later in ordinary
speech do not wake H.A.N.N.I. Other wake aliases remain token-bounded.

**Why.** Rejecting `honey` made the owner's actual wake phrase unreliable, while
accepting it globally recreated false wakes in ordinary conversation. Positional
matching is a deterministic compromise until a dedicated local wake-word model
is introduced.

**What would change it.** A later dedicated wake-word detector or improved STT
biasing may allow `honey` to be removed without reducing wake reliability.

## D-0017 - Milestone 4 temporary local voice uses Windows SAPI

**Decision.** Milestone 4 uses the Windows built-in `System.Speech` / SAPI
synthesizer as H.A.N.N.I.'s temporary voice backend. Python sends sanitized text
as JSON over stdin to a local Windows PowerShell process; model/user content is
never interpolated into a PowerShell command string. The configured voice,
rate, volume, and chunk size are external configuration. The backend is exposed
through a small replaceable TTS interface.

The live `hanni attend` path speaks each completed sanitized Supervisor reply.
Microphone processing intentionally pauses while the current M4 speech call is
playing so H.A.N.N.I. does not transcribe her own speakers. Cancellable speech
and listening during playback belong to Milestone 5 barge-in.

**Why.** Windows SAPI is fully local, already present on the target Windows
laptop, adds no cloud dependency, and avoids delaying the voice pipeline on the
separate signature-voice project. It provides a reliable integration baseline
while keeping the voice engine replaceable.

**What would change it.** The separate H.A.N.N.I. voice project will eventually
replace this temporary backend with a more natural local TTS engine. The core
and `attend` path should not need architectural changes when that happens.

## D-0018 - Milestone 5 cancellable TTS and deterministic barge-in

**Decision.** Milestone 5 replaces the M4 blocking speech boundary with a
background microphone/STT transcript pump and cancellable Windows SAPI playback.
The microphone remains active while H.A.N.N.I. speaks. Configured interrupt
phrases such as `stop`, `wait`, and `hold on` terminate only the active
TTS process without asking the Supervisor model whether playback should stop.
A substantive owner utterance heard during playback also cancels TTS and is
routed through the existing relevance boundary as the next conversational turn.
Filler-only utterances do not interrupt.

Because laptop speaker output may be captured by the microphone, M5 adds a
local deterministic echo-suppression layer that compares live transcripts with
the response currently being spoken. Multi-word/high-overlap matches are
ignored as probable speaker echo; explicit interrupt phrases take priority.
Thresholds and phrases remain configuration rather than hard-coded behavior.

**Why.** Natural voice interaction requires the owner to be able to correct or
stop H.A.N.N.I. without waiting for a long answer to finish. Keeping this path
local and deterministic minimizes interruption latency and prevents an LLM
round trip from becoming a safety/control dependency. Text-level echo
suppression is a practical V1 defense while using the temporary speaker-based
Windows SAPI backend.

**What would change it.** A later neural/full-duplex voice stack or acoustic echo
cancellation may replace the transcript-level heuristic. The interaction
contract remains: owner speech can interrupt immediately, filler does not, and
H.A.N.N.I.'s own output should not cause repeated self-interruption.

## D-0019 - M6 wake aliases match anywhere and tools use a validated one-step boundary

**Decision.** At the owner's request, every configured wake alias now uses
case-insensitive token-bounded matching anywhere in the transcribed utterance.
This includes the practical Whisper fallback `honey`. The previous M3.2 rule
that restricted `honey` to the beginning of an utterance is retired. The wake
name is removed from the command text before routing, so utterances such as
`Can you open VS Code, Hanni?` become `Can you open VS Code`.

Milestone 6 introduces the first real computer-action boundary: a central tool
registry with argument validation, permission/risk levels, deterministic
emergency-stop gating, JSONL audit records, and explicit confirmation for Level
3/dynamically dangerous actions. A small deterministic one-step voice router
handles high-value actions such as opening apps and reading system/process state.
Unmatched speech still goes to the normal Supervisor conversation path.
General LLM-selected multi-step planning is deliberately deferred to M8.

**Why.** Wake-name placement should feel natural in spoken conversation rather
than force a rigid command grammar. Separately, computer control needs a tested
permission/tool boundary before allowing a model to plan arbitrary sequences of
actions. A transparent one-step router proves the boundary with low ambiguity
while making M6 useful immediately.

**What would change it.** Real-world false wakes may justify a dedicated local
wake-word model or per-alias confidence rules. M8 will replace/augment the
one-step intent router with model-driven structured planning, but all execution
must continue through the same registry, permission, stop, and audit boundary.

## D-0020 - M7 active-window sampling, privacy-first capture, and on-demand local vision

**Decision.** Milestone 7 samples the local foreground Windows surface at about
1 Hz while H.A.N.N.I. is running. The cheap path reads foreground-window
metadata, checks configured process/title/browser-URL privacy exclusions, then
captures the active-window pixels and computes a small visual fingerprint. Only
meaningfully changed frames (plus explicit user-requested fresh frames) enter an
in-memory buffer, and every raw frame is capped by the existing 120-second
screen-retention limit. Screenshots are not written to disk by the normal M7
pipeline.

Windows UI Automation/accessibility inspection is attempted before expensive
visual inference. Password-like controls are omitted from structured UI text.
The separate local multimodal model is invoked only when the owner explicitly
asks about the screen or visual interpretation is otherwise required; it is not
called by the ~1 Hz sampler.

The initial configured vision model is `ggml-org/Qwen2.5-VL-3B-Instruct-GGUF:Q4_K_M`
served by llama.cpp on `127.0.0.1:8081`. It starts with zero GPU layers so it can
coexist with the always-loaded Qwen Supervisor on the target laptop's 8 GB GPU.
This is a conservative baseline, not a permanent performance choice.

**Why.** Continuous VLM inference would waste compute/VRAM and contradict the
privacy-first design. Active-window capture plus UI Automation gives useful
context cheaply, reduces accidental background-screen exposure, and still
allows a real local VLM to answer visual questions when structured Windows
metadata is insufficient.

**What would change it.** Hardware benchmarking may justify partial GPU offload,
a different local VLM, or a more capable accessibility backend. M8 may consume
M7 observations inside a multi-step agent loop, but it must preserve the same
privacy gate and ephemeral-frame contract.

## D-0021 - M8 uses one-action structured replanning through the existing M6 boundary

**Decision.** Milestone 8 starts with one local Supervisor planner, not a worker
pool. For an explicit multi-step local-computer goal, the planner returns one
strict JSON next action at a time: a registered tool call, a request for owner
input, or completion. Tool calls carry an `observe`, `act`, or `verify` phase.
After every result H.A.N.N.I. replans from bounded structured observations.
Successful `act` steps create an outstanding verification requirement; the loop
will not accept completion until a successful `verify` step occurs.

All computer actions continue through the Milestone 6 `ToolRegistry`. The model
cannot grant itself permissions, invent executable tools, bypass argument
validation, suppress the emergency stop, or bypass Level-3/dynamic confirmation.
M7 privacy-gated active-window/accessibility context may be supplied as evidence
but does not authorize actions. Task state/checkpoints are in-memory for M8;
durable task persistence remains later work.

M8.0 keeps the deterministic one-step router as the fast path for common
commands and activates the agent loop only for explicit multi-step local tasks.
This prevents normal conversation and simple actions from paying agent-loop
latency or gaining unnecessary autonomy.

**Why.** The validated M6 boundary and grounded M7 perception are now mature
enough to support autonomy, but unrestricted free-form shell generation would
undo the safety work already completed. One-action replanning makes every
transition observable and auditable, naturally incorporates tool failures, and
allows deterministic verification and step limits.

**What would change it.** Later M8 refinements may make the live task runner
fully asynchronous/interruptible and add richer UI action primitives. M10 may
introduce specialist workers, but workers must still use the same validated
execution boundary and may not expand permissions.

## D-0022 - M9.1 uses capability discovery plus a mutable task plan

**Decision.** M9.1 adds a structured capability-discovery and task-planning
layer above the existing M8.0 one-action executor. The Supervisor is given
capability descriptors derived from registered H.A.N.N.I. tools rather than raw
`.py`, `.ps1`, `.cmd`, shell script contents, or arbitrary executable files. A
capability descriptor identifies what the runtime can do, its typed inputs and
outputs, risk/confirmation metadata, side-effect class, and retrieval tags.
Implementation details remain behind the validated execution boundary.

For a multi-step owner goal, H.A.N.N.I. first retrieves a bounded subset of
relevant registered capabilities and asks the Supervisor for a structured,
bounded TODO/dependency plan. The plan records intended steps, purpose,
dependencies where known, expected evidence, and status. It is advisory and
mutable rather than an executable batch. The runtime continues to execute only
one registered capability at a time. After each real observation, the planner
updates task state and may revise, insert, skip, or replace future steps before
selecting the next action. Material changes still require verification before
completion.

The full ToolRegistry remains authoritative. Capability retrieval cannot grant a
missing/disabled capability, model output cannot bypass argument validation or
permissions, and `powershell.run` remains subject to its deterministic risk
escalation. M6 confirmation, audit, emergency-stop, M7 privacy, and prompt-
injection boundaries remain unchanged. The existing deterministic router may
remain the low-latency fast path for obvious one-step requests.

**Why.** A high-level TODO plan gives the model global task coherence, visible
progress, dependencies, and a better way to reason about longer workflows, while
M8.0's one-step observation loop prevents stale plans from being followed
blindly. Structured capability retrieval also scales better than injecting a
huge tool catalog into every prompt and is safer than exposing implementation
scripts directly to the model.

**What would change it.** Later work may add semantic capability indexing,
learned routing, persistent/resumable task graphs, parallel branches, or M10
specialist workers. None of those may bypass the same validated capability and
permission boundary.


## D-0023 - M9.1 runtime-owned plans and target-specific verification

**Decision.** Implement D-0022 by extending AgentPlanner/AgentLoop, using stdlib
validated dataclasses and deterministic lexical capability retrieval. Production
session construction enables the structured M9.1 protocol. A replan replaces
future strategy transactionally while preserving executed history. The runtime
owns step completion and verification obligations independently of model phases
or proposed revisions. Optional argument bindings copy real completed-dependency
outputs using literal substitution, never code evaluation.

Add registered file metadata, exact-PID inspection, and Python project verification
tools where existing tools cannot provide the necessary evidence. Copy outputs
identify the actual destination and source hash; system.stats metadata uses its
actual ram_percent output. Plain Remove-Item now receives the same explicit
confirmation boundary as recursive/force deletion.

**Why.** Generic successful 'verify' labels do not establish that a particular
change succeeded. Evidence must match the target and, for written content, the
actual observed bytes/text. Unsupported generic shell/external effects remain
unverified instead of being certified from a planner assertion. Python tests and
script-output checks use real process exit status through registered tools.

**Boundaries.** No model/hardware profile changes, cloud dependency, worker pool,
or automatic durable-memory injection. Existing registry permissions, stop state,
confirmation and audit remain authoritative. Execution remains synchronous;
in-flight interruption and persistent resumable tasks are not added here.


## D-0024 - Complete M9 memory integration without expanding to M10/M11

**Authorization and scope.** The owner requested "finish all of m9" against the
new uploaded source, which already contains M9.1. This authorizes the remaining
M9 memory extraction, retrieval, project-use and cleanup exit criteria. It
supersedes the earlier M9.0/M9.1 deferral of automatic extraction/retrieval; those
entries remain historical. No model, quantization, GPU, STT/TTS or permission
configuration changes are part of this decision.

**Decision.** Place the owner memory boundary outside the existing session stack,
so only direct owner input reaches deterministic extraction. Enable configurable
conservative English stable-fact extraction and bounded lexical recall by default.
Recalled JSON is historical data, separate from current owner instructions; it
never grants capability or confirmation authority. Keep simple tools on their
existing fast path and feed relevant memory hints into the existing M9.1 planner.
Never store task graphs, tool output or raw transcript buffers in SQLite.

Use SQLite schema 2, migrated in place with existing IDs/timestamps preserved.
Recognized project/preference/device/workflow subjects have fact keys. Explicit
owner correction updates the key in place and removes conflicting duplicates;
automatic extraction cannot silently choose between conflicts or downgrade an
explicit fact. Unsupported or ambiguous facts remain explicit searchable records.

Add `folder.open` to the existing registry because `app.open` also accepts files
and executables. The folder capability validates an existing directory and uses
a fixed Explorer executable with a separate path argument. It reports only a
launch request, not proof of a visible Explorer window. Re-read project state
before launch; bound confirmations and missing-path clarification to 120 seconds.

**Privacy/cleanup.** Full-topic deletion is transactional and never limited by
the UI search cap. SQLite secure_delete, index maintenance, post-delete checks
and WAL truncation verify database cleanup. No extra vector store or durable
recall cache exists. Database changes invalidate session memory-derived history,
path caches and pending tasks before the next owner turn. Ordinary TextSession
history is filtered to the two-minute window on access; recalled facts/responses
are excluded from it. Existing execution audit and OS/storage backups are outside
memory deletion. Read-only recall remains usable in Safe Mode; writes and tool
actions remain blocked. No automatic memory mutation changes safety policy.

**Limits.** Lexical retrieval and small English extraction templates intentionally
miss unsupported phrasing. No semantic conflict adjudicator, encryption-at-rest
layer, migration backup containing duplicate private facts, specialist workers,
or persistent/resumable task framework is introduced. Existing synchronous
in-flight execution remains M8/M11 hardening debt. Windows Qwen/voice/Explorer
smoke results must be recorded on the owner machine separately from automated
fixture-based tests.


## D-0025 - M9.2 broad capability surface with deterministic intent routing

**Decision.** The registered capability surface is widened from the Milestone 6
core (files, processes, windows, PowerShell, project verification) to cover the
question categories the owner actually asks about on this machine: network and
connectivity, storage and space, installed software, Windows services and
startup items, audio/media/display, Spotify, content search and archives, time
and scheduling, developer workflow, and H.A.N.N.I.'s own runtime state. Each
capability is an ordinary `ToolDefinition` in the same registry, carrying typed
arguments, an output contract, risk/permission levels, a side-effect class, and
retrieval tags.

Retrieval gains two deterministic layers above lexical overlap: phrase hits,
where a multi-word alias appears verbatim in the goal, and curated *intent
routes* that pin a well-known owner phrasing ("what song is this", "what's
eating my disk space", "how long has my computer been on") to the single
capability that answers it. Routing is table-driven, offline, and reproducible;
`scripts/capability_routing_check.py --strict` asserts every documented phrasing
still ranks its intended capability first.

None of this changes authority. An intent route only raises a retrieval score.
Execution still passes argument validation, the permission profile check,
explicit confirmation for Level 3 and dynamically dangerous arguments, the
deterministic emergency stop, and the audit log. `hanni.capabilities` exposes
introspection over descriptors only - never handlers, script bodies, or file
paths - so listing a capability can never widen what H.A.N.N.I. may do (D-0022).

**Why.** With a small catalog the Supervisor could usually guess the right tool,
but the failure mode of a large catalog is different: near-synonyms compete and
the same question resolves differently from one wording to the next. Curated
routes make the common questions deterministic, keep the model's job to
planning rather than tool lookup, and give a regression test a concrete thing to
assert. Generating `docs/HANNI_CAPABILITY_MATRIX.md` from the live registry
prevents documentation drift.

**What would change it.** Semantic or learned retrieval may later replace the
lexical layer, and routes may be data-driven rather than in-source. Neither may
bypass the validated capability and permission boundary, and neither may make
retrieval nondeterministic for the phrasings covered by the routing check.


## D-0026 - M9.2 boundaries: local-only Spotify, read-only Git, gated state changes

**Decision.** Three boundaries constrain the D-0025 expansion.

*Spotify stays local.* Playback state is read from the running desktop client's
own window title, transport control uses the standard Windows media keys, and
navigation uses the locally registered `spotify:` URI handler. The Spotify Web
API and any other cloud music service are out of scope for V1, which keeps
D-0009's local-first rule intact and avoids storing an account credential.
Per-application volume uses the optional `pycaw` package when present and
reports honestly when it is not, rather than guessing a number.

*Git capabilities are read-only.* `git.status`, `git.log`, `git.diff`, and
`git.branches` observe a repository; commit, push, reset, checkout, and stash
are deliberately not registered in V1. Git is called with fixed argument lists
through the executable, never as a shell string, so branch and path text cannot
become commands.

*State changes are gated, bounded, and reversible where possible.* Volume, mute,
brightness, clipboard writes, archive creation/extraction, and formatting are
Level 2. Windows service control and temporary-file cleanup are Level 3 and
therefore always require explicit owner confirmation; service control refuses a
protected-service list outright, and cleanup is confined to known temporary
directories, filtered by file age, and defaults to a dry run that reports what
it *would* remove. Archive extraction rejects any member whose resolved path
escapes the destination folder. Capabilities that shell out do so through fixed
templates with single-quoted arguments (`hanni.tools.winshell.quote`); free-form
owner commands remain the sole responsibility of `powershell.run` and its
existing deterministic risk escalation.

**Why.** The expansion is only safe if the widened surface does not widen
authority. Read-only-by-default with a small, explicit set of confirmation-gated
writes keeps the M6 boundary meaningful, and refusing to invent a cloud
dependency or a destructive git operation keeps V1's scope honest.

**What would change it.** An owner-approved decision could add authenticated
Spotify control, write-side git operations behind Level 3 confirmation, or
elevated service management. Each would need its own decision entry, its own
confirmation policy, and coverage in the routing and safety checks.


## D-0027 - Merge capability expansion with completed M9 memory

The owner supplied an M9.2 capability bundle and requested its integration into
the completed M9 repository. Preserve D-0024 memory completion; renumber incoming
D-0024/D-0025 to D-0025/D-0026. Retain folder.open, all memory/session changes,
model/GPU/speech settings, and the same ToolRegistry. The combined registry has
92 capabilities in 28 categories. Original matrix/manifest attachments are kept
under docs/upstream_m92; regenerate the current inventory from registered tools.

Correct concrete integration defects before enabling the expanded surface:
Windows PowerShell 5.1 ping syntax, real MiB telemetry fields/model IDs, exact
mute refusal without readback, clipboard audit omission, service readback result,
read-only Git helper suppression, isolated Python module imports, archive bounds
and overwrite confirmation, typographic-quote argument encoding, and Spotify
window-targeted transport instead of global player keys. Delayed notifications
must re-enter the registry rather than run an independent shell job; timers are
bounded and ephemeral, reject one-shot CLI use and preserve stop/permission gates.

The hardware smoke workflow must share the normal stop-state location and use
unique scratch outputs. It must not reset Safe Mode, delete earlier smoke folders,
read/overwrite clipboard contents, or claim to restore an unmeasured audio state.
Natural-language intent routes remain advisory retrieval, not permission grants
or a new argument-extraction/execution framework. Existing M9.1 verification debt
for unsupported material effects remains enforced. Live Windows/Qwen acceptance
is separate from the full automated regression result in M92_MERGE_REPORT.md.


## D-0028 - M9.3 second capability wave: computation, insight, posture, notes

**Decision.** The capability surface is widened a second time, from 92 to 137
registered capabilities, in nine areas the owner asks about but the M9.2 wave
could not answer: deterministic local computation (`calc.*`, `unit.*`, `text.*`,
`random.*`, `id.*`), file-inventory insight (`file.recent`, `file.duplicates`,
`file.composition`, `file.empty_folders`, `file.open`), power and battery
(`power.*`), security posture (`security.*`, `system.event_errors`), hardware
inventory (`device.*`), environment and shell context (`env.*`), window
management (`ui.windows_detailed`, `ui.minimize_all`, `ui.window_state`,
`ui.close_window`), a composite machine snapshot (`system.performance`,
`process.find`), and owner-explicit quick notes (`note.*`).

Two general retrieval improvements land with it. A *filesystem-context* signal
gives file and archive capabilities a bounded boost when the goal names an
actual filename or path, but only where the capability already matches the goal
on two terms - so a generic word such as "folder" cannot outvote measured
telemetry. The synonym bridge and curated intent-route table grow to cover the
new vocabulary. The routing regression check grows from 55 to 98 owner
phrasings, all asserted first-rank.

Arithmetic, unit conversion, and identifier generation are registered
capabilities rather than model output. `calc.evaluate` parses with `ast` and
walks a strict node allow-list; it never calls `eval` and cannot reach a name,
attribute, call, or import.

**Why.** A language model asked to do arithmetic or convert units will
occasionally be confidently wrong, and there is no reason to accept that when
the answer is computable locally and verifiably. The rest of the wave follows
the same principle as D-0025: the owner's real questions - "why is my computer
slow", "is my antivirus on", "what did I work on yesterday", "do I need to
restart" - should resolve to measured local state through one deterministic
capability rather than a guess or a multi-step improvisation.

**What would change it.** More families may be added the same way. Any new
capability must carry retrieval tags, a routing-check case where a common
phrasing must resolve to it, and a risk level that matches what it can change.

## D-0029 - M9.3 boundaries: observe security, do not administer it; notes are not memory

**Decision.** Two boundaries constrain the D-0028 wave.

*Security capabilities observe only.* `security.defender`, `security.firewall`,
`security.bitlocker`, `security.updates`, `security.pending_reboot`, and
`system.event_errors` report posture. H.A.N.N.I. does not disable Defender or
real-time protection, add or remove firewall rules, read or store BitLocker
recovery keys, install or uninstall updates, or reboot the machine. Those are
precisely the security and credential changes the Master Spec names as
dangerous, and they stay outside the registry in V1. Browser history is
deliberately not registered either: it is a detailed record of the owner's
activity that no current capability needs, and the privacy buffer principle in
M7 argues against making it casually queryable.

*Notes are a separate thing from durable memory.* `note.*` writes plain daily
Markdown files under the data directory - readable, greppable, and deletable by
the owner without H.A.N.N.I.'s help. It does not touch the M9.0 SQLite memory
store, does not carry source/confidence metadata, and does not participate in
memory retrieval. Note text passes the same privacy validator durable memory
uses, so passwords, 2FA codes, API keys, and card numbers are refused rather
than written to disk, and `note.append` is Level 2 because it writes.
Environment reads apply the same care in the other direction: `env.list` and
`env.get` redact any value whose variable name is credential-shaped, and pass
everything else through the audit-log redactor.

Window closing uses WM_CLOSE, never a forced process kill, so an application
still gets to prompt about unsaved work; it is Level 2 with argument-dependent
confirmation, refuses a title substring shorter than three characters, refuses
protected system windows, and refuses an ambiguous multi-window match unless the
owner explicitly asks for all of them.

**Why.** The expansion is only worth having if it cannot quietly become a way to
weaken the machine's defences, exfiltrate a credential, or lose the owner's
work. Keeping notes visibly outside durable memory also keeps D-0021's promise
that memory is written only on an explicit remember command.

**What would change it.** Administering security, reading browser history, or
promoting notes into durable memory would each need an owner-approved decision,
its own confirmation policy, and coverage in the routing and safety checks.

## D-0030 - M9.4 makes local/actionable requests workflow-first

**Decision.** M9.4 removes the deterministic one-step router as an *execution
bypass* for ordinary local/actionable requests. After wake/relevance (or a text
turn), H.A.N.N.I. first classifies whether the request needs local capabilities.
If it does, the existing M9.1 capability-aware Supervisor creates a typed TODO
workflow before any capability executes. The workflow may contain one step or
many. Execution remains exactly one registered capability at a time, followed
by a real observation and another planner decision/replan.

The legacy `VoiceToolRouter` and curated capability intent routes remain useful
as deterministic *admission and retrieval hints* so common phrasings such as
"what's using my RAM" resolve reliably. After Qwen authors/selects a TODO step,
a deterministic `WorkflowExecutionRouter` maps that step to exactly one
validated `ToolRequest` before the registry/safety boundary. They no longer execute the tool before
the workflow exists when `agent.workflow_first` is enabled. Such hints never
grant authority and cannot override ToolRegistry validation, permissions,
confirmation, emergency stop, or audit.

Pure conversation/knowledge questions continue through the normal model path;
explicit screen-perception questions remain on M7's privacy/staleness-gated
screen path. This avoids inventing meaningless tool workflows for requests that
do not need local capabilities.

**Why.** The owner wants one consistent decision model: Qwen understands the
goal and maintains the TODO/workflow, while deterministic code executes and
polices the selected capabilities. This gives simple and complex computer tasks
the same observable planning semantics without handing the LLM unrestricted
shell authority.

**What would change it.** A future planner may combine initial planning and the
first ready action to reduce latency, or may add non-tool conversational plan
steps. Either change must preserve the registered execution boundary and prove
that screen/privacy and safety paths cannot be bypassed.

## D-0031 - SUPERSEDED: M9.4 local calendar was owner-local .ics

**Decision.** H.A.N.N.I. gets a real calendar in V1, implemented as a folder of
RFC 5545 `.ics` files under the configured data directory. H.A.N.N.I. writes
exactly one file, `hanni.ics`; every other `.ics` in that folder - a file
exported from another application, or an invitation the owner dropped in - is
read as an additional read-only source and is never modified, including by
`calendar.cancel_event`.

Twelve capabilities are registered: `calendar.today`, `.agenda`, `.next`,
`.search`, `.free_slots`, `.conflicts`, `.reminders` (Level 0 reads),
`.add_event`, `.import_ics`, `.export_ics` (Level 2), `.cancel_event` (Level 3,
always confirmed), and `.sources`. Event text passes the durable-memory privacy
validator, so a credential pasted into an event title is refused rather than
written to disk.

Google Calendar, Microsoft Graph, CalDAV, and any other account-backed calendar
are explicitly **not** implemented. They would require OAuth credentials, token
storage, and outbound network access, contradicting the local-first rule
(D-0009) and the V1 "no secrets" position (D-0010).

The iCalendar subset is implemented in-tree (`hanni.tools.icalendar`) rather than
by adding a dependency, and it covers VEVENT with date or date-time bounds,
summary, location, description, status, and RRULE limited to
FREQ=DAILY/WEEKLY/MONTHLY/YEARLY with INTERVAL, COUNT, UNTIL, and weekly BYDAY.
Anything outside that subset - VTIMEZONE interpretation, BYSETPOS, BYMONTHDAY -
is reported as unsupported rather than approximated, and a DTSTART carrying a
TZID keeps that TZID on the event so the information is never silently lost.

**Why.** A local file store gives the owner a calendar H.A.N.N.I. can actually
read and write today, with no account to connect, no token to protect, and no
network dependency to fail. `.ics` is the interchange format every calendar
application already imports and exports, so the data is not trapped: the owner
can hand `hanni.ics` to any client, or drop an export from their phone into the
folder and have H.A.N.N.I. read it. Approximating an unsupported recurrence rule
would produce a calendar that is quietly wrong about when things happen, which
is worse than saying the rule is unsupported.

**Boundaries.** The natural phrasing owners use - "dentist thursday at 3" - is
resolved by a deterministic parser (`hanni.tools.whenparse`), never by the
Supervisor. That parser refuses what it cannot resolve, including bare numeric
dates such as 9/12 that mean different days in different countries. Adding an
event reports a clash but does not refuse it; the owner decides. Cancellation is
Level 3, matches by uid or an unambiguous title, and refuses an ambiguous
multi-event match unless explicitly told to remove them all.

**What would change it.** An owner-approved decision could add a read-only view
of a locally installed Outlook profile through COM automation, or a genuine
account-backed sync. Either would need its own decision entry, a credential
story for the second, and coverage in the routing and safety checks. Until then,
`calendar.sources` states plainly that no cloud calendar account is connected.


## D-0032 - M10 analysis-only specialists under the existing Supervisor

**Authorization.** The owner requested M10 against the newly attached repository,
which already contains both M9.4 tracks. This supersedes prior milestone-scope
statements deferring workers, without changing M8 execution, M9 memory or M9.4
workflow-first admission. M11 restoration remains unstarted.

**Decision.** Extend AgentTask/AgentPlanner/AgentLoop with an ephemeral dependency
graph and strict `delegate`/`review_workers` actions. Coding, reviewer and research
workers analyze supplied text evidence only. They have no tools, filesystem
adapter, memory store, permission tokens or delegation API. The Supervisor must
review every result before tools, replanning, further delegation or completion.
Failed/blocked/cancelled/expired findings cannot be accepted. Review never becomes
a successful tool result, a confirmed action or verification evidence.

Use existing configured coder/critic/research profiles or the currently selected
Supervisor fallback. Do not download models, modify production defaults, change
quantization/GPU splits or load specialist servers automatically. Roles sharing
a loopback port serialize; independent endpoints may run concurrently. Bound
active workers at four and runtime-derived parent depth at two. Bound graph size,
rounds, inference context/output and elapsed time. CPU/RAM pressure blocks queued
analysis; unavailable telemetry falls back to serial work. No GPU residency or
new asynchronous voice orchestrator is introduced.

Persisted emergency stop is checked before launch and repeatedly while waiting.
Cancelled/timed-out results are discarded; their slots stay occupied until the
underlying calls exit. Workers use one bounded client attempt. Running inference
may outlive cancellation until a stream chunk/socket timeout, but cannot execute
tools or advance the owner task. M8 in-flight tool cancellation debt is unchanged.

Assignments/results/review reasons expire on access after 120 seconds. Worker
content is not copied into durable memory or routine task history/audit. Structural
graph diagnostics remain ephemeral. Owner-requested JSON may expose fresh findings.
Vision remains on M7's existing privacy-gated path, rather than making raw frames
available to workers. Accepted code proposals still require ordinary registered
writes, readback and real project tests. All 149 registered capabilities and
model/speech/memory policies remain unchanged.

**Validation.** Deterministic scheduler/contract tests plus a real filesystem and
pytest integration prove parallel independent analysis, dependencies, failure
handling, review gating, plan revision and verification. Windows live-model smoke
uses a disposable confined project and the normal stop/audit state. Model-quality,
latency and hardware acceptance must be assessed on the owner's machine; reusing
one model for separate roles does not create independent model judgment.


## D-0033 — Model-first admission and owner-authorized Google reads (2026-09-13)

**Authorization.** The owner reverted to hanni_m10_implementation and requested
model processing before deciding whether a TODO is needed, fixes/tests for current
scripts, useful new capabilities, and reading email/calendar for two Google addresses.
This supersedes Google/OAuth deferrals in D-0031 and the V1 plan for these reads only.
It does not restore M11 or autonomous self-development from a different branch.

**Decision.** The default `agent.workflow_first: true` now selects a compact
model decision before normal conversation/tool routing. It answers chat, asks a
required clarification, selects the existing privacy-gated screen path, or requests
a typed TODO through the same AgentPlanner/AgentLoop. Keyword routing supplies
retrieval hints; it cannot execute ahead of the model decision. Emergency stop,
confirmation, task control and explicit memory commands retain their deterministic
handlers. Existing waiting-task clarification continues through the task planner.
A 120-second, size-bounded owner/conversation cache resolves homework follow-ups.
Malformed decisions fail closed rather than dropping into executable legacy routing.

Use llama.cpp JSON response_format and disable thinking for structured decision/plan
requests only; production model/GPU/speech settings are unchanged. Initial planning
gets a separate short schema prompt. No relaxed parsing of prose or action batches.

Add local persistent todo.add/list/get/complete/due with explicit owner input,
privacy checks, SQLite transactions and duplicate identity. Extend calendar with
UID readback and verification obligations, atomic file replacement, exact duplicate
suppression, and deterministic spoken time fixes. Calendar files remain single-writer
local ICS; no claim of multi-process serialization or timezone-complete ICS support.

Google API capabilities are optional reads. Two account slots use separate tokens
in Windows Credential Manager, not repo files. Explicit owner-run desktop OAuth
verifies the actual Gmail profile address against the expected address before save.
Scopes are exactly Gmail read, calendar events read, calendar list read. No Google
send/create/update/delete endpoint is exposed. Account/calendar labels and partial
errors travel with results. APIs have fixed hosts, redirect rejection, timeouts,
response/query limits and bounded pagination. Token refresh persists to the vault;
login is never initiated by an agent tool. Local disconnect removes only local
credentials; Google-side revocation is a separate owner account setting.

No email/event bodies are copied into durable memory or the tool audit. Queries
are masked in audit arguments. External content is untrusted evidence and cannot
grant authority; all tools retain registry checks and deterministic stop.

**Acceptance.** See MODEL_FIRST_COMPLETION_REPORT.md. Windows hardware, actual
Whisper/Qwen response quality, credential-vault operations and live Google OAuth/API
calls require the owner's machine. Offline mocks do not prove that acceptance.


## D-0034: Three-model admission and durable background queue (2026-09-14)

The owner explicitly requested the v2 three-model routing implementation. Qwen3
8B classifies meaningful requests; Phi-4 remains primary; Qwen3 32B is an optional
initial planner. Independent one-tool requests execute through the existing
registry without constructing AgentTask/TodoPlan. Moderate chains use the
executor without TODO; genuinely complex work runs through a durable queue around
the existing task/checkpoint types. Foreground priority and one mutation lane
preserve permission, confirmation and verification gates. Uncertain interrupted
actions are blocked instead of replayed. See THREE_MODEL_ROUTING.md and its report.
This supersedes historical instructions requiring TODO admission for every tool.
No repository was published or pushed.

## D-0035: Cached capability search/get/call (2026-09-15)

Owner authorization: the attached capability-registry architecture request extends
D-0034 and supersedes historical requirements to plan a TODO for every action.
Keep stable existing semantic IDs and Python/PowerShell executors. A per-registry
CapabilityAPI supplies exact/alias lookup, bounded indexed search, cached schemas,
and calls through the existing ToolRegistry. No network MCP server, cloud model,
raw-script discovery or generic nested call proxy is introduced.

Known deterministic commands still pass Qwen3 classification (except established
clock/calendar and safety controls), but skip discovery and Phi-4 speculation.
Missing or low router confidence uses at most five retrieved schemas; selection
outside that set fails closed. Atomic calls do not create tasks/TODOs. Compound
work remains foreground. Workflow metadata forces existing queue admission, and
foreground-only metadata is checked by the authoritative registry in the job lane.
Worker/model output cannot supply execution authority. Existing checkpoint,
verification, stop, memory, voice and confirmation behavior stays authoritative.

Types and optional constraints generate the invocation schema and validation.
Current process I/O sampling adds one read-only capability; it reports measured
counter deltas and unavailable samples, not a historical disk-activity claim.
Discovery scores are ranking values, not authorization or calibrated confidence.
See `docs/CAPABILITY_API.md` for the contract, measurements and acceptance limits.

## D-0036: Measured local model residency (2026-09-15)

The owner authorized memory optimization and a central process residency manager.
Keep Phi-4 and Qwen3 8B pinned; load planner and vision only when requested and
admitted by resource budgets. Only idle owned optional servers can be evicted;
active inference, queued dependencies and pinned models remain protected. Preserve
the existing background queue, checkpoints, safety and model identities.

Use one slot and Q8 KV with installed-build capability detection. Phi-4's total
context falls from the old launcher's 16K to 4K. Keep router at 4K because a real
2,471-token history/catalog input failed at 2K. Preserve configurable larger
contexts. On the current single discrete GPU, both pinned models use the RX 9060
XT by name; RX 6600 XT remains the preferred router assignment if available.
No-host testing increased host RAM and is not enabled by default. The host savings
for pinned models were modest; do not claim otherwise. See MODEL_RESIDENCY.md for
measurements, unavailable scenarios, runtime behavior and validation limits.

## D-0037: V1 stabilization and independent routing evaluation (2026-09-15)

The owner freezes milestone expansion and authorizes exactly three admission
routes: CONVERSATION, SINGLE_ACTION, WORKFLOW. This supersedes D-0034/D-0035's
four-route policy and STANDARD foreground chains. Known deterministic atomic
commands skip Qwen and Phi planning but retain registry safety. Unknown requests
use Qwen3 8B; Phi-4 converses and plans durable queued workflows. Both remain
pinned under D-0036. No automatic 32B planner or production Phi shadow fallback
is part of V1 admission. Existing legacy checkpoint decoding remains compatible.

Reuse the existing JobManager, AgentLoop, TODO graph and checkpoint format. V1
primary planning retains its graph even for one step. Persist step outcome and
timing metadata without copying raw tool observations into durable storage.
Preserve permissions, confirmation, stop, verification, memory and voice gates.

`hanni eval` runs the supplied unchanged balanced 150-case CSV against both live
models independently, blocks capability execution, uses temporary registry state
and saves ignored local results. Expected labels never enter model input. Report
real errors, unsupported capabilities and incomplete scoring ground truth; do not
alter labels or fabricate performance. Confidence-threshold comparisons are
in-sample research only. See V1_STABILIZATION.md for measurements and limitations.
No M12, push or publication is authorized.

## D-0038: Separate intent from capability feasibility (2026-09-15)

The owner requests benchmark-driven V1 refinement. Completed evidence shows
unsupported actions changing route, incorrect deterministic target types and
uncalibrated confidence. Retain the three routes and existing executors. Classify
intent without a tool inventory, then use a second bounded Qwen call only for
SINGLE_ACTION capability/argument selection. The selector cannot overwrite route.
Known atomic fast paths still skip inference. Provide concrete runtime policy
metadata while leaving all authorization in ToolRegistry.

Correct folder versus app and per-process versus system-memory shortcuts; enrich
existing GPU/process retrieval metadata without adding capabilities. Preserve
voice, memory, stop, permissions and workflow recovery. Do not enable a Phi
routing fallback solely on confidence: the completed baseline shows no accuracy
benefit and added cost. Preserve every before/after regression and raw output.

The prior evaluator incorrectly treated relative volume as unsupported despite
the existing audio.set_volume delta contract. Restore that scoring equivalence
and rescore both runs identically; do not edit historical raw files or CSV labels.
Comparison output includes counterfactual fallback latency estimates, clearly
distinguished from live sequential measurements. See V1_REFINEMENT.md. The owner
has not authorized new capabilities, dashboard expansion, M12 or publication.

## D-0039: Rank GPU placement by VRAM at startup (2026-09-17)

The owner requests automatic discovery of the GPUs with the most VRAM and actual
llama.cpp placement on them. Replace fixed supervisor/router GPU name hints with
capacity ranks 0/1. Filter known UMA/software adapters, require valid memory
readings and budget/reserve headroom, and fall back by capacity when necessary.
One-card systems can share their card. Keep CPU-only and manually split optional
profiles unchanged. Serialize GPU starts and pass the resolved command directly
to the process launcher. Require positive GPU layer-offload evidence for automatic
placements; preserve external-process ownership and warn when placement is unknown.
See GPU_SELECTION.md. No routing, voice, permission or model identity change.


## D-0040 - Google Calendar is the sole calendar provider (2026-09-22)

**Decision.** The owner retired the local `.ics` calendar capability family. H.A.N.N.I. now has one calendar source of truth: connected Google Calendar accounts. The `calendar.*` local provider, its RFC 5545 implementation, and its registry entries are removed. Generic natural-language calendar requests route to `google_calendar.*`; deterministic local date/time resolution remains in front of those calls.

**Why.** Maintaining both a local calendar and Google Calendar created duplicate capabilities and ambiguous routing. One provider gives the small resident model a simpler tool surface and prevents events from being split across two stores.

**Boundary.** This does not broaden general write authority. `google_calendar.create` remains the explicitly allowlisted calendar write path and continues through normal validation, permission, emergency-stop, and audit controls.

## 2026-09-22 — Diagnostic sub-intent retrieval scopes

**Decision.** After capability-family classification, computer-diagnostic requests are narrowed again by a diagnostic sub-intent before individual MCP capabilities are ranked. The current sub-intents are `general_slowdown`, `memory_pressure`, `cpu_pressure`, `gpu_vram`, `disk_io`, `network`, `thermal_power`, `windows_errors`, and `model_runtime`.

These sub-intents are retrieval scopes only. They do not diagnose a problem, authorize or execute a tool, or choose the final capability for the model. Their purpose is to prevent unrelated diagnostic tools from competing in the MCP candidate pool while leaving final tool selection and interpretation to the resident model.

### Dynamic diagnostic MCP menus and curated bundles (2026-09-22)

**Decision.** Diagnostic retrieval no longer fills a fixed five-tool menu. Each diagnostic sub-intent owns a curated candidate bundle and a default retrieval budget. Specific culprit questions such as “what process is using the most RAM?” shrink to the smallest useful menu (`process.top_memory`, `system.stats`), while broad questions such as “why is my PC slow?” expose a six-tool cross-resource bundle (`system.performance`, `system.stats`, `process.top_cpu`, `process.top_memory`, `process.top_disk_io`, `gpu.top_processes`). The configured MCP tool count is a hard ceiling (8), not a quota. Bundles affect retrieval only; the resident model still decides which exposed tools to call and no capability is executed during retrieval.

### Negative routing signals and LLM-final tool choice (2026-09-22)

**Decision.** Capability retrieval now applies narrow negative routing signals before individual MCP tools are ranked. Plain system-RAM language strongly promotes `process.top_memory` and suppresses GPU-memory tools unless the owner explicitly refers to VRAM/GPU/graphics memory. Recency phrases such as “right now” do not surface `time.*` unless the request is actually about the clock/date. “Windows” in a performance complaint is treated as the operating system and does not surface `ui.*` unless window/focus language is explicit.

These signals are retrieval corrections only. They do not infer a diagnosis, execute a capability, or replace the resident model’s decision-making.

**Tool-choice boundary.** Deterministic parsing may still resolve facts that should not be guessed, such as an exact date for “tomorrow,” and may constrain tool arguments through fixed schema values. It no longer executes allowlisted tools on the model’s behalf. After retrieval, the resident Qwen model receives the bounded MCP menu and must emit the actual tool call. This applies to read tools and to explicitly allowlisted actions such as Google Calendar creation; execution still passes through `ToolRegistry` validation, permissions, emergency-stop, and audit controls.

## D-0041 - Freeze the deterministic router for the model bake-off (2026-09-24)

The 1,087-case routing regression suite scores 99.66 average and 99.82% strict.
Treat the router as frozen during Qwen and K2 measurement. A new locked
personal-language holdout measures generalization, including cases where the
router gives the model the wrong menu. Report those as routing failures rather
than adding phrase-specific aliases or changing the benchmark after inference.
The owner timezone remains the deliberate `America/Chicago` setting in
`config/hanni.yaml`; it matches the owner's current location and date behavior.

## D-0042 - Defer Tool Intelligence V1 freeze; standardize catalog metadata (2026-09-24)

**Decision.** Do not freeze Tool Intelligence V1 or start a V1.1 capability
batch. Qwen stays the resident production model. Qwen reached 82% development
and 50% locked-holdout task success; 21/50 holdout requests lacked a sufficient
MCP menu. Keep the router freeze policy and the locked corpus intact. Add
advisory family/risk/state/source/permission metadata to all existing
capabilities without changing ranking, IDs, tool schemas, or authorization.
The model-facing MCP host never exposes the broad legacy `powershell.run` tool,
including when action exposure is enabled; manual CLI use retains registry
gates. See [Phases 11–15 checkpoint](PHASE11_TO_15_CHECKPOINT.md).

**Why.** The roadmap's quality gate is not met, so a freeze or new capability
batch would imply confidence the live evidence does not support. Metadata and
the broad-tool boundary can be improved independently without teaching the
router the locked holdout or changing the production model.

## D-0043 - Secret-aware MCP results and post-freeze regression intake (2026-09-24)

**Decision.** Keep OAuth credentials in the existing Windows credential
provider. Deny model-facing file-content reads of known credential paths,
exclude those paths from content search, and redact model-facing tool results.
Preserve manual local file operations and the frozen routing menus. Pin the
150-capability registry baseline and require new capabilities to have at least
two routing probes and two mocked LLM scenarios. Prepare an empty, manually
reviewed real-world failure corpus, but do not collect or promote interactions
before Tool Intelligence V1 freezes. Exclude that corpus from source exports
and source distributions. Preserve the configured Qwen production model and
reuse the same benchmark through a separate K2 profile.

**Why.** File-content tools otherwise provide a path for credential-shaped
files to reach the resident model. Evaluation coverage must grow alongside
capabilities, while the current quality gate and absence of reviewed real
failures preclude a V1.1 expansion or a populated real-world corpus. See the
[Phases 16–20 checkpoint](PHASE16_TO_20_CHECKPOINT.md).

## D-0044 - Scoped Hermes task coordination and shared MCP ownership (2026-10-12)

The owner requested automatic task delegation to the existing Karina Hermes
installation. Implement an explicit opt-in task bridge using the installed agent
loop and supported bootstrap, without another messaging gateway or Windows
executor. Keep local conversation, audio controls and emergency stop in HANNI.
Windows operations retain the original registry, permission profile, audit,
definition validation and per-action mutation confirmation. Remote model claims
are separate from actual receipts; general goals require evidence review.

A canonical catalog can reconcile separately managed MCP registrations in both
applications. Registration is not connection or tool execution permission. New
native Hermes entries start with an empty executable-tool whitelist. Existing
entries and unrelated configuration retain their ownership. Private loopback
forwards preserve host-key verification and the original MCP network policy.
Configuration activation stays pending when an idle graceful lifecycle or active
registration has not been verified. This changes the integration policy for
explicitly managed entries, not the original Hub's unconditional startup behavior.

The [implementation checkpoint](HERMES_INTEGRATION.md) distinguishes local tests,
live bridge/MCP/registry receipts, retained failures and untested voice/ingress
acceptance. This decision does not promote an unattended task family, alter model
defaults, or certify the unresolved Honcho recall integration.
# Hermes connection-only preference (2026-10-12)

The owner's latest request supersedes shared HANNI MCP use for this deployment: keep Hermes as the MCP consumer, expose a simple Hermes connection/task-review page, and automatically own SSH forwards when the HANNI backend opens. Private `connection_only` configuration prevents catalog import and external registry attachment while preserving HANNI's local controller, task approvals and existing stored server entries. The optional standalone PowerShell script uses the same bounded tunnel implementation. See [connection setup and rollback](HERMES_CONNECTION.md).
