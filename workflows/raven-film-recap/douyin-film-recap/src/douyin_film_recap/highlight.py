from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .asr import nearest_segment_boundaries, transcript_text_in_range
from .config import AppConfig
from .media import extract_frames_batch, make_contact_sheet
from .models import (
    BoundaryQuality,
    HighlightCandidate,
    HighlightDocument,
    HighlightRerankBatch,
    HighlightRisks,
    HighlightScores,
    SceneAnalysisDocument,
    SceneAnalysisItem,
    SceneIndex,
    SourceManifest,
    StoryBundle,
    TranscriptDocument,
)
from .prompts import HIGHLIGHT_RERANK_SYSTEM, highlight_rerank_prompt
from .providers import OpenAICompatibleClient
from .utils import chunks, clamp, overlap_seconds

HIGHLIGHT_TYPES = {
    "confrontation",
    "counterattack",
    "action",
    "dialogue",
    "performance",
    "emotion",
    "reveal",
    "suspense",
    "comedy",
    "spectacle",
    "character_definition",
    "relationship_shift",
    "moral_choice",
}

BASE_WEIGHTS = {
    "story_significance": 0.14,
    "immediate_intensity": 0.10,
    "performance_value": 0.10,
    "dialogue_value": 0.07,
    "visual_value": 0.07,
    "action_value": 0.07,
    "emotion_value": 0.08,
    "reveal_value": 0.07,
    "suspense_value": 0.06,
    "comedy_value": 0.04,
    "relationship_shift": 0.06,
    "state_change_strength": 0.07,
    "context_independence": 0.04,
    "genre_fit": 0.02,
    "novelty": 0.01,
}

GENRE_ADJUSTMENTS = {
    "action": {
        "action_value": 1.7,
        "visual_value": 1.35,
        "immediate_intensity": 1.25,
        "dialogue_value": 0.7,
    },
    "suspense": {
        "suspense_value": 1.7,
        "reveal_value": 1.45,
        "state_change_strength": 1.25,
        "action_value": 0.8,
    },
    "drama": {
        "performance_value": 1.55,
        "dialogue_value": 1.2,
        "emotion_value": 1.35,
        "relationship_shift": 1.35,
    },
    "romance": {
        "performance_value": 1.45,
        "emotion_value": 1.55,
        "relationship_shift": 1.45,
        "immediate_intensity": 0.8,
    },
    "comedy": {
        "comedy_value": 2.1,
        "dialogue_value": 1.2,
        "performance_value": 1.2,
        "story_significance": 0.8,
    },
}

TYPE_ALIASES = {
    "冲突": "confrontation",
    "训斥": "confrontation",
    "羞辱": "confrontation",
    "摊牌": "confrontation",
    "反击": "counterattack",
    "打脸": "counterattack",
    "回怼": "counterattack",
    "动作": "action",
    "打斗": "action",
    "追逐": "action",
    "台词": "dialogue",
    "表演": "performance",
    "微表情": "performance",
    "情绪": "emotion",
    "反转": "reveal",
    "揭示": "reveal",
    "悬念": "suspense",
    "喜剧": "comedy",
    "笑点": "comedy",
    "视觉奇观": "spectacle",
    "人物塑造": "character_definition",
    "关系变化": "relationship_shift",
    "道德选择": "moral_choice",
    "conflict": "confrontation",
    "humiliation": "confrontation",
    "insult": "confrontation",
    "fight": "action",
    "chase": "action",
    "line": "dialogue",
    "acting": "performance",
    "microexpression": "performance",
    "emotional": "emotion",
    "twist": "reveal",
    "reversal": "reveal",
    "thrill": "suspense",
    "visual": "spectacle",
    "relationship": "relationship_shift",
}


