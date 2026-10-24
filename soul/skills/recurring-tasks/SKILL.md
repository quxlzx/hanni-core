---
name: recurring-tasks
description: Create and manage persistent daily updates, hourly checks, and weekly reports delivered to a HANNI conversation.
metadata:
  hanni:
    triggers: [daily, every day, everyday, weekly, every week, hourly, every hour, repeat, recurring, schedule a task, scheduled task]
---

# Repeating tasks

For a request such as "update me daily on the AI world", call `schedule_task`
directly. Do not inspect workspace folders, run terminals, write scheduling
scripts, or generate the current news digest instead of saving the schedule.
Set a descriptive title and a self-contained execution prompt: search current
sources, cover the last 24 hours, summarize key developments, and include links.
A scheduled run has no full conversation or attached documents unless its
prompt contains the relevant context.

Use the user's requested frequency, time, timezone, and weekday (Monday=0).
When no time is supplied, the tool defaults to 09:00 in HANNI's configured
timezone. Report that choice and the actual `next_run_local`, timezone, and job
ID returned by the tool. Only claim scheduling succeeded after an `ok` receipt.
Hourly/interval schedules repeat from creation; daily/weekly schedules preserve
local wall time across DST. Results and approval requests return to the linked
conversation. HANNI must be running; missed slots catch up once on the next
launch, without producing a backlog of duplicate runs.

Use `scheduled_tasks` to list, pause, resume, or delete by exact ID. Pausing or
deleting does not cancel already-submitted work; use the actual job tools to
inspect/cancel such a run. Future runs may automatically use read-only tools;
other tool actions still need approval. Never promise silent external sends.
When the context contains `scheduled_job_id`, execute the prompt once and return
the answer with sources; do not create another schedule.

The deterministic fallback is `/schedule daily 09:00 | Task`, `/schedule weekly
mon 09:00 | Task`, `/schedule hourly | Task`, or `/schedule every 2 hours | Task`.
Manage with `/schedule list`, `/schedule pause ID`, `/schedule resume ID`, and
`/schedule delete ID`. The Schedule page provides the same operations.
