# M4 independent native review, cycle 1

**FAIL acceptance: the selectable startup reconnect setting promises behavior the manager does not implement.** The numerical appearance/interaction mean is **8.79/10**, AI-template score **1.1/10**; the Add-server surface scores **8.15/10**. These scores do not override the concrete functional defect.

The verifier launched the actual portable Windows executable, navigated its real WebView and captured Win32 window frames with PIL ImageGrab. CDP was used for navigation and DOM inspection, never to generate the reviewed screenshots. The matrix contains **48 actual PNGs**, twelve states at physical **1920×1080, 1440×900, 1366×768 and 900×650**, with recorded DPI **120 (125%)**. A second actual native run captured **36 supplemental frames** at 1366×768 and 900×650, including dialog bottoms and inspector content/actions. All 84 frames were independently opened and inspected. No 150% DPI claim is made.

Evidence is retained under `data/hanni-mcp-hub-review/native-cycle-1-capture-retry/` and `native-cycle-1-supplemental/`; both include `results.json`. The initial `native-cycle-1/` attempt failed the verification harness's CDP target selection before any MCP frame/check was recorded. Its actual Home failure frame was inspected and retained; the harness dispatcher/target-selection correction changed no application code.

## Genuine interaction evidence

Both successful native runs passed **14/14** checks with no JavaScript errors, external requests or document horizontal overflow. The supplemental run performed the interaction sequence at the compact 900px window after initial Settings navigation. Settings → Integrations opens the Hub; saving creates disabled configuration without a child launch; connection cancellation launches nothing; actual paginated SDK discovery lists three tools without execution. UI approval installs the original registry adapter, and the original CLI-bound host/session executes exactly `mock.echo` once. UI disabling withdraws availability. Native export creates an actual owned JSON file matching the readonly review dialog and safe manager export; search has a real empty state; import preview neither launches nor persists a server; remove cancellation preserves configuration; actual delayed SDK discovery times out and revokes availability. No unrelated node, terminal or power writes occurred.

The protocol ledger contains list cursor 0, list cursor 2, one explicitly verified `mock.echo` call, and the timed-out subsequent list. The native model choice is explicitly deterministic; protocol, private Hub API, SQLite store, registry, controller session and exported file are real. Telemetry/device/model samples are synthetic, voice is inactive/unbound, and the isolated Google vault is empty. This native fixture does not claim configured local-model inference. The separately inspected actual configured Qwen model proof is recorded in [m5-controller-evidence.md](m5-controller-evidence.md).

OS clipboard contents were neither read nor overwritten. Copy JSON control availability and readonly output were inspected; native export file creation and exact bytes/JSON were verified before fixture cleanup.

## Exact Phase 2.6 rubric

Every category is scored out of **2**, exactly as the user specified: Typography/hierarchy, Layout/density, Spacing/consistency, Professional appearance, Interaction polish. State scores reflect all four sizes plus the relevant supplemental content; they are not scores for source code or unobserved below-fold controls. The overall score is the arithmetic mean of the twelve state totals.

| State | Typography/hierarchy /2 | Layout/density /2 | Spacing/consistency /2 | Professional appearance /2 | Interaction polish /2 | Total /10 |
|---|---|---|---|---|---|---|
| Empty | 1.80 | 1.75 | 1.80 | 1.80 | 1.65 | 8.80 |
| Add server | 1.80 | 1.70 | 1.75 | 1.75 | 1.15 | 8.15 |
| Connection review | 1.80 | 1.70 | 1.80 | 1.80 | 1.80 | 8.90 |
| Discovered tools | 1.80 | 1.60 | 1.75 | 1.80 | 1.70 | 8.65 |
| Tool inspector | 1.80 | 1.55 | 1.75 | 1.80 | 1.75 | 8.65 |
| Raw definitions | 1.80 | 1.60 | 1.75 | 1.80 | 1.75 | 8.70 |
| Tool approval | 1.85 | 1.80 | 1.80 | 1.80 | 1.85 | 9.10 |
| Server overview | 1.80 | 1.80 | 1.80 | 1.80 | 1.65 | 8.85 |
| Export review | 1.80 | 1.70 | 1.80 | 1.80 | 1.80 | 8.90 |
| Import preview | 1.80 | 1.65 | 1.75 | 1.80 | 1.80 | 8.80 |
| Remove confirmation | 1.85 | 1.80 | 1.80 | 1.80 | 1.85 | 9.10 |
| Timeout error | 1.80 | 1.70 | 1.80 | 1.80 | 1.80 | 8.90 |

