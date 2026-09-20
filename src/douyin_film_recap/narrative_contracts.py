"""Shared, deterministic contracts for planning and narrative QC.

These checks validate declared evidence and editorial decisions. They do not
claim to establish whether a model's description of a shot is true.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .config import AppConfig
from .models import HighlightCandidate, RecapPlan, StoryBundle, VisualReference


_FORMAT_FIELDS = (
    "first_highlight_deadline_sec",
    "original_ratio_range",
    "original_clip_range_sec",
    "max_original_over_15s",
    "micro_cycle_sec",
    "reset_interval_sec",
    "vo_chars_per_sec",
    "allow_cta",
)

_GENRE_PRESETS: dict[str, dict[str, Any]] = {
    "action": {
        "original_ratio_range": (0.35, 0.55),
        "original_clip_range_sec": (4.0, 15.0),
        "max_original_over_15s": 4,
    },
    "drama": {"original_ratio_range": (0.35, 0.55)},
    "romance": {
        "original_clip_range_sec": (4.0, 18.0),
        "max_original_over_15s": 4,
        "micro_cycle_sec": (16.0, 30.0),
        "reset_interval_sec": (50.0, 90.0),
        "vo_chars_per_sec": (3.8, 4.8),
    },
    "suspense": {"vo_chars_per_sec": (4.0, 5.0)},
    "comedy": {
        "original_clip_range_sec": (4.0, 15.0),
        "max_original_over_15s": 3,
    },
}


def _genre_profile(genres: list[str], configured: str) -> str:
    if configured != "auto":
        return configured
    text = " ".join(genres).lower()
    for profile, keywords in (
        ("comedy", ("喜剧", "comedy")),
        ("action", ("动作", "战争", "犯罪", "武侠", "action", "war")),
        ("suspense", ("悬疑", "惊悚", "谍战", "推理", "suspense", "thriller")),
        ("romance", ("爱情", "恋爱", "治愈", "文艺", "romance")),
        ("drama", ("家庭", "婚恋", "复仇", "剧情", "drama")),
    ):
        if any(keyword in text for keyword in keywords):
            return profile
    return "general"


def duration_bounds(config: AppConfig, mode: str) -> tuple[int, int]:
    """Keep the legacy names stable; the new highlight mode is 30–90 seconds."""
    return {
        "highlight": config.format.highlight_range_sec,
        "short": config.format.short_range_sec,
        "standard": config.format.standard_range_sec,
        "deep": config.format.deep_range_sec,
        "series": config.format.deep_range_sec,
    }.get(mode, config.format.standard_range_sec)


def resolve_format_constraints(
    config: AppConfig,
    genres: list[str] | None = None,
    *,
    duration_mode: str | None = None,
) -> dict[str, Any]:
    """Resolve explicit config > genre preset > default and record provenance.

    Explicit values equal to defaults are still user choices. Using Pydantic's
    model_fields_set preserves that distinction and keeps old full configs stable.
    """
    profile = _genre_profile(genres or [], config.highlight.genre_profile)
    preset = _GENRE_PRESETS.get(profile, {})
    explicit = config.format.model_fields_set
    result: dict[str, Any] = {}
    origins: dict[str, str] = {}
    for key in _FORMAT_FIELDS:
        if key in explicit:
            result[key] = getattr(config.format, key)
            origins[key] = "explicit_config"
        elif key in preset:
            result[key] = preset[key]
            origins[key] = f"genre:{profile}"
        else:
            result[key] = getattr(config.format, key)
            origins[key] = "default"
    mode = duration_mode or config.format.duration_mode
    result.update(
        contract_version=1,
        genre_profile=profile,
        duration_mode=mode,
        duration_range_sec=duration_bounds(config, mode),
        beat_count_range=(2, 5) if mode == "highlight" else (6, 14),
        sources=origins,
    )
    return deepcopy(result)


def get_plan_constraints(plan: RecapPlan, config: AppConfig) -> dict[str, Any]:
    """QC and storyboard consume the same frozen planning budget.

    Old plans without the snapshot use their existing explicit configuration.
    """
    constraints = resolve_format_constraints(config, duration_mode=plan.duration_mode)
    constraints.update(deepcopy(plan.resolved_constraints))
    return constraints


def hook_eligibility(
    highlight: HighlightCandidate, story: StoryBundle, config: AppConfig
) -> tuple[bool, str]:
    """Check whether a declared highlight can open the recap without an override.

    The first revealed event is not considered preposed. For later events every
    linked knowledge state must explicitly permit preposition. Missing mappings
    are insufficient evidence, rather than implicit permission.
    """
    events = {event.event_id: event for event in story.story_graph.events}
    linked_ids = set(highlight.event_ids)
    if not linked_ids:
        linked_ids = {
            event.event_id
            for event in events.values()
            if any(
                span.source_id == highlight.source_id
                and min(span.end, highlight.end) > max(span.start, highlight.start)
                for span in event.source_spans
            )
        }
    if not linked_ids or not linked_ids.issubset(events):
        return False, "高光缺少有效事件映射，无法验证揭示顺序"
    brief = config.project.editorial_brief
    if brief.spoiler_policy == "allow":
        explanation = brief.spoiler_reason.strip() or "用户在 editorial_brief 中明确允许剧透/结果前置"
        return True, f"explicit_spoiler_override: {explanation}"
    first_reveal = min(event.reveal_order for event in events.values())
    preposed_ids = {
        event_id for event_id in linked_ids if events[event_id].reveal_order > first_reveal
    }
    if not preposed_ids:
        return True, "原片最早揭示事件，无跨事件前置"
    states = {state.event_id: state for state in story.knowledge_timeline.states}
    denied = sorted(
        event_id
        for event_id in preposed_ids
        if event_id not in states or not states[event_id].allow_prepose
    )
    if denied:
        return False, f"事件禁止前置或缺少许可: {', '.join(denied)}"
    return True, "所有前置事件均有 allow_prepose=true"


def validate_visual_reference(
    visual: VisualReference, visual_pool: dict[str, dict[str, Any]]
) -> None:
    """Reject unsupported VO ranges instead of silently clamping invented cuts."""
    unit = visual_pool.get(visual.unit_id or "")
    if unit is None:
        raise ValueError(f"VO visual must reference a known visual-pool unit_id: {visual.unit_id}")
    if visual.source_id != unit["source_id"]:
        raise ValueError(f"VO visual source does not match unit {visual.unit_id}")
    if visual.highlight_id and visual.highlight_id != unit.get("highlight_id"):
        raise ValueError(f"VO visual highlight does not match evidence unit {visual.unit_id}")
    if visual.start < unit["start"] - 0.001 or visual.end > unit["end"] + 0.001:
        raise ValueError(f"VO visual range leaves evidence unit {visual.unit_id}")
