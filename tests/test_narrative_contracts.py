from __future__ import annotations

import json

import pytest

from douyin_film_recap.config import AppConfig
from douyin_film_recap.models import (
    Character,
    CharacterRegistry,
    HighlightCandidate,
    HighlightDocument,
    KnowledgeState,
    KnowledgeTimeline,
    RecapBeat,
    RecapPlan,
    RhythmProfile,
    SceneAnalysisDocument,
    SceneAnalysisItem,
    SceneIndex,
    SceneUnit,
    SourceInfo,
    SourceManifest,
    StoryBundle,
    StoryEvent,
    StoryGraph,
    Storyboard,
    StoryboardSegment,
    TimeSpan,
    TranscriptDocument,
    VisualReference,
)
from douyin_film_recap.narrative_contracts import (
    get_plan_constraints,
    hook_eligibility,
    resolve_format_constraints,
)
from douyin_film_recap.planning import (
    _storyboard_payload,
    build_plan,
    build_storyboard,
    choose_target_duration,
)
from douyin_film_recap.qc import preflight_qc


def _config(**overrides) -> AppConfig:
    return AppConfig.model_validate(
        {"models": {"llm_model": "test", "vlm_model": "test"}, **overrides}
    )


def _artifacts(config):
    source = SourceInfo(
        source_id="s1", path="/tmp/source.mp4", fingerprint="source-v1",
        filename="source.mp4", duration=120, width=1920, height=1080, fps=25,
    )
    manifest = SourceManifest(sources=[source], config_fingerprint=config.fingerprint())
    transcript = TranscriptDocument(provider="fixture", segments=[], source_fingerprints={"s1": "source-v1"})
    events = [
        StoryEvent(event_id="e_open", story_order=1, reveal_order=1, event="危险出现",
                   source_spans=[TimeSpan(source_id="s1", start=0, end=8)]),
        StoryEvent(event_id="e_context", story_order=2, reveal_order=2, event="藏起证据",
                   source_spans=[TimeSpan(source_id="s1", start=20, end=30)]),
        StoryEvent(event_id="e_twist", story_order=0, reveal_order=3, event="凶手身份揭晓",
                   source_spans=[TimeSpan(source_id="s1", start=90, end=100)]),
    ]
    story = StoryBundle(
        character_registry=CharacterRegistry(characters=[Character(character_id="c1", display_name="甲")]),
        story_graph=StoryGraph(main_plot="寻找凶手", genres=["悬疑"], events=events),
        knowledge_timeline=KnowledgeTimeline(states=[
            KnowledgeState(event_id="e_open", allow_prepose=False),
            KnowledgeState(event_id="e_twist", allow_prepose=False, reveal_sensitivity="high"),
        ]),
    )
    highlights = HighlightDocument(
        genre_profile="suspense", weights={}, source_fingerprints={"s1": "source-v1"},
        candidates=[
            HighlightCandidate(highlight_id="h_twist", source_id="s1", start=92, end=98,
                               types=["reveal"], story_function="终局答案", event_ids=["e_twist"],
                               selected=True, final_score=0.99),
            HighlightCandidate(highlight_id="h_open", source_id="s1", start=1, end=5,
                               types=["suspense"], story_function="危险出现", event_ids=["e_open"],
                               selected=True, final_score=0.6),
        ],
    )
    return manifest, transcript, story, highlights


def _plan(hook="h_open", beats=3):
    return RecapPlan(
        viewer_promise="看清这段关系", pov="甲", main_spine="甲寻找证据",
        hook_strategy="原声冷开", hook_highlight_id=hook, target_duration_sec=60,
        duration_mode="highlight", original_ratio_target=0.4, ending_strategy="payoff",
        reveal_strategy="chronological", rhythm=RhythmProfile(),
        beats=[RecapBeat(beat_id=f"b{i}", function="escalation", change="风险增加",
                        event_ids=["e_context"], audience_question_in="证据在哪",
                        audience_question_out="会被发现吗", narration_job="context",
                        target_duration_sec=20) for i in range(beats)],
    )


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def chat_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0).model_copy(deep=True)


def test_hook_protects_late_reveal_but_allows_actual_opening():
    config = _config()
    _, _, story, highlights = _artifacts(config)
    assert hook_eligibility(highlights.candidates[0], story, config)[0] is False
    assert hook_eligibility(highlights.candidates[1], story, config)[0] is True


