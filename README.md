# H.A.N.N.I.

**Experimental alpha.** Use the current [publication checklist](docs/PUBLIC_RELEASE_PREPARATION.md) and `PUBLIC_READINESS.json` in the prepared release copy. Automated software checks do not certify live voice latency, model planning quality, or external integrations. Historical evaluation reports retain their original scope and failures.

H.A.N.N.I. (Highly Adaptive Neural Network Intelligence) is a **local Windows 11 assistant** with bounded, permission-aware workflows for persistent goals.

## Quick start on Windows

1. Install **Python 3.12**. The setup command can install llama.cpp with WinGet when available.
2. Download or clone this repository, open its folder, and run `SETUP_HANNI.cmd`. It creates `.venv` and installs the normal app, speech, and Google dependencies. The first setup needs internet access; model weights are not included in GitHub.
3. Open **HANNI OS** from the Desktop or Start menu, or run `START_HANNI.cmd`. HANNI opens in its own Windows window and starts its agent in the background. `START_HANNI_OS.cmd` opens the same app. `START_BRAIN.cmd` remains the explicit terminal/browser launcher; the older voice/controller path is available through `scripts/start_dashboard.ps1`.

Closing the app window keeps HANNI in the system tray. Windows notifications are enabled for new installations; existing preferences are retained. Open **Notifications** for unread task results, approval requests, failures, and reminders. Right-click the tray icon to toggle **Desktop notifications**, send a test notification, reopen the app, or **Exit desktop**. Exiting stops services the app started; an already-running session remains independent. See [Windows application setup](docs/WINDOWS_APPLICATION.md).

In **Settings → Permissions → Tool access**, choose **Read only**, **Ask before writes**, or **Full access (read & write)**, then select **Save tool access**. **Existing permissions** preserves the original task and schedule approvals until you choose a mode. Read only blocks agent writes, terminal commands, code execution, and schedule changes; task progress and read-only delegation remain available. Ask before writes overrides earlier automatic write grants and uses Task review. Full access authorizes local agent actions and enabled MCP tools without individual reviews. Disabled tools, approved MCP definitions, file boundaries, cancellation, and connection permissions still apply. Remote Windows controllers keep their own execution checks. The saved mode applies to chat, scheduled runs and child agents before their next tool starts; it does not undo running actions. Direct application controls and explicit slash commands remain owner actions. MCP read-only enforcement relies on the tool classification you approved.

To use HANNI **inside Microsoft Teams on this PC**, run `SETUP_TEAMS.cmd`, upload `dist/teams/HANNI-Teams.zip` as a custom Teams app, then run `START_TEAMS.cmd` while HANNI is running. Enter the launcher's one-use pairing code in the HANNI tab. Setup trusts a localhost development certificate for your Windows account. Your tenant must allow custom app uploads. See [Microsoft Teams setup](docs/MICROSOFT_TEAMS.md).

## Portable native brain (any machine, no install ritual)

The native agent stack — agent loop, durable memory, skills, local + web tools, approval receipts — runs on **Linux or Windows** with Python **3.12+** for the full Hanni OS interface:

```
git clone <this repo> && cd HANNI
python scripts/get_models.py            # tier models + llama.cpp binaries
./start_brain.sh                        # Linux   (Windows: START_BRAIN.cmd)
```

First boot benchmarks candidates from largest to smallest (7B → 3.7B → 2B), selecting the first that meets its speed floor or the fastest usable fallback. You can choose a tier explicitly. The browser opens only after the model, bridge, and Conversation inbox are ready.

| Service | Default address | Purpose |
|---|---|---|
| Hanni OS | **http://localhost:8311** | Internal app interface; browser access remains available for development |
| Agent bridge | `http://127.0.0.1:8312` | Tasks, approvals, receipts, and model status |
| Model API | `http://127.0.0.1:8411/v1` | Internal llama.cpp endpoint; not the Hanni OS interface |

Memories, tasks, cron jobs, generated model configurations, and launcher metadata live under `state/`. Shipped skills live under `soul/skills`. A supervised launch cleans up owned services when Stop is selected, startup fails, or the launcher exits. A model connected with `--reuse-model` or `--brain-url` stays owned by its original launcher.

To reconnect to an already running local model, run:

