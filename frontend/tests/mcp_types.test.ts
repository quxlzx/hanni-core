import test from "node:test";
import assert from "node:assert/strict";
import {
  approvalPayload,
  currentApproval,
  parseServerForm,
  schemaParameters,
  serverForm,
  toolState,
  type MCPClassification,
  type MCPForm,
  type MCPServer,
  type MCPTool,
} from "../src/mcp_types.ts";

const localForm = () => ({
  ...serverForm(),
  name: "Local review",
  command: "python",
});
const remoteForm = () => ({
  ...localForm(),
  transport: "streamable_http" as const,
  url: "https://service.example/mcp",
});
const tool = (changes: Partial<MCPTool> = {}): MCPTool => ({
  internal_id: "mcp.fixture.a1",
  original_name: "echo",
  description: "Original description",
  input_schema: {
    type: "object",
    properties: { text: { type: "string", description: "Original parameter" } },
    required: ["text"],
  },
  output_schema: null,
  annotations: null,
  metadata: null,
  valid: true,
  validation_errors: [],
  enabled: false,
  available: false,
  classification: "unknown",
  version: 1,
  definition_hash: "current-hash",
  approval: null,
  ...changes,
});
const server = (tools = [tool()]): MCPServer => ({
  id: "server-id",
  name: "Local review",
  transport: "stdio",
  config: parseServerForm(localForm()),
  config_hash: "config-hash",
  enabled: true,
  state: "connected",
  error: null,
  last_connected_at: null,
  last_discovery_at: null,
  definition_revision: 1,
  tools,
  discovered_count: tools.length,
  enabled_count: tools.filter((row) => row.enabled).length,
});

