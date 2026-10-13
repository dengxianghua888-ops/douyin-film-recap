"""Validate resumed VO visuals against the current, source-bound evidence.

The complete analyzed index is accepted, including manually registered evidence;
this is not limited to the bounded retrieval pool offered to the model writer.
"""
from __future__ import annotations

from .models import HighlightDocument, SceneAnalysisDocument, SceneIndex, SourceManifest, Storyboard
from .narrative_contracts import validate_visual_reference
from .utils import fingerprint_json


class VisualEvidenceError(ValueError):
    def __init__(self, message, *, segment_id=None):
        super().__init__(message)
        self.segment_id = segment_id


def validate_storyboard_visual_evidence(
    storyboard: Storyboard,
    manifest: SourceManifest,
    highlights: HighlightDocument,
    scene_index: SceneIndex | None,
    scene_analysis: SceneAnalysisDocument | None,
) -> None:
    voiceovers = [segment for segment in storyboard.segments if segment.mode == "voiceover"]
    if not voiceovers:
        return
    if scene_index is None or scene_analysis is None:
        raise VisualEvidenceError("VO visual evidence requires the current scene index and analysis")
    source_map = {source.source_id: source for source in manifest.sources}
    fingerprints = {key: source.fingerprint for key, source in source_map.items()}
    if scene_index.source_fingerprints != fingerprints:
        raise VisualEvidenceError("Scene index source identity does not match the current manifest")
    expected = fingerprint_json([unit.model_dump(mode="json") for unit in scene_index.units])
    if scene_analysis.unit_fingerprint != expected:
        raise VisualEvidenceError("Scene analysis fingerprint does not match the current scene index")
    units = {unit.unit_id: unit for unit in scene_index.units}
    analysis_ids = {item.unit_id for item in scene_analysis.items}
    if len(units) != len(scene_index.units) or len(analysis_ids) != len(scene_analysis.items):
        raise VisualEvidenceError("Duplicate unit_id in scene index or scene analysis")
    if not analysis_ids <= units.keys():
        raise VisualEvidenceError("Scene analysis references an unknown scene unit")
    pool = {}
    for key in analysis_ids:
        unit = units[key]
        source = source_map.get(unit.source_id)
        if source is None or unit.end > source.duration + 0.001:
            raise VisualEvidenceError(f"Scene unit has an invalid source range: {key}")
        pool[key] = {"source_id": unit.source_id, "start": unit.start, "end": unit.end}
    for highlight in highlights.candidates:
        if not highlight.selected:
            continue
        key = f"highlight:{highlight.highlight_id}"
        if key in pool:
            raise VisualEvidenceError(f"Duplicate visual evidence unit_id: {key}")
        source = source_map.get(highlight.source_id)
        if (source is None or highlight.end > source.duration + 0.001
                or highlights.source_fingerprints.get(highlight.source_id) != source.fingerprint):
            raise VisualEvidenceError(f"Highlight source evidence does not match the manifest: {key}")
        pool[key] = {"source_id": highlight.source_id, "start": highlight.start,
                     "end": highlight.end, "highlight_id": highlight.highlight_id}
    for segment in voiceovers:
        for visual in segment.visuals:
            try:
                validate_visual_reference(visual, pool)
            except ValueError as exc:
                raise VisualEvidenceError(str(exc), segment_id=segment.segment_id) from exc