```powershell
.\.venv\Scripts\python.exe scripts\firstboot.py --serve --wait --ui --reuse-model --port 8311
```

For another OpenAI-compatible server, use `--brain-url http://host:port/v1` and, if it advertises multiple models, `--brain-model EXACT_ID`. The ID must match `/v1/models`. API credentials belong in `HANNI_MODEL_API_KEY`. Use `--secure` to require per-action approvals; the default keeps the existing automatic local execution mode.

The **Models** page can switch between installed **MiniCPM 2B**, **K2 3.7B**, **K2 7B**, and an OpenAI-compatible API. Enter the API base URL, exact model ID, and optional key; **Test connection** checks model discovery and **Apply model** switches the agent. Keys entered in the UI use the system credential store (Windows Credential Manager on Windows), and are not written into model configuration files. Model changes require finishing or canceling active tasks; a failed load attempts to restore the previous model. The last successful selection is saved for the next launch when no explicit model or tier is supplied.

Context defaults to **64K (65,536 tokens)**. Select up to **256K (262,144 tokens)** in Models, or pass `--context 262144` to the launcher. The installed MiniCPM file declares a **128K** maximum, so larger choices are disabled for that model; the installed K2 models support the full selectable range. Local context is verified against the running server. An API provider controls its own actual context limit.

Local inference detects usable GPUs through the installed llama.cpp backend. It prefers a discrete GPU over integrated graphics and uses automatic VRAM fitting where supported, keeping the selected context size. If the model and cache exceed available VRAM, excess layers use CPU/system RAM. With no supported GPU, inference runs on CPU/system RAM. Both K and V caches use **Q8 (`q8_0`)**, including benchmarks and model switches; a build without these cache options reports an error instead of silently using F16. External API servers control their own hardware and cache settings.

Chat shows a live, expandable **Reasoning & activity** view: model-returned reasoning, applied skills, tool requests and receipts, approval waits, and response writing. Supported models stream reasoning and answer text as they generate it. The view opens while working and folds after completion unless you choose to keep it open; its history is saved with the task. Models that return no separate reasoning show actual activity only. A provider that explicitly rejects streaming falls back to ordinary responses. The displayed duration includes model requests, tools, and approval waits.

Each native response also has an inline **Task review**. Expand it to inspect
tool arguments and execution receipts without leaving the conversation. Pending
approvals open it automatically, with **Approve** and **Deny** for local and MCP
actions. Decisions apply only to the exact request displayed; changed, expired,
or already dispatched requests cannot be approved again. Approval grants
dispatch, while the eventual receipt reports whether execution succeeded.
Failed or uncertain outcomes remain visible, and saved reviews can be reopened
after refreshing. Actions owned by another controller retain their existing
review path through **Open agent tools**.

The bottom chat readout shows the last request's context usage against the model's context limit, the reply's reported input/output token total, and server-measured **decode t/s**. It refreshes every two minutes and when a reply completes. Missing usage or generation timings appear as unavailable; request latency is not presented as decode speed. Hover over a value for exact counts and its measurement scope.

In **MCP**, use **Add server** for a local stdio executable or a Streamable HTTP endpoint, or **Import JSON** for an `mcpServers` configuration. **Save and connect** starts the connection and discovers tools. Choose each tool's permission and select **Enable tool** to make it available to the native chat agent. Reads use the approved definition; other tool effects require an action decision in **Agent tools → Tasks & approvals**. Environment variables and saved credential references keep secrets out of configuration. Local packages must already be installed (`npx --no-install` is supported). Optional startup reconnect pins the exact configuration after a successful connection; **Disconnect** pauses it.

For local Office files, select **MCP → Microsoft Office**, enter a document folder, and select **Connect Office files**. The bundled connector reads documents and provides tools to create/append Word paragraphs, create/write Excel cells, and create/append PowerPoint slides. Only listing and reading are enabled by default; enable individual writing tools in the server’s tool list. Edits require the current file hash returned by reading, and creation refuses to overwrite files. Files must fit within 8 MiB; close a locked document before editing. Complex formatting, macros, and formula recalculation are not supported. This is HANNI’s local file connector, separate from Microsoft 365 cloud accounts and unsaved desktop windows. If dependencies are missing, rerun `SETUP_HANNI.cmd` and restart HANNI.