def test_hook_requires_all_linked_late_events_to_allow_prepose():
    config = _config()
    _, _, story, highlights = _artifacts(config)
    twist = highlights.candidates[0]
    story.knowledge_timeline.states[1].allow_prepose = True
    assert hook_eligibility(twist, story, config)[0] is True
    twist.event_ids.append("e_context")  # No knowledge permission for this event.
    assert hook_eligibility(twist, story, config)[0] is False


def test_spoiler_override_is_explicit_and_cannot_invent_event_evidence():
    config = _config(project={"editorial_brief": {
        "spoiler_policy": "allow", "spoiler_reason": "本条采用已知结局的过程解读",
    }})
    _, _, story, highlights = _artifacts(config)
    allowed, reason = hook_eligibility(highlights.candidates[0], story, config)
    assert allowed and "已知结局" in reason
    highlights.candidates[0].event_ids = ["invented"]
    assert hook_eligibility(highlights.candidates[0], story, config)[0] is False


def test_missing_highlight_event_ids_can_use_overlapping_source_evidence():
    config = _config()
    _, _, story, highlights = _artifacts(config)
    opening = highlights.candidates[1]
    opening.event_ids = []
    assert hook_eligibility(opening, story, config)[0] is True
    opening.start, opening.end = 45, 50
    assert hook_eligibility(opening, story, config)[0] is False


def test_invalid_hook_replans_once_without_highest_score_fallback():
    config = _config(format={"duration_mode": "highlight"})
    manifest, transcript, story, highlights = _artifacts(config)
    client = FakeClient(_plan("invented"), _plan("h_open"))
    plan = build_plan(manifest, transcript, story, highlights, config, client)
    assert plan.hook_highlight_id == "h_open"
    assert len(client.calls) == 2
    second_payload = json.loads(client.calls[1]["prompt"].split("\n\n", 1)[1])
    assert second_payload["eligible_hook_highlight_ids"] == ["h_open"]
    assert "revision_required" in second_payload


def test_repeated_ineligible_hook_stops_instead_of_silently_selecting():
    config = _config(format={"duration_mode": "highlight"})
    manifest, transcript, story, highlights = _artifacts(config)
    client = FakeClient(_plan("h_twist"), _plan("h_twist"))
    with pytest.raises(ValueError, match="ineligible hook after replan"):
        build_plan(manifest, transcript, story, highlights, config, client)
    assert len(client.calls) == 2


def test_no_eligible_hook_blocks_before_any_model_call():
    config = _config(format={"duration_mode": "highlight"})
    manifest, transcript, story, highlights = _artifacts(config)
    highlights.candidates = highlights.candidates[:1]
    client = FakeClient()
    with pytest.raises(ValueError, match="No eligible opening highlight"):
        build_plan(manifest, transcript, story, highlights, config, client)
    assert not client.calls


def test_plan_records_user_brief_and_spoiler_override_reason():
    config = _config(format={"duration_mode": "highlight"}, project={"editorial_brief": {
        "narrative_question": "这个选择的代价是什么", "spoiler_policy": "allow",
        "spoiler_reason": "用户希望结果前置", "avoid_phrases": ["殊不知"],
    }})
    manifest, transcript, story, highlights = _artifacts(config)
    client = FakeClient(_plan("h_twist"))
    plan = build_plan(manifest, transcript, story, highlights, config, client)
    assert plan.editorial_brief["narrative_question"] == "这个选择的代价是什么"
    assert any("用户希望结果前置" in risk for risk in plan.risks)
    assert plan.resolved_constraints["beat_count_range"] == (2, 5)


def test_explicit_constraints_override_genre_even_when_equal_to_defaults():
    automatic = resolve_format_constraints(_config(), ["动作"])
    explicit = resolve_format_constraints(_config(format={"original_ratio_range": [0.25, 0.45]}), ["动作"])
    assert automatic["original_ratio_range"] == (0.35, 0.55)
    assert automatic["sources"]["original_ratio_range"] == "genre:action"
    assert explicit["original_ratio_range"] == (0.25, 0.45)
    assert explicit["sources"]["original_ratio_range"] == "explicit_config"


def test_plan_constraint_snapshot_is_shared_and_not_recomputed_from_defaults():
    plan = _plan()
    plan.resolved_constraints = resolve_format_constraints(_config(), ["文艺"], duration_mode="highlight")
    actual = get_plan_constraints(plan, _config(format={"original_clip_range_sec": [4, 8]}))
    assert actual["original_clip_range_sec"] == (4, 18)
    assert actual["vo_chars_per_sec"] == (3.8, 4.8)


def test_config_fingerprint_tracks_explicit_intent_as_well_as_values():
    implicit = _config()
    explicit = _config(format={"original_ratio_range": [0.25, 0.45]})
    assert implicit.model_dump() == explicit.model_dump()
    assert implicit.fingerprint() != explicit.fingerprint()


