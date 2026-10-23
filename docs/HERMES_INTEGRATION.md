# HANNI–Hermes integration checkpoint

This is an implementation and deployment checkpoint, not full acceptance. The
Karina bridge is installed and healthy. The Windows profile is configured but
automatic delegation remains **disabled**. Reopen HANNI to load the new backend,
then review its scope and enable the mode in Settings → Integrations → MCP Hub.
The configured resident model was unavailable during the natural-language
ingress check. Physical wake, recognition, playback, barge-in and first audible
latency are **NOT TESTED** in this checkpoint.

## Actual paths and services

The inspected Windows project is
`C:\Projects\HANNI_NEGATIVE_SIGNALS_LLM_FINAL_ROUTING`. Its existing launchers
are `START_HANNI.cmd`, `START_HANNI_OS.cmd`, and `scripts/start_dashboard.ps1`;
its portable desktop is `dist/HANNI OS/HANNI OS.exe`. The inspected user Startup,
Desktop and Programs directories contained no matching HANNI shortcuts. No
different installation or startup shortcut was invented.

Karina's existing launcher is `/home/user/.local/bin/hermes`. Its installed
bootstrap supports `--run-module`; it uses the existing managed Python runtime,
not an assumed venv. The adapter uses the installed `AIAgent.run_conversation`
loop with a closed tool dispatcher. ACP session/source interfaces were examined;
their general tool surface was not exposed to Windows. `hermes mcp serve` and
one-shot CLI approval bypasses are not used.

New, separately owned deployment:

- `/home/user/hanni-hermes-bridge`, owner marker `hanni-hermes-v1`.
- User unit `hanni-hermes-bridge.service`, loopback `127.0.0.1:8092`.
- Adapter loader `/home/user/.hermes/hermes-agent/hanni_hermes_adapter.py`.
- Durable SQLite tasks, catalog, approvals and observations under `state/`.
- An existing authenticated provider on Wonyoung is reused. Its model remains
  `qwen3.8-flash-next-iq3_s`, with both observed configured context fields at
  **131000**. Usable context capacity was not measured.

The existing `hermes-gateway.service` was not restarted. Its observed PID remained
1395035 across the deployment checks. No second messaging gateway, model server,
model download, sudo rule or public listener was introduced. Chaewon and Yunjin
are not used.

## Authority and task lifecycle

When enabled, requests to perform work use the task bridge automatically.
Existing ingress classification and a small resident semantic classification
handle task wording and relevant follow-ups. Ordinary conversation stays in the
original session; local voice and emergency controls remain local. Task context
contains the approved execution scope and, only for a classified follow-up,
bounded prior-task context. Prior model statements are explicitly unverified;
conversation context expires after 120 seconds. ChatGPT history, continuous
screens/audio, Honcho recall and broad memory history are not transferred.

Submission returns a durable ID. Requests have idempotency keys bound to the
original HANNI request ID where available. Lost acknowledgments are recovered by
status lookup, not automatic side-effect replay. Calls are short; no MCP request
is held open for a complete task. One worker runs at a time, with 12 planning
iterations, 32 actions, a 900-second run deadline, 300-second action approval
deadlines, 256 retained tasks and 64 retained events per task. Retention exhaustion
blocks new submissions rather than deleting idempotency evidence.

The menu contains at most eight Windows capabilities, twelve remote capabilities,
and one bounded rediscovery operation. Discovery grants no execution authority.
Native shell, code execution, recursive delegation and messaging handlers are
not available through this dispatcher. Unknown/changed definitions, unavailable
providers, invalid arguments and permission failures stay visible as failures.
No paid-provider fallback is enabled.

Windows execution uses the original `ToolRegistry`, current permission profile,
schema validation, definition fingerprint, audit and verification. Original
eligible reads can run with `confirmed=False`, the original background-eligibility
gate, and foreground priority. Mutations and application launch require a visible
owner action approval. The initial file scope is only
`data/hermes/workspace`; the application whitelist is Calculator and Notepad.
Changing these private scopes requires deliberate configuration and reload.
There is no generic Windows shell callback.

Remote capabilities require exact definition/argument approval. An optional
private list of owner-reviewed read definition hashes can authorize narrowly
scoped reads through an audited registry policy; it is empty in this deployment.
Registration or untrusted read-only annotations never populate that list.

