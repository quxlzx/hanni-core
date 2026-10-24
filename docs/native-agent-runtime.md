# Native agent runtime

HANNI can run its native loop or use the configured Hermes bridge. These are
separate runtimes; installing HANNI does not install or configure Hermes or Honcho.
This document records the native implementation against the eight requested
Hermes capabilities.

| Capability | Native implementation | Practical limit |
| --- | --- | --- |
| Action and feedback loop | `native/loop.py` feeds actual tool receipts into subsequent model turns. Validation and handler errors become observations. Transient inference failures get two retries without replaying effects. Cancellation is checked between calls and stream updates; the bridge terminates owned processes when cancelled. | Twelve action iterations plus at most one answer-only turn, a 900-second worker deadline, and 32 durable action requests per task. An interrupted write is never assumed undone. |
| Context management | `native/compact.py` prunes older output, summarizes with goal, constraints, completed work, blockers and next steps, retains the original task anchor, and aligns boundaries around complete assistant/tool groups. Tool schemas count against the prompt budget. Bridge transfers also account for JSON escaping and large retry receipts. | Token counts are estimates. An oversized protected exchange fails explicitly instead of sending an overflowing prompt. Transfer excerpts are marked; full history and receipts remain searchable. Pruned skills can be reloaded with `skill_read`. |
| Distinct memory purposes | Personal and environment notes use `memory.sqlite3`; searchable chat history uses `dashboard-chat.sqlite3`; working messages and the task journal use the `checkpoints` table in `tasks.sqlite3`. Preferences and device/environment notes get a small startup allowance. | Search results are historical observations and can be stale. The native loop does not silently extract or publish new personal facts. `/remember` and `/forget` remain explicit owner commands. |
| Reusable skills | Catalog discovery reads metadata; only relevant procedures are loaded. `skill_read` loads another procedure or Markdown reference. `skill_save` creates or corrects a learned procedure with an exact revision, correction and verification evidence. Bundled skills can be shadowed without modifying the distribution. | Saves follow the normal write approval policy. Verification text is attributed evidence, not a claim that the runtime independently verified the procedure. Updates change instructions, not model weights. |
| Consistent tools and errors | `native/runtime.py` provides shared schema validation, scope checks and structured errors for model calls and script RPC. Actual dispatch still uses durable approvals, current MCP definitions, and receipts. Unavailable MCP discovery no longer disables every other tool. | Unknown outcomes of external writes stay unknown and are not automatically retried. Calendar failures distinguish rejected requests from a lost creation acknowledgment. |
| Separate delegation contexts | `delegate_task` starts a child with only the named subset of its parent's tools, inherited authorization, independent messages and its own terminal cwd. Ordinary/cron tasks retain the shared workspace cwd. `agent_job` returns status, a final summary and receipt IDs. Completed summaries enter the parent's next model turn or the next turn in the same conversation. | At most two active children per parent and no nested delegation. Files are shared; separate cwd/processes are not filesystem isolation. Foreground, background and child scheduler lanes are bounded to 1, 1 and 2 workers. One inference GPU can still queue model requests. |
| Repetitive work | `execute_code` runs Python with `from hanni_tools import call`. Each call uses the same scoped registry and durable approvals. Intermediate tool results stay in the subprocess; only printed output enters the conversation. | Sixty-second script deadline, 24 RPC calls, 8KB each for stdout and stderr, no recursive code/delegation calls. This is an owned subprocess, not an OS security sandbox. In-flight external calls may finish after cancellation; their actual receipts remain authoritative. |
| Durable state and visibility | SQLite stores tasks, action decisions, receipts, events, checkpoints, reasoning returned by the provider, usage and timing. `/jobs`, `/status`, `/context` and the existing task UI expose progress. Authenticated bridge `GET /tasks/<id>/context` exposes saved working context. | Queued tasks survive restart. In-flight tasks are interrupted and unacknowledged dispatches become uncertain. Resuming a conversation uses its saved history and child results; restarting never blindly replays a checkpoint's writes. |

## Optional external memory

Connect and approve a read-only memory search tool through the existing MCP
settings, then create `state/memory-providers.json`:

```json
{
  "company-memory": {
    "tool": "<exact registered MCP tool name from the approved native tool catalog>",
    "query_parameter": "query"
  }
}
```

The agent can explicitly call
`memory_search(query="endpoint diagnosis", provider="company-memory")`.
The adapter supports providers such as Honcho when they expose a compatible
read-only MCP tool. No provider is implicitly installed or connected; no notes
or transcripts are automatically uploaded. Changed or unavailable tool
definitions fail at the existing MCP boundary.

## Procedures and recovery

Learned procedures live under `state/skills/<name>/SKILL.md`, with revision
evidence in `state/skill-revisions.sqlite3`. A bundled
`strata-endpoint-diagnostics` procedure records health/model-list/configuration
checks and verification without assuming an old host address or tuning table.

Use `/jobs result <id>` for a background result. Use `/resume <session>` to
continue saved chat, and `/compress [focus]` for a manual context summary.
`/undo` changes conversation history; it does not undo tool effects.

## Design references

The audit used the official Hermes documentation for the
[agent loop](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop),
[context compression](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching),
[memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory),
[skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills),
[tool runtime](https://hermes-agent.nousresearch.com/docs/developer-guide/tools-runtime),
[delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation), and
[code execution](https://hermes-agent.nousresearch.com/docs/user-guide/features/code-execution).
