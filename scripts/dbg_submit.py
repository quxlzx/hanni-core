#!/usr/bin/env python3
"""Submit one auto-approved local-runtime task to the debug bridge."""
import json
import urllib.request

token = open('/tmp/hanni-cron-dbg/bridge.token').read().strip()
req = urllib.request.Request('http://127.0.0.1:8095/tasks', method='POST',
    data=json.dumps({"key": "dbg2", "task": {
        "prompt": "Use local_terminal to run echo dbg-ok and report the output.",
        "windows_tools": [], "origin": "hanni",
        "context": {"local_runtime": {"auto_approve": ["*"]}}}}).encode(),
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=20) as r:
    print('submitted:', json.loads(r.read())['id'])
