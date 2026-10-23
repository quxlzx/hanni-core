from __future__ import annotations
import unittest
from hanni.speech.relevance import SpeechRelevanceClassifier

class FakeClock:

    def __init__(self, value: float=100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds

class RelevanceClassifierTests(unittest.TestCase):

    def setUp(self) -> None:
        self.clock = FakeClock()
        self.classifier = SpeechRelevanceClassifier(clock=self.clock, engagement_seconds=0.0)

    def test_explicit_wake_name_is_relevant_and_engages(self) -> None:
        decision = self.classifier.classify('Hanni, open VS Code.')
        self.assertTrue(decision.relevant)
        self.assertTrue(decision.wake_word_detected)
        self.assertTrue(decision.engaged)
        self.assertEqual(decision.command_text, 'open VS Code')
        self.assertEqual(decision.reason, 'wake_name')

    def test_real_whisper_ani_variant_is_a_wake_alias(self) -> None:
        decision = self.classifier.classify("Ani, what's the weather today?")
        self.assertTrue(decision.relevant)
        self.assertTrue(decision.wake_word_detected)
        self.assertEqual(decision.command_text, "what's the weather today")

    def test_honey_can_wake_from_middle_of_utterance(self) -> None:
        decision = self.classifier.classify('Hey honey, how are you doing?')
        self.assertTrue(decision.relevant)
        self.assertTrue(decision.wake_word_detected)
        self.assertEqual(decision.command_text, 'Hey how are you doing')

    def test_alias_is_token_bounded_not_substring(self) -> None:
        self.assertFalse(self.classifier.classify('The animal is outside.').relevant)
        self.assertFalse(self.classifier.classify('Hannibal is a name.').relevant)

    def test_follow_up_remains_relevant_until_explicit_disengage(self) -> None:
        self.classifier.classify('Hanni, are you there?')
        self.clock.advance(60 * 60 * 8)
        decision = self.classifier.classify('Open the project.')
        self.assertTrue(decision.relevant)
        self.assertTrue(decision.follow_up)
        self.assertFalse(decision.wake_word_detected)
        self.assertEqual(decision.reason, 'engaged_follow_up')

    def test_optional_positive_timeout_mode_still_supported(self) -> None:
        classifier = SpeechRelevanceClassifier(clock=self.clock, engagement_seconds=20.0)
        classifier.classify('Hanni, hello')
        self.clock.advance(20.1)
        self.assertFalse(classifier.classify('Open the project.').relevant)

    def test_background_speech_is_ignored_when_idle(self) -> None:
        decision = self.classifier.classify('The coffee machine is making a loud noise.')
        self.assertFalse(decision.relevant)
        self.assertEqual(decision.reason, 'background')

    def test_disengage_phrase_clears_engagement_but_listener_can_wake_again(self) -> None:
        self.classifier.classify('Hanni, hello')
        decision = self.classifier.classify("That's all.")
        self.assertFalse(decision.relevant)
        self.assertTrue(decision.disengaged)
        self.assertFalse(self.classifier.is_engaged())
        self.assertFalse(self.classifier.classify('Open it.').relevant)
        self.assertTrue(self.classifier.classify('Hanni, come back.').relevant)

    def test_multiple_explicit_disengage_phrases(self) -> None:
        for phrase in ("we're done", 'stand by', 'go quiet', 'stop responding'):
            classifier = SpeechRelevanceClassifier()
            classifier.classify('Hanni, hello')
            decision = classifier.classify(phrase)
            self.assertTrue(decision.disengaged, phrase)
            self.assertFalse(classifier.is_engaged(), phrase)

    def test_wake_plus_disengage_does_not_reengage(self) -> None:
        decision = self.classifier.classify("Hanni, that's all.")
        self.assertFalse(decision.relevant)
        self.assertTrue(decision.disengaged)
        self.assertFalse(self.classifier.is_engaged())

    def test_wake_only_utterance_is_still_relevant(self) -> None:
        decision = self.classifier.classify('Hanni')
        self.assertTrue(decision.relevant)
        self.assertEqual(decision.command_text, 'Hanni')

    def test_filler_only_is_ignored_while_idle(self) -> None:
        for filler in ('umm', 'uhh...', 'hmm', 'mm', 'erm'):
            decision = self.classifier.classify(filler)
            self.assertFalse(decision.relevant, filler)
            self.assertTrue(decision.filler_ignored, filler)
            self.assertEqual(decision.reason, 'filler_only')

    def test_filler_only_is_ignored_while_engaged_without_disengaging(self) -> None:
        self.classifier.classify('Hanni')
        decision = self.classifier.classify('Hmm...')
        self.assertFalse(decision.relevant)
        self.assertTrue(decision.filler_ignored)
        self.assertTrue(decision.engaged)
        self.assertTrue(self.classifier.is_engaged())
        self.assertTrue(self.classifier.classify('Tell me something.').relevant)

    def test_leading_fillers_are_stripped_from_meaningful_followup(self) -> None:
        self.classifier.classify('Hanni')
        decision = self.classifier.classify('Umm, can you explain that?')
        self.assertTrue(decision.relevant)
        self.assertEqual(decision.command_text, 'can you explain that?')

    def test_leading_filler_does_not_block_wake(self) -> None:
        decision = self.classifier.classify('Umm, Hanni, open VS Code.')
        self.assertTrue(decision.wake_word_detected)
        self.assertEqual(decision.command_text, 'open VS Code')

    def test_old_recent_turn_compatibility_remains(self) -> None:
        decision = self.classifier.classify('What should I do next?', recent_turns=['Hanni, open the repo.'])
        self.assertTrue(decision.relevant)
        self.assertTrue(decision.follow_up)
        self.assertEqual(decision.reason, 'recent_turn_follow_up')

    def test_empty_text_is_ignored(self) -> None:
        self.assertFalse(self.classifier.classify('   ').relevant)

    def test_invalid_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SpeechRelevanceClassifier(wake_names=())
        with self.assertRaises(ValueError):
            SpeechRelevanceClassifier(engagement_seconds=-1)

    def test_honey_at_start_is_accepted_as_stt_wake_alias(self) -> None:
        classifier = SpeechRelevanceClassifier()
        decision = classifier.classify('Honey, how are you?')
        self.assertTrue(decision.relevant)
        self.assertTrue(decision.wake_word_detected)
        self.assertEqual(decision.command_text, 'how are you')

    def test_configured_wake_alias_is_detected_anywhere(self) -> None:
        classifier = SpeechRelevanceClassifier()
        decision = classifier.classify('I told her, honey, come here.')
        self.assertTrue(decision.relevant)
        self.assertTrue(decision.wake_word_detected)
        self.assertEqual(decision.command_text, 'I told her come here')

    def test_wake_name_at_end_of_sentence_activates(self) -> None:
        classifier = SpeechRelevanceClassifier()
        decision = classifier.classify('Can you open VS Code, Hanni?')
        self.assertTrue(decision.relevant)
        self.assertTrue(decision.wake_word_detected)
        self.assertEqual(decision.command_text, 'Can you open VS Code')

    def test_passive_acknowledgements_are_ignored_but_keep_engagement(self) -> None:
        self.classifier.classify('Hanni')
        for text in ('Thank you.', 'Yeah.', 'Okay', 'Got it'):
            decision = self.classifier.classify(text)
            self.assertFalse(decision.relevant, text)
            self.assertTrue(decision.acknowledgement_ignored, text)
            self.assertTrue(self.classifier.is_engaged(), text)

    def test_bye_disengages(self) -> None:
        self.classifier.classify('Hanni')
        decision = self.classifier.classify('Bye.')
        self.assertTrue(decision.disengaged)
        self.assertFalse(self.classifier.is_engaged())
if __name__ == '__main__':
    unittest.main()