Dispatch intent is durable before a possible write. Restarted or uncertain writes
are quarantined. Repeated identical effect proposals reuse existing receipts;
new trusted read calls can obtain fresh observations. Cancellation keeps completed
effects, marks local cancellation durably, propagates remotely and suppresses
completion speech. Emergency-stop listeners do not wait for network calls.
Closing the owning HANNI session requests cancellation and closes its SSH forwards.
Cancellation during a disconnect is a request, not proof of remote termination.

Model reports remain separate from receipts. Windows success presentation checks
HANNI's own local dispatch journal rather than trusting a remote success claim.
The existing `VERIFIED`/independent readback contract supports individual action
claims. General task results remain `review_required`: a fully independent
general-goal verifier has not been established. Do not enable unattended task
families from this checkpoint or treat these trials as the earlier Phase 2/3
acceptance cohorts.

## Shared MCP catalog

The canonical, versioned catalog lives on Karina. The common catalog editor in
HANNI updates both clients through one workflow. It supports managed add/update,
desired enable/disable, tombstone removal, environment credential references,
revision conflicts, retry, schema observations and separate connection approvals.
The implemented shared transport is mapped loopback Streamable HTTP; unrelated
existing stdio Hub entries are retained. Shared stdio/remote-public adapters are
not implemented.

| Server | Hermes endpoint | Windows forwarded endpoint | Observed schemas |
|---|---|---|---:|
| hanni_capabilities | `127.0.0.1:8090/mcp` | `127.0.0.1:18090/mcp` | 6 |
| hanni_speech | `127.0.0.1:8091/mcp` | `127.0.0.1:18091/mcp` | 2 |
| hanni_browser | `127.0.0.1:8931/mcp` | `127.0.0.1:8931/mcp` | 25 |

These counts are live observations, not hardcoded capability contracts. All three
were registered in the real HANNI Hub and connected through key-authenticated SSH.
All imported executable tools remained disabled. Browser originally rejected the
18931 mapping; matching its working port-qualified Host solved it without altering
its container allowlist. SearXNG, Honcho and Kuma were not falsely registered as MCP.

Registration, discovery permission, tool review and action execution are separate.
New native Hermes YAML entries use its installed `tools.include: []` filter;
existing adopted server filters are preserved. The task adapter skips unapproved
connections. Mapping changes invalidate connection approval; changed schemas
invalidate applicable tool approval. Unrelated YAML values and Hub entries remain
owned by their original sources. Hermes round-trip YAML editing preserves comments
and quotes, with backups and a compare-before-replace check. Hub backups are saved
under `data/hermes/backups` before managed reconciliation. Partial cross-node sync
is recoverable; conflicts are reported rather than forcibly overwritten.

Native gateway activation remains **pending** until its active registration and
graceful idle lifecycle can be verified. No gateway restart loops or mid-task
restart was added. New task workers read the current approved catalog directly.
The fixture was seen in both saved registrations and live task-adapter discovery;
this is not proof of an activated Discord gateway fixture.

## Attachments and networking

The existing shared folder's live owner UID 10001, group 1000 and mode 2770 were
checked. `/data` is the core/speech container mapping. An explicit registered
attachment operation permits at most 4 MiB from configured Windows roots, rejects
symlinks and credential paths/content where detectable, verifies SHA-256 and saves
content-addressed files. The parent folder is not made world writable. Model and
MCP results use HANNI's credential filtering. Image/PDF contents cannot be fully
classified before processing; owner approval is required for transfer, and known
credential patterns are filtered in extracted results before model use.

Managed forwards bind Windows IPv4 loopback only. They retain host-key verification,
use batch/key authentication, reject occupied ports, and reconnect with bounded
backoff and an eight-attempt limit. The original private/reserved MCP destination
policy is unchanged. Forwarding failures and authentication failures are visible.

## Verified results and retained failures

- Local protocol tests cover idempotent submission, reconnect, cancellation,
  approval expiry/rejection, uncertain restart, duplicate effects, fresh reads,
  catalog revision/name conflicts, preservation, connection approval, changed
  definition checks, attachment boundaries, authentication failure, outages,
  occupied forwards, original-registry approval and independently read saved files.
  SDK compatibility tests cover two/three-channel transports and wire aliases.
- A real Hermes/Wonyoung/core search returned the official Python documentation
  URL. Submission was **62 ms**, complete observed run **28.078 s**.
