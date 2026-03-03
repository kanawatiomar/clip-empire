import json
import tempfile
import unittest
from pathlib import Path

from engine.ingest.base import RawClip
from engine.ingest.safety import ClipPolicyFilter
from engine.ingest.trend_radar import TrendRadar
from engine.transform.ab import generate_title_pair


class FeatureSmokeTests(unittest.TestCase):
    def test_trend_radar_augments_sources(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "signals.json"
            p.write_text(json.dumps({"*": [{"keyword": "btc crash"}]}), encoding="utf-8")
            radar = TrendRadar(str(p))
            out = radar.augment_sources("market_meltdowns", [{"url": "a", "priority": 5}])
            self.assertGreaterEqual(len(out), 2)

    def test_policy_filter_blocks_terms(self):
        clip = RawClip(title="graphic violence compilation")
        f = ClipPolicyFilter(policy_path="does-not-exist.json")
        self.assertFalse(f.allow(clip))

    def test_ab_generation_has_two_variants(self):
        a, b = generate_title_pair("market_meltdowns")
        self.assertTrue(a)
        self.assertTrue(b)
        self.assertNotEqual(a, "")


if __name__ == "__main__":
    unittest.main()
