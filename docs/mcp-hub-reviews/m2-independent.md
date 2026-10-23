# M2 independent protocol and security review

Reviewed 2026-10-09 by the independent verifier. **PASS for the M2 connection, discovery, persistence and tested security boundaries.** Imported-tool execution, original-controller integration and native visual acceptance are not covered by this result and remain pending M3 onward.

## Executed evidence

Command: `.venv\Scripts\python.exe -m pytest -q tests/unit/test_mcp_hub.py tests/unit/test_mcp_hub_api.py tests/integration/test_mcp_hub_verifier.py --junitxml=data/hanni-mcp-hub-review/m2-independent-pytest.xml`

Result: **49 passed, zero failures, zero errors, zero skips in 11.962 seconds**. This contains 29 implementation tests, 9 dashboard API tests and 11 independently authored parametrized adversarial tests. The machine-readable report is in the ignored review data directory.

The independent tests use real MCP SDK stdio and Streamable HTTP transports, actual SQLite stores and actual authenticated Hub APIs. The local mock servers expose synthetic status/echo/create-record data. No production assistant, model, microphone, provider account, SSH session or remote machine action was started. DNS destination checks use an explicitly injected resolver; they make no external DNS request.

| Boundary | Actual independent observation |
|---|---|
| Discovery approval | Adding a stdio configuration creates no subprocess. Connecting without owner approval raises before launch. Approved discovery logs only list events, no tools/call. |
| Child environment | A synthetic unrelated parent secret is absent from the actual SDK child; an explicitly referenced synthetic variable is present. Secret values are absent from snapshot/export. |
| HTTP authentication | The actual SDK HTTP server rejects an incorrect bearer value. HANNI reports authentication_required. Updating the injected environment reference and reconnecting succeeds without persisting or exporting the credential. |
| Redirect/auth isolation | A real 307 endpoint points to a separate local HTTP listener. HANNI rejects the redirect; the target records zero requests and therefore receives no Authorization header. |
| DNS destinations | Public hostnames resolving to loopback IPv4/IPv6, metadata/link-local, private IPv4 or mapped loopback IPv6 are rejected. |
| Future database version | An actual SQLite database with user_version 999 is refused. The original file SHA-256, version and user content remain unchanged. |
| Schema reference safety | Dangling local references and a self-reference that validates the same instance without descending are rejected. |

The implementation/API suite additionally exercises paginated definitions, preservation of schemas/metadata, disabled persistence, import preview without launch, changed-definition approval invalidation, standard destination gates, explicit command-runner constraints and management API token/confirmation requirements. These suite results are execution evidence, not a claim that every possible hostile schema or network condition has been exhausted.

## Reviewed artifact hashes

| File | SHA-256 |
|---|---|
| src/hanni/mcp/manager.py | 79e930fdac1d728d968301837b518194cb31b698fe9851dabfd9f76dd2c40335 |
| src/hanni/mcp/security.py | 8a4cda2695af62f07ca8db9d5504eebd11df2551799ae84cacf9525ad6facc24 |
| src/hanni/mcp/store.py | 6c387657a58e793d1b9624dba4f278bfe8ec1a68ce8393b7eb5f6e523a7b1b84 |
| src/hanni/mcp/transport.py | 1485888ffe165abcd7c20b09ef9cd1ac445d48f7a62028fddb2d8ea8dfa93c45 |
| tests/fixtures/mcp_hub_mock.py | 633fb54ab1b1a20047d2244dd9517fd01224fa99078898b3052f74d40bcaa79f |
| src/hanni/dashboard/mcp_hub.py | 5ec36892b9c1380f2883e02ce0aeca1762a3ef6fda00e5ebdddecfb5433111f6 |

## Remaining acceptance

M2 intentionally has no registry execution adapters. It cannot satisfy the user requirement to invoke imported tools through the original registry, retrieval/router, model-facing MCP session and controller. M3 must prove that route with original permission checks, full runtime input/output schema validation, audit records, changed approval revocation and stale-handler safety. Native review will use the Phase 2.6 five-category rubric, each category worth two points. No visual grade is assigned to this source/test-only review.
