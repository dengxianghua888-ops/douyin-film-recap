from __future__ import annotations

from douyin_film_recap.highlight import _compute_final_score, genre_weights
from douyin_film_recap.models import HighlightCandidate, HighlightScores


def test_action_profile_rewards_action() -> None:
    weights = genre_weights("action")
    action = HighlightCandidate(
        highlight_id="h1",
        source_id="src",
        start=0,
        end=5,
        types=["action"],
        story_function="反击",
        scores=HighlightScores(action_value=1, visual_value=0.9, story_significance=0.7),
        confidence=0.9,
    )
    quiet = HighlightCandidate(
        highlight_id="h2",
        source_id="src",
        start=6,
        end=11,
        types=["dialogue"],
        story_function="说明",
        scores=HighlightScores(action_value=0.05, visual_value=0.1, story_significance=0.7),
        confidence=0.9,
    )
    assert _compute_final_score(action, weights) > _compute_final_score(quiet, weights)
