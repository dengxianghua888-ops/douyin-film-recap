from __future__ import annotations

from douyin_film_recap.models import (
    HighlightCandidate,
    HighlightDocument,
    SourceInfo,
    SourceManifest,
    Storyboard,
    StoryboardSegment,
    VisualReference,
)
from douyin_film_recap.planning import _normalize_storyboard


def test_visual_highlight_id_is_promoted_to_segment(app_config) -> None:
    source = SourceInfo(
        source_id="src_001",
        path="/tmp/source.mp4",
        fingerprint="abc",
        filename="source.mp4",
        duration=20,
        width=1920,
        height=1080,
        fps=25,
    )
    manifest = SourceManifest(
        sources=[source], config_fingerprint=app_config.fingerprint()
    )
    highlights = HighlightDocument(
        genre_profile="drama",
        candidates=[
            HighlightCandidate(
                highlight_id="h0001",
                source_id="src_001",
                start=4,
                end=8,
                types=["dialogue"],
                quote="别再逼我。",
                story_function="摊牌",
                selected=True,
            )
        ],
        weights={},
        source_fingerprints={"src_001": "abc"},
    )
    storyboard = Storyboard(
        project_name="demo",
        sources=[source],
        plan_fingerprint="p",
        target_duration_sec=4,
        segments=[
            StoryboardSegment(
                segment_id="seg_1",
                beat_id="b1",
                mode="original",
                title="摊牌",
                text="别再逼我。",
                text_raw="别再逼我。",
                visuals=[
                    VisualReference(
                        source_id="src_001",
                        start=4,
                        end=8,
                        highlight_id="h0001",
                    )
                ],
                audio_owner="original_dialogue",
                planned_duration_sec=4,
                notes="保留完整原声",
            )
        ],
    )
    _normalize_storyboard(storyboard, manifest, highlights, app_config)
    assert storyboard.segments[0].highlight_id == "h0001"