For Outlook, calendar, Teams, and OneDrive/SharePoint data, choose **Microsoft 365 cloud** in that same setup screen. Follow its Microsoft Work IQ installation and sign-in instructions, then connect the installed executable and review its tools. HANNI never saves your Microsoft password or accepts Microsoft’s terms automatically. Work IQ needs an eligible organization account, administrator consent, and Microsoft’s required billing/licensing setup. Connecting confirms MCP discovery; account data access is checked when a tool is used. See [Office and Microsoft 365 setup](docs/OFFICE_MCP.md).

The active **Skills** collection contains 28 procedures. Everyday workplace skills cover email, meeting notes, task planning, spreadsheet analysis, document summaries, memos and proposals, presentations, status updates, business research, calendar planning, customer responses, and process/onboarding guides. Document-reading skills cover PDFs, HTML, JSON/JSONL/XML/YAML, and Word/PowerPoint/OpenDocument text, alongside spreadsheet and CSV/TSV analysis. They complement the retained research, citations, knowledge management, recurring tasks, and engineering skills. Skills match the task automatically; email, calendar, and file actions still depend on available tools and the user's instructions. A draft is not reported as a sent message, saved event, or finished document file.

Run `.\.venv\Scripts\python.exe scripts\diagnose_brain.py` to inspect the current model identity, bridge, dashboard, and generated configuration without running tools or submitting a task.

Type `/` in chat for command suggestions, or `/help` for all 33 commands and examples. Commands run directly in HANNI, including when the inference model is disconnected. `/history [search]` searches titles and saved message text; `/resume <session>` accepts an exact ID, unique ID prefix, or exact title. `/new` retains personal memory. `/remember <fact>` saves explicit memory; `/forget <memory-id>` verifies deletion against the backend.

For repeating work, ask naturally (for example, **“Update me daily on AI news”**)
or open **Agent tools → Schedule**. Create an hourly, daily, weekly, or custom
interval task, choose its timezone, and pause, resume, or delete it later.
The AI news example fills in a source-backed digest prompt; it does not create
a schedule until you select **Create repeating task**. Natural-language requests
without a time default to **09:00 in HANNI's configured timezone**, and the agent
returns the actual next run and schedule ID after saving.

The deterministic conversation command is:

```text
/schedule daily 09:00 | Search current AI news and summarize five developments with sources
/schedule weekly mon 09:00 | Review the project notes and summarize next steps
/schedule every 2 hours | Check system resources and report problems
/schedule list
/schedule pause <id>
/schedule resume <id>
/schedule delete <id>
```

Commands and agent-created schedules deliver into the originating conversation;
the Schedule form creates a separate conversation with an **Open conversation**
link. Scheduled results and pending approvals appear there with Task review.
New schedules automatically authorize only built-in read tools; writes, terminal
execution, and other actions retain normal approval requirements. Existing job
policies are preserved. HANNI must be running: missed runs catch up once after
launch, without replaying every missed slot or overlapping the same job. Daily
and weekly schedules follow local wall time across daylight-saving changes;
skipped times move to the first valid minute, and repeated times fire once.
Pausing/deleting a schedule retains already-submitted runs and saved reports;
use `/jobs` to inspect or cancel an existing run. Existing schedules migrate
without resetting their enabled state or next run.

In native chat, use the **paperclip** or drag files into the conversation to attach
PDF, Word (`.docx`), PowerPoint (`.pptx`), Excel (`.xlsx`, `.xlsm`, `.xls`),
OpenDocument (`.odt`, `.ods`), HTML (`.html`, `.htm`), text, CSV/TSV,
JSON/JSONL, XML, YAML, or source-code files. Attach up to **five
files, 8 MiB each**, then send your question; sending files without a message asks
Hanni to review them. Uploads can be removed before sending, and unsent files
return after refreshing. Sent files stay with their conversation and can be
downloaded again. `/retry` retains the files while keeping tools disabled;
`/undo` removes the exchange and its files. Clearing chat history removes stored
uploads, including unsent files.

