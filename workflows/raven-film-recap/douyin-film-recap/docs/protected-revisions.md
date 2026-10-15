# Protected local revisions (I2 minimum)

`09_storyboard.json` remains the rendering authority. A revision uses the existing
`.film-workspace.json` pointer, `.generations/`, `.migrations/` recovery archives
and work lock. It does not introduce another writable project/revision head.

## Local edit and render

1. `revision-snapshot WORK_DIR` returns the current generation, pointer and state
   hashes, stage artifact hashes, full source/subtitle identities and existing VO
   audio identities. Keep the whole returned object as the proposal's `base`.
2. `revise WORK_DIR --proposal proposal.json` accepts a JSON object with `base`,
   `artifacts`, `scope`, optional `kind: "local"` and optional `reason`.
   `artifacts` maps the literal filename `09_storyboard.json` to the full candidate
   document. `scope` names `segment_ids` and optionally `fields`.
3. `render-current WORK_DIR --config config.yaml` opens the current authored
   generation directly. It runs the existing pre-QC, rendering, post-QC and
   delivery stages. It does not run ingest, analysis, planning or TTS.

The initial local whitelist is segment `notes`, `title` and voiceover `visuals`.
Visual replacements must reference the existing analyzed source-bound evidence.
Segment order and IDs, sources, narration text, audio files, TTS timings and original
boundaries cannot be changed by this local entry. Original boundary proposals use
B2's dedicated validator and coherent 07/08/09 adoption. Display-only subtitle
text overrides, arbitrary audio edits, reorder and retiming are not implemented.

The scope is an edit boundary, not permission to remove protection. Existing
protection is enforced; unknown JSON fields are retained. Local visual edits with
opaque segment/visual dependencies fail closed because retaining an unknown effect's
bytes does not prove its timing remains meaningful.

## Transaction and evidence

The candidate is validated under the existing work lock. The previous bytes are
copied and verified in the recovery archive. A complete private generation is
prepared, then pointer, document, source and audio hashes are checked again before
one pointer replacement publishes it. No sequence of active 07/08/09 replacements
is presented as a transaction. Prior generations and failed private preparations
remain intact. Member files and directory entries are fsynced before publishing;
regression tests inject process interruptions, not physical power loss.

A successful adoption means `ADOPTED` and `qc_status: NOT_RUN`; it does not mean
content, media or final quality passed. Previous output pointers are cleared,
new QC/delivery state is pending, and the archive retains the old output and review
records. Boundary receipt content hashes describe the actual post-cleanup 07/08/09
candidate committed together. New media review must bind to the actual new output.

If a process stops after the pointer changed but before a receipt is returned,
read the current generation again. Reusing the old base is rejected; it cannot
silently adopt the same edit over a newer head. This coordinates cooperating
writers and detects observed manual changes; it is not isolation from a malicious
process with the same filesystem permissions.

## Configuration and remote requests

Normal runs now save a bound resolved-config receipt. `render-current` permits only
render configuration differences from that verified receipt; other settings,
source/subtitle bytes, context and provider binding must remain the same. Older
workspaces without the receipt can bootstrap it only with their exact original
normalized full runtime fingerprint. Render-only configuration changes also use
the atomic generation path.

`render-current` never grants new remote sends or reuses a broad saved remote grant.
An exactly matching successful semantic-QC send intent can replay through the
existing guard. A missing result or an `UNKNOWN` intent cannot be resent. If fresh
semantic review cannot run, the existing QC policy reports the gap as `DEGRADED`
or `BLOCKED`; structural checks do not stand in for semantic or audiovisual review.

Ordinary `run` on an adopted revision requires an explicit `--from-stage` handoff,
or the user should use `render-current`. With an explicit handoff, stages preceding
that point are not regenerated because they happen to be pending. Rendering or
delivery handoffs still start no later than pre-QC, preserving both QC gates.

## Exact-text narration follow-through

The separate `narration-revise-plan` / `narration-revise-apply` entries extend the
minimum local visual-edit entry. They do not widen the `revise` whitelist or the
zero-new-remote `render-current` contract.

- `prepare_narration_revision(work_dir, base=..., edits={segment_id: new_text},
  reason="...")` returns a deterministic `PENDING_TTS` plan without writing files,
  synthesizing, editing the current board or claiming a render. The full plan is
  required for execution; changing a field invalidates it.
