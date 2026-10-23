from __future__ import annotations
import unittest
from hanni.speech.barge_in import BargeInClassifier

class BargeInClassifierTests(unittest.TestCase):

    def setUp(self) -> None:
        self.classifier = BargeInClassifier(filler_words=('um', 'umm', 'uh', 'hmm'), echo_min_words=3, echo_overlap_ratio=0.72)

    def test_explicit_stop_interrupts_without_supervisor_turn(self) -> None:
        decision = self.classifier.classify('Stop', spoken_text='I can keep explaining if you want.')
        self.assertTrue(decision.interrupt)
        self.assertFalse(decision.route_after_interrupt)
        self.assertEqual(decision.reason, 'interrupt_phrase')

    def test_pause_is_not_an_explicit_interrupt_phrase(self) -> None:
        decision = self.classifier.classify('pause', spoken_text='I can keep explaining if you want.')
        self.assertTrue(decision.interrupt)
        self.assertTrue(decision.route_after_interrupt)
        self.assertEqual(decision.command_text, 'pause')
        self.assertEqual(decision.reason, 'owner_speech')

    def test_interrupt_prefix_can_carry_correction(self) -> None:
        decision = self.classifier.classify('Wait, use the other folder', spoken_text='I am opening the current folder now.')
        self.assertTrue(decision.interrupt)
        self.assertTrue(decision.route_after_interrupt)
        self.assertEqual(decision.command_text, 'use the other folder')

    def test_interrupt_phrase_is_detected_inside_sentence(self) -> None:
        decision = self.classifier.classify('I said wait, use the other folder', spoken_text='I am opening the current folder now.')
        self.assertTrue(decision.interrupt)
        self.assertTrue(decision.route_after_interrupt)
        self.assertEqual(decision.command_text, 'use the other folder')

    def test_filler_does_not_interrupt(self) -> None:
        decision = self.classifier.classify('Umm...', spoken_text='This is a long answer.')
        self.assertFalse(decision.interrupt)
        self.assertTrue(decision.filler_ignored)

    def test_multiword_speaker_echo_is_ignored(self) -> None:
        decision = self.classifier.classify('your computer uses short term memory', spoken_text="RAM is your computer's short term memory for active work.")
        self.assertFalse(decision.interrupt)
        self.assertTrue(decision.echo_ignored)

    def test_short_two_word_echo_is_ignored(self) -> None:
        decision = self.classifier.classify("that's all", spoken_text="And that's all you need for this step.")
        self.assertFalse(decision.interrupt)
        self.assertTrue(decision.echo_ignored)

    def test_substantive_non_echo_speech_interrupts_and_routes(self) -> None:
        decision = self.classifier.classify('Actually open the other project', spoken_text='The current project failed because a dependency is missing.')
        self.assertTrue(decision.interrupt)
        self.assertTrue(decision.route_after_interrupt)
        self.assertEqual(decision.command_text, 'Actually open the other project')

    def test_invalid_overlap_ratio_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BargeInClassifier(echo_overlap_ratio=0.2)
if __name__ == '__main__':
    unittest.main()
