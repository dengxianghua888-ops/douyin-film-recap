# Iterative editing implementation — 2026-10-13

Baseline: `a204591627b0b059079f46041f258721f327da99`.
Branch: `feat/iterative-editing-20261013`. No merge or deployment is authorized.

This implements the delivered optimization proposal in dependency order, with a
separate commit and focused verification for each item. Design references are
summarized here rather than introducing another project authority.

| Item | Deliverable | Status |
| --- | --- | --- |
| I0 | Pure derived render plan, dependency keys, expected/realized timing | Implemented; 20 local fixtures and exact-commit full CI pass |
| I1 | Opt-in whole-segment AV cache, verified bytes, full finalization/QC | Implemented; synthetic FFmpeg and safety fixtures pass; full CI pass |
| I2 | Protected local revision/render-only and targeted narration entry | Implemented; 20 local revision + 15 narration tests pass; full CI pass |
| B1 | Immutable cross-window boundary proposals and validation | Implemented; 11 local synthetic contract tests pass; full CI pass |
| B2 | Consistent 07/08/09 adoption with stale-reference isolation | Implemented; 12 local adoption fixtures pass; full CI pass |
| R1 | Same-budget query reranking above existing Beat-stratified baseline | Implemented; 14 retrieval + 3 config fixtures pass; full CI pass |
| V1 | Independently bound raw evidence, advisory model decisions | Implemented; 21 generated-media fixtures pass; real-model quality NOT_RUN |
| X1 | Restricted one-way OTIO exchange package and explicit losses | Implemented; 8 local fixtures pass; 5 official-parser tests pass in CI; actual host acceptance NOT_RUN |
| X2 | Saved-snapshot three-way readback proposals, no active-host writes | Implemented; 20 local readback tests pass; real-host round-trip NOT_RUN |

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
creation is part of this implementation. The sole new dependency is the dev-only
official opentimelineio==0.18.1 pin, with upstream Apache-2.0/NOTICE review and
actual remote CI installation. No local installation or network restriction
workaround was used.

## Results

