# H.A.N.N.I. Development Instructions

## Automatic GPU placement (2026-09-17)

The owner requested placement on the highest-VRAM GPUs. Read `docs/GPU_SELECTION.md`
and D-0039. Discover llama.cpp device IDs at startup; retain explicit CPU/manual
profiles and existing ownership rules. Do not restore model-specific GPU names
in the primary/router defaults or reselect a device after resolving a launch command.

## Current benchmark-driven refinement (2026-09-15)

Read `docs/V1_REFINEMENT.md` and D-0038. Intent classification is separate from
capability selection; only SINGLE_ACTION needs the second bounded router call.
Do not let registry availability rewrite intent or interpret confidence as
calibrated permission. No Phi routing fallback is enabled without new evidence.
Retain the fixed evaluation data and compare both sides with identical scoring.

## Current owner-authorized V1 stabilization (2026-09-15)

Milestone expansion is frozen. Read `docs/V1_STABILIZATION.md` and D-0037.
Production admission has exactly CONVERSATION, SINGLE_ACTION and WORKFLOW.
Known deterministic commands skip model routing while retaining all execution
gates. Qwen3 8B routes unknown requests; Phi-4 converses and plans durable
workflows. The old STANDARD foreground chain is superseded by V1 queue admission.
Keep both models pinned under D-0036. The optional 32B planner is not required
for V1. `hanni eval` independently classifies the fixed 150 prompts with both
models and must never execute capabilities. Preserve the official dataset,
honest metrics, safety, voice and privacy; no M12 or publishing is authorized.

## Current owner-authorized residency update (2026-09-15)

The owner requested llama.cpp RAM/VRAM optimization and pinned/on-demand model
management. Read `docs/MODEL_RESIDENCY.md` and D-0036. Preserve model identities,
active inference leases, background job dependencies, safety and voice behavior.
Do not restore duplicated launch flags or automatic optional-model startup.

## Current owner-authorized update (2026-09-15)

The owner requested the internal MCP-style capability search/get/call architecture.
Read `docs/CAPABILITY_API.md` and D-0035. Preserve D-0034's atomic fast paths and
background queue; do not restore historical workflow-always admission. Capability
metadata and discovery are not execution authority. All executors still use the
same registry, permission, confirmation, stop, audit and verification boundaries.

## Current owner-authorized update (2026-09-13)

The owner reverted to this M10 baseline and requested model-first TODO decisions,
script fixes, additional useful capabilities, and two-account Google email/calendar
reading. Read `docs/MODEL_FIRST_GOOGLE.md` and D-0033 before changing this update.
This authorization supersedes older Google/OAuth deferrals below for read-only
integration only. All inference remains local; no email sending or Google writes
are implemented. M11/self-development changes from other exports are not included.


Read before working:

- `docs/HANNI_MASTER_SPEC.md`
- `docs/HANNI_V1_IMPLEMENTATION_PLAN.md`
- `docs/DECISIONS.md`
- `docs/HANNI_CAPABILITY_MATRIX.md` (generated inventory of every registered capability)

The Master Spec is the long-term source of truth. The V1 plan defines the
current single-PC scope. Recorded decisions must not be silently re-litigated.

## Current Architecture

One Windows laptop: local microphone, STT, Supervisor LLM, TTS, screen
awareness, Windows tools, memory, and agent loop. No Discord, no second PC, and
no cross-machine networking in V1 (D-0009).

## Current Milestone

M10 is now owner-authorized and implemented on the attached M9.4 baseline.
Read `docs/HANNI_M10.md` and D-0032 before changing delegation. Workers analyze
only; the Supervisor reviews every result before any subsequent tool action.
Use the same AgentLoop, TODO plan, execution router and ToolRegistry. Enforce
four workers maximum, depth two, bounded task graphs/time/context, persisted
stop checks, and two-minute worker-content expiry. Never execute worker text or
let review clear verification debt. M11 is not started. Live Windows/Qwen/voice
acceptance remains an owner-machine check; automated results are in
`M10_IMPLEMENTATION_REPORT.md`.

### Retained M9 foundation (historical milestone scope)

