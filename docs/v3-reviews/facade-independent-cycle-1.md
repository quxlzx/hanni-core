# V3 private API and lifecycle fault cycle 1

**FAIL: original 2/4 passed; expanded 2/5 passed.** Independent fault tests are `tests/integration/test_workflow_facade_verifier.py`. JUnit evidence is `data/hanni-v3-review/facade-independent-cycle-1.xml` and `facade-independent-expanded-cycle-1.xml`. Current integration/test hashes are recorded in `facade-cycle-1-source.json`.

Two genuine HTTP gate tests pass **13 denied private reads and 8 denied mutations/path requests** against the original `DashboardServer`/`Handler`, before any workflow lookup or action. Cases include invalid host, foreign/null origin, cross-site fetch, absent/stale token, token supplied only in query text and a dynamic-looking unsupported path. Only the endpoint observer is injected; no model, service executor, provider, node or user state is used.

Three actual integration behaviors fail under injected component errors:

| Finding | Severity | Evidence | Correction |
|---|---|---|---|
| Failed controller replacement reports prior detached registry attached | Medium truthfulness | First attachment succeeds; replacement `service.attach` raises; runner is unavailable but `controller_attached` remains true for the prior registry | Clear previous identity when detaching/replacing; no stale attachment after failed startup |
| Detach error skips original session cleanup | High lifecycle | Injected `detach_controller` RuntimeError occurs before `_close_interactive_session` enters its cleanup body; original session `close` receives zero calls | Fence workflow admission while ensuring original session and observer cleanup still run if workflow detach fails |
| Failed detach retains facade admission flags | High lifecycle | Injected `service.detach` failure leaves both `runner_attached` and `controller_attached` true | Clear/fence attachment state before the potentially failing component call, and retain a truthful error state |

Root was notified before bounded production corrections. These tests inject service/session failures to assess integration cleanup and truthfulness; they are not evidence that a working engine executes or completes goals. The original HTTP authority checks pass within the observed 21-denial scope. Engine-level registry/approval/scope behavior remains NOT TESTED. The eighteen sealed planning cases remain unchanged and unexecuted.