def infer_genre_profile(story: StoryBundle, configured: str) -> str:
    if configured != "auto":
        return configured
    genre_text = " ".join(story.story_graph.genres).lower()
    mappings = [
        ("comedy", ["喜剧", "comedy"]),
        ("action", ["动作", "战争", "犯罪", "武侠", "action", "war"]),
        ("suspense", ["悬疑", "惊悚", "谍战", "推理", "suspense", "thriller"]),
        ("romance", ["爱情", "恋爱", "治愈", "romance"]),
        ("drama", ["家庭", "婚恋", "复仇", "剧情", "drama"]),
    ]
    for profile, keywords in mappings:
        if any(keyword in genre_text for keyword in keywords):
            return profile
    return "drama"


def genre_weights(profile: str) -> dict[str, float]:
    weights = dict(BASE_WEIGHTS)
    for key, multiplier in GENRE_ADJUSTMENTS.get(profile, {}).items():
        weights[key] *= multiplier
    total = sum(weights.values()) or 1.0
    return {key: value / total for key, value in weights.items()}


def _normalize_types(values: list[str]) -> list[str]:
    output: list[str] = []
    for raw in values:
        key = raw.strip().lower().replace(" ", "_")
        key = TYPE_ALIASES.get(key, key)
        if key in HIGHLIGHT_TYPES and key not in output:
            output.append(key)
    return output or ["character_definition"]


def _scene_score(item: SceneAnalysisItem, key: str, fallback: float = 0.0) -> float:
    aliases = {
        "immediate_intensity": ["drama", "intensity", "tension"],
        "performance_value": ["performance", "acting"],
        "dialogue_value": ["dialogue", "line"],
        "visual_value": ["visual", "spectacle"],
        "action_value": ["action", "motion"],
        "emotion_value": ["emotion"],
        "reveal_value": ["reveal", "twist"],
        "suspense_value": ["suspense"],
        "comedy_value": ["comedy", "humor"],
        "relationship_shift": ["relationship", "relationship_shift"],
        "state_change_strength": ["state_change", "change"],
    }
    for alias in aliases.get(key, [key]):
        if alias in item.scores:
            return clamp(float(item.scores[alias]), 0.0, 1.0)
    return fallback


def _events_for_span(
    story: StoryBundle, source_id: str, start: float, end: float
) -> list[Any]:
    events = []
    for event in story.story_graph.events:
        if any(
            span.source_id == source_id
            and overlap_seconds(start, end, span.start, span.end) > 0
            for span in event.source_spans
        ):
            events.append(event)
    return events


