"""Narrow, source-bound local edits using the existing workspace authority.

The snapshot is a compare-and-swap precondition, never a second editable head.
This first entry supports notes/title and analyzed VO visual replacements. Text,
TTS, original boundaries, ordering and protection changes need their own contract.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .workspace import (POINTER, WorkspaceError, commit_generation, digest, member,
                        preflight, read, sha, work_lock)

BOARD = "09_storyboard.json"
MANIFEST = "00_source_manifest.json"
HIGHLIGHTS = "07_highlight_candidates.json"
PLAN = "08_recap_plan.json"
BOUNDARY_RECEIPT = ".receipts/boundary-adoption.json"
LOCAL_FIELDS = frozenset({"title", "notes", "visuals"})
_PROTECTION_KEYS = {"protected", "protection", "protected_fields", "protected_segments",
                    "protected_segment_ids", "protected_ranges", "content_protection", "user_protected",
                    "locked", "locks", "user_modified", "manual_lock", "manual_overrides"}


def _file_identity(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise WorkspaceError("REVISION_BOUND_RESOURCE_UNSAFE")
    return {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}


def _sources(active):
    manifest = read(member(active, MANIFEST))
    result = []
    seen = set()
    for source in manifest.get("sources", []):
        if source["source_id"] in seen:
            raise WorkspaceError("REVISION_DUPLICATE_SOURCE")
        seen.add(source["source_id"])
        identity = _file_identity(source["path"])
        if (source.get("identity_schema") != "sha256-full/2"
                or source["fingerprint"] != identity["sha256"]
                or source.get("size_bytes") not in (None, identity["bytes"])):
            raise WorkspaceError("REVISION_SOURCE_BINDING_CHANGED")
        identity["source_id"] = source["source_id"]
        if source.get("subtitle_path"):
            subtitle = _file_identity(source["subtitle_path"])
            if source.get("subtitle_fingerprint") != subtitle["sha256"]:
                raise WorkspaceError("REVISION_SUBTITLE_BINDING_CHANGED")
            identity["subtitle"] = subtitle
        result.append(identity)
    if not result:
        raise WorkspaceError("REVISION_SOURCE_BINDINGS_REQUIRED")
    return result


def _freeze(active, root):
    paths = sorted(p for p in active.glob("[0-9][0-9]_*.json") if p.is_file())
    paths.extend(p for p in [member(active, ".receipts/config-binding.json"),
                            member(active, BOUNDARY_RECEIPT)] if p.is_file())
    if not (active / BOARD).is_file() or not (active / "state.json").is_file():
        raise WorkspaceError("REVISION_CURRENT_STORYBOARD_REQUIRED")
    board = read(member(active, BOARD))
    audio = [_file_identity(segment["audio_file"]) for segment in board.get("segments", [])
             if segment.get("mode") == "voiceover" and segment.get("audio_file")]
    return {"schema": "film-revision-base/1", "generation": str(active.relative_to(root)),
            "pointer_sha256": sha(root / POINTER) if (root / POINTER).exists() else None,
            "state_sha256": sha(active / "state.json"),
            "artifact_hashes": {str(p.relative_to(active)): sha(p) for p in paths},
            "sources": _sources(active), "audio": audio}


def freeze_revision(work_dir):
    root, _ = preflight(work_dir)
    with work_lock(root):
        root, active = preflight(root)
        return _freeze(active, root)


def assert_revision_base(work_dir, base):
    root, active = preflight(work_dir)
    if not isinstance(base, dict) or base.get("schema") != "film-revision-base/1":
        raise WorkspaceError("REVISION_BASE_REQUIRED")
    if _freeze(active, root) != base:
        raise WorkspaceError("REVISION_BASE_CONFLICT")
    return active


def _protected(value):
    if isinstance(value, dict):
        return any((key in _PROTECTION_KEYS and bool(item)) or _protected(item)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(_protected(item) for item in value)
    return False


def _preserve_unknown(old, new, model):
    """Known models allow extras for compatibility; adopting may not erase them."""
    for key in set(old) - set(model.model_fields):
        if key not in new or old[key] != new[key]:
            raise WorkspaceError(f"REVISION_UNKNOWN_FIELD_CHANGED:{key}")


def _validate_board(old, candidate, scope, *, local):
    from .models import Storyboard, StoryboardSegment, VisualReference

    Storyboard.model_validate(candidate)  # Validate without replacing the raw document.
    _preserve_unknown(old, candidate, Storyboard)
    if old.get("sources") != candidate.get("sources"):
        raise WorkspaceError("REVISION_SOURCE_DOCUMENT_CHANGED")
    before = old.get("segments", [])
    after = candidate.get("segments", [])
    if [s["segment_id"] for s in before] != [s["segment_id"] for s in after]:
        raise WorkspaceError("REVISION_SEGMENT_ORDER_OR_ID_CHANGED")
    allowed_ids = scope.get("segment_ids")
    if (not isinstance(allowed_ids, list) or (local and not allowed_ids)
            or not all(isinstance(value, str) for value in allowed_ids)
            or len(set(allowed_ids)) != len(allowed_ids)):
        raise WorkspaceError("REVISION_EXPLICIT_SEGMENT_SCOPE_REQUIRED")
    if not set(allowed_ids) <= {s["segment_id"] for s in before}:
        raise WorkspaceError("REVISION_UNKNOWN_SEGMENT_SCOPE")
    fields = scope.get("fields", sorted(LOCAL_FIELDS))
    if not isinstance(fields, list) or not all(isinstance(k, str) for k in fields):
        raise WorkspaceError("REVISION_FIELD_SCOPE_INVALID")
    if local and not set(fields) <= LOCAL_FIELDS:
        raise WorkspaceError("REVISION_FIELD_UNSUPPORTED")
    top_before = {k: v for k, v in old.items() if k != "segments"}
    top_after = {k: v for k, v in candidate.items() if k != "segments"}
    if local and top_before != top_after:
        raise WorkspaceError("REVISION_TOP_LEVEL_EDIT_UNSUPPORTED")
    if old != candidate and any(k in _PROTECTION_KEYS and bool(v) for k, v in old.items()):
        raise WorkspaceError("REVISION_PROTECTED_DOCUMENT")
    changed = []
    for previous, current in zip(before, after):
        _preserve_unknown(previous, current, StoryboardSegment)
        changes = {k for k in set(previous) | set(current) if previous.get(k) != current.get(k)}
        if not changes:
            continue
        if previous["segment_id"] not in allowed_ids:
            raise WorkspaceError("REVISION_OUTSIDE_SEGMENT_SCOPE")
        if _protected(previous):
            raise WorkspaceError("REVISION_PROTECTED_SEGMENT")
        if local and not changes <= set(fields):
            raise WorkspaceError("REVISION_FIELD_UNSUPPORTED")
        if "visuals" in changes:
            # Unknown segment-level effects can anchor to the old visual clock.
            # Retaining their JSON alone cannot certify their unchanged meaning.
            if local and (set(previous) - set(StoryboardSegment.model_fields) -
                          {"rendered_file", "rendered_duration_sec"}):
                raise WorkspaceError("REVISION_UNKNOWN_SEGMENT_DEPENDENCY")
            if local and previous["mode"] != "voiceover":
                raise WorkspaceError("REVISION_ORIGINAL_BOUNDARY_REQUIRES_PROPOSAL")
            old_visuals = previous.get("visuals", [])
            new_visuals = current.get("visuals", [])
            # Existing opaque effects may refer to an index/time anchor. Until a
            # typed mapping exists, do not move or remove that unknown behavior.
            domain_fields = set() if local else {"evidence_revision", "source_sha256", "timebase_hash", "unit_lineage"}
            known_fields = set(VisualReference.model_fields) | domain_fields
            opaque_old = [{k: v for k, v in visual.items() if k not in known_fields}
                          for visual in old_visuals]
            opaque_new = [{k: v for k, v in visual.items() if k not in known_fields}
                          for visual in new_visuals]
            if (any(opaque_old) or any(opaque_new)) and (local or opaque_old != opaque_new):
                raise WorkspaceError("REVISION_UNKNOWN_VISUAL_DEPENDENCY")
        changed.append(previous["segment_id"])
    return changed


def _validate_visuals(active, artifacts):
    from .models import (HighlightDocument, SceneAnalysisDocument, SceneIndex,
                         SourceManifest, Storyboard)
    from .visual_evidence import validate_storyboard_visual_evidence

    board = Storyboard.model_validate(artifacts[BOARD])
    manifest = SourceManifest.model_validate(read(active / MANIFEST))
    expected = {source.source_id: source for source in manifest.sources}
    if board.sources != manifest.sources:
        raise WorkspaceError("REVISION_STORYBOARD_MANIFEST_MISMATCH")
    for segment in board.segments:
        for visual in segment.visuals:
            if visual.source_id not in expected or visual.end > expected[visual.source_id].duration:
                raise WorkspaceError("REVISION_VISUAL_SOURCE_RANGE_INVALID")
    validate_storyboard_visual_evidence(board, manifest,
        HighlightDocument.model_validate(artifacts.get(HIGHLIGHTS, read(active / HIGHLIGHTS))),
        SceneIndex.model_validate(read(active / "02_scene_index.json")),
        SceneAnalysisDocument.model_validate(read(active / "03_scene_analysis.json")))


def adopt_revision(work_dir, *, base, artifacts, scope, kind="local", reason="", validator=None,
                   interrupt=None):
    """Adopt a full candidate; domain wrappers must freshly validate boundary proposals.

    The public CLI exposes only ``local``. A boundary wrapper supplies its validator;
    protection, identity and unknown-field preservation are never delegated away.
    """
    root, _ = preflight(work_dir)
    artifacts = deepcopy(artifacts)
    scope = deepcopy(scope)
    if not isinstance(artifacts, dict) or not isinstance(scope, dict):
        raise WorkspaceError("REVISION_CANDIDATE_INVALID")
    if kind == "local":
        if set(artifacts) != {BOARD}:
            raise WorkspaceError("REVISION_LOCAL_MEMBERS_INVALID")
    elif kind == "boundary":
        if set(artifacts) != {HIGHLIGHTS, PLAN, BOARD, BOUNDARY_RECEIPT} or not callable(validator):
            raise WorkspaceError("REVISION_BOUNDARY_VALIDATION_REQUIRED")
    else:
        raise WorkspaceError("REVISION_KIND_UNSUPPORTED")

    def validate(active):
        assert_revision_base(root, base)
        old = read(active / BOARD)
        changed = _validate_board(old, artifacts[BOARD], scope, local=kind == "local")
        if kind == "local" and not changed:
            raise WorkspaceError("REVISION_NO_CHANGES")
        if kind == "boundary":
            from .models import HighlightDocument, RecapPlan
            for name, model in [(HIGHLIGHTS, HighlightDocument), (PLAN, RecapPlan)]:
                previous = read(active / name)
                model.model_validate(artifacts[name])
                _preserve_unknown(previous, artifacts[name], model)
                if previous != artifacts[name] and _protected(previous):
                    raise WorkspaceError("REVISION_PROTECTED_DOCUMENT")
            validator(active, deepcopy(artifacts))
        _validate_visuals(active, artifacts)

    with work_lock(root):
        _, active = preflight(root)
        validate(active)
        replacement = deepcopy(artifacts)
        # Output evidence is bound to previous media. Never carry PASSED into a new
        # generation; preserve it only in the immutable recovery archive.
        replacement[BOARD]["output"] = {}
        for segment in replacement[BOARD]["segments"]:
            segment.pop("rendered_file", None)
            segment.pop("rendered_duration_sec", None)
            segment["status"] = "audio_ready" if segment.get("audio_file") else "planned"
        adopted_hashes = {name: digest(replacement[name]) for name in (HIGHLIGHTS, PLAN, BOARD)
                          if name in replacement}
        if kind == "boundary":
            replacement[BOUNDARY_RECEIPT]["artifact_content_hashes"] = adopted_hashes
            replacement[BOUNDARY_RECEIPT]["status"] = "adopted"
        replacement[".receipts/revision-adoption.json"] = {
            "schema": "film-revision-adoption/1", "kind": kind, "base": base,
            "scope": scope, "reason": reason, "candidate_sha256": digest(artifacts),
            "adopted_artifact_content_hashes": adopted_hashes,
            "qc_status": "NOT_RUN", "semantic_and_av_review_inherited": False}
        return commit_generation(root, replacements=replacement,
            expected_generation=base["generation"], expected_pointer_sha256=base["pointer_sha256"],
            validate=validate, invalidate_from="highlights" if kind == "boundary" else "pre_qc",
            reason=reason, interrupt=interrupt)
