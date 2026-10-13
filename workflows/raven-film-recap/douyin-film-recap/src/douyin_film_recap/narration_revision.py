"""Targeted exact-text narration replacement; preparation never sends or adopts.

Only explicitly targeted VO is synthesized. Existing generation/CAS, TTS media
primitives and send guards remain authoritative; this is not a second ledger.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import uuid

from .config import AppConfig
from .models import StoryboardSegment
from .pipeline import FilmRecapPipeline, StageBlocked
from .revision import (BOARD, NARRATION_RECEIPT, _validate_board, _validate_visuals,
                       adopt_revision, assert_revision_base, validate_narration_fields)
from .send_guard import SendBlocked, send_session
from .tts import (_CACHED_AUDIO_FIELDS, _fit_audio_timing, _generate_segment_audio,
                  _restore_segment_cache, _segment_cache_key)
from .utils import content_fingerprint, read_json, write_json
from .workspace import WorkspaceError, atomic, digest, member, now, preflight, read, work_lock

PLAN_SCHEMA = "film-narration-revision-plan/1"


def prepare_narration_revision(work_dir, *, base, edits, reason=""):
    """Return a deterministic reviewable pending plan, without changing files."""
    root, _ = preflight(work_dir)
    with work_lock(root):
        active = assert_revision_base(root, base)
        if not member(active, ".receipts/config-binding.json").is_file():
            raise WorkspaceError("NARRATION_BOUND_CONFIG_RECEIPT_REQUIRED")
        if not isinstance(edits, dict) or not edits:
            raise WorkspaceError("NARRATION_EDITS_REQUIRED")
        if any(not isinstance(key, str) or not isinstance(text, str) or not text.strip()
               for key, text in edits.items()):
            raise WorkspaceError("NARRATION_NONEMPTY_TEXT_REQUIRED")
        old = read(member(active, BOARD))
        candidate = deepcopy(old)
        ids = {row["segment_id"] for row in old["segments"]}
        if not set(edits) <= ids:
            raise WorkspaceError("NARRATION_TARGET_UNKNOWN")
        changed = []
        for segment in candidate["segments"]:
            identifier = segment["segment_id"]
            if identifier not in edits:
                continue
            if segment["mode"] != "voiceover":
                raise WorkspaceError("NARRATION_VOICEOVER_TARGET_REQUIRED")
            if segment["text"] == edits[identifier]:
                raise WorkspaceError("NARRATION_TEXT_UNCHANGED")
            changed.append({"segment_id": identifier, "old_text": segment["text"],
                            "new_text": edits[identifier], "old_audio_file": segment.get("audio_file"),
                            "old_duration_sec": segment.get("audio_duration_sec"),
                            "visual_coverage_sec": sum(v["end"] - v["start"] for v in segment["visuals"])})
            segment["text"] = edits[identifier]
        scope = {"segment_ids": sorted(edits)}
        _validate_board(old, candidate, scope, local=False)
        validate_narration_fields(old, candidate, scope)
        _validate_visuals(active, {BOARD: candidate})
        result = {"schema": PLAN_SCHEMA, "status": "PENDING_TTS", "base": deepcopy(base),
                  "edits": dict(edits), "scope": scope, "reason": reason,
                  "targets": changed, "candidate_storyboard": candidate,
                  "text_policy": "exact; no automatic rewrite", "remote_requests_sent": 0,
                  "unchanged_voiceover_policy": "preserve existing fields and audio bytes",
                  "required_stages": ["targeted_tts", "pre_qc", "render", "post_qc", "delivery"],
                  "qc_status": "NOT_RUN", "render_status": "NOT_RUN"}
        result["plan_sha256"] = digest(result)
        return result


def _checked_plan(root, plan):
    if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA:
        raise WorkspaceError("NARRATION_PLAN_INVALID")
    fresh = prepare_narration_revision(root, base=plan.get("base"), edits=plan.get("edits"),
                                       reason=plan.get("reason", ""))
    if fresh != plan:
        raise WorkspaceError("NARRATION_PLAN_CHANGED_OR_STALE")
    return fresh


def _exact_pipeline(root, plan, config, on_update):
    active = assert_revision_base(root, plan["base"])
    receipt = read(member(active, ".receipts/config-binding.json"))
    prior = AppConfig.model_validate(receipt.get("config", {}))
    prior.format.__pydantic_fields_set__ = set(receipt.get("explicit_format_fields", []))
    if prior.fingerprint() != config.fingerprint():
        raise WorkspaceError("NARRATION_CONFIG_CHANGE_REQUIRES_NEW_PLAN")
    current = FilmRecapPipeline.from_current(work_dir=root, config=config, on_update=on_update)
    assert_revision_base(root, plan["base"])
    return current


def _check_unresolved_tts(root, segment, config):
    # Older pipeline TTS scopes also remain authoritative. A new entry point or
    # plan must not re-submit the same unresolved provider payload under a new key.
    payload = {"text": segment.text, "voice": config.tts.voice, "rate": config.tts.rate,
               "pitch": config.tts.pitch, "volume": config.tts.volume, "boundary": "WordBoundary"}
    identity = digest(payload)
    for path in member(root, ".remote-intents").glob("*.json"):
        previous = read(member(root, str(path.relative_to(root))))
        if (previous.get("kind") == "edge_tts" and previous.get("payload_sha256") == identity
                and previous.get("status") not in {"SUCCEEDED", "NOT_SUBMITTED_CONFIRMED"}):
            raise SendBlocked(f"SEND_OUTCOME_UNKNOWN: matching TTS payload {path.stem}; reconcile before resubmitting")


def execute_narration_revision(work_dir, *, plan, config, allow_remote=False,
                               max_remote_requests=None, render=False, on_update=None):
    """Synthesize targeted VO, atomically adopt, optionally perform normal QC/render.

    A persisted grant is reusable only for this exact plan and provider binding.
    Successful audio can be replayed without a new grant. UNKNOWN is never retried.
    """
    if max_remote_requests is not None and (type(max_remote_requests) is not int or max_remote_requests < 0):
        raise WorkspaceError("NARRATION_REQUEST_LIMIT_INVALID")
    root, _ = preflight(work_dir)
    with work_lock(root):
        plan = _checked_plan(root, plan)
        pipeline = _exact_pipeline(root, plan, config, on_update)
        effective = pipeline._effective_tts_config()
        grant_path = member(root, ".remote-authorization.json")
        grant = None
        if allow_remote:
            grant = {"schema": "film-remote-authorization/1", "id": uuid.uuid4().hex,
                     "binding": pipeline.binding, "remote_policy": pipeline.remote_policy,
                     "stages": ["tts"], "narration_plan_sha256": plan["plan_sha256"],
                     "max_requests": max_remote_requests, "request_limit_is_billing_cap": False}
            atomic(grant_path, grant)
        elif grant_path.is_file():
            previous = read(grant_path)
            if (previous.get("schema") == "film-remote-authorization/1"
                    and previous.get("binding") == pipeline.binding
                    and previous.get("remote_policy") == pipeline.remote_policy
                    and previous.get("narration_plan_sha256") == plan["plan_sha256"]
                    and previous.get("stages") == ["tts"]):
                grant = previous
        raw_candidate = deepcopy(plan["candidate_storyboard"])
        targets = set(plan["scope"]["segment_ids"])
        audio_root = member(root, f".narration-audio/{plan['plan_sha256']}")
        audio_records = []
        try:
            sent = 0
            for raw in raw_candidate["segments"]:
                if raw["segment_id"] not in targets:
                    continue
                segment = StoryboardSegment.model_validate(raw)
                request_key = _segment_cache_key(segment, effective)
                cache_path = member(audio_root, f"cache/{request_key}.json")
                hit = False
                if cache_path.is_file():
                    cached = read_json(cache_path)
                    if (cached.get("request_fingerprint") != request_key
                            or cached.get("revision_plan_sha256") != plan["plan_sha256"]
                            or cached.get("segment", {}).get("text") != segment.text):
                        raise WorkspaceError("NARRATION_AUDIO_CACHE_BINDING_CHANGED")
                    hit = _restore_segment_cache(segment, cache_path)
                if not hit:
                    _check_unresolved_tts(root, segment, effective)
                    # Request identity depends only on this target and actual
                    # transmitted text/voice parameters, never cosmetic plan
                    # reason, a generation hash, other targets or visual timing.
                    # Exact-plan authorization remains separate below.
                    scope = {"stage": "narration_tts", "segment_id": segment.segment_id,
                        "stage_inputs": digest({"provider": effective.tts.provider, "text": segment.text,
                                                "edge_tts": pipeline.remote_policy["edge_tts"]}),
                        "remote_policy": {"edge_tts": pipeline.remote_policy["edge_tts"]}}
                    remaining = None if max_remote_requests is None else max_remote_requests - sent
                    with send_session(root, scope, authorized=bool(grant), max_requests=remaining, grant=grant) as sends:
                        _generate_segment_audio(segment, member(audio_root, request_key), effective)
                    sent += sends.sent
                    visual_duration = sum(v.end - v.start for v in segment.visuals)
                    _fit_audio_timing(segment, desired_duration=min(visual_duration, segment.planned_duration_sec),
                                      min_speed=effective.tts.min_speedup, max_speed=effective.tts.max_speedup)
                    segment.planned_duration_sec = float(segment.audio_duration_sec or 0)
                    write_json(cache_path, {"request_fingerprint": request_key,
                        "revision_plan_sha256": plan["plan_sha256"],
                        "audio_fingerprint": content_fingerprint(segment.audio_file),
                        "segment": {key: getattr(segment, key) for key in _CACHED_AUDIO_FIELDS}})
                visual_duration = sum(v.end - v.start for v in segment.visuals)
                if (not segment.audio_duration_sec or segment.audio_duration_sec > visual_duration + 1e-9):
                    raise WorkspaceError(f"NARRATION_VISUAL_COVERAGE_REQUIRED:{segment.segment_id}")
                if segment.text != plan["edits"][segment.segment_id]:
                    raise WorkspaceError("NARRATION_EXACT_TEXT_CHANGED")
                # Merge only intended text/audio fields into raw source JSON;
                # Pydantic defaults must not alter unrelated authored fields.
                for key in _CACHED_AUDIO_FIELDS:
                    raw[key] = getattr(segment, key)
                audio_records.append({"segment_id": segment.segment_id,
                    "audio_file": segment.audio_file, "sha256": content_fingerprint(segment.audio_file),
                    "duration_sec": segment.audio_duration_sec, "cache_hit": hit})
            receipt = {"schema": "film-narration-revision/1", "status": "prepared",
                "plan_sha256": plan["plan_sha256"], "base": plan["base"], "targets": audio_records,
                "new_remote_requests": sent, "text_policy": plan["text_policy"],
                "qc_status": "NOT_RUN", "render_status": "NOT_RUN",
                "invalidated": ["output_time_map", "subtitles", "pre_qc", "render", "post_qc", "delivery"]}
            artifacts = {BOARD: raw_candidate, NARRATION_RECEIPT: receipt}

            def validate(active, candidate):
                _checked_plan(root, plan)
                if candidate != artifacts:
                    raise WorkspaceError("NARRATION_CANDIDATE_CHANGED")
                for audio in audio_records:
                    path = Path(audio["audio_file"])
                    if (not path.is_relative_to(audio_root) or path.is_symlink()
                            or content_fingerprint(path) != audio["sha256"]):
                        raise WorkspaceError("NARRATION_NEW_AUDIO_CHANGED")

            result = adopt_revision(root, base=plan["base"], artifacts=artifacts,
                scope=plan["scope"], kind="narration", reason=plan["reason"], validator=validate)
        except BaseException as exc:
            try:
                atomic(member(root, f".receipts/narration-failures/{plan['plan_sha256']}-{uuid.uuid4().hex}.json"),
                       {"schema": "film-narration-failure/1", "plan_sha256": plan["plan_sha256"], "at": now(),
                        "error": {"code": type(exc).__name__, "message": str(exc)},
                        "authority_unchanged_unless_pointer_committed": True})
            except BaseException as persistence_error:
                exc.add_note(f"Could not persist narration failure: {persistence_error}")
            raise
        result.update(narration_plan_sha256=plan["plan_sha256"], targets=audio_records,
                      new_remote_requests=sent, targeted_tts_requests=sent,
                      qc_render_requests=0, render_status="NOT_RUN")
        if render:
            current = FilmRecapPipeline.from_current(work_dir=root, config=config, on_update=on_update)
            remaining = None if max_remote_requests is None else max_remote_requests - sent
            def request_count():
                return sum(len(read(path).get("send_attempts", []))
                           for path in member(root, ".remote-intents").glob("*.json"))
            before = request_count()
            try:
                if allow_remote:
                    delivery = current.run(from_stage="pre_qc", allow_remote=True,
                                           max_remote_requests=remaining)
                else:
                    # Cached target audio does not migrate an unrelated broad
                    # legacy grant to fresh semantic QC for this changed text.
                    delivery = current.render_only()
                pre_status = read(current.paths["pre_qc"])["status"]
                post_status = read(current.paths["post_qc"])["status"]
                result.update(delivery_report=str(delivery), render_status="EXECUTED",
                    pre_qc_status=pre_status, post_qc_status=post_status,
                    qc_status="DEGRADED" if "DEGRADED" in (pre_status, post_status) else "PASSED")
            except Exception as exc:
                # TTS adoption has already committed. Preserve that fact and give
                # callers a resumable current generation rather than implying rollback.
                result.update(status="ADOPTED_RENDER_BLOCKED" if isinstance(exc, StageBlocked) else "ADOPTED_RENDER_FAILED",
                    render_status="BLOCKED" if isinstance(exc, StageBlocked) else "FAILED",
                    qc_status=exc.report.status if isinstance(exc, StageBlocked) else "NOT_RUN",
                    render_error={"code": type(exc).__name__, "message": str(exc)},
                    resume="render-current, or explicit run --from-stage pre_qc when new semantic review is authorized")
            after = request_count()
            result.update(qc_render_requests=after - before, new_remote_requests=sent + after - before)
        return result