def _candidate_from_hint(
    *,
    item: SceneAnalysisItem,
    unit: Any,
    hint: Any,
    candidate_index: int,
    transcript: TranscriptDocument,
    story: StoryBundle,
) -> HighlightCandidate:
    start = hint.start_hint if hint.start_hint is not None else unit.start
    end = hint.end_hint if hint.end_hint is not None else unit.end
    # Tolerate providers that accidentally return offsets relative to the unit.
    unit_duration = unit.end - unit.start
    if hint.start_hint is not None and float(start) < unit.start and 0 <= float(start) <= unit_duration:
        start = unit.start + float(start)
    if hint.end_hint is not None and float(end) <= unit_duration and float(end) < unit.start:
        end = unit.start + float(end)
    start = clamp(float(start), unit.start, unit.end - 0.05)
    end = clamp(float(end), start + 0.05, unit.end)
    if end - start < 1.5:
        center = (start + end) / 2
        start = max(unit.start, center - 1.2)
        end = min(unit.end, center + 1.2)
    types = _normalize_types(hint.types)
    must_hear = bool(
        hint.must_hear_original
        or any(
            kind in types
            for kind in {"dialogue", "performance", "action", "emotion", "reveal", "comedy"}
        )
    )
    requires_sentence_boundary = "dialogue" in types
    snapped_start, snapped_end, entry_safe, exit_safe = nearest_segment_boundaries(
        transcript, unit.source_id, start, end
    )
    if requires_sentence_boundary and entry_safe:
        start = max(unit.start, snapped_start)
    if requires_sentence_boundary and exit_safe:
        end = min(unit.end, snapped_end)
    if end <= start:
        start, end = unit.start, unit.end
    events = _events_for_span(story, unit.source_id, start, end)
    quote = transcript_text_in_range(transcript, unit.source_id, start, end)
    story_significance = max((event.confidence for event in events), default=0.35)
    scores = HighlightScores(
        story_significance=story_significance,
        immediate_intensity=_scene_score(item, "immediate_intensity", unit.signals.motion),
        performance_value=_scene_score(item, "performance_value", 0.2),
        dialogue_value=_scene_score(item, "dialogue_value", unit.signals.speech_density),
        visual_value=_scene_score(item, "visual_value", unit.signals.motion),
        action_value=_scene_score(item, "action_value", unit.signals.motion),
        emotion_value=_scene_score(item, "emotion_value", 0.25),
        reveal_value=_scene_score(item, "reveal_value", 0.1),
        suspense_value=_scene_score(item, "suspense_value", 0.1),
        comedy_value=_scene_score(item, "comedy_value", 0.0),
        relationship_shift=_scene_score(item, "relationship_shift", 0.2),
        state_change_strength=_scene_score(item, "state_change_strength", 0.3),
        context_independence=0.5,
        genre_fit=0.5,
        novelty=0.5,
    )
    return HighlightCandidate(
        highlight_id=f"h{candidate_index:04d}",
        source_id=unit.source_id,
        start=start,
        end=end,
        types=types,
        characters=[character.temporary_id for character in item.characters],
        event_ids=[event.event_id for event in events],
        quote=quote,
        story_function=hint.reason,
        state_change="; ".join(
            change for event in events for change in event.state_change.values()
        )[:1000],
        must_hear_original=must_hear,
        boundary=BoundaryQuality(
            entry_safe=entry_safe or not requires_sentence_boundary,
            exit_safe=exit_safe or not requires_sentence_boundary,
            sentence_complete=(entry_safe and exit_safe)
            if requires_sentence_boundary
            else True,
            action_complete="action" not in types,
            entry_anchor=snapped_start if entry_safe else None,
            exit_anchor=snapped_end if exit_safe else None,
        ),
        scores=scores,
        risks=HighlightRisks(
            spoiler=max(
                (
                    0.85
                    for state in story.knowledge_timeline.states
                    if state.event_id in {event.event_id for event in events}
                    and state.reveal_sensitivity == "high"
                ),
                default=0.0,
            ),
            context_dependency=0.5,
            unsafe_boundary=0.0
            if (entry_safe and exit_safe) or not requires_sentence_boundary
            else 0.65,
        ),
        evidence=[
            {
                "unit_id": unit.unit_id,
                "visible_facts": item.visible_facts,
                "dialogue_facts": item.dialogue_facts,
                "performance_moments": item.performance_moments,
            }
        ],
        confidence=min(item.confidence, max(0.3, story_significance)),
    )


def _fallback_hints(item: SceneAnalysisItem, unit: Any) -> list[Any]:
    class Hint:
        start_hint = None
        end_hint = None
        must_hear_original = False

        def __init__(self, types: list[str], reason: str, must: bool = False):
            self.types = types
            self.reason = reason
            self.must_hear_original = must

    hints: list[Any] = []
    if unit.signals.motion >= 0.45 or _scene_score(item, "action_value") >= 0.6:
        hints.append(Hint(["action"], "高运动强度或动作场面候选"))
    if _scene_score(item, "performance_value") >= 0.58:
        hints.append(Hint(["performance"], "表演强度候选", True))
    if _scene_score(item, "dialogue_value") >= 0.62:
        hints.append(Hint(["dialogue"], "关键台词候选", True))
    if _scene_score(item, "reveal_value") >= 0.6:
        hints.append(Hint(["reveal"], "信息揭示或反转候选", True))
    if _scene_score(item, "emotion_value") >= 0.65:
        hints.append(Hint(["emotion"], "情绪落点候选", True))
    return hints


def _compute_final_score(candidate: HighlightCandidate, weights: dict[str, float]) -> float:
    positive = sum(
        weights.get(key, 0.0) * float(getattr(candidate.scores, key)) for key in weights
    )
    penalty = (
        candidate.risks.spoiler * 0.06
        + candidate.risks.context_dependency * 0.08
        + candidate.risks.redundancy * 0.10
        + candidate.risks.unsafe_boundary * 0.15
    )
    return clamp((positive - penalty) * (0.65 + 0.35 * candidate.confidence), 0.0, 1.0)


