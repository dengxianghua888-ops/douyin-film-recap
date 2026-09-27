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
