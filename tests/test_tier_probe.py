"""Tier selection tests: pure decide() over synthetic fleet facts."""
import unittest

from hanni.native.probe import Facts, decide


def facts(ram, vram=0.0, cores=4, measured=None):
    gpus = [{"name": "test", "vram_gb": vram}] if vram else []
    return Facts(ram_gb=ram, cores=cores, gpus=gpus, disk_free_gb=100.0, measured_decode_tps=measured)


class TierDecisionTests(unittest.TestCase):
    def test_wonyoung_class_gets_full(self):
        self.assertEqual(decide(facts(80, 32))["tier"], "full")

    def test_gaming_pc_gets_large(self):
        self.assertEqual(decide(facts(16, 12))["tier"], "large")

    def test_yunjin_class_gets_large_via_ram(self):
        self.assertEqual(decide(facts(22, 8))["tier"], "large")

    def test_jeongyeon_class_gets_small(self):
        self.assertEqual(decide(facts(14, 0))["tier"], "small")

    def test_thin_client_gets_pocket(self):
        self.assertEqual(decide(facts(7, 0))["tier"], "pocket")

    def test_tiny_box_gets_none(self):
        self.assertEqual(decide(facts(3, 0))["tier"], "none")

    def test_measurement_overrides_specs(self):
        # a box that specs as 'large' but measures 2 tok/s must drop to remote
        self.assertEqual(decide(facts(16, 12, measured=2.0))["tier"], "none")

    def test_measurement_confirms_small(self):
        self.assertEqual(decide(facts(14, 0, measured=17.9))["tier"], "small")

    def test_model_names_match_tiers(self):
        self.assertEqual(decide(facts(80, 32))["model"], "wonyoung-strata")
        self.assertEqual(decide(facts(7, 0))["model"], "minicpm5-2b")
        self.assertIsNone(decide(facts(3, 0))["model"])


if __name__ == "__main__":
    unittest.main()
