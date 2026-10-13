from __future__ import annotations

import pytest

from douyin_film_recap.models import TranscriptSegment
from douyin_film_recap.planning import _normalize_storyboard
from douyin_film_recap.qc import preflight_qc
from douyin_film_recap.subtitles import build_cues
from test_qc import _base_artifacts


@pytest.mark.parametrize("audio_owner", ["action_sound", "ambience", "music", "silence"])
def test_must_hear_original_preserves_non_dialogue_role(app_config, audio_owner):
    manifest, transcript, story, highlights, plan, storyboard = _base_artifacts(
        app_config, unsafe=False
    )
    transcript.segments = []
    highlight = highlights.candidates[0]
    highlight.must_hear_original = True
    highlight.types = ["action" if audio_owner == "action_sound" else "performance"]
    highlight.quote = ""
    segment = storyboard.segments[0]
    segment.audio_owner = audio_owner
    segment.text = segment.text_raw = ""
    segment.original_cues_verified = True

    _normalize_storyboard(storyboard, manifest, highlights, app_config)
    assert segment.audio_owner == audio_owner
    assert segment.mute_original is False
    report = preflight_qc(
        manifest=manifest, transcript=transcript, story=story, highlights=highlights,
        plan=plan, storyboard=storyboard, config=app_config,
    )
    assert report.status != "BLOCKED"
    assert not any(finding.rule_id == "UNSAFE_DIALOGUE_BOUNDARY" for finding in report.findings)
    assert build_cues(storyboard, app_config) == []


@pytest.mark.parametrize("has_dialogue", [False, True])
def test_must_hear_dialogue_still_requires_safe_boundaries(app_config, has_dialogue):
    manifest, transcript, story, highlights, plan, storyboard = _base_artifacts(
        app_config, unsafe=False
    )
    highlights.candidates[0].must_hear_original = True
    transcript.segments = (
        [TranscriptSegment(source_id="src_001", start=0.1, end=3.9, text="完整对白")]
        if has_dialogue else []
    )
    _normalize_storyboard(storyboard, manifest, highlights, app_config)
    assert storyboard.segments[0].audio_owner == "original_dialogue"
    assert storyboard.segments[0].mute_original is False
    report = preflight_qc(
        manifest=manifest, transcript=transcript, story=story, highlights=highlights,
        plan=plan, storyboard=storyboard, config=app_config,
    )
    assert report.status == "BLOCKED"
    assert any(finding.rule_id == "UNSAFE_DIALOGUE_BOUNDARY" for finding in report.findings)


@pytest.mark.parametrize("audio_owner", ["action_sound", "ambience", "music", "silence"])
@pytest.mark.parametrize("cue_range, blocked", [((0.5, 2), True), ((2, 3.5), True), ((1.5, 2.5), False)])
def test_actual_dialogue_cuts_cannot_hide_behind_non_dialogue_role(
    app_config, audio_owner, cue_range, blocked
):
    manifest, transcript, story, highlights, plan, storyboard = _base_artifacts(
        app_config, unsafe=False
    )
    highlight = highlights.candidates[0]
    highlight.must_hear_original = True
    segment = storyboard.segments[0]
    segment.audio_owner = audio_owner
    transcript.segments = [
        TranscriptSegment(source_id="src_001", start=cue_range[0], end=cue_range[1], text="源片对白")
    ]
    _normalize_storyboard(storyboard, manifest, highlights, app_config)
    report = preflight_qc(
        manifest=manifest, transcript=transcript, story=story, highlights=highlights,
        plan=plan, storyboard=storyboard, config=app_config,
    )
    boundary_findings = [finding for finding in report.findings
                         if finding.rule_id == "UNSAFE_DIALOGUE_BOUNDARY"]
    assert bool(boundary_findings) is blocked
    assert (report.status == "BLOCKED") is blocked
    if blocked:
        assert boundary_findings[0].evidence["cut_cues"]
