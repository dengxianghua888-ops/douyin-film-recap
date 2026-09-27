"""Pure host-neutral WorkDocument mapping and conflict-preserving patch preparation.

No editor API is selected here. A concrete adapter must provide an atomic host
compare-and-swap. This module never writes Work SQLite or host projects.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Protocol


SNAPSHOT_SCHEMA = "host-neutral-snapshot/1"
PATCH_SCHEMA = "host-neutral-patch/1"
WORK_SCHEMA = "work-document/1"
SECTIONS = ("sources", "clips", "captions", "audio_tracks", "style_bindings", "notes", "visual_layers")
SINGLETONS = ("clip_order", "caption_style", "evidence_protection")
PLAN_FIELDS = ("fps", "width", "height", "fit", "allow_source_reuse")
WORK_FIELDS = {"schema", "plan", "captions", "caption_style", "audio_tracks", "style_bindings", "notes", "visual_layers", "evidence_protection"}


class BridgeError(ValueError):
    """A stable code with no silent fallback."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise BridgeError(code)


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _work_state(state: dict) -> dict:
    _require(isinstance(state, dict), "WORK_STATE_REQUIRED")
    required = ("work_id", "sequence", "version", "document_sha256", "document")
    _require(all(k in state for k in required), "WORK_STATE_INCOMPLETE")
    _require(isinstance(state["work_id"], str) and bool(state["work_id"]), "WORK_ID_REQUIRED")
    _require(type(state["sequence"]) is int and state["sequence"] > 0, "WORK_SEQUENCE_INVALID")
    doc = state["document"]
    _require(isinstance(doc, dict) and doc.get("schema") == WORK_SCHEMA, "WORK_DOCUMENT_SCHEMA_INVALID")
    _require(_digest(doc) == state["document_sha256"], "WORK_DOCUMENT_HASH_MISMATCH")
    token = _digest({"work_id": state["work_id"], "sequence": state["sequence"], "document_sha256": state["document_sha256"]})
    _require(token == state["version"], "WORK_VERSION_HASH_MISMATCH")
    _require(isinstance(doc.get("plan"), dict) and isinstance(doc["plan"].get("clips"), list)
             and isinstance(doc["plan"].get("sources"), dict), "WORK_PLAN_INVALID")
    for field in ("captions", "audio_tracks", "style_bindings", "notes"):
        _require(isinstance(doc.get(field), dict), "WORK_FIELD_INVALID: " + field)
    _require(not set(doc).difference(WORK_FIELDS), "WORK_FIELD_UNSUPPORTED")
    return state


def _work_ref(state: dict) -> dict:
    return {key: state[key] for key in ("work_id", "sequence", "version", "document_sha256")}


def _projection(doc: dict) -> dict:
    plan = doc["plan"]
    clips = plan["clips"]
    _require(all(isinstance(c, dict) and isinstance(c.get("id"), str) and c["id"] for c in clips), "CLIP_ID_REQUIRED")
    order = [c["id"] for c in clips]
    _require(len(set(order)) == len(order), "DUPLICATE_CLIP_ID")
    return {
        "settings": copy.deepcopy({k: v for k, v in plan.items() if k not in ("clips", "sources")}),
        "sources": copy.deepcopy(plan["sources"]),
        "clips": {c["id"]: copy.deepcopy(c) for c in clips},
        "clip_order": order,
        "captions": copy.deepcopy(doc["captions"]),
        "caption_style": copy.deepcopy(doc["caption_style"]),
        "audio_tracks": copy.deepcopy(doc["audio_tracks"]),
        "style_bindings": copy.deepcopy(doc["style_bindings"]),
        "notes": copy.deepcopy(doc["notes"]),
        "visual_layers": copy.deepcopy(doc.get("visual_layers", {})),
        "evidence_protection": copy.deepcopy(doc.get("evidence_protection")),
        "evidence_protection_present": "evidence_protection" in doc,
        "visual_layers_present": "visual_layers" in doc,
    }


def export_snapshot(state: dict, project_id: str, host_revision: str,
                    previous_snapshot: dict | None = None) -> dict:
    """Map a verified Work state into a neutral host snapshot, retaining native sidecars."""
    state = _work_state(state)
    _require(isinstance(project_id, str) and bool(project_id), "HOST_PROJECT_ID_REQUIRED")
    _require(isinstance(host_revision, str) and bool(host_revision), "HOST_REVISION_REQUIRED")
    sidecar = {"host_opaque": {}, "host_opaque_entities": {}}
    if previous_snapshot is not None:
        _snapshot(previous_snapshot)
        _require(previous_snapshot["project_id"] == project_id, "HOST_PROJECT_CONFLICT")
        _require(previous_snapshot["work_ref"]["work_id"] == state["work_id"], "WORK_ID_CONFLICT")
        imported = import_snapshot(previous_snapshot)
        _require(imported["document_sha256"] == previous_snapshot["work_ref"]["document_sha256"],
                 "HOST_MANUAL_EDIT_REQUIRES_PATCH")
        sidecar = {k: copy.deepcopy(previous_snapshot[k]) for k in sidecar}
    mapped = _projection(state["document"])
    return {"schema": SNAPSHOT_SCHEMA, "project_id": project_id, "host_revision": host_revision,
            "work_ref": _work_ref(state), "mapped": mapped, **sidecar,
            "mapped_document_sha256": state["document_sha256"], "sync_status": "MATCHED_WORK"}