The retained Milestone 9 foundation is implemented through M9.4 on top of the merged M9.3 capability wave. M9 includes M9.0 SQLite memory, M9.1 capability-aware planning on the M8 executor, bounded relevant recall/project aliases, conservative owner-fact extraction, explicit conflict resolution, verified cleanup (D-0024), the merged M9.2 capability surface and hardening (D-0025/D-0026/D-0027), M9.3's second capability wave (D-0028/D-0029), and the retained workflow-first admission foundation. The legacy owner-local `.ics` calendar from D-0031 is retired; Google Calendar is now the sole calendar provider. Automated regression coverage is provided; live Windows/Qwen/voice and M9.3/M9.4 hardware smoke verification still requires the owner machine. M10 workers and M11 resumable tasks are not authorized by this M9 work. Do not move the roadmap backward to M8 or weaken memory privacy, confirmations, stop state, permissions, or the registered execution boundary.

Milestones 0-6 are complete. Preserve the Milestone 6 baseline:
- configured wake aliases now match as token-bounded words anywhere in the utterance, including the practical `honey` STT fallback
- central tool registry with typed/validated arguments
- permission/risk checks are enforced outside the LLM
- deterministic emergency stop blocks new tool execution
- Level 3 and dynamically dangerous actions require explicit confirmation
- JSONL tool audit log with redaction; file-write content is not copied into audit logs
- read-only system/process tools
- app/URL open and basic Windows window-list/focus tools
- file read/search/write/copy/move plus confirmation-gated single-file delete
- non-elevated PowerShell with deterministic high-risk pattern escalation
- deterministic one-step voice routing for common actions; general multi-step model planning remains M8
- `hanni tools`, `hanni tool-run`, `hanni tool-audit`
- `scripts/test_m6.ps1` real-hardware smoke test
- setup validates the M6 registry and read-only system tool

## Rules

- Work only on the current milestone.
- Do not begin the next milestone without owner approval.
- Inspect existing code before modifying it.
- Test before declaring a milestone complete.
- Do not silently deviate from the Master Spec, V1 plan, or DECISIONS.md.
- Keep H.A.N.N.I. local-first; no cloud AI dependencies without approval.
- Model endpoints are loopback-only in V1.
- Do not implement Discord, a second PC, or cross-machine networking in V1.
- Keep interfaces separate from H.A.N.N.I. Core.
- Keep LLM reasoning separate from tool authorization/execution.
- Never expose secrets in source control.
- Preserve the two-minute privacy-buffer requirement.
- Preserve the deterministic emergency stop.
- Prefer modular, replaceable components and working vertical slices.

## Working in this repository

```text
.\scripts\start_hanni.ps1     create/update venv and run foundation health
.\scripts\start_llama.ps1     run configured local Supervisor
.\scripts\test_m1.ps1         real-hardware Milestone 1 smoke test
.\scripts\setup_speech.ps1     install optional Milestone 2 speech stack
.\scripts\test_m2.ps1          real-hardware Milestone 2 smoke test
.\scripts\test_m3.ps1          real-hardware Milestone 3 relevance test
.\scripts\test_m4.ps1          real-hardware Milestone 4 TTS test
.\scripts\test_m5.ps1          real-hardware Milestone 5 barge-in test
.\scripts\test_m6.ps1          real-hardware Milestone 6 tool test
.\scripts\start_vision.ps1       start M7 local Qwen2.5-VL vision model on 127.0.0.1:8081
.\scripts\test_m7.ps1          real-hardware Milestone 7 screen/vision test
.\scripts\start_qwen35.ps1      optional Qwen3.5 9B multimodal benchmark server
.\scripts\test_qwen35.ps1       optional Qwen3.5 9B text/screen smoke test
python -m pytest              automated suite
.\scripts\test_m92.ps1         real-hardware Milestone 9.2 capability smoke test
.\scripts\test_m93.ps1         real-hardware Milestone 9.3 capability smoke test
.\scripts\test_m94_workflow.ps1 workflow-first/Qwen smoke only
.\scripts\verify_capabilities.ps1       offline routing/safety/doc verification (all waves)
python scripts\capability_routing_check.py --strict   owner-phrasing routing regression check
python scripts\capability_safety_check.py             capability risk/confirmation invariants
python scripts\capability_matrix.py                   regenerate docs\HANNI_CAPABILITY_MATRIX.md
hanni health
hanni resources
hanni model-info
hanni model-health
hanni chat [PROMPT]
hanni mics
hanni speech-info
hanni tts-info
hanni voices
hanni speak TEXT
hanni listen [--once]
hanni relevance-info
hanni barge-info
hanni vision-info
hanni screen-snapshot
hanni screen-describe [--model-id VISION_MODEL] [PROMPT]
hanni tools
hanni capabilities [--json]
hanni capability-search GOAL [--json] [--limit N]
hanni tool-run TOOL --arg KEY=VALUE [--arg KEY=VALUE ...] [--confirm]
# Legacy JSON is still accepted with --args, but --arg is preferred on Windows PowerShell.
hanni tool-audit [--limit N]
hanni attend [--model-id TEXT_MODEL] [--vision-model-id VISION_MODEL] [--once] [--show-ignored] [--no-tts]
hanni text [PROMPT] [--model-id TEXT_MODEL] [--vision-model-id VISION_MODEL] [--tts]   # keyboard-only full stack; alias: hanni type
hanni stop | status | resume
```