def test_new_highlight_mode_does_not_redefine_legacy_short_duration():
    short_config = _config(format={"duration_mode": "short"})
    manifest, _, story, _ = _artifacts(short_config)
    assert choose_target_duration(manifest, story, short_config) == ("short", 270)
    assert choose_target_duration(manifest, story, _config(format={"duration_mode": "highlight"})) == ("highlight", 60)
    custom = _config(format={"duration_mode": "short", "short_range_sec": [10, 30]})
    assert choose_target_duration(manifest, story, custom) == ("short", 20)


def _scene_artifacts():
    index = SceneIndex(
        detector="fixture", source_fingerprints={"s1": "source-v1"},
        units=[SceneUnit(unit_id="u_context", source_id="s1", start=20, end=26,
                         analysis_window_only=True, original_shot_spans=[(20, 40)],
                         continuity_shot_ids=["shot_2"])],
    )
    analysis = SceneAnalysisDocument(
        provider="fixture", model="fixture", unit_fingerprint="fixture", items=[
            SceneAnalysisItem(unit_id="u_context", visible_facts=["甲将照片放进抽屉"],
                              performance_moments=["回望门口"], confidence=0.9),
        ],
    )
    return index, analysis


def test_storyboard_receives_ordinary_visual_evidence_and_continuity_metadata():
    config = _config()
    manifest, _, story, highlights = _artifacts(config)
    index, analysis = _scene_artifacts()
    payload = _storyboard_payload("demo", manifest, story, highlights, _plan(), config, index, analysis)
    pool = {unit["unit_id"]: unit for unit in payload["visual_pool"]}
    assert pool["u_context"]["visible_facts"] == ["甲将照片放进抽屉"]
    assert pool["u_context"]["continuity_shot_ids"] == ["shot_2"]
    assert pool["u_context"]["analysis_window_only"] is True
    assert "highlight:h_open" in pool
    assert payload["estimated_segment_count"] < 12


def _storyboard(manifest, visual):
    return Storyboard(project_name="demo", sources=manifest.sources, plan_fingerprint="fixture",
                      target_duration_sec=60, segments=[
                          StoryboardSegment(segment_id="seg1", beat_id="b0", mode="voiceover",
                                            title="证据", text="他藏起了照片", visuals=[visual],
                                            audio_owner="narration", planned_duration_sec=4,
                                            notes="照片举证并交代危险"),
                      ])


@pytest.mark.parametrize("unit_id,source_id,start,end,error", [
    (None, "s1", 20, 24, "known visual-pool"),
    ("invented", "s1", 20, 24, "known visual-pool"),
    ("u_context", "wrong-source", 20, 24, "source does not match"),
    ("u_context", "s1", 20, 29, "leaves evidence unit"),
])
def test_new_storyboard_rejects_unanchored_visuals(unit_id, source_id, start, end, error):
    config = _config()
    manifest, _, story, highlights = _artifacts(config)
    index, analysis = _scene_artifacts()
    visual = VisualReference(unit_id=unit_id, source_id=source_id, start=start, end=end)
    client = FakeClient(_storyboard(manifest, visual))
    with pytest.raises(ValueError, match=error):
        build_storyboard(project_name="demo", manifest=manifest, story=story, highlights=highlights,
                         plan=_plan(), config=config, client=client, scene_index=index, scene_analysis=analysis)


def test_new_storyboard_retains_valid_unit_and_visual_role():
    config = _config()
    manifest, _, story, highlights = _artifacts(config)
    index, analysis = _scene_artifacts()
    visual = VisualReference(unit_id="u_context", source_id="s1", start=20, end=24,
                             visual_role="direct_evidence", purpose="照片进入抽屉")
    result = build_storyboard(
        project_name="demo", manifest=manifest, story=story, highlights=highlights,
        plan=_plan(), config=config, client=FakeClient(_storyboard(manifest, visual)),
        scene_index=index, scene_analysis=analysis,
    )
    actual = result.segments[0].visuals[0]
    assert actual.unit_id == "u_context" and actual.visual_role == "direct_evidence"
    assert actual.start == 20 and actual.end == 24


def test_ordinary_visual_cannot_claim_an_unrelated_highlight():
    config = _config()
    manifest, _, story, highlights = _artifacts(config)
    index, analysis = _scene_artifacts()
    visual = VisualReference(unit_id="u_context", source_id="s1", start=20, end=24,
                             highlight_id="h_open")
    with pytest.raises(ValueError, match="highlight does not match"):
        build_storyboard(
            project_name="demo", manifest=manifest, story=story, highlights=highlights,
            plan=_plan(), config=config, client=FakeClient(_storyboard(manifest, visual)),
            scene_index=index, scene_analysis=analysis,
        )


