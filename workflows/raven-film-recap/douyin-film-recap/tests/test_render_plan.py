"""Pure planner regression tests. Also runnable without pytest via unittest."""
from __future__ import annotations

import copy
from fractions import Fraction
import unittest

from douyin_film_recap.config import AppConfig, RenderConfig
from douyin_film_recap.models import SourceInfo, Storyboard, StoryboardSegment, VisualReference
from douyin_film_recap.render_contracts import RenderContractError, canonical_bytes, digest, quantize, rational
from douyin_film_recap.render_plan import RENDER_FIELDS, SEGMENT_FIELDS, compile_render_plan


class RenderPlanTests(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig(models={"llm_model": "unused", "vlm_model": "unused"})
        self.sources = {"a": {"sha256": "a" * 64, "size": 100}, "b": {"sha256": "b" * 64, "size": 200}}
        self.toolchain = {"verified": True, "ffmpeg_sha256": "f" * 64, "ffprobe_sha256": "f" * 64, "version": "fixture", "implementation_digest": "e" * 64}
        self.board = Storyboard(project_name="fixture", plan_fingerprint="p", target_duration_sec=2,
            sources=[SourceInfo(source_id=sid, path=f"/not-read/{sid}.mp4", fingerprint=v["sha256"],
                size_bytes=v["size"], filename=sid, duration=100, width=320, height=240, fps=24)
                for sid, v in self.sources.items()],
            segments=[StoryboardSegment(segment_id=f"s{i}", beat_id="b", mode="original", title="fixture",
                text="", visuals=[VisualReference(source_id=sid, start=0, end=1)],
                audio_owner="action_sound", planned_duration_sec=1, notes="")
                for i, sid in enumerate(self.sources)])

    def plan(self, board=None, config=None, **kwargs):
        return compile_render_plan(board or self.board, config or self.config,
            source_identities=self.sources, toolchain=self.toolchain, **kwargs)

    @staticmethod
    def nodes(plan):
        return {node["node_id"]: node for node in plan["nodes"]}

    def test_pure_deterministic_no_mutation(self):
        before = self.board.model_dump()
        self.assertEqual(self.plan(), self.plan())
        self.assertEqual(self.board.model_dump(), before)

    def test_exhaustive_known_field_inventory(self):
        self.assertFalse(set(RenderConfig.model_fields) - set(RENDER_FIELDS))
        self.assertFalse(set(StoryboardSegment.model_fields) - set(SEGMENT_FIELDS))

    def test_unrelated_source_change_does_not_change_other_segment(self):
        prior = self.nodes(self.plan())
        self.sources["b"]["sha256"] = "c" * 64
        self.board.sources[1].fingerprint = "c" * 64
        changed = self.nodes(self.plan())
        self.assertEqual(prior["segment_av:s0"]["semantic_key"], changed["segment_av:s0"]["semantic_key"])
        self.assertNotEqual(prior["segment_av:s1"]["semantic_key"], changed["segment_av:s1"]["semantic_key"])

    def test_path_and_source_order_are_not_content_keys(self):
        before = self.nodes(self.plan())
        self.board.sources.reverse()
        for source in self.board.sources:
            source.path = "/elsewhere/" + source.filename
        after = self.nodes(self.plan())
        for sid in ("s0", "s1"):
            self.assertEqual(before[f"segment_av:{sid}"]["semantic_key"], after[f"segment_av:{sid}"]["semantic_key"])

    def test_title_notes_change_review_not_media(self):
        before = self.plan()
        self.board.segments[0].notes = "different evidence"
        self.board.project_name = "renamed"
        after = self.plan(previous_plan=before)
        self.assertEqual(self.nodes(before)["segment_av:s0"]["semantic_key"], self.nodes(after)["segment_av:s0"]["semantic_key"])
        self.assertNotEqual(before["review_binding"], after["review_binding"])
        self.assertEqual(self.nodes(after)["segment_av:s0"]["action"], "reuse_candidate")

    def test_subtitle_style_only_affects_finalization(self):
        before = self.nodes(self.plan())
        self.config.render.subtitle_font_size += 2
        after = self.nodes(self.plan())
        self.assertEqual(before["segment_av:s0"]["semantic_key"], after["segment_av:s0"]["semantic_key"])
        self.assertEqual(before["cue_local:s0"]["semantic_key"], after["cue_local:s0"]["semantic_key"])
        self.assertNotEqual(before["finalize"]["provisional_key"], after["finalize"]["provisional_key"])

    def test_encoder_change_affects_segment(self):
        before = self.nodes(self.plan())
        self.config.render.crf += 1
        self.assertNotEqual(before["segment_av:s0"]["semantic_key"], self.nodes(self.plan())["segment_av:s0"]["semantic_key"])

    def test_unused_blur_and_bed_changes_do_not_dirty_original_crop(self):
        self.config.render.layout = "center_crop"
        before = self.nodes(self.plan())
        self.config.render.blur_sigma += 5
        self.config.render.original_bed_db -= 5
        self.assertEqual(before["segment_av:s0"]["semantic_key"], self.nodes(self.plan())["segment_av:s0"]["semantic_key"])

    def test_reorder_changes_placement_not_local_content(self):
        before = self.plan()
        self.board.segments.reverse()
        after = self.plan()
        self.assertEqual(self.nodes(before)["segment_av:s0"]["semantic_key"], self.nodes(after)["segment_av:s0"]["semantic_key"])
        self.assertNotEqual(self.nodes(before)["assembly"]["provisional_key"], self.nodes(after)["assembly"]["provisional_key"])

    def test_length_change_moves_later_segment_not_local_key(self):
        before = self.plan()
        self.board.segments[0].visuals[0].end = 1.5
        after = self.plan()
        self.assertEqual(self.nodes(before)["segment_av:s1"]["semantic_key"], self.nodes(after)["segment_av:s1"]["semantic_key"])
        self.assertEqual(after["timeline"]["expected"][1]["start_frame"], 45)
        self.assertEqual(after["timeline"]["expected"][1]["start_sample"], 72000)

    def test_voice_identity_and_speed_are_consumed_text_is_cue(self):
        segment = self.board.segments[0]
        segment.mode, segment.audio_owner = "voiceover", "narration"
        segment.audio_duration_sec = 1
        voices = {"s0": {"sha256": "d" * 64, "size": 10}}
        first = self.nodes(self.plan(audio_identities=voices))
        segment.text = "新旁白"
        second = self.nodes(self.plan(audio_identities=voices))
        self.assertEqual(first["segment_av:s0"]["semantic_key"], second["segment_av:s0"]["semantic_key"])
        self.assertNotEqual(first["cue_local:s0"]["semantic_key"], second["cue_local:s0"]["semantic_key"])
        voices["s0"]["sha256"] = "e" * 64
        third = self.nodes(self.plan(audio_identities=voices))
        self.assertNotEqual(second["segment_av:s0"]["semantic_key"], third["segment_av:s0"]["semantic_key"])
        segment.audio_speed = 1.01
        self.assertNotEqual(third["segment_av:s0"]["semantic_key"], self.nodes(self.plan(audio_identities=voices))["segment_av:s0"]["semantic_key"])

    def test_unknown_parameter_forces_provisional(self):
        self.config.render.unknown_effect = "global-animation"
        node = self.nodes(self.plan())["segment_av:s0"]
        self.assertIsNone(node["semantic_key"])
        self.assertIn("UNCLASSIFIED_PARAMETER", node["reason_codes"])

    def test_missing_toolchain_is_not_reusable(self):
        self.toolchain = {}
        self.assertIsNone(self.nodes(self.plan())["segment_av:s0"]["semantic_key"])

    def test_source_identity_mismatch_is_rejected(self):
        self.sources["a"]["sha256"] = "c" * 64
        with self.assertRaisesRegex(RenderContractError, "SOURCE_BINDING_CHANGED"):
            self.plan()

    def test_descendants_are_provisional_until_realized(self):
        plan = self.plan()
        self.assertIsNone(self.nodes(plan)["assembly"]["semantic_key"])
        artifacts = {}
        for node in plan["nodes"]:
            if node["kind"] == "segment_av":
                artifacts[node["node_id"]] = {"semantic_key": node["semantic_key"], "sha256": "1" * 64,
                    "size": 123, "media_contract": {"frame_count": 30, "fps": {"num": 30, "den": 1}, "sample_count": 48000},
                    "verification": {"hash_checked": True, "probe_checked": True, "decode_checked": True}}
        realized = self.plan(realized_artifacts=artifacts)
        self.assertEqual(realized["timeline"]["placement_state"], "realized")
        self.assertIsNotNone(self.nodes(realized)["assembly"]["semantic_key"])
        self.assertIsNone(self.nodes(realized)["finalize"]["semantic_key"])
        artifacts["segment_av:s0"]["sha256"] = "2" * 64
        self.assertNotEqual(self.nodes(realized)["assembly"]["semantic_key"], self.nodes(self.plan(realized_artifacts=artifacts))["assembly"]["semantic_key"])

    def test_realized_requires_verification(self):
        node = self.nodes(self.plan())["segment_av:s0"]
        with self.assertRaisesRegex(RenderContractError, "REALIZED_UNVERIFIED"):
            self.plan(realized_artifacts={node["node_id"]: {"semantic_key": node["semantic_key"]}})

    def test_thousand_boundaries_quantize_cumulatively(self):
        self.config.render.fps = "30000/1001"
        self.board.segments = [self.board.segments[0].model_copy(deep=True) for _ in range(1000)]
        for i, segment in enumerate(self.board.segments):
            segment.segment_id = str(i)
            segment.visuals[0].end = 0.01
        timeline = self.plan()["timeline"]["expected"]
        self.assertEqual(timeline[-1]["end_frame"], 300)
        self.assertEqual(timeline[-1]["end_sample"], 480000)
        self.assertEqual(timeline[-1]["end"], {"num": 10, "den": 1})

    def test_invalid_rational_components_rejected(self):
        for bad in ({"num": 1.5, "den": 2}, {"num": True, "den": 2}, {"num": 1, "den": 0}):
            with self.assertRaises(RenderContractError):
                rational(bad)

    def test_duplicate_segment_ids_rejected(self):
        self.board.segments[1].segment_id = "s0"
        with self.assertRaises(ValueError):
            self.plan()

    def test_non_finite_values_rejected(self):
        with self.assertRaises(RenderContractError):
            canonical_bytes({"bad": float("nan")})
        self.assertEqual(quantize(Fraction(1, 2)), 1)
        self.assertNotEqual(digest({}), digest({"x": None}))


if __name__ == "__main__":
    unittest.main()
