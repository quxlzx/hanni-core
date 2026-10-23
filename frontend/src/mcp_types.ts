export type MCPClassification =
  "read_only" | "write" | "destructive" | "unknown";
export type MCPConfig = {
  name: string;
  transport: "stdio" | "streamable_http";
  command: string | null;
  args: string[];
  cwd: string | null;
  env_refs: Record<string, string>;
  url: string | null;
  auth: {
    type: "none" | "bearer_env" | "bearer_secret";
    reference: string | null;
  };
  allow_local_http: boolean;
  auto_connect: boolean;
  timeout_seconds: number;
};
export type MCPTool = {
  internal_id: string;
  original_name: string;
  description: string;
  input_schema: unknown;
  output_schema: unknown | null;
  annotations: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  valid: boolean;
  validation_errors: string[];
  enabled: boolean;
  available: boolean;
  classification: MCPClassification;
  version: number;
  definition_hash: string;
  approval: {
    definition_hash: string;
    classification: MCPClassification;
    approved_at: string;
  } | null;
};
export type MCPServer = {
  id: string;
  name: string;
  transport: MCPConfig["transport"];
  config: MCPConfig;
  config_hash: string;
  enabled: boolean;
  state:
    | "connected"
    | "connecting"
    | "authentication_required"
    | "disconnected"
    | "failed"
    | "disabled";
  error: string | null;
  last_connected_at: string | null;
  last_discovery_at: string | null;
  definition_revision: number;
  tools: MCPTool[];
  discovered_count: number;
  enabled_count: number;
};
export type MCPData = {
  available: boolean;
  servers: MCPServer[];
  revision: number;
  reason?: string;
  controller_attached?: boolean;
  model_tools_enabled?: boolean;
  observe_first?: boolean;
  policy_reason?: string;
};
export type MCPImportPreview = { candidates: MCPConfig[]; warnings: string[] };
export type MCPExport = {
  configuration: Record<string, unknown>;
  file: { name: string; path: string };
};
export type MCPForm = {
  name: string;
  transport: MCPConfig["transport"];
  command: string;
  args: string;
  cwd: string;
  env_refs: string;
  url: string;
  auth_type: MCPConfig["auth"]["type"];
  auth_reference: string;
  allow_local_http: boolean;
  auto_connect: boolean;
  timeout_seconds: number;
};
export const classificationLabels: Record<MCPClassification, string> = {
  read_only: "Read-only",
  write: "Write",
  destructive: "Destructive",
  unknown: "Unknown",
};
export function serverForm(config?: MCPConfig): MCPForm {
  return {
    name: config?.name || "",
    transport: config?.transport || "stdio",
    command: config?.command || "",
    args: JSON.stringify(config?.args || [], null, 2),
    cwd: config?.cwd || "",
    env_refs: JSON.stringify(config?.env_refs || {}, null, 2),
    url: config?.url || "",
    auth_type: config?.auth.type || "none",
    auth_reference: config?.auth.reference || "",
    allow_local_http: config?.allow_local_http || false,
    auto_connect: config?.auto_connect || false,
    timeout_seconds: config?.timeout_seconds || 20,
  };
}
export function parseServerForm(form: MCPForm): MCPConfig {
  if (!["stdio", "streamable_http"].includes(form.transport))
    throw new Error("Choose stdio or Streamable HTTP transport.");
  if (!["none", "bearer_env", "bearer_secret"].includes(form.auth_type))
    throw new Error("Choose a supported authentication reference.");
  if (!form.name.trim()) throw new Error("Enter a server name.");
  if (form.name.length > 100)
    throw new Error("Server names must be 100 characters or fewer.");
  if (
    [form.name, form.command, form.cwd, form.url, form.auth_reference].some(
      (value) => /[\u0000-\u001f]/.test(value),
    )
  )
    throw new Error("Server settings cannot contain control characters.");
  if (
    !Number.isFinite(form.timeout_seconds) ||
    form.timeout_seconds < 2 ||
    form.timeout_seconds > 120
  )
    throw new Error("Connection timeout must be between 2 and 120 seconds.");
  let args: unknown, refs: unknown;
  try {
    args = form.transport === "stdio" ? JSON.parse(form.args || "[]") : [];
  } catch {
    throw new Error("Arguments must be a JSON array of strings.");
  }
  if (
    !Array.isArray(args) ||
    args.length > 64 ||
    args.some(
      (arg) =>
        typeof arg !== "string" ||
        arg.length > 8192 ||
        /[\u0000\r\n]/.test(arg),
    )
  )
    throw new Error(
      "Arguments must contain at most 64 strings, each up to 8,192 characters.",
    );
  try {
    refs = form.transport === "stdio" ? JSON.parse(form.env_refs || "{}") : {};
  } catch {
    throw new Error("Environment references must be a JSON object.");
  }
  if (
    !refs ||
    typeof refs !== "object" ||
    Array.isArray(refs) ||
    Object.keys(refs).length > 32 ||
    Object.entries(refs).some(
      ([key, value]) =>
        !/^[A-Za-z_][A-Za-z0-9_]{0,127}$/.test(key) ||
        typeof value !== "string" ||
        !/^[A-Za-z_][A-Za-z0-9_]{0,127}$/.test(value),
    )
  )
    throw new Error(
      "Use environment variable names as keys and existing variable names as references, up to 32 entries.",
    );
  if (form.transport === "stdio" && !form.command.trim())
    throw new Error("Enter the executable to launch.");
  if (form.transport === "streamable_http") {
    let url: URL;
    try {
      url = new URL(form.url);
    } catch {
      throw new Error("Enter a valid MCP endpoint URL.");
    }
    if (url.username || url.password || url.hash || url.search)
      throw new Error(
        "URLs cannot contain credentials, query strings or fragments. Use an authentication reference.",
      );
    const loopback = ["127.0.0.1", "[::1]"].includes(url.hostname);
    if (
      url.protocol !== "https:" &&
      !(
        form.allow_local_http &&
        url.protocol === "http:" &&
        loopback &&
        url.port &&
        Number(url.port) >= 1024
      )
    )
      throw new Error(
        "Use HTTPS, or explicitly allow HTTP on a literal loopback address with a nonstandard port.",
      );
    if (form.auth_type !== "none" && !form.auth_reference.trim())
      throw new Error("Enter an existing authentication reference.");
    if (
      form.auth_type === "bearer_env" &&
      !/^[A-Za-z_][A-Za-z0-9_]{0,127}$/.test(form.auth_reference.trim())
    )
      throw new Error(
        "Bearer environment authentication requires an existing variable name.",
      );
  }
  return {
    name: form.name.trim(),
    transport: form.transport,
    command: form.transport === "stdio" ? form.command.trim() : null,
    args: form.transport === "stdio" ? (args as string[]) : [],
    cwd: form.transport === "stdio" ? form.cwd.trim() || null : null,
    env_refs:
      form.transport === "stdio" ? (refs as Record<string, string>) : {},
    url: form.transport === "streamable_http" ? form.url.trim() : null,
    auth:
      form.transport === "streamable_http"
        ? {
            type: form.auth_type,
            reference:
              form.auth_type === "none" ? null : form.auth_reference.trim(),
          }
        : { type: "none", reference: null },
    allow_local_http:
      form.transport === "streamable_http" && form.allow_local_http,
    auto_connect: form.auto_connect,
    timeout_seconds: form.timeout_seconds,
  };
}
export function currentApproval(tool: MCPTool) {
  return Boolean(
    tool.approval && tool.approval.definition_hash === tool.definition_hash,
  );
}
export function toolState(
  tool: MCPTool,
  policy?: Pick<MCPData, "observe_first">,
) {
  if (!tool.valid) return "Invalid definition";
  if (!currentApproval(tool))
    return tool.version > 1 ? "Review required" : "Awaiting approval";
  if (!tool.enabled) return "Disabled";
  if (!tool.available) return "Enabled, unavailable";
  if (
    tool.classification === "destructive" ||
    tool.classification === "unknown"
  )
    return "Policy restricted";
  if (tool.classification === "write")
    return policy?.observe_first === false
      ? "Confirmation required"
      : "Policy restricted";
  return "Available";
}
export function schemaParameters(schema: unknown) {
  if (!schema || typeof schema !== "object" || Array.isArray(schema)) return [];
  const definition = schema as Record<string, unknown>;
  const properties = definition.properties;
  if (
    !properties ||
    typeof properties !== "object" ||
    Array.isArray(properties)
  )
    return [];
  const rawRequired = definition.required;
  const required = Array.isArray(rawRequired) ? rawRequired : [];
  return Object.entries(properties).map(([name, value]) => {
    const field =
      value && typeof value === "object" && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : {};
    return {
      name,
      required: required.includes(name),
      type:
        typeof field.type === "string"
          ? field.type
          : Array.isArray(field.type)
            ? field.type.join(" | ")
            : "See schema",
      description:
        typeof field.description === "string" ? field.description : "",
    };
  });
}
export function approvalPayload(
  server: MCPServer,
  tools: MCPTool[],
  classification: MCPClassification,
) {
  if (!Object.hasOwn(classificationLabels, classification))
    throw new Error("Choose an explicit permission classification.");
  if (
    !tools.length ||
    tools.some(
      (tool) =>
        !tool.valid ||
        !server.tools.some(
          (current) =>
            current.original_name === tool.original_name &&
            current.definition_hash === tool.definition_hash,
        ),
    )
  )
    throw new Error(
      "Refresh definitions and select valid current tools before approving.",
    );
  return {
    server_id: server.id,
    tools: tools.map((tool) => ({
      original_name: tool.original_name,
      definition_hash: tool.definition_hash,
      classification,
    })),
  };
}
