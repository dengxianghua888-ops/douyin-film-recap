from __future__ import annotations

from douyin_film_recap.models import (
    Character,
    CharacterRegistry,
    HighlightCandidate,
    HighlightDocument,
    KnowledgeTimeline,
    RecapBeat,
    RecapPlan,
    RhythmProfile,
    SourceInfo,
    SourceManifest,
    StoryBundle,
    StoryEvent,
    StoryGraph,
    Storyboard,
    StoryboardSegment,
    TimeSpan,
    TranscriptDocument,
    TranscriptSegment,
    VisualReference,
)
from douyin_film_recap.qc import preflight_qc


def _base_artifacts(app_config, unsafe: bool):
    source = SourceInfo(
        source_id="src_001",
        path="/tmp/source.mp4",
        fingerprint="abc",
        filename="source.mp4",
        duration=10,
        width=1920,
        height=1080,
        fps=25,
    )
    manifest = SourceManifest(
        sources=[source], config_fingerprint=app_config.fingerprint()
    )
    transcript = TranscriptDocument(
        provider="fixture",
        segments=[
            TranscriptSegment(
                source_id="src_001", start=1, end=3, text="你到底想干什么"
            )
        ],
        source_fingerprints={"src_001": "abc"},
    )
    story = StoryBundle(
        character_registry=CharacterRegistry(
            characters=[Character(character_id="c001", display_name="甲")]
        ),
        story_graph=StoryGraph(
            main_plot="甲被逼问",
            events=[
                StoryEvent(
                    event_id="e001",
                    story_order=1,
                    reveal_order=1,
                    participants=["c001"],
                    event="被逼问",
                    source_spans=[TimeSpan(source_id="src_001", start=1, end=3)],
                )
            ],
        ),
        knowledge_timeline=KnowledgeTimeline(states=[]),
    )
    highlights = HighlightDocument(
        genre_profile="drama",
        candidates=[
            HighlightCandidate(
                highlight_id="h0001",
                source_id="src_001",
                start=1,
                end=3,
                types=["dialogue"],
                quote="你到底想干什么",
                story_function="冲突",
                selected=True,
                confidence=0.9,
            )
        ],
        weights={},
        source_fingerprints={"src_001": "abc"},
    )
    beat = RecapBeat(
        beat_id="b1",
        function="hook",
        change="平静到冲突",
        audience_question_in="发生什么",
        audience_question_out="甲会如何回应",
        preferred_highlights=["h0001"],
        narration_job="none",
        target_duration_sec=2,
        target_original_sec=2,
    )
    plan = RecapPlan(
        viewer_promise="看清冲突",
        pov="甲",
        main_spine="被逼问",
        hook_strategy="原声",
        hook_highlight_id="h0001",
        target_duration_sec=2,
        duration_mode="short",
        original_ratio_target=0.8,
        ending_strategy="payoff",
        reveal_strategy="chronological",
        beats=[beat] * 6,
        rhythm=RhythmProfile(),
    )
    start, end = (0.4, 3.6) if unsafe else (1, 3)
    storyboard = Storyboard(
        project_name="demo",
        sources=[source],
        plan_fingerprint="p",
        target_duration_sec=2,
        segments=[
            StoryboardSegment(
                segment_id="s1",
                beat_id="b1",
                mode="original",
                title="冲突",
                text="你到底想干什么",
                text_raw="你到底想干什么",
                visuals=[VisualReference(source_id="src_001", start=start, end=end)],
                audio_owner="original_dialogue",
                planned_duration_sec=end - start,
                highlight_id="h0001",
                notes="完整保留冲突",
            )
        ],
    )
    return manifest, transcript, story, highlights, plan, storyboard


def test_preflight_blocks_unsafe_dialogue_boundary(app_config) -> None:
    artifacts = _base_artifacts(app_config, unsafe=True)
    report = preflight_qc(
        manifest=artifacts[0],
        transcript=artifacts[1],
        story=artifacts[2],
        highlights=artifacts[3],
        plan=artifacts[4],
        storyboard=artifacts[5],
        config=app_config,
        client=None,
    )
    assert report.status == "BLOCKED"
    assert any(item.rule_id == "UNSAFE_DIALOGUE_BOUNDARY" for item in report.findings)


def test_preflight_accepts_complete_dialogue(app_config) -> None:
    artifacts = _base_artifacts(app_config, unsafe=False)
    report = preflight_qc(
        manifest=artifacts[0],
        transcript=artifacts[1],
        story=artifacts[2],
        highlights=artifacts[3],
        plan=artifacts[4],
        storyboard=artifacts[5],
        config=app_config,
        client=None,
    )
    assert report.status != "BLOCKED"