def _hook_report(tmp_path, visuals, audio_duration, *, declared=True, lead_duration=0):
    config = _config()
    manifest, transcript, story, highlights = _artifacts(config)
    storyboard = _storyboard(manifest, visuals[0])
    segment = storyboard.segments[0]
    segment.visuals = visuals
    segment.highlight_id = "h_open" if declared else None
    segment.audio_duration_sec = audio_duration
    segment.audio_file = str(tmp_path / "fixture-audio.mp3")
    # Preflight only needs the available asset identity here; no model or audio
    # synthesis is involved in testing deterministic source-range accounting.
    (tmp_path / "fixture-audio.mp3").write_bytes(b"fixture")
    if lead_duration:
        lead = segment.model_copy(deep=True)
        lead.segment_id = "lead"
        lead.highlight_id = None
        lead.audio_duration_sec = lead_duration
        lead.visuals = [VisualReference(source_id="s1", start=30, end=30 + lead_duration)]
        storyboard.segments.insert(0, lead)
    return preflight_qc(
        manifest=manifest, transcript=transcript, story=story, highlights=highlights,
        plan=_plan(), storyboard=storyboard, config=config, client=None,
    )


@pytest.mark.parametrize("source_id,start,end", [("s1", 20, 24), ("wrong-source", 1, 5)])
def test_declared_hook_without_matching_consumed_source_is_blocked(tmp_path, source_id, start, end):
    report = _hook_report(tmp_path, [VisualReference(source_id=source_id, start=start, end=end)], 4)
    false_reference = next(item for item in report.findings if item.rule_id == "HOOK_REFERENCE_WITHOUT_SOURCE_EVIDENCE")
    assert false_reference.deterministic and false_reference.blocking
    assert any(item.rule_id == "HOOK_NOT_USED" for item in report.findings)
    assert report.metrics["hook_start_sec"] is None


def test_hook_in_unconsumed_vo_candidate_does_not_count(tmp_path):
    report = _hook_report(tmp_path, [
        VisualReference(source_id="s1", start=20, end=26),
        VisualReference(source_id="s1", start=1, end=5, highlight_id="h_open"),
    ], 3, declared=False)
    assert any(item.rule_id == "HOOK_REFERENCE_WITHOUT_SOURCE_EVIDENCE" for item in report.findings)
    assert any(item.rule_id == "HOOK_NOT_USED" for item in report.findings)
    assert report.metrics["hook_start_sec"] is None


@pytest.mark.parametrize("duration", [0.5, 1.0])
def test_unconsumed_tail_or_touching_hook_boundary_does_not_count(tmp_path, duration):
    # The highlight starts at source second 1; a [0, 1] consumed interval has no
    # positive-duration overlap even though the available visual extends to 6.
    report = _hook_report(tmp_path, [VisualReference(source_id="s1", start=0, end=6)], duration)
    assert report.metrics["hook_start_sec"] is None
    assert any(item.rule_id == "HOOK_NOT_USED" for item in report.findings)


def test_hook_time_includes_preceding_segments_visuals_and_intra_visual_offset(tmp_path):
    report = _hook_report(tmp_path, [
        VisualReference(source_id="s1", start=20, end=24),
        VisualReference(source_id="s1", start=0, end=5, highlight_id="h_open"),
    ], 8, lead_duration=3)
    # 3 seconds in the previous segment + 4 seconds of ordinary picture + 1
    # second into the matching visual, rather than the containing segment's 3s.
    assert report.metrics["hook_start_sec"] == pytest.approx(8)
    late = next(item for item in report.findings if item.rule_id == "HOOK_TOO_LATE")
    assert late.evidence["actual_sec"] == pytest.approx(8)
    assert late.location.output_time == pytest.approx(8)
    assert not any(item.rule_id == "HOOK_NOT_USED" for item in report.findings)


def test_actual_hook_picture_counts_without_an_id_tag(tmp_path):
    report = _hook_report(tmp_path, [VisualReference(source_id="s1", start=0, end=6)], 3, declared=False)
    assert report.metrics["hook_start_sec"] == pytest.approx(1)
    assert not any(item.rule_id in {"HOOK_NOT_USED", "HOOK_REFERENCE_WITHOUT_SOURCE_EVIDENCE"}
                   for item in report.findings)
