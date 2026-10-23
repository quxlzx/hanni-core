from __future__ import annotations
import unittest
from hanni.speech.live import PUMP_FINISHED, TranscriptPump
from hanni.speech.types import TranscriptRecord

class FakePipeline:

    def run(self, *, stop_event=None):
        yield TranscriptRecord('one', 0.0, 0.5)
        yield TranscriptRecord('two', 0.5, 1.0)

class TranscriptPumpTests(unittest.TestCase):

    def test_pipeline_runs_in_background_and_finishes(self) -> None:
        pump = TranscriptPump(FakePipeline())
        pump.start()
        first = pump.get(timeout=1)
        second = pump.get(timeout=1)
        done = pump.get(timeout=1)
        self.assertEqual(first.text, 'one')
        self.assertEqual(second.text, 'two')
        self.assertIs(done, PUMP_FINISHED)
        pump.stop()
if __name__ == '__main__':
    unittest.main()
