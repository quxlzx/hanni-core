from __future__ import annotations
import json
import subprocess
import unittest
from unittest import mock
from hanni.speech.tts import TtsError, WindowsSapiTts, split_for_speech

class TtsChunkingTests(unittest.TestCase):

    def test_empty_text_produces_no_chunks(self) -> None:
        self.assertEqual(split_for_speech('   '), ())

    def test_prefers_sentence_boundaries(self) -> None:
        chunks = split_for_speech('First sentence. Second sentence. Third sentence.', max_chars=40)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(' '.join(chunks), 'First sentence. Second sentence. Third sentence.')
        self.assertTrue(all((len(c) <= 40 for c in chunks)))

    def test_long_sentence_is_bounded(self) -> None:
        text = 'This is a deliberately long sentence with enough words to require several chunks for local speech synthesis without losing any meaningful words'
        chunks = split_for_speech(text, max_chars=50)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all((len(c) <= 50 for c in chunks)))
        self.assertEqual(' '.join(chunks), text)

    def test_rejects_tiny_chunk_limit(self) -> None:
        with self.assertRaises(ValueError):
            split_for_speech('hello', max_chars=20)

class WindowsSapiTests(unittest.TestCase):

    def test_configuration_validation(self) -> None:
        with self.assertRaises(ValueError):
            WindowsSapiTts(rate=11, powershell='powershell.exe')
        with self.assertRaises(ValueError):
            WindowsSapiTts(volume=101, powershell='powershell.exe')

    def test_speak_sends_text_via_stdin_json_not_command_interpolation(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout='', stderr='')
        with mock.patch('hanni.speech.tts.os.name', 'nt'), mock.patch('hanni.speech.tts.subprocess.run', return_value=completed) as run_mock:
            engine = WindowsSapiTts(voice='Test Voice', rate=1, volume=80, powershell='powershell.exe')
            dangerous = 'Hello "there"; Write-Host hacked'
            engine.speak(dangerous)
        kwargs = run_mock.call_args.kwargs
        payload = json.loads(kwargs['input'])
        self.assertEqual(payload['voice'], 'Test Voice')
        self.assertEqual(payload['rate'], 1)
        self.assertEqual(payload['volume'], 80)
        self.assertEqual(payload['chunks'], [dangerous])
        self.assertNotIn('Write-Host hacked', ' '.join(run_mock.call_args.args[0]))

    def test_non_windows_backend_fails_cleanly(self) -> None:
        with mock.patch('hanni.speech.tts.os.name', 'posix'):
            engine = WindowsSapiTts(powershell='powershell.exe')
            with self.assertRaisesRegex(TtsError, 'only available on Windows'):
                engine.speak('hello')
if __name__ == '__main__':
    unittest.main()

class _FakeStdin:

    def __init__(self) -> None:
        self.data = ''
        self.closed = False

    def write(self, value: str) -> None:
        self.data += value

    def close(self) -> None:
        self.closed = True

class _FakePopen:

    def __init__(self) -> None:
        self.stdin = _FakeStdin()
        self.stderr = None
        self.returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = 0

    def wait(self, timeout=None):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

class WindowsSapiCancellablePlaybackTests(unittest.TestCase):

    def test_start_returns_cancellable_playback_and_uses_stdin_json(self) -> None:
        fake = _FakePopen()
        with mock.patch('hanni.speech.tts.os.name', 'nt'), mock.patch('hanni.speech.tts.subprocess.Popen', return_value=fake):
            engine = WindowsSapiTts(voice='Test Voice', powershell='powershell.exe')
            playback = engine.start('Hello "there"')
        self.assertTrue(playback.active)
        payload = json.loads(fake.stdin.data)
        self.assertEqual(payload['chunks'], ['Hello "there"'])
        self.assertTrue(fake.stdin.closed)
        playback.stop()
        self.assertFalse(playback.active)
        self.assertTrue(fake.terminated)
