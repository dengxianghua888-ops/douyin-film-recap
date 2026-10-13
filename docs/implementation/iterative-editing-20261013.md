# Iterative editing implementation — 2026-10-13

Baseline: `a204591627b0b059079f46041f258721f327da99`.
Branch: `feat/iterative-editing-20261013`. No merge or deployment is authorized.

This implements the delivered optimization proposal in dependency order, with a
separate commit and focused verification for each item. Design references are
summarized here rather than introducing another project authority.

| Item | Deliverable | Status |
| --- | --- | --- |
| I0 | Pure derived render plan, dependency keys, expected/realized timing | Implemented; 20 local fixtures and exact-commit full CI pass |
| I1 | Opt-in whole-segment AV cache, verified bytes, full finalization/QC | Implemented; synthetic FFmpeg and safety fixtures pass; full CI pending |
| I2 | Protected local revision/render-only entry using existing generation | Implemented; 20 local fixtures plus existing regressions pass; full CI pending |
| B1 | Immutable cross-window boundary proposals and validation | Implemented; 11 local synthetic contract tests pass; full CI pending |
| B2 | Consistent 07/08/09 adoption with stale-reference isolation | Implemented; 12 local adoption fixtures pass; full CI pending |
| R1 | Same-budget query reranking above existing Beat-stratified baseline | Implemented; 14 retrieval + 3 config fixtures pass; full CI pending |
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

### I0 verification

Pure planner: 20 standard-library unittest fixtures passed locally. CLI read-only/stale-authority fixtures added; full pytest and CLI execution await CI because local pytest/typer are unavailable. Python compileall passed. No media/QC or performance claim.

### I1 verification

Opt-in remains disabled by default. Synthetic FFmpeg checks cover full/cold/warm
decoded audio/video equality, selective shot invalidation, mixed original/voice,
reordering, same-key parallel rendering, cross-generation reuse, corruption,
malformed manifests, path safety and no-clobber publication. Planner regressions
remain green. Additional focused checks cover historical disabled-config identity,
bounded realized clocks in QC, and recovery references before a stage is marked
passed. The full pipeline still finalizes and reruns QC. Default-off legacy config
identity is preserved. Real-film/human listening, production speedups and broad
platform/FPS acceptance are NOT_RUN. The verified opt-in toolchain collector is
currently Linux/ldd; unsupported toolchains fail closed while the default renderer
is unchanged. I0 exact-SHA CI: e4759d429106f4f11ad0657f095e08dcb617bcd7, run38373950716,
all three jobs succeeded.

### I2 verification

The minimum local scope is segment notes/title and already-analyzed VO visual
replacement. Text/TTS, independent subtitle-display overrides, reorder and arbitrary
original-range edits remain unsupported by this entry. Original boundary changes
use B2. Twenty focused local tests passed; existing resumed-evidence and interruption
regressions passed. CLI fixtures await full CI. Adoption preserves archives, rejects
stale sources/heads/unknown or protected modifications, and switches one existing
generation pointer. render-current retains both QC gates, forbids new remote sends,
and leaves UNKNOWN unresolved. Ordinary run cannot silently regenerate adopted
work; explicit from-stage or render-current is required. No true host CAS is claimed.

### B1 verification

Eleven local fixtures pass: immutable source/revision/timebase bindings, cross-window coverage, missing-middle UNKNOWN, legacy bool UNKNOWN, detector provenance and stale-reference rejection. Semantic and audio observation IDs alone are shape-level advisory records, not proof that raw audio was consumed. Real-film boundary-quality acceptance is NOT_RUN.

### B2 verification

Twelve local tests pass, including actual generation adoption, stale retry rejection, preserved archived Storyboard bytes, quote/cue/event/reveal reconciliation, VO subspan preservation and independent source PTS probing. The apply-boundary CLI obtains current clocks from bound source bytes rather than trusting the proposal clock. A changed selected set or incompatible protected/manual edits requires a separate editorial revision. Full original pre/post QC remains required after adoption.

### R1 verification

R0 remains default. R1 uses derived Beat/event query text, constrained lexical
ranking and bounded exploration while retaining the separate highlight append
policy. Fourteen retrieval and three config tests pass, including per-Beat
knowledge limits, same ordinary-count envelope, actual pretty-printed writer-pool
UTF-8 bytes, short-row budget counterexamples and explicit uncovered Beats.
Instrumented token comparison is supported by an injected counter; production
provider-token equality, total-machine-cost equality and real-film quality remain
UNKNOWN/NOT_RUN. A retrieved candidate does not become truth or narrow the full
manual evidence index. Default config identity is preserved. I1 and I2 exact-commit
full CI both succeeded (runs38376556294 and38376804026).
