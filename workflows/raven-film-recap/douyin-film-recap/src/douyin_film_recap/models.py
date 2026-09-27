from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ArtifactModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    @classmethod
    def now_iso(cls) -> str:
        return datetime.now(timezone.utc).isoformat()


class TimeSpan(ArtifactModel):
    source_id: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)

    @model_validator(mode="after")
    def valid_range(self) -> "TimeSpan":
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self

    @property
    def duration(self) -> float:
        return self.end - self.start


class SourceInfo(ArtifactModel):
    source_id: str
    path: str
    fingerprint: str
    filename: str
    duration: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: float = Field(gt=0)
    has_audio: bool = True
    subtitle_path: str | None = None
    order: int = 0


class SourceManifest(ArtifactModel):
    schema_version: int = 1
    created_at: str = Field(default_factory=ArtifactModel.now_iso)
    sources: list[SourceInfo]
    rights_confirmed: bool = False
    publish_mode: Literal["draft", "publish"] = "draft"
    config_fingerprint: str


class TranscriptWord(ArtifactModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str
    probability: float | None = Field(default=None, ge=0, le=1)
    timing_source: Literal["asr", "aligned", "estimated", "unknown"] = "unknown"

    @model_validator(mode="after")
    def valid_range(self) -> "TranscriptWord":
        if self.end <= self.start:
            raise ValueError("word end must be greater than start")
        return self


class TranscriptSegment(ArtifactModel):
    source_id: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str
    speaker: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    words: list[TranscriptWord] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_range(self) -> "TranscriptSegment":
        if self.end <= self.start:
            raise ValueError("segment end must be greater than start")
        return self


class TranscriptDocument(ArtifactModel):
    schema_version: int = 1
    created_at: str = Field(default_factory=ArtifactModel.now_iso)
    language: str = "zh"
    provider: str
    model: str | None = None
    segments: list[TranscriptSegment]
    source_fingerprints: dict[str, str]


class SceneSignals(ArtifactModel):
    motion: float = Field(default=0, ge=0, le=1)
    speech_density: float = Field(default=0, ge=0, le=1)
    shot_density: float = Field(default=0, ge=0, le=1)
    audio_energy: float | None = Field(default=None, ge=0, le=1)


class SceneUnit(ArtifactModel):
    unit_id: str
    source_id: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    shot_spans: list[tuple[float, float]] = Field(default_factory=list)
    transcript: str = ""
    transcript_segments: list[int] = Field(default_factory=list)
    frame_paths: list[str] = Field(default_factory=list)
    contact_sheet_path: str | None = None
    signals: SceneSignals = Field(default_factory=SceneSignals)

    @model_validator(mode="after")
    def valid_range(self) -> "SceneUnit":
        if self.end <= self.start:
            raise ValueError("scene unit end must be greater than start")
        return self


class SceneIndex(ArtifactModel):
    schema_version: int = 1
    created_at: str = Field(default_factory=ArtifactModel.now_iso)
    units: list[SceneUnit]
    source_fingerprints: dict[str, str]
    detector: str
    detector_params: dict[str, Any] = Field(default_factory=dict)


class SceneCharacterMention(ArtifactModel):
    temporary_id: str
    name_guess: str | None = None
    visual_signature: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class SceneHighlightHint(ArtifactModel):
    types: list[str]
    start_hint: float | None = None
    end_hint: float | None = None
    reason: str
    must_hear_original: bool = False


class SceneAnalysisItem(ArtifactModel):
    unit_id: str
    visible_facts: list[str] = Field(default_factory=list)
    dialogue_facts: list[str] = Field(default_factory=list)
    characters: list[SceneCharacterMention] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    emotions: list[str] = Field(default_factory=list)
    performance_moments: list[str] = Field(default_factory=list)
    candidate_highlights: list[SceneHighlightHint] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    uncertainties: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class SceneAnalysisDocument(ArtifactModel):
    schema_version: int = 1
    created_at: str = Field(default_factory=ArtifactModel.now_iso)
    provider: str
    model: str
    items: list[SceneAnalysisItem]
    unit_fingerprint: str


class CharacterRelationship(ArtifactModel):
    target_id: str
    relation: str
    state: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence: list[TimeSpan] = Field(default_factory=list)


class Character(ArtifactModel):
    character_id: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    temporary_name: bool = True
    description: str = ""
    visual_signatures: list[str] = Field(default_factory=list)
    relationships: list[CharacterRelationship] = Field(default_factory=list)
    evidence: list[TimeSpan] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class CharacterRegistry(ArtifactModel):
    schema_version: int = 1
    created_at: str = Field(default_factory=ArtifactModel.now_iso)
    characters: list[Character]
    unresolved_conflicts: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class StoryEvent(ArtifactModel):
    event_id: str
    story_order: float
    reveal_order: float
    participants: list[str] = Field(default_factory=list)
    event: str
    goal_before: dict[str, str] = Field(default_factory=dict)
    state_change: dict[str, str] = Field(default_factory=dict)
    causes: list[str] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)
    source_spans: list[TimeSpan] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class StoryGraph(ArtifactModel):
    schema_version: int = 1
    created_at: str = Field(default_factory=ArtifactModel.now_iso)
    title_guess: str | None = None
    genres: list[str] = Field(default_factory=list)
    main_plot: str
    themes: list[str] = Field(default_factory=list)
    events: list[StoryEvent]
    arcs: list[dict[str, Any]] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class KnowledgeState(ArtifactModel):
    event_id: str
    audience_knows_before: list[str] = Field(default_factory=list)
    audience_knows_after: list[str] = Field(default_factory=list)
    character_beliefs: dict[str, list[str]] = Field(default_factory=dict)
    reveal_sensitivity: Literal["low", "medium", "high"] = "medium"
    allow_prepose: bool = False
    reason: str = ""


