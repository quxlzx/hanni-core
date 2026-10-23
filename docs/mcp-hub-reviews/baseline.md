# MCP Hub independent baseline and verification audit

Reviewed2026-10-09 before implementation, authoritative tracked commit `edd9a043b45d1b6c7ef056cae4460fc5c82c8468`. The independent verifier read the complete Phase2.6 user brief and inspected actual repository contracts. No application code, production assistant, microphone, model, external MCP process or GUI was started by this audit. Exactly the existing three specialized subagents are retained; the verifier does not implement features.

## Independently run baseline

| Check | Actual result | Evidence |
| --- | --- | --- |
| Full Python suite | **882 passed,2 skipped,17 passing subtests**, zero failures/errors,55.121seconds; exit0 | `.venv/Scripts/python.exe -m pytest -q --junitxml=data/hanni-mcp-hub-review/baseline-pytest.xml` |
| Frontend type check | **PASS**, exit0 | `npm.cmd run check`, cwd `frontend/`, actual `tsc --noEmit` |
| Frontend production build | **Coordinator-run PASS**,341.58kB app/60.14kB CSS; no logical tracked changes | Root-owned build before M1checkpoint `e768d1a`; no verifier concurrent build |
| Native MCP Hub interface | Not implemented at audit | No screenshot/visual grade fabricated |

JUnit records901total including seventeen subtests,884top-level cases,2skips,0failures/errors. Existing skips are the historical local inference report absent from this checkout and console-script check because `hanni` is not on PATH. The tracked worktree remained clean after tests. Five pre-existing unrelated untracked files were left untouched: `CALENDAR_FUTURE_DATE_ROOT_CAUSE.md`, `HANNI_LAYA_SHADOW_PATCH_20261009.zip`, `MODEL_BAKEOFF_FINAL.json`, `MODEL_BAKEOFF_FINAL.md`, `MODEL_PERSONALITY_BLIND.md`.

## Actual reusable contracts

- Installed official MCP SDK is **2.2.0**. Local inspection confirms `mcp.client.stdio` and `mcp.client.streamable_http` modules, with project dependency `mcp>=2.0,<3`. This is observed local availability, not a claim that external connections already work in HANNI.
- `src/hanni/mcp/host.py` supplies `McpHost`, bounded current-registry retrieval/model schemas and calls through `ToolRegistry.execute`. `session.py` supplies the existing bounded model/tool loop. `server.py` is HANNI's local read-only server facade, not an external connection manager. The original controller/session construction is in `cli.py`; no presumed `core/controller.py` exists.
- `src/hanni/tools/base.py` owns ToolDefinition/ToolRequest/ToolRegistry. Actual authorization uses permission profiles, Safe Mode/emergency stop and dynamic confirmation. `McpHost.call` supplies confirmed=false and preserves final registry authority. Approval to connect a server must not replace confirmation of a sensitive execution.
- ToolDefinition currently derives JSON Schema from flat Python types and limited constraints. Imported nested objects, arrays, unions, references and additionalProperties must be faithfully preserved and actually validated, or clearly rejected. A lossy permissive flattening is not acceptable schema preservation.
- CapabilityAPI and LocalCapabilityDiscovery have revision-aware caches; ToolRegistry increments revision on register and does not currently expose unregister. Dynamic removal/replacement must update original-registry revision/indexes without discarding built-ins or leaving stale executable tools.
- Model-facing wire names currently normalize IDs and truncate to64characters. External identity collisions must be explicitly resolved/tested while retaining original external call names and stable server identity.
- DashboardServer gates same-origin/token writes and private reads. MCP API reads/mutations must retain these gates. Original ToolAudit/redaction and local persistence patterns are reusable; credentials must not enter diagnostics, snapshots or exported configuration.

The audit identifies verification risks, not tested defects in an unimplemented Hub. Worker1 owns integration changes; the root owns architecture/contracts and build synchronization. Workers received source-specific findings before implementation.

## Required independent acceptance evidence

Use an isolated temporary data directory and actual local mock MCP stdio plus Streamable HTTP servers. Mock service content is disclosed, but manager/registry/router/controller/permission calls are genuine. Do not mock private Hub CRUD responses in final UI verification. Discovery may initialize/list only and must never tools/call.

Critical tests must cover faithful schema/output metadata, pagination and list-change refresh, namespace/wire collisions, valid and invalid argument types, restrictive unknown classification, explicit connect approval, separate per-tool enablement, changed-definition reapproval, disabled/removed/unavailable rejection, request-token/Origin/session isolation, environment allowlist and secret redaction, unsafe endpoint/redirect/metadata denial, timeouts/cancellation, hot updates/in-flight safety, atomic persistence/reopen and built-in capability preservation.

The integration must prove at least status/echo/create-record-style tools through **original registry retrieval, existing McpHost/model-facing tool selection, existing session/controller execution and permission gates**, ending in genuine mock-server tools/call. Direct SDK connectivity or calling an adapter alone is insufficient router/controller proof. Model response determinism may be used for reproducible session-layer tests, explicitly distinguished from a configured local-model smoke.

Final UI checks must exercise Add/Test & Discover with explicit local command approval, disabled initial tools, actual schema/version inspector, individual/bulk enable/disable, definition-change approval reset, refresh/reconnect/disconnect/remove Cancel/confirm, readable safe failures, import preview without launch/overwrite, non-secret export, real persistence, keyboard navigation and responsive composition. Actual native framed captures use1920x1080,1440x900,1366x768 and a compact window at observedWindows125%DPI; no150%DPI claim. No GUI starts before coordinator ownership release/coherent build.

## Exact new Phase2.6 visual rubric

This task replaces the preceding Phase1/2 six-category rubric. **Typography/hierarchy2; Layout/density2; Spacing/consistency2; Professional appearance2; Interaction polish2**, summed to10. Visual quality must exceed8.5, AI-template appearance must be at most2, and all critical security/controller integration/regression gates must pass. No native/Desktop category substitution and no reuse of historical8.69 as an MCP Hub score. Actual pixels must be independently inspected before numerical grading.

Resume after root saves architecture baseline/checkpoint and approves non-overlapping implementation contracts. Preserve this baseline; record implementation failures and checkpoints honestly before bounded repairs.