def _snapshot(snapshot: dict) -> dict:
    _require(isinstance(snapshot, dict) and snapshot.get("schema") == SNAPSHOT_SCHEMA, "HOST_SNAPSHOT_SCHEMA_INVALID")
    for key in ("project_id", "host_revision", "work_ref", "mapped", "host_opaque", "host_opaque_entities"):
        _require(key in snapshot, "HOST_SNAPSHOT_INCOMPLETE: " + key)
    _require(isinstance(snapshot["project_id"], str) and bool(snapshot["project_id"]), "HOST_PROJECT_ID_REQUIRED")
    _require(isinstance(snapshot["host_revision"], str) and bool(snapshot["host_revision"]), "HOST_REVISION_REQUIRED")
    _require(isinstance(snapshot["host_opaque"], dict) and isinstance(snapshot["host_opaque_entities"], dict), "HOST_OPAQUE_INVALID")
    work_ref = snapshot["work_ref"]
    _require(isinstance(work_ref, dict) and set(work_ref) == {"work_id", "sequence", "version", "document_sha256"},
             "HOST_WORK_REF_INVALID")
    mapped = snapshot["mapped"]
    _require(isinstance(mapped, dict), "HOST_MAPPING_INVALID")
    for key in ("settings",) + SECTIONS:
        _require(isinstance(mapped.get(key), dict), "HOST_MAPPING_INVALID: " + key)
    _require(isinstance(mapped.get("clip_order"), list), "HOST_CLIP_ORDER_INVALID")
    _require(set(mapped["clip_order"]) == set(mapped["clips"]) and len(mapped["clip_order"]) == len(mapped["clips"]), "HOST_CLIP_ORDER_CONFLICT")
    return snapshot


def import_snapshot(snapshot: dict) -> dict:
    """Return a WorkDocument candidate plus all host-only state, without adoption."""
    _snapshot(snapshot)
    m = snapshot["mapped"]
    plan = copy.deepcopy(m["settings"])
    plan["sources"] = copy.deepcopy(m["sources"])
    plan["clips"] = [copy.deepcopy(m["clips"][cid]) for cid in m["clip_order"]]
    doc = {"schema": WORK_SCHEMA, "plan": plan, "captions": copy.deepcopy(m["captions"]),
           "caption_style": copy.deepcopy(m["caption_style"]), "audio_tracks": copy.deepcopy(m["audio_tracks"]),
           "style_bindings": copy.deepcopy(m["style_bindings"]), "notes": copy.deepcopy(m["notes"])}
    if m.get("visual_layers_present", False):
        doc["visual_layers"] = copy.deepcopy(m["visual_layers"])
    if m.get("evidence_protection_present", False):
        doc["evidence_protection"] = copy.deepcopy(m["evidence_protection"])
    unsupported = []
    if snapshot["host_opaque"]:
        unsupported.append("host_opaque")
    for section, entities in snapshot["host_opaque_entities"].items():
        if entities:
            unsupported.append("host_opaque_entities." + section)
    return {"document": doc, "document_sha256": _digest(doc), "expected_work_ref": copy.deepcopy(snapshot["work_ref"]),
            "host_revision": snapshot["host_revision"], "unsupported_host_fields": unsupported,
            "host_opaque": copy.deepcopy(snapshot["host_opaque"]),
            "host_opaque_entities": copy.deepcopy(snapshot["host_opaque_entities"]),
            "complete_host_roundtrip": not unsupported}


def _scope(scope: dict) -> dict:
    _require(isinstance(scope, dict), "BRIDGE_SCOPE_REQUIRED")
    allowed = set(SECTIONS) | set(SINGLETONS) | {"settings"}
    _require(set(scope) == allowed, "BRIDGE_SCOPE_KEYS_INVALID")
    for key in SECTIONS + ("settings",):
        values = scope[key]
        _require(isinstance(values, list) and all(isinstance(v, str) and v for v in values)
                 and len(values) == len(set(values)), "BRIDGE_SCOPE_IDS_INVALID: " + key)
    for key in SINGLETONS:
        _require(type(scope[key]) is bool, "BRIDGE_SCOPE_FLAG_INVALID: " + key)
    _require(set(scope["settings"]) <= set(PLAN_FIELDS), "BRIDGE_SETTING_UNSUPPORTED")
    return scope