The nine bounded implementation items below are delivered as contracts, CLI or
module entry points, and deterministic fixtures. This is not acceptance of every
future capability in the 30-page proposal. The final code commit
`4ca8c356ae9f9a9e73b69bf6955c1e0a5fdec770` passed all three jobs in
[CI 38379433404](https://github.com/dengxianghua888-ops/douyin-film-recap/actions/runs/38379433404).
The subsequent documentation-only commit must also be checked at its own exact SHA;
that terminal receipt is reported with delivery rather than claiming it in advance.

### I0 verification

Pure planner: 20 standard-library unittest fixtures passed locally. CLI read-only/stale-authority fixtures added; full pytest and CLI fixtures subsequently passed in remote CI; local pytest/typer are unavailable. Python compileall passed. No media/QC or performance claim.

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
replacement. This original entry does not perform Text/TTS; the separate targeted narration
entry below now does. Independent subtitle-display overrides, reorder and arbitrary
original-range edits remain unsupported by this entry. Original boundary changes
use B2. Twenty focused local tests passed; existing resumed-evidence and interruption
regressions passed. CLI fixtures subsequently passed in full CI. Adoption preserves archives, rejects
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

### X1 verification

Eight local fixtures pass, including synthetic FFmpeg source/VO media and automatic
full-frame ffprobe facts. A restricted one-way package contains frozen Storyboard,
source/media hashes, occurrence identities, OTIO cuts, caption sidecars, capabilities,
loss reports and opaque extensions. It writes a new destination only. Unsupported
retiming/layout/effects/timebases are rejected or explicitly classified, never
silently promoted to a native editable equivalent. Five official OTIO 0.18.1 parser/read-write-read fixtures subsequently passed in
remote CI; see the package parser-acceptance document for the actual JUnit receipt.
Actual host import/save/reopen/render acceptance remains NOT_RUN; this is not a
verified Kdenlive profile. The parser dependency is dev-only; no local dependency
was installed.

### X2 verification

Twenty local saved-snapshot tests pass: hash-sealed snapshots, three-way proposals,
missing/duplicate occurrence identity, same-field and timing conflicts, protected
caption/document edits, opaque source timing dependencies, resource drift/relinking,
caption IDs and live-file DIVERGED detection. The snapshot proposal includes an I2
base token but does not invoke adoption or overwrite any host. It does not claim
real-time bidirectional sync or actual-host round-trip acceptance. The actual-host acceptance gap recorded for X1 still applies; official native-parser
fixtures have passed remotely.

### V1 verification

Twenty-one local generated-media tests pass, including full source redecoding and
pixel/PCM verification, real observer byte consumption, independent coverage and
modality gaps, answer-blind observations, neutral opaque labels, separate observation
and judgment hashes, and advisory accept/reject. B2 can optionally declare approved
raw-card hashes; required cards are reverified under the existing adoption lock.
Absent raw cards are explicitly not_verified, and neither verified bindings nor
model judgments certify semantic correctness or upgrade final-render QC. Real-model
quality, film evidence recall and human AV review remain NOT_RUN. B1/B2/R1/X1/X2
exact-commit full CI succeeded before this integration.

V1 metadata isolation: observer bytes are independently re-decoded canonical media, not caller containers. Audit asset hashes and consumed-byte hashes are separate; PNG text metadata and subtitle comments cannot leak the proposed answer through the raw-input boundary. The corresponding concrete counterexample now passes.

### I2 targeted narration follow-through

The initial narrow I2 scope is extended by a separate exact-text narration plan
and explicit execution entry. Fifteen focused tests pass, including real guarded
fake-provider transport, target-only generation, unchanged VO bytes/fields, request
budget zero, old/new UNKNOWN records, reason-only/rebase retry protection, cache
replay after interruption, source/head drift and explicit render continuation.
A real synthetic-media fixture uses actual generated MP3, ffprobe, incremental
render and post-QC: the changed VO segment executes, the unchanged VO segment is
reused, and longer audio moves later captions on the realized timeline. Semantic
pre-QC is explicitly synthetic DEGRADED; this is not real-film semantic or human
listening acceptance. No real provider was contacted or paid.

The exact requested text is never silently rewritten. Insufficient existing visual
coverage blocks adoption and retains generated audio; automatic new visuals and
independent subtitle-display override remain outside this contract. Planning is
read-only. Execution requires explicit remote authorization or an exact matching
saved grant; UNKNOWN cannot be retried by changing cosmetic plan fields. The
render-current entry still forbids new remote requests. Optional narration --render
continues existing QC/render stages within its explicit remaining request budget.
Adopted-but-render-blocked state is preserved with an explicit resume route.

## Delivery and acceptance matrix

“Implemented” means the bounded code/contract and deterministic regression scope,
not real-film editorial acceptance or a complete general-purpose NLE integration.

| Area | Delivered and verified | Unverified, restricted or deferred |
| --- | --- | --- |
| I0 | Pure derived plan, keys, expected/realized timing, CLI and fixtures | No independent media-quality or performance claim |
| I1 | Entire-segment AV reuse, full finalization and QC, generated FFmpeg equivalence/invalidation | Default OFF; opt-in verified toolchain Linux/ldd only; real-film listening, speedup, broad platform/FPS and actual power-loss recovery NOT_RUN |
| I2 | Protected revisions plus exact-text narration plan/apply, guarded fake-provider target-only regeneration, actual MP3/ffprobe/render/post-QC fixture | Real-provider TTS and real-film semantic QC/listening NOT_RUN; synthetic pre-QC explicitly DEGRADED; insufficient visual coverage blocks adoption; arbitrary reorder/subtitle-display overrides unsupported |
| B1/B2 | Source/revision/timebase-bound cross-window proposals, consistent 07/08/09 application and old-reference isolation | Real-film boundary-quality/human acceptance NOT_RUN; incompatible selected-set changes require separate editorial revision |
| R1 | Optional lexical reranking/exploration, Beat limits, ordinary-count and actual serialized-byte bounds, separate highlights | R0 remains default; provider-token parity, total compute cost and real-film quality UNKNOWN/NOT_RUN |
| V1 | Independently re-decoded raw byte interfaces and optional B2 bindings; advisory accept/reject; fail-closed evidence gaps | Real-model observation/decision accuracy, recall and human AV review NOT_RUN; never upgrades QC or semantic truth |
| X1 | Restricted source-size CFR, 1x cuts package; hashes/IDs/loss reporting; official 0.18.1 parser fixtures PASS | Actual NLE import/reopen/render NOT_RUN; no verified Kdenlive profile; unsupported effects/layout/retiming rejected or explicitly classified; no per-export parser certification |
| X2 | Saved snapshots, three-way field proposals, stale/ambiguous/conflict detection | No active-host writes or adopted roundtrip; actual host CAS absent; real-host roundtrip NOT_RUN |
| I3/I4 and wider future work | Explicitly deferred, not claimed by these nine implementation rows | Finer-grained incremental layers, broader host adapters/CAS, arbitrary timeline editing and wider effect/media support need their own contracts and acceptance |

External acceptance prerequisites are missing only for their corresponding
experiments: authorized representative films and human review; separately authorized
real model/provider runs and budgets; actual host environment and its safe save/CAS
contract. None of those were replaced by fabricated results. Deterministic code,
synthetic media, fake transport, CLI and official-parser regressions were still run.
No confirmed implementation blocker remained after the independent safety review.

### Published implementation checkpoints

Each SHA was independently published and remote-ref checked. CI run numbers below
are completed success, not queued checks. The final code run includes all items.

| Checkpoint | Commit | Full CI run |
| --- | --- | --- |
| Plan | 0f18328353634283ea4daaff3910495ac4a4107a | 38373002196 |
| I0 | e4759d429106f4f11ad0657f095e08dcb617bcd7 | 38373950716 |
| I1 | 6a5391f30fc3a5fd417c9eadac6b4b01dfe596ce | 38376556294 |
| I2 protected revision | ba7f9be0a8f581043148e7b1d7370840c03c40ec | 38376804026 |
| B1 | 125435ff714f5c88caa32aecc8bf414dce9fe1ef | 38376960115 |
| B2 | 822c7259687b3e7693d38910f4d7e19cddb0d71d | 38377235669 |
| R1 | a77964ae86883adc104805ea1b68f7924cb4ab08 | 38377407817 |
| X1 | f49e3ca11cf82e868c3d555b46ec4ba6c123178d | 38377664934 |
| X2 | d1ce51be711ced2e4967b79c5d57ed8690d85036 | 38377814151 |
| Official OTIO parser | f317db6d2d2915bd96457174a639c595bf3f1750 | 38378974343 |
| V1 | 60e3b519a2fe9236958e3b16dfd3ad2ea1108901 | 38379120487 |
| I2 narration follow-through | 4ca8c356ae9f9a9e73b69bf6955c1e0a5fdec770 | 38379433404 |

Independent final local review ran 155 combined fixtures, followed by all 15
latest narration tests; all passed. These overlapping totals are not added as
unique test counts. Root structure/skill validation and diff checks also passed.
The full dev environment and CLI/parser suites ran in remote CI; restricted local
package availability is not represented as full local regression success.
