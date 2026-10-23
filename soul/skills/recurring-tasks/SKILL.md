---
name: recurring-tasks
description: "Create recurring agent jobs (daily digests, monitors) with the built-in cron daemon."
version: 1
author: Hanni
license: MIT
metadata:
  hermes:
    tags: [cron, automation, digest, monitoring]
---

# Recurring tasks (cron)

HANNI ships a durable cron daemon that fires agent tasks on a schedule.
Jobs are stored in `state/cron.sqlite3`; the daemon submits each due job
as a normal task and the bridge runs it with the native worker. Restarts
never double-fire (idempotency key = job id + scheduled slot).

## Create a job
From the repo root, while HANNI is running:

```
# daily AI-news digest (writes a dated report into the workspace)
.venv\Scripts\python -m hanni.native.cron --root state add ^
  --prompt "Search the web for the most important AI/ML news of the last 24 hours (model releases, inference research, hardware). Write a 5-bullet digest with links to reports/ai-news-<date>.md and reply with the bullets." ^
  --interval 86400 --auto-approve-all

# hourly GPU/heat watch that only speaks up when something is wrong
python3 -m hanni.native.cron --root state add \
  --prompt "Run system_info; if RAM usage > 90% or disk free < 10GB, append a warning line with timestamp to reports/alerts.log, otherwise do nothing." \
  --interval 3600 --auto-approve system_info local_append_file
```

Minimum interval is 300s. `--auto-approve a,b,c` pre-authorizes only the
named tools for that job (receipts carry `approved_by: task_policy`);
`--auto-approve-all` pre-authorizes everything the task requests.

## Manage jobs
```
python -m hanni.native.cron --root state list
python -m hanni.native.cron --root state disable --job ID
```
The daemon itself starts automatically with `START_BRAIN` / `start_brain.sh`
(suppress with `--no-cron`). Fired jobs appear in the Hanni OS Tasks tab
like any other task, with full receipts.

## Good recurring jobs
- morning news digest (web_search + web_fetch + local_write_file)
- price/paper/arxiv watchers (search, compare to last report, alert on change)
- workspace hygiene (list_dir + search_files for stale temp files)
- weekly self-review: summarize reports/ and append highlights to notes/journal.md

## Pitfalls
- The daemon must be running (it is, unless --no-cron); jobs added while
  it is down fire on its next pass, never retroactively twice.
- Keep prompts self-contained: a cron task has no conversation, only its
  prompt plus durable memory.
- Prefer narrow --auto-approve lists for anything touching local_terminal.
