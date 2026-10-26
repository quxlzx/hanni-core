---
name: google-tasks
description: Review connected Google Tasks, add explicitly requested tasks, and complete a selected task with a verified provider receipt.
metadata:
  hanni:
    triggers: [google tasks, google task, google to-do, google todo, tasks in google, add to google tasks, complete my google task]
---

# Google Tasks to-dos

Use Google Tasks only when it is the requested provider; it is separate from
local HANNI tasks, reminders and recurring agent jobs. Keep the selected account
and task list on every operation. The default list is `@default`; use another
list only when its exact ID is known, not a guessed display name.

Use `google.tasks.list` for incomplete tasks. Report the returned title, due
value when present and status, noting pagination or errors. Do not call a partial
list empty or treat similar titles as the same task.

For an explicitly requested addition, use `google.tasks.create` with the title.
An existing same-title task may need clarification before creating a duplicate.
The creation schema currently supports only title, account and task-list ID:
due dates, recurrence, notes and reminder notifications cannot be set here.
Explain a requested unsupported field before creating an incomplete substitute.

To finish a task, find its exact ID and list through a read, then use
`google.tasks.complete` under the existing confirmation policy. If the user names
an ambiguous task, resolve that choice first. Report the returned account, list,
ID and confirmed status. An unknown write outcome needs inspection rather than
an automatic duplicate retry. Proposing a task list alone does not save tasks.