class KnowledgeTimeline(ArtifactModel):
    schema_version: int = 1
    created_at: str = Field(default_factory=ArtifactModel.now_iso)
    states: list[KnowledgeState]


class HighlightScores(ArtifactModel):
    story_significance: float = Field(default=0.5, ge=0, le=1)
    immediate_intensity: float = Field(default=0.5, ge=0, le=1)
    performance_value: float = Field(default=0.5, ge=0, le=1)
    dialogue_value: float = Field(default=0.5, ge=0, le=1)
    visual_value: float = Field(default=0.5, ge=0, le=1)
    action_value: float = Field(default=0.5, ge=0, le=1)
    emotion_value: float = Field(default=0.5, ge=0, le=1)
    reveal_value: float = Field(default=0.5, ge=0, le=1)
    suspense_value: float = Field(default=0.5, ge=0, le=1)
    comedy_value: float = Field(default=0.0, ge=0, le=1)
    relationship_shift: float = Field(default=0.5, ge=0, le=1)
    state_change_strength: float = Field(default=0.5, ge=0, le=1)
    context_independence: float = Field(default=0.5, ge=0, le=1)
    genre_fit: float = Field(default=0.5, ge=0, le=1)
    novelty: float = Field(default=0.5, ge=0, le=1)


class HighlightRisks(ArtifactModel):
    spoiler: float = Field(default=0, ge=0, le=1)
    context_dependency: float = Field(default=0, ge=0, le=1)
    redundancy: float = Field(default=0, ge=0, le=1)
    unsafe_boundary: float = Field(default=0, ge=0, le=1)


class BoundaryQuality(ArtifactModel):
    entry_safe: bool = True
    exit_safe: bool = True
    sentence_complete: bool = True
    action_complete: bool = True
    entry_anchor: float | None = None
    exit_anchor: float | None = None