def _ops(base: dict, target: dict, scope: dict) -> list[dict]:
    ops = []
    for section in ("settings",) + SECTIONS:
        before, after = base[section], target[section]
        changed = set(before) | set(after)
        changed = {key for key in changed if key not in before or key not in after or before[key] != after[key]}
        _require(changed <= set(scope[section]), "BRIDGE_OUTSIDE_SCOPE: " + section)
        for key in sorted(changed):
            present = key in before
            ops.append({"section": section, "id": key, "before_exists": present,
                        "before_sha256": _digest(before[key]) if present else None,
                        "after_exists": key in after, "value": copy.deepcopy(after[key]) if key in after else None})
    for section in SINGLETONS:
        if base[section] != target[section]:
            _require(scope[section], "BRIDGE_OUTSIDE_SCOPE: " + section)
            ops.append({"section": section, "before_exists": True, "before_sha256": _digest(base[section]),
                        "after_exists": True, "value": copy.deepcopy(target[section])})
    for key in ("evidence_protection_present", "visual_layers_present"):
        if base[key] != target[key]:
            raise BridgeError("BRIDGE_MEMBERSHIP_CHANGE_REQUIRES_EXPLICIT_WORK_OPERATION: " + key)
    return ops


def prepare_patch(base_snapshot: dict, target_work_state: dict, scope: dict) -> dict:
    """Freeze a Work-to-host patch. Target/manual changes are CAS checked at application."""
    _snapshot(base_snapshot)
    target_work_state = _work_state(target_work_state)
    scope = _scope(scope)
    base_ref = base_snapshot["work_ref"]
    _require(base_ref["work_id"] == target_work_state["work_id"], "WORK_ID_CONFLICT")
    _require(target_work_state["sequence"] > base_ref["sequence"], "WORK_TARGET_NOT_NEWER")
    base_doc = import_snapshot(base_snapshot)
    _require(base_doc["document_sha256"] == base_ref["document_sha256"], "BASE_HOST_WORK_DIVERGED")
    target = _projection(target_work_state["document"])
    ops = _ops(base_snapshot["mapped"], target, scope)
    return {"schema": PATCH_SCHEMA, "project_id": base_snapshot["project_id"],
            "expected_host_revision": base_snapshot["host_revision"], "expected_work_ref": copy.deepcopy(base_ref),
            "target_work_ref": _work_ref(target_work_state), "scope": copy.deepcopy(scope), "operations": ops,
            "unsupported_host_fields": base_doc["unsupported_host_fields"],
            "host_write_status": "PREPARED_ONLY_REQUIRES_ADAPTER_CAS"}


def rebase_patch(patch: dict, latest_snapshot: dict) -> dict:
    """Allow a disjoint host edit to advance revision while target preconditions remain unchanged."""
    _snapshot(latest_snapshot)
    _require(patch.get("schema") == PATCH_SCHEMA, "HOST_PATCH_SCHEMA_INVALID")
    _require(latest_snapshot["project_id"] == patch["project_id"], "HOST_PROJECT_CONFLICT")
    _require(latest_snapshot["work_ref"] == patch["expected_work_ref"], "WORK_BASE_CONFLICT")
    for op in patch["operations"]:
        section = op["section"]
        if "id" in op:
            container = latest_snapshot["mapped"][section]
            exists = op["id"] in container
            value = container.get(op["id"])
        else:
            exists = True
            value = latest_snapshot["mapped"][section]
        _require(exists == op["before_exists"] and (not exists or _digest(value) == op["before_sha256"]),
                 "HOST_TARGET_MANUAL_EDIT_CONFLICT: " + section + ("." + op["id"] if "id" in op else ""))
    rebound = copy.deepcopy(patch)
    rebound["expected_host_revision"] = latest_snapshot["host_revision"]
    return rebound


def apply_patch_preview(current_snapshot: dict, patch: dict, new_host_revision: str) -> dict:
    """Pure preview. An adapter still must atomically CAS and persist the change."""
    _snapshot(current_snapshot)
    _require(current_snapshot["host_revision"] == patch.get("expected_host_revision"), "HOST_REVISION_CONFLICT")
    rebase_patch(patch, current_snapshot)
    _require(isinstance(new_host_revision, str) and bool(new_host_revision)
             and new_host_revision != current_snapshot["host_revision"], "NEW_HOST_REVISION_REQUIRED")
    candidate = copy.deepcopy(current_snapshot)
    for op in patch["operations"]:
        if "id" in op:
            section = candidate["mapped"][op["section"]]
            if op["after_exists"]:
                section[op["id"]] = copy.deepcopy(op["value"])
            else:
                section.pop(op["id"], None)
        else:
            candidate["mapped"][op["section"]] = copy.deepcopy(op["value"])
    candidate["host_revision"] = new_host_revision
    candidate["work_ref"] = copy.deepcopy(patch["target_work_ref"])
    mapped_digest = import_snapshot(candidate)["document_sha256"]
    candidate["mapped_document_sha256"] = mapped_digest
    candidate["sync_status"] = "MATCHED_WORK" if mapped_digest == patch["target_work_ref"]["document_sha256"] else "HOST_DIVERGED_REVIEW_REQUIRED"
    return candidate


