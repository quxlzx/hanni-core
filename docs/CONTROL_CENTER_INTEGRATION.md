# Hanni inference control

The Models screen now opens the control center adapted from
`HANNI-Control-Center-8d7482a.zip`. HANNI and Wonyoung node details in Cluster
use the same controls. Benchmarks remains a tab in Models; worker scheduling
limits remain available under the cluster controls.

The integration includes four deployment cards, exact upstream model readiness,
start/stop/restart, process status, logs, GPU and host measurements, context
validation results, independent streaming chats, simultaneous comparison,
per-model conversation history, clear history, cancellation, reasoning controls,
temperature/top-p/output budgets, and measured token usage and latency.
Flash-Next also exposes its supported reasoning-token budget.

The existing Linux control service owns GPU/RAM admission, systemd/Strata
lifecycle, SQLite history, metrics and request accounting. Hanni's Windows
backend adapts its authenticated API at `/api/inference/`; the UI sends requests
to Hanni's loopback dashboard. This integration depends on that existing service
running on the configured HANNI node at port 8200. It does not deploy a replacement
Linux service or copy the ZIP's historical evaluation results into live evidence.

Hanni reads the existing operator token through its configured, trusted SSH
transport from `/home/<configured-user>/hanni-control/.env`. The token stays in
backend memory and is registered for log redaction. `HANNI_CONTROL_TOKEN` can
override that source. Destinations come from private compute configuration;
browser input cannot choose a host, credential file, command or upstream URL.
All model/history reads require the dashboard token, and mutations also require
Hanni's same-origin write checks. Safe Mode blocks generation and lifecycle
changes while permitting cancellation and history access. Active streaming
requests check the stop boundary between upstream chunks.

## Private deployment migration

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/import_control_center.py
```

This updates the protected `data/compute/deployment.json`, with a first-run backup
at `data/compute/deployment.before-control-center.json`:

| Worker | Deployment | Port | Configured context |
| --- | --- | ---: | ---: |
| athena-p6000 | Nex-N2-mini | 8102 | 32768 |
| athena-p40 | Mellum 2.1 | 8103 | 65536 |
| hanni-swift | Swift 1.5 | 8101 | 32768 |
| wonyoung-strata | Flash-Next | 8080 | 131072 |

The migration replaces overlapping registrations, adds Swift, retains other
workers and existing sharing permissions, and preserves scheduler policy.
These services are externally managed: the older compute launcher is disabled
for them, so Hanni cannot create competing model processes with old settings.
Live health and model identity are measured through the existing SSH tunnels.
Adaptive routing and Model Lab therefore see the same deployments; automatic
eligibility still depends on measured capabilities and authorized data sharing.
The resident assistant's model selection is governed by those existing policies.

## Validation and remaining limits

The focused dashboard, adapter, compute and routing suites passed 120 tests.
They cover private API access across all verbs, bounded routes and
parameters, protected lifecycle, emergency stop, streaming cleanup, native SSE,
history operations and repeatable migration. The frontend passes TypeScript
checking and builds its packaged dashboard assets.

Live verification on the configured private cluster found all four exact model
identities healthy at their configured contexts, read their actual GPU/host
metrics, and completed four simultaneous synthetic streaming requests through
the native Hanni API. A live cancellation check returned a completed, cancelled
stream for only the selected model. These checks do not establish model quality or independently
verify full-context retrieval. Browser checks cover deployment cards, the
metrics dialog, comparison, independent chats, Benchmarks navigation, and narrow
layout. Browser comparison histories are isolated from operator histories.

The imported controller's Flash-Next stop/restart protection remains active.
Mellum's documented repetitive-input correctness failure remains unresolved.
Unavailable telemetry remains N/A, and claimed context targets remain separate
from verified retrieval evidence. Remote stop/restart was not exercised during
integration verification. The installed service and models remain independently
managed. The native desktop shell uses the repository backend and rebuilt
dashboard assets; restart Hanni to load the updated backend.

Verification output and screenshots are in the ignored local directory
`data/control-center-verification/`. Lifecycle acceptance receipts made through
Hanni are stored locally at `data/inference-control/audit.sqlite`; prompts and
credentials are not included in those receipts.
