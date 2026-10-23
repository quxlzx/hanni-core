#!/usr/bin/env python3
"""Submit via TaskStore directly (external process) to test run_queue pickup."""
import sys
sys.path.insert(0, "src")
from hanni.hermes.state import TaskStore

store = TaskStore("/tmp/hanni-cron-dbg/tasks.sqlite3")
task = store.submit("ext-1", {"prompt": "Use local_terminal to run echo ext-ok and report the output.",
                              "windows_tools": [], "origin": "hanni",
                              "context": {"local_runtime": {"auto_approve": ["*"]}}})
print("submitted:", task["id"], task["state"])
print("queued() sees:", [t["id"] for t in store.queued()])
