"""Soul, skills, compaction, and memory injection for the native loop."""
import tempfile
import unittest
from pathlib import Path

from hanni.native.compact import compact, estimate_tokens
from hanni.native.memory_inject import memory_block
from hanni.native.skills import load_skills, match_skills
from hanni.native.soul import build_system_prompt, load_soul


class ScriptedClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def chat(self, messages, schemas):
        self.calls.append(messages)
        return {"message": dict(self.reply), "finish": "stop"}


class SoulTests(unittest.TestCase):
    def test_repo_soul_loads(self):
        self.assertIn("HANNI", load_soul())

    def test_missing_soul_is_empty(self):
        self.assertEqual(load_soul("/nonexistent/SOUL.md"), "")

    def test_prompt_ordering(self):
        prompt = build_system_prompt("CONTRACT", "SOULTEXT", "SKILLTEXT")
        self.assertLess(prompt.index("SOULTEXT"), prompt.index("CONTRACT"))
        self.assertLess(prompt.index("CONTRACT"), prompt.index("SKILLTEXT"))


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        Path(self.dir.name, "strata.md").write_text(
            "---\nname: strata-ops\ndescription: tuning the strata server\n"
            "triggers: strata, benchmark\n---\nAlways warm up before measuring.\n")
        Path(self.dir.name, "cooking.md").write_text("no frontmatter, never matched by keywords")

    def tearDown(self):
        self.dir.cleanup()

    def test_load_and_match(self):
        skills = load_skills(self.dir.name)
        self.assertEqual(len(skills), 2)
        hit = match_skills(skills, "please benchmark the strata server again")
        self.assertIn("warm up before measuring", hit)
        self.assertNotIn("cooking", hit)

    def test_budget_caps_output(self):
        skills = load_skills(self.dir.name)
        self.assertLessEqual(len(match_skills(skills, "strata benchmark", char_budget=50)), 50)

    def test_no_match_empty(self):
        self.assertEqual(match_skills(load_skills(self.dir.name), "totally unrelated"), "")

    def test_standard_metadata_triggers_select_the_relevant_procedure(self):
        Path(self.dir.name, 'SKILL.md').write_text(
            '---\nname: minutes\ndescription: Summarize a discussion.\n'
            'metadata:\n  hanni:\n    triggers: [meeting notes, action items]\n'
            '---\nSeparate decisions from proposals.\n')
        skills = load_skills(self.dir.name)
        result = match_skills(skills, 'Extract action items from these meeting notes.')
        self.assertIn('### skill: minutes', result)
        self.assertNotIn('minutes', match_skills(skills, 'Summarize a discussion.'))

    def test_existing_top_level_triggers_take_precedence(self):
        Path(self.dir.name, 'SKILL.md').write_text(
            '---\nname: minutes\ndescription: Summarize a discussion.\n'
            'triggers: [notes]\nmetadata:\n  hanni:\n    triggers: [ignored]\n'
            '---\nRecord the decisions.\n')
        skills = load_skills(self.dir.name)
        self.assertIn('### skill: minutes', match_skills(skills, 'notes'))
        self.assertEqual(match_skills(skills, 'ignored'), '')

    def test_multiple_skill_budget_includes_separators(self):
        skills = [{'name': name, 'triggers': ['notes'], 'body': 'abcdefghij'}
                  for name in ('first', 'second')]
        result = match_skills(skills, 'notes', char_budget=50)
        self.assertIn('### skill: second', result)
        self.assertLessEqual(len(result), 50)


class CompactTests(unittest.TestCase):
    def _messages(self, n=20):
        msgs = [{"role": "system", "content": "sys"}]
        for i in range(n):
            msgs.append({"role": "user", "content": f"turn {i} " + "x" * 400})
            msgs.append({"role": "assistant", "content": f"reply {i} " + "y" * 400})
        return msgs

    def test_under_budget_untouched(self):
        msgs = self._messages(2)
        self.assertEqual(compact(msgs, ScriptedClient({"content": "s"}), max_tokens=100000), msgs)

    def test_over_budget_folds_middle(self):
        msgs = self._messages(20)
        client = ScriptedClient({"content": "FOLDED SUMMARY"})
        out = compact(msgs, client, max_tokens=2000, keep_recent=4)
        self.assertEqual(out[0]["role"], "system")
        self.assertIn("FOLDED SUMMARY", out[1]["content"])
        self.assertIn("compacted summary", out[1]["content"])
        self.assertIn("reply 19", out[-1]["content"])
        self.assertEqual(len(client.calls), 1)  # one summary call

    def test_tool_groups_not_split(self):
        msgs = self._messages(10)
        msgs.insert(11, {"role": "tool", "tool_call_id": "t", "content": "receipt"})
        msgs.insert(10, {"role": "assistant", "content": "", "tool_calls": [{"id": "t"}]})
        out = compact(msgs, ScriptedClient({"content": "s"}), max_tokens=1000, keep_recent=4)
        # the assistant-with-calls and its tool result stay adjacent
        for i, m in enumerate(out):
            if m.get("role") == "tool":
                self.assertEqual(out[i - 1].get("tool_calls"), [{"id": "t"}])

    def test_summary_failure_falls_back_extractive(self):
        class Boom:
            def chat(self, *a):
                raise RuntimeError("model down")
        out = compact(self._messages(20), Boom(), max_tokens=2000)
        self.assertIn("turn 1", out[1]["content"])  # extractive fallback keeps content


class MemoryInjectTests(unittest.TestCase):
    def test_relevant_memories_injected(self):
        from hanni.memory.store import MemoryStore
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "m.sqlite3")
            store.remember("The Strata tuning table must match hipBLASLt runtime version 100200")
            store.remember("Laynce's cat is named Momo")
            block = memory_block(store, "which hipblaslt tuning table does strata need")
            self.assertIn("100200", block)
            self.assertIn("untrusted data", block)

    def test_empty_store_empty_block(self):
        from hanni.memory.store import MemoryStore
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(memory_block(MemoryStore(Path(tmp) / "m.sqlite3"), "anything"), "")


if __name__ == "__main__":
    unittest.main()
