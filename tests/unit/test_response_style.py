from __future__ import annotations
import unittest
from hanni.core.response_style import sanitize_assistant_text, sanitize_response_chunk, runaway_reason, guard_assistant_text

class ResponseStyleTests(unittest.TestCase):

    def test_runaway_guard_rejects_pathological_digits_and_passage_loops(self) -> None:
        self.assertEqual(runaway_reason('Network latency ' + '0' * 90), 'long_digit_run')
        paragraph = 'CPU 28%, RAM 51%, and no obvious resource bottleneck in this snapshot. '
        self.assertEqual(runaway_reason(paragraph * 4), 'repeated_passage')
        self.assertIn("couldn't finish", guard_assistant_text(paragraph * 4))
        self.assertIsNone(runaway_reason('No, no, no—that is not what the result says.'))

    def test_chunk_cleanup_is_stream_safe_for_markdown_markers(self) -> None:
        self.assertEqual(sanitize_response_chunk('**Hello** 😊'), 'Hello ')
        self.assertEqual(sanitize_response_chunk('### Heading\nNext'), ' Heading Next')

    def test_complete_cleanup_collapses_chat_format(self) -> None:
        text = '**Sure!**\n- First thing\n- Second thing 😊'
        clean = sanitize_assistant_text(text)
        self.assertNotIn('*', clean)
        self.assertNotIn('😊', clean)
        self.assertNotIn('\n', clean)
        self.assertIn('Sure!', clean)
if __name__ == '__main__':
    unittest.main()
