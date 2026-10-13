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
