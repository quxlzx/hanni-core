# Independent MCP Hub review harnesses

These scripts are verification-only. They do not implement application features.

`session_probe.py` runs the actual original `McpHost.route` and `McpToolSession`
with a deterministic model choice. It refuses a missing imported tool in the
original menu and does not patch host calls, registry execution or permissions.
The surrounding test must use a genuine local SDK mock server and separately
assert its call ledger and original HANNI audit. This is repeatable controller
layer proof, not a claim of configured local-model inference.

`hub_fixture.py` attaches the actual original CLI controller registry to the
isolated dashboard. It empties only the fixture's Google vault and marks voice
inactive. `adversarial_server.py` wraps the reusable actual SDK server to record
only booleans for two synthetic environment variables, never their values.

`check_browser.py` uses headless Edge and the actual local Hub management
API/store/registry with an SDK stdio fixture. `check_native.py` uses the same
real boundaries through the actual portable Windows executable, capturing
framed Win32 images rather than browser screenshots. Neither mocks private
CRUD responses. Separate independent integration tests cover genuine
Streamable HTTP execution. Root must freeze application source, build the
frontend assets and release GUI ownership before captures. Synthetic service
content/telemetry are disclosed. Never connect arbitrary production MCP
commands/endpoints or read the user's credential vault for test convenience.

Use `check_native.py --supplemental-only` to capture compact dialog bottoms
and inspector content/actions at 1366x768 and 900x650, performing the interaction
sequence at the compact size. Each run retains actual results, frame metadata,
artifact hashes, SDK ledger and original audit. A harness pass is not a visual
score: the verifier must open and inspect the actual PNG pixels.

`../check_hanni_mcp_controller.py` independently starts the original text
launcher with the actual configured local model and isolated state. It proves
discovery without execution, hot registration, model-selected exact external
echo invocation, original private audit, live withdrawal and clean shutdown.
It uses no GUI, microphone or mocked model client.

The current Phase 2.6 rubric has five equally weighted two-point categories:
Typography/hierarchy, Layout/density, Spacing/consistency, Professional
appearance, Interaction polish. Overall must exceed 8.5 and AI-template score
must not exceed 2. Security/controller integration gates remain mandatory.
