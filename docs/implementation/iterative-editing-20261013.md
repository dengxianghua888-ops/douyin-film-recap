# Iterative editing implementation — 2026-10-13

Baseline: `a204591627b0b059079f46041f258721f327da99`.
Branch: `feat/iterative-editing-20261013`. No merge or deployment is authorized.

This implements the delivered optimization proposal in dependency order, with a
separate commit and focused verification for each item. Design references are
summarized here rather than introducing another project authority.

| Item | Deliverable | Status |
| --- | --- | --- |
| I0 | Pure derived render plan, dependency keys, expected/realized timing | Pending |
| I1 | Opt-in whole-segment AV cache, verified bytes, full finalization/QC | Pending |
| I2 | Protected local revision/render-only entry using existing generation | Pending |
| B1 | Immutable cross-window boundary proposals and validation | Pending |
| B2 | Consistent 07/08/09 adoption with stale-reference isolation | Pending |
| R1 | Same-budget query reranking above existing Beat-stratified baseline | Pending |
| V1 | Independently bound raw evidence, advisory model decisions | Pending |
| X1 | Restricted one-way OTIO exchange package and explicit losses | Pending |
| X2 | Saved-snapshot three-way readback proposals, no active-host writes | Pending |

## Non-negotiable boundaries

- `09_storyboard.json` remains film render authority. Derived plans, caches and
  exchange files are not editable authorities. Reuse workspace generation; no
  third revision ledger.
- Retain source protection, existing workspace locks, pre/post QC and UNKNOWN
  remote-send guards. Cache hits never inherit content approval.
- I1 caches entire segment AV only; full-frame finalization, captions, loudness,
  preview and QC still run. Existing global `_segment_key` is not a reuse key.
- Distinguish planned timing from realized media. Descendant keys without verified
  artifacts remain provisional. Preserve local/global clocks.
- Ordinary candidate budget is 160 by default and already Beat-stratified;
  selected highlights are appended separately. Compare equal actual budgets.
- Boundary proposals bind revision, source SHA and timebase. Old evidence must
  remain distinguishable; 07/08/09 cannot silently diverge.
- Model accept and reject are both advisory. Missing evidence is not a pass.
- Without host atomic compare-and-swap, export new files or read saved snapshots;
  never overwrite an active host project.

## Verification and evidence

Use unit/property-style fixtures and deterministic synthetic FFmpeg media.
Report focused and full regressions separately. Verify each published remote SHA
and final exact-HEAD CI to terminal state. Real-film/model quality and actual-host
round-trip remain NOT_RUN until their own authorized inputs and tools exist;
those gaps do not block independent deterministic engineering.

No user media, user computer, unrelated repository, paid model call, credential
creation, or new dependency is part of this implementation. Dependencies, if
needed later, require official-source and license review first. Existing network
restrictions are respected.

## Results

Initial planning commit only. Implementation and media/host acceptance are not
claimed by this document. Subsequent item commits update this table and add exact
checks and limitations.