test("local arguments retain literal shell metacharacters and exact value boundaries", () => {
  const args = [
    "server.py",
    "C:\\my folder\\notes",
    "$(not-a-command)",
    "a; b",
    "`literal`",
    "",
  ];
  const parsed = parseServerForm({
    ...localForm(),
    args: JSON.stringify(args),
  });
  assert.deepEqual(parsed.args, args);
  assert.equal(parsed.command, "python");
  assert.equal(parsed.auto_connect, false);
});
test("argument JSON rejects shell strings, scalar values, nulls and oversized arrays", () => {
  for (const args of [
    '"server.py --flag"',
    "[12]",
    "[null]",
    "{}",
    JSON.stringify(Array(65).fill("a")),
    '["\\u0000"]',
  ])
    assert.throws(() => parseServerForm({ ...localForm(), args }), /Arguments/);
});
test("environment references preserve names and refuse raw values or invalid mappings", () => {
  assert.deepEqual(
    parseServerForm({
      ...localForm(),
      env_refs: '{"SERVICE_TOKEN":"OWNER_SERVICE_TOKEN"}',
    }).env_refs,
    { SERVICE_TOKEN: "OWNER_SERVICE_TOKEN" },
  );
  for (const env_refs of [
    "[]",
    "null",
    '{"TOKEN":123}',
    '{"TOKEN":"Bearer actual token"}',
    '{"bad-key":"KEY"}',
  ])
    assert.throws(
      () => parseServerForm({ ...localForm(), env_refs }),
      /reference/,
    );
});
test("transport switching removes irrelevant local command and environment settings", () => {
  const parsed = parseServerForm({
    ...remoteForm(),
    args: "invalid hidden JSON",
    env_refs: "also invalid",
  });
  assert.equal(parsed.command, null);
  assert.deepEqual(parsed.args, []);
  assert.deepEqual(parsed.env_refs, {});
  assert.equal(parsed.cwd, null);
});
test("insecure HTTP requires explicit literal loopback and nonstandard port", () => {
  for (const url of ["http://127.0.0.1:3030/mcp", "http://[::1]:3030/mcp"]) {
    assert.throws(() => parseServerForm({ ...remoteForm(), url }), /HTTPS/);
    assert.equal(
      parseServerForm({ ...remoteForm(), url, allow_local_http: true }).url,
      url,
    );
  }
  for (const url of [
    "http://localhost:3030/mcp",
    "http://192.0.2.30:3030/mcp",
    "http://192.0.2.29/mcp",
    "http://127.0.0.1/mcp",
    "http://127.0.0.1:80/mcp",
    "http://127.0.0.1:81/mcp",
    "http://127.0.0.1:500/mcp",
    "http://127.0.0.1:1023/mcp",
    "file:///etc/passwd",
  ])
    assert.throws(
      () => parseServerForm({ ...remoteForm(), url, allow_local_http: true }),
      /HTTPS/,
    );
});
test("URL credentials and fragments are refused and bearer references stay opaque", () => {
  for (const url of [
    ("https" + "://owner:token@service.example/mcp"),
    "https://service.example/mcp#token",
  ])
    assert.throws(
      () => parseServerForm({ ...remoteForm(), url }),
      /credentials/,
    );
  assert.throws(
    () => parseServerForm({ ...remoteForm(), auth_type: "bearer_env" }),
    /reference/,
  );
  assert.deepEqual(
    parseServerForm({
      ...remoteForm(),
      auth_type: "bearer_env",
      auth_reference: "MY_TOKEN",
    }).auth,
    { type: "bearer_env", reference: "MY_TOKEN" },
  );
});
test("configuration bounds, required fields and control characters are validated", () => {
  for (const timeout_seconds of [0, 1, 121, Number.NaN])
    assert.throws(
      () => parseServerForm({ ...localForm(), timeout_seconds }),
      /timeout/,
    );
  assert.throws(
    () => parseServerForm({ ...localForm(), name: "" }),
    /server name/,
  );
  assert.throws(
    () => parseServerForm({ ...localForm(), command: "" }),
    /executable/,
  );
  assert.throws(
    () => parseServerForm({ ...localForm(), command: "python\0" }),
    /control/,
  );
  assert.throws(
    () =>
      parseServerForm({
        ...localForm(),
        transport: "sse",
      } as unknown as MCPForm),
    /transport/,
  );
  assert.equal(
    parseServerForm({ ...localForm(), name: "n".repeat(100) }).name.length,
    100,
  );
  assert.throws(
    () => parseServerForm({ ...localForm(), name: "n".repeat(101) }),
    /100 characters/,
  );
});
test("existing settings round trip without inserting tokens or changing literal arguments", () => {
  const config = parseServerForm({
    ...localForm(),
    args: '["server.py","--keep-spaces"," a  b "]',
    cwd: "C:\\Project Files",
    env_refs: '{"TOKEN":"EXISTING_TOKEN"}',
    auto_connect: true,
    timeout_seconds: 120,
  });
  assert.deepEqual(parseServerForm(serverForm(config)), config);
});
test("schema inspection preserves the original schema and distinguishes actual required fields", () => {
  const schema = {
    type: "object",
    required: ["title"],
    properties: {
      title: { type: "string", description: "Original tool text" },
      count: { type: ["integer", "null"] },
      complex: { anyOf: [{ type: "string" }, { type: "object" }] },
      boolSchema: true,
    },
  };
  const original = structuredClone(schema);
  assert.deepEqual(schemaParameters(schema), [
    {
      name: "title",
      type: "string",
      required: true,
      description: "Original tool text",
    },
    { name: "count", type: "integer | null", required: false, description: "" },
    { name: "complex", type: "See schema", required: false, description: "" },
    {
      name: "boolSchema",
      type: "See schema",
      required: false,
      description: "",
    },
  ]);
  assert.deepEqual(schema, original);
  assert.deepEqual(schemaParameters({ anyOf: [{ type: "object" }] }), []);
  for (const invalid of [null, false, 42, "malformed", [], { properties: [] }])
    assert.deepEqual(schemaParameters(invalid), []);
});
test("unapproved, changed, invalid and disconnected tool states cannot imply availability", () => {
  assert.equal(toolState(tool()), "Awaiting approval");
  const approval = {
    definition_hash: "old-hash",
    classification: "read_only" as const,
    approved_at: "2026-10-09T12:00:00Z",
  };
  assert.equal(
    currentApproval(tool({ approval, version: 2, enabled: true })),
    false,
  );
  assert.equal(
    toolState(tool({ approval, version: 2, enabled: true })),
    "Review required",
  );
  assert.equal(
    toolState(tool({ valid: false, available: true })),
    "Invalid definition",
  );
  const current = { ...approval, definition_hash: "current-hash" };
  assert.equal(
    toolState(tool({ approval: current, enabled: true, available: false })),
    "Enabled, unavailable",
  );
  assert.equal(
    toolState(tool({ approval: current, enabled: false })),
    "Disabled",
  );
  assert.equal(
    toolState(
      tool({
        approval: current,
        enabled: true,
        available: true,
        classification: "read_only",
      }),
    ),
    "Available",
  );
});
test("registered tools display current model restrictions separately from availability", () => {
  const available = {
    approval: {
      definition_hash: "current-hash",
      classification: "unknown" as const,
      approved_at: "2026-10-09T12:00:00Z",
    },
    enabled: true,
    available: true,
  };
  for (const classification of ["unknown", "destructive"] as const) {
    assert.equal(
      toolState(tool({ ...available, classification }), {
        observe_first: true,
      }),
      "Policy restricted",
    );
    assert.equal(
      toolState(tool({ ...available, classification }), {
        observe_first: false,
      }),
      "Policy restricted",
    );
  }
  const write = tool({ ...available, classification: "write" });
  assert.equal(toolState(write), "Policy restricted");
  assert.equal(toolState(write, { observe_first: true }), "Policy restricted");
  assert.equal(
    toolState(write, { observe_first: false }),
    "Confirmation required",
  );
  assert.equal(write.available, true);
  assert.equal(
    toolState(tool({ ...available, classification: "read_only" }), {
      observe_first: true,
    }),
    "Available",
  );
  assert.equal(
    toolState(
      tool({ ...available, classification: "write", available: false }),
      { observe_first: false },
    ),
    "Enabled, unavailable",
  );
});
test("approvals bind exact original name/hash and explicit conservative classification", () => {
  const current = tool();
  assert.deepEqual(approvalPayload(server([current]), [current], "unknown"), {
    server_id: "server-id",
    tools: [
      {
        original_name: "echo",
        definition_hash: "current-hash",
        classification: "unknown",
      },
    ],
  });
  assert.throws(
    () =>
      approvalPayload(
        server(),
        [tool({ definition_hash: "stale-hash" })],
        "read_only",
      ),
    /current tools/,
  );
  assert.throws(
    () => approvalPayload(server(), [tool({ valid: false })], "read_only"),
    /current tools/,
  );
  assert.throws(
    () => approvalPayload(server(), [], "unknown"),
    /current tools/,
  );
  assert.throws(
    () =>
      approvalPayload(server(), [current], "auto_trusted" as MCPClassification),
    /explicit/,
  );
});