- `execute_narration_revision(work_dir, plan=..., config=..., allow_remote=False,
  max_remote_requests=None, render=False)` regenerates only explicitly targeted
  voiceover segments. It retains every non-target narration field and audio byte
  (derived rendered-status/output pointers are invalidated during adoption).
- The new text is exact. There is no automatic rewrite-model call. Existing TTS
  provider and bounded timing adjustment are reused. If the measured new voiceover
  exceeds the existing visual coverage, adoption is blocked; a new visual plan is
  needed. Verified generated audio remains available for safe retry/inspection.
- New TTS sends need explicit authorization or a saved grant for this exact plan,
  source/config/provider binding and scope. A broad old pipeline grant is not
  migrated. Request identity is based on the actual target/text/voice payload,
  independently of cosmetic reason and generation metadata. An unresolved matching
  TTS request, including from the original pipeline, blocks resubmission. Changing
  the reason or rebasing an unrelated edit does not clear `UNKNOWN`.
- Successful targeted audio is hash-checked, the source/base is checked again, and
  exact-text/audio fields are adopted via the same atomic generation switch.
  The old board/audio/output survives in the archive. Output clock, subtitles,
  rendering, pre-QC, post-QC and delivery are invalidated; none inherits `PASSED`.
- Default execution stops at adopted audio with `render_status: NOT_RUN`. Explicit
  `render=True` (CLI `--render`) continues through the existing pre-QC, render,
  post-QC and delivery stages. New semantic-QC calls require the same explicit
  execution authorization and share its remaining local request budget. If that
  continuation blocks, the result retains `ADOPTED_RENDER_BLOCKED`/`FAILED`, the
  current generation and a resume instruction; it does not imply the narration
  adoption rolled back.

Validation is deliberately split. Fake-provider unit tests exercise real durable
send guards, exact target-only mutation, recovery and cue invalidation. One local
FFmpeg integration fixture returns actual synthesized-test MP3 bytes from that fake
provider, measures them with real ffprobe, executes the real incremental renderer,
checks that only the changed AV segment executes while the other is reused, and
runs real post-render QC. Its pre-QC result is explicitly a synthetic `DEGRADED`
fixture; it does not certify story, spoken delivery or real film quality. No remote
provider or paid production work is used by these tests.

### Cleaned debug images across revisions

Copied scene/index references can still name a prior generation's frames or contact
sheets. A later revision inherits their absence only when the current generation's
pinned, verified recovery archive already recorded that same debug path as optional,
and its archived scenes hash matches the current scenes record. The path must belong
to this workspace's original debug directory or an owned generation's debug directory.
Explicit cleanup receipts must still match path and hash; a missing or altered receipt
cannot become a legacy exemption. The separate legacy completed-run absence reason is
preserved without upgrading it to proof of observed cleanup.

This exception applies only to scene debug artifacts and frame/contact-sheet references.
It does not exempt ordinary external files, source media, TTS audio, or newly missing
old-generation files merely because a new cleanup receipt lists them. Regression tests
cover three consecutive revisions, a render-configuration generation change, and these
failure cases; neither scenes metadata nor source evidence hashes are rewritten.

Delivery cleanup preserves this evidence across `revise → render-current → revise`.
If the current generation has no registered local debug targets, it leaves the old
receipt (or legacy lack of a receipt) untouched and does not delete unregistered
directories. When local targets and historical cleanup coexist, only absence facts
validated by the existing inventory/recovery checks are carried into the new receipt;
unrelated receipt entries grant no authority. If historical absence is legacy-only,
cleanup conservatively leaves the current debug files in place because the v1 receipt
cannot record that uncertainty separately without upgrading it to observed cleanup.
Tests exercise two full render/delivery/revision cycles with synthetic gates/media,
repeated cleanup, mixed-generation targets, and a tampered receipt that must still fail.

### Render-current snapshot binding

Pre-QC preparation/checking, rendering and post-QC repair parse and hash the same
initial storyboard bytes before running callbacks. They recheck that byte identity
before rendering, publishing an updated board or accepting a QC report. A detected
manual save preserves the new draft and stops the stale attempt. Repair iterations
advance the binding only to the exact bytes this attempt published, rather than
rehashing a later disk version and treating it as the older in-memory draft. This
covers observed edits during preparation, validation, rendering and QC; the existing
work lock coordinates cooperating writers, not hostile filesystem writers.