Document text goes to the selected inference provider as source material.
The reader keeps up to 200,000 extracted characters per file and uses bounded
excerpts when needed to fit model context. Images and scanned PDFs require OCR
before upload; password-protected PDFs must be unlocked. PDF reading is limited
to 200 pages. Original files are kept in the chat database, with a 100 MiB total
upload limit. Excel extraction preserves sheet names, cell references, formulas,
and last-saved cached values when available; XLS exposes saved values only.
Cached values can be stale. XLSX/XLSM/XLS reading stops at 10,000 rows and 256
columns per sheet and reports truncation. ODS repeat counts remain explicit.
Office/OpenDocument archives are limited to 24 MiB expanded and 8 MiB per part.
HTML is read as static text without loading resources or running scripts.
Word/slide reading extracts text, not rendered layout, images, or speaker notes.
Legacy DOC/PPT, RTF, and XLSB require conversion to a supported format first.
Spreadsheet formulas, macros and uploaded code are not executed.

For documents already in the agent workspace, the `local_read_document` tool
uses the same readers and supports `offset`/`limit` pagination. Its result states
whether extraction was truncated and returns `next_offset` for later text.
Workspace access follows the existing tool approval policy. Uploaded excerpts
are supplied directly to the model; attachment IDs are not workspace paths.

`/undo` removes the last conversation exchange and retains task receipts; it does not reverse tool actions. `/retry` regenerates the last answer with previous observations and tools disabled, preventing repeated effects. `/stop` cancels queued and active chat responses, stops speech, cancels compression, and reports remaining background work. Scheduled job settings are unchanged. `/compress [focus]` saves a summary for future model context while retaining the full browsable history. `/context` reports the native loop's actual compression threshold and distinguishes estimated context from provider-reported usage.

`/model` lists installed local models and saved API connections; `/model <name>` switches through the supervising launcher. API connections applied in Models are saved as reusable profiles. `/reasoning low|medium|high` requires advertised model support and applies to subsequent responses from that model. `/status`, `/tools`, and `/connections` show actual availability; an unconfigured service is identified as such.

`/voice on|off` controls an already running voice assistant, `/wake on|off` controls wake activation, and `/mute on|off` controls spoken output independently of microphone capture. The native chat launcher does not start a voice capture session; `/voice on` reports this clearly when no voice controller is attached. Use the existing Windows voice/controller launcher when voice conversation is needed.

Workplace commands reuse the same registry permissions, connected accounts, task stores, and MCP approvals:

| Command | Example / behavior |
| --- | --- |
| `/today` | Calendar, open tasks, today’s reminders, overdue and next-seven-day deadlines in your configured time zone. |
| `/calendar day` / `/calendar week` | Read connected Google Calendar events; clearly labels cached or unavailable data. |
| `/calendar create` | `Team meeting \| 2027-01-04T09:00-06:00 \| 2027-01-04T09:30-06:00 [\| account \| calendar-id]` |
| `/calendar edit` | `event-id \| New title \| - \| - [\| account \| calendar-id]`; `-` preserves the title or both times. Writes are read back from Calendar. |
| `/remind` | `in 10 minutes Check report` or `tomorrow at 9am \| Check report`; returns an exact scheduled time and ID. |
| `/tasks` | `list [all/open/completed]`, `add Draft report [\| due tomorrow at 5pm]`, or `done <exact task-id>`. |
| `/search` | A public web query; synthesizes search excerpts and returns the actual source URLs. |
| `/screen [question]` | One explicit desktop capture, local Windows OCR, then text-model analysis. Images, layout, and visual details are not assessed. Screen exclusion rules apply; frames never touch disk. |
| `/clipboard [instruction]` | Read current clipboard text, then summarize/explain/rewrite with tools disabled. Does not overwrite the clipboard. |
| `/hermes <task>` | Requires configured, enabled Hermes. Sends bounded text from the current conversation, returns a job ID, and grants no blanket tool approval. |
| `/jobs` | Lists saved jobs. `status <id>` shows state and exact pending requests; `result <id>` retrieves reports and receipts; `cancel <id>` requests cancellation without reversing effects. |
| `/approve <request-id>` / `/deny <request-id> [reason]` | First inspect `/jobs status <job-id>`. Decisions are bound to the exact displayed request; changed, hidden, expired, or settled actions cannot be approved through the command. |
| `/reload-mcp` | Reconnect enabled configurations, report each result, and refresh tools. Disabled servers stay disabled; changed tools still require approval. |

