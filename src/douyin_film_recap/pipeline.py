from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from .analysis import build_story, load_story_bundle, analyze_scenes
from .asr import build_transcript
from .config import AppConfig
from .highlight import build_highlights
from .media import build_manifest, build_scene_index, find_sidecar_subtitle
from .models import (
    CharacterRegistry,
    HighlightDocument,
    KnowledgeTimeline,
    OriginalCue,
    QCReport,
    RecapPlan,
    SceneAnalysisDocument,
    SceneIndex,
    SourceManifest,
    StoryGraph,
    Storyboard,
    TranscriptDocument,
)
from .narrative_contracts import get_plan_constraints
from .planning import build_plan, build_storyboard, write_human_script
from .providers import OpenAICompatibleClient
from .qc import post_render_qc, preflight_qc
from .render import render_storyboard
from .state import STAGES, StateStore
from .tts import synthesize_storyboard
from .utils import (
    content_fingerprint,
    discover_videos,
    file_fingerprint,
    fingerprint_json,
    read_json,
    safe_slug,
    write_json,
)


class StageBlocked(RuntimeError):
    def __init__(self, stage: str, report: QCReport):
        super().__init__(f"{stage} blocked with {len(report.findings)} finding(s)")
        self.stage = stage
        self.report = report


PIPELINE_REVISION = "0.2.0-receipts-1"