class HighlightCandidate(ArtifactModel):
    highlight_id: str
    source_id: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    types: list[str]
    characters: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    quote: str = ""
    story_function: str
    state_change: str = ""
    must_hear_original: bool = False
    boundary: BoundaryQuality = Field(default_factory=BoundaryQuality)
    scores: HighlightScores = Field(default_factory=HighlightScores)
    risks: HighlightRisks = Field(default_factory=HighlightRisks)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    final_score: float = 0.0
    selected: bool = False
    selection_reason: str = ""
    rejection_reason: str = ""

    @model_validator(mode="after")
    def valid_range(self) -> "HighlightCandidate":
        if self.end <= self.start:
            raise ValueError("highlight end must be greater than start")
        return self


class HighlightDocument(ArtifactModel):
    schema_version: int = 1
    created_at: str = Field(default_factory=ArtifactModel.now_iso)
    genre_profile: str
    candidates: list[HighlightCandidate]
    weights: dict[str, float]
    source_fingerprints: dict[str, str]


class RhythmProfile(ArtifactModel):
    tempo_intent: str = "fast_but_legible"
    first_payoff_deadline_sec: float = 6
    micro_cycle_sec: tuple[float, float] = (12, 25)
    reset_interval_sec: tuple[float, float] = (45, 75)
    vo_chars_per_sec: tuple[float, float] = (4.2, 5.2)
    shot_duration_sec: dict[str, tuple[float, float]] = Field(default_factory=dict)
    original_ratio: tuple[float, float] = (0.25, 0.45)
    max_original_over_15s: int = 2
    breathing_slots: list[dict[str, Any]] = Field(default_factory=list)
    audio_switch_target_sec: tuple[float, float] = (8, 20)
    tension_curve: list[dict[str, Any]] = Field(default_factory=list)


class RecapBeat(ArtifactModel):
    beat_id: str
    function: str
    event_ids: list[str] = Field(default_factory=list)
    change: str
    audience_question_in: str
    audience_question_out: str
    character_focus: list[str] = Field(default_factory=list)
    preferred_highlights: list[str] = Field(default_factory=list)
    narration_job: str
    target_duration_sec: float = Field(gt=0)
    target_original_sec: float = Field(default=0, ge=0)


class RecapPlan(ArtifactModel):
    schema_version: int = 1
    created_at: str = Field(default_factory=ArtifactModel.now_iso)
    viewer_promise: str
    pov: str
    main_spine: str
    hook_strategy: str
    hook_highlight_id: str
    target_duration_sec: float = Field(gt=0)
    duration_mode: str
    original_ratio_target: float = Field(ge=0, le=1)
    ending_strategy: str
    reveal_strategy: str
    beats: list[RecapBeat]
    kill_list: list[str] = Field(default_factory=list)
    rhythm: RhythmProfile
    risks: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    resolved_constraints: dict[str, Any] = Field(default_factory=dict)
    content_unit: str = "auto"
    editorial_brief: dict[str, Any] = Field(default_factory=dict)


class VisualReference(ArtifactModel):
    source_id: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    purpose: str = ""
    highlight_id: str | None = None
    unit_id: str | None = None
    visual_role: Literal["direct_evidence", "context", "reaction", "transition"] = "context"

    @model_validator(mode="after")
    def valid_range(self) -> "VisualReference":
        if self.end <= self.start:
            raise ValueError("visual end must be greater than start")
        return self


class OriginalCue(TimeSpan):
    text: str
    words: list[TranscriptWord] = Field(default_factory=list)


class StoryboardSegment(ArtifactModel):
    segment_id: str
    beat_id: str
    mode: Literal["voiceover", "original"]
    title: str
    text: str
    text_raw: str = ""
    original_cues: list[OriginalCue] = Field(default_factory=list)
    original_cues_verified: bool = False
    visuals: list[VisualReference]
    audio_owner: Literal[
        "narration",
        "original_dialogue",
        "action_sound",
        "ambience",
        "music",
        "silence",
    ]
    narration_job: Literal[
        "none",
        "context",
        "causal_link",
        "foreshadow",
        "interpretation",
        "transition",
    ] = "none"
    mute_original: bool = True
    planned_duration_sec: float = Field(gt=0)
    audio_file: str | None = None
    audio_source_duration_sec: float | None = None
    audio_duration_sec: float | None = None
    audio_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    tts_word_boundaries: list[dict[str, Any]] = Field(default_factory=list)
    highlight_id: str | None = None
    hook_preposed: bool = False
    allow_reuse: bool = False
    notes: str
    status: Literal["planned", "audio_ready", "rendered", "failed"] = "planned"


