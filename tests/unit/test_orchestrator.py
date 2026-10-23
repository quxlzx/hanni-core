from __future__ import annotations
import unittest
from hanni.core.orchestrator import DEFAULT_SYSTEM_PROMPT, TextSession
from hanni.core.response_style import sanitize_assistant_text

class StubClient:

    def __init__(self, chunks=None) -> None:
        self.calls = []
        self.chunks = chunks or ['Hi', ' there']

    def stream_chat(self, messages, **kwargs):
        self.calls.append((list(messages), kwargs))
        yield from self.chunks

class TextSessionTests(unittest.TestCase):

    def test_session_streams_and_preserves_conversation_history(self) -> None:
        client = StubClient()
        session = TextSession(client, system_prompt='SYSTEM')
        self.assertEqual(''.join(session.stream_response('hello')), 'Hi there')
        self.assertEqual(session.history[-2]['content'], 'hello')
        self.assertEqual(session.history[-1]['content'], 'Hi there')
        self.assertEqual(''.join(session.stream_response('again')), 'Hi there')
        messages, _ = client.calls[-1]
        self.assertEqual(messages[0], {'role': 'system', 'content': 'SYSTEM'})
        self.assertIn({'role': 'assistant', 'content': 'Hi there'}, messages)

    def test_stream_removes_markdown_and_emoji_artifacts(self) -> None:
        client = StubClient(['**Sure!** ', "Here's `the answer` 😊"])
        session = TextSession(client)
        output = ''.join(session.stream_response('hello'))
        self.assertNotIn('*', output)
        self.assertNotIn('`', output)
        self.assertNotIn('😊', output)
        self.assertIn('Sure!', output)
        self.assertEqual(session.history[-1]['content'], sanitize_assistant_text(output))

    def test_default_prompt_is_voice_first_and_concise(self) -> None:
        lower = DEFAULT_SYSTEM_PROMPT.lower()
        self.assertIn('voice-first', lower)
        self.assertIn('one to three short sentences', lower)
        self.assertIn('do not use markdown', lower)
        self.assertIn('do not end every reply with a question', lower)

    def test_empty_prompt_rejected(self) -> None:
        with self.assertRaises(ValueError):
            list(TextSession(StubClient()).stream_response('   '))
if __name__ == '__main__':
    unittest.main()