Reminders are durable one-time records in `state/reminders.sqlite3`. The running dashboard delivers them to its notification center and attempts a Windows alert. If HANNI is stopped, due reminders are delivered on the next launch. Notification preferences and Safe Mode remain effective. Screen/clipboard source buffers are not added to conversation history, personal memory, or command records; the requested answer is retained as the command result. Connected inference providers receive the text needed for that requested analysis.


To connect Google Calendar, obtain a Google OAuth **Desktop app** client in Google Cloud, then run this from the repository folder in PowerShell:

```powershell
.\.venv\Scripts\hanni.exe google login
```

HANNI finds a downloaded client JSON in Downloads or asks for its path, opens browser sign-in, and saves the authorization locally. Check or remove the connection with `.\.venv\Scripts\hanni.exe google status` and `.\.venv\Scripts\hanni.exe google logout`. Google login is optional for non-Google features. See [Google setup](docs/GOOGLE.md) for the one-time Google Cloud steps.

Optional **Laya memory intelligence** is now bundled as an opt-in, read-only shadow observer. The normal `START_HANNI.cmd` launch can also start or connect to Laya automatically, including over SSH to a private GPU machine. Laya does not influence memory writes, replies or permissions. It is **off by default** and training weights/private datasets are not shipped. See [Laya shadow setup](docs/LAYA_SHADOW.md).

**V3.5 personal memory** adds a Memory Explorer with source/history inspection, owner-reviewed corrections and suggestions, bounded contextual retrieval, and explicit links to existing projects and verified workflow receipts. New contextual integration and LAYA advisory/reranking remain disabled by default. A working installed LAYA model has not been independently verified, so its production quality gate remains closed. See [V3.5 configuration](docs/HANNI_V3_5_SETUP.md), [verified results and limitations](docs/HANNI_V3_5_REPORT.md), and [milestone checkpoints](docs/HANNI_V3_5_CHECKPOINTS.md).

This repository does **not** include model weights, Google credentials, account tokens, logs, chat history, or local evaluation transcripts. Keep those files local; see [security and sharing](SECURITY.md).

Models now opens the integrated four-model inference control center, with lifecycle controls, streaming chats, comparison, saved histories and live metrics. The same controls appear in HANNI and Wonyoung cluster details. See [control-center integration and deployment](docs/CONTROL_CENTER_INTEGRATION.md).

## Current architecture

This checkpoint intentionally has one resident language model and one model-facing capability path:

```text
Owner (text / voice / dashboard)
            |
            v
family / sub-intent retrieval + resolved local dates
            |
            v
1-8 relevant MCP schemas -> Qwen3.5-4B chooses tool calls
            |
            v
validated HANNI capability registry
            |
            v
live local computer state / approved MCP servers
```

The model is conversational and interpretive. It is not the source of truth for live machine state. CPU, RAM, GPU, process, storage, network, application, and service information must come from validated local tools.

**Settings → Integrations → MCP Hub** adds owner-configured stdio and Streamable HTTP servers to this same execution path. Connect approval, hash-bound tool approval and execution confirmation remain separate; imported tools start disabled. See [MCP Hub setup and policy](docs/MCP_HUB.md) for safe connection settings, import/export, persistence and the observe-first model limits. [Implementation checkpoints](docs/MCP_HUB_CHECKPOINTS.md) record actual verification progress.

## Deliberate constraints at this checkpoint

[Reliability & Intelligence V2](docs/RELIABILITY_V2.md) documents metadata-based retrieval, conservative action verification, bounded recovery and execution inspection in Activity. [Milestone checkpoints](docs/RELIABILITY_V2_CHECKPOINTS.md) distinguish measured baseline, development checks and independent final acceptance.

The [final independent comparison](docs/RELIABILITY_V2_REPORT.md) is **PARTIAL**: controlled reliability and Activity checks pass, while untouched language retrieval remains below target. It includes measured counts, confidence intervals, failure analysis and reproducible evaluation inputs.

Persistent local goals now use the original controller through **Workflows**: bounded dependency plans, exact approvals, durable invocation checkpoints, conservative crash recovery and required outcome criteria. [Workflow setup and architecture](docs/WORKFLOWS_V3.md) explains modes, limits, private retention and the independent backend/window lifecycle. [V3 checkpoints](docs/WORKFLOWS_V3_CHECKPOINTS.md) preserve completed checks and failed evaluation cycles.