class Storyboard(ArtifactModel):
    schema_version: int = 1
    created_at: str = Field(default_factory=ArtifactModel.now_iso)
    project_name: str
    sources: list[SourceInfo]
    plan_fingerprint: str
    target_duration_sec: float
    segments: list[StoryboardSegment]
    output: dict[str, Any] = Field(default_factory=dict)


class QCLocation(ArtifactModel):
    segment_id: str | None = None
    source_id: str | None = None
    source_time: float | None = None
    output_time: float | None = None


class QCFinding(ArtifactModel):
    finding_id: str
    stage: str
    severity: Literal["info", "warning", "error", "critical"]
    blocking: bool
    deterministic: bool
    rule_id: str
    message: str
    location: QCLocation = Field(default_factory=QCLocation)
    evidence: dict[str, Any] = Field(default_factory=dict)
    next_action: str = ""


class QCReport(ArtifactModel):
    schema_version: int = 1
    created_at: str = Field(default_factory=ArtifactModel.now_iso)
    stage: str
    status: Literal["PASSED", "DEGRADED", "BLOCKED"]
    findings: list[QCFinding] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    providers: dict[str, str] = Field(default_factory=dict)
    attempts: int = 1
    coverage: dict[str, Any] = Field(default_factory=dict)


class StageRecord(ArtifactModel):
    status: Literal["pending", "running", "passed", "failed", "skipped"] = "pending"
    started_at: str | None = None
    finished_at: str | None = None
    artifact: str | None = None
    fingerprint: str | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)
    input_fingerprint: str | None = None
    error: dict[str, Any] | None = None


class PipelineState(ArtifactModel):
    schema_version: int = 1
    project_name: str
    created_at: str = Field(default_factory=ArtifactModel.now_iso)
    updated_at: str = Field(default_factory=ArtifactModel.now_iso)
    input_paths: list[str]
    input_fingerprint: str | None = None
    config_fingerprint: str
    stages: dict[str, StageRecord]
    last_error: dict[str, Any] | None = None


class SceneAnalysisBatch(ArtifactModel):
    items: list[SceneAnalysisItem]


class StoryBundle(ArtifactModel):
    character_registry: CharacterRegistry
    story_graph: StoryGraph
    knowledge_timeline: KnowledgeTimeline


class HighlightRerankItem(ArtifactModel):
    highlight_id: str
    scores: HighlightScores
    risks: HighlightRisks = Field(default_factory=HighlightRisks)
    types: list[str] = Field(default_factory=list)
    must_hear_original: bool = False
    story_function: str = ""
    state_change: str = ""
    selection_reason: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)


class HighlightRerankBatch(ArtifactModel):
    items: list[HighlightRerankItem]


class SemanticQCBundle(ArtifactModel):
    findings: list[QCFinding] = Field(default_factory=list)


class StoryChunkEvent(ArtifactModel):
    event: str
    participants: list[str] = Field(default_factory=list)
    source_spans: list[TimeSpan] = Field(default_factory=list)
    state_change: str = ""
    reveal_note: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)


class StoryChunkSummary(ArtifactModel):
    chunk_id: str
    source_ids: list[str] = Field(default_factory=list)
    characters: list[dict[str, Any]] = Field(default_factory=list)
    events: list[StoryChunkEvent] = Field(default_factory=list)
    relationship_changes: list[str] = Field(default_factory=list)
    knowledge_reveals: list[str] = Field(default_factory=list)
    genre_signals: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
