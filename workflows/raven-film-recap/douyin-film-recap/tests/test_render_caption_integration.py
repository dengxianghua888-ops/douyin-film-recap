from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from douyin_film_recap.media import ffprobe_json
from douyin_film_recap.models import OriginalCue, SourceInfo, Storyboard, StoryboardSegment, VisualReference
from douyin_film_recap.qc import post_render_qc
from douyin_film_recap.render import render_storyboard
from douyin_film_recap.utils import run_command

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")


def test_burned_captions_and_consumed_edl_real_ffmpeg(tmp_path, app_config):
    filters = run_command(["ffmpeg", "-hide_banner", "-filters"]).stdout
    if "subtitles" not in filters:
        pytest.skip("FFmpeg libass required")
    source = tmp_path / "synthetic.mp4"
    audio = tmp_path / "tone.m4a"
    run_command(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                 "testsrc2=size=640x360:rate=24:duration=6", "-f", "lavfi", "-i",
                 "sine=frequency=440:sample_rate=48000:duration=6", "-c:v", "libx264",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", source])
    run_command(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                 "sine=frequency=660:sample_rate=48000:duration=2", "-c:a", "aac", audio])
    config = app_config.model_copy(deep=True)
    config.render.subtitle_burn_in = True
    # The static FFmpeg can advertise a CoreText PingFang family whose file is
    # absent. Explicitly load a real CJK font instead of trusting family lookup.
    candidates = [
        (Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"), "Arial Unicode MS"),
        (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"), "Noto Sans CJK JP"),
    ]
    selected = next(((path, family) for path, family in candidates if path.is_file()), None)
    if selected is None:
        pytest.skip("A known readable CJK font is required for the burn-in integration test")
    config.render.subtitle_font_file = str(selected[0])
    config.render.subtitle_font = selected[1]
    info = SourceInfo(source_id="s1", path=str(source), fingerprint="synthetic-fixture",
                      filename=source.name, duration=6, width=640, height=360, fps=24)
    board = Storyboard(project_name="caption-regression", sources=[info], plan_fingerprint="fixture",
                      target_duration_sec=4, segments=[
        StoryboardSegment(segment_id="original", beat_id="b1", mode="original", title="原声",
                          text="完整原声", text_raw="完整原声", audio_owner="original_dialogue",
                          original_cues=[OriginalCue(source_id="s1", start=1.5, end=2.6, text="完整原声")],
                          original_cues_verified=True,
                          visuals=[VisualReference(source_id="s1", start=1, end=3)],
                          planned_duration_sec=2, notes="synthetic caption timing fixture"),
        StoryboardSegment(segment_id="vo", beat_id="b2", mode="voiceover", title="配音",
                          text="中文配音字幕", audio_owner="narration", mute_original=True,
                          visuals=[VisualReference(source_id="s1", start=3, end=6)],
                          planned_duration_sec=2, audio_file=str(audio), audio_duration_sec=2,
                          tts_word_boundaries=[{"text": "中文配音字幕", "start": 0.2, "duration": 1.6}],
                          notes="tone is synthetic; not a speech quality test"),
    ])
    board = render_storyboard(board, config, tmp_path / "render")
    probe = ffprobe_json(board.output["final_video"])
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert video["codec_name"] == "h264" and video["avg_frame_rate"] == "24/1"
    assert (video["width"], video["height"]) == (360, 640)
    assert board.output["subtitle_burn_status"] == "applied"
    font_report = json.loads(Path(board.output["subtitle_font_report"]).read_text())
    assert font_report["status"] == "applied"
    assert font_report["missing_glyph_errors"] == []
    assert any("fontselect:" in line for line in font_report["font_selection_log"])
    srt = Path(board.output["subtitle"]).read_text()
    assert "00:00:00,500 --> 00:00:01,600" in srt
    assert "00:00:02,200 --> 00:00:03,800" in srt
    edl = json.loads(Path(board.output["edl"]).read_text())
    assert edl[1]["source_spans"][0]["end"] == 5
    report = post_render_qc(storyboard=board, config=config)
    assert report.status == "DEGRADED"  # No fabricated viewing/listening record.
    assert not any(f.blocking for f in report.findings), report.model_dump()
    assert report.coverage["visual"]["status"] == "not_checked"
    (tmp_path / "qc.json").write_text(report.model_dump_json(indent=2))
    run_command(["ffmpeg", "-y", "-v", "error", "-ss", "0.8", "-i", board.output["final_video"],
                 "-frames:v", "1", tmp_path / "caption-frame.png"])