[V4 adaptive routing](docs/HANNI_V4_ADAPTIVE_MODELS.md) uses measured endpoint capabilities and existing sharing permissions. [V4.1 collaboration](docs/HANNI_V4_1_COLLABORATION.md) adds selective independent analysis and review to the same Workflows interface; the original controller still verifies outcomes and controls tools.

[V4.2 performance optimization](docs/HANNI_V4_2_PERFORMANCE.md) adds bounded recent placement, compatible-worker queue ordering, invalidated profile/memory caches, and endpoint telemetry in Model routing. The [independent comparison](docs/HANNI_V4_2_BENCHMARK_COMPARISON.md) records measured application gains, unchanged model settings, verified 8K/16K context, and the limits of current remote hardware access.

[V4.3 Model Intelligence Lab](docs/HANNI_V4_3_MODEL_LAB.md) brings registered model inventory, benchmark controls, per-case evidence, historical runs, export, comparison and routing insights into the existing desktop. Implemented development suites retain explicit evaluation scopes and original scoring/admission; [checkpoints](docs/HANNI_V4_3_CHECKPOINTS.md) and the [independent review](docs/v43-reviews/INDEPENDENT_REVIEW.md) record actual execution and visual evidence.

[V4.4 full-system validation](docs/HANNI_V4_4_FINAL_VALIDATION.md) evaluates routing, collaboration, distributed inference, workflows, memory, MCP and the native desktop. [Durable checkpoints](docs/HANNI_V4_4_CHECKPOINTS.md) distinguish controlled regression coverage from actual model results and unavailable deployment evidence.

The [V3 implementation and independent assessment](docs/WORKFLOWS_V3_REPORT.md) is **PARTIAL**. Execution, recovery, security and the native interface pass their documented engineering checks. Natural-language goal planning remains experimental: the current configured planning path completed **0/15 fresh supported multi-step goals**. The requested 95% autonomous completion target is not met; scripted execution tests do not measure model planning quality.

To run that backend without voice capture or interactive input:

```powershell
.\.venv\Scripts\python.exe -m hanni.dashboard.launcher --workflow-only --no-browser
```

Keep that backend terminal open. Submit `/goal <objective>` from the existing keyboard session. The primary interface now contains Assistant, Mission and Hermes; the former Workspace navigation is removed. Workflow execution still obeys original permissions and Stop; an uncertain write never becomes an automatic retry. Unattended intent execution remains disabled until its task-family acceptance gate passes.

- Exactly **one configured LLM** (`supervisor`).
- The default model is `Qwen3.5-4B-Q4_K_M.gguf` through llama.cpp.
- The resident model is intended to stay loaded with a modest 16K context.
- GPU AUTO routing prefers the **smallest discrete 8 GB-class GPU** that can safely fit the model; dashboard override remains available.
- The model is exposed to at most a small relevant set of tools per turn.
- The MCP layer is **observe-first**: read tools and explicitly allowlisted owner actions are exposed. The allowlist includes Calendar creation, existing application launch and media/Spotify controls.
- Existing validation, permission, safety, and audit checks remain below MCP.
- Voice, memory, telemetry, and the dashboard remain part of the foundation.
- Legacy autonomous agent/planner/delegation and screen-vision runtime were removed from the active package. The current routing and mocked-tool evaluations are maintained separately under `src/hanni/evals/`.

## Important files

- `config/models.yaml` — the single resident model and GPU/runtime budget.
- `config/hanni.yaml` — MCP, voice, memory, logging, and recovery configuration.
- `src/hanni/mcp/host.py` — natural-language routing, bounded capability discovery, exact argument locking, and action allowlisting.
- `src/hanni/mcp/session.py` — model -> tool -> model loop.
- `src/hanni/mcp/server.py` — MCP v2 server facade for the same validated local capabilities.
- `src/hanni/tools/` — existing local computer capability implementations.
- `src/hanni/models/runtime.py` — llama.cpp launch and GPU routing.
- `src/hanni/dashboard/` — local dashboard and GPU selection UI.
- `docs/ASSISTANT_RESET_CHECKPOINT.md` — exact state of this handoff and next steps.

## Natural-language routing

