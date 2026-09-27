# Host-neutral Work bridge v1

Implementation: `runtime/host_bridge.py`. It is a pure Python mapping and patch-preparation module. It does not select a target editor, write Work SQLite, access an editor API, or claim an NLE project round trip.

## Snapshot

`export_snapshot(work_state, project_id, host_revision, previous_snapshot=None)` accepts a verified `work-version read` state. The module independently checks `work_id`, `sequence`, canonical document digest and version token. It maps:

- `plan.sources`, clip IDs and `clip_order`, plus output settings;
- captions and `caption_style`;
- `audio_tracks`, `style_bindings`, notes;
- optional `visual_layers` and `evidence_protection` as Work fields that must survive round trip.

The result is `host-neutral-snapshot/1` with an opaque `host_revision`, `work_ref`, `mapped_document_sha256`, `host_opaque` and `host_opaque_entities`. An editor adapter owns the concrete conversion between its project model and this snapshot. Native-only effects, tracks, keyframes, bins and editor state must be stored in the opaque sidecars with stable IDs; nonempty sidecars are returned as `unsupported_host_fields`. They are never silently copied into a WorkDocument or discarded during a targeted patch. Unknown native fields cannot be called Work-supported or publishable. `export_snapshot` refuses to replace a previous snapshot containing mapped manual edits; use a scoped patch or import proposal.

`import_snapshot(snapshot)` reconstructs a WorkDocument candidate and returns all native sidecars, the source `work_ref`, host revision and a complete-roundtrip flag. This is mapping only; the existing Work runtime remains responsible for media/source validation and any Work commit.

## Work → host patch

`prepare_patch(base_snapshot, target_work_state, scope)` requires a later verified Work version, a matching base Work document digest and explicit allowed IDs. Scope keys are exactly `settings`, `sources`, `clips`, `clip_order`, `captions`, `caption_style`, `audio_tracks`, `style_bindings`, `notes`, `visual_layers`, `evidence_protection`. ID sections and `settings` are lists; the other keys are booleans. Settings are limited to `fps`, `width`, `height`, `fit`, `allow_source_reuse`. Changing Work field membership such as optional `visual_layers` or `evidence_protection` needs an explicit Work operation upstream; no ordinary patch promotes it silently.

Each operation records the target field, existence, prior canonical SHA-256, and proposed value. `rebase_patch(patch, latest_snapshot)` can advance the expected host revision only when every target field still matches its prior hash. A change to an unrelated host field is preserved; a manual edit to a targeted field returns `HOST_TARGET_MANUAL_EDIT_CONFLICT`. `apply_patch_preview` builds an in-memory candidate after revision and target checks. It never persists. When unrelated mapped host fields differ from the target Work document, the candidate is marked `HOST_DIVERGED_REVIEW_REQUIRED`, while the manual values remain intact.

Concrete adapter slot: `HostAdapter.read_snapshot(project_id)` and `HostAdapter.compare_and_swap(project_id, expected_revision, patch, expected_entity_hashes)`. The adapter must perform one atomic host-side CAS of the project revision and target entity hashes, preserve opaque sidecars, assign the new host revision and re-read persisted state. A pure preview or successful API return is not host acceptance. If the target editor lacks CAS, the adapter must stop on concurrent changes and require review instead of blind overwrite.

## Host → Work import

`prepare_import(snapshot, current_work_state)` requires the snapshot's `work_ref` to match the current SQLite state. It emits a `work-candidate/1` bundle with an explicit scope and `REVIEW_REQUIRED_NO_WORK_COMMIT`. Host manual changes in supported mapped fields appear in the candidate; untouched fields stay from the snapshot. Native-only fields remain in the sidecars and are listed as unsupported. Protection membership or declaration changes must use the existing `work-version set-protection` decision path. The caller must run `timeline-revise`/Work validation, inspect invalidated reviews and use `work-version commit` with its `expected_version`; a host revision must also be rechecked before that commit. Any failed CAS retains both states for reconciliation.

## Limits

Style bindings are metadata, not automatic effects. This bridge makes no claim of complete NLE feature fidelity, media relink success, waveform or frame accuracy, real manual edit identity, or target host acceptance. Actual adapter implementation and integrated validation are intentionally separate.
