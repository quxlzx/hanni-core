import { useEffect, useRef, useState, type FormEvent } from "react";
import { write, type useResource } from "./api";
import { usePrivateResource } from "./feature_types";
import type { Telemetry } from "./types";
import { OutputSettings } from "./output_settings";

type Selection = {
  source: "local" | "api";
  local_model?: string;
  endpoint?: string;
  api_model?: string;
  context: number;
  has_api_key?: boolean;
};
type Settings = {
  available: boolean;
  active: Selection | null;
  local_models: {
    id: string;
    name: string;
    installed: boolean;
    max_context: number;
  }[];
  min_context: number;
  max_context: number;
  environment_key: boolean;
  change: { id: string; status: string; detail: string } | null;
};
const contextOptions = [65536, 98304, 131072, 196608, 262144];

export function ModelsPanel({
  token,
  telemetry,
}: {
  token: string;
  telemetry: ReturnType<typeof useResource<Telemetry>>;
}) {
  const resource = usePrivateResource<Settings>(
    "/api/model-settings",
    token,
    1500,
  );
  const [source, setSource] = useState<"local" | "api">("local");
  const [localModel, setLocalModel] = useState("MiniCPM5-2B-Q4_K_M.gguf");
  const [endpoint, setEndpoint] = useState(""),
    [apiModel, setApiModel] = useState(""),
    [apiKey, setApiKey] = useState("");
  const [context, setContext] = useState(65536);
  const [working, setWorking] = useState(false),
    [error, setError] = useState(""),
    [note, setNote] = useState("");
  const initialized = useRef(false);
  const pending = useRef<{ fingerprint: string; id: string } | null>(null);
  const data = resource.data;
  const change = data?.change;
  const changing =
    change?.status === "pending" || change?.status === "applying";
  const active = data?.active;
  const localLimit =
    data?.local_models.find((item) => item.id === localModel)?.max_context ||
    262144;
  useEffect(() => {
    if (source === "local" && context > localLimit) setContext(localLimit);
  }, [source, localLimit, context]);
  const disabled =
    working ||
    changing ||
    !data?.available ||
    !token ||
    Boolean(resource.error);
  useEffect(() => {
    if (!data || initialized.current) return;
    initialized.current = true;
    if (data.active) {
      setSource(data.active.source);
      setLocalModel(data.active.local_model || "MiniCPM5-2B-Q4_K_M.gguf");
      setEndpoint(
        data.active.source === "api" ? data.active.endpoint || "" : "",
      );
      setApiModel(
        data.active.source === "api" ? data.active.api_model || "" : "",
      );
      setContext(Math.max(65536, data.active.context));
    }
  }, [data]);
  useEffect(() => {
    if (change?.status === "ready" || change?.status === "failed")
      telemetry.refresh();
  }, [change?.id, change?.status]);

  async function execute(operation: "test" | "apply") {
    if (disabled) return;
    setWorking(true);
    setError("");
    setNote("");
    const values = {
      operation,
      source,
      context,
      ...(source === "local"
        ? { local_model: localModel }
        : { endpoint, api_model: apiModel, api_key: apiKey }),
    };
    const fingerprint = JSON.stringify(values);
    const id =
      pending.current?.fingerprint === fingerprint
        ? pending.current.id
        : crypto.randomUUID();
    pending.current = { fingerprint, id };
    try {
      if (operation === "test") {
        const result = await write<{ connected: boolean; detail: string }>(
          "/api/model-settings",
          token,
          { ...values, id },
        );
        setNote(result.detail);
      } else {
        const result = await write<Settings>("/api/model-settings", token, {
          ...values,
          id,
        });
        resource.setData(result);
        setApiKey("");
      }
      pending.current = null;
      resource.refresh();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The model request could not be confirmed. Retry with the same settings.",
      );
    } finally {
      setWorking(false);
    }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    void execute("apply");
  }
  const model = telemetry.data;
  const activeName =
    active?.source === "api"
      ? active.api_model
      : data?.local_models.find((item) => item.id === active?.local_model)
          ?.name || active?.local_model;
  return (
    <section className="hc-panel-content hc-models-panel">
      <header>
        <h1>Models</h1>
        <button
          onClick={() => {
            resource.refresh();
            telemetry.refresh();
          }}
        >
          Refresh
        </button>
      </header>
      <p>Choose a model on this computer or connect your own model API.</p>
      {resource.error && (
        <p className="hc-error-text" role="alert">
          {resource.error}
        </p>
      )}
      {!data && !resource.error && <p role="status">Reading model settings…</p>}
      {data && !data.available && (
        <p role="status">
          Model switching is available when HANNI runs through START_HANNI.
        </p>
      )}
      <div className="hc-active-model" aria-label="Active model">
        <div>
          <span className="hc-muted">Current model</span>
          <strong>
            {activeName ||
              model?.model?.file?.split(/[\\/]/).at(-1) ||
              "Checking…"}
          </strong>
        </div>
        <span>
          {changing
            ? "Switching…"
            : telemetry.error
              ? "Status unavailable"
              : model?.model_status || "Checking…"}
        </span>
      </div>
      {active && (
        <dl className="hc-model-context">
          <div>
            <dt>Requested context</dt>
            <dd>{active.context.toLocaleString()} tokens</dd>
          </div>
          <div>
            <dt>Server context</dt>
            <dd>
              {model?.model?.context_verified && !telemetry.error
                ? `${model.model.context?.toLocaleString()} tokens`
                : "Not reported by this provider"}
            </dd>
          </div>
        </dl>
      )}
      <OutputSettings token={token} disabled={changing} />
      {change && (
        <p
          className={
            change.status === "failed"
              ? "hc-error-text hc-model-notice"
              : "hc-model-notice"
          }
          role="status"
        >
          {change.detail}
        </p>
      )}
      <form className="hc-model-form" onSubmit={submit}>
        <fieldset disabled={disabled}>
          <legend>Model source</legend>
          <div className="hc-model-sources">
            <label>
              <input
                type="radio"
                name="model-source"
                value="local"
                checked={source === "local"}
                onChange={() => {
                  setSource("local");
                  setError("");
                  setNote("");
                }}
              />
              <span>Local model</span>
            </label>
            <label>
              <input
                type="radio"
                name="model-source"
                value="api"
                checked={source === "api"}
                onChange={() => {
                  setSource("api");
                  setError("");
                  setNote("");
                }}
              />
              <span>API connection</span>
            </label>
          </div>
        </fieldset>
        <fieldset disabled={disabled}>
          <legend className="sr-only">Model connection</legend>
          {source === "local" ? (
            <label className="hc-model-field">
              Local model
              <select
                value={localModel}
                onChange={(event) => setLocalModel(event.target.value)}
                required
              >
                {(data?.local_models || []).map((item) => (
                  <option
                    value={item.id}
                    key={item.id}
                    disabled={!item.installed}
                  >
                    {item.name}
                    {item.installed ? "" : " — not installed"}
                  </option>
                ))}
              </select>
              <small>
                Installed GGUF models. Loading a different model keeps your
                conversations.
              </small>
            </label>
          ) : (
            <>
              <label className="hc-model-field">
                API base URL
                <input
                  type="url"
                  value={endpoint}
                  onChange={(event) => {
                    setEndpoint(event.target.value);
                    setNote("");
                  }}
                  placeholder="https://your-provider.example/v1"
                  required
                  autoComplete="off"
                  spellCheck={false}
                />
                <small>Use an OpenAI-compatible Chat Completions API.</small>
              </label>
              <label className="hc-model-field">
                Model ID
                <input
                  value={apiModel}
                  onChange={(event) => {
                    setApiModel(event.target.value);
                    setNote("");
                  }}
                  placeholder="Exact model ID from your provider"
                  required
                  maxLength={256}
                  autoComplete="off"
                  spellCheck={false}
                />
              </label>
              <label className="hc-model-field">
                API key{" "}
                <span className="hc-muted">
                  (optional for unauthenticated servers)
                </span>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  autoComplete="new-password"
                  maxLength={8192}
                  placeholder={
                    active?.source === "api" &&
                    active.has_api_key &&
                    active.endpoint === endpoint
                      ? "Saved key — leave blank to keep"
                      : "Enter API key"
                  }
                />
                <small>
                  Saved in your system credential store.{" "}
                  {data?.environment_key
                    ? "HANNI_MODEL_API_KEY is also available."
                    : "You can also set HANNI_MODEL_API_KEY before starting HANNI."}
                </small>
              </label>
            </>
          )}
          <label className="hc-model-field hc-context-field">
            Context window
            <select
              value={context}
              onChange={(event) => setContext(Number(event.target.value))}
              required
            >
              {!contextOptions.includes(context) && (
                <option value={context}>
                  {(context / 1024).toLocaleString()}K —{" "}
                  {context.toLocaleString()} tokens
                </option>
              )}
              {contextOptions.map((value) => (
                <option
                  value={value}
                  key={value}
                  disabled={source === "local" && value > localLimit}
                >
                  {value / 1024}K — {value.toLocaleString()} tokens
                  {value === 65536 ? " (default)" : ""}
                </option>
              ))}
            </select>
            <small>
              {source === "local" && localLimit < 262144
                ? `This model supports up to ${localLimit / 1024}K. Choose K2 for 256K. `
                : "64K minimum, up to 256K. "}
              Larger contexts use more memory. API limits are controlled by the
              provider.
            </small>
          </label>
        </fieldset>
        {(error || note) && (
          <p
            className={error ? "hc-error-text" : "hc-model-notice"}
            role={error ? "alert" : "status"}
          >
            {error || note}
          </p>
        )}
        <div className="hc-model-buttons">
          {source === "api" && (
            <button
              type="button"
              disabled={disabled || !endpoint.trim() || !apiModel.trim()}
              onClick={() => void execute("test")}
            >
              Test connection
            </button>
          )}
          <button
            type="submit"
            className="hc-model-apply"
            disabled={
              disabled ||
              (source === "api" && (!endpoint.trim() || !apiModel.trim()))
            }
          >
            {working
              ? "Checking…"
              : changing
                ? "Loading model…"
                : "Apply model"}
          </button>
        </div>
      </form>
    </section>
  );
}
