# Workflows browser cycle 2: failed completion assertion

The second actual headless browser cycle retained 24 passing checks and failed its 25th check, a compound read-workflow completion assertion. Evidence remains in `data/hanni-v3-review/browser-cycle-2/browser-review.json` and its debug browser image. No visual score was assigned.

The dedicated expiry browser context passed: its advanced client clock did not affect the main window. The genuine private-read outage disabled the captured plan confirmation, and a real plan approval in another window invalidated that captured review. The real backend received one `approve_plan` and one `start`, after the previously demonstrated identical-UUID submission retry.

The subsequent assertion required all of: completed workflow status, one verified step, `VERIFIED` acceptance evidence and unchanged original source bytes. Its failure did not record the individual values, so this cycle cannot establish which term failed. An isolated direct service reproduction using the same fixture and original pipeline returned completed status, one verified step, `VERIFIED` evidence and the expected LF source bytes. That separate diagnostic is not a browser pass and does not explain away the retained failure.

Root authorized adding those actual individual values and invocation evidence before the unchanged assertion in a fresh cycle. No production source or expected completion value changes. Remaining artifact, sensitive-write, rejection, lost-approval-response, cold-history and responsive checks were not reached in cycle 2.

The compiled app SHA256 remains `a9f09e6e3ea93e00b1d825f525e4f9fe5b86e2a64dc337e978908379756e71a2`; style SHA256 remains `76c1e4d5c353b93acf71f02cf40de00d11f03515aae2a3930e9f31d675333e4e`. Cycle-2 harness SHA256 is `9f05645ef60035f8177ab5ef4643218d1601916b3a798238bc9a5124f3a11f3a`. The artifact records a Python source manifest for frozen-source diagnosis; cycle 3 narrows that manifest to production modules by excluding `src/hanni/evals`, matching the stated scope.

All fixture limitations from [cycle 1](browser-cycle-1.md) still apply: actual private HTTP/store/host/registry and local file handlers, scripted two-pass model planning, synthetic cached telemetry, disconnected provider credentials, isolated owned files, fixture-only original file.write allowlist and no live model/provider/native/voice/node action. No JavaScript errors or nonlocal requests were recorded before failure. Debug browser images are not native visual acceptance.
