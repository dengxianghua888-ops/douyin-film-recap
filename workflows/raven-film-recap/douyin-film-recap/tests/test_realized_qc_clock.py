import unittest
from douyin_film_recap.config import AppConfig
from douyin_film_recap.models import Storyboard, StoryboardSegment, VisualReference
from douyin_film_recap.qc import _checked_realized_timeline

class RealizedQCClockTests(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig(models={"llm_model":"unused", "vlm_model":"unused"})
        self.board = Storyboard(project_name="fixture", sources=[], plan_fingerprint="p", target_duration_sec=2,
            segments=[StoryboardSegment(segment_id=f"s{i}", beat_id="b", mode="original", title="",
                text="", audio_owner="action_sound", notes="", planned_duration_sec=1,
                visuals=[VisualReference(source_id="source", start=i, end=i+1)]) for i in range(2)])
    def test_no_realized_retains_legacy(self):
        self.assertIsNone(_checked_realized_timeline(self.board, self.config))
    def test_exact_realized_clock(self):
        rows = [{"segment_id":f"s{i}", "start":i, "end":i+1} for i in range(2)]
        self.board.output["realized_timeline"] = rows
        self.assertEqual(rows, _checked_realized_timeline(self.board, self.config))
    def test_forged_duration_cannot_override_authority(self):
        self.board.output["realized_timeline"] = [{"segment_id":"s0", "start":0,"end":10},
                                                  {"segment_id":"s1", "start":10,"end":11}]
        with self.assertRaisesRegex(ValueError,"TOLERANCE"):
            _checked_realized_timeline(self.board, self.config)
    def test_reorder_is_rejected(self):
        self.board.output["realized_timeline"] = [{"segment_id":"s1", "start":0,"end":1},
                                                  {"segment_id":"s0", "start":1,"end":2}]
        with self.assertRaises(ValueError):
            _checked_realized_timeline(self.board, self.config)

if __name__ == "__main__": unittest.main()
