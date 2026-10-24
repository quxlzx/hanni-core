import { useEffect, useState } from "react";
import { usePrivateResource } from "./feature_types";
import { ChatMarkdown } from "./chat_markdown";

export type CommandResult = {
  ok?: boolean;
  pending?: boolean;
  id?: string;
  message: string;
  conversation?: string;
  reset_history?: boolean;
  sessions?: { id: string; title: string; message_count: number }[];
};
type Command = {
  name: string;
  arguments: string;
  description: string;
  example: string;
};

export function CommandSuggestions({
  draft,
  token,
  choose,
}: {
  draft: string;
  token: string;
  choose: (text: string) => void;
}) {
  const catalog = usePrivateResource<{ commands: Command[] }>(
    "/api/chat/commands",
    token,
    0,
  );
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => setDismissed(false), [draft]);
  const query = draft.trimStart();
  if (dismissed || !query.startsWith("/") || /\s/.test(query)) return null;
  const commands = (catalog.data?.commands || []).filter((command) =>
    command.name.startsWith(query.toLowerCase()),
  );
  if (!commands.length) return null;
  return (
    <div className="hc-command-menu" aria-label="Slash command suggestions">
      <div className="hc-command-menu-heading">
        <span>Commands</span>
        <button
          type="button"
          aria-label="Dismiss command suggestions"
          onClick={() => setDismissed(true)}
        >
          ×
        </button>
      </div>
      <div className="hc-command-choices">
        {commands.map((command) => (
          <button
            key={command.name}
            type="button"
            title={command.example}
            onClick={() =>
              choose(command.name + (command.arguments ? " " : ""))
            }
          >
            <span>
              <strong>{command.name}</strong> <small>{command.arguments}</small>
            </span>
            <span>{command.description}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function CommandOutput({
  command,
  result,
  dismiss,
  resume,
}: {
  command: string;
  result: CommandResult;
  dismiss: () => void;
  resume: (id: string) => void;
}) {
  return (
    <section
      className={`hc-command-result ${result.ok === false ? "hc-command-error" : ""}`}
      aria-label="Command result"
      aria-live="polite"
    >
      <header>
        <strong title={command}>{command}</strong>
        <button
          type="button"
          aria-label="Dismiss command result"
          onClick={dismiss}
        >
          ×
        </button>
      </header>
      <div
        className="hc-command-result-body"
        aria-busy={Boolean(result.pending)}
      >
        <ChatMarkdown text={result.message} />
        {result.sessions?.map((session) => (
          <button
            className="hc-command-session"
            key={session.id}
            onClick={() => resume(session.id)}
          >
            <strong>{session.title}</strong>
            <span>
              {session.message_count} messages · {session.id}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
