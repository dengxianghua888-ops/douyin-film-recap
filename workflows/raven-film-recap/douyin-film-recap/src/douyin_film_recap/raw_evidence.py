"""Independently source-bound raw observations and advisory claim verification.

No model/remote service is invoked by default. Original assets are read and
re-decoded locally; derived story/plan text is never an observer input.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import tempfile
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import Field
from .boundary import Contract, Interval, SHA, State, TimebaseBinding, interval_coverage
from .models import SourceManifest
from .utils import content_fingerprint, fingerprint_json, run_command


class RawAsset(Contract):
    asset_id: str = Field(min_length=1)
    modality: Literal["video", "audio", "subtitle"]
    kind: Literal["video_clip", "video_frame", "audio_pcm", "subtitle_sidecar"]
    relative_path: str
    sha256: str = Field(pattern=SHA)
    source_id: str
    source_sha256: str = Field(pattern=SHA)
    stream_id: str
    source_range: Interval
    frame_index: int | None = Field(default=None, ge=0)
    source_pts: int | None = None
    sample_time: float | None = Field(default=None, ge=0)
    subtitle_origin: Literal["sidecar"] | None = None
    subtitle_source_sha256: str | None = None
    decoder_version: str = Field(min_length=1)
    sampling_version: Literal["raw-source/1"] = "raw-source/1"


class RawEvidenceCard(Contract):
    schema_version: Literal["raw-evidence/1"] = "raw-evidence/1"
    layer: Literal["raw_source"] = "raw_source"
    evidence_id: str = Field(min_length=1)
    source_id: str
    source_sha256: str = Field(pattern=SHA)
    timebase: TimebaseBinding
    requested_range: Interval
    assets: list[RawAsset] = Field(default_factory=list)
    coverage_gaps: list[Interval] = Field(default_factory=list)
    budget_exhausted: bool = False
    # No story summaries, scores, visible_facts or generated explanations allowed.


class DerivedClaim(Contract):
    schema_version: Literal["derived-claim/1"] = "derived-claim/1"
    claim_id: str = Field(min_length=1)
    generation_revision: str = Field(pattern=SHA)
    exact_text: str = Field(min_length=1)
    claim_type: Literal["identity", "action", "sequence", "causality", "motivation", "reveal",
                        "dialogue_text", "tone", "speaker", "sound_event", "silence"]
    event_ids: list[str] = Field(default_factory=list)
    canonical_character_ids: list[str] = Field(default_factory=list)
    proposed_support_ids: list[str] = Field(default_factory=list)
    required_nodes: list[Literal["claim", "entry", "action", "result", "reaction", "dialogue",
        "speaker", "tone", "sound", "identity", "sequence", "reveal"]] = Field(default_factory=lambda:["claim"])
    required_modalities: list[Literal["video", "audio", "subtitle"]] = Field(default_factory=list)


class RawObservation(Contract):
    node: str
    evidence_id: str
    asset_id: str
    modality: Literal["video", "audio", "subtitle"]
    source_time: float = Field(ge=0)
    observation: str = Field(min_length=1)
    relation: Literal["support", "contradict", "insufficient"]


class ClaimJudgment(Contract):
    state: State = "unknown"
    reason: str
    limitations: list[str] = Field(default_factory=list)


class ClaimVerification(Contract):
    schema_version: Literal["claim-verification/1"] = "claim-verification/1"
    claim_id: str
    claim_revision: str
    generation_revision: str
    raw_card_hashes: dict[str, str]
    raw_asset_hashes: dict[str, str]
    consumed_asset_hashes: dict[str, str] = Field(default_factory=dict)
    structural_state: State
    advisory_verdict: State
    status: Literal["ADVISORY", "UNKNOWN", "BLOCKED"]
    observations: list[RawObservation]
    observation_input_hash: str | None
    observation_output_hash: str | None
    judgment_input_hash: str | None
    judgment_output_hash: str | None
    checks: list[dict[str, Any]]
    reason: str
    reviewer: str
    reviewer_version: str
    advisory: Literal[True] = True
    qc_upgrade_allowed: Literal[False] = False
    final_render_review_inherited: Literal[False] = False


_REQUIRED = {
    "identity":{"video"}, "action":{"video"}, "sequence":{"video"}, "causality":{"video"},
    "motivation":{"video"}, "reveal":{"video"}, "dialogue_text":{"audio"},
    "tone":{"audio"}, "speaker":{"video","audio"}, "sound_event":{"audio"}, "silence":{"audio"},
}


def _decoder_version():
    return run_command(["ffmpeg","-version"],timeout=15).stdout.splitlines()[0]


def _raw_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or str(rel) in {"", "."}:
        raise ValueError("RAW_ASSET_PATH_UNSAFE")
    path = root / rel
    cursor = path
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError("RAW_ASSET_SYMLINK")
        cursor = cursor.parent
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("RAW_ASSET_ESCAPES_ROOT")
    return path


def _frame_rows(source):
    raw = run_command(["ffprobe","-v","error","-select_streams","v:0","-show_frames",
        "-show_entries","frame=best_effort_timestamp,pkt_duration,duration","-of","json",source.path],timeout=120)
    return json.loads(raw.stdout).get("frames",[])


def _decode_asset(source, asset: RawAsset, timebase: TimebaseBinding, output: Path):
    start = timebase.origin_pts * timebase.numerator / timebase.denominator + asset.source_range.start
    end = timebase.origin_pts * timebase.numerator / timebase.denominator + asset.source_range.end
    args = ["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-n","-copyts","-i",source.path,
            "-map_metadata","-1","-map_metadata:s","-1","-map_chapters","-1"]
    if asset.kind == "video_frame":
        if asset.stream_id != "v:0" or asset.frame_index is None or asset.source_pts is None:
            raise ValueError("RAW_FRAME_PTS_REQUIRED")
        rows = _frame_rows(source)
        if asset.frame_index >= len(rows) or int(rows[asset.frame_index].get("best_effort_timestamp", -1)) != asset.source_pts:
            raise ValueError("RAW_FRAME_SOURCE_PTS_CHANGED")
        actual = (asset.source_pts-timebase.origin_pts)*timebase.numerator/timebase.denominator
        if not asset.source_range.start <= actual < asset.source_range.end:
            raise ValueError("RAW_FRAME_OUTSIDE_DECLARED_RANGE")
        if asset.sample_time is None or abs(actual-asset.sample_time)>1e-9:
            raise ValueError("RAW_FRAME_SAMPLE_TIME_CHANGED")
        args += ["-map","0:v:0","-vf",f"select=eq(n\\,{asset.frame_index})",
                 "-fps_mode","passthrough","-frames:v","1",str(output)]
    elif asset.kind == "video_clip":
        if asset.stream_id != "v:0":
            raise ValueError("RAW_VIDEO_STREAM_UNSUPPORTED")
        args += ["-map","0:v:0","-vf",f"trim=start={start:.12f}:end={end:.12f},setpts=PTS-STARTPTS",
                 "-fps_mode","passthrough","-an","-c:v","ffv1",str(output)]
    elif asset.kind == "audio_pcm":
        if asset.stream_id != "a:0":
            raise ValueError("RAW_AUDIO_STREAM_UNSUPPORTED")
        args += ["-map","0:a:0","-af",f"atrim=start={start:.12f}:end={end:.12f},asetpts=PTS-STARTPTS",
                 "-vn","-c:a","pcm_s16le",str(output)]
    else:
        raise ValueError("RAW_ASSET_KIND_NOT_DECODABLE")
    run_command(args,timeout=120)
    if not output.is_file() or output.stat().st_size == 0:
        raise ValueError("RAW_DECODE_EMPTY")


def _decoded_digest(path: Path, kind: str):
    if kind == "video_frame":
        from PIL import Image
        with Image.open(path) as img:
            rgb=img.convert("RGB")
            return fingerprint_json({"size":rgb.size,"pixels":hashlib.sha256(rgb.tobytes()).hexdigest()})
    if kind == "audio_pcm":
        import wave
        with wave.open(str(path),"rb") as wav:
            return fingerprint_json({"rate":wav.getframerate(),"channels":wav.getnchannels(),
                "width":wav.getsampwidth(),"frames":wav.getnframes(),
                "pcm":hashlib.sha256(wav.readframes(wav.getnframes())).hexdigest()})
    # Hash decoded frames/timing; ignore non-deterministic Matroska metadata.
    return run_command(["ffmpeg","-v","error","-i",str(path),"-map","0:v:0",
                        "-f","framehash","-hash","sha256","-"],timeout=120).stdout




def _canonical_observer_bytes(path: Path, kind: str) -> bytes:
    """Only decoded native content may reach the observer, never asset tags."""
    if kind == "video_frame":
        from PIL import Image
        with Image.open(path) as img:
            rgb=img.convert("RGB")
            clean=Image.frombytes("RGB",rgb.size,rgb.tobytes())
            output=io.BytesIO();clean.save(output,format="PNG")
            return output.getvalue()
    if kind == "audio_pcm":
        import wave
        with wave.open(str(path),"rb") as wav:
            channels,width,rate=wav.getnchannels(),wav.getsampwidth(),wav.getframerate()
            samples=wav.readframes(wav.getnframes())
        output=io.BytesIO()
        with wave.open(output,"wb") as wav:
            wav.setnchannels(channels);wav.setsampwidth(width);wav.setframerate(rate);wav.writeframes(samples)
        return output.getvalue()
    # This file was independently re-decoded from source using explicit metadata
    # removal. Original caller-provided Matroska tags are never delivered.
    return path.read_bytes()


def _native_coverage(source, asset, path, timebase):
    """Derive coverage from decoded samples and actual demux timing, not labels."""
    if asset.kind == "video_frame":
        return []  # Point sample is never continuous video coverage.
    if asset.kind == "audio_pcm":
        import wave
        from .media import ffprobe_json
        with wave.open(str(path),"rb") as wav:
            count, rate = wav.getnframes(), wav.getframerate()
        if count <= 0 or rate <= 0:
            raise ValueError("RAW_AUDIO_HAS_NO_SAMPLES")
        streams=[s for s in ffprobe_json(source.path).get("streams",[]) if s.get("codec_type")=="audio"]
        if not streams:
            raise ValueError("RAW_SOURCE_AUDIO_MISSING")
        from fractions import Fraction
        try:
            stream=streams[0]
            origin=float(int(stream["start_pts"])*Fraction(stream["time_base"]))
            origin-=timebase.origin_pts*timebase.numerator/timebase.denominator
        except (KeyError,ValueError,TypeError,ZeroDivisionError):
            return []  # Unknown audio clock must not invent coverage.
        start=max(asset.source_range.start,origin)
        end=min(asset.source_range.end,float(Fraction(str(start))+Fraction(count,rate)))
        return [Interval(start=start,end=end)] if end>start else []
    if asset.kind == "subtitle_sidecar":
        return []  # Caption presence says nothing about audio/video continuity.
    rows=_frame_rows(source)
    intervals=[]
    selected=[]
    for index,row in enumerate(rows):
        if "best_effort_timestamp" not in row:
            continue
        pts=int(row["best_effort_timestamp"])
        start=(pts-timebase.origin_pts)*timebase.numerator/timebase.denominator
        if not asset.source_range.start <= start < asset.source_range.end:
            continue
        selected.append(row)
        duration=row.get("duration",row.get("pkt_duration"))
        if duration is not None and int(duration)>0:
            end=(pts-timebase.origin_pts+int(duration))*timebase.numerator/timebase.denominator
        elif index+1<len(rows) and "best_effort_timestamp" in rows[index+1]:
            end=(int(rows[index+1]["best_effort_timestamp"])-timebase.origin_pts)*timebase.numerator/timebase.denominator
        else:
            continue  # Last-frame duration unknown, never borrow manifest.duration.
        end=min(end,asset.source_range.end)
        if end>start:
            intervals.append(Interval(start=start,end=end))
    hashes=[line for line in _decoded_digest(path,"video_clip").splitlines() if line and not line.startswith("#")]
    if not hashes or len(hashes)!=len(selected):
        raise ValueError("RAW_VIDEO_FRAME_COUNT_OR_COVERAGE_INVALID")
    return intervals


def verify_raw_evidence(card: RawEvidenceCard, *, manifest: SourceManifest,
                        evidence_root: str | Path) -> dict[str, Any]:
    """Re-read full identities and independently re-decode each native raw asset.

    Returns verified bytes to the observer; paths and caller-supplied hashes alone
    never count as observed input. Exceptions are deterministic structural failures.
    """
    from .boundary_apply import collect_boundary_timebases
    root=Path(evidence_root).resolve()
    sources=[s for s in manifest.sources if s.source_id==card.source_id]
    if len(sources)!=1:
        raise ValueError("RAW_SOURCE_ID_NOT_UNIQUE")
    source=sources[0]
    if source.fingerprint!=card.source_sha256 or content_fingerprint(source.path)!=card.source_sha256:
        raise ValueError("RAW_SOURCE_SHA_MISMATCH")
    if card.requested_range.end>source.duration:
        raise ValueError("RAW_SOURCE_RANGE_INVALID")
    current=collect_boundary_timebases(manifest.model_copy(update={"sources":[source]}))[source.source_id]
    if card.timebase != current:
        raise ValueError("RAW_TIMEBASE_MISMATCH")
    if len({a.asset_id for a in card.assets})!=len(card.assets):
        raise ValueError("RAW_ASSET_ID_DUPLICATE")
    observed=[]
    modality_spans={"video":[],"audio":[]}
    decoder=_decoder_version()
    with tempfile.TemporaryDirectory(prefix="recap-raw-verify-") as folder:
        for asset in card.assets:
            if asset.source_id!=card.source_id or asset.source_sha256!=card.source_sha256:
                raise ValueError("RAW_ASSET_SOURCE_MISMATCH")
            if (asset.source_range.start<card.requested_range.start or
                asset.source_range.end>card.requested_range.end):
                raise ValueError("RAW_ASSET_RANGE_INVALID")
            expected={"video_frame":"video","video_clip":"video","audio_pcm":"audio","subtitle_sidecar":"subtitle"}
            if expected[asset.kind]!=asset.modality:
                raise ValueError("RAW_MODALITY_KIND_MISMATCH")
            path=_raw_path(root,asset.relative_path)
            if not path.is_file() or path.stat().st_size>64*1024*1024:
                raise ValueError("RAW_ASSET_MISSING_OR_TOO_LARGE")
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=asset.sha256:
                raise ValueError("RAW_ASSET_SHA_MISMATCH")
            if asset.kind=="subtitle_sidecar":
                if (asset.subtitle_origin!="sidecar" or not source.subtitle_path or
                    asset.subtitle_source_sha256!=source.subtitle_fingerprint or
                    content_fingerprint(source.subtitle_path)!=asset.subtitle_source_sha256 or
                    asset.sha256!=asset.subtitle_source_sha256 or path.suffix.lower() not in {".srt",".vtt",".ass"}):
                    raise ValueError("RAW_SUBTITLE_PROVENANCE_INVALID")
                raw.decode("utf-8-sig")
                from .asr import parse_subtitle
                cues=[{"start":cue.start,"end":cue.end,"text":cue.text}
                      for cue in parse_subtitle(path,source.source_id)
                      if cue.start>=asset.source_range.start and cue.end<=asset.source_range.end]
                # Strip file comments/style/metadata and out-of-range captions;
                # exact original bytes stay hash-bound in the audit record.
                consumed=json.dumps({"source_cues":cues},ensure_ascii=False,separators=(",",":")).encode("utf-8")
            else:
                if asset.decoder_version!=decoder:
                    raise ValueError("RAW_DECODER_VERSION_CHANGED_REEXTRACT_REQUIRED")
                suffix={"video_frame":".png","video_clip":".mkv","audio_pcm":".wav"}[asset.kind]
                decoded=Path(folder)/f"asset-{len(observed)}{suffix}"
                _decode_asset(source,asset,card.timebase,decoded)
                if _decoded_digest(path,asset.kind)!=_decoded_digest(decoded,asset.kind):
                    raise ValueError("RAW_ASSET_NOT_SOURCE_CONTENT")
                consumed=_canonical_observer_bytes(decoded,asset.kind)
            if asset.modality in modality_spans:
                modality_spans[asset.modality].extend(_native_coverage(source,asset,path,card.timebase))
            if content_fingerprint(path)!=asset.sha256:
                raise ValueError("RAW_ASSET_CHANGED_DURING_READ")
            observed.append({"evidence_id":card.evidence_id,"asset_id":asset.asset_id,
                "modality":asset.modality,"kind":asset.kind,"source_id":source.source_id,
                "source_range":asset.source_range.model_dump(mode="json"),
                "sample_time":asset.sample_time,"asset_sha256":asset.sha256,
                "sha256":hashlib.sha256(consumed).hexdigest(),"bytes":consumed})
    if content_fingerprint(source.path)!=card.source_sha256:
        raise ValueError("RAW_SOURCE_CHANGED_DURING_VERIFICATION")
    return {"evidence_id":card.evidence_id,"card_hash":fingerprint_json(card.model_dump(mode="json")),
            "assets":observed,"coverage_gaps":[g.model_dump(mode="json") for g in card.coverage_gaps],
            "budget_exhausted":card.budget_exhausted,
            "modality_gaps":{key:[gap.model_dump(mode="json") for gap in interval_coverage(spans,card.requested_range)[1]]
                             for key,spans in modality_spans.items()}}


def create_raw_evidence_card(*, manifest: SourceManifest, source_id: str, source_range: Interval,
    evidence_root: str | Path, include_video=True, include_audio=False,
    sample_times: list[float] | None=None, evidence_id="raw1") -> RawEvidenceCard:
    """Explicit local extraction helper; no overwrite, remote service or model."""
    from .boundary_apply import collect_boundary_timebases
    source=next(s for s in manifest.sources if s.source_id==source_id)
    timebase=collect_boundary_timebases(manifest.model_copy(update={"sources":[source]}))[source_id]
    if source_range.end>source.duration or source_range.end-source_range.start>30:
        raise ValueError("RAW_EXTRACTION_RANGE_OUTSIDE_30_SECOND_BUDGET")
    samples=sample_times or []
    if len(samples)>24 or any(not math.isfinite(t) or not source_range.start<=t<source_range.end for t in samples):
        raise ValueError("RAW_SAMPLING_BUDGET_OR_RANGE_INVALID")
    root=Path(evidence_root).resolve();root.mkdir(parents=True,exist_ok=True)
    directory=Path(tempfile.mkdtemp(prefix="raw-",dir=root))
    decoder=_decoder_version()
    assets=[]
    def asset(kind,modality,suffix,**extra):
        name=f"{kind}-{len(assets)}{suffix}"
        item=RawAsset(asset_id=f"{evidence_id}:{kind}:{len(assets)}",kind=kind,modality=modality,
            relative_path=str((directory/name).relative_to(root)),sha256="0"*64,
            source_id=source_id,source_sha256=source.fingerprint,stream_id="a:0" if modality=="audio" else "v:0",
            source_range=source_range,decoder_version=decoder,**extra)
        _decode_asset(source,item,timebase,directory/name)
        if kind in {"video_clip", "audio_pcm"}:
            _native_coverage(source,item,directory/name,timebase)
        item.sha256=content_fingerprint(directory/name);assets.append(item)
    if include_video:
        asset("video_clip","video",".mkv")
    if include_audio:
        if not source.has_audio:
            raise ValueError("RAW_AUDIO_MODALITY_UNAVAILABLE")
        asset("audio_pcm","audio",".wav")
    rows=_frame_rows(source) if samples else []
    used=set()
    for requested in samples:
        candidates=[(i,int(row["best_effort_timestamp"])) for i,row in enumerate(rows)
            if "best_effort_timestamp" in row and requested<=
            (int(row["best_effort_timestamp"])-timebase.origin_pts)*timebase.numerator/timebase.denominator<source_range.end]
        if not candidates:
            raise ValueError("RAW_SAMPLE_NOT_COVERED")
        index,pts=candidates[0]
        if index in used:
            continue
        used.add(index)
        actual=(pts-timebase.origin_pts)*timebase.numerator/timebase.denominator
        asset("video_frame","video",".png",frame_index=index,source_pts=pts,sample_time=actual)
    if content_fingerprint(source.path)!=source.fingerprint:
        raise ValueError("RAW_SOURCE_CHANGED_DURING_EXTRACTION")
    return RawEvidenceCard(evidence_id=evidence_id,source_id=source_id,source_sha256=source.fingerprint,
        timebase=timebase,requested_range=source_range,assets=assets)


def verify_claim(claim: DerivedClaim, cards: list[RawEvidenceCard], *, manifest: SourceManifest,
    evidence_root: str | Path, observer: Callable | None=None, judge: Callable | None=None,
    reviewer="unconfigured", version="unconfigured") -> ClaimVerification:
    """Two-stage advisory interface. Observer gets raw bytes and neutral targets.

    The observer is never given exact_text, story/events, prior scores or reasons.
    Judge receives the frozen claim and first-stage raw observations, never story
    explanations. Both accept and reject remain advisory; only invalid bindings
    become deterministic BLOCKED.
    """
    claim_hash=fingerprint_json(claim.model_dump(mode="json"))
    hashes={card.evidence_id:fingerprint_json(card.model_dump(mode="json")) for card in cards}
    checks=[];verified=[];observations=[];asset_hashes={}
    result=dict(claim_id=claim.claim_id,claim_revision=claim_hash,generation_revision=claim.generation_revision,
        raw_card_hashes=hashes,raw_asset_hashes=asset_hashes,consumed_asset_hashes={},
        structural_state="accept",advisory_verdict="unknown",
        status="UNKNOWN",observations=observations,observation_input_hash=None,observation_output_hash=None,
        judgment_input_hash=None,judgment_output_hash=None,checks=checks,reason="No semantic reviewer ran",
        reviewer=reviewer,reviewer_version=version)
    try:
        if len(hashes)!=len(cards) or not set(claim.proposed_support_ids)<=set(hashes):
            raise ValueError("CLAIM_EVIDENCE_ID_MISMATCH")
        for card in cards:
            if card.evidence_id not in claim.proposed_support_ids:
                continue
            verified.append(verify_raw_evidence(card,manifest=manifest,evidence_root=evidence_root))
        result["raw_card_hashes"]={row["evidence_id"]:row["card_hash"] for row in verified}
        assets=[asset for row in verified for asset in row["assets"]]
        asset_map={(a["evidence_id"],a["asset_id"]):a for a in assets}
        if len(asset_map)!=len(assets):
            raise ValueError("RAW_GLOBAL_ASSET_ID_COLLISION")
        asset_hashes.update({f'{a["evidence_id"]}/{a["asset_id"]}':a["asset_sha256"] for a in assets})
        result["consumed_asset_hashes"]={f'{a["evidence_id"]}/{a["asset_id"]}':a["sha256"] for a in assets}
    except (ValueError,OSError,RuntimeError,KeyError) as exc:
        result.update(structural_state="reject",status="BLOCKED",reason=str(exc))
        checks.append({"check":"raw_identity_and_content","state":"reject","deterministic":True,"reason":str(exc)})
        return ClaimVerification(**result)
    required=_REQUIRED[claim.claim_type] | set(claim.required_modalities)
    present={a["modality"] for a in assets}
    missing=required-present
    checks.append({"check":"raw_identity_and_content","state":"accept","deterministic":True})
    unknown=[]
    if missing: unknown.append("missing_modalities:"+",".join(sorted(missing)))
    if any(row["coverage_gaps"] for row in verified): unknown.append("raw_coverage_gap")
    if any(row["budget_exhausted"] for row in verified): unknown.append("budget_exhausted")
    if claim.claim_type in {"action","sequence","causality"} and not any(a["kind"]=="video_clip" for a in assets):
        unknown.append("continuous_video_not_observed")
    continuous={"audio"} if "audio" in required else set()
    if claim.claim_type in {"action","sequence","causality","speaker"}:
        continuous.add("video")
    for modality in continuous:
        if any(row["modality_gaps"].get(modality) for row in verified):
            unknown.append(f"independent_{modality}_coverage_gap")
    if not claim.required_nodes:
        unknown.append("required_nodes_not_specified")
    if claim.claim_type=="motivation": unknown.append("internal_motivation_not_directly_observable")
    if observer is None or judge is None:
        result["reason"]="; ".join(unknown or ["No semantic reviewer ran"])
        return ClaimVerification(**result)
    target={"claim_type":claim.claim_type,"required_nodes":claim.required_nodes,
            "required_modalities":sorted(required)}
    # Do not leak caller-controlled evidence/source labels as "neutral" clues.
    # The observer sees opaque IDs; keep the reversible audit map privately.
    from copy import deepcopy
    opaque_assets=[]; opaque_map={}
    evidence_ids={key:f"evidence_{i:04d}" for i,key in enumerate(dict.fromkeys(a["evidence_id"] for a in assets))}
    source_ids={key:f"source_{i:04d}" for i,key in enumerate(dict.fromkeys(a["source_id"] for a in assets))}
    for index,asset in enumerate(assets):
        opaque={**asset,"evidence_id":evidence_ids[asset["evidence_id"]],
                "asset_id":f"asset_{index:04d}","source_id":source_ids[asset["source_id"]]}
        opaque_map[(opaque["evidence_id"],opaque["asset_id"])]=(asset["evidence_id"],asset["asset_id"])
        opaque_assets.append(opaque)
    public_assets=[{key:value for key,value in asset.items() if key!="bytes"} for asset in opaque_assets]
    result["observation_input_hash"]=fingerprint_json({"target":target,"assets":public_assets})
    try:
        raw_observations=observer(deepcopy({"target":target,"assets":opaque_assets}))
    except (ValueError,TypeError,RuntimeError,OSError) as exc:
        result["reason"]=f"Observer unavailable: {exc}"
        return ClaimVerification(**result)
    try:
        observations=[RawObservation.model_validate(row) for row in raw_observations]
        result["observation_output_hash"]=fingerprint_json([row.model_dump(mode="json") for row in observations])
        for observation in observations:
            original=opaque_map.get((observation.evidence_id,observation.asset_id))
            if original is None:
                raise ValueError("OBSERVATION_OPAQUE_ID_UNKNOWN")
            observation.evidence_id,observation.asset_id=original
            asset=asset_map.get((observation.evidence_id,observation.asset_id))
            if not asset or observation.modality!=asset["modality"]:
                raise ValueError("OBSERVATION_ASSET_OR_MODALITY_MISMATCH")
            span=asset["source_range"]
            if not span["start"]<=observation.source_time<span["end"]:
                raise ValueError("OBSERVATION_TIME_OUTSIDE_RAW_ASSET")
            if asset["kind"]=="video_frame" and observation.source_time!=asset["sample_time"]:
                raise ValueError("OBSERVATION_NOT_AT_SAMPLED_FRAME")
    except (ValueError,TypeError) as exc:
        result["reason"]=str(exc)
        checks.append({"check":"reviewer_output","state":"unknown","deterministic":False})
        return ClaimVerification(**result)
    result["observations"]=observations
    observation_payload=[row.model_dump(mode="json") for row in observations]
    judgment_input={"claim":claim.model_dump(mode="json"),"observations":observation_payload}
    result["judgment_input_hash"]=fingerprint_json(judgment_input)
    try:
        judgment=ClaimJudgment.model_validate(judge(deepcopy(judgment_input)))
    except (ValueError,TypeError,RuntimeError,OSError) as exc:
        result["reason"]=f"Judgment unavailable: {exc}"
        return ClaimVerification(**result)
    result["judgment_output_hash"]=fingerprint_json(judgment.model_dump(mode="json"))
    observed_modalities={row.modality for row in observations}
    if not required<=observed_modalities: unknown.append("required_modality_not_observed_by_reviewer")
    if not set(claim.required_nodes)<={row.node for row in observations if row.relation!="insufficient"}:
        unknown.append("required_claim_nodes_not_covered")
    if judgment.state=="accept" and (not observations or any(row.relation!="support" for row in observations)):
        unknown.append("accept_without_consistent_located_support")
    if judgment.state=="reject" and not any(row.relation=="contradict" for row in observations):
        unknown.append("reject_without_located_contradiction")
    verdict="unknown" if unknown else judgment.state
    result.update(advisory_verdict=verdict,status="UNKNOWN" if verdict=="unknown" else "ADVISORY",
                  reason="; ".join(unknown) if unknown else judgment.reason)
    checks.append({"check":"semantic_review","state":verdict,"deterministic":False,"advisory":True,
                   "limitations":judgment.limitations})
    return ClaimVerification(**result)




def verify_boundary_raw_evidence(proposal, cards: list[RawEvidenceCard], *,
    manifest: SourceManifest, evidence_root: str | Path) -> dict[str, Any]:
    """Optional B2 input binding, re-executed by its locked transaction validator.

    Verifies source bytes/content/coverage only, never semantic completeness or
    whether a historical model actually consumed an audio asset.
    """
    from .boundary import proposal_hash
    declared=proposal.raw_evidence_card_hashes
    by_id={card.evidence_id:card for card in cards}
    required=set(proposal.raw_evidence_ids + proposal.audio_evidence_ids)
    if len(by_id)!=len(cards) or set(declared)!=set(by_id) or not required<=set(declared):
        raise ValueError("BOUNDARY_RAW_CARD_SET_MISMATCH")
    receipts={};assets={};covered={"video":[],"audio":[]}
    for eid,card in by_id.items():
        if fingerprint_json(card.model_dump(mode="json"))!=declared[eid]:
            raise ValueError("BOUNDARY_RAW_CARD_HASH_CHANGED")
        if card.source_id!=proposal.source_id or card.source_sha256!=proposal.source_sha256 or card.timebase!=proposal.timebase:
            raise ValueError("BOUNDARY_RAW_SOURCE_OR_TIMEBASE_MISMATCH")
        verified=verify_raw_evidence(card,manifest=manifest,evidence_root=evidence_root)
        if verified["budget_exhausted"] or verified["coverage_gaps"]:
            raise ValueError("BOUNDARY_RAW_COVERAGE_UNKNOWN")
        receipts[eid]=verified["card_hash"]
        assets[eid]={asset["asset_id"]:asset["asset_sha256"] for asset in verified["assets"]}
        for modality in covered:
            # Only independently observed complete card coverage can contribute.
            if not verified["modality_gaps"][modality] and any(a["modality"]==modality for a in verified["assets"]):
                covered[modality].append(card.requested_range)
        if eid in proposal.audio_evidence_ids and not any(a["modality"]=="audio" for a in verified["assets"]):
            raise ValueError("BOUNDARY_AUDIO_CARD_HAS_NO_AUDIO")
    needed={"video"} | ({"audio"} if proposal.must_preserve_source_track else set())
    for modality in needed:
        if interval_coverage(covered[modality],proposal.proposed_range)[1]:
            raise ValueError(f"BOUNDARY_RAW_{modality.upper()}_COVERAGE_UNKNOWN")
    return {"state":"verified_source_bindings","proposal_hash":proposal_hash(proposal),
        "raw_card_hashes":receipts,"raw_asset_hashes":assets,"semantic_advisory":True,
        "historical_model_consumption_verified":False,"qc_upgrade_allowed":False}


def claim_verification_finding(verification: ClaimVerification):
    """QC adapter: semantic accept/reject cannot upgrade or hard-block QC."""
    from .models import QCFinding
    structural_failure=verification.structural_state=="reject"
    return QCFinding(finding_id="claim_"+verification.claim_revision[:16],
        stage="source_verification",severity="error" if structural_failure else "info" if verification.advisory_verdict=="accept" else "warning",
        blocking=structural_failure,deterministic=structural_failure,
        rule_id="raw_source_binding" if structural_failure else "source_claim_advisory",
        message=verification.reason,evidence={"verification":verification.model_dump(mode="json")},
        next_action="Repair source/evidence bindings" if structural_failure else "Review located observations; final rendered AV review remains required")


def main(argv=None):
    parser=argparse.ArgumentParser(description="Verify local raw bindings; absent reviewer remains UNKNOWN")
    sub=parser.add_subparsers(dest="command",required=True)
    command=sub.add_parser("verify-claim")
    command.add_argument("--request",required=True,type=Path)
    args=parser.parse_args(argv)
    request=json.loads(args.request.read_text(encoding="utf-8"))
    report=verify_claim(DerivedClaim.model_validate(request["claim"]),
        [RawEvidenceCard.model_validate(card) for card in request["cards"]],
        manifest=SourceManifest.model_validate(request["manifest"]),evidence_root=request["evidence_root"])
    print(report.model_dump_json(indent=2))
    return 2 if report.status=="BLOCKED" else 0


if __name__=="__main__":
    raise SystemExit(main())
