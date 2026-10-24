"""Consume dashboard chat through the existing, separately supervised native agent."""
from __future__ import annotations

import threading
from .bridge_panel import bridge_proxy
from hanni.hermes.state import TERMINAL


class NativeChat:
    def __init__(self, hub, shutdown_event, *, proxy=bridge_proxy):
        self.hub, self.shutdown, self.proxy = hub, shutdown_event, proxy
        self.hub.native_mode = True
        self.stop = threading.Event()
        self.task_id = None
        from hanni.native.model_settings import ModelSettings
        self.model_settings = ModelSettings.from_env()
        self.thread = threading.Thread(target=self.run, name="hanni-native-chat", daemon=True)

    def start(self):
        self.thread.start()

    def request(self, method, path, body=None):
        result = self.proxy(method, path, body)
        if result.get("error") and "state" not in result:
            raise RuntimeError(result["error"])
        return result

    def run(self):
        activated = False
        while not self.stop.is_set() and not self.shutdown.is_set():
            try:
                status = self.request("GET", "/model")
                with self.hub.lock:
                    ready = bool(status.get('ready')) and not self.model_settings.pending()
                    if not activated and ready:
                        self.hub.activate()
                        activated = True
                    self.hub.ready = ready
                    prompt = self.hub.take() if ready else None
                if prompt is not None:
                    self.respond(prompt)
            except (RuntimeError, OSError, ValueError, KeyError):
                with self.hub.lock:
                    self.hub.ready = False
            self.stop.wait(.5)

    def respond(self, prompt):
        row = self.hub.begin(prompt, "browser")
        turn, _ = self.hub.turn_context(row)
        context = self.hub.native_context(self.hub.conversation_for_row(row), exclude_turn=turn)
        try:
            if self.hub.is_cancelled(turn):
                self.hub.update(row, '', 'interrupted')
                return
            previous_task = context.pop('previous_task_id', None)
            if previous_task:
                previous = self.request('GET', '/tasks/' + previous_task)
                context['previous_tool_receipts'] = [a.get('receipt') for a in previous.get('actions', []) if a.get('receipt')]
                context['previous_receipts_task_id'] = previous_task
            from hanni.native.context_budget import transfer_context
            import json
            files = self.hub.files.context(turn, budget=max(1000, min(42000, 53000 - len(json.dumps(prompt)))))
            context = transfer_context(context, max_encoded_chars=max(1000, 57000 - len(json.dumps(prompt)) - len(json.dumps(files))))
            if files:
                context['attached_files_untrusted'] = files
            task = self.request("POST", "/tasks", {"key": "chat-" + turn, "task": {
                "prompt": prompt, "windows_tools": [], "origin": "hanni", "context": context}})
            self.task_id = task["id"]
            self.hub.bind_task(row, self.task_id)
            while not self.stop.is_set() and not self.shutdown.is_set():
                if self.hub.is_cancelled(turn):
                    self.request('POST', '/tasks/' + self.task_id + '/cancel', {})
                    self.hub.update(row, '', 'interrupted')
                    return
                task = self.request("GET", "/tasks/" + self.task_id)
                if task["state"] in TERMINAL:
                    result = task.get("result") or {}
                    answer = result.get("model_claims") or task.get("error") or "No final answer was returned. Review Mission → Tasks."
                    self.hub.update(row, answer, "complete" if task["state"] == "review_required" else "interrupted")
                    return
                self.hub.update(row, "Waiting for your approval in Mission → Tasks."
                                if task["state"] == "approval" else "HANNI is working…")
                self.stop.wait(.5)
            self.hub.update(row, "The response was interrupted.", "interrupted")
        except (RuntimeError, OSError, ValueError, KeyError) as exc:
            self.hub.update(row, f"Native bridge unavailable: {exc}. Review Mission → Tasks before retrying.", "interrupted")
        finally:
            if self.task_id:
                if self.stop.is_set() or self.shutdown.is_set():
                    self.proxy("POST", "/tasks/" + self.task_id + "/cancel", {})
                self.task_id = None

    def close(self):
        self.stop.set()
        if self.thread.is_alive():
            self.thread.join(timeout=17)
