import { useEffect } from "react";
import { usePrivateResource } from "./feature_types";
import type { Message, Telemetry } from "./types";

type Usage = {
  model_requests: number;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  last_prompt_tokens?: number | null;
  last_completion_tokens?: number | null;
  tokens_per_second: number | null;
  rate_source: "generation" | "request" | null;
  context_limit?: number | null;
  model_file?: string | null;
};
type Detail = { id: string; result?: { stats?: Usage | null } | null };

function compact(value: number): string {
  return value >= 1024
    ? `${(value / 1024).toLocaleString(undefined, { maximumFractionDigits: value % 1024 ? 1 : 0 })}K`
    : value.toLocaleString();
}

export function ComposerMetrics({
  row,
  token,
  model,
}: {
  row?: Message;
  token: string;
  model?: Telemetry["model"];
}) {
  const id = row?.task_id;
  const task = usePrivateResource<Detail>(
    id ? `/api/bridge/task/${encodeURIComponent(id)}` : "/api/bridge/tasks",
    id ? token : "",
    120000,
  );
  useEffect(() => {
    if (id && row?.status !== "working") task.refresh();
  }, [id, row?.status, task.refresh]);
  const stats = task.data?.id === id ? task.data?.result?.stats : null;
  const number = (value: unknown): value is number =>
    typeof value === "number" && Number.isFinite(value) && value >= 0;
  const prompt =
    stats?.last_prompt_tokens ??
    (stats?.model_requests === 1 ? stats.prompt_tokens : null);
  const completion =
    stats?.last_completion_tokens ??
    (stats?.model_requests === 1 ? stats.completion_tokens : null);
  const fileName = (file: string) =>
    file.replaceAll("\\", "/").split("/").at(-1);
  const sameModel =
    !stats?.model_file ||
    !model?.file ||
    fileName(stats.model_file) === fileName(model.file);
  const sameContext =
    !stats?.context_limit || stats.context_limit === model?.context;
  const used =
    sameModel && sameContext && number(prompt) && number(completion)
      ? prompt + completion
      : null;
  const capacity =
    number(model?.context) && model.context > 0 ? model.context : null;
  const total =
    number(stats?.prompt_tokens) && number(stats?.completion_tokens)
      ? stats.prompt_tokens + stats.completion_tokens
      : null;
  const decode =
    stats?.rate_source === "generation" && number(stats.tokens_per_second)
      ? stats.tokens_per_second
      : null;
  const stale =
    id && task.error
      ? " Last known values; refresh is currently unavailable."
      : " Refreshes every 2 minutes and after a response finishes.";
  const contextTitle = `${used == null ? "Context usage has not been reported." : `${used.toLocaleString()} tokens in the last model request, including its prompt and generated tokens.`} ${capacity == null ? "Context limit is unavailable." : `${capacity.toLocaleString()}-token ${model?.context_verified ? "verified" : "configured"} context limit.`}${stale}`;
  return (
    <div
      className="hc-composer-metrics"
      aria-label="Context, token usage, and decode speed"
    >
      <span title={contextTitle}>
        Context{" "}
        <strong>
          {used == null ? "—" : compact(used)} /{" "}
          {capacity == null ? "—" : compact(capacity)}
        </strong>
      </span>
      <span
        title={`${total == null ? "No token usage has been reported yet." : `${stats?.prompt_tokens?.toLocaleString()} input + ${stats?.completion_tokens?.toLocaleString()} output tokens across ${stats?.model_requests} model request(s) in this reply. Output includes reasoning tokens when the provider counts them.`}${stale}`}
      >
        Tokens <strong>{total == null ? "—" : total.toLocaleString()}</strong>
      </span>
      <span
        title={`${decode == null ? "The model server has not reported generation timing; request latency is not used as decode speed." : "Decode throughput for the most recent reply, measured by the model server across its generation steps."}${stale}`}
      >
        Decode <strong>{decode == null ? "—" : decode.toFixed(1)} t/s</strong>
      </span>
    </div>
  );
}