- Two programmatically supervised real Hermes/core/Windows-registry trials saved
  the requested URL on the laptop. The original registry returned independent
  `read_after_write` verification, and the validation process separately opened
  each target file. Submission was **406 / 484 ms**; observed duration
  **52.047 / 54.922 s**. These include controller/polling/approval work, not just
  model throughput. The first fixture had a progress-hub setup error; its write
  evidence was retained and the corrected fixture was run separately.
- A temporary live fixture MCP registered in HANNI and Hermes configuration,
  was discovered by both clients, and was disabled/removed through the canonical
  catalog. Its only imported tool remained disabled. Its owned process was stopped.
- Four initial task runs failed in discovery: two old SDK import failures, one
  transport tuple failure and one wire-field alias failure. Their receipts remain.
  The initial install's missing PyYAML assumption was corrected by reusing installed
  `hermes_yaml`, without installing dependencies. The initial browser Host rejection
  remains recorded. Initial regression failures from an unconfigured dashboard's
  absent data root were fixed and rerun.

Raw receipts are private under `data/hermes`. The source archive excludes them,
tokens, task databases and deployment credentials. Reproducible commands follow.
The targeted regression run passed **147 tests**; the final bridge-specific run
passed **26 tests**. TypeScript checking and the production frontend build passed.
The final installed schema probe again returned 6/2/25 schemas with no failure.
Sparse development trials do not establish completion rates or P50/P95 distributions.
Natural-language ingress with the real resident, physical voice, first audible
latency, busy-model/outage/restart hardware scenarios and fully independent
general-goal completion remain unaccepted or **NOT TESTED**. Honcho recall errors
remain separate and unresolved; transcription compatibility was not changed.

## Setup, validation and rollback

From this Windows project, using the existing environment:

```powershell
.venv\Scripts\python.exe scripts\setup_hermes_bridge.py inspect
# Fresh installation only; refuses occupied paths or existing units:
.venv\Scripts\python.exe scripts\setup_hermes_bridge.py deploy
# Owned bridge source updates require all bridge tasks to be terminal:
.venv\Scripts\python.exe scripts\setup_hermes_bridge.py update
# Fresh Windows configuration only; refuses existing private settings:
.venv\Scripts\python.exe scripts\setup_hermes_bridge.py configure-windows --windows-root <authorized-folder>
.venv\Scripts\python.exe -m pytest tests/unit/test_hermes_bridge.py tests/unit/test_dashboard.py tests/unit/test_mcp_hub.py tests/unit/test_mcp_session.py tests/unit/test_desktop_launcher_integration.py tests/unit/test_assistant_lifecycle.py tests/unit/test_voice_interruption.py tests/unit/test_phase1_response.py -q
npm.cmd run check --prefix frontend
npm.cmd run build --prefix frontend
.venv\Scripts\python.exe scripts\check_hermes_bridge_live.py --output data/hermes/fresh-research-receipt.json
.venv\Scripts\python.exe scripts\check_hermes_bridge_live.py --windows-save --output data/hermes/fresh-save-receipt.json
```

The live checks refuse existing receipt files and require their mapped ports to
be free; close the owning HANNI session first. They use synthetic public research
and programmatic approval, not real microphone input or a physical UI click.

Deployment and private Windows setup have already been performed on these machines.
The next activation command is the existing `START_HANNI.cmd`, after gracefully
closing the old session. Review the bounded scope and connection/tool definitions
in MCP Hub before clicking **Enable delegation**. Then run the six requested
physical acceptance scenarios. A new source backend must be loaded; reloading
only the webpage does not update a running Python controller.

To roll back, disable delegation in the Hub (or set the private profile's `enabled`
to false while HANNI is closed). On Karina run:

```sh
sh /home/user/hanni-hermes-bridge/deployment/rollback-karina.sh
```

It disables only the new bridge and retains receipts/backups. Compare before
restoring any `config.yaml.hanni-*.bak` or Hub revision backup so unrelated changes
are not lost. Restoring native gateway configuration requires a separately
authorized, verified idle graceful activation; do not restart the protected gateway
as part of an automatic rollback. The resident model and other inference services
have no changed defaults to restore.

Priority handoff: restore the configured resident's normal owned startup and run
physical voice acceptance; validate general-goal evidence instead of model-only
completion; verify native gateway activation for newly registered servers; expand
fresh task cohorts and permitted integrations without widening execution scopes.