def _candidate_sheet(
    candidate: HighlightCandidate,
    manifest: SourceManifest,
    work_dir: Path,
    frame_count: int = 6,
) -> Path:
    source = next(value for value in manifest.sources if value.source_id == candidate.source_id)
    duration = candidate.end - candidate.start
    frame_dir = work_dir / "frames" / "highlights" / candidate.highlight_id
    frame_paths: list[str] = []
    labels: list[str] = []
    requests: list[tuple[float, Path]] = []
    for index in range(frame_count):
        timestamp = candidate.start + duration * (index + 0.5) / frame_count
        path = frame_dir / f"f{index + 1:02d}_{timestamp:.3f}.jpg"
        requests.append((timestamp, path))
        frame_paths.append(str(path))
        labels.append(f"{candidate.highlight_id} · {timestamp:.2f}s")
    extract_frames_batch(source.path, requests)
    sheet = work_dir / "contact_sheets" / "highlights" / f"{candidate.highlight_id}.jpg"
    return make_contact_sheet(frame_paths, labels, sheet)


def _rerank_candidates(
    candidates: list[HighlightCandidate],
    manifest: SourceManifest,
    story: StoryBundle,
    config: AppConfig,
    client: OpenAICompatibleClient,
    work_dir: Path,
) -> None:
    event_map = {event.event_id: event for event in story.story_graph.events}
    for group_index, group in enumerate(chunks(candidates, 6)):
        group_list = list(group)
        images = [_candidate_sheet(candidate, manifest, work_dir) for candidate in group_list]
        payload: list[dict[str, Any]] = []
        for candidate in group_list:
            payload.append(
                {
                    "highlight_id": candidate.highlight_id,
                    "source_id": candidate.source_id,
                    "time_range": [candidate.start, candidate.end],
                    "types": candidate.types,
                    "quote": candidate.quote,
                    "initial_scores": candidate.scores.model_dump(mode="json"),
                    "initial_risks": candidate.risks.model_dump(mode="json"),
                    "story_function": candidate.story_function,
                    "events": [
                        event_map[event_id].model_dump(mode="json")
                        for event_id in candidate.event_ids
                        if event_id in event_map
                    ],
                }
            )
        story_context = {
            "genres": story.story_graph.genres,
            "main_plot": story.story_graph.main_plot,
            "themes": story.story_graph.themes,
        }
        result = client.chat_json(
            intent_key=f"highlights:rerank:{group_index:04d}",
            system=HIGHLIGHT_RERANK_SYSTEM,
            prompt=highlight_rerank_prompt(payload, story_context),
            model_type=HighlightRerankBatch,
            vision=True,
            images=images,
            temperature=config.models.temperature.get("analysis", 0.1),
            max_tokens=7000,
        )
        updates = {item.highlight_id: item for item in result.items}
        for candidate in group_list:
            update = updates.get(candidate.highlight_id)
            if update is None:
                candidate.evidence.append({"rerank": "missing_model_item"})
                candidate.confidence *= 0.8
                continue
            candidate.scores = update.scores
            candidate.risks = update.risks
            candidate.types = _normalize_types(update.types or candidate.types)
            candidate.must_hear_original = update.must_hear_original
            candidate.story_function = update.story_function or candidate.story_function
            candidate.state_change = update.state_change or candidate.state_change
            candidate.selection_reason = update.selection_reason
            candidate.confidence = update.confidence
            candidate.evidence.append({"vlm_rerank": update.model_dump(mode="json")})


