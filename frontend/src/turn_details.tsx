import { usePrivateResource } from "./feature_types";
import { ChatIcon } from "./chat_app";
import { ChatMarkdown } from "./chat_markdown";
import type { Message } from "./types";

type Stats = {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  elapsed_seconds: number;
  tokens_per_second: number | null;
  rate_source: "generation" | "request" | null;
  model_requests: number;
};
type TaskDetail = {
  id: string;
  state: string;
  created: number;
  events?: { time: number; text: string }[];
  actions?: {
    id: string;
    state: string;
    created?: number;
    spec: { name: string };
    receipt?: { ok: boolean; message?: string; error?: string } | null;
  }[];
  result?: {
    reasoning?: { step: number; text: string; truncated: boolean }[];
    stats?: Stats | null;
    draft?: string;
    activity?: {
      phase: string;
      step: number;
      started_at: number;
      tool?: string;
    };
  } | null;
  error?: string;
};

function ReasoningDetails({
  row,
  data,
  error,
  retry,
  openTasks,
}: {
  row: Message;
  data: TaskDetail | null;
  error: string;
  retry: () => void;
  openTasks: () => void;
}) {
  const working =
    row.status === "working" &&
    ![
      "review_required",
      "failed",
      "cancelled",
      "interrupted",
      "uncertain",
      "completed",
    ].includes(data?.state || "");
  const [expanded, setExpanded] = useState(working),
    [now, setNow] = useState(Date.now());
  const touched = useRef(false);
  const body = useRef<HTMLDivElement>(null),
    follow = useRef(true);
  useEffect(() => {
    if (!working) {
      if (!touched.current) {
        setExpanded(false);
        if (body.current) body.current.scrollTop = 0;
      }
      return;
    }
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [working]);
  const reasoning = data?.result?.reasoning || [];
  const activity = data?.result?.activity;
  const actions = data?.actions || [];
  const elapsed = working
    ? Math.max(
        0,
        now / 1000 - (activity?.started_at || data?.created || row.created),
      )
    : data?.result?.stats?.elapsed_seconds;
  const heading = working
    ? data?.state === "approval" &&
      actions.some((action) => action.state === "pending")
      ? "Waiting for approval"
      : activity?.phase === "writing"
        ? "Writing response"
        : activity?.phase === "tools"
          ? actions.some((a) => a.state === "dispatching")
            ? "Using tools"
            : "Preparing a tool call"
          : data
            ? "Thinking"
            : "Preparing response"
    : row.status === "interrupted" ||
        ["failed", "cancelled", "interrupted", "uncertain"].includes(
          data?.state || "",
        )
      ? "Response interrupted"
      : "Reasoning & activity";
  useEffect(() => {
    if (working && follow.current && body.current)
      body.current.scrollTop = body.current.scrollHeight;
  }, [
    working,
    heading,
    reasoning.at(-1)?.text,
    actions.map((action) => action.state).join(","),
  ]);
  type Item = {
    id: string;
    time: number;
    label: string;
    status: string;
    text?: string;
    truncated?: boolean;
    note?: string;
  };
  const items: Item[] = [];
  const events = data?.events || [];
  const requests = events.flatMap((event) => {
    const match = event.text.match(/^native loop: request (\d+)\//);
    return match ? [{ step: Number(match[1]), time: event.time }] : [];
  });
  if (data && events.length)
    items.push({
      id: "prepare",
      time: data.created,
      label: "Prepared the task",
      status: "complete",
    });
  const skillEvent = events.find((event) =>
    event.text.startsWith("Skills applied: "),
  );
  if (skillEvent)
    items.push({
      id: "skills",
      time: skillEvent.time,
      label: "Applied relevant skills",
      status: "complete",
      note: skillEvent.text.slice(16),
    });
  const modelSteps = new Set([
    ...requests.map((item) => item.step),
    ...reasoning.map((item) => item.step),
    ...(activity ? [activity.step] : []),
  ]);
  for (const step of modelSteps) {
    const entry = reasoning.find((item) => item.step === step);
    const request = requests.find((item) => item.step === step);
    const current = step === (activity?.step || Math.max(...modelSteps));
    const active =
      working && current && (!activity || activity.phase === "thinking");
    items.push({
      id: `model-${step}`,
      time:
        request?.time ||
        (activity?.started_at || data?.created || row.created) + step * 0.001,
      label: entry ? "Model reasoning" : "Generating a response",
      status: active
        ? "active"
        : current && row.status === "interrupted"
          ? "stopped"
          : "complete",
      text: entry?.text,
      truncated: entry?.truncated,
    });
  }
  events.forEach((event, index) => {
    if (event.text === "Writing response.")
      items.push({
        id: `writing-${index}`,
        time: event.time,
        label: "Writing response",
        status:
          working &&
          activity?.phase === "writing" &&
          !events
            .slice(index + 1)
            .some((item) => item.text.startsWith("native loop: request "))
            ? "active"
            : "complete",
      });
  });
  for (const action of actions) {
    const status =
      action.state === "fulfilled"
        ? action.receipt?.ok
          ? "complete"
          : "failed"
        : action.state === "pending"
          ? working
            ? "waiting"
            : "stopped"
          : action.state === "dispatching"
            ? working
              ? "active"
              : "stopped"
            : "failed";
    items.push({
      id: action.id,
      time: action.created || data?.created || row.created,
      label: action.spec.name.replace(/^local_/, "").replaceAll("_", " "),
      status,
      note:
        status === "waiting"
          ? "Approval needed"
          : action.receipt?.error || action.receipt?.message,
    });
  }
  items.sort((a, b) => a.time - b.time);
  return (
    <details
      className={`hc-reasoning ${working ? "hc-reasoning-live" : ""}`}
      open={expanded}
    >
      <summary
        onClick={(event) => {
          event.preventDefault();
          touched.current = true;
          setExpanded((value) => !value);
        }}
      >
        <ChatIcon name="reasoning" />
        <span className="hc-reasoning-heading" aria-live="polite">
          {heading}
        </span>
        {elapsed != null && Number.isFinite(elapsed) && (
          <small className="hc-reasoning-duration">{elapsed.toFixed(1)}s</small>
        )}
        <span className="hc-reasoning-chevron" aria-hidden="true">
          <ChatIcon name="chevron" />
        </span>
      </summary>
      <div
        className="hc-reasoning-body"
        ref={body}
        onScroll={() => {
          const node = body.current;
          if (node)
            follow.current =
              node.scrollHeight - node.scrollTop - node.clientHeight < 60;
        }}
      >
        {error && row.task_id ? (
          <p className="hc-turn-note">
            Could not load response details.{" "}
            <button onClick={retry}>Retry</button>
          </p>
        ) : (
          <>
            {items.length > 0 && (
              <ol className="hc-reasoning-timeline" aria-label="Response steps">
                {items.map((item) => (
                  <li
                    key={item.id}
                    className={`hc-reasoning-item hc-step-${item.status}`}
                  >
                    <span className="hc-step-marker" aria-hidden="true">
                      <ChatIcon
                        name={
                          item.status === "complete"
                            ? "check"
                            : item.status === "failed" ||
                                item.status === "stopped"
                              ? "close"
                              : item.status === "waiting"
                                ? "clock"
                                : "reasoning"
                        }
                      />
                    </span>
                    <div>
                      <div className="hc-step-heading">
                        <span>{item.label}</span>
                        <small>
                          {item.status === "active"
                            ? "In progress"
                            : item.status === "waiting"
                              ? "Waiting"
                              : item.status === "failed"
                                ? "Failed"
                                : item.status === "stopped"
                                  ? "Stopped"
                                  : "Done"}
                        </small>
                      </div>
                      {item.note && <p className="hc-step-note">{item.note}</p>}
                      {item.text && <p className="hc-step-text">{item.text}</p>}
                      {item.truncated && (
                        <small>This reasoning excerpt was shortened.</small>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            )}
            {working && (
              <p className="hc-reasoning-current">
                <span className="hc-live-dot" />
                {heading}…
              </p>
            )}
            {!working && !reasoning.length && (
              <p className="hc-reasoning-empty">
                {data?.result && Object.hasOwn(data.result, "reasoning")
                  ? "The model did not return separate reasoning text. Available activity is shown above."
                  : row.task_id && !data
                    ? "Loading recorded activity…"
                    : "Reasoning was not recorded for this older response."}
              </p>
            )}
            {actions.length > 0 && (
              <button className="hc-text-button" onClick={openTasks}>
                Review tasks &amp; approvals
              </button>
            )}
          </>
        )}
      </div>
    </details>
  );
}

function ResponseStats({ stats }: { stats: Stats }) {
  return (
    <div className="hc-response-stats" aria-label="Response statistics">
      {stats.completion_tokens != null && (
        <span
          title={`Completion tokens across ${stats.model_requests} model request${stats.model_requests === 1 ? "" : "s"}${stats.prompt_tokens != null ? `; ${stats.prompt_tokens.toLocaleString()} prompt tokens` : ""}`}
        >
          <ChatIcon name="tokens" />
          {stats.completion_tokens.toLocaleString()} tokens
        </span>
      )}
      {Number.isFinite(stats.elapsed_seconds) && (
        <span title="Agent run time, including model requests, tools, and approval waits">
          <ChatIcon name="clock" />
          {stats.elapsed_seconds.toFixed(1)}s
        </span>
      )}
      {stats.tokens_per_second != null &&
        Number.isFinite(stats.tokens_per_second) && (
          <span
            title={
              stats.rate_source === "generation"
                ? "Generation throughput reported by the model server"
                : "Completion tokens divided by model request time, including prompt processing"
            }
          >
            <ChatIcon name="speed" />
            {stats.tokens_per_second.toFixed(1)} tokens/s
          </span>
        )}
    </div>
  );
}

export function AssistantResponse({
  row,
  token,
  openTasks,
}: {
  row: Message;
  token: string;
  openTasks: () => void;
}) {
  const working = row.status === "working";
  const task = usePrivateResource<TaskDetail>(
    row.task_id
      ? `/api/bridge/task/${encodeURIComponent(row.task_id)}`
      : "/api/bridge/tasks",
    row.task_id ? token : "",
    working ? 500 : 0,
  );
  const data = task.data?.id === row.task_id ? task.data : null;
  return (
    <>
      <ReasoningDetails
        row={row}
        data={data}
        error={task.error}
        retry={task.refresh}
        openTasks={openTasks}
      />
      {(!working || data?.result?.draft) && (
        <ChatMarkdown
          text={working ? data?.result?.draft || "" : row.content}
          working={working}
        />
      )}
      {!working && data?.result?.stats && (
        <ResponseStats stats={data.result.stats} />
      )}
    </>
  );
}
import { useEffect, useRef, useState } from "react";
