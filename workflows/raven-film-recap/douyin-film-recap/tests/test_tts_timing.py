from __future__ import annotations

import pytest

from douyin_film_recap.models import StoryboardSegment, VisualReference
from douyin_film_recap.tts import _fit_audio_timing


def test_fit_audio_timing_scales_duration_and_boundaries() -> None:
    segment = StoryboardSegment(
        segment_id="s1",
        beat_id="b1",
        mode="voiceover",
        title="解说",
        text="危险正在逼近",
        visuals=[VisualReference(source_id="src", start=0, end=5)],
        audio_owner="narration",
        narration_job="foreshadow",
        planned_duration_sec=5,
        audio_source_duration_sec=5.25,
        audio_duration_sec=5.25,
        tts_word_boundaries=[{"text": "危险", "start": 1.05, "duration": 0.42}],
        notes="测试",
    )
    _fit_audio_timing(segment, desired_duration=5, min_speed=0.95, max_speed=1.08)
    assert segment.audio_speed == pytest.approx(1.05)
    assert segment.audio_duration_sec == pytest.approx(5)
    assert segment.tts_word_boundaries[0]["start"] == pytest.approx(1)
    assert segment.tts_word_boundaries[0]["duration"] == pytest.approx(0.4)


def test_fit_audio_timing_refuses_excessive_speedup() -> None:
    segment = StoryboardSegment(
        segment_id="s1",
        beat_id="b1",
        mode="voiceover",
        title="解说",
        text="过长解说",
        visuals=[VisualReference(source_id="src", start=0, end=5)],
        audio_owner="narration",
        narration_job="context",
        planned_duration_sec=5,
        audio_source_duration_sec=7,
        audio_duration_sec=7,
        notes="测试",
    )
    _fit_audio_timing(segment, desired_duration=5, min_speed=0.95, max_speed=1.08)
    assert segment.audio_speed == pytest.approx(1)
    assert segment.audio_duration_sec == pytest.approx(7)
