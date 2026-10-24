import { useRef, useState, type FormEvent } from "react";
import { request } from "./api";
import { usePrivateResource } from "./feature_types";
import { OfficeSetup } from "./office_setup";
import {
  approvalPayload,
  classificationLabels,
  currentApproval,
  parseServerForm,
  schemaParameters,
  serverForm,
  toolState,
  type MCPClassification,
  type MCPConfig,
  type MCPData,
  type MCPForm,
  type MCPImportPreview,
  type MCPServer,
  type MCPTool,
} from "./mcp_types";
import "./mcp_panel.css";

type Editor = { form: MCPForm; original?: MCPServer };
export function MCPPanel({ token }: { token: string }) {
  const resource = usePrivateResource<MCPData>("/api/mcp", token, 3000);
  const [editor, setEditor] = useState<Editor | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [importing, setImporting] = useState(false),
    [document, setDocument] = useState(""),
    [preview, setPreview] = useState<MCPImportPreview | null>(null);
  const [remove, setRemove] = useState<string | null>(null);
  const [officeSetup, setOfficeSetup] = useState(false);
  const [notice, setNotice] = useState("");
  const [classes, setClasses] = useState<
    Record<string, MCPClassification | "">
  >({});
  const lock = useRef(false),
    pending = useRef<{ signature: string; id: string } | null>(null);
  const data = resource.data;
  const disabled =
    busy || !token || !data?.available || Boolean(resource.error);
  async function call<T>(operation: string, payload: unknown): Promise<T> {
    const signature = JSON.stringify({ operation, data: payload, token });
    const id =
      pending.current?.signature === signature
        ? pending.current.id
        : crypto.randomUUID();
    pending.current = { signature, id };
    const result = await request<T>("/api/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Hanni-Token": token },
      body: JSON.stringify({ id, operation, data: payload, confirmed: true }),
      signal: AbortSignal.timeout(135000),
    });
    pending.current = null;
    return result;
  }
  async function act(run: () => Promise<void>) {
    if (disabled || lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await run();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The MCP request could not be confirmed. Retry the same action.",
      );
    } finally {
      lock.current = false;
      setBusy(false);
      resource.refresh();
    }
  }
  function setField<K extends keyof MCPForm>(key: K, value: MCPForm[K]) {
    setEditor((current) =>
      current ? { ...current, form: { ...current.form, [key]: value } } : null,
    );
  }
  async function connect(server: MCPServer) {
    await call("test_discover", {
      server_id: server.id,
      expected_config_hash: server.config_hash,
      approved: true,
    });
  }
  function save(event: FormEvent, connectNow: boolean) {
    event.preventDefault();
    if (!editor) return;
    let config: MCPConfig;
    try {
      config = parseServerForm(editor.form);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Check the server settings.",
      );
      return;
    }
    const original = editor.original;
    void act(async () => {
      const result = await call<MCPServer | MCPData>(
        original ? "update" : "add",
        original
          ? {
              server_id: original.id,
              expected_config_hash: original.config_hash,
              config,
            }
          : { config },
      );
      const saved =
        "servers" in result
          ? result.servers.find((item) => item.id === original?.id)
          : result;
      setEditor(null);
      if (connectNow && saved) await connect(saved);
    });
  }
  const toolKey = (server: MCPServer, tool: MCPTool) =>
    `${server.id}:${tool.definition_hash}`;
  function enableTool(server: MCPServer, tool: MCPTool) {
    const classification =
      classes[toolKey(server, tool)] ||
      (tool.classification !== "unknown" ? tool.classification : "");
    if (!classification) {
      setError("Choose a tool permission before enabling it.");
      return;
    }
    void act(async () => {
      await call(
        "approve_tools",
        approvalPayload(server, [tool], classification),
      );
    });
  }
  return (
    <section className="hc-panel-content hc-mcp-panel" aria-busy={busy}>
      <header>
        <h1>MCP</h1>
        <div className="hc-mcp-actions">
          <button
            disabled={disabled}
            onClick={() => {
              setOfficeSetup(true);
              setEditor(null);
              setImporting(false);
              setError("");
              setNotice("");
            }}
          >
            Microsoft Office
          </button>
          <button
            disabled={disabled}
            onClick={() => {
              setEditor({ form: serverForm() });
              setOfficeSetup(false);
              setImporting(false);
              setError("");
            }}
          >
            Add server
          </button>
          <button
            disabled={disabled}
            onClick={() => {
              setImporting(true);
              setOfficeSetup(false);
              setEditor(null);
              setError("");
            }}
          >
            Import JSON
          </button>
          <button onClick={resource.refresh} disabled={busy}>
            Refresh
          </button>
        </div>
      </header>
      <p>Connect tool servers and choose which tools HANNI can use.</p>
      {notice && <p className="hc-mcp-notice" role="status">{notice}</p>}
      {(error || resource.error || data?.reason) && (
        <p className="hc-error-text hc-mcp-notice" role="alert">
          {error || resource.error || data?.reason}
        </p>
      )}
      {!data && !resource.error && <p role="status">Reading connections…</p>}
      {data?.policy_reason && (
        <p className="hc-mcp-policy">{data.policy_reason}</p>
      )}
      {officeSetup && (
        <OfficeSetup
          token={token}
          disabled={disabled}
          busy={busy}
          onCancel={() => setOfficeSetup(false)}
          onCloudSetup={(settings) => {
            void act(async () => {
              await call("office_cloud_setup", settings);
              setOfficeSetup(false);
              setNotice("Microsoft 365 Work IQ server connected. Review and enable tools below. Account access is checked on your first query.");
            });
          }}
          onSetup={(settings) => {
            void act(async () => {
              const result = await call<{ folder: string }>("office_setup", settings);
              setOfficeSetup(false);
              setNotice(`Office files connected: ${result.folder}. Review the tools below to enable creating and editing.`);
            });
          }}
        />
      )}
      {editor && (
        <form className="hc-mcp-editor" onSubmit={(event) => save(event, true)}>
          <h2>
            {editor.original
              ? `Edit ${editor.original.name}`
              : "Add MCP server"}
          </h2>
          <fieldset disabled={disabled}>
            <label>
              Server name
              <input
                value={editor.form.name}
                onChange={(event) => setField("name", event.target.value)}
                maxLength={100}
                required
                placeholder="My tools"
                autoFocus
              />
            </label>
            <label>
              Connection type
              <select
                value={editor.form.transport}
                onChange={(event) =>
                  setField(
                    "transport",
                    event.target.value as MCPForm["transport"],
                  )
                }
              >
                <option value="stdio">Local command (stdio)</option>
                <option value="streamable_http">
                  Remote URL (Streamable HTTP)
                </option>
              </select>
            </label>
            {editor.form.transport === "stdio" ? (
              <>
                <label>
                  Executable
                  <input
                    value={editor.form.command}
                    onChange={(event) =>
                      setField("command", event.target.value)
                    }
                    placeholder="node, python, or an executable path"
                    required
                    spellCheck={false}
                  />
                </label>
                <label>
                  Arguments (JSON array)
                  <textarea
                    rows={3}
                    value={editor.form.args}
                    onChange={(event) => setField("args", event.target.value)}
                    placeholder={'["path/to/server.js"]'}
                    spellCheck={false}
                  />
                </label>
                <p className="hc-mcp-hint">
                  Use an installed executable. For npx, include --no-install and
                  install the server package beforehand.
                </p>
                <label>
                  Working directory <span>(optional)</span>
                  <input
                    value={editor.form.cwd}
                    onChange={(event) => setField("cwd", event.target.value)}
                    spellCheck={false}
                  />
                </label>
                <details>
                  <summary>Environment variable references</summary>
                  <label>
                    Environment mapping (JSON)
                    <textarea
                      rows={3}
                      value={editor.form.env_refs}
                      onChange={(event) =>
                        setField("env_refs", event.target.value)
                      }
                      placeholder={'{"API_KEY":"MY_API_KEY"}'}
                      spellCheck={false}
                    />
                  </label>
                  <p className="hc-mcp-hint">
                    Map the server’s variable names to environment variables set
                    before starting HANNI. Enter variable names, not secret
                    values.
                  </p>
                </details>
              </>
            ) : (
              <>
                <label>
                  MCP endpoint URL
                  <input
                    type="url"
                    value={editor.form.url}
                    onChange={(event) => setField("url", event.target.value)}
                    placeholder="https://your-server.example/mcp"
                    required
                    spellCheck={false}
                  />
                </label>
                <label>
                  Authentication
                  <select
                    value={editor.form.auth_type}
                    onChange={(event) =>
                      setField(
                        "auth_type",
                        event.target.value as MCPForm["auth_type"],
                      )
                    }
                  >
                    <option value="none">None</option>
                    <option value="bearer_env">
                      Bearer token from environment variable
                    </option>
                    <option value="bearer_secret">
                      Bearer token from credential store reference
                    </option>
                  </select>
                </label>
                {editor.form.auth_type !== "none" && (
                  <label>
                    {editor.form.auth_type === "bearer_env"
                      ? "Environment variable name"
                      : "Saved MCP credential reference"}
                    <input
                      value={editor.form.auth_reference}
                      onChange={(event) =>
                        setField("auth_reference", event.target.value)
                      }
                      required
                      autoComplete="off"
                      spellCheck={false}
                    />
                    <small>
                      Use an existing reference. Credentials stay out of server
                      configuration.
                    </small>
                  </label>
                )}
                <label className="hc-mcp-check">
                  <input
                    type="checkbox"
                    checked={editor.form.allow_local_http}
                    onChange={(event) =>
                      setField("allow_local_http", event.target.checked)
                    }
                  />
                  Allow HTTP on a literal loopback address, such as
                  127.0.0.1:8000
                </label>
              </>
            )}
            <label className="hc-mcp-check">
              <input
                type="checkbox"
                checked={editor.form.auto_connect}
                onChange={(event) =>
                  setField("auto_connect", event.target.checked)
                }
              />
              Reconnect when HANNI starts
            </label>
            <label className="hc-mcp-timeout">
              Connection timeout (seconds)
              <input
                type="number"
                min={2}
                max={120}
                value={editor.form.timeout_seconds}
                onChange={(event) =>
                  setField("timeout_seconds", Number(event.target.value))
                }
                required
              />
            </label>
          </fieldset>
          <div className="hc-mcp-actions">
            <button
              className="hc-mcp-primary"
              type="submit"
              disabled={disabled}
            >
              {busy ? "Saving…" : "Save and connect"}
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={(event) => {
                const form = event.currentTarget.form;
                if (form?.reportValidity()) save(event, false);
              }}
            >
              Save only
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setEditor(null)}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
      {importing && (
        <form
          className="hc-mcp-editor"
          onSubmit={(event) => {
            event.preventDefault();
            void act(async () => {
              setPreview(
                await call<MCPImportPreview>("import_preview", {
                  document: JSON.parse(document),
                }),
              );
            });
          }}
        >
          <h2>Import MCP configuration</h2>
          <label>
            Configuration JSON
            <textarea
              rows={7}
              value={document}
              onChange={(event) => {
                setDocument(event.target.value);
                setPreview(null);
              }}
              placeholder={
                '{"mcpServers":{"my-server":{"command":"node","args":["server.js"]}}}'
              }
              required
              spellCheck={false}
            />
          </label>
          {preview && (
            <div className="hc-mcp-preview">
              <p>
                {preview.candidates.length} server
                {preview.candidates.length === 1 ? "" : "s"} ready to import.
              </p>
              {preview.candidates.map((config) => (
                <p key={config.name}>
                  {config.name} ·{" "}
                  {config.transport === "stdio"
                    ? "Local command"
                    : "Remote URL"}
                </p>
              ))}
              {preview.warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          )}
          <div className="hc-mcp-actions">
            <button type="submit" disabled={disabled}>
              Preview import
            </button>
            {preview && preview.candidates.length > 0 && (
              <button
                type="button"
                className="hc-mcp-primary"
                disabled={disabled}
                onClick={() =>
                  void act(async () => {
                    await call("import", { configs: preview.candidates });
                    setPreview(null);
                    setDocument("");
                    setImporting(false);
                  })
                }
              >
                Import {preview.candidates.length} server
                {preview.candidates.length === 1 ? "" : "s"}
              </button>
            )}
            <button
              type="button"
              disabled={busy}
              onClick={() => setImporting(false)}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
      {data && !data.servers.length && !editor && !importing && !officeSetup && (
        <div className="hc-panel-empty">
          <h2>No MCP servers yet</h2>
          <p>
            Add a local command or remote URL, or import an mcpServers JSON
            configuration.
          </p>
          <button
            className="hc-mcp-primary"
            disabled={disabled}
            onClick={() => setEditor({ form: serverForm() })}
          >
            Add your first server
          </button>
        </div>
      )}
      <div className="hc-mcp-servers">
        {data?.servers.map((server) => (
          <section className="hc-mcp-server" key={server.id}>
            <header>
              <div>
                <h2>{server.name}</h2>
                <p>
                  {server.transport === "stdio"
                    ? "Local command"
                    : "Streamable HTTP"}{" "}
                  · {server.state.replaceAll("_", " ")} · {server.enabled_count}
                  /{server.discovered_count} tools enabled
                </p>
              </div>
            </header>
            <p className="hc-mcp-endpoint">
              {server.transport === "stdio"
                ? [server.config.command, ...server.config.args].join(" ")
                : server.config.url}
            </p>
            {server.error && (
              <p className="hc-error-text" role="status">
                {server.error}
              </p>
            )}
            <div className="hc-mcp-actions">
              {server.state === "connected" ? (
                <>
                  <button
                    disabled={disabled}
                    onClick={() =>
                      void act(async () => {
                        await call("disconnect", { server_id: server.id });
                      })
                    }
                  >
                    Disconnect
                  </button>
                  <button
                    disabled={disabled}
                    onClick={() =>
                      void act(async () => {
                        await call("refresh", { server_id: server.id });
                      })
                    }
                  >
                    Refresh tools
                  </button>
                </>
              ) : (
                <button
                  className="hc-mcp-primary"
                  disabled={disabled || server.state === "connecting"}
                  onClick={() =>
                    void act(async () => {
                      await connect(server);
                    })
                  }
                >
                  {server.state === "connecting" ? "Connecting…" : "Connect"}
                </button>
              )}
              <button
                disabled={disabled}
                onClick={() => {
                  setEditor({
                    original: server,
                    form: serverForm(server.config),
                  });
                  setImporting(false);
                  setOfficeSetup(false);
                  setError("");
                }}
              >
                Edit
              </button>
              <button disabled={disabled} onClick={() => setRemove(server.id)}>
                Remove
              </button>
            </div>
            {remove === server.id && (
              <div className="hc-mcp-remove">
                <p>Remove {server.name} and its saved tool approvals?</p>
                <button
                  disabled={disabled}
                  onClick={() =>
                    void act(async () => {
                      await call("remove", { server_id: server.id });
                      setRemove(null);
                    })
                  }
                >
                  Remove server
                </button>
                <button disabled={busy} onClick={() => setRemove(null)}>
                  Keep server
                </button>
              </div>
            )}
            {server.tools.length > 0 && (
              <details className="hc-mcp-tools" open>
                <summary>Tools ({server.tools.length})</summary>
                {server.tools.map((tool) => (
                  <div
                    className="hc-mcp-tool"
                    key={tool.internal_id + tool.definition_hash}
                  >
                    <div className="hc-mcp-tool-heading">
                      <h3>{tool.original_name}</h3>
                      <span>{toolState(tool, data)}</span>
                    </div>
                    <p>{tool.description}</p>
                    <details>
                      <summary>Parameters and schema</summary>
                      {schemaParameters(tool.input_schema).map((field) => (
                        <p key={field.name}>
                          <code>{field.name}</code> · {field.type}
                          {field.required ? " · required" : ""}
                          {field.description ? ` — ${field.description}` : ""}
                        </p>
                      ))}
                      <pre>{JSON.stringify(tool.input_schema, null, 2)}</pre>
                    </details>
                    {!tool.valid && (
                      <p className="hc-error-text">
                        {tool.validation_errors.join(" ")}
                      </p>
                    )}
                    <div className="hc-mcp-tool-controls">
                      {tool.enabled && currentApproval(tool) ? (
                        <button
                          disabled={disabled}
                          onClick={() =>
                            void act(async () => {
                              await call("disable_tools", {
                                server_id: server.id,
                                names: [tool.original_name],
                              });
                            })
                          }
                        >
                          Disable tool
                        </button>
                      ) : (
                        <>
                          <label>
                            Permission for {tool.original_name}
                            <select
                              value={
                                classes[toolKey(server, tool)] ??
                                (tool.classification !== "unknown"
                                  ? tool.classification
                                  : "")
                              }
                              onChange={(event) =>
                                setClasses((current) => ({
                                  ...current,
                                  [toolKey(server, tool)]: event.target
                                    .value as MCPClassification,
                                }))
                              }
                              disabled={disabled}
                            >
                              <option value="">Choose permission</option>
                              {Object.entries(classificationLabels).map(
                                ([value, label]) => (
                                  <option value={value} key={value}>
                                    {label}
                                  </option>
                                ),
                              )}
                            </select>
                          </label>
                          <button
                            disabled={
                              disabled ||
                              !tool.valid ||
                              server.state !== "connected" ||
                              !(
                                classes[toolKey(server, tool)] ||
                                (tool.classification !== "unknown" &&
                                  tool.classification)
                              )
                            }
                            onClick={() => enableTool(server, tool)}
                          >
                            Enable tool
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </details>
            )}
          </section>
        ))}
      </div>
    </section>
  );
}
