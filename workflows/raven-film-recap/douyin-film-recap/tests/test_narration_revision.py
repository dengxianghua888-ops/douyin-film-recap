"""No-network exact-text revision tests through the real TTS/send boundary."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

import test_protected_revision as protected_fixture
from douyin_film_recap.models import Storyboard, StoryboardSegment, QCReport
from douyin_film_recap.narration_revision import prepare_narration_revision, execute_narration_revision
from douyin_film_recap.revision import BOARD, freeze_revision
from douyin_film_recap.send_guard import SendBlocked
from douyin_film_recap.subtitles import build_cues, output_timeline
from douyin_film_recap import workspace as w


class NarrationRevisionTests(unittest.TestCase):
    def setUp(self):
        protected_fixture.ProtectedRevisionTests.setUp(self)
        segments = []
        for identifier, text, start in [("one", "旧句", 0), ("two", "下一句", 5)]:
            audio = self.root / f"{identifier}-old.mp3"
            audio.write_bytes(f"unchanged-audio:{identifier}".encode())
            segments.append(StoryboardSegment(segment_id=identifier, beat_id="beat", mode="voiceover",
                title=identifier, text=text, notes="keep notes", audio_owner="narration",
                narration_job="context", planned_duration_sec=1, audio_file=str(audio),
                audio_source_duration_sec=1, audio_duration_sec=1, status="audio_ready",
                tts_word_boundaries=[{"text": text, "start": 0, "duration": 1}],
                visuals=[{"source_id": "source", "start": start, "end": start + 5, "unit_id": "unit"}]))
        self.board = Storyboard(project_name="fixture", sources=[self.source], plan_fingerprint="plan",
            target_duration_sec=2, segments=segments,
            output={"duration_sec": 2, "realized_timeline": [{"segment_id": "one", "start": 0, "end": 1},
                                                          {"segment_id": "two", "start": 1, "end": 2}]}).model_dump(mode="json")
        w.atomic(self.work / BOARD, self.board)
        self.calls = []
        self.duration = 3.0
        self.unknown = False
        self.on_send = None
        outer = self
        class Communicate:
            def __init__(self, *, text, **kwargs):
                self.text = text
            async def stream(self):
                outer.calls.append(self.text)
                if outer.on_send:
                    outer.on_send()
                if outer.unknown:
                    raise TimeoutError("synthetic provider outcome is unknown")
                yield {"type": "audio", "data": ("synthetic-audio:" + self.text).encode()}
                yield {"type": "WordBoundary", "text": self.text, "offset": 0,
                       "duration": int(outer.duration * 10_000_000)}
        self.addCleanup(patch.stopall)
        patch.dict(sys.modules, {"edge_tts": SimpleNamespace(Communicate=Communicate)}).start()
        self.duration_patch = patch("douyin_film_recap.tts.media_duration", side_effect=lambda _: self.duration)
        self.duration_patch.start()

    def prepare(self, **kwargs):
        return prepare_narration_revision(self.work, base=freeze_revision(self.work),
            edits=kwargs.pop("edits", {"one": "替换后的这句话"}), **kwargs)

    def execute(self, plan, **kwargs):
        return execute_narration_revision(self.work, plan=plan, config=self.config, **kwargs)

    def test_prepare_is_read_only_and_exact_target(self):
        before = {str(p): p.read_bytes() for p in self.work.rglob("*") if p.is_file()}
        plan = self.prepare(reason="exact narration correction")
        after = {str(p): p.read_bytes() for p in self.work.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(plan["status"], "PENDING_TTS")
        self.assertEqual(plan["candidate_storyboard"]["segments"][0]["text"], "替换后的这句话")
        self.assertEqual(plan["candidate_storyboard"]["segments"][1], self.board["segments"][1])
        self.assertEqual(self.calls, [])

    def test_only_target_synthesizes_and_actual_length_repositions_cues(self):
        before_bytes = Path(self.board["segments"][1]["audio_file"]).read_bytes()
        plan = self.prepare()
        result = self.execute(plan, allow_remote=True, max_remote_requests=1)
        self.assertEqual(self.calls, ["替换后的这句话"])
        self.assertEqual(result["new_remote_requests"], 1)
        self.assertEqual(result["render_status"], "NOT_RUN")
        active = Path(result["active_dir"])
        new = w.read(active / BOARD)
        self.assertEqual(new["segments"][1], self.board["segments"][1])
        self.assertEqual(Path(new["segments"][1]["audio_file"]).read_bytes(), before_bytes)
        self.assertEqual(new["segments"][0]["text"], "替换后的这句话")
        self.assertEqual(new["segments"][0]["planned_duration_sec"], 3)
        self.assertEqual(new["segments"][0]["audio_duration_sec"], 3)
        self.assertEqual(new["output"], {})
        board = Storyboard.model_validate(new)
        self.assertEqual(output_timeline(board)[1]["start"], 3)
        next_cue = next(cue for cue in build_cues(board, self.config) if cue.text == "下一句")
        self.assertEqual(next_cue.start, 3)
        state = w.read(active / "state.json")
        self.assertEqual(state["stages"]["pre_qc"]["status"], "pending")
        receipt = w.read(active / ".receipts/narration-revision.json")
        self.assertIn("output_time_map", receipt["invalidated"])
        self.assertEqual(receipt["adopted_storyboard_content_hash"], w.digest(new))
        with self.assertRaisesRegex(w.WorkspaceError, "BASE_CONFLICT"):
            self.execute(plan, allow_remote=True)
        self.assertEqual(len(self.calls), 1)

    def test_new_synthesis_needs_specific_authorization(self):
        plan = self.prepare()
        with self.assertRaisesRegex(SendBlocked, "AUTHORIZATION_REQUIRED"):
            self.execute(plan)
        self.assertEqual(self.calls, [])
        self.assertEqual(w.preflight(self.work)[1], self.work)

    def test_broad_existing_grant_does_not_authorize_new_revision_scope(self):
        plan = self.prepare()
        w.atomic(self.work / ".remote-authorization.json", {"schema": "film-remote-authorization/1",
            "id": "old-broad-grant", "binding": self.pipeline.binding, "remote_policy": self.pipeline.remote_policy,
            "stages": ["tts"], "max_requests": None})
        with self.assertRaisesRegex(SendBlocked, "AUTHORIZATION_REQUIRED"):
            self.execute(plan)
        self.assertEqual(self.calls, [])

    def test_unknown_real_send_intent_never_resends_even_with_new_grant(self):
        plan = self.prepare()
        self.unknown = True
        with self.assertRaises(TimeoutError):
            self.execute(plan, allow_remote=True)
        intent = next((self.work / ".remote-intents").glob("*.json"))
        before = intent.read_bytes()
        self.assertEqual(w.read(intent)["status"], "UNKNOWN")
        self.unknown = False
        with self.assertRaisesRegex(SendBlocked, "SEND_OUTCOME_UNKNOWN"):
            self.execute(plan, allow_remote=True)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(intent.read_bytes(), before)
        self.assertEqual(w.preflight(self.work)[1], self.work)

    def test_original_pipeline_unknown_payload_cannot_be_resent_by_revision_entry(self):
        from douyin_film_recap.send_guard import guarded_send, send_session
        plan = self.prepare()
        payload = {"text": plan["edits"]["one"], **self.pipeline.remote_policy["edge_tts"], "boundary": "WordBoundary"}
        def timeout():
            raise TimeoutError("prior pipeline provider outcome unknown")
        with send_session(self.work, {"stage": "tts", "binding": "older-production-scope"}, authorized=True):
            with self.assertRaises(TimeoutError):
                guarded_send("edge_tts", payload, timeout, intent_key="tts:one:audio:initial")
        with self.assertRaisesRegex(SendBlocked, "SEND_OUTCOME_UNKNOWN"):
            self.execute(plan, allow_remote=True)
        self.assertEqual(self.calls, [])

    def test_cosmetic_reason_or_unrelated_rebase_cannot_bypass_unknown_request(self):
        self.unknown = True
        with self.assertRaises(TimeoutError):
            self.execute(self.prepare(reason="first reason"), allow_remote=True)
        self.unknown = False
        for rebase in (False, True):
            if rebase:
                board = deepcopy(self.board)
                board["segments"][1]["notes"] = "unrelated note changed before replanning"
                w.atomic(self.work / BOARD, board)
            plan = self.prepare(reason="cosmetic new reason")
            with self.assertRaisesRegex(SendBlocked, "SEND_OUTCOME_UNKNOWN"):
                self.execute(plan, allow_remote=True)
        self.assertEqual(self.calls, ["替换后的这句话"])
        self.assertEqual(len(list((self.work / ".remote-intents").glob("*.json"))), 1)

    def test_interrupted_adoption_reuses_target_audio_without_second_send(self):
        plan = self.prepare()
        with patch("douyin_film_recap.narration_revision.adopt_revision", side_effect=OSError("disk before adoption")):
            with self.assertRaises(OSError):
                self.execute(plan, allow_remote=True)
        # Remove the grant; verified generated target cache remains sufficient.
        (self.work / ".remote-authorization.json").unlink()
        result = self.execute(plan)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["new_remote_requests"], 0)
        self.assertTrue(result["targets"][0]["cache_hit"])

    def test_cached_target_optional_render_does_not_migrate_legacy_broad_grant(self):
        plan = self.prepare()
        with patch("douyin_film_recap.narration_revision.adopt_revision", side_effect=OSError("stop before adoption")):
            with self.assertRaises(OSError):
                self.execute(plan, allow_remote=True)
        w.atomic(self.work / ".remote-authorization.json", {"schema": "film-remote-authorization/1",
            "id": "unrelated-old-grant", "binding": self.pipeline.binding,
            "remote_policy": self.pipeline.remote_policy, "stages": ["pre_qc", "render", "post_qc", "delivery"]})
        def cached_only_render(current):
            w.atomic(current.paths["pre_qc"], {"status": "DEGRADED"})
            w.atomic(current.paths["post_qc"], {"status": "DEGRADED"})
            return current.paths["delivery"]
        with patch("douyin_film_recap.pipeline.FilmRecapPipeline.run", side_effect=AssertionError("broad grant could be reused")), \
             patch("douyin_film_recap.pipeline.FilmRecapPipeline.render_only", autospec=True, side_effect=cached_only_render) as render_call:
            result = self.execute(plan, render=True)
        self.assertEqual(render_call.call_count, 1)
        self.assertEqual(result["render_status"], "EXECUTED")
        self.assertEqual(result["new_remote_requests"], 0)
        self.assertEqual(len(self.calls), 1)

    def test_too_long_exact_text_is_not_rewritten_or_adopted(self):
        plan = self.prepare()
        self.duration = 10
        with self.assertRaisesRegex(w.WorkspaceError, "VISUAL_COVERAGE_REQUIRED"):
            self.execute(plan, allow_remote=True)
        self.assertEqual(self.calls, [plan["edits"]["one"]])
        self.assertEqual(w.preflight(self.work)[1], self.work)
        self.assertEqual(w.read(self.work / BOARD), self.board)
        with self.assertRaisesRegex(w.WorkspaceError, "VISUAL_COVERAGE_REQUIRED"):
            self.execute(plan)
        self.assertEqual(len(self.calls), 1)

    def test_stale_during_send_preserves_user_edit_and_refuses_adoption(self):
        plan = self.prepare()
        late = deepcopy(self.board); late["segments"][1]["notes"] = "late manual edit"
        self.on_send = lambda: w.atomic(self.work / BOARD, late)
        with self.assertRaisesRegex(w.WorkspaceError, "BASE_CONFLICT"):
            self.execute(plan, allow_remote=True)
        self.assertEqual(w.read(self.work / BOARD), late)
        self.assertEqual(w.preflight(self.work)[1], self.work)
        self.assertEqual(len(self.calls), 1)

    def test_protected_targets_and_tampered_proposals_are_rejected(self):
        plan = self.prepare()
        plan["candidate_storyboard"]["segments"][1]["text"] = "scope escape"
        with self.assertRaisesRegex(w.WorkspaceError, "PLAN_CHANGED"):
            self.execute(plan, allow_remote=True)
        protected = deepcopy(self.board); protected["segments"][0]["protection"] = {"locked": True}
        w.atomic(self.work / BOARD, protected)
        with self.assertRaisesRegex(w.WorkspaceError, "PROTECTED"):
            self.prepare()
        self.assertEqual(self.calls, [])

    def test_request_budget_blocks_before_provider(self):
        with self.assertRaisesRegex(SendBlocked, "REQUEST_LIMIT"):
            self.execute(self.prepare(), allow_remote=True, max_remote_requests=0)
        self.assertEqual(self.calls, [])

    @unittest.skipUnless(__import__("shutil").which("ffmpeg") and __import__("shutil").which("ffprobe"), "FFmpeg required")
    def test_real_audio_measurement_and_renderer_reuse_only_unchanged_segment(self):
        import subprocess
        from douyin_film_recap.media import media_duration
        from douyin_film_recap.pipeline import FilmRecapPipeline
        from douyin_film_recap.render import render_storyboard
        from douyin_film_recap.utils import fingerprint_json, write_json
        self.duration_patch.stop()
        def ffmpeg(*arguments):
            subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, arguments)], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ffmpeg("-f", "lavfi", "-i", "testsrc2=size=64x64:rate=30:duration=10",
               "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", self.source_path)
        generated = self.root / "synthetic-new-tts.mp3"
        ffmpeg("-f", "lavfi", "-i", "sine=frequency=660:sample_rate=48000:duration=3",
               "-c:a", "libmp3lame", generated)
        for segment in self.board["segments"]:
            ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1",
                   "-c:a", "libmp3lame", segment["audio_file"])
            measured = media_duration(Path(segment["audio_file"]))
            segment.update(audio_source_duration_sec=measured, audio_duration_sec=measured,
                           planned_duration_sec=measured)
        self.source = self.source.model_copy(update={"fingerprint": w.sha(self.source_path),
            "size_bytes": self.source_path.stat().st_size, "width": 64, "height": 64,
            "fps": 30, "has_audio": False})
        self.board["sources"] = [self.source.model_dump(mode="json")]
        self.board["output"] = {}
        self.config.render.width = self.config.render.height = 64
        self.config.render.fps = 30
        self.config.render.layout = "fit_black"
        self.config.render.preset = "ultrafast"
        self.config.render.subtitle_burn_in = False
        self.config.render.incremental_cache = True
        self.config.runtime.max_parallel_ffmpeg = 1
        self.pipeline = FilmRecapPipeline(input_path=self.source_path, work_dir=self.work, config=self.config)
        self.work = self.pipeline.work_dir
        self.artifacts["00_source_manifest.json"].sources = [self.source]
        self.artifacts["00_source_manifest.json"].config_fingerprint = self.config.fingerprint()
        for filename in ("01_transcript.json", "02_scene_index.json", "07_highlight_candidates.json"):
            self.artifacts[filename].source_fingerprints = {"source": self.source.fingerprint}
        self.artifacts["03_scene_analysis.json"].unit_fingerprint = fingerprint_json([
            unit.model_dump(mode="json") for unit in self.artifacts["02_scene_index.json"].units])
        self.artifacts[BOARD] = self.board
        for name, value in self.artifacts.items():
            write_json(self.work / name, value)
        # Prime the real whole-AV cache with independently generated synthetic media.
        warm = render_storyboard(Storyboard.model_validate(self.board), self.config, self.work)
        write_json(self.work / BOARD, warm)
        old_audio = Path(warm.segments[1].audio_file).read_bytes()
        payload = generated.read_bytes()
        calls = self.calls
        class RealBytesCommunicate:
            def __init__(self, *, text, **kwargs):
                self.text = text
            async def stream(self):
                calls.append(self.text)
                yield {"type": "audio", "data": payload}
                yield {"type": "WordBoundary", "text": self.text, "offset": 0, "duration": 30_000_000}
        pre = QCReport(stage="pre_render", status="DEGRADED", findings=[],
                       coverage={"semantic": {"status": "not_checked", "reason": "synthetic fixture"}})
        with patch.dict(sys.modules, {"edge_tts": SimpleNamespace(Communicate=RealBytesCommunicate)}), \
             patch("douyin_film_recap.pipeline.preflight_qc", return_value=pre):
            result = self.execute(self.prepare(), allow_remote=True, max_remote_requests=1, render=True)
        self.assertEqual(self.calls, ["替换后的这句话"])
        self.assertEqual(result["render_status"], "EXECUTED", result)
        active = Path(result["active_dir"])
        board = Storyboard.model_validate(w.read(active / BOARD))
        self.assertAlmostEqual(board.segments[0].audio_source_duration_sec, media_duration(generated), places=6)
        self.assertGreater(board.segments[0].audio_duration_sec, 2.9)
        self.assertEqual(Path(board.segments[1].audio_file).read_bytes(), old_audio)
        receipt = w.read(Path(board.output["render_receipt"]))
        self.assertEqual([row["action"] for row in receipt["segments"]], ["executed", "reused"])
        self.assertTrue(receipt["finalize_executed"])
        realized = board.output["realized_timeline"]
        timeline = output_timeline(board, realized_timeline=realized)
        self.assertGreater(timeline[1]["start"], 2.9)
        second = next(cue for cue in build_cues(board, self.config, realized_timeline=realized)
                      if cue.text == "下一句")
        self.assertAlmostEqual(second.start, timeline[1]["start"], places=6)
        self.assertGreater(media_duration(Path(board.output["final_video"])), 3.9)
        self.assertNotEqual(result["qc_status"], "PASSED")  # No semantic/AV content certification.

    def test_optional_render_runs_fresh_existing_gates_after_adoption(self):
        pre = QCReport(stage="pre_render", status="DEGRADED", findings=[])
        post = QCReport(stage="post_render", status="DEGRADED", findings=[])
        def synthetic_renderer(board, config, work_dir):
            output = {}
            for key, filename in [("final_video", "final.mp4"), ("preview_video", "preview.mp4"),
                                  ("subtitle", "captions.srt"), ("edl", "edl.json")]:
                path = work_dir / "synthetic-output" / filename
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(b"synthetic, no media quality claim")
                output[key] = str(path)
            board.output = {**output, "duration_sec": 4}
            return board
        with patch("douyin_film_recap.pipeline.preflight_qc", return_value=pre) as pre_call, \
             patch("douyin_film_recap.pipeline.post_render_qc", return_value=post) as post_call, \
             patch("douyin_film_recap.pipeline.render_storyboard", side_effect=synthetic_renderer):
            result = self.execute(self.prepare(), allow_remote=True, max_remote_requests=2, render=True)
        self.assertEqual(self.calls, ["替换后的这句话"])
        self.assertEqual(pre_call.call_count, 1)
        self.assertEqual(post_call.call_count, 1)
        self.assertEqual(result["qc_status"], "DEGRADED")
        self.assertEqual(result["render_status"], "EXECUTED")
        self.assertIn("DEGRADED", Path(result["delivery_report"]).read_text())


if __name__ == "__main__":
    unittest.main()
