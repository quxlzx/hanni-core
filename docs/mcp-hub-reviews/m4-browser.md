# M4: genuine browser interaction review

Final functional outcome: **browser-cycle-7 PASS, 86 recorded checks, zero errors**, after the actual native review identified a startup-reconnect affordance mismatch. Evidence is `data/hanni-mcp-hub-review/browser-cycle-7/browser-result.json`. The accepted cycle-6 baseline remains unchanged with 82 checks. Every earlier result, failure screenshot and failure page text remains under its original cycle directory. Browser debug images are functional evidence; independent native screenshots determine visual acceptance.

The harness is `scripts/mcp_hub_review/check_browser.py`, running installed headless Microsoft Edge against `HubReviewFixture`. The fixture uses the actual authenticated DashboardServer adapter, MCPManager, SQLite persistence, official SDK stdio connection, and the controller's original ToolRegistry. Its external server is the bounded SDK fixture in `tests/fixtures/mcp_hub_mock.py`. Telemetry and deterministic model fixtures are synthetic. Private CRUD, discovered schemas, registry state and persistence results are not fabricated.

## Retained cycles and corrections

| Cycle | Outcome / recorded checks | Observed failure | Classification and correction |
| --- | --- | --- | --- |
| 1 | FAIL / 12 | Strict focus assertion rejected a Chromium Tab transition to BODY/browser chrome. | Harness expectation. The native HTML dialog remained modal and background controls remained inert. The corrected check permits BODY only while `:modal` is true and an explicit attempt to focus a background control is rejected. No dialog implementation change. |
| 2 | FAIL / 18 | Raw Windows path substring was absent from the JSON-rendered argument array because backslashes were escaped. | Harness expectation. The corrected check parses the argument JSON and compares every original argument and the literal executable exactly. No UI change. |
| 3 | FAIL / 32 | Expected an inspectable invalid tool after sending a protocol-invalid root schema type. | Harness expectation: SDK InputSchema requires root `type: object`, so the malformed whole listing correctly fails closed. The revised harness separately checks that failure and a protocol-valid object schema containing an unsupported regex, which HANNI retains for inspection and blocks from approval. **A real UI copy defect was also found:** a failed refresh snapshot still produced “Definitions refreshed.” Root authorized a neutral refresh-attempt notice, described below. |
| 4 | FAIL / 38 | Missing-executable test remained disabled because its new connection dialog captured an old configuration hash immediately after a concurrent update. | Harness synchronization. Backend rejection was correct. The harness now explicitly refreshes status and waits for the current server name before opening the next approval. Stale-dialog rejection is still tested separately. |
| 5 | FAIL / 48 | Persistence assertion compared server arrays in insertion order before restart and UUID order after SQLite reload. | Harness expectation. `MCPStore.load()` intentionally reads `ORDER BY id`. The revised comparison checks ID-keyed complete configurations, config hashes and original-name-keyed definition hashes, recording both maps as evidence. No storage change. |
| 6 | **PASS / 82** | None. | Frozen UI and backend; verification-only fixes described above. |
| 7 | **PASS / 86** | None. | Rebuilt after the real native-review startup-reconnect copy/affordance correction and Settings breadcrumb correction; four explicit regression checks added. |

Cycle 3's actual UI correction changes the success-path notice to **“Definition refresh attempt finished. Review server status and any definitions requiring approval.”** MCP runtime errors can return an authoritative failed snapshot with HTTP 200; this notice accurately describes the completed attempt without claiming successful discovery. Cycle 6 explicitly verifies the neutral notice when the protocol-malformed listing fails. No status logic or backend contract changed.

## Actual functional coverage