At completion of a milestone:
1. Run tests.
2. Verify exit criteria.
3. Explain what was implemented.
4. Give exact owner manual-testing instructions.
5. Stop and wait for approval.


## M6.1 real-hardware refinement

The current M6 tool layer includes real-hardware fixes for Start Menu application discovery, active-window metadata, top-CPU normalization, simple folder/file voice intents, and natural current-date PowerShell routing. Do not regress these while working on later milestones. General multi-step tool planning remains M8.

### M6.3 hardware fixes

M6.3 fixes issues found in live voice testing: benign `Get-Date -Format ...` no longer trips the destructive PowerShell detector; a pending high-risk tool confirmation can be completed with a narrow follow-up such as `yes`, `go ahead`, or `you can do that`; folder-only requests such as `list my folders in my download` route to the file tool; meta-questions such as `How do you open Riot Client?` are no longer executed as commands; and app launching now prefers known executable locations and falls back when a stale Desktop/OneDrive shortcut fails (notably Spotify).


## Milestone 7 screen-awareness rules

M7 is the active milestone. Preserve the M0-M6 voice, barge-in, wake-anywhere,
confirmation, and Windows-tool behavior while adding perception.

- Sample the active screen at approximately 1 Hz, but do not run visual model
  inference continuously.
- Raw screenshots remain in memory only and expire within 120 seconds. Never
  create a continuous screenshot archive or add captured frames to Git/logs.
- Apply `privacy.yaml` screen exclusions before retaining pixels or invoking the
  vision model. Password-manager, authentication/2FA, banking, and private/
  incognito contexts should fail closed where detectable.
- Prefer Windows UI Automation/accessibility metadata before image inference.
  Do not use OCR as the primary screen-understanding mechanism.
- The local multimodal model is configuration-driven (`vision` role) and runs
  on loopback only. The default M7 Qwen2.5-VL 3B server is on port 8081 and is
  invoked only for explicit/necessary visual questions.
- The initial vision server uses CPU-first inference so the 8 GB GPU remains
  available to the Qwen Supervisor. Do not silently increase GPU offload without
  hardware evidence that both models can coexist reliably.
- Screen perception does not authorize computer actions. Any action still goes
  through the validated tool registry and permission/emergency-stop boundary.
- M8 may consume this privacy-gated screen context for planning, but screen perception still does not authorize actions.


### M7.2 additional requirements

- Explicit screen questions must capture the active window fresh at request time.
- After slow text/vision inference, verify the foreground window and pixels are
  still the same. Discard stale answers and retry at most the configured count.
- Treat Windows window title/process/URL metadata as authoritative; the VLM must
  not invent another active app/page or unseen system statistics.