class FilmRecapPipeline:
    def __init__(
        self,
        *,
        input_path: str | Path,
        work_dir: str | Path,
        config: AppConfig,
        on_update: Callable[[str], None] | None = None,
    ):
        self.input_path = Path(input_path).expanduser().resolve()
        self.work_dir = Path(work_dir).expanduser().resolve()
        if self.input_path.is_dir() and self.work_dir.is_relative_to(self.input_path):
            raise ValueError("work_dir must be outside the input media directory to prevent importing generated videos")
        if self.input_path.is_relative_to(self.work_dir):
            raise ValueError("Input media must be outside work_dir to protect source files from generated outputs")
        self.config = config
        self.on_update = on_update or (lambda _: None)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.project_name = safe_slug(
            self.input_path.stem if self.input_path.is_file() else self.input_path.name
        )
        self.client = OpenAICompatibleClient(config.models)
        self.store = StateStore(self.work_dir)
        current_inputs = discover_videos(self.input_path)
        input_fingerprint = fingerprint_json(
            [self._source_input_identity(path) for path in current_inputs]
        )
        context_fingerprint = None
        if config.story.allow_external_context and config.project.context_file:
            context_path = Path(config.project.context_file).expanduser()
            if context_path.exists():
                context_fingerprint = file_fingerprint(context_path)
        runtime_fingerprint = fingerprint_json(
            {
                "config": config.fingerprint(),
                "pipeline_revision": PIPELINE_REVISION,
                "context_fingerprint": context_fingerprint,
            }
        )
        state = self.store.load_or_create(
            project_name=self.project_name,
            input_paths=[str(self.input_path)],
            input_fingerprint=input_fingerprint,
            config_fingerprint=runtime_fingerprint,
        )
        if (
            state.input_paths != [str(self.input_path)]
            or state.input_fingerprint != input_fingerprint
            or state.config_fingerprint != runtime_fingerprint
        ):
            state.input_paths = [str(self.input_path)]
            state.input_fingerprint = input_fingerprint
            state.config_fingerprint = runtime_fingerprint
            self.store.invalidate_from(state, "ingest")
        self.state = state
        if not self.config.runtime.cache:
            self.store.invalidate_from(self.state, "ingest")

    @property
    def paths(self) -> dict[str, Path]:
        return {
            "manifest": self.work_dir / "00_source_manifest.json",
            "transcript": self.work_dir / "01_transcript.json",
            "scene_index": self.work_dir / "02_scene_index.json",
            "scene_analysis": self.work_dir / "03_scene_analysis.json",
            "characters": self.work_dir / "04_character_registry.json",
            "story": self.work_dir / "05_story_graph.json",
            "knowledge": self.work_dir / "06_knowledge_timeline.json",
            "highlights": self.work_dir / "07_highlight_candidates.json",
            "plan": self.work_dir / "08_recap_plan.json",
            "storyboard": self.work_dir / "09_storyboard.json",
            "pre_qc": self.work_dir / "10_preflight_qc.json",
            "post_qc": self.work_dir / "11_post_render_qc.json",
            "script": self.work_dir / "scripts" / "final_script.md",
            "delivery": self.work_dir / "output" / "delivery_report.md",
        }

    def _say(self, message: str) -> None:
        self.on_update(message)

    def _source_input_identity(self, path: Path) -> dict:
        subtitle = find_sidecar_subtitle(path) if self.config.asr.prefer_sidecar_subtitle else None
        return {
            "path": str(path), "fingerprint": file_fingerprint(path),
            "subtitle": {"path": str(subtitle), "fingerprint": content_fingerprint(subtitle)}
                        if subtitle else None,
        }

    def _snapshot_path(self, stage: str) -> Path:
        return self.work_dir / ".receipts" / f"{stage}_storyboard.json"

    def _storyboard_identity(self) -> dict:
        data = read_json(self.paths["storyboard"])
        data.pop("output", None)
        for segment in data.get("segments", []):
            for key in ("status", "rendered_file", "rendered_duration_sec"):
                segment.pop(key, None)
        return data

    def _stage_inputs(self, stage: str) -> str:
        dependencies = {
            "ingest": [], "transcript": ["manifest"], "scenes": ["manifest", "transcript"],
            "scene_analysis": ["scene_index"], "story": ["scene_index", "scene_analysis"],
            "highlights": ["manifest", "transcript", "scene_index", "scene_analysis", "characters", "story", "knowledge"],
            "plan": ["manifest", "transcript", "characters", "story", "knowledge", "highlights"],
            "storyboard": ["manifest", "characters", "story", "knowledge", "highlights", "plan", "scene_index", "scene_analysis"],
            "tts": ["plan"],
            "pre_qc": ["manifest", "transcript", "characters", "story", "knowledge", "highlights", "plan"],
            "render": ["pre_qc"], "post_qc": ["pre_qc"], "delivery": ["pre_qc", "post_qc", "highlights", "plan"],
        }
        payload: dict = {"config": self.state.config_fingerprint, "inputs": self.state.input_fingerprint}
        payload["files"] = {name: content_fingerprint(self.paths[name]) for name in dependencies[stage]}
        if stage == "tts":
            board = self._storyboard_identity()
            payload["voiceover"] = [
                {key: segment.get(key) for key in ("segment_id", "text", "planned_duration_sec", "visuals", "narration_job")}
                for segment in board.get("segments", []) if segment.get("mode") == "voiceover"
            ]
        if stage in {"pre_qc", "render", "post_qc", "delivery"}:
            payload["storyboard"] = self._storyboard_identity()
            payload["audio"] = {
                segment["audio_file"]: content_fingerprint(segment["audio_file"])
                if Path(segment["audio_file"]).is_file() else "MISSING"
                for segment in payload["storyboard"].get("segments", [])
                if segment.get("mode") == "voiceover" and segment.get("audio_file")
            }
        if stage in {"post_qc", "delivery"}:
            output = read_json(self.paths["storyboard"]).get("output", {})
            payload["output"] = output
            payload["output_files"] = {
                key: content_fingerprint(output[key]) if Path(output[key]).is_file() else "MISSING"
                for key in ("final_video", "subtitle", "edl", "preview_video") if output.get(key)
            }
            evidence = Path(output.get("review_file") or self.work_dir / "output" / "review_evidence.json")
            payload["review_evidence"] = content_fingerprint(evidence) if evidence.is_file() else None
        return fingerprint_json(payload)

    def _required_artifacts(self, stage: str, artifact: Path | None) -> list[Path]:
        if stage in {"storyboard", "tts"}:
            paths = [self._snapshot_path(stage)]
            if stage == "tts":
                paths.append(self.paths["script"])
                paths.extend(Path(segment.audio_file) for segment in self._storyboard().segments
                             if segment.mode == "voiceover" and segment.audio_file)
            return paths
        paths = [artifact] if artifact else []
        if stage == "story":
            paths.extend([self.paths["characters"], self.paths["knowledge"]])
        elif stage == "ingest":
            paths.extend(Path(source.subtitle_path) for source in self._manifest().sources if source.subtitle_path)
        elif stage == "scenes":
            for unit in self._scene_index().units:
                paths.extend(Path(path) for path in unit.frame_paths)
                if unit.contact_sheet_path:
                    paths.append(Path(unit.contact_sheet_path))
        elif stage == "render":
            output = self._storyboard().output
            paths.extend(Path(output[key]) for key in ("preview_video", "subtitle", "edl") if output.get(key))
            if not all(output.get(key) for key in ("final_video", "preview_video", "subtitle", "edl")):
                raise ValueError("Render did not provide the complete delivery artifact set")
        elif stage == "delivery":
            paths.append(self.work_dir / "output" / "master.srt")
        return list(dict.fromkeys(paths))

    def _artifact_exists(self, stage: str) -> bool:
        record = self.state.stages[stage]
        artifacts = getattr(record, "artifacts", {})
        if not artifacts:
            return False
        if stage in {"storyboard", "tts"} and not self.paths["storyboard"].is_file():
            return False
        for name, expected in artifacts.items():
            path = Path(name)
            optional_debug = (stage == "scenes" and not self.config.runtime.keep_debug_frames
                              and self.state.stages["scene_analysis"].status == "passed"
                              and self.state.stages["highlights"].status == "passed"
                              and (path.is_relative_to(self.work_dir / "frames")
                                   or path.is_relative_to(self.work_dir / "contact_sheets")))
            if optional_debug and not path.exists():
                continue
            if not path.is_file() or content_fingerprint(path) != expected:
                return False
        try:
            return record.input_fingerprint == self._stage_inputs(stage)
        except (OSError, ValueError, KeyError):
            return False

    def _adopt_manual_artifacts(self, from_stage: str) -> None:
        # --from-stage is the explicit handoff: preserve edits to preceding authored JSONs.
        for stage in STAGES[:min(STAGES.index(from_stage), STAGES.index("tts"))]:
            record = self.state.stages[stage]
            if record.status != "passed":
                continue
            artifacts = getattr(record, "artifacts", {})
            if artifacts and all(Path(path).is_file() for path in artifacts):
                try:
                    input_fingerprint = self._stage_inputs(stage)
                except (OSError, ValueError, KeyError):
                    continue  # Missing dependencies must be rebuilt by the normal stage loop.
                record.artifacts = {path: content_fingerprint(path) for path in artifacts}
                record.input_fingerprint = input_fingerprint
        self.store.save(self.state)

    def run(self, *, until: str | None = None, from_stage: str | None = None) -> Path:
        if until and until not in STAGES:
            raise ValueError(f"Unknown stage: {until}")
        if from_stage and from_stage not in STAGES:
            raise ValueError(f"Unknown stage: {from_stage}")
        if from_stage:
            self._adopt_manual_artifacts(from_stage)
            self.store.invalidate_from(self.state, from_stage)
        for stage in self.store.selected_stages(until):
            if self.state.stages[stage].status == "passed" and self._artifact_exists(stage):
                self._say(f"[cache] {stage}")
                continue
            # Rebuilding an upstream artifact invalidates every dependent receipt, including QC.
            self.store.invalidate_from(self.state, stage)
            self._run_stage(stage)
        return (self.paths["delivery"] if self.state.stages["delivery"].status == "passed"
                and self.paths["delivery"].is_file() else self.work_dir)

    def _run_stage(self, stage: str) -> None:
        handler = getattr(self, f"_stage_{stage}")
        self._say(f"[start] {stage}")
        self.store.start(self.state, stage)
        try:
            artifact = handler()
            if stage in {"storyboard", "tts"}:
                write_json(self._snapshot_path(stage), read_json(self.paths["storyboard"]))
            required = self._required_artifacts(stage, artifact)
            fingerprints = {str(path): content_fingerprint(path) for path in required}
            self.store.pass_stage(
                self.state, stage, artifact=str(artifact) if artifact else None,
                fingerprint=content_fingerprint(artifact) if artifact and artifact.is_file() else None,
                artifacts=fingerprints, input_fingerprint=self._stage_inputs(stage),
            )
            self._say(f"[done] {stage}")
        except Exception as exc:
            self.store.fail(self.state, stage, exc)
            self._say(f"[failed] {stage}: {exc}")
            raise

    def _manifest(self) -> SourceManifest:
        return SourceManifest.model_validate(read_json(self.paths["manifest"]))

    def _transcript(self) -> TranscriptDocument:
        return TranscriptDocument.model_validate(read_json(self.paths["transcript"]))

    def _scene_index(self) -> SceneIndex:
        return SceneIndex.model_validate(read_json(self.paths["scene_index"]))

    def _scene_analysis(self) -> SceneAnalysisDocument:
        return SceneAnalysisDocument.model_validate(read_json(self.paths["scene_analysis"]))

    def _story_bundle(self):
        return load_story_bundle(
            CharacterRegistry.model_validate(read_json(self.paths["characters"])),
            StoryGraph.model_validate(read_json(self.paths["story"])),
            KnowledgeTimeline.model_validate(read_json(self.paths["knowledge"])),
        )

    def _highlights(self) -> HighlightDocument:
        return HighlightDocument.model_validate(read_json(self.paths["highlights"]))

    def _plan(self) -> RecapPlan:
        return RecapPlan.model_validate(read_json(self.paths["plan"]))

    def _storyboard(self) -> Storyboard:
        return Storyboard.model_validate(read_json(self.paths["storyboard"]))

    def _stage_ingest(self) -> Path:
        manifest = build_manifest(self.input_path, self.config, self.work_dir)
        write_json(self.paths["manifest"], manifest)
        return self.paths["manifest"]

    def _stage_transcript(self) -> Path:
        transcript = build_transcript(self._manifest(), self.config)
        write_json(self.paths["transcript"], transcript)
        return self.paths["transcript"]

    def _stage_scenes(self) -> Path:
        scene_index = build_scene_index(
            self._manifest(), self._transcript(), self.config, self.work_dir
        )
        write_json(self.paths["scene_index"], scene_index)
        return self.paths["scene_index"]

    def _stage_scene_analysis(self) -> Path:
        analysis = analyze_scenes(self._scene_index(), self.config, self.client)
        write_json(self.paths["scene_analysis"], analysis)
        return self.paths["scene_analysis"]

    def _stage_story(self) -> Path:
        bundle = build_story(
            self._scene_index(), self._scene_analysis(), self.config, self.client
        )
        write_json(self.paths["characters"], bundle.character_registry)
        write_json(self.paths["story"], bundle.story_graph)
        write_json(self.paths["knowledge"], bundle.knowledge_timeline)
        return self.paths["story"]

    def _stage_highlights(self) -> Path:
        highlights = build_highlights(
            self._manifest(),
            self._transcript(),
            self._scene_index(),
            self._scene_analysis(),
            self._story_bundle(),
            self.config,
            self.client,
            self.work_dir,
        )
        write_json(self.paths["highlights"], highlights)
        return self.paths["highlights"]

    def _stage_plan(self) -> Path:
        plan = build_plan(
            self._manifest(),
            self._transcript(),
            self._story_bundle(),
            self._highlights(),
            self.config,
            self.client,
        )
        write_json(self.paths["plan"], plan)
        return self.paths["plan"]

    def _stage_storyboard(self) -> Path:
        storyboard = build_storyboard(
            project_name=self.project_name,
            manifest=self._manifest(),
            story=self._story_bundle(),
            highlights=self._highlights(),
            plan=self._plan(),
            config=self.config,
            client=self.client,
            scene_index=self._scene_index(),
            scene_analysis=self._scene_analysis(),
        )
        self._attach_original_cues(storyboard)
        write_json(self.paths["storyboard"], storyboard)
        write_human_script(storyboard, self.paths["script"])
        return self.paths["storyboard"]

    def _attach_original_cues(self, storyboard: Storyboard) -> None:
        transcript = self._transcript()
        manifest_fingerprints = {source.source_id: source.fingerprint for source in self._manifest().sources}
        for segment in storyboard.segments:
            if segment.mode != "original":
                continue
            segment.original_cues = [
                OriginalCue.model_validate(cue.model_dump(mode="json")) for cue in transcript.segments
                if any(cue.source_id == visual.source_id and cue.end > visual.start
                       and cue.start < visual.end for visual in segment.visuals)
            ]
            segment.original_cues_verified = bool(segment.visuals) and all(
                visual.source_id in transcript.source_fingerprints
                and transcript.source_fingerprints[visual.source_id] == manifest_fingerprints.get(visual.source_id)
                for visual in segment.visuals
            )

    def _effective_tts_config(self) -> AppConfig:
        effective = self.config.model_copy(deep=True)
        effective.format.vo_chars_per_sec = tuple(get_plan_constraints(self._plan(), self.config)["vo_chars_per_sec"])
        return effective

    def _stage_tts(self) -> Path:
        storyboard = synthesize_storyboard(
            self._storyboard(), self._effective_tts_config(), self.client, self.work_dir
        )
        self._attach_original_cues(storyboard)
        write_json(self.paths["storyboard"], storyboard)
        write_human_script(storyboard, self.paths["script"])
        return self.paths["storyboard"]

    def _stage_pre_qc(self) -> Path:
        storyboard = self._storyboard()
        self._attach_original_cues(storyboard)
        write_json(self.paths["storyboard"], storyboard)
        report = preflight_qc(
            manifest=self._manifest(),
            transcript=self._transcript(),
            story=self._story_bundle(),
            highlights=self._highlights(),
            plan=self._plan(),
            storyboard=storyboard,
            config=self.config,
            client=self.client,
        )
        write_json(self.paths["pre_qc"], report)
        if report.status == "BLOCKED":
            raise StageBlocked("pre_qc", report)
        return self.paths["pre_qc"]

    def _stage_render(self) -> Path:
        storyboard = render_storyboard(self._storyboard(), self.config, self.work_dir)
        write_json(self.paths["storyboard"], storyboard)
        final = Path(storyboard.output["final_video"])
        return final

    def _clear_render_outputs(self) -> None:
        for relative in ["clips/rendered", "clips/visuals"]:
            shutil.rmtree(self.work_dir / relative, ignore_errors=True)
        for name in ["base_no_subtitles.mp4", "final.mp4", "preview.mp4"]:
            (self.work_dir / "output" / name).unlink(missing_ok=True)

    def _stage_post_qc(self) -> Path:
        storyboard = self._storyboard()
        auto_repairable = {
            "MISSING_OUTPUT_REFERENCE",
            "MISSING_FINAL_VIDEO",
            "MISSING_VIDEO_STREAM",
            "MISSING_AUDIO_STREAM",
            "OUTPUT_DIMENSION_MISMATCH",
            "OUTPUT_DURATION_MISMATCH",
        }
        report: QCReport | None = None
        attempts = 1
        while attempts <= self.config.qc.self_repair_rounds + 1:
            report = post_render_qc(
                storyboard=storyboard,
                config=self.config,
                attempts=attempts,
            )
            # Persist the current finding before a repair that might itself fail.
            write_json(self.paths["post_qc"], report)
            if report.status != "BLOCKED":
                break
            blocking_ids = {item.rule_id for item in report.findings if item.blocking}
            if attempts > self.config.qc.self_repair_rounds or not blocking_ids <= auto_repairable:
                break
            self._say(f"[repair] render pass {attempts + 1}")
            self._clear_render_outputs()
            storyboard = render_storyboard(storyboard, self.config, self.work_dir)
            write_json(self.paths["storyboard"], storyboard)
            final = Path(storyboard.output["final_video"])
            self.store.pass_stage(
                self.state, "render", artifact=str(final), fingerprint=content_fingerprint(final),
                artifacts={str(path): content_fingerprint(path) for path in self._required_artifacts("render", final)},
                input_fingerprint=self._stage_inputs("render"),
            )
            attempts += 1
        assert report is not None
        write_json(self.paths["post_qc"], report)
        if report.status == "BLOCKED":
            raise StageBlocked("post_qc", report)
        return self.paths["post_qc"]

    def _stage_delivery(self) -> Path:
        storyboard = self._storyboard()
        pre_report = QCReport.model_validate(read_json(self.paths["pre_qc"]))
        post_report = QCReport.model_validate(read_json(self.paths["post_qc"]))
        final_status = (
            "DEGRADED"
            if "DEGRADED" in {pre_report.status, post_report.status}
            else "PASSED"
        )
        output_dir = self.work_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        source_srt = Path(storyboard.output.get("subtitle", ""))
        if source_srt.exists():
            shutil.copy2(source_srt, output_dir / "master.srt")
        selected_highlights = [
            candidate
            for candidate in self._highlights().candidates
            if candidate.selected
        ]
        lines = [
            f"# {self.project_name} · 影视解说交付报告",
            "",
            f"- 最终状态：**{final_status}**",
            f"- 最终成片：`{storyboard.output.get('final_video')}`",
            f"- 预览：`{storyboard.output.get('preview_video')}`",
            f"- 字幕：`{output_dir / 'master.srt'}`",
            f"- EDL：`{storyboard.output.get('edl')}`",
            f"- Storyboard：`{self.paths['storyboard']}`",
            f"- 目标时长：{self._plan().target_duration_sec:.1f}s",
            f"- 实际时长：{float(storyboard.output.get('duration_sec', 0)):.1f}s",
            f"- 入选高光：{len(selected_highlights)} 个",
            f"- LLM：`{self.config.models.llm_model}`",
            f"- VLM：`{self.config.models.vlm_model}`",
            f"- ASR：`{self._transcript().provider}`",
            f"- TTS：`{self.config.tts.provider}` / `{self.config.tts.voice}`",
            "- 云端上传：模型分析会上传压缩 contact sheet 与对应文本；默认不上传完整影片文件",
            "",
            "## 主线",
            "",
            self._story_bundle().story_graph.main_plot,
            "",
            "## 高光清单",
            "",
        ]
        for candidate in selected_highlights:
            lines.append(
                f"- `{candidate.highlight_id}` {candidate.source_id} "
                f"{candidate.start:.2f}-{candidate.end:.2f}s · "
                f"{', '.join(candidate.types)} · {candidate.selection_reason}"
            )
        lines.extend(
            [
                "",
                "## QC 摘要",
                "",
                f"- 渲染前：{pre_report.status}，{len(pre_report.findings)} 项发现",
                f"- 渲染后：{post_report.status}，{len(post_report.findings)} 项发现",
                "",
                "### 未阻断问题",
                "",
            ]
        )
        non_blocking = [
            item
            for item in pre_report.findings + post_report.findings
            if not item.blocking
        ]
        if non_blocking:
            for item in non_blocking:
                lines.append(f"- `{item.rule_id}` {item.message}")
        else:
            lines.append("- 无")
        lines.extend(
            [
                "",
                "## 发布边界",
                "",
                "本工具只生成草稿或成片文件，不自动发布，不规避版权检测。",
                "发布者仍需确认影视素材、音乐、配音与平台规则所需权利。",
                "",
            ]
        )
        if self.config.format.duration_mode == "series":
            lines.extend(
                [
                    "## Series 提示",
                    "",
                    "当前运行时每次只生成一个 Part。对于多集或超长素材，建议按故事阶段分别运行，",
                    "并让每个 Part 拥有独立钩子、阶段回报和下一段问题。",
                    "",
                ]
            )
        self.paths["delivery"].write_text("\n".join(lines), encoding="utf-8")
        if not self.config.runtime.keep_debug_frames:
            shutil.rmtree(self.work_dir / "frames", ignore_errors=True)
            shutil.rmtree(self.work_dir / "contact_sheets", ignore_errors=True)
        return self.paths["delivery"]
