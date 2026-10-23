# Routing hardening milestone

HANNI still has 150 capabilities and uses Qwen3.5-4B. No capability implementation,
calendar provider, production model, or remote integration was added.

Natural language is normalized for ordinary shorthand, then separated into request
clauses. Specific operation/object intents constrain the candidate family; resource
questions retain diagnostic sub-intents and curated evidence menus. Unknown requests
use the existing metadata retriever only above an evidence threshold. A weak lexical
match does not force a tool. The resulting decision records confidence (`high` or
`low`, not a calibrated probability), status, menu families, sub-intents and blocked
capability IDs. `clarification` means the conversational model must interpret or ask
about the request; it does not mean deterministic code writes a response.

Each clause gets a candidate menu. The host unions these in round-robin order so a
large diagnostic cannot starve a calendar or process lookup. Menus have a hard ceiling
of eight; single-purpose lookups often have one or two tools. Resource lists such as
CPU and RAM remain together. Quoted strings are protected from conjunction splitting.
A blocked action in a compound request blocks the compound menu and reports the
blocked capability; the session returns a fixed refusal without silently doing
half the task or asking the model for a workaround.

The existing negative signals still separate system RAM from VRAM, incidental “right
now” from clock requests, and Windows performance from window UI state. Specific
process lookups, installed software, event logs, PATH, files and model health now have
operation-specific retrieval vocabulary. This avoids filling menus with irrelevant
capabilities sharing words like “show”, “running” or “what”. The rules match vocabulary
and operations, not complete benchmark utterances. Evaluation data is never imported
by the production router.

MCP publishes descriptions and argument schemas, and passes only a selected model
call to the existing ToolRegistry validation/permission/confirmation/stop/audit gates.
The router does not execute tools or diagnose the machine. Qwen decides whether to
call a tool, supplies unfixed arguments, reads results, chooses subsequent calls from
the menu and produces the final answer. A nonempty menu does not force a call.

Google Calendar is the only calendar provider. Owner-local date resolution uses the
IANA `user.timezone` in `config/hanni.yaml` before
the model receives tools, with exact values fixed in schema constants and enforced at
call time. Supported reads include today/tomorrow/tmr/yesterday, weekdays, next weekday,
this weekend, next week, ISO dates and calendar follow-ups. Bare weekdays mean the next
occurrence; `next Friday` follows the existing parser convention of the following
occurrence after that. `this weekend` on Sunday includes the Saturday just passed.
An availability request “after 6” retrieves the whole local day; Qwen interprets event
times from that evidence, and must clarify ambiguous AM/PM if needed. Invalid or
ambiguous numeric dates return clarification instead of guessed tool arguments.

The original app-launch and Spotify implementations were present but unexposed.
`config/hanni.yaml` now explicitly allows app.open, Spotify launch/focus/search/URI and
playback controls, and generic media transport. Sensitive writes, shell commands,
process termination, service control, volume changes and unlisted actions remain
blocked. Other low-risk actions (such as browser URLs, DNS/ping and notifications)
remain intentionally unexposed under this milestone's policy; coverage tests verify
their correct blocked identity. All existing permission gates still apply. Spotify's
play/pause description now says that it toggles state, and its menu includes status
so the model can observe before toggling. A search does not claim to start playback.

The deterministic evaluator clones the live registry into a metadata-only registry.
Every handler, execution entry point and dynamic confirmation callback is replaced by
a hard failure. It cannot call Google, launch applications, inspect the machine through
capability handlers, or mutate user files. Only its own report files are written.
Coverage counts direct required/primary or explicit blocked-target probes; incidental
acceptable/forbidden mentions do not count. New registry entries without probes cause
CLI failure and automated-test failure. Unreachable/unverified entries also fail the
CLI. The LLM benchmark retains unknown token usage as unknown, rather than inventing it.

The routing corpus has 750 preserved original prompts, 300 registry probes, and 37
additional date/composition/diagnostic/clarification regressions. Its numeric weights
and strict precision threshold remain unchanged. New assertions strengthen strict
scoring for family presence, sub-intent, classification and blocked identity. Family
accuracy here means the declared families represented in the retrieved menu; it is
not a separately trained classifier accuracy. All nine diagnostic sub-intents have
explicit probes. See [routing baseline](../evals/routing/BASELINE.md) for exact metrics
and annotation corrections. The old corpus contains repetitive wording; no old cases
were removed to improve results, and final development scores should not be read as
held-out generalization estimates.

Run from the repository root:

```powershell
.venv\Scripts\python.exe -m hanni.evals.routing --json evals/routing/after.json
.venv\Scripts\python.exe -m hanni.evals.llm_tools --json data/qwen-4b-tool-eval-final.json
.venv\Scripts\python.exe -m pytest
```

The routing CLI exits 2 for missing/unverified coverage, 1 below the strict target
(85% by default), and 0 otherwise. `--cases`, `--config`, `--coverage`, and
`--min-pass-rate` are configurable. After deliberately editing authored probe data,
rebuild with `scripts/expand_routing_corpus.py` followed by
`scripts/add_routing_regressions.py`. Never regenerate expectations from selected tools.

LLM Tool Eval V1 runs the configured local model against 150 synthetic scenarios
covering diagnostics, direct system questions, Calendar, applications/Spotify,
files, HANNI state, mixed requests, conversation and safety. The harness uses the
production routing/schema/client/policy boundaries but has no real tool transport.
Model calls receive fixture results only, within bounded rounds/call counts. Errors,
nonexistent or unexposed tools, unexpected arguments, incorrect fixed dates,
repeated/unnecessary calls, stopping, latency and server token usage are recorded.
Routing pass, selection pass and synthetic execution failure remain separate fields.

Final-answer grading uses explicit claim patterns, evidence-source requirements and
checks for unsupported diagnoses/numbers. This is an intentionally limited heuristic,
not proof of reasoning quality: negation scope, paraphrases, implied claims and derived
numbers can require human review. Full transcripts are saved. The healthy-machine
case requires acknowledging no visible bottleneck; it does not reward inventing a
problem. Correct-sounding unsupported answers fail evidence checks. Unit tests use
scripted clients to prove scoring and isolation; they are not Qwen performance data.

For model comparison, use a separate single-model `--config-dir` profile and the
same 150 cases, menu, prompt, timezone, and evaluator. The production model stays
Qwen3.5-4B. `hanni eval compare` rejects reports with mismatched protocol hashes.
The historical Qwen 51.33% and 82.00% runs are preserved as sanitized summaries
in `evals/llm_tools/`; the current full run is stored locally under ignored `data/`.
See [LLM Tool Eval](LLM_TOOL_EVAL.md) for the live baseline and limitations.

Remaining limitations include complex quoted compound requests, multiple differently
parameterized requests for the same capability, broad health menu precision, some
storage slang, and context-dependent Gmail IDs. The router can expose a menu for an
existing capability while execution still fails because a dependency, Google OAuth,
installed app or Windows facility is unavailable. Those runtime issues are distinct
from routing and were not repaired by weakening the benchmark or adding capabilities.
