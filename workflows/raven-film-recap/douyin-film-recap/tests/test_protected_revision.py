"""Protected revision regressions, executable without pytest as well as under CI."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from douyin_film_recap.config import AppConfig
from douyin_film_recap.models import (
    CharacterRegistry, HighlightDocument, KnowledgeTimeline, QCReport, RecapBeat,
    RecapPlan, RhythmProfile, SceneAnalysisDocument, SceneAnalysisItem, SceneIndex,
    SceneUnit, SourceInfo, SourceManifest, StoryGraph, Storyboard, StoryboardSegment,
    TranscriptDocument,
)
from douyin_film_recap.pipeline import FilmRecapPipeline, StageBlocked
from douyin_film_recap.revision import BOARD, adopt_revision, freeze_revision
from douyin_film_recap.utils import fingerprint_json, write_json
from douyin_film_recap import workspace as w


class ProtectedRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source_path = self.root / "source.mp4"
        self.source_path.write_bytes(b"synthetic source identity; never decoded")
        self.config = AppConfig.model_validate({"models": {"llm_model": "test", "vlm_model": "test"}})
        self.pipeline = FilmRecapPipeline(input_path=self.source_path, work_dir=self.root / "work", config=self.config)
        self.work = self.pipeline.work_dir
        source = SourceInfo(source_id="source", path=str(self.source_path),
            fingerprint=w.sha(self.source_path), size_bytes=self.source_path.stat().st_size,
            filename="source.mp4", duration=10, width=640, height=360, fps=30)
        self.source = source
        self.board = Storyboard(project_name="fixture", sources=[source], plan_fingerprint="plan",
            target_duration_sec=2, opaque_metadata={"vendor": [1, 2]}, segments=[
                StoryboardSegment(segment_id="one", beat_id="beat", mode="original", title="Original",
                    text="", notes="original note", audio_owner="ambience", planned_duration_sec=2,
                    visuals=[{"source_id": "source", "start": 0, "end": 2}],
                    opaque_field={"do_not_drop": True})]).model_dump(mode="json")
        index = SceneIndex(units=[SceneUnit(unit_id="unit", source_id="source", start=0, end=10)],
            source_fingerprints={"source": source.fingerprint}, detector="synthetic")
        self.artifacts = {
            "00_source_manifest.json": SourceManifest(sources=[source], config_fingerprint=self.config.fingerprint()),
            "01_transcript.json": TranscriptDocument(provider="synthetic", segments=[], source_fingerprints={"source": source.fingerprint}),
            "02_scene_index.json": index,
            "03_scene_analysis.json": SceneAnalysisDocument(provider="synthetic", model="none", items=[SceneAnalysisItem(unit_id="unit")], unit_fingerprint=fingerprint_json([u.model_dump(mode="json") for u in index.units])),
            "04_character_registry.json": CharacterRegistry(characters=[]),
            "05_story_graph.json": StoryGraph(main_plot="fixture", events=[]),
            "06_knowledge_timeline.json": KnowledgeTimeline(states=[]),
            "07_highlight_candidates.json": HighlightDocument(genre_profile="synthetic", weights={}, candidates=[], source_fingerprints={"source": source.fingerprint}),
            "08_recap_plan.json": RecapPlan(viewer_promise="test", pov="test", main_spine="test",
                hook_strategy="test", hook_highlight_id="none", target_duration_sec=2, duration_mode="short",
                original_ratio_target=1, ending_strategy="test", reveal_strategy="chronological",
                beats=[RecapBeat(beat_id="beat", function="test", change="test", audience_question_in="test",
                    audience_question_out="test", narration_job="none", target_duration_sec=2)], rhythm=RhythmProfile()),
            BOARD: self.board,
        }
        for name, value in self.artifacts.items():
            write_json(self.work / name, value)

    def candidate(self):
        value = deepcopy(w.read(self.work / BOARD))
        value["segments"][0]["notes"] = "edited note"
        return value

    def adopt(self, candidate=None, base=None, **kwargs):
        return adopt_revision(self.work, base=base or freeze_revision(self.work),
            artifacts={BOARD: candidate or self.candidate()}, scope={"segment_ids": ["one"], "fields": ["notes", "visuals"]}, **kwargs)

    def test_atomic_generation_preserves_unknown_bytes_and_invalidates_qc(self):
        original_bytes = (self.work / BOARD).read_bytes()
        w.atomic(self.work / "10_preflight_qc.json", {"status": "PASSED", "old": True})
        w.atomic(self.work / "11_post_render_qc.json", {"status": "PASSED", "old": True})
        result = self.adopt()
        active = Path(result["active_dir"])
        self.assertEqual(w.preflight(self.work)[1], active)
        self.assertEqual((self.work / BOARD).read_bytes(), original_bytes)
        archive = w.verify_archive(result["archive"])
        self.assertEqual((Path(result["archive"]) / "files" / BOARD).read_bytes(), original_bytes)
        board = w.read(active / BOARD)
        self.assertEqual(board["opaque_metadata"], self.board["opaque_metadata"])
        self.assertEqual(board["segments"][0]["opaque_field"], {"do_not_drop": True})
        self.assertEqual(board["segments"][0]["notes"], "edited note")
        self.assertEqual(result["qc_status"], "NOT_RUN")
        self.assertEqual(w.read(active / "state.json")["stages"]["pre_qc"]["status"], "pending")
        self.assertEqual(archive["previous_active"], str(self.work))
        self.assertFalse((active / "10_preflight_qc.json").exists())
        self.assertFalse((active / "11_post_render_qc.json").exists())
        self.assertEqual(w.read(Path(result["archive"]) / "files/11_post_render_qc.json")["status"], "PASSED")

    def _register_missing_debug(self, *, legacy=False):
        frame = self.work / "frames/source/unit.jpg"
        index = w.read(self.work / "02_scene_index.json")
        index["units"][0]["frame_paths"] = [str(frame)]
        w.atomic(self.work / "02_scene_index.json", index)
        analysis = w.read(self.work / "03_scene_analysis.json")
        analysis["unit_fingerprint"] = fingerprint_json(index["units"])
        w.atomic(self.work / "03_scene_analysis.json", analysis)
        state = w.read(self.work / "state.json")
        state["stages"]["scenes"] = {"status": "passed", "artifacts": {str(frame): "a" * 64}}
        if legacy:
            for stage in ("scene_analysis", "highlights", "delivery"):
                state["stages"][stage] = {"status": "passed"}
        else:
            w.atomic(self.work / ".receipts/debug-cleanup.json", {"schema": "film-debug-cleanup/1",
                "files": [{"path": str(frame), "sha256": "a" * 64}]})
        w.atomic(self.work / "state.json", state)
        return frame

    def _adopt_current_note(self, note):
        _, active = w.preflight(self.work)
        candidate = w.read(active / BOARD)
        candidate["segments"][0]["notes"] = note
        return adopt_revision(self.work, base=freeze_revision(self.work), artifacts={BOARD: candidate},
                              scope={"segment_ids": ["one"], "fields": ["notes"]})

    def _assert_debug_absence_survives_generations(self, *, legacy):
        frame = self._register_missing_debug(legacy=legacy)
        expected = "missing_regenerable_debug_after_delivery" if legacy else "recorded_regenerable_debug_cleanup"
        for number in range(3):
            result = self._adopt_current_note(f"revision {number}")
            active = Path(result["active_dir"])
            archive = w.verify_archive(result["archive"])
            absent = {row["original_path"]: row["reason"] for row in archive["unavailable_optional_references"]}
            self.assertEqual(absent[str(frame)], expected)
            self.assertFalse(frame.exists())
            self.assertEqual(w.read(active / "02_scene_index.json")["units"][0]["frame_paths"], [str(frame)])
            self.assertEqual(w.read(active / "state.json")["stages"]["scenes"]["artifacts"][str(frame)], "a" * 64)
        changed = self.config.model_copy(deep=True)
        changed.render.crf += 1
        current = FilmRecapPipeline.from_current(work_dir=self.work, config=changed)
        self.assertNotEqual(current.work_dir, active)
        result = self._adopt_current_note("revision after render configuration change")
        absent = {row["original_path"]: row["reason"]
                  for row in w.verify_archive(result["archive"])["unavailable_optional_references"]}
        self.assertEqual(absent[str(frame)], expected)

    def test_recorded_debug_cleanup_survives_multiple_revisions_and_render_config(self):
        self._assert_debug_absence_survives_generations(legacy=False)

    def test_legacy_completed_debug_absence_survives_multiple_revisions_and_render_config(self):
        self._assert_debug_absence_survives_generations(legacy=True)

    def test_cleanup_from_an_owned_generation_is_inherited(self):
        first = self._adopt_current_note("create first generation")
        self.work = Path(first["active_dir"])
        frame = self._register_missing_debug()
        for number in range(2):
            result = self._adopt_current_note(f"later generation {number}")
            absent = {row["original_path"] for row in w.verify_archive(result["archive"])["unavailable_optional_references"]}
            self.assertIn(str(frame), absent)

    def test_inherited_cleanup_rejects_missing_or_mismatched_receipt_and_state_hash(self):
        frame = self._register_missing_debug()
        active = Path(self._adopt_current_note("first revision")["active_dir"])
        receipt_path = active / ".receipts/debug-cleanup.json"
        receipt = w.read(receipt_path)
        state = w.read(active / "state.json")
        pointer = (self.work / w.POINTER).read_bytes()
        for mutation in ("missing", "schema", "path", "hash", "scene_hash"):
            with self.subTest(mutation=mutation):
                changed = deepcopy(receipt)
                changed_state = deepcopy(state)
                if mutation == "schema":
                    changed["schema"] = "unknown-cleanup/99"
                elif mutation == "path":
                    changed["files"][0]["path"] = str(frame.with_name("wrong.jpg"))
                elif mutation == "hash":
                    changed["files"][0]["sha256"] = "b" * 64
                elif mutation == "scene_hash":
                    changed_state["stages"]["scenes"]["artifacts"][str(frame)] = "b" * 64
                w.atomic(receipt_path, changed)
                if mutation == "missing":
                    receipt_path.unlink()
                w.atomic(active / "state.json", changed_state)
                with self.assertRaisesRegex(w.WorkspaceError, "REQUIRED_EXTERNAL_ARTIFACT_MISSING"):
                    self._adopt_current_note(f"must reject {mutation}")
                self.assertEqual((self.work / w.POINTER).read_bytes(), pointer)

    def test_missing_debug_without_receipt_or_completed_history_still_blocks(self):
        self._register_missing_debug()
        (self.work / ".receipts/debug-cleanup.json").unlink()
        with self.assertRaisesRegex(w.WorkspaceError, "REQUIRED_ARCHIVE_MEMBER_MISSING"):
            self._adopt_current_note("unproven missing debug")
        self.assertFalse((self.work / w.POINTER).exists())

    def test_new_old_generation_or_foreign_missing_path_cannot_gain_cleanup_exemption(self):
        self._register_missing_debug()
        active = Path(self._adopt_current_note("first revision")["active_dir"])
        state = w.read(active / "state.json")
        receipt = w.read(active / ".receipts/debug-cleanup.json")
        for missing in (self.work / "frames/source/never-recorded.jpg",
                        self.root / "different-workspace/frames/source/unit.jpg",
                        self.work / "audio/missing-voice.mp3"):
            with self.subTest(missing=str(missing)):
                changed_state = deepcopy(state)
                changed_state["stages"]["scenes"]["artifacts"][str(missing)] = "c" * 64
                changed_receipt = deepcopy(receipt)
                changed_receipt["files"].append({"path": str(missing), "sha256": "c" * 64})
                w.atomic(active / "state.json", changed_state)
                w.atomic(active / ".receipts/debug-cleanup.json", changed_receipt)
                with self.assertRaisesRegex(w.WorkspaceError, "REQUIRED_EXTERNAL_ARTIFACT_MISSING"):
                    self._adopt_current_note("unproven external absence")

    def test_scene_cleanup_does_not_exempt_required_non_scene_artifact(self):
        frame = self._register_missing_debug()
        active = Path(self._adopt_current_note("first revision")["active_dir"])
        state = w.read(active / "state.json")
        state["stages"]["tts"] = {"status": "passed", "artifacts": {str(frame): "a" * 64}}
        w.atomic(active / "state.json", state)
        with self.assertRaisesRegex(w.WorkspaceError, "REQUIRED_EXTERNAL_ARTIFACT_MISSING"):
            self._adopt_current_note("debug path is also required by TTS")

    def test_missing_source_or_voice_audio_still_blocks_with_inherited_cleanup(self):
        self._register_missing_debug()
        active = Path(self._adopt_current_note("first revision")["active_dir"])
        original_source = self.source_path.read_bytes()
        self.source_path.unlink()
        with self.assertRaisesRegex(w.WorkspaceError, "BOUND_RESOURCE_UNSAFE"):
            self._adopt_current_note("missing source")
        self.source_path.write_bytes(original_source)
        board = w.read(active / BOARD)
        board["segments"][0].update(mode="voiceover", audio_owner="narration",
            audio_file=str(self.work / "audio/missing-voice.mp3"))
        w.atomic(active / BOARD, board)
        with self.assertRaisesRegex(w.WorkspaceError, "BOUND_RESOURCE_UNSAFE"):
            self._adopt_current_note("missing voice audio")

    def test_conflicting_adoption_cannot_replace_new_head(self):
        base = freeze_revision(self.work)
        result = self.adopt(base=base)
        with self.assertRaisesRegex(w.WorkspaceError, "BASE_CONFLICT"):
            self.adopt(base=base)
        self.assertEqual(str(w.preflight(self.work)[1]), result["active_dir"])

    def test_same_path_changed_source_bytes_rejected(self):
        base = freeze_revision(self.work)
        self.source_path.write_bytes(b"different source bytes")
        with self.assertRaisesRegex(w.WorkspaceError, "SOURCE_BINDING_CHANGED"):
            self.adopt(base=base)
        self.assertFalse((self.work / w.POINTER).exists())

    def test_manual_base_edit_detected(self):
        base = freeze_revision(self.work)
        w.atomic(self.work / BOARD, self.candidate())
        with self.assertRaisesRegex(w.WorkspaceError, "BASE_CONFLICT"):
            self.adopt(base=base)

    def test_protection_unknown_and_unsupported_fields_rejected(self):
        for mutation, error in [("protection", "PROTECTED"), ("unknown", "UNKNOWN_FIELD"),
                                ("text", "FIELD_UNSUPPORTED"), ("original", "ORIGINAL_BOUNDARY")]:
            with self.subTest(mutation=mutation):
                board = deepcopy(self.board)
                if mutation == "protection":
                    board["segments"][0]["protection"] = {"locked": True}
                w.atomic(self.work / BOARD, board)
                candidate = deepcopy(board)
                candidate["segments"][0]["notes"] = "changed"
                if mutation == "unknown":
                    candidate["segments"][0].pop("opaque_field")
                elif mutation == "text":
                    candidate["segments"][0]["text"] = "new TTS is unauthorized"
                elif mutation == "original":
                    board["segments"][0].pop("opaque_field")
                    candidate["segments"][0].pop("opaque_field")
                    w.atomic(self.work / BOARD, board)
                    candidate["segments"][0]["visuals"][0]["end"] = 3
                with self.assertRaisesRegex(w.WorkspaceError, error):
                    self.adopt(candidate)

    def test_visual_replacement_must_have_current_analyzed_evidence(self):
        board = deepcopy(self.board)
        segment = board["segments"][0]
        segment.update(mode="voiceover", audio_owner="narration")
        segment.pop("opaque_field")  # A known visual-only edit has no opaque timing dependency.
        segment["visuals"][0]["unit_id"] = "unit"
        w.atomic(self.work / BOARD, board)
        candidate = deepcopy(board)
        candidate["segments"][0]["visuals"][0].update(start=2, end=4)
        result = self.adopt(candidate)
        self.assertEqual(w.read(Path(result["active_dir"]) / BOARD)["segments"][0]["visuals"][0]["start"], 2)

    def test_interruption_before_pointer_never_changes_active_documents(self):
        for point in ("copied", "archived", "prepared"):
            with self.subTest(point=point):
                before = (self.work / BOARD).read_bytes()
                def interrupt(observed):
                    if point == observed:
                        raise RuntimeError("simulated crash")
                with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                    self.adopt(reason=point, interrupt=interrupt)
                self.assertEqual(w.preflight(self.work)[1], self.work)
                self.assertEqual((self.work / BOARD).read_bytes(), before)
        self.assertEqual(self.adopt()["status"], "ADOPTED")

    def test_post_switch_interruption_can_be_discovered_without_readopting(self):
        base = freeze_revision(self.work)
        def interrupt(point):
            if point == "switched":
                raise RuntimeError("lost receipt")
        with self.assertRaisesRegex(RuntimeError, "lost receipt"):
            self.adopt(base=base, interrupt=interrupt)
        active = w.preflight(self.work)[1]
        self.assertNotEqual(active, self.work)
        self.assertEqual(w.read(active / BOARD)["segments"][0]["notes"], "edited note")
        with self.assertRaisesRegex(w.WorkspaceError, "BASE_CONFLICT"):
            self.adopt(base=base)

    def test_mutation_during_preparation_rejects_commit(self):
        def interrupt(point):
            if point == "prepared":
                self.source_path.write_bytes(b"changed while preparing")
        with self.assertRaisesRegex(w.WorkspaceError, "SOURCE_BINDING_CHANGED"):
            self.adopt(interrupt=interrupt)
        self.assertFalse((self.work / w.POINTER).exists())

    def test_from_current_does_not_enter_prepare_and_accepts_only_render_delta(self):
        changed = self.config.model_copy(deep=True)
        changed.render.crf += 1
        with patch("douyin_film_recap.pipeline.prepare", side_effect=AssertionError("upstream prepare entered")):
            current = FilmRecapPipeline.from_current(work_dir=self.work, config=changed)
        self.assertNotEqual(current.work_dir, self.work)
        self.assertEqual(w.read(current.paths["storyboard"])["segments"], self.board["segments"])
        changed.tts.voice = "unauthorized-new-voice"
        with self.assertRaisesRegex(w.WorkspaceError, "NON_RENDER_CONFIG_CHANGED"):
            FilmRecapPipeline.from_current(work_dir=self.work, config=changed)

    def test_legacy_missing_config_receipt_requires_exact_config(self):
        (self.work / ".receipts/config-binding.json").unlink()
        changed = self.config.model_copy(deep=True); changed.render.crf += 1
        with self.assertRaisesRegex(w.WorkspaceError, "ORIGINAL_CONFIG_REQUIRED"):
            FilmRecapPipeline.from_current(work_dir=self.work, config=changed)
        FilmRecapPipeline.from_current(work_dir=self.work, config=self.config)
        self.assertTrue((self.work / ".receipts/config-binding.json").is_file())

    def test_render_current_runs_existing_gates_in_order_no_upstream(self):
        current = FilmRecapPipeline.from_current(work_dir=self.work, config=self.config)
        stages = []
        def run_stage(stage):
            stages.append(stage)
        with patch.object(current, "_run_stage", side_effect=run_stage), patch.object(current, "_stage_tts", side_effect=AssertionError("TTS entered")):
            current.render_only()
        self.assertEqual(stages, ["pre_qc", "render", "post_qc", "delivery"])
        self.assertFalse(w.read(self.work / ".receipts/render-current.json")["new_remote_requests_allowed"])

    def test_blocked_pre_qc_prevents_render_and_persists_failure(self):
        current = FilmRecapPipeline.from_current(work_dir=self.work, config=self.config)
        blocked = QCReport(stage="pre_render", status="BLOCKED", findings=[])
        with patch("douyin_film_recap.pipeline.preflight_qc", return_value=blocked), patch.object(current, "_stage_render", side_effect=AssertionError("render bypassed gate")):
            with self.assertRaises(StageBlocked):
                current.render_only()
        self.assertEqual(w.read(self.work / "state.json")["stages"]["pre_qc"]["status"], "failed")
        self.assertEqual(w.read(self.work / "10_preflight_qc.json")["status"], "BLOCKED")

    def test_remote_unknown_intent_is_preserved_and_never_resent(self):
        from douyin_film_recap import send_guard as guard
        current = FilmRecapPipeline.from_current(work_dir=self.work, config=self.config)
        current._prepare_stage("pre_qc")
        scope = {"binding": current.binding, "stage": "pre_qc",
                 "stage_inputs": current._stage_inputs("pre_qc"), "remote_policy": current.remote_policy}
        def lost_transport():
            raise TimeoutError("provider outcome unknown")
        payload = current.remote_policy["edge_tts"]
        with guard.send_session(current.task_root, scope, authorized=True):
            with self.assertRaises(TimeoutError):
                guard.guarded_send("edge_tts", payload, lost_transport, intent_key="qc-test")
        intent = next((current.task_root / ".remote-intents").glob("*.json"))
        before = intent.read_bytes()
        transport_calls = []
        class Client:
            def chat_json(self, **kwargs):
                return guard.guarded_send("edge_tts", payload,
                    lambda: transport_calls.append(True), intent_key="qc-test")
        current.client = Client()
        with self.assertRaises(StageBlocked):
            current.render_only()
        self.assertEqual(transport_calls, [])
        self.assertEqual(intent.read_bytes(), before)
        report = w.read(current.paths["pre_qc"])
        self.assertTrue(any("SEND_OUTCOME_UNKNOWN" in f["message"] for f in report["findings"]))
        self.assertEqual(report["coverage"]["semantic"]["status"], "not_checked")

    def test_fresh_pre_and_post_qc_with_real_stage_orchestration(self):
        current = FilmRecapPipeline.from_current(work_dir=self.work, config=self.config)
        pre = QCReport(stage="pre_render", status="DEGRADED", findings=[])
        post = QCReport(stage="post_render", status="DEGRADED", findings=[])
        def synthetic_renderer(board, config, work_dir):
            output = {}
            for key, filename in [("final_video", "final.mp4"), ("preview_video", "preview.mp4"),
                                  ("subtitle", "captions.srt"), ("edl", "edl.json")]:
                path = work_dir / "synthetic-output" / filename
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(b"synthetic artifact, not media certification")
                output[key] = str(path)
            board.output = {**output, "duration_sec": 2}
            board.segments[0].status = "rendered"
            return board
        with patch("douyin_film_recap.pipeline.preflight_qc", return_value=pre) as pre_call, \
             patch("douyin_film_recap.pipeline.post_render_qc", return_value=post) as post_call, \
             patch("douyin_film_recap.pipeline.render_storyboard", side_effect=synthetic_renderer), \
             patch.object(current, "_stage_tts", side_effect=AssertionError("TTS entered")):
            delivery = current.render_only()
        self.assertEqual(pre_call.call_count, 1)
        self.assertEqual(post_call.call_count, 1)
        self.assertIn("DEGRADED", delivery.read_text())
        state = w.read(current.work_dir / "state.json")
        self.assertTrue(all(state["stages"][name]["status"] == "passed"
                            for name in ("pre_qc", "render", "post_qc", "delivery")))

    def test_ordinary_run_cannot_silently_regenerate_adopted_documents(self):
        self.adopt()
        current = FilmRecapPipeline.from_current(work_dir=self.work, config=self.config)
        with self.assertRaisesRegex(w.WorkspaceError, "PROTECTED_REVISION_REQUIRES"):
            current.run()
        stages = []
        with patch.object(current, "_run_stage", side_effect=stages.append):
            current.run(from_stage="tts", until="pre_qc")
        self.assertEqual(stages, ["tts", "pre_qc"])

    def test_normal_constructor_binding_change_cannot_replace_adopted_head(self):
        result = self.adopt()
        pointer_before = (self.work / w.POINTER).read_bytes()
        changed = self.config.model_copy(deep=True); changed.render.crf += 1
        with self.assertRaisesRegex(w.WorkspaceError, "BINDING_CHANGED_USE_RENDER_CURRENT"):
            FilmRecapPipeline(input_path=self.source_path, work_dir=self.work, config=changed)
        self.assertEqual((self.work / w.POINTER).read_bytes(), pointer_before)
        self.assertEqual(str(w.preflight(self.work)[1]), result["active_dir"])
        current = FilmRecapPipeline.from_current(work_dir=self.work, config=changed)
        self.assertNotEqual(str(current.work_dir), result["active_dir"])

    def test_explicit_render_resume_on_revision_forces_both_qc_gates(self):
        self.adopt()
        current = FilmRecapPipeline.from_current(work_dir=self.work, config=self.config)
        stages = []
        with patch.object(current, "_run_stage", side_effect=stages.append):
            current.run(from_stage="render")
        self.assertEqual(stages, ["pre_qc", "render", "post_qc", "delivery"])

    def test_render_does_not_overwrite_late_manual_storyboard_edit(self):
        current = FilmRecapPipeline.from_current(work_dir=self.work, config=self.config)
        late = self.candidate()
        def render(board, config, work_dir):
            w.atomic(work_dir / BOARD, late)
            return board
        with patch("douyin_film_recap.pipeline.render_storyboard", side_effect=render):
            with self.assertRaisesRegex(w.WorkspaceError, "STORYBOARD_CHANGED"):
                current._stage_render()
        self.assertEqual(w.read(current.paths["storyboard"]), late)

    def test_boundary_cannot_be_used_without_domain_validator(self):
        with self.assertRaisesRegex(w.WorkspaceError, "BOUNDARY_VALIDATION_REQUIRED"):
            adopt_revision(self.work, base=freeze_revision(self.work), artifacts={BOARD: self.candidate()},
                           scope={"segment_ids": ["one"]}, kind="boundary")


if __name__ == "__main__":
    unittest.main()
