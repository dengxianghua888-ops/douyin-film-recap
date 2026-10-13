"""Versioned cross-window proposals; this module never mutates a workspace.

Source/range validation, semantic observations and editorial adoption are separate.
Legacy BoundaryQuality booleans are deliberately not evidence.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .models import HighlightCandidate, SceneAnalysisDocument, SceneIndex, SourceManifest
from .utils import fingerprint_json

State = Literal["accept", "reject", "unknown"]
SHA = r"^[0-9a-f]{64}$"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Interval(Contract):
    start: float = Field(ge=0)
    end: float = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("interval must have start < end")
        return self


class TimebaseBinding(Contract):
    """Explicit verified media-PTS mapping, never inferred as frame-number/fps."""
    mapping_version: str = Field(min_length=1)
    numerator: int = Field(gt=0)
    denominator: int = Field(gt=0)
    origin_pts: int = 0
    origin_seconds: float = Field(default=0, ge=0)
    method: Literal["demux_pts", "verified_cfr", "unknown"] = "unknown"
    verified: bool = False


class EvidenceUnitBinding(Contract):
    unit_id: str = Field(min_length=1)
    unit_revision: str = Field(pattern=SHA)
    analysis_revision: str = Field(pattern=SHA)
    source_id: str
    source_sha256: str = Field(pattern=SHA)
    timebase_hash: str = Field(pattern=SHA)


class BoundaryObservation(Contract):
    node: str = Field(min_length=1)
    state: State = "unknown"
    evidence_ids: list[str] = Field(default_factory=list)
    observed_range: Interval | None = None
    modality: Literal["video", "audio", "subtitle", "multimodal"]
    method: Literal["model", "human", "deterministic"]
    reviewer: str = Field(min_length=1)
    version: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class BoundaryProposal(Contract):
    schema_version: Literal["boundary-proposal/1"] = "boundary-proposal/1"
    proposal_id: str = Field(min_length=1)
    candidate_id: str
    candidate_revision: str = Field(pattern=SHA)
    source_id: str
    source_sha256: str = Field(pattern=SHA)
    original_range: Interval
    proposed_range: Interval
    original_highlight_hash: str = Field(pattern=SHA)
    timebase: TimebaseBinding | None = None
    ordered_evidence_units: list[EvidenceUnitBinding] = Field(default_factory=list)
    evidence_shot_ids: list[str] = Field(default_factory=list)
    shot_detection_status: Literal["detected", "fallback", "mixed", "unknown"] = "unknown"
    context_range: Interval | None = None
    raw_evidence_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    canonical_character_ids: list[str] = Field(default_factory=list)
    required_nodes: list[str] = Field(default_factory=list)
    observations: list[BoundaryObservation] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    alternative_boundaries: list[Interval] = Field(default_factory=list)
    start_uncertainty: Interval | None = None
    end_uncertainty: Interval | None = None
    audio_evidence_ids: list[str] = Field(default_factory=list)
    source_audio_stream_id: str | None = None
    must_preserve_source_track: bool = False
    dialogue_required: bool = False
    observed_audio_roles: list[str] = Field(default_factory=list)
    dialogue_spans: list[Interval] = Field(default_factory=list)
    sentence_boundary_provenance: str | None = None
    contained_reveal_ids: list[str] = Field(default_factory=list)
    newly_exposed_reveal_ids: list[str] = Field(default_factory=list)
    knowledge_snapshot_hash: str = Field(pattern=SHA)
    allowed_output_position_constraints: dict[str, Any] = Field(default_factory=dict)
    producer: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    cost: dict[str, Any] = Field(default_factory=dict)
    base_artifact_hashes: dict[str, str] = Field(default_factory=dict)
    editorial_decision: Literal["pending", "approved", "rejected"] = "pending"
    approved_proposal_hash: str | None = None
    proposal_content_hash: str | None = None


class BoundaryCheck(Contract):
    check: str
    state: State
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)
    advisory: bool = False


class BoundaryValidation(Contract):
    proposal_hash: str
    structural_state: State
    semantic_state: State
    validation_state: State
    checks: list[BoundaryCheck]
    covered_intervals: list[Interval]
    coverage_gaps: list[Interval]
    semantic_advisory: bool = True


def proposal_hash(proposal: BoundaryProposal) -> str:
    return fingerprint_json(proposal.model_dump(mode="json", exclude={
        "editorial_decision", "approved_proposal_hash", "proposal_content_hash",
    }))


def candidate_revision(candidate: HighlightCandidate) -> str:
    return str((candidate.model_extra or {}).get("evidence_revision")
               or fingerprint_json(candidate.model_dump(mode="json")))


def _state(values) -> State:
    values = list(values)
    return "reject" if "reject" in values else "unknown" if "unknown" in values else "accept"


def interval_coverage(intervals: list[Interval], target: Interval) -> tuple[list[Interval], list[Interval]]:
    """Exact union; no arbitrary tolerance or min/max bridge across missing data."""
    merged: list[list[float]] = []
    for item in sorted(intervals, key=lambda value: (value.start, value.end)):
        lo, hi = max(item.start, target.start), min(item.end, target.end)
        if lo >= hi:
            continue
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(hi, merged[-1][1])
        else:
            merged.append([lo, hi])
    gaps, cursor = [], target.start
    for lo, hi in merged:
        if cursor < lo:
            gaps.append(Interval(start=cursor, end=lo))
        cursor = hi
    if cursor < target.end:
        gaps.append(Interval(start=cursor, end=target.end))
    return [Interval(start=lo, end=hi) for lo, hi in merged], gaps


def validate_boundary_proposal(
    proposal: BoundaryProposal, *, manifest: SourceManifest,
    candidate: HighlightCandidate, scene_index: SceneIndex,
    scene_analysis: SceneAnalysisDocument, knowledge_snapshot_hash: str,
    timebases: dict[str, TimebaseBinding],
) -> BoundaryValidation:
    checks: list[BoundaryCheck] = []

    def add(check, state, reason, ids=(), advisory=False):
        checks.append(BoundaryCheck(check=check, state=state, reason=reason,
                                    evidence_ids=list(ids), advisory=advisory))

    content_hash = proposal_hash(proposal)
    add("proposal_hash", "accept" if proposal.proposal_content_hash == content_hash else "reject",
        "Proposal content must match its frozen hash")
    source = next((s for s in manifest.sources if s.source_id == proposal.source_id), None)
    valid_source = bool(source and source.identity_schema == "sha256-full/2"
                        and source.fingerprint == proposal.source_sha256
                        and candidate.source_id == proposal.source_id
                        and scene_index.source_fingerprints.get(proposal.source_id) == source.fingerprint)
    add("source_identity", "accept" if valid_source else "reject", "Full source SHA and source ID binding")
    current_hash = fingerprint_json(candidate.model_dump(mode="json"))
    original_ok = (proposal.candidate_id == candidate.highlight_id
                   and proposal.candidate_revision == candidate_revision(candidate)
                   and proposal.original_highlight_hash == current_hash
                   and (proposal.original_range.start, proposal.original_range.end)
                   == (candidate.start, candidate.end))
    add("candidate_revision", "accept" if original_ok else "reject", "No stale candidate or implicit ID rebinding")
    add("knowledge_revision", "accept" if proposal.knowledge_snapshot_hash == knowledge_snapshot_hash else "reject",
        "Knowledge snapshot must remain unchanged")
    add("source_range", "accept" if source and proposal.proposed_range.end <= source.duration else "reject",
        "Proposed range is within the source duration")
    tb, current_tb = proposal.timebase, timebases.get(proposal.source_id)
    if tb is None or current_tb is None or not tb.verified or tb.method == "unknown":
        add("timebase", "unknown", "Missing verified PTS mapping; fps division is not a VFR mapping")
    else:
        add("timebase", "accept" if tb == current_tb else "reject", "Frozen timebase mapping")
    units = {unit.unit_id: unit for unit in scene_index.units}
    analyses = {item.unit_id: item for item in scene_analysis.items}
    from .visual_evidence import _scene_unit_fingerprints
    index_ok = (len(units) == len(scene_index.units)
                and len(analyses) == len(scene_analysis.items)
                and scene_analysis.unit_fingerprint in _scene_unit_fingerprints(scene_index))
    add("analysis_revision", "accept" if index_ok else "reject", "Analysis is bound to the complete current scene index")
    spans, order = [], []
    ids = [ref.unit_id for ref in proposal.ordered_evidence_units]
    add("unique_units", "accept" if len(ids) == len(set(ids)) else "reject", "Evidence units must be unique")
    for ref in proposal.ordered_evidence_units:
        unit, analysis = units.get(ref.unit_id), analyses.get(ref.unit_id)
        valid = bool(unit and analysis and ref.source_id == proposal.source_id
                     and unit.source_id == proposal.source_id
                     and ref.source_sha256 == proposal.source_sha256
                     and ref.unit_revision == fingerprint_json(unit.model_dump(mode="json"))
                     and ref.analysis_revision == fingerprint_json(analysis.model_dump(mode="json"))
                     and tb and ref.timebase_hash == fingerprint_json(tb.model_dump(mode="json")))
        add(f"unit:{ref.unit_id}", "accept" if valid else "reject", "Source, unit, analysis and timebase lineage", [ref.unit_id])
        if valid:
            spans.append(Interval(start=unit.start, end=unit.end))
            order.append((unit.start, unit.end, unit.unit_id))
    add("unit_order", "accept" if order == sorted(order) else "reject", "Evidence references follow source time")
    covered, gaps = interval_coverage(spans, proposal.proposed_range)
    add("coverage", "unknown" if gaps else "accept", "Unobserved middle intervals remain unknown", ids)
    if proposal.context_range is None or proposal.context_range.start > proposal.proposed_range.start or proposal.context_range.end < proposal.proposed_range.end:
        add("context", "unknown", "Context does not cover the full proposed range")
    if proposal.shot_detection_status != scene_index.detection_status:
        add("shot_provenance", "reject", "Shot detection status differs from the current index")
    if proposal.evidence_shot_ids and proposal.shot_detection_status in {"fallback", "unknown"}:
        add("shot_provenance", "reject", "Fallback windows cannot establish real shot identity")
    if proposal.evidence_shot_ids:
        # Global mixed/detected status cannot certify a fallback source or an
        # invented shot ID. IDs are admitted only from bound units of this source.
        verified_shots = set()
        source_metadata = scene_index.source_detection.get(proposal.source_id)
        source_is_fallback = bool(source_metadata and (
            source_metadata.detector_used == "fixed_interval"
            or source_metadata.boundary_confidence == "unknown"))
        for ref in proposal.ordered_evidence_units:
            unit = units.get(ref.unit_id)
            if not unit or unit.source_id != proposal.source_id or source_is_fallback:
                continue
            metadata = unit.scene_detection or source_metadata
            if not metadata or metadata.detector_used == "fixed_interval" or metadata.boundary_confidence != "detector_estimated":
                continue
            extra = unit.model_extra or {}
            if extra.get("original_shot_spans"):
                verified_shots.update(extra.get("continuity_shot_ids", []))
        add("shot_identity", "accept" if set(proposal.evidence_shot_ids) <= verified_shots else "reject",
            "Every shot ID must belong to source-bound detector evidence", proposal.evidence_shot_ids)
    structural = _state(c.state for c in checks)
    semantic_checks = []
    available_ids = set(proposal.raw_evidence_ids + proposal.audio_evidence_ids)
    if not proposal.required_nodes:
        semantic_checks.append(BoundaryCheck(check="semantic_nodes", state="unknown",
                                             reason="Required semantic nodes were not specified", advisory=True))
    for node in proposal.required_nodes:
        rows = [row for row in proposal.observations if row.node == node]
        usable = [row for row in rows if row.evidence_ids and set(row.evidence_ids) <= available_ids
                  and row.observed_range and proposal.context_range
                  and row.observed_range.start >= proposal.proposed_range.start
                  and row.observed_range.end <= proposal.proposed_range.end]
        state = _state(row.state for row in usable) if usable else "unknown"
        semantic_checks.append(BoundaryCheck(check=f"semantic:{node}", state=state,
            reason="Semantic observations remain advisory; old completeness booleans are not migrated",
            evidence_ids=[eid for row in usable for eid in row.evidence_ids], advisory=True))
    audio_observed = any(row.modality in {"audio", "multimodal"}
                         and row.state == "accept" and row.evidence_ids
                         and set(row.evidence_ids) <= set(proposal.audio_evidence_ids)
                         and row.observed_range
                         and row.observed_range.start <= proposal.proposed_range.start
                         and row.observed_range.end >= proposal.proposed_range.end
                         for row in proposal.observations)
    if proposal.must_preserve_source_track and not (proposal.audio_evidence_ids and proposal.source_audio_stream_id and audio_observed):
        semantic_checks.append(BoundaryCheck(check="source_audio", state="unknown", reason="Required original audio was not independently observed", advisory=True))
    if proposal.dialogue_required and not (proposal.dialogue_spans and proposal.sentence_boundary_provenance):
        semantic_checks.append(BoundaryCheck(check="dialogue_boundary", state="unknown", reason="Dialogue requires observed sentence boundary provenance", advisory=True))
    if proposal.cost.get("budget_exhausted"):
        semantic_checks.append(BoundaryCheck(check="budget", state="unknown", reason="Evidence budget exhausted", advisory=True))
    semantic = _state(c.state for c in semantic_checks)
    checks.extend(semantic_checks)
    return BoundaryValidation(proposal_hash=content_hash, structural_state=structural,
        semantic_state=semantic, validation_state=_state([structural, semantic]), checks=checks,
        covered_intervals=covered, coverage_gaps=gaps)


def highlight_reference_binding(candidate: HighlightCandidate) -> dict[str, Any]:
    """Only new explicitly bound revisions acquire strict binding requirements."""
    extra = candidate.model_extra or {}
    keys = ("evidence_revision", "source_sha256", "timebase_hash", "unit_lineage")
    if not any(key in extra for key in keys):
        return {}
    if any(key not in extra for key in keys):
        raise ValueError(f"Incomplete highlight evidence binding: {candidate.highlight_id}")
    return {key: extra[key] for key in keys}


def validate_highlight_reference_binding(visual, candidate: HighlightCandidate) -> None:
    expected = highlight_reference_binding(candidate)
    actual = visual.model_extra or {}
    if expected and any(actual.get(key) != value for key, value in expected.items()):
        raise ValueError(f"Stale or missing highlight evidence revision: {candidate.highlight_id}")
    if not expected and actual.get("evidence_revision"):
        raise ValueError(f"Bound visual cannot be downgraded to legacy highlight: {candidate.highlight_id}")