def prepare_import(snapshot: dict, current_work_state: dict) -> dict:
    """Expose host manual edits as a Work candidate; never commit them automatically."""
    _snapshot(snapshot)
    current = _work_state(current_work_state)
    _require(snapshot["work_ref"] == _work_ref(current), "WORK_BASE_CONFLICT")
    imported = import_snapshot(snapshot)
    base = _projection(current["document"])
    changed = {}
    for section in ("settings",) + SECTIONS:
        a, b = base[section], snapshot["mapped"][section]
        changed[section] = sorted(k for k in set(a) | set(b) if k not in a or k not in b or a[k] != b[k])
    for section in SINGLETONS:
        changed[section] = base[section] != snapshot["mapped"][section]
    _require(base["evidence_protection_present"] == snapshot["mapped"]["evidence_protection_present"],
             "PROTECTION_MEMBERSHIP_REQUIRES_SET_PROTECTION")
    _require(not changed["evidence_protection"], "PROTECTION_CHANGE_REQUIRES_SET_PROTECTION")
    _require(set(changed["settings"]) <= set(PLAN_FIELDS), "WORK_SETTING_UNSUPPORTED")
    clip_ids = set(changed["clips"])
    if changed["clip_order"]:
        clip_ids.update(base["clip_order"])
        clip_ids.update(snapshot["mapped"]["clip_order"])
    for source_id in changed["sources"]:
        clip_ids.update(c["id"] for c in current["document"]["plan"]["clips"] if c["source_id"] == source_id)
        clip_ids.update(c["id"] for c in imported["document"]["plan"]["clips"] if c["source_id"] == source_id)
    scope = {"clip_ids": sorted(clip_ids), "source_ids": changed["sources"],
             "caption_ids": changed["captions"], "audio_ids": changed["audio_tracks"],
             "style_keys": changed["style_bindings"], "note_keys": changed["notes"],
             "visual_ids": changed["visual_layers"], "output_fields": changed["settings"],
             "caption_style": changed["caption_style"], "freeze_positions": [], "freeze_duration": False,
             "evidence_mapping": False}
    return {"schema": "host-work-import-proposal/1", "host_revision": snapshot["host_revision"],
            "expected_work_version": current["version"], "changed": changed,
            "candidate": {"schema": "work-candidate/1", "base_version": current["version"],
                          "base_document_sha256": current["document_sha256"],
                          "document": imported["document"], "scope": scope},
            "unsupported_host_fields": imported["unsupported_host_fields"],
            "status": "REVIEW_REQUIRED_NO_WORK_COMMIT"}


class HostAdapter(Protocol):
    """Concrete editor adapter slot; implementation must make CAS atomic in host state."""

    def read_snapshot(self, project_id: str) -> dict: ...

    def compare_and_swap(self, project_id: str, expected_revision: str,
                         patch: dict, expected_entity_hashes: list[dict]) -> dict: ...


def execute(request: dict, directory=None, tools=None) -> dict:
    """Expose the pure bridge through the shared runtime request contract."""
    from editing_runtime import exact_keys, require

    action = request.get("action")
    fields = {
        "export": ["work_state", "project_id", "host_revision"],
        "import": ["snapshot"],
        "prepare-patch": ["base_snapshot", "target_work_state", "scope"],
        "rebase-patch": ["patch", "latest_snapshot"],
        "preview-patch": ["current_snapshot", "patch", "new_host_revision"],
        "prepare-import": ["snapshot", "current_work_state"],
    }
    require(action in fields, "HOST_BRIDGE_ACTION_UNSUPPORTED")
    optional = ["previous_snapshot"] if action == "export" else []
    exact_keys(request, ["operation", "action"] + fields[action] + optional,
               ["operation", "action"] + fields[action])
    if action == "export":
        return export_snapshot(request["work_state"], request["project_id"],
                               request["host_revision"], request.get("previous_snapshot"))
    if action == "import":
        return import_snapshot(request["snapshot"])
    if action == "prepare-patch":
        return prepare_patch(request["base_snapshot"], request["target_work_state"], request["scope"])
    if action == "rebase-patch":
        return rebase_patch(request["patch"], request["latest_snapshot"])
    if action == "preview-patch":
        return apply_patch_preview(request["current_snapshot"], request["patch"], request["new_host_revision"])
    return prepare_import(request["snapshot"], request["current_work_state"])