Typography uses clear page/section/tool hierarchy, restrained readable interface text and monospaced original tool names/JSON. The plain graphite surface, aligned tables and genuine empty/error states avoid marketing templates. Spacing and control sizes remain consistent across native dimensions. The inspector earns a lower density score because page/status/connection controls push selected-tool content below the initial compact viewport; supplemental frames prove its full content and approval controls remain usable by ordinary vertical scrolling. Expanded schemas leave a sparse left column at desktop widths, another small density deduction. Long executable paths wrap in review/preview; the export filename is available in a selectable input although its tail is initially offscreen. Long Add/import/export dialogs require normal vertical scrolling at 900px, and their bottom buttons were actually captured and exercised rather than presumed accessible.

Approval/removal dialogs are particularly clear: exact tool identity/hash/classification, readable scope and distinct cancellation/destructive actions. Error state accurately says timeout/Failed and leaves appropriate reconnect controls. The Add-server interaction deduction specifically reflects the unsupported option below; the broad identity mismatch also lowers overall navigation polish.

**AI-template: 1.1/10.** The result is a restrained management console with actual protocol facts and original schemas. There are no gradients, promotional badges, fabricated avatars/logos, generic three-feature tiles, decorative halos or fake metrics. Standard form/dialog affordances and a common charcoal palette account for the small residual score.

## Actual defects and ownership

| Severity | Screen/evidence | Observed defect | Required correction | Owner |
|---|---|---|---|---|
| Medium | `native-cycle-1-supplemental/add-server-bottom-900x650-native.png` and 1366 equivalent | Selectable “Reconnect this approved configuration when HANNI starts” promises automatic launch although the manager intentionally never auto-connects. Detail wording also implies automatic reconnect support. | Remove the unsupported selectable promise and state that restarting requires explicit reconnect. Preserve safe legacy import metadata without presenting it as implemented behavior. | Worker 2, coordinated by root |
| Low | `native-cycle-1-capture-retry/empty-1920x1080-native.png` and all desktop page states | Header breadcrumb says “Mission / MCP Hub” while page says “Settings / Integrations” and Settings is selected. | Use the correct Settings group breadcrumb for this route. | Root |

No clipping defect was inferred from legitimate scrolling. Supplemental `tool-inspector-content-900x650-native.png` and `tool-inspector-actions-900x650-native.png` prove actual schema/classification/control readability; `connection-review-bottom`, `import-preview-bottom` and `export-review-bottom` prove their compact action areas.

## Reviewed artifact and remaining gate

| Artifact | SHA-256 |
|---|---|
| Native executable | 9bf90dc1438e1776369f668117d88c2a5f76a33fc6f796c4d9f41a8a7e586263 |
| app.js | 5e7129a6bc1f6bcc924fc8ac48c9bcf39a0777bc439327b364b6616f890a68fe |
| style.css | 56239e48e73c565b17bbbf815cbea8dd0110a727be102b72bff173a6f8de7c00 |

[Independent full backend acceptance](m3-cycle-3.md) remains **964 passed, two skipped, 17 subtests**. The coordinator's separately executed browser cycle 6 reports **82 passing checks**, including responsive/stale approval/persistence/security interactions; these are attributed evidence, not silently claimed as this verifier's native execution.

All owned native and SDK processes closed after capture. A bounded label-only correction requires a new built-bundle hash and targeted actual native Settings navigation/Add/detail confirmation, plus relevant browser checks. This report preserves cycle 1 as failed; final acceptance is pending that correction and independent recapture.

