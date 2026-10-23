# Workflows browser cycle 1: failed harness isolation

The actual headless browser cycle failed after 22 passing checks. Evidence is retained in `data/hanni-v3-review/browser-cycle-1/browser-review.json` and `browser-debug-failure.png`. This is not native visual acceptance and no visual score was assigned.

The failure occurred when the main window's plan confirmation was expected to become enabled after a temporary private-read outage. An earlier expiry test called `expiry_page.clock.set_system_time(...)`. Inspection of the installed Playwright 1.63.0 implementation (`_impl/_clock.py`) confirms that its `Clock` forwards operations to `BrowserContext`, rather than applying them only to one page. The expiry page shared the main page's context, so both client clocks moved beyond the approval's expiry. The UI correctly retained an expired, disabled confirmation. Closing the expiry page did not reset the sibling window's clock.

The authorized correction changes verification only: the expiry test uses its own browser context with the same actual private server, token and approval record. Its request/error listeners remain recorded, and the context closes in `finally`. The unchanged main-window oracle still requires confirmation to recover after the genuine endpoint outage ends. Production UI/backend source and compiled assets are unchanged by this correction; a new cycle directory retains the original failure.

## Actual checks reached

The 22 passing checks cover the original private-token gate, first-fetch error without a false empty state, actual unattached empty history, eight keyboard/modal background-inert cycles, Escape without a mutation, two rapid activations producing one submission, a real durable goal submission whose HTTP response is aborted, an identical explicit retry with the same UUID and one workflow, two scripted planning passes through the original model interface, actual notification creation in the existing store, notification Inspect opening and consuming its exact workflow ID, no approval/invocation/revision change from reading that notification, client expiry preventing an approval POST, exact planned path/hash/criteria inspection, and disabled confirmation with an explanation during the real private endpoint outage.

No goal was approved or executed before this failure. The remainder of the authored suite, including actual file outcomes, managed artifact hashes, sensitive write approval/rejection, completion reconciliation, detached saved history and responsive layout checks, was not reached and has no result in this cycle. No browser JavaScript errors or nonlocal requests were recorded before the failure.

## Frozen artifact fingerprints

| Artifact | SHA256 |
| --- | --- |
| Compiled app.js | `a9f09e6e3ea93e00b1d825f525e4f9fe5b86e2a64dc337e978908379756e71a2` |
| Compiled style.css | `76c1e4d5c353b93acf71f02cf40de00d11f03515aae2a3930e9f31d675333e4e` |
| workflow_types.ts | `90ebd86343ac76db7aae723ee219e9476c2650d1156b4361e08f983a6c6356fa` |
| workflows.tsx | `51cb18572bad35addf083501da553f7d3c0e2dbc5a26ccfc63d4effa1b2e95ae` |
| Original cycle-1 harness | `7d0550950dad38b86ade8414c2ae6d2d8640ffc3f7a6700bd61fb5fcb5bacf2d` |

## Fixture limits

The suite uses the real isolated DashboardServer, private WorkflowHub, WorkflowService, original McpHost and original ToolRegistry. Planning replies and cached RAM/device telemetry are scripted/synthetic, so this is not a natural-language intelligence or real-hardware measurement. A fixture-only original host action whitelist includes `file.write`; read-only mode, owner permissions, risk and confirmation gates remain real. Original handler observers preserve execution gates and record handler entry rather than substituting `host.call`.

The private outage injects HTTP 503 only after the original Host/Origin/private-token checks. The lost-response test aborts a real successful backend response without fabricating a CRUD result. All files, stores, goals and notifications belong to the isolated temporary fixture; provider credentials are explicitly disconnected. No live model, native window, provider, microphone, app launch, SSH or node power action is used. Debug browser images do not establish a native visual score. The final planning holdout remains separate and was not read or tuned.
