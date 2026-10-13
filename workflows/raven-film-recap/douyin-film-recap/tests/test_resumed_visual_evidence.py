"""Deterministic evidence checks for manually edited Storyboards."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from douyin_film_recap.models import (
    HighlightCandidate, HighlightDocument, SceneAnalysisDocument, SceneAnalysisItem,
    SceneIndex, SceneUnit, SourceInfo, SourceManifest, Storyboard, StoryboardSegment, VisualReference,
    RecapPlan, RhythmProfile, StoryBundle, TranscriptDocument,
)
from douyin_film_recap.utils import fingerprint_json
from douyin_film_recap.visual_evidence import VisualEvidenceError, validate_storyboard_visual_evidence


class VisualEvidenceTests(unittest.TestCase):
    def setUp(self):
        source = SourceInfo(source_id="s", path="/synthetic/source.mp4", fingerprint="source-sha",
                            filename="source.mp4", duration=60, width=640, height=360, fps=25)
        self.manifest = SourceManifest(sources=[source], config_fingerprint="config")
        self.index = SceneIndex(units=[SceneUnit(unit_id="u", source_id="s", start=10, end=20)],
                                source_fingerprints={"s": "source-sha"}, detector="synthetic")
        self.analysis = SceneAnalysisDocument(provider="synthetic", model="none",
            items=[SceneAnalysisItem(unit_id="u")], unit_fingerprint=self.fingerprint())
        self.highlights = HighlightDocument(genre_profile="synthetic", weights={}, candidates=[],
                                            source_fingerprints={"s": "source-sha"})
        self.board = Storyboard(project_name="test", sources=[source], plan_fingerprint="plan",
            target_duration_sec=4, segments=[StoryboardSegment(segment_id="vo", beat_id="beat",
                mode="voiceover", title="test", text="Manual narration", audio_owner="narration",
                planned_duration_sec=4, notes="", visuals=[VisualReference(unit_id="u", source_id="s", start=11, end=15)])])

    def fingerprint(self):
        return fingerprint_json([unit.model_dump(mode="json") for unit in self.index.units])

    def validate(self):
        validate_storyboard_visual_evidence(self.board, self.manifest, self.highlights, self.index, self.analysis)

    def test_valid_analyzed_visual_is_accepted(self):
        self.validate()

    def test_missing_unknown_and_out_of_range_manual_references_are_rejected(self):
        for field, value, message in (("unit_id", None, "known"), ("unit_id", "invented", "known"),
                                      ("start", 9, "range"), ("end", 21, "range"),
                                      ("source_id", "other", "source"), ("highlight_id", "wrong", "highlight")):
            with self.subTest(field=field, value=value):
                visual = self.board.segments[0].visuals[0]
                original = getattr(visual, field)
                setattr(visual, field, value)
                with self.assertRaisesRegex(VisualEvidenceError, message) as raised:
                    self.validate()
                self.assertEqual(raised.exception.segment_id, "vo")
                setattr(visual, field, original)

    def test_analysis_must_be_bound_to_current_units(self):
        self.index.units[0].end = 21
        with self.assertRaisesRegex(VisualEvidenceError, "fingerprint"):
            self.validate()

    def test_scene_source_identity_must_match(self):
        self.index.source_fingerprints["s"] = "old-source"
        with self.assertRaisesRegex(VisualEvidenceError, "source identity"):
            self.validate()

    def test_unanalyzed_unit_is_not_accepted(self):
        self.analysis.items = []
        with self.assertRaisesRegex(VisualEvidenceError, "known"):
            self.validate()

    def test_duplicate_analysis_unit_is_rejected(self):
        self.analysis.items.append(self.analysis.items[0].model_copy(deep=True))
        with self.assertRaisesRegex(VisualEvidenceError, "Duplicate"):
            self.validate()

    def test_manually_registered_evidence_can_be_used_outside_writer_pool(self):
        self.index.units.append(SceneUnit(unit_id="manual", source_id="s", start=30, end=40))
        self.analysis.items.append(SceneAnalysisItem(unit_id="manual", visible_facts=["explicit observation"]))
        self.analysis.unit_fingerprint = self.fingerprint()
        self.board.segments[0].visuals = [VisualReference(unit_id="manual", source_id="s", start=31, end=35)]
        self.validate()

    def test_selected_highlight_reference_is_accepted_and_bound(self):
        self.highlights.candidates = [HighlightCandidate(highlight_id="h", source_id="s", start=30, end=40,
                                                         types=["action"], story_function="synthetic action", selected=True)]
        self.board.segments[0].visuals = [VisualReference(unit_id="highlight:h", highlight_id="h", source_id="s", start=31, end=35)]
        self.validate()
        self.highlights.source_fingerprints["s"] = "stale-source"
        with self.assertRaisesRegex(VisualEvidenceError, "Highlight source"):
            self.validate()

    def test_missing_evidence_is_not_a_silent_compatibility_bypass(self):
        with self.assertRaisesRegex(VisualEvidenceError, "requires"):
            validate_storyboard_visual_evidence(self.board, self.manifest, self.highlights, None, None)

    def test_original_only_board_does_not_require_vo_evidence(self):
        self.board.segments[0].mode = "original"
        self.board.segments[0].audio_owner = "action_sound"
        validate_storyboard_visual_evidence(self.board, self.manifest, self.highlights, None, None)

    def test_resumed_tts_rejects_invalid_visual_before_provider_or_tts(self):
        from douyin_film_recap.pipeline import FilmRecapPipeline
        pipeline = object.__new__(FilmRecapPipeline)
        pipeline._storyboard = lambda: self.board
        pipeline._manifest = lambda: self.manifest
        pipeline._highlights = lambda: self.highlights
        pipeline._scene_index = lambda: self.index
        pipeline._scene_analysis = lambda: self.analysis
        self.board.segments[0].visuals[0].unit_id = None
        with patch("douyin_film_recap.pipeline.synthesize_storyboard") as synthesize:
            with self.assertRaisesRegex(VisualEvidenceError, "known"):
                pipeline._stage_tts()
            synthesize.assert_not_called()

    def test_preflight_blocks_invalid_visual_and_skips_semantic_send(self):
        from douyin_film_recap.config import AppConfig
        from douyin_film_recap.qc import preflight_qc
        from unittest.mock import Mock
        client = Mock()
        self.board.segments[0].visuals[0].unit_id = "invented"
        report = preflight_qc(
            manifest=self.manifest, storyboard=self.board, highlights=self.highlights,
            transcript=TranscriptDocument(provider="synthetic", segments=[], source_fingerprints={"s": "source-sha"}),
            story=StoryBundle.model_validate({"character_registry": {"characters": []},
                "story_graph": {"main_plot": "synthetic", "events": []}, "knowledge_timeline": {"states": []}}),
            plan=RecapPlan(viewer_promise="test", pov="test", main_spine="test", hook_strategy="test",
                hook_highlight_id="none", target_duration_sec=4, duration_mode="highlight", original_ratio_target=0,
                ending_strategy="test", reveal_strategy="test", beats=[], rhythm=RhythmProfile()),
            config=AppConfig.model_validate({"models": {"llm_model": "test", "vlm_model": "test"}}),
            client=client, scene_index=self.index, scene_analysis=self.analysis,
        )
        self.assertEqual(report.status, "BLOCKED")
        finding = next(item for item in report.findings if item.rule_id == "VISUAL_EVIDENCE_INVALID")
        self.assertTrue(finding.blocking and finding.deterministic)
        self.assertEqual(finding.location.segment_id, "vo")
        client.chat_json.assert_not_called()

    def test_scene_evidence_changes_invalidate_tts_and_pre_qc_cache(self):
        from douyin_film_recap.pipeline import FilmRecapPipeline
        from douyin_film_recap.utils import write_json
        with TemporaryDirectory() as temporary:
            pipeline = object.__new__(FilmRecapPipeline)
            pipeline.work_dir = Path(temporary)
            pipeline.state = SimpleNamespace(config_fingerprint="config", input_fingerprint="source")
            write_json(pipeline.paths["storyboard"], self.board)
            write_json(pipeline.paths["scene_index"], self.index)
            write_json(pipeline.paths["scene_analysis"], self.analysis)
            before = {stage: pipeline._stage_inputs(stage) for stage in ("tts", "pre_qc")}
            self.analysis.items[0].visible_facts.append("a corrected observation")
            write_json(pipeline.paths["scene_analysis"], self.analysis)
            for stage, fingerprint in before.items():
                self.assertNotEqual(pipeline._stage_inputs(stage), fingerprint)

    def test_explicit_resume_fails_before_tts_and_records_stage(self):
        from douyin_film_recap.config import AppConfig
        from douyin_film_recap.pipeline import FilmRecapPipeline
        from douyin_film_recap.state import STAGES
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.mp4"
            source.write_bytes(b"synthetic source identity; never decoded")
            config = AppConfig.model_validate({"models": {"llm_model": "test", "vlm_model": "test"}})
            pipeline = FilmRecapPipeline(input_path=source, work_dir=Path(temporary) / "work", config=config)
            pipeline._storyboard = lambda: self.board
            pipeline._manifest = lambda: self.manifest
            pipeline._highlights = lambda: self.highlights
            pipeline._scene_index = lambda: self.index
            pipeline._scene_analysis = lambda: self.analysis
            pipeline._stage_inputs = lambda stage: stage
            pipeline._artifact_exists = lambda stage: True
            for stage in STAGES[:STAGES.index("tts")]:
                pipeline.state.stages[stage].status = "passed"
            pipeline.store.save(pipeline.state)
            self.board.segments[0].visuals[0].unit_id = "invented"
            with patch("douyin_film_recap.pipeline.synthesize_storyboard") as synthesize:
                with self.assertRaisesRegex(VisualEvidenceError, "known"):
                    pipeline.run(until="tts", from_stage="tts")
                synthesize.assert_not_called()
            self.assertEqual(pipeline.state.stages["tts"].status, "failed")
            self.assertFalse((pipeline.task_root / ".remote-intents").exists())


if __name__ == "__main__":
    unittest.main()
