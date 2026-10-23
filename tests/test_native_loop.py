"""Native loop tests: fake model client, no network, no model required."""
import json
import unittest

from hanni.native.loop import run_loop, strip_reasoning


class FakeClient:
    """Scripted replies: each chat() call returns the next canned message."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, tools=None):
        self.calls.append({"messages": list(messages), "tools": tools})
        return self.replies.pop(0)


def spec(name):
    return {"name": name, "target": "windows", "schema": {"type": "function", "function": {
        "name": name, "description": f"tool {name}",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}}}


class NativeLoopTests(unittest.TestCase):
    def test_plain_answer(self):
        client = FakeClient([{"message": {"content": "hello"}, "finish": "stop", "usage": {}}])
        out = run_loop(client, system_prompt="s", user_message="u", tool_specs=[], execute=lambda n, a, c=None: {"ok": True})
        self.assertEqual(out["claims"], "hello")
        self.assertFalse(out["interrupted"])

    def test_reasoning_stripped(self):
        client = FakeClient([{"message": {"content": "<think>secret churn</think>visible", "reasoning_content": "", "finish": "stop", "usage": {}}}])
        out = run_loop(client, system_prompt="s", user_message="u", tool_specs=[], execute=lambda n, a, c=None: {"ok": True})
        self.assertEqual(out["claims"], "visible")

    def test_tool_roundtrip(self):
        client = FakeClient([
            {"message": {"content": "", "tool_calls": [{"id": "c1", "function": {"name": "lookup", "arguments": json.dumps({})}}]}, "finish": "tool_calls", "usage": {}},
            {"message": {"content": "done", "finish": "stop", "usage": {}}, },
        ])
        seen = []
        out = run_loop(client, system_prompt="s", user_message="u", tool_specs=[spec("lookup")],
                       execute=lambda n, a, c=None: seen.append(n) or {"ok": True, "data": {}})
        self.assertEqual(seen, ["lookup"])
        self.assertEqual(out["claims"], "done")
        tool_message = client.calls[1]["messages"][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertIn("untrusted_observation", json.loads(tool_message["content"]))

    def test_invalid_json_arguments_blocked(self):
        client = FakeClient([
            {"message": {"content": "", "tool_calls": [{"id": "c1", "function": {"name": "lookup", "arguments": "{not json"}}]}, "finish": "tool_calls", "usage": {}},
            {"message": {"content": "blocked", "finish": "stop", "usage": {}}},
        ])
        executed = []
        out = run_loop(client, system_prompt="s", user_message="u", tool_specs=[spec("lookup")],
                       execute=lambda n, a, c=None: executed.append(n) or {"ok": True})
        self.assertEqual(executed, [])
        self.assertEqual(out["claims"], "blocked")

    def test_unknown_tool_blocked(self):
        client = FakeClient([
            {"message": {"content": "", "tool_calls": [{"id": "c1", "function": {"name": "terminal", "arguments": "{}"}}]}, "finish": "tool_calls", "usage": {}},
            {"message": {"content": "refused", "finish": "stop", "usage": {}}},
        ])
        executed = []
        run_loop(client, system_prompt="s", user_message="u", tool_specs=[spec("lookup")],
                 execute=lambda n, a, c=None: executed.append(n) or {"ok": True})
        self.assertEqual(executed, [])

    def test_menu_replacement_applies(self):
        replacement = [spec("new_tool")["schema"]]
        client = FakeClient([
            {"message": {"content": "", "tool_calls": [{"id": "c1", "function": {"name": "discover", "arguments": "{}"}}]}, "finish": "tool_calls", "usage": {}},
            {"message": {"content": "", "tool_calls": [{"id": "c2", "function": {"name": "new_tool", "arguments": "{}"}}]}, "finish": "tool_calls", "usage": {}},
            {"message": {"content": "ok", "finish": "stop", "usage": {}}},
        ])
        executed = []

        def execute(name, args, call_id=None):
            executed.append(name)
            if name == "discover":
                return {"ok": True, "data": {"replacement_menu": replacement}}
            return {"ok": True, "data": {}}
        out = run_loop(client, system_prompt="s", user_message="u", tool_specs=[spec("discover")], execute=execute)
        self.assertEqual(executed, ["discover", "new_tool"])
        self.assertEqual(out["claims"], "ok")

    def test_iteration_bound_interrupts(self):
        looping = [{"message": {"content": "", "tool_calls": [{"id": "c", "function": {"name": "lookup", "arguments": "{}"}}]}, "finish": "tool_calls", "usage": {}}] * 5
        client = FakeClient(looping)
        out = run_loop(client, system_prompt="s", user_message="u", tool_specs=[spec("lookup")],
                       execute=lambda n, a, c=None: {"ok": True}, max_iterations=3)
        self.assertTrue(out["interrupted"])
        self.assertEqual(out["iterations"], 3)

    def test_strip_reasoning_open_tag(self):
        self.assertEqual(strip_reasoning("answer<think>dangling"), "answer")


if __name__ == "__main__":
    unittest.main()
