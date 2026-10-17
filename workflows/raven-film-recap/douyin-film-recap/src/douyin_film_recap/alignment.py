"""Offline result contract, not an acoustic aligner or proof of model execution.

Independently implemented. No optional ML imports, model downloads or inference.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import SourceInfo, TranscriptSegment, TranscriptWord
from .utils import SourceChangedDuringRead, content_identity


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class AlignmentToken(StrictRecord):
    text: str = Field(min_length=1)
    status: Literal["observed", "interpolated", "missing", "unknown"]
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, gt=0)
    score: float | None = None

    @model_validator(mode="after")
    def valid_timing(self):
        if (self.start is None) != (self.end is None):
            raise ValueError("token must have both timestamps or neither")
        if self.start is not None and self.end <= self.start:
            raise ValueError("token end must exceed start")
        if self.status == "observed" and (self.start is None or self.score is None):
            raise ValueError("observed token requires native timestamps and score")
        return self


class AlignmentCue(StrictRecord):
    cue_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    tokens: list[AlignmentToken]

    @model_validator(mode="after")
    def valid_range(self):
        if self.end <= self.start:
            raise ValueError("cue end must exceed start")
        return self


class AlignmentResult(StrictRecord):
    schema_version: Literal["film-alignment/1"] = "film-alignment/1"
    source_id: str = Field(min_length=1)
    media_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    subtitle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer: str = Field(min_length=1)
    producer_revision: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    method: str = Field(min_length=1)
    score_semantics: str = Field(min_length=1)
    provenance: Literal["producer_declared"] = "producer_declared"
    cues: list[AlignmentCue] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_cues(self):
        indices = [cue.cue_index for cue in self.cues]
        if len(indices) != len(set(indices)):
            raise ValueError("duplicate cue_index")
        return self


def read_result(path: str | Path) -> tuple[AlignmentResult, dict]:
    before = content_identity(path)
    result = AlignmentResult.model_validate_json(Path(path).read_bytes())
    if content_identity(path) != before:
        raise SourceChangedDuringRead("Alignment result changed while reading")
    return result, before


def import_alignment(path: str | Path, source: SourceInfo,
                     segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """Replace only complete observed cue word timings, never subtitle text/bounds.

    Bad identities/text/times abort. Missing or inferred evidence retains the entire
    original estimated cue. Selected windows are exactly the listed cue indices.
    """
    result, identity = read_result(path)
    if not source.has_audio or not source.subtitle_path:
        raise ValueError("Alignment import requires audio and existing subtitles")
    media = content_identity(source.path)
    subtitle = content_identity(source.subtitle_path)
    if (result.source_id != source.source_id or result.media_sha256 != media["sha256"]
            or result.subtitle_sha256 != subtitle["sha256"]
            or source.fingerprint != media["sha256"]
            or (source.subtitle_fingerprint is not None
                and source.subtitle_fingerprint != subtitle["sha256"])):
        raise ValueError("Alignment input identity mismatch")
    if any(segment.source_id != source.source_id for segment in segments):
        raise ValueError("Subtitle segment source identity mismatch")
    output = [segment.model_copy(deep=True) for segment in segments]
    provenance = result.model_dump(exclude={"cues"})
    provenance["result_sha256"] = identity["sha256"]
    for cue in result.cues:
        if cue.cue_index >= len(output):
            raise ValueError("Alignment cue_index outside subtitle")
        segment = output[cue.cue_index]
        if (cue.text != segment.text or cue.start != segment.start or cue.end != segment.end):
            raise ValueError("Alignment cue text/bounds mismatch")
        if cue.end > source.duration:
            raise ValueError("Alignment cue exceeds media duration")
        expected = [word.text for word in segment.words]
        # Missing tokens may be represented explicitly, never silently omitted.
        if [token.text for token in cue.tokens] != expected:
            raise ValueError("Alignment token text/count mismatch")
        previous_end = cue.start
        for token in cue.tokens:
            if token.start is not None:
                if token.start < previous_end or token.end > cue.end:
                    raise ValueError("Alignment token overlap or outside cue")
                previous_end = token.end
        missing = [i for i, token in enumerate(cue.tokens) if token.status != "observed"]
        overlapping = any(i != cue.cue_index and other.start < cue.end
                          and cue.start < other.end for i, other in enumerate(segments))
        fallback = "overlapping_subtitle_cues" if overlapping else (
            "incomplete_or_inferred_tokens" if missing or not cue.tokens else None)
        segment.alignment = {**provenance, "cue_index": cue.cue_index,
                             "status": "estimated" if fallback else "aligned",
                             "fallback_reason": fallback, "unobserved_token_indices": missing,
                             "tokens": [token.model_dump() for token in cue.tokens]}
        if fallback:
            for word in segment.words:
                word.timing_source = "estimated"
                word.alignment_score = None
        else:
            segment.words = [TranscriptWord(text=token.text, start=token.start, end=token.end,
                                           timing_source="aligned", alignment_score=token.score)
                             for token in cue.tokens]
    if content_identity(source.path) != media or content_identity(source.subtitle_path) != subtitle:
        raise SourceChangedDuringRead("Alignment inputs changed while importing")
    if content_identity(path) != identity:
        raise SourceChangedDuringRead("Alignment result changed while importing")
    return output


# Conversion only supports a reviewed upstream representation with native chars.
# Word timestamps alone cannot reveal interpolation or partial-character coverage.
WHISPERX_REVISION = "771b4a14a9486f8fd5aef18ef49e35d639523dd3"


def convert_whisperx(receipt: dict) -> AlignmentResult:
    """Convert per-cue raw char outputs plus explicit producer execution receipt.

    Receipt identities must have been captured by the producer at inference time.
    They are not filled in retrospectively. No WhisperX code is imported/executed.
    """
    from .asr import _TOKEN_RE

    header = dict(receipt)
    raw_cues = header.pop("whisperx_cues")
    dictionary = header.pop("dictionary")
    interpolation = header.pop("interpolate_method")
    if (header.get("producer") != "whisperx"
            or header.get("producer_revision") != WHISPERX_REVISION
            or interpolation != "ignore"
            or not isinstance(dictionary, list) or not dictionary
            or not all(isinstance(char, str) and char for char in dictionary)):
        raise ValueError("Unsupported WhisperX receipt/revision/dictionary/interpolation")
    header["method"] = "whisperx-native-char-token-span/1"
    header["score_semantics"] = "arithmetic mean of native character CTC scores; not accuracy probability"
    vocab = set(dictionary)
    cues = []
    for entry in raw_cues:
        cue = {key: entry[key] for key in ("cue_index", "text", "start", "end")}
        raw = entry["result"]
        # Multi-sentence regrouping can lose offsets or duplicate boundary chars;
        # decline it rather than reconstruct positions or change original text.
        parts = raw.get("segments", [])
        if len(parts) != 1 or parts[0].get("text") != cue["text"]:
            raise ValueError("Only one exact-text WhisperX segment per cue is supported")
        chars = parts[0].get("chars")
        if not isinstance(chars, list) or "".join(c.get("char", "") for c in chars) != cue["text"]:
            raise ValueError("Exact native character output required; word-only output unsupported")
        if any(len(c.get("char", "")) != 1 for c in chars):
            raise ValueError("One native record per character required")
        tokens = []
        for match in _TOKEN_RE.finditer(cue["text"]):
            selected = chars[match.start():match.end()]
            native = all(c["char"].lower() in vocab and all(k in c for k in ("start", "end", "score"))
                         for c in selected)
            if native:
                validated = [AlignmentToken(text=c["char"], status="observed", start=c["start"],
                                            end=c["end"], score=c["score"]) for c in selected]
                if any(a.end > b.start for a, b in zip(validated, validated[1:])):
                    raise ValueError("Overlapping native characters")
                tokens.append(AlignmentToken(text=match.group(), status="observed",
                                             start=validated[0].start, end=validated[-1].end,
                                             score=sum(c.score for c in validated) / len(validated)))
            else:
                tokens.append(AlignmentToken(text=match.group(), status="missing"))
        cues.append(AlignmentCue(**cue, tokens=tokens))
    return AlignmentResult(**header, cues=cues)
