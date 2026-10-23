# MCP Hub independent verification plan

This is a test plan, not executed results. Baseline is [baseline.md](baseline.md); M1 checkpoint `e768d1a`. Verifier owns supplemental test/harness/report artifacts only. Worker1 owns manager/transport/registry implementation and reusable actual SDK mock servers; Worker2 owns Hub components. GUI and production builds remain coordinator-serialized.

## Public manager contract to verify

Proposed synchronous `MCPManager(data_dir, registry=None)` provides snapshot/add/update/connect/refresh/reconnect/enable_server/disable_server/disconnect/remove/approve_tools/disable_tools/preview_import/import_configs/export_configs/attach_registry/close. Initial constructor reads local SQLite only; no auto-connect or executable capability until separate connection approval, definition-bound tool approval and available server. Exact concrete API/module is inspected before tests are written; proposed names are not assumed implemented.

## Adversarial verification matrix

| Area | Genuine stimulus | Required observation |
| --- | --- | --- |
| Discovery only | SDK mock initializes and returns multiple/paginated tool definitions | Original descriptions/input/output schemas/annotations preserved; server call ledger stays empty |
| Input contract | Nested object/array, required fields, unions, bool against integer, extra properties, enum, finite number | Exact valid arguments reach original external name; invalid input never reaches server |
| Untrusted schema | Invalid schema, unsupported reference/dialect, huge/deep definition, malicious description | Reject or safely mark unavailable with readable redacted diagnostic; no speculative inferred fields/execution |
| Definition approval | Approve current hash, mutate description/schema/annotation/meta, refresh | Version/hash changes, stale approval cannot enable or invoke, renewed approval required |
| Lifecycle race | Save selected McpTool/ToolDefinition, disable/disconnect/remove/replace before invoke | Stale saved handler cannot call unavailable server or inherit changed approval; built-ins remain present |
| Dynamic retrieval | Prime CapabilityAPI/discovery caches before approve, disable and remove | Same registry/host immediately reflects update, revision changes, original index invalidates; no restart |
| Wire identity | Two long/similarly normalized external names, same tool on two servers, duplicate definition | Internal/wire identities collision-safe; exact external names preserved on tools/call |
| Execution authority | Original McpHost route plus McpToolSession selects imported tool | Actual mocktools/call ends original model/session/registry path, audit/request correlation preserved |
| Permission separation | Connect approved but tool unapproved; unknown/write/destructive classification; restricted actor; SafeMode | No connection approval becomes blanket execution authority; explicit existing confirmation/profile gates remain final |
| Session isolation | Missing/wrong token, wrongOrigin/Host, cross-site session on private Hub routes | 403 before secret/store/process/network access; UI nevertools/call directly |
| Local process | Constructor/import/add first, then unapprovedconnect, then approved fixture command | No initial launch/download; shellFalse/direct argv; explicit approved command only; bounded teardown |
| Environment privacy | Parent unrelated syntheticsecret plus explicit syntheticsecret reference | Inherited environment allowlisted; only explicitly referenced values reach server; never snapshot/export/log |
| HTTP endpoint | Metadata/privateDNS/IP, mixed public/privateDNS, credential URL, unsafe scheme, redirects | Reject before network; pinned approved address prevents rebind; no proxy/redirect auth leak |
| Auth privacy | HTTP401 with hostile body, Bearer synthetictoken, remoteerror echoescredential | Auth-required state/redacted diagnostics; synthetictoken absent from API/UI/export/log/store where prohibited |
| Resource bounds | Slowtools/list/call, huge output, malformedresult, unsupportedbinary/resource | Timeout/cancel where supported and bounded compatible result; no leaked process/session |
| Persistence | Reopen actual manager/store after configured+approved+disabled states | Stable IDs/hash/settings retained, disabled not autoenabled, no auto-process/connect, corruption fails safely |
| Import/export | Common mcpServers JSON preview, conflict/unsupported/env literal, confirmation | Preview neverlaunches; duplicate cannot overwrite silently; exports nonsecret references only |
| Built-in preservation | Existing CPU/RAM/process capabilities and routing evaluations before/after | Original builtin registry/permissions/results unchanged; no expected benchmark edits |

Mock service definitions/data are synthetic and explicitly disclosed, but transports, manager, registry, local HTTP gates, store and controller calls are real. Worker1 reusable mock fixture must expose actual stdio and StreamableHTTP startup plus safe metadata change/error/latency controls. Independent tests supplement worker checks; they do not monkeypatch private CRUD to return desired outcomes.

## Native UI review

After coherent build/source freeze and root GUI GO, capture actual framed executable at1920x1080,1440x900,1366x768 and compact900x650 observed125%DPI. Review empty server state, configured awaiting approval, real connected discovered tool list, exact schema/version inspector, permission approval, disabled/unavailable/changed definition, safe authentication/timeout error, import preview and exact remove confirmation. Exercise keyboard search/filter/select/dialog, individual/bulk enable/disable, refresh/reconnect/disconnect, import conflict/no-launch and export redaction, actual application/store close/reopen.

The new visual rubric is **Typography/hierarchy2 + Layout/density2 + Spacing/consistency2 + Professional appearance2 + Interaction polish2**. Sum actual inspected category points; require>8.5overall and AI-template<=2. Earlier desktop rubric/scores are not reused. A passing interface cannot override an unauthorized execution, missing actual controller routing or failing builtin regression.

## Configured local-model proof

The coordinator owns a final isolated original configured-model/controller smoke using the safe discovered mock status/echo tool, shared native Mini or Conversation and genuine original execution audit. The verifier independently inspects its actual framed response and metadata. Deterministic model doubles can verify repeatable session-level safety, but are labeled accordingly and are insufficient as the only claim that HANNI's local model can use imported tools.

Checkpoint each actual stage; preserve failed test/frame evidence before repairs. Final report states PASS/FAIL/BLOCKED only for independently observed or explicitly attributed coordinator-run results.
