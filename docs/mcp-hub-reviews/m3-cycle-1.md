# M3 independent execution and regression review, cycle 1

**FAIL: the full backend regression gate has three failures.** The 13 independent dynamic-controller/security cases pass, but that does not override the launcher regression. No native visual score is assigned: GUI review has not been released for this candidate.

Executed command: `.venv\Scripts\python.exe -m pytest -q --junitxml=data/hanni-mcp-hub-review/m3-full-pytest.xml`

JUnit records **982 entries, three failures, two skips and zero errors in 117.490 seconds**. Using the repository's established reporting convention, this is **960 passed, three failed, two skipped, 17 subtests passed**. Evidence is retained in `data/hanni-mcp-hub-review/m3-full-pytest.xml`. The complete hash manifest for 183 application source/frontend/build artifacts is `data/hanni-mcp-hub-review/m3-source-sha256.json`.

## Reproduced defects

| Finding | Severity | Evidence and implication | Owner / required fix |
|---|---|---|---|
| Dashboard cleanup assumes MCP Hub was constructed | High, backend acceptance blocker | `DashboardServer.__init__` binds the socket before assigning `self.mcp`. The standard HTTPServer constructor calls `server_close()` when a port is occupied. New cleanup unconditionally calls `self.mcp.close()`, raising AttributeError and masking WinError 10048. Existing available-port fallback therefore stops working. | Main/root: make cleanup safe before Hub construction, preserve original binding error and fallback; verify both existing launcher tests. |
| Existing exact navigation contract omits the authorized new MCP route | Expected test-contract update, not a runtime defect | Actual `workspace_contract` includes the new `mcp` screen. The existing test's exact expected list still has the original 16 screens. | Main/root: add the authorized route to the contract assertion. Do not change routing/benchmark outcomes. |

Failing original tests:

- `tests/unit/test_dashboard.py::test_launcher_reuses_model_and_finds_free_dashboard_port`
- `tests/unit/test_desktop_launcher_integration.py::test_foreground_launcher_opens_native_client_on_actual_port_and_preserves_cli`
- `tests/unit/test_dashboard_gateway.py::test_workspace_contract_only_discovers_existing_definitions`

The two launcher failures share the same initialization cleanup defect. This is a reproduced regression, not a host-software transient or a mocked-interface interpretation.

## Executed dynamic MCP evidence

All **13 independently authored cases** in `tests/integration/test_mcp_hub_controller_verifier.py` pass inside this full run. They use actual MCP SDK stdio/Streamable HTTP servers, the actual manager/store, the original registry and permission gates, original bounded retrieval and original model-facing tool loop. Only model selection is deterministic; this is not configured local-model inference proof. The fixture explicitly empties its Google vault and does not access production provider credentials.

Observed passing boundaries:

- Actual original model-facing session selects and calls `mock.echo` on both transports, returns the genuine server result to its model client and writes the original execution audit.
- Nested object/array, required, enum, nullable, additional-properties, local-reference, oneOf/allOf constraints are preserved in the original function menu. Invalid arguments are refused before tools/call; invalid structured output is refused.
- Changes to description, input schema, output schema, annotations and metadata revoke approval and cached executable handlers. Stale hashes cannot reapprove.
- Long names sharing a prefix and identical original names on different servers retain distinct bounded wire identities and call the exact external name. Removal preserves the other server's owned capabilities.
- Writes retain original execution confirmation/profile gates. Emergency stop removes availability and cancels connections; clearing it does not reconnect automatically. Explicit reconnect is required before a confirmed synthetic write can succeed.
- Genuine SDK tools/list_changed delivery changes the definition, triggers rediscovery and invalidates approval without a verifier-injected manager callback or tool execution.
- Both short and long synthetic authentication values reflected in tool definitions are kept out of public projections, saved SQLite definitions and model schemas. Safe rejection is accepted; original definitions are not silently rewritten to claim schema fidelity.

SDK fixture-only notification validation also received one real notification and changed list, with no call events. It confirms the verification fixture's protocol behavior independently of HANNI.

## Candidate provenance

| File | SHA-256 |
|---|---|
| src/hanni/mcp/manager.py | 6321de5035a7227b79852f8c90abe5ed7d9ea7eb1db907d3adbef54d0059e3c1 |
| src/hanni/mcp/adapter.py | 789e14181ebe199ec4ca227453897beb8d36bacb12861ee65809bda22eae8f95 |
| src/hanni/mcp/host.py | 945b5058b800e9d8e62e57886b1e9589f0eb08959fc3bcceb625bfc1af56c627 |
| src/hanni/mcp/session.py | 24a5a6516d5576105ae7c9a4e078ef2d7d2c174a1caeb82477a3d4bcee8a6fbc |
| src/hanni/tools/base.py | 0f92d8d2eee9a664d737f84593032fcaa7434b153f20ff1ac3bb8d0cd4373811 |
| src/hanni/dashboard/server.py | 43477fb9da5041f3da1fcf3547a75ecf78cabb78d091e02443cec31a161df80f |

After the failed-cycle checkpoint, the coordinator must repair cleanup, run the focused existing failures and repeat the full suite. Native four-size review, export-file interaction, exact five-category visual scoring and configured-model/controller proof remain pending and cannot be inferred from these backend tests.
