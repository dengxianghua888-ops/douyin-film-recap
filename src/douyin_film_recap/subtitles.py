from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import AppConfig
from .models import Storyboard, StoryboardSegment, VisualReference


@dataclass
class SubtitleCue:
    start: float
    end: float
    text: str


def segment_output_duration(segment: StoryboardSegment) -> float:
    if segment.mode == "voiceover" and segment.audio_duration_sec:
        return float(segment.audio_duration_sec)
    return sum(visual.end - visual.start for visual in segment.visuals)


def resolved_visual_spans(segment: StoryboardSegment) -> list[VisualReference]:
    """Resolve the source intervals actually consumed, without mutating the plan.

    Rendering, the EDL and preflight must use this same decision. Surplus VO
    footage is an availability budget, not footage used in the finished cut.
    """
    if segment.mode == "original":
        return list(segment.visuals)
    remaining = float(segment.audio_duration_sec or segment.planned_duration_sec)
    resolved: list[VisualReference] = []
    for visual in segment.visuals:
        if remaining <= 1e-9:
            break
        duration = min(visual.end - visual.start, remaining)
        if duration > 0:
            resolved.append(visual.model_copy(update={"end": visual.start + duration}))
            remaining -= duration
    return resolved


def output_timeline(storyboard: Storyboard) -> list[dict[str, float | str]]:
    cursor = 0.0
    timeline: list[dict[str, float | str]] = []
    for segment in storyboard.segments:
        duration = segment_output_duration(segment)
        timeline.append(
            {
                "segment_id": segment.segment_id,
                "start": cursor,
                "end": cursor + duration,
                "duration": duration,
            }
        )
        cursor += duration
    return timeline


def _visible_units(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _split_text(text: str, max_chars: int) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    sentences = [
        item.strip()
        for item in re.split(r"(?<=[。！？!?；;，,])", cleaned)
        if item.strip()
    ]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if _visible_units(current + sentence) <= max_chars:
            current += sentence
            continue
        if current:
            chunks.append(current.strip())
            current = ""
        while _visible_units(sentence) > max_chars:
            index = max_chars
            chunks.append(sentence[:index].strip())
            sentence = sentence[index:]
        current = sentence
    if current:
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk]


def _cues_from_boundaries(
    segment: StoryboardSegment,
    output_start: float,
    max_chars: int,
) -> list[SubtitleCue]:
    boundaries = segment.tts_word_boundaries
    if not boundaries:
        return []
    groups: list[list[dict]] = []
    current: list[dict] = []
    current_text = ""
    for boundary in boundaries:
        token = str(boundary.get("text", "")).strip()
        if not token:
            continue
        start = float(boundary.get("start", 0.0))
        duration = max(0.04, float(boundary.get("duration", 0.0)))
        normalized = {"text": token, "start": start, "duration": duration}
        proposed = current_text + token
        current_duration = (
            start + duration - float(current[0]["start"]) if current else duration
        )
        punctuation_break = bool(re.search(r"[。！？!?；;]$", token))
        if current and (
            _visible_units(proposed) > max_chars
            or current_duration > 3.2
            or punctuation_break and current_duration >= 0.9
        ):
            groups.append(current)
            current = []
            current_text = ""
        current.append(normalized)
        current_text += token
    if current:
        groups.append(current)

    cues: list[SubtitleCue] = []
    audio_duration = segment.audio_duration_sec or segment.planned_duration_sec
    for group in groups:
        start = output_start + float(group[0]["start"])
        end_relative = float(group[-1]["start"]) + float(group[-1]["duration"])
        end = output_start + min(audio_duration, max(end_relative, group[0]["start"] + 0.5))
        text = "".join(str(item["text"]) for item in group).strip()
        if end > start and text:
            cues.append(SubtitleCue(start=start, end=end, text=text))
    return cues


def _distributed_cues(
    text: str,
    output_start: float,
    duration: float,
    max_chars: int,
) -> list[SubtitleCue]:
    chunks = _split_text(text, max_chars)
    if not chunks or duration <= 0:
        return []
    weights = [max(1, _visible_units(chunk)) for chunk in chunks]
    total = sum(weights)
    cumulative = 0
    cues: list[SubtitleCue] = []
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        start = output_start + duration * cumulative / total
        cumulative += weight
        end = output_start + duration * cumulative / total
        if index == len(chunks) - 1:
            end = output_start + duration
        if end - start < 0.35:
            end = min(output_start + duration, start + 0.35)
        if end > start:
            cues.append(SubtitleCue(start=start, end=end, text=chunk))
    return cues


def _original_cues(
    segment: StoryboardSegment, output_start: float, config: AppConfig
) -> list[SubtitleCue]:
    """Map source-timed dialogue, never distribute descriptive text over a shot.

    A partial cue without word timing cannot safely retain its entire sentence;
    omit it and let preflight report the missing reliable boundary.
    """
    cues: list[SubtitleCue] = []
    cursor = output_start
    for visual in resolved_visual_spans(segment):
        for source_cue in getattr(segment, "original_cues", []):
            if source_cue.source_id != visual.source_id:
                continue
            if source_cue.end <= visual.start or source_cue.start >= visual.end:
                continue
            pieces: list[tuple[float, float, str]] = []
            if source_cue.start >= visual.start - 0.001 and source_cue.end <= visual.end + 0.001:
                pieces = [(source_cue.start, source_cue.end, source_cue.text)]
            else:
                words = [word for word in getattr(source_cue, "words", [])
                         if word.timing_source in {"asr", "aligned"}
                         and word.start >= visual.start - 0.001 and word.end <= visual.end + 0.001]
                if words:
                    pieces = [(words[0].start, words[-1].end, "".join(word.text for word in words))]
            for start, end, text in pieces:
                if not text.strip():
                    continue
                wrapped = "\n".join(_split_text(text, config.render.subtitle_max_chars_per_line))
                cues.append(SubtitleCue(
                    start=cursor + max(0.0, start - visual.start),
                    end=cursor + min(visual.end, end) - visual.start,
                    text=wrapped,
                ))
        cursor += visual.end - visual.start
    return sorted(cues, key=lambda cue: (cue.start, cue.end))


def build_cues(storyboard: Storyboard, config: AppConfig) -> list[SubtitleCue]:
    max_chars = config.render.subtitle_max_chars_per_line * config.render.subtitle_max_lines
    cues: list[SubtitleCue] = []
    cursor = 0.0
    for segment in storyboard.segments:
        duration = segment_output_duration(segment)
        if segment.mode == "voiceover":
            segment_cues = _cues_from_boundaries(segment, cursor, max_chars)
            if not segment_cues:
                segment_cues = _distributed_cues(
                    segment.text, cursor, duration, max_chars
                )
            for cue in segment_cues:
                cue.text = "\n".join(_split_text(cue.text, config.render.subtitle_max_chars_per_line))
        else:
            segment_cues = _original_cues(segment, cursor, config)
        cues.extend(segment_cues)
        cursor += duration
    return cues


def _srt_time(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(cues: Iterable[SubtitleCue], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    blocks: list[str] = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n{_srt_time(cue.start)} --> {_srt_time(cue.end)}\n{cue.text}"
        )
    target.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
    return target
