# HANNI MCP Hub verification

Phase 2.6 is **PASS**. The MCP Hub connects installed stdio servers and Streamable HTTP endpoints, discovers original definitions without execution, and registers approved tools in HANNI's existing registry/router/controller. The actual configured local model selected and executed an imported read-only tool. The original backend, profiles, confirmation, audit and EmergencyStop remain authoritative.

```text
HANNI MCP HUB - VERIFICATION

MCP stdio support:           PASS
MCP HTTP support:            PASS
Tool discovery:             PASS
Schema preservation:        PASS
Dynamic registry:           PASS
Router integration:         PASS
Permission enforcement:     PASS
Tool execution:             PASS
Configuration persistence:  PASS
Frontend functionality:     PASS
Backend regressions:        PASS

Visual quality:             8.85/10
AI-template appearance:     1.1/10

Overall status:             PASS
```

## Executed evidence

| Gate | Verified result | Report |
| --- | --- | --- |
| Full backend regressions | 964 tests passed, two existing skips, 17 passing subtests; zero failures/errors. Includes 81 MCP Hub cases, 24 independently authored. | [Independent backend cycle 3](mcp-hub-reviews/m3-cycle-3.md) |
| Frontend | Typecheck/production build and 12 contract tests passed. Actual manager-backed browser cycle 7 passed 86 checks, including 24 layouts, stale approvals, persistence, import/export and UUID retry. | [Browser review](mcp-hub-reviews/m4-browser.md) |
| Actual configured model | Six checks passed through the original launcher/controller with local Qwen3.5-4B. Paginated discovery made no calls; model execution called exact external `mock.echo` once; private audit, hot withdrawal and clean shutdown corroborate it. | [Independent model evidence](mcp-hub-reviews/m5-controller-evidence.md) |
| Native functionality | 17 distinct checks passed in each of two actual native runs, including the corrected navigation/restart guidance and owned export bytes. No JavaScript, external-request, overflow or capture errors. | [Independent native cycle 2](mcp-hub-reviews/m4-native-cycle-2.md) |
| Native visuals | Independently inspected 92 fresh actual Win32-framed images: 52 matrix and 40 supplemental compact frames. Four physical sizes, measured 125% DPI. Exact five-category /2 rubric: mean 8.85, minimum state 8.65; AI-template 1.1. | [Scores and visual limits](mcp-hub-reviews/m4-native-cycle-2.md) |
| Security | Original permissions/stop, hash-bound approvals, schema/runtime validation, restricted launch, guarded destinations/authentication, credential reflection protection, private audit and transactional persistence are verified within the documented scope. | [Security report](MCP_HUB_SECURITY.md) |

The final native fixture uses the real private API, manager, SQLite, original registry/controller and official SDK server. Its model selection and telemetry are explicitly synthetic, voice is inactive and its Google vault is empty. Actual configured-model inference is proved separately above. No live external provider, voice input or node power action is claimed.

Failed backend/native cycles and browser harness corrections are preserved in [resumable checkpoints](MCP_HUB_CHECKPOINTS.md). They exposed and repaired occupied-port cleanup, rejected shadow-service POST cleanup, misleading refresh status, unsupported startup-reconnect guidance and an incorrect breadcrumb. No original denial assertion, model-training file or benchmark expected answer was changed.

## Connect a real server

Open **Settings > Integrations > MCP Hub**. Add an already installed executable with literal JSON arguments, or a public HTTPS Streamable HTTP endpoint. Choose **Test & Discover**, review the exact destination and explicitly approve the connection. Inspect discovered original definitions, select the intended tools and approve an appropriate classification. Approved connected read-only tools become available to the running assistant without a model restart. [Complete setup and examples](MCP_HUB.md) cover credential references, imports, exports and bounds.

Normal conversations retain the existing read-only/observe-first policy. Write/destructive/unknown tools require original authority; the tested write path is a trusted confirmed ToolRequest on the attached registry. No conversational write-confirmation/resume UI or standalone imported-tool CLI is added. Saved servers require explicit reconnect after restart. Private/Tailscale remote MCP endpoints, automatic OAuth and automatic startup connection are unsupported.

The native wrapper is unchanged; it loads the rebuilt frontend and repository backend. Restart an already-running original dashboard/controller to load new Python code. All verification-owned model, dashboard, SDK and native processes were closed. No publish or push was performed. The five unrelated pre-existing root files remain untouched.

## Reviewed artifact

| Artifact | SHA-256 |
| --- | --- |
| Native executable | `9bf90dc1438e1776369f668117d88c2a5f76a33fc6f796c4d9f41a8a7e586263` |
| app.js | `358c171b3c1aafabf811c6d42b35315410e84d0ca40e90e0fadbfde938bfeca0` |
| style.css | `56239e48e73c565b17bbbf815cbea8dd0110a727be102b72bff173a6f8de7c00` |

Local raw evidence: `data/hanni-mcp-hub-review/m3-cycle-3-full-pytest.xml`, `browser-cycle-7/browser-result.json`, `live-controller-cycle-1/`, `native-cycle-2/` and `native-cycle-2-supplemental/`. These verification artifacts are retained locally; reproducible harnesses live under `scripts/mcp_hub_review` and `scripts/check_hanni_mcp_controller.py`.
