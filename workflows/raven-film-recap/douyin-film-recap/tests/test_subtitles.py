from __future__ import annotations

from douyin_film_recap.models import Storyboard, StoryboardSegment, VisualReference
from douyin_film_recap.subtitles import build_cues, output_timeline


def test_subtitles_use_output_timeline(app_config) -> None:
    storyboard = Storyboard(
        project_name="demo",
        sources=[],
        plan_fingerprint="x",
        target_duration_sec=5,
        segments=[
            StoryboardSegment(
                segment_id="s1",
                beat_id="b1",
                mode="original",
                title="原片",
                text="你好",
                text_raw="你好",
                visuals=[VisualReference(source_id="src", start=10, end=12)],
                audio_owner="original_dialogue",
                planned_duration_sec=2,
                notes="完整原声",
            ),
            StoryboardSegment(
                segment_id="s2",
                beat_id="b2",
                mode="voiceover",
                title="解说",
                text="他这才意识到，真正的危险刚刚开始。",
                visuals=[VisualReference(source_id="src", start=20, end=23)],
                audio_owner="narration",
                narration_job="foreshadow",
                mute_original=True,
                planned_duration_sec=3,
                audio_duration_sec=3,
                tts_word_boundaries=[],
                notes="补充预期",
            ),
        ],
    )
    timeline = output_timeline(storyboard)
    assert timeline[1]["start"] == 2
    cues = build_cues(storyboard, app_config)
    assert cues
    assert any(cue.start >= 2 for cue in cues if "危险" in cue.text)
    assert all(cue.end > cue.start for cue in cues)


import pytest
from pydantic import ValidationError
from douyin_film_recap.config import RenderConfig, TTSConfig, StoryConfig, SceneConfig
from douyin_film_recap.subtitles import _split_text


@pytest.mark.parametrize("value", [0, -1])
def test_invalid_subtitle_limits_fail_immediately(value):
    for name in ("subtitle_max_chars_per_line", "subtitle_max_lines", "width", "height", "fps"):
        with pytest.raises(ValidationError):
            RenderConfig(**{name: value})
    with pytest.raises(ValueError, match="positive integer"):
        _split_text("甲乙", value)
    with pytest.raises(ValueError, match="positive integer"):
        _split_text("", value)
    with pytest.raises(ValidationError):
        StoryConfig(chunk_units=value)
    with pytest.raises(ValidationError):
        SceneConfig(contact_sheet_units=value)


def test_smallest_subtitle_limit_and_speed_range():
    assert _split_text("甲乙", 1) == ["甲", "乙"]
    assert RenderConfig(subtitle_max_chars_per_line=1, subtitle_max_lines=1)
    with pytest.raises(ValidationError):
        TTSConfig(min_speedup=1.1, max_speedup=1.0)


from douyin_film_recap.subtitles import _distributed_cues, _cues_from_boundaries


def test_short_distributed_cues_never_extend_into_next():
    cues = _distributed_cues("甲乙丙丁", 0, 0.4, 1)
    assert len(cues) == 4
    assert all(a.end <= b.start for a, b in zip(cues, cues[1:]))
    assert cues[-1].end == 0.4
    assert "".join(cue.text for cue in cues) == "甲乙丙丁"


def test_fast_word_boundaries_do_not_overlap():
    segment = StoryboardSegment(segment_id="s", beat_id="b", mode="voiceover",
        title="测试", text="甲乙丙", planned_duration_sec=0.4,
        audio_duration_sec=0.4, audio_owner="narration", visuals=[], notes="测试",
        tts_word_boundaries=[{"text": text, "start": index * 0.1, "duration": 0.1}
                             for index, text in enumerate("甲乙丙")])
    cues = _cues_from_boundaries(segment, 1, 1)
    assert len(cues) == 3
    assert all(a.end <= b.start for a, b in zip(cues, cues[1:]))
    assert cues[-1].end <= 1.4


def test_post_qc_blocks_overlapping_caption_track(tmp_path, app_config, monkeypatch):
    from douyin_film_recap import qc
    from douyin_film_recap.subtitles import SubtitleCue, write_srt
    cues = [SubtitleCue(0, 0.35, "甲"), SubtitleCue(0.1, 0.4, "乙")]
    subtitle = write_srt(cues, tmp_path / 'overlap.srt')
    storyboard = Storyboard(project_name="qc", sources=[], plan_fingerprint="x",
        target_duration_sec=1, segments=[], output={"subtitle": str(subtitle)})
    monkeypatch.setattr(qc, 'build_cues', lambda *args, **kwargs: cues)
    builder = qc.FindingBuilder('test')
    qc._subtitle_delivery_checks(builder, storyboard, app_config, 1, 'unused')
    assert any(item.rule_id == 'INVALID_SUBTITLE_FILE' and item.blocking
               and 'overlap' in item.message for item in builder.findings)
