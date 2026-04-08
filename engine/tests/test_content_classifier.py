import unittest

from engine.classification import classify_clip
from engine.ingest.base import RawClip


class ContentClassifierTests(unittest.TestCase):
    def test_detects_fortnite_clutch_from_title_and_creator(self):
        clip = RawClip(
            title="Tfue wins the 1v3 clutch in Fortnite ranked",
            creator="tfue",
            source_url="https://www.twitch.tv/tfue/clip/abc",
            metadata={},
        )
        profile = classify_clip(clip, channel_name="arc_highlightz")
        self.assertEqual(profile.primary_game, "fortnite")
        self.assertEqual(profile.primary_mode, "clutch")
        self.assertIn("fortnite", profile.labels)
        self.assertIn("clutch", profile.labels)

    def test_detects_reaction_from_transcript_style_metadata(self):
        clip = RawClip(
            title="Moist reacts to the weirdest clip ever",
            creator="moistcr1tikal",
            metadata={
                "transcript_selected": True,
                "segment_reason": "funny reaction and surprise payoff",
                "source_video_title": "Reacting to bizarre internet videos",
            },
        )
        profile = classify_clip(clip, channel_name="unfiltered_clips")
        self.assertEqual(profile.primary_mode, "reaction")
        self.assertIn("funny", profile.labels)

    def test_detects_podcast_style_content(self):
        clip = RawClip(
            title="Podcast guest tells the craziest startup story",
            creator="founder podcast",
            metadata={"description": "full interview episode clip"},
        )
        profile = classify_clip(clip, channel_name="self_made_clips")
        self.assertEqual(profile.primary_mode, "podcast")
        self.assertIsNone(profile.primary_game)


if __name__ == "__main__":
    unittest.main()
