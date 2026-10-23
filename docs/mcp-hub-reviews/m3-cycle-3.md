# M3 independent backend acceptance, cycle 3

**PASS: the complete frozen backend regression suite and independent imported-tool execution/security checks pass.** Native visual/frontend acceptance remains a separate pending gate; this report assigns no visual score.

Executed by the verifier: `.venv\Scripts\python.exe -m pytest -q --junitxml=data/hanni-mcp-hub-review/m3-cycle-3-full-pytest.xml`

Result: **964 passed, two skipped, 17 subtests passed in 120.654 seconds**. JUnit contains 983 entries, zero failures and zero errors. The two existing skips remain the baseline historical-artifact/PATH conditions; no MCP or regression test was skipped to obtain acceptance.

The coordinator's focused Laya/dashboard/launcher/gateway checks, including a meaningful new rejected-body timeout/no-model-execution case, passed **51/51 in 12.240 seconds** (`m3-cycle-3-focused.xml`). The full suite above independently repeats those tests and all 13 independently authored controller/security cases.

## Repairs and retained evidence

The occupied-port cleanup regression and authorized new-route assertion were fixed after [cycle 1](m3-cycle-1.md). [Cycle 2](m3-cycle-2.md) preserved two full failures of the unchanged Laya unauthorized POST response, despite its focused pass. The coordinator then added bounded rejected-body cleanup for unauthorized/unknown-path POST requests, retaining the original denial and no-evaluation behavior. This cycle passes without assertion weakening, test exclusion or benchmark changes.

Source and build hashes for 183 files are retained in `data/hanni-mcp-hub-review/m3-cycle-3-source-sha256.json`. Key identifiers:

| Artifact | SHA-256 |
|---|---|
| src/hanni/laya/server.py | d3cf85a8740e421555446ea09e7e46c0c145b312a21b7e512f91b98eaf5c9222 |
| src/hanni/dashboard/server.py | cbab1f391de01e2fd6473654625a0f7980d74132a7bdbb6400458d608288b5eb |
| src/hanni/mcp/manager.py | 6321de5035a7227b79852f8c90abe5ed7d9ea7eb1db907d3adbef54d0059e3c1 |
| src/hanni/mcp/adapter.py | 789e14181ebe199ec4ca227453897beb8d36bacb12861ee65809bda22eae8f95 |
| Native thin-wrapper executable | 9bf90dc1438e1776369f668117d88c2a5f76a33fc6f796c4d9f41a8a7e586263 |
| app.js | 5e7129a6bc1f6bcc924fc8ac48c9bcf39a0777bc439327b364b6616f890a68fe |
| style.css | 56239e48e73c565b17bbbf815cbea8dd0110a727be102b72bff173a6f8de7c00 |

## Executed integration scope

All 13 independent cases pass: real stdio and Streamable HTTP tools/call through the original registry/retrieval/model-facing session; exact external-name/audit behavior; complete nested schema/menu preservation and runtime validation; five classes of changed-definition approval revocation; stale-handler/removal safety; collision-safe long/cross-server names; original write confirmation/profile/Safe Mode authority; genuine SDK tool-list notifications; and short/long credential-reflection rejection in public projections, saved definitions and model menus.

These repeatable cases use an explicitly deterministic model choice, actual protocol/store/registry execution and an empty fixture Google vault. They do not fabricate configured local-model inference, provider connectivity, microphone capture or remote node actions. The independently inspected coordinator-run configured-model proof is recorded separately in [m5-controller-evidence.md](m5-controller-evidence.md).

Backend M3 acceptance is now complete. Native four-size images, actual UI export files, interaction review and exact five-category visual/AI scores must still be verified against the frozen application before final Phase 2.6 acceptance.
