"""Contract regressions; mock media probes do not claim real media acceptance."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from douyin_film_recap import qc, render
from douyin_film_recap.models import OriginalCue, Storyboard, StoryboardSegment, TranscriptWord, VisualReference
from douyin_film_recap.subtitles import build_cues, write_srt
from douyin_film_recap.utils import content_fingerprint
from test_qc import _base_artifacts


@pytest.mark.parametrize("changes", [
    {"path": "/tmp/different.mp4"}, {"fingerprint": "different"}, {"duration": 0.1},
])
def test_preflight_binds_storyboard_to_indexed_source(app_config, changes):
    manifest, transcript, story, highlights, plan, storyboard = _base_artifacts(app_config, False)
    storyboard.sources = [storyboard.sources[0].model_copy(update=changes)]
    report = qc.preflight_qc(manifest=manifest, transcript=transcript, story=story,
                             highlights=highlights, plan=plan, storyboard=storyboard, config=app_config)
    assert report.status == "BLOCKED"
    assert "SOURCE_IDENTITY_MISMATCH" in {finding.rule_id for finding in report.findings}


def _original_segment(**updates):
    values = dict(segment_id="s1", beat_id="b1", mode="original", title="动作",
                  text="场景描述并非台词", text_raw="", audio_owner="action_sound",
                  visuals=[VisualReference(source_id="src", start=10, end=20)],
                  planned_duration_sec=10, notes="保留完整动作", original_cues_verified=True)
    values.update(updates)
    return StoryboardSegment(**values)


def _storyboard(segment):
    return Storyboard(project_name="test", sources=[], plan_fingerprint="test",
                      target_duration_sec=segment.planned_duration_sec, segments=[segment])


def test_original_captions_follow_source_timing_including_silence(app_config):
    segment = _original_segment(original_cues=[
        OriginalCue(source_id="src", start=11, end=12, text="先停下"),
        OriginalCue(source_id="src", start=17, end=18, text="现在走"),
    ])
    cues = build_cues(_storyboard(segment), app_config)
    assert [(cue.start, cue.end, cue.text) for cue in cues] == [(1, 2, "先停下"), (7, 8, "现在走")]


def test_silent_original_never_gets_scene_description_as_subtitle(app_config):
    assert build_cues(_storyboard(_original_segment()), app_config) == []


@pytest.mark.parametrize("timing_source,expected", [("estimated", []), ("unknown", []), ("asr", ["留下"]), ("aligned", ["留下"])])
def test_partial_original_cue_requires_real_word_timing(app_config, timing_source, expected):
    cue = OriginalCue(source_id="src", start=9, end=12, text="你留下", words=[
        TranscriptWord(start=9, end=10, text="你", timing_source=timing_source),
        TranscriptWord(start=10.5, end=11.5, text="留下", timing_source=timing_source),
    ])
    segment = _original_segment(original_cues=[cue])
    assert [item.text for item in build_cues(_storyboard(segment), app_config)] == expected


def test_render_and_edl_consume_identical_vo_source_intervals(tmp_path, app_config, monkeypatch):
    audio = tmp_path / "vo.wav"
    audio.write_bytes(b"fixture")
    segment = StoryboardSegment(segment_id="vo", beat_id="b1", mode="voiceover", title="旁白",
        text="开始", visuals=[VisualReference(source_id="src", start=0, end=5),
                              VisualReference(source_id="src", start=5, end=10)],
        audio_owner="narration", planned_duration_sec=2, audio_duration_sec=2,
        audio_file=str(audio), notes="画面预算多于真实配音")
    consumed = []
    monkeypatch.setattr(render, "_render_visual_piece", lambda visual, source, duration, *args, **kwargs: consumed.append((visual.start, visual.start + duration)))
    monkeypatch.setattr(render, "_concat_copy", lambda *args: None)
    monkeypatch.setattr(render, "run_command", lambda *args, **kwargs: None)
    render._render_voiceover_segment(segment, {"src": object()}, tmp_path / "out.mp4", tmp_path, app_config)
    spans = render.build_edl(_storyboard(segment))[0]["source_spans"]
    assert consumed == [(0, 2)]
    assert [(span["start"], span["end"]) for span in spans] == consumed
    assert spans[0]["output_start"] == 0 and spans[0]["output_end"] == 2
    assert segment.visuals[0].end == 5  # Availability plan remains immutable.


def _prepared_delivery(tmp_path, app_config, monkeypatch):
    segment = _original_segment(visuals=[VisualReference(source_id="src", start=10, end=12)],
        planned_duration_sec=2, original_cues=[OriginalCue(source_id="src", start=10, end=12, text="停下")])
    board = _storyboard(segment)
    final = tmp_path / "final.mp4"
    final.write_bytes(b"mock media bytes - probe is explicitly stubbed")
    srt = write_srt(build_cues(board, app_config), tmp_path / "master.srt")
    board.output = {"final_video": str(final), "subtitle": str(srt),
        "final_fingerprint": content_fingerprint(final), "subtitle_fingerprint": content_fingerprint(srt),
        "subtitle_burn_status": "applied" if app_config.render.subtitle_burn_in else "not_requested",
        "review_file": str(tmp_path / "review_evidence.json")}
    probe = {"streams": [
        {"codec_type": "video", "codec_name": "h264", "width": app_config.render.width,
         "height": app_config.render.height, "avg_frame_rate": f"{app_config.render.fps}/1", "r_frame_rate": f"{app_config.render.fps}/1"},
        {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
    ]}
    monkeypatch.setattr(qc, "ffprobe_json", lambda _: probe)
    monkeypatch.setattr(qc, "media_duration", lambda _: 2)
    monkeypatch.setattr(qc, "_detect_intervals", lambda *args: [])
    return board, probe


def _review_record(board, *, fingerprint=None, ranges=None):
    """Synthetic records only exercise acceptance logic; no claim of listening."""
    Path(board.output["review_file"]).write_text(json.dumps({
        "artifact_sha256": fingerprint or board.output["final_fingerprint"],
        "checks": [{"kind": kind, "result": "passed", "method": method,
                    "reviewer": "test fixture", "evidence": ["synthetic regression fixture"],
                    "checked_ranges": ranges or [[0, 2]]}
                   for kind, method in [("visual", "human_frame_review"), ("audio", "human_listen")]],
    }), encoding="utf-8")


def test_structural_qc_alone_is_not_media_acceptance(tmp_path, app_config, monkeypatch):
    board, _ = _prepared_delivery(tmp_path, app_config, monkeypatch)
    report = qc.post_render_qc(storyboard=board, config=app_config)
    assert report.status == "DEGRADED"
    assert report.coverage["structural"]["status"] == "checked"
    assert report.coverage["visual"]["status"] == report.coverage["audio"]["status"] == "not_checked"


def test_bound_independent_review_can_complete_qc(tmp_path, app_config, monkeypatch):
    board, _ = _prepared_delivery(tmp_path, app_config, monkeypatch)
    _review_record(board)
    report = qc.post_render_qc(storyboard=board, config=app_config)
    assert report.status == "PASSED"
    assert report.coverage["audio"]["provenance"] == "independent_review_record"


@pytest.mark.parametrize("record", [{"fingerprint": "old-artifact"}, {"ranges": [[0, 1]]}])
def test_stale_or_partial_review_does_not_complete_qc(tmp_path, app_config, monkeypatch, record):
    board, _ = _prepared_delivery(tmp_path, app_config, monkeypatch)
    _review_record(board, **record)
    assert qc.post_render_qc(storyboard=board, config=app_config).status == "DEGRADED"


def test_wrong_fps_codecs_and_missing_subtitles_are_blocking(tmp_path, app_config, monkeypatch):
    board, probe = _prepared_delivery(tmp_path, app_config, monkeypatch)
    _review_record(board)
    probe["streams"][0].update(avg_frame_rate="12/1", r_frame_rate="12/1", codec_name="mpeg4")
    probe["streams"][1]["codec_name"] = "mp3"
    Path(board.output["subtitle"]).unlink()
    report = qc.post_render_qc(storyboard=board, config=app_config)
    assert report.status == "BLOCKED"
    assert {"OUTPUT_FPS_MISMATCH", "OUTPUT_VIDEO_CODEC_MISMATCH", "OUTPUT_AUDIO_CODEC_MISMATCH", "MISSING_SUBTITLE_FILE"} <= {item.rule_id for item in report.findings}


def test_subtitle_timing_must_match_current_decisions(tmp_path, app_config, monkeypatch):
    board, _ = _prepared_delivery(tmp_path, app_config, monkeypatch)
    _review_record(board)
    Path(board.output["subtitle"]).write_text("1\n00:00:00,000 --> 00:00:09,000\n停下\n", encoding="utf-8")
    report = qc.post_render_qc(storyboard=board, config=app_config)
    assert report.status == "BLOCKED"
    assert "INVALID_SUBTITLE_FILE" in {item.rule_id for item in report.findings}


def test_burn_in_request_requires_bound_execution_record(tmp_path, app_config, monkeypatch):
    app_config.render.subtitle_burn_in = True
    board, _ = _prepared_delivery(tmp_path, app_config, monkeypatch)
    _review_record(board)
    board.output["subtitle_burn_status"] = "not_requested"
    report = qc.post_render_qc(storyboard=board, config=app_config)
    assert "SUBTITLE_BURN_UNVERIFIED" in {item.rule_id for item in report.findings}
    assert report.status == "BLOCKED"


def test_finalize_refuses_silent_subtitle_loss(tmp_path, app_config):
    app_config.render.subtitle_burn_in = True
    with pytest.raises(ValueError, match="captions are missing"):
        render._finalize(tmp_path / "base.mp4", tmp_path / "missing.srt", tmp_path / "final.mp4", app_config)