The routing-hardening milestone covers all **150 registered capabilities** with
**1,087 cases**, including blocked actions. Qwen remains the final tool selector.
See [architecture and benchmark commands](docs/ROUTING_HARDENING.md),
[before/after scores](evals/routing/BASELINE.md), and
[capability coverage](evals/routing/capability-coverage.json).
The [150-case LLM Tool Eval](docs/LLM_TOOL_EVAL.md) is separate from routing scores.
The current Qwen3.5-4B live development run passed **139/150 (92.67%)** of
tasks with the configured Personality V2 prompt. Diagnostics passed **37/45
(82.22%)**; tuned Language V3 routing passed **150/150** on its development
phrases. The once-run locked Holdout V2 passed **45/72 (62.50%)**, with 24
routing failures, so Tool Intelligence V1 is **not frozen**. See the
[freeze blockers](docs/TOOL_INTELLIGENCE_V1_BLOCKERS.md) and
[final handoff](FINAL_GENERALIZATION_HANDOFF.md).

Language Generalization V2 adds a separate 200-case owner-style development
corpus and a 50-dialogue follow-up corpus. These are inspectable development
tests, not blind evidence. Run `hanni eval routing-language-v2` and
`hanni eval routing-multiturn-v1`; results and freeze status are in
[the V2 report](docs/LANGUAGE_GENERALIZATION_V2_REPORT.md). HANNI's
warm/casual style is configured under `personality` in `config/hanni.yaml`;
[Personality V2](docs/PERSONALITY_V2.md) documents its grounding and the
50-pair synthetic A/B evaluation. Run `hanni eval llm-coverage --strict` to
audit two mocked schema/menu probes for each model-facing capability.

HANNI uses Google Calendar as its only calendar provider and accepts ordinary owner language rather than tool/API syntax. High-confidence time and Calendar intents are resolved deterministically before the 4B model sees a tool. For example, `what do I have tomorrow?` resolves tomorrow in `config/hanni.yaml`'s `user.timezone` and exposes exactly that Google Calendar window; `schedule dinner Friday at 8pm for 2 hours` resolves an exact start/end in the same IANA timezone and routes to the single allowlisted `google_calendar.create` action. The resolved arguments are locked server-side so the model cannot silently change the date. Set `user.timezone` to your local IANA timezone if you move. Generic computer/file/process questions continue through the bounded capability retriever.

Google login defaults to Calendar read-only access. Add Calendar writes with `hanni google login --replace --scopes calendar.write`. Gmail, Drive, Docs and Google Tasks have separate opt-in grants. See [Google capabilities and setup](docs/GOOGLE.md) for scopes, named accounts, follow-ups and write gates.

## Development setup

The native **HANNI OS** workspace includes Assistant, Workspace and Mission
Control, with sixteen screens and the globally accessible HANNI Mini. It reuses
the existing local controller, chat inbox, permissions and voice loop. Launch
`START_HANNI_OS.cmd` or `START_HANNI.cmd` for the desktop application.
See [desktop setup](docs/HANNI_DESKTOP.md),
[workspace integration](docs/HANNI_WORKSPACE_INTEGRATION.md), and
[Phase 1 + Phase 2 verification](docs/HANNI_PHASE12_FINAL_VERIFICATION.md)
for measured results, actual screenshots and remaining limitations.

Python 3.12+ is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Google support is included in a normal HANNI install. With the virtual environment activated, use:

```powershell
hanni google login
hanni google status
hanni google logout
```

If this HANNI installation has no Google OAuth Desktop client yet, `login` looks
for one in Downloads. If none is found, it opens Google Cloud and asks for the
downloaded client JSON path. It imports the file
into the ignored `config/google-oauth-client.json` path, then continues directly
to browser sign-in. A client created for HANNI must exist before Google can
authorize Gmail and Calendar; the user does not need to copy files manually.

Named accounts such as `personal`, `school` and `work` use `--account`. HANNI stores
authorization in Windows Credential Manager. Enable other read services with
`hanni google login --replace --scopes calendar.read gmail.read drive.read docs.read tasks.read`.
Use `hanni google use school --service calendar` to choose a service default;
unqualified requests search one account. `google status --verify` checks authorized APIs.

To benchmark the configured resident model against synthetic MCP results:

