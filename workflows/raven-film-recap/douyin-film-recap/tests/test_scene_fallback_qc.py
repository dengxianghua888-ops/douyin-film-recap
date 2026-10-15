"""Scene detector fallback remains visible to QC and delivery."""
import unittest

from douyin_film_recap.config import AppConfig
from douyin_film_recap.models import (
    HighlightDocument, RecapPlan, RhythmProfile, SceneDetectionMetadata, SceneIndex,
    SourceManifest, StoryBundle, Storyboard, TranscriptDocument,
)
from douyin_film_recap.qc import preflight_qc, report_status


class SceneFallbackQCTests(unittest.TestCase):
    def report(self, detection):
        # Empty synthetic content isolates provenance, not film acceptance.
        return preflight_qc(
            manifest=SourceManifest(sources=[], config_fingerprint="test"),
            transcript=TranscriptDocument(provider="test", segments=[], source_fingerprints={}),
            story=StoryBundle.model_validate({"character_registry": {"characters": []},
                "story_graph": {"main_plot": "test", "events": []}, "knowledge_timeline": {"states": []}}),
            highlights=HighlightDocument(genre_profile="test", candidates=[], weights={}, source_fingerprints={}),
            plan=RecapPlan(viewer_promise="test", pov="test", main_spine="test", hook_strategy="test",
                hook_highlight_id="none", target_duration_sec=10, duration_mode="highlight", original_ratio_target=0,
                ending_strategy="test", reveal_strategy="test", beats=[], rhythm=RhythmProfile()),
            storyboard=Storyboard(project_name="test", sources=[], plan_fingerprint="test",
                                  target_duration_sec=10, segments=[]),
            config=AppConfig.model_validate({"models": {"llm_model": "test", "vlm_model": "test"}}),
            scene_index=SceneIndex(units=[], source_fingerprints={}, detector="test", source_detection={"s": detection}),
        )

    def test_fallback_is_nonblocking_and_degraded(self):
        detection = SceneDetectionMetadata(detector_requested="content", detector_used="fixed_windows",
            fallback_reason="synthetic detector unavailable", boundary_confidence="unknown")
        report = self.report(detection)
        findings = [item for item in report.findings if item.rule_id == "SCENE_DETECTION_FALLBACK"]
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].deterministic)
        self.assertFalse(findings[0].blocking)
        self.assertEqual(findings[0].location.source_id, "s")
        self.assertEqual(findings[0].evidence, detection.model_dump(mode="json"))
        self.assertEqual(report_status(findings), "DEGRADED")

    def test_successful_detection_does_not_invent_a_fallback(self):
        report = self.report(SceneDetectionMetadata(detector_requested="content", detector_used="content",
                                                   boundary_confidence="detector_estimated"))
        self.assertFalse(any(item.rule_id == "SCENE_DETECTION_FALLBACK" for item in report.findings))


if __name__ == "__main__":
    unittest.main()