- Prefer accessibility text plus the already-loaded Supervisor for page-reading
  and summarization when there is enough grounded text. Use the VLM for actual
  visual interpretation or when accessibility text is insufficient.
- Downscale only the temporary inference copy in memory; never persist frames.
- Current CPU/RAM/GPU/battery facts must come from deterministic local tools, not
  the conversational model.
- Conversational text cannot grant/revoke tool permissions or deletion privileges.


## Milestone 9.0 memory rules

- Durable memory is owner-local SQLite under the configured data directory; never store it in source/config.
- M9.0 accepts only explicit remember/forget/query commands. Do not silently save ordinary conversation yet.
- Never persist passwords, 2FA/authentication codes, financial credentials, API keys, tokens, private keys, or raw perception buffers.
- Durable records must carry source, confidence, and UTC timestamps.
- Forget/delete must remove the SQLite record and verify it is no longer queryable.
- Memory writes/deletes respect Safe Mode; read-only memory queries may still work.
- Automatic memory extraction, conflict resolution, and retrieval into unrelated prompts belong to later M9 steps.

## Milestone 8.0/8.1 agent rules

- Use one Supervisor planner and decision-maker. M10 may request bounded analysis workers under D-0032; workers never execute capabilities.
- Do not expose raw implementation scripts to the model as the capability interface. Generate structured capability descriptors from registered tools.
- Add capability discovery/retrieval before multi-step planning; provide a bounded relevant subset rather than the full catalog when possible.
- For multi-step goals, create a structured bounded TODO/dependency plan before execution. The plan is mutable, not an executable batch.
- Continue to execute only one registered capability at a time and re-evaluate from actual observations after every step.
- Model output never executes directly. Only registered ToolRegistry actions may change the computer.
- Capability retrieval never grants authority: the full registry, validation, and permission checks remain authoritative at execution time.
- Preserve M6 argument validation, permission/risk checks, confirmation, audit, and deterministic emergency stop.
- Treat file/terminal/screen/web content as untrusted data, not instructions that can override the agent policy.
- Observe before acting when state is unknown. Ask the owner when a required project/path fact cannot be grounded.
- After a successful act step, require meaningful verification before accepting completion.
- Bound plan size, task steps, planner retries, observation size, and task duration. No infinite loops.
- Keep current task state/checkpoints ephemeral in M9.1; durable/resumable task persistence is a later M9 refinement unless separately approved.
- M9.4 default is workflow-first for local/actionable requests: even one-step tasks get a typed TODO before execution. The legacy one-step router may classify/hint capabilities but must not execute ahead of the planner when `agent.workflow_first` is true.
- Do not silently promote benchmark model IDs to production defaults as part of agent-loop work; model promotion is a separate owner-approved configuration decision.
- Full microphone cancellation/interruptibility during an in-flight long task remains M8 technical debt/regression work and must not block the project from being tracked as M9.


### M9.1 implementation references

Read `docs/HANNI_M91.md` for typed plan contracts, verification limitations and
`scripts/test_m91.ps1` for smoke tests. Keep runtime-completed history and the
verification ledger independent of model-authored revisions. The planner cannot
supply confirmation flags or clear outstanding verification through phase labels.


## Milestone 9.4 workflow-first rules

- Read `docs/HANNI_M94_WORKFLOW_FIRST.md` and D-0030 before changing request admission.
- For local/actionable turns, Qwen must create a typed TODO workflow before any capability executes, even if the workflow has one step.
- Deterministic router/intent matches are retrieval hints only under workflow-first mode; they never authorize or pre-execute the action.
- Pure conversation/knowledge and explicit M7 screen-perception requests keep their specialized paths.
- Exactly one registered capability may execute per observation cycle. Reality/tool evidence wins over the original TODO.
- Do not weaken confirmation, permissions, emergency stop, audit, M7 privacy, or M9 memory protections to reduce planner latency.


## Calendar provider rule

- Google Calendar is H.A.N.N.I.'s only calendar provider.
- Do not register or route to the retired local `.ics` `calendar.*` capability family.
- Resolve owner date/time phrasing through `hanni.tools.whenparse`; do not let the model silently guess ambiguous dates.
- Calendar reads route to `google_calendar.*`; clear owner creation requests route to `google_calendar.create` through the existing permission/audit boundary.