```powershell
hanni eval llm-tools
hanni eval llm-tools --audit
hanni eval compare data\qwen-4b-tool-eval-final.json data\k2-tool-eval.json
```

See [LLM Tool Eval V1](docs/LLM_TOOL_EVAL.md) for filters, scoring, and safety guarantees.

For local speech dependencies:

```powershell
python -m pip install -e ".[dev,speech]"
```

The project depends on the stable MCP Python SDK v2 line.

## Validate this checkpoint

```powershell
python -m pytest
hanni health
hanni model-info
```

A live-model test additionally requires a current llama.cpp build and the configured Qwen GGUF (or Hugging Face loading through llama.cpp).

## Not implemented yet

Do not treat this checkpoint as the final HANNI architecture. The next phase should expand **computer awareness and MCP coverage**, then improve dashboard/state presentation and only later add remote-server observers such as LocalForge/Kubernetes. Additional write/action tools should remain separately and explicitly allowlisted; do not expose the full mutation catalog to the resident model.

## Natural-language routing evaluation

HANNI includes a 1,087-case routing benchmark that does **not** execute real capabilities.
It checks whether normal owner language retrieves the right bounded MCP tool set, resolves
calendar dates/times correctly, and blocks unsupported write actions.

```powershell
python -m hanni.evals.routing
```

See `evals/routing/README.md` for the corpus, scoring, and untuned baseline.

The [Routing Generalization V4 handoff](ROUTING_GENERALIZATION_V4_HANDOFF.md)
records the 300-case development run, the untouched V4B first-run gate, and
the current non-freeze decision. Inspect a request's deterministic menu and
prototype scores with:

```powershell
hanni eval routing-debug "Friday agenda, remaining disk space"
```

## Native brain (no Hermes required)

HANNI can now run its own resident agent loop instead of delegating to an
installed Hermes. The native loop (`src/hanni/native/`) speaks the
OpenAI-compatible `/chat/completions` protocol directly to the resident model
endpoint from `config/models.yaml` (Strata, llama-server, or any compatible
server), while keeping the existing security architecture identical: bounded
tool menus, JSON-Schema validation, durable action requests, and
receipt-producing execution authority (`hanni.hermes.state`).

Select the engine when starting the bridge service:

```sh
# Linux
./run_hanni_native.sh
```

```bat
:: Windows
START_HANNI_NATIVE.cmd
```

or directly:

```
python -m hanni.hermes.service --root <root> --hermes-config config/hanni.yaml \
    --token-file <token> --brain native
```

Environment:

- `HANNI_MODEL_CONFIG` — path to `models.yaml` (defaults to `config/models.yaml`)
- `HANNI_MODEL_ID` — pick a model entry by id (defaults to the `supervisor` role)
- `HANNI_MODEL_API_KEY` — bearer token for the endpoint (default `local`)

Native-loop options can be set per model entry in `models.yaml`:
`native_max_tokens`, `native_temperature`, `native_reasoning_budget`
(the last maps to llama-server's `--reasoning-budget`, which keeps small
models from ruminating without converging).

## Cross-platform support

See [native agent runtime](docs/native-agent-runtime.md) for action recovery,
context management, separate memory stores, learned skills, scoped background
agents, script orchestration, limits, and the optional MCP memory provider setup.

The repository targets both Windows and Linux:

- process supervision in `hanni.hermes.service` uses process groups on both
  platforms (`CREATE_NEW_PROCESS_GROUP`/`taskkill` on Windows,
  `start_new_session`/`killpg` on POSIX)
- all path handling is `pathlib`-based
- Linux quick start:

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
sudo apt install libportaudio2   # audio stack (speech features; tests that
                                 # boot the full UI backend need it too)
./run_hanni_native.sh
```

- Windows quick start: `SETUP_HANNI.cmd` then `START_HANNI_NATIVE.cmd`
- run the test suite on either platform with `.venv/bin/python -m pytest tests/`
  (`tests/test_native_loop.py` covers the native loop with a scripted model
  client and needs no network, model, or audio device)

For the offline assistant test layers, coverage, frontend/package checks, and
recorded verification results, see [assistant harness testing](docs/assistant-harness/testing.md).

See [repository maintenance](docs/REPOSITORY_MAINTENANCE.md) for generated files,
retained evaluation evidence, and earlier material available in Git history.
