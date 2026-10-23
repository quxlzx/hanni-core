# M3 independent regression review, cycle 2

**FAIL: one existing Laya unauthorized-response test fails in two full runs.** The MCP controller/security cases and the previously failing launcher/navigation tests pass. Native GUI review remains held; no visual score or final backend acceptance is claimed.

The coordinator's bounded cleanup repair makes DashboardServer close safely before MCP Hub construction. The expected navigation contract now includes the authorized new MCP route. The existing three focused failures pass **3/3 in 1.751 seconds** (`data/hanni-mcp-hub-review/m3-cycle-2-focused.xml`).

## Full-suite results

| Run | Actual result | Duration | Evidence |
|---|---|---|---|
| Frozen repaired candidate | 962 passed, 1 failed, 2 skipped, 17 subtests passed | 124.712 s | data/hanni-mcp-hub-review/m3-cycle-2-full-pytest.xml |
| Unchanged focused Laya test between full runs | 1 passed | 0.705 s | data/hanni-mcp-hub-review/m3-cycle-2-laya-focused.xml |
| Full retry, with no source/assertion edits | 962 passed, 1 failed, 2 skipped, 17 subtests passed | 124.364 s | data/hanni-mcp-hub-review/m3-cycle-2-full-retry-pytest.xml |

Both full JUnit reports have 982 entries, one failure, two skips and zero errors. The 13 independent original-controller/security cases pass in both full runs. Candidate source/build provenance is retained in the 183-file manifest `data/hanni-mcp-hub-review/m3-cycle-2-source-sha256.json`.

## Repeated failure

`tests/unit/test_laya_shadow.py::ShadowContractTests::test_server_is_read_only_and_never_returns_prediction`

At line 52 the test sends an unauthorized POST to the isolated shadow HTTP service and expects `HTTPError`. Both full runs instead raise `ConnectionAbortedError: [WinError 10053]` at Python `socket.py:720` while reading the response. Earlier authorized assertions succeed, including the response's shadow-only contract and no prediction disclosure.

The Laya implementation and this test are unchanged by the MCP work. Read-only inspection found its unauthorized `do_POST` path sends 401 and returns without consuming the request body. Closing with unread request bytes is a plausible connection-cleanup cause; the full traces establish the failure but do not alone prove which Windows component aborts the socket. The focused test's pass is insufficient to override two failing full runs.

The coordinator will preserve the unauthorized 401 authority and original assertions while considering a bounded rejected-body cleanup repair. Further blind full retries are held until that repair and focused proof. The verifier has not edited application code or weakened/skipped this test.

## Artifact identifiers

| Artifact | SHA-256 |
|---|---|
| Repaired src/hanni/dashboard/server.py | cbab1f391de01e2fd6473654625a0f7980d74132a7bdbb6400458d608288b5eb |
| Native thin-wrapper executable | 9bf90dc1438e1776369f668117d88c2a5f76a33fc6f796c4d9f41a8a7e586263 |
| app.js | e90c54aecec3f4de085727ddb62dc2b36da512160098381c36ceee487cb4d8c7 |
| style.css | 56239e48e73c565b17bbbf815cbea8dd0110a727be102b72bff173a6f8de7c00 |

The prior failed cycle is [m3-cycle-1.md](m3-cycle-1.md). Dynamic execution observations from that report remain passing and have been repeated here, but the required full-regression gate is still **FAIL**. Configured-model inference and native screenshot acceptance remain pending.
