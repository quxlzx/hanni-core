# Connect an MCP server in HANNI OS

Open **Settings → Integrations → MCP Hub**. Add a server, review its exact executable and arguments or HTTP endpoint, then choose **Test & Discover** and approve that connection. Saving or importing settings does not connect anything. Discovery retrieves definitions without calling tools.

Select a server to inspect original tool descriptions, required and optional parameters, raw input/output JSON Schema, annotations and definition versions. Tools start disabled. Select only the tools you intend to use, choose a conservative classification and approve their current definitions. A changed definition requires another review. Disable, disconnect or remove a server to remove its executable adapters from HANNI's registry immediately; unrelated capabilities are retained.

When the assistant is running, approved connected tools enter its existing capability registry without restarting the model. The original router retrieves a relevant subset for each turn. The default assistant policy exposes read-only tools. Write, destructive and unknown capabilities retain the original permission and execution-confirmation requirements: approving a definition does not confirm an individual execution. The Hub reports whether the original controller is attached and explains its current policy.

This phase preserves the existing observe-first policy: normal model conversations do not advertise imported write/destructive/unknown tools or provide an execution-confirmation/resume dialog. Trusted backend callers can submit a confirmed `ToolRequest` on the attached original registry, subject to the same profile and stop guards. The separate standalone `hanni tool` CLI builds a fresh registry and does not connect Hub servers; it is not an imported-tool launcher. Registry availability and model exposure are distinct.

## Local stdio

Use an already installed executable. Enter one executable path and a JSON array of literal arguments, for example `python` and `["C:\\MyMcpServer\\server.py"]`. Choose its working directory if needed. Arguments are not shell-split. Commands that download packages are not installed by the Hub; `npx` must use `--no-install`, and `uvx` must use `--offline`. Set up packages separately before adding them. Inspect every command before authorizing launch.

Only a restricted baseline environment is inherited. To supply another variable, use a reference map such as `{"SERVICE_API_TOKEN":"MY_EXISTING_SERVICE_TOKEN"}`. This identifies an existing environment variable; it does not save its value. Restart the assistant after changing its parent environment.

## Streamable HTTP

Enter a public HTTPS endpoint, then choose no authentication, an existing bearer environment-variable name, or an existing Windows secure credential reference. Credential references use the service `HANNI.MCP.v1`; values stay in the local credential store/environment and are never exported. Automatic OAuth/browser login is not provided.

For a server you run on this computer, explicitly authorize literal loopback HTTP with a port of at least 1024, such as `http://127.0.0.1:8008/mcp/`. Private/reserved/link-local/metadata destinations, credential-bearing URLs and redirects are rejected. Remote DNS addresses are validated and pinned while TLS still checks the original hostname. System proxy settings are not inherited.

## Import, export and restart

Import common `mcpServers` JSON with executable/argument settings or Streamable HTTP settings. Review the normalized preview and warnings before selecting entries to save. Plain environment values are not imported as credentials. Duplicate names reject the transaction; existing configurations are never overwritten. Export includes non-secret configuration and reference identifiers, not credential values or execution approvals. It atomically saves a JSON file under `data_dir/mcp/exports`; the Hub shows its location and a selectable JSON preview. This also works in the native application, whose browser-download permission remains disabled.

Settings, definition snapshots and exact-hash approvals are stored transactionally at `data_dir/mcp/hub.sqlite3`. Unsupported or corrupt storage fails closed without resetting the database. After restarting HANNI, configurations remain available but connections stay disconnected until an explicit reconnect. Disabled servers stay disabled. The automatic-connection preference is recorded for compatibility; this release deliberately never launches a saved server on startup.

Schemas are preserved rather than converted to a flat form. Definitions using unsupported validation constructs are shown as invalid and cannot be approved. Current limits: 32 servers, 256 tools per server, 64 KiB per definition, 2 MiB per discovery snapshot, 1 MiB per result, and 2–120 second configured timeouts. Binary content is not rendered or opened automatically; resource URLs are not fetched. Tool results remain untrusted data for the assistant.

## Local integration fixture

The repository's `tests/fixtures/mcp_hub_mock.py` uses the official SDK and exposes `mock.get_status`, `mock.echo` and `mock.create_record`, with paginated discovery. To run the stdio fixture through the Hub, choose the full path to `.venv\\Scripts\\python.exe`, and arguments containing the absolute fixture path, `--control`, an isolated JSON control file path, `--ledger` and an isolated JSONL ledger path. Use an empty JSON object for the control file. Approve only `mock.get_status` and `mock.echo` as read-only for normal assistant testing; `mock.create_record` demonstrates the separate execution-confirmation gate. These are test tools, not production service integrations.

Illustrative import files are in [examples/mcp](../examples/mcp). Replace the paths/endpoints with an installed server you trust before approving a connection.

Final result and exact supported scope: [verification](MCP_HUB_VERIFICATION.md). Implementation evidence and milestone status: [checkpoints](MCP_HUB_CHECKPOINTS.md) and [independent reviews](mcp-hub-reviews).

An opt-in [Hermes coordination and shared catalog](HERMES_INTEGRATION.md) now lives
in this Hub. Its common workflow registers mapped servers in HANNI and Hermes;
registration, discovery permission, exact definition review and execution approval
remain separate. The existing reserved/private network policy and unrelated Hub
entries are preserved. Gateway activation and physical voice acceptance are pending.