def _deduplicate(candidates: list[HighlightCandidate]) -> list[HighlightCandidate]:
    kept: list[HighlightCandidate] = []
    for candidate in sorted(candidates, key=lambda value: value.final_score, reverse=True):
        duplicate = None
        for existing in kept:
            if existing.source_id != candidate.source_id:
                continue
            overlap = overlap_seconds(
                existing.start, existing.end, candidate.start, candidate.end
            )
            denominator = max(0.001, min(existing.end - existing.start, candidate.end - candidate.start))
            if overlap / denominator >= 0.65:
                duplicate = existing
                break
        if duplicate:
            duplicate.types = list(dict.fromkeys(duplicate.types + candidate.types))
            duplicate.evidence.extend(candidate.evidence)
            candidate.rejection_reason = f"与 {duplicate.highlight_id} 高度重叠"
        else:
            kept.append(candidate)
    return kept


def _select_diverse(
    candidates: list[HighlightCandidate], config: AppConfig
) -> list[HighlightCandidate]:
    selected: list[HighlightCandidate] = []
    type_counts: Counter[str] = Counter()
    character_counts: Counter[str] = Counter()
    limit = config.highlight.final_pool_size
    for candidate in sorted(candidates, key=lambda value: value.final_score, reverse=True):
        if candidate.confidence < config.highlight.min_confidence:
            candidate.rejection_reason = "置信度低于阈值"
            continue
        if candidate.risks.redundancy > config.highlight.max_redundancy:
            candidate.rejection_reason = "重复风险高于阈值"
            continue
        next_size = len(selected) + 1
        primary_type = candidate.types[0]
        if next_size > 4 and (type_counts[primary_type] + 1) / next_size > config.highlight.max_same_type_ratio:
            candidate.rejection_reason = "同类型候选过多，执行多样性约束"
            continue
        dominant_character = candidate.characters[0] if candidate.characters else None
        if (
            dominant_character
            and next_size > 4
            and (character_counts[dominant_character] + 1) / next_size
            > config.highlight.max_same_character_ratio
        ):
            candidate.rejection_reason = "单一人物候选过多，执行多样性约束"
            continue
        candidate.selected = True
        if not candidate.selection_reason:
            candidate.selection_reason = "综合故事、表演、视听与传播价值进入高光池"
        selected.append(candidate)
        type_counts[primary_type] += 1
        if dominant_character:
            character_counts[dominant_character] += 1
        if len(selected) >= limit:
            break
    return selected


def build_highlights(
    manifest: SourceManifest,
    transcript: TranscriptDocument,
    scene_index: SceneIndex,
    scene_analysis: SceneAnalysisDocument,
    story: StoryBundle,
    config: AppConfig,
    client: OpenAICompatibleClient,
    work_dir: Path,
) -> HighlightDocument:
    unit_map = {unit.unit_id: unit for unit in scene_index.units}
    candidates: list[HighlightCandidate] = []
    counter = 1
    for item in scene_analysis.items:
        unit = unit_map.get(item.unit_id)
        if unit is None:
            continue
        hints = item.candidate_highlights or _fallback_hints(item, unit)
        for hint in hints:
            candidate = _candidate_from_hint(
                item=item,
                unit=unit,
                hint=hint,
                candidate_index=counter,
                transcript=transcript,
                story=story,
            )
            candidates.append(candidate)
            counter += 1
    profile = infer_genre_profile(story, config.highlight.genre_profile)
    weights = genre_weights(profile)
    for candidate in candidates:
        candidate.final_score = _compute_final_score(candidate, weights)
    candidates.sort(key=lambda value: value.final_score, reverse=True)
    candidates = candidates[: config.highlight.candidate_pool_size]
    rerank_pool = candidates[: config.highlight.rerank_top_k]
    if rerank_pool:
        _rerank_candidates(rerank_pool, manifest, story, config, client, work_dir)
    for candidate in candidates:
        candidate.final_score = _compute_final_score(candidate, weights)
    deduplicated = _deduplicate(candidates)
    _select_diverse(deduplicated, config)
    # Keep selected and rejected candidates for auditability, selected first.
    audited = sorted(
        deduplicated,
        key=lambda value: (not value.selected, -value.final_score),
    )
    return HighlightDocument(
        genre_profile=profile,
        candidates=audited,
        weights=weights,
        source_fingerprints={source.source_id: source.fingerprint for source in manifest.sources},
    )
