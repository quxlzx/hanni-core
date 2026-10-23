"""Stick builder + firstboot logic tests."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("firstboot", ROOT / "scripts" / "firstboot.py")
firstboot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(firstboot)

from hanni.native.probe import Facts, decide  # noqa: E402


class FirstbootTests(unittest.TestCase):
    def test_candidates_largest_first_ram_fit(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for m in firstboot.MODEL_FOR_TIER.values():
                (d / m).write_text("x")
            big = Facts(ram_gb=32, gpus=[])
            names = firstboot.candidates(big, d)
            self.assertEqual(names[0], firstboot.MODEL_FOR_TIER["large"])
            self.assertEqual(len(names), 3)

    def test_small_ram_drops_large(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for m in firstboot.MODEL_FOR_TIER.values():
                (d / m).write_text("x")
            small = Facts(ram_gb=6, gpus=[])
            names = firstboot.candidates(small, d)
            self.assertNotIn(firstboot.MODEL_FOR_TIER["large"], names)

    def test_measured_speed_cascades_tier(self):
        # 7B measured at 5 tok/s on this host -> decide says none -> cascade
        trial = Facts(ram_gb=22, measured_decode_tps=5.0)
        self.assertEqual(decide(trial)["tier"], "none")
        trial2 = Facts(ram_gb=22, measured_decode_tps=23.0)
        self.assertNotEqual(decide(trial2)["tier"], "none")

    def test_model_files_match_probe_names(self):
        # firstboot's tier->file map must cover every tier decide() can pick
        # except 'full' (Strata host, not a stick tier)
        for tier in ("large", "small", "pocket"):
            self.assertIn(tier, firstboot.MODEL_FOR_TIER)
            self.assertIn(firstboot.MODEL_GB[firstboot.MODEL_FOR_TIER[tier]], {1.6, 3.2, 5.6})


if __name__ == "__main__":
    unittest.main()