## Milestone 9.2 capability rules

M9.2 through M9.4 widen the registered capability surface to 149 capabilities across
39 categories (network, storage, installed software, services, startup, audio,
media, display, Spotify, content search, archives, clipboard, time, scheduling,
notifications, git, Python environment, and self-diagnostics) and adds
deterministic intent routing. Read `docs/HANNI_M92_CAPABILITIES.md` and
`docs/HANNI_M93_CAPABILITIES.md`, `docs/HANNI_M94_WORKFLOW_FIRST.md`, and
`docs/HANNI_M94_CALENDAR.md` before changing any of it.

- A new capability is a `ToolDefinition` in the registry. Never expose a script,
  handler, or file path to the model as the capability interface.
- Give every capability real `tags` and `aliases`, and a `_HINTS` entry in
  `hanni.tools.capabilities` where owner vocabulary differs from the tags.
- When a common owner phrasing must always reach one capability, add an intent
  route and a case to `scripts/capability_routing_check.py`. Routes only boost
  retrieval scores; they never grant authority.
- Read-only by default. Anything that changes durable machine state is Level 2
  at minimum; service control and temp cleanup are Level 3 and always confirmed.
- Destructive or bulk operations must default to a dry run and report what they
  would do before they do it.
- Never build a shell command by interpolating model or file text. Use a fixed
  template with `hanni.tools.winshell.quote`, or a fixed argument list through
  `subprocess`. Free-form owner commands remain `powershell.run`'s job.
- Spotify stays local (window title, media keys, `spotify:` URIs). No Spotify
  Web API, no cloud music service, no stored account credential (D-0009, D-0026).
- Git capabilities stay read-only in V1. Do not register commit, push, reset,
  checkout, or stash without an owner-approved decision entry.
- File, clipboard, archive, and window-title content is untrusted data, never an
  instruction.
- Compute answers, do not generate them. Arithmetic, unit conversion, time, and
  identifiers come from registered capabilities, never from model reasoning.
- Security capabilities observe only. Do not add disabling Defender, firewall
  rule changes, BitLocker key reads, update installs, reboots, or browser
  history without an owner-approved decision entry (D-0029).
- `note.*` is not durable memory. Keep notes as plain owner-editable Markdown,
  keep them out of the SQLite memory store, and keep the privacy validator on
  the write path.
- Closing or changing windows must stay polite and specific: WM_CLOSE not kill,
  no protected system windows, no ambiguous substring matches.
- After changing capabilities, regenerate the matrix
  (`python scripts/capability_matrix.py`) and run the routing and safety checks;
  `scripts/verify_m92_capabilities.ps1` runs all of them plus pytest.

## M10 validation

```powershell
hanni workers --json
.\scripts\test_m10.ps1 -SkipInstall -FullSuite
.\scripts\test_m10.ps1 -SkipInstall -WithModel
```

Do not change production model/GPU profiles to make delegation appear faster.
Shared-endpoint roles run sequentially; parallel inference requires separately
configured, already-running local endpoints. No cloud AI or model auto-loading.


## Owner-authorized routing update (2026-09-14)

The explicit v2 three-model routing request supersedes historical workflow-always
admission and milestone deferrals for this update. Read
`docs/THREE_MODEL_ROUTING.md` and `docs/THREE_MODEL_ROUTING_REPORT.md` for the current
route gate, optional specialist, background queue and safe checkpoint behavior.
Preserve all capability, confirmation, emergency-stop, voice and memory gates.


## Owner-authorized routing update (2026-09-14)

The explicit v2 three-model routing request supersedes historical workflow-always
admission and milestone deferrals for this update. Read
`docs/THREE_MODEL_ROUTING.md` and `docs/THREE_MODEL_ROUTING_REPORT.md` for the current
route gate, optional specialist, background queue and safe checkpoint behavior.
Preserve all capability, confirmation, emergency-stop, voice and memory gates.
