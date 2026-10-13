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


def _scene_unit_fingerprints(scene_index: SceneIndex) -> set[str]:
    current = [unit.model_dump(mode="json") for unit in scene_index.units]
    fingerprints = {fingerprint_json(current)}
    if scene_index.schema_version != 1:
        return fingerprints
    # Schema-1 indices from before detector provenance omit these new defaults.
    # Only omit fields that were genuinely absent in the loaded artifact. Explicit
    # metadata, including explicit null/default values, must remain hash-bound.
    legacy = []
    for unit in scene_index.units:
        row = unit.model_dump(mode="json")
        if "scene_detection" not in unit.model_fields_set:
            row.pop("scene_detection", None)
        if "shot_density_available" not in unit.signals.model_fields_set:
            row["signals"].pop("shot_density_available", None)
        legacy.append(row)
    fingerprints.add(fingerprint_json(legacy))
    return fingerprints


def validate_storyboard_visual_evidence(
    storyboard: Storyboard,
    manifest: SourceManifest,
    highlights: HighlightDocument,
    scene_index: SceneIndex | None,
    scene_analysis: SceneAnalysisDocument | None,
) -> None:
    voiceovers = [segment for segment in storyboard.segments if segment.mode == "voiceover"]
    # Bound highlight references, including original-mode segments, cannot drift
    # to a newer range just because their logical h0001 ID stayed the same.
    from .boundary import validate_highlight_reference_binding, highlight_reference_binding
    current_highlights = {item.highlight_id: item for item in highlights.candidates}
    sources = {item.source_id: item for item in manifest.sources}
    for segment in storyboard.segments:
        for visual in segment.visuals:
            highlight_id = visual.highlight_id
            if not highlight_id and (visual.unit_id or "").startswith("highlight:"):
                highlight_id = visual.unit_id[len("highlight:"):]
            highlight = current_highlights.get(highlight_id or "")
            try:
                if highlight is None:
                    if (visual.model_extra or {}).get("evidence_revision"):
                        raise ValueError(f"Missing versioned highlight evidence: {highlight_id}")
                    continue
                binding = highlight_reference_binding(highlight)
                validate_highlight_reference_binding(visual, highlight)
                if binding:
                    source = sources.get(highlight.source_id)
                    if source is None or source.fingerprint != binding["source_sha256"]:
                        raise ValueError(f"Bound highlight source SHA changed: {highlight_id}")
                    validate_visual_reference(visual, {visual.unit_id: {
                        "source_id": highlight.source_id, "start": highlight.start,
                        "end": highlight.end, "highlight_id": highlight.highlight_id,
                    }})
            except ValueError as exc:
                raise VisualEvidenceError(str(exc), segment_id=segment.segment_id) from exc
    if not voiceovers:
        return
    if scene_index is None or scene_analysis is None:
        raise VisualEvidenceError("VO visual evidence requires the current scene index and analysis")
    source_map = {source.source_id: source for source in manifest.sources}
    fingerprints = {key: source.fingerprint for key, source in source_map.items()}
    if scene_index.source_fingerprints != fingerprints:
        raise VisualEvidenceError("Scene index source identity does not match the current manifest")
    if scene_analysis.unit_fingerprint not in _scene_unit_fingerprints(scene_index):
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