- Settings → Integrations opens the genuine empty Hub; keyboard Tab keeps the background inert; Escape cancels without saving or launching.
- Invalid argument types fail before API save. Saving a server leaves it disabled and unlaunched. A deliberately aborted actual Add response after the backend write exercises an explicit identical UUID retry; the persisted server is not duplicated.
- Connection review preserves the exact executable and original argument array. Explicit approval starts SDK initialization and paginated discovery; discovered tools remain disabled until exact-definition approval. Original input/output schemas, annotations and metadata remain inspectable.
- Individual and batch approval affect only selected exact definitions in the original registry. Disable removes actual registry availability. Changed tool hashes reset approval and block an already-open stale approval dialog. Concurrent configuration changes cannot launch an unseen executable; stale editor saves fail while preserving the draft.
- A malformed protocol listing fails closed with cached tools unavailable. A protocol-valid unsupported regex schema remains inspectable, is marked invalid, and cannot be approved. Actual missing-executable failure is reported without false availability; editing and explicitly reconnecting restores discovery.
- Server/tool search and filters have useful empty states. Import preview launches nothing, validates supported candidates, excludes plaintext environment values, and preserves warning details. Import commits disabled even if the imported preference requests reconnect. Conflicting import is rejected without overwrite or launch.
- Export performs the actual fixed local file write under the fixture-owned `mcp/exports` directory. The displayed readonly JSON equals that file exactly, credentials are excluded, and no browser download is required. Explicit Copy JSON is checked only after browser clipboard permission is granted for the isolated fixture origin.
- Actual manager close/recreation reloads stable IDs, complete configurations, config hashes and tool-definition hashes from SQLite. Imported disabled servers remain disabled and unlaunched. Browser reload reads the persisted records.
- Overview and selected inspector each pass horizontal document overflow checks at 512, 600, 640, 720, 800, 900, 1024, 1079, 1280, 1366, 1440 and 1920 CSS pixels: **24 layout checks**. These are browser layout checks, not native visual scores.
- A real private GET rejected by changing its request token retains the inspectable stale snapshot and blocks mutation controls. Authenticated refresh recovers. Escape cancellation preserves the selected integration; confirmed removal deletes only that integration.
- All frontend mutations use the authenticated fixed-operation UUID/confirmation body. The SDK ledger contains ten paginated `list` entries and **zero `call` entries**. No frontend JavaScript errors, external browser requests, unrelated SSH or node power requests occurred.

## Cycle-6 baseline artifact and limits

Build/typecheck passed after the copy correction; twelve frontend contract tests passed. The frozen bundle is 375.64 kB JavaScript and 68.25 kB CSS.

| Artifact | SHA-256 |
| --- | --- |
| `src/hanni/dashboard/static/app.js` | `5e7129a6bc1f6bcc924fc8ac48c9bcf39a0777bc439327b364b6616f890a68fe` |
| `src/hanni/dashboard/static/style.css` | `56239e48e73c565b17bbbf815cbea8dd0110a727be102b72bff173a6f8de7c00` |

This cycle does not execute discovered tools, use a live model/provider/microphone, launch native GUI, issue SSH or power actions, or alter production data. Manager persistence testing proves genuine SQLite reload, not an entire native application restart. One real Add response is deliberately lost to test UUID retry; one private read is deliberately rejected with an invalid token. Those faults do not mock private write results. Browser clipboard access is explicitly scoped to the isolated origin and user-click action; native clipboard review is separate. Registered write/destructive/unknown tools remain subject to the existing model policy and execution confirmation gates. Direct tool execution is absent from the Hub. Independent native screenshot scoring remains pending this functional milestone.

## Native-review correction and cycle-7 frozen artifact

The independent native Add-server capture exposed a real behavior mismatch: the selectable “Reconnect this approved configuration when HANNI starts” checkbox promised automatic startup behavior that MCPManager intentionally does not perform. After native review processes closed, root authorized a bounded UI correction. The checkbox is replaced with “Saved servers require an explicit reconnect after restarting HANNI.” Connection settings now display “After restart / Explicit reconnect required.” Internal `auto_connect` form/config metadata and imported/exported compatibility remain unchanged; no backend behavior changes. Root also corrected the MCP Hub shell breadcrumb to Settings.

One coordinated production build/typecheck passed, and the existing twelve frontend tests passed, including the full legacy `auto_connect: true` roundtrip. Cycle 7 repeats every accepted cycle-6 behavior and adds four genuine UI/store checks: Settings breadcrumb, manual restart note with no selectable startup-reconnect checkbox, truthful connection detail fact, and imported legacy `auto_connect: true` surviving actual SQLite reload while remaining disabled and unlaunched. **86 checks passed, including the same 24 browser layouts; no JavaScript errors, external requests or discovered tool calls.** Cycle 6 evidence is retained without modification.

The current frozen bundle is 375.51 kB JavaScript and 68.25 kB CSS:

| Artifact | SHA-256 |
| --- | --- |
| `src/hanni/dashboard/static/app.js` | `358c171b3c1aafabf811c6d42b35315410e84d0ca40e90e0fadbfde938bfeca0` |
| `src/hanni/dashboard/static/style.css` | `56239e48e73c565b17bbbf815cbea8dd0110a727be102b72bff173a6f8de7c00` |

Independent native recapture and visual acceptance are coordinated by root and Verifier. No visual score is assigned by Worker 2.
