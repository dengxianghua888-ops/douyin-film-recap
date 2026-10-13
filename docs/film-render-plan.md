# Derived film render plan (I0)

`09_storyboard.json` remains the sole film render authority. `compile_render_plan`
compiles that snapshot without filesystem/network access, subprocesses, mutation,
TTS, rendering or QC adoption. `collect_render_inputs` is a separate read-only
adapter that hashes complete local inputs and identifies the FFmpeg toolchain.

The planner accepts source identities keyed by source ID and audio identities
keyed by segment ID. Source SHA and known size must match the storyboard. Source
paths, unrelated sources, titles, notes, segment order and global placement do
not enter the local whole-segment AV key. Voice bytes, consumed source intervals,
audio ownership behavior, fades, layout and relevant encoding settings do.
Existing `resolved_visual_spans` remains the source-range resolver. Field
inventories classify every current segment/render option. Unknown options or an
unverified toolchain make segment keys provisional, preventing cache adoption.

Ordered assembly includes actual artifact SHA and complete supplied media
contracts once those artifacts are verified. Before that, descendant keys are
explicitly provisional, never promises of hits. `reuse_candidate` only means an
unchanged key relative to a supplied earlier plan. It is not a verified cache hit.

Expected clocks use rational seconds and cumulative nearest-half-up frame/sample
boundaries. Realized clocks require verified frame counts, sample counts and FPS;
frame-grid placements must remain within one output frame of both segment and
cumulative expected durations. This shadow policy never trims speech or pads a
storyboard silently. Actual decode/PTS/encoder-delay validation belongs to the
cache/media verifier, not a pure planner.

The first implementation always retains whole-film concat, finalization (including
loudness and final CFR), captions, preview and full QC. Notes/evidence changes can
leave media keys equal but always change review binding. No old PASSED result is
inherited. Font-dependent finalization stays provisional until actual resolution;
font name or path alone never establishes reusable burned-caption pixels.

I0 does not modify the original render execution path. Pure regression tests run
with `python -m unittest discover -s tests -p test_render_plan.py` in the film
package with `src` on PYTHONPATH. Synthetic/unit evidence is not real-film content,
audio listening, quality, or performance validation. The public config currently
accepts integer FPS; rational-clock tests exercise the derived compiler's clock
math without claiming new accepted production FPS configuration.

## Opt-in whole-segment cache (I1)

Set `render.incremental_cache: true` explicitly to use the verified experimental
path. The default is false, including when ordinary `runtime.cache` is true.
Without that setting the original full renderer path is retained. Enabling this
option does not bypass pre-QC, post-QC, remote-send authorization or the existing
workspace lock. It cannot initiate TTS/model requests or adopt editorial changes.

Each attempt freezes independently copied source/voice bytes after validating
full SHA/size against the storyboard. Rendered segments consume those snapshots,
not mutable source paths. Equal keys within an attempt use singleflight and
recheck after the first producer completes. Segment keys do not use the legacy
attempt-wide `_segment_key`. Currently toolchain verification identifies Linux
FFmpeg/ffprobe binaries, version/build output, transitive `ldd` library bytes and
renderer implementation bytes. Unresolved/static/non-Linux dependency discovery
is explicitly unverified and blocks the opt-in path; the default full path stays
available. This is a conservative portability limitation, not a media fallback.

The shared disposable cache is under the canonical existing workspace root,
across validated generations. It is neither a project head nor a recovery source
for editorial decisions. `render_plan.json` and `render_receipt.json` are separate
attempt-owned audit artifacts; recovery should retain those references, not copy
the whole regenerable cache. No eviction or user-file deletion is implemented.

A reusable entry binds semantic key, renderer/toolchain identity, exact consumed
source identities, voice dependencies, parameter digest, actual artifact SHA/size
and media contract. Validation measures all decoded video/audio frames and audio
packets, enforces local monotonic CFR video and continuous audio PTS, and runs a
complete FFmpeg decode with error escalation. The contract records both decoded
samples and packet-presentation samples, encoder skip delay and trailing padding.
Decoded tail padding is not counted as editorial duration. Both segment and
cumulative realized frame placements remain within one output frame of expected
clocks; concat frame count/PTS are independently checked against that realized
map with the same bounded shadow tolerance. Violations block this attempt rather
than silently trimming dialogue, padding footage, or changing render strategy.
Caption and EDL placement use the realized map. Final concat, whole-film loudness,
subtitle generation/burning, final CFR encoding and preview still execute.

Every cache read is materialized as an exclusive independent attempt copy and
re-hashed, probed and fully decoded before adoption. Symlink parents, symlink
objects, manifest path traversal and linked cache artifacts are rejected.
Existing output files are never overwritten. Publishing writes/fsyncs a unique
independent object and a pending manifest before atomically linking the immutable
COMPLETE manifest with no-clobber semantics. Concurrent writers can publish
separate verified entries for the same key; no winner is overwritten. Interrupted
or corrupt artifacts remain non-adoptable and do not replace old output. There is
no GC, so live readers cannot race eviction. This protects ordinary process and
filesystem failures; it does not claim isolation from a hostile same-user process.

Receipts report executed/reused segment counts, actual rendering FFmpeg calls,
actual verification decode/probe calls (including rejected candidates), wall time,
artifact identities and reason codes. They explicitly do not inherit QC. A new
attempt always receives a fresh review-evidence path. Cache correctness or byte
equality is not an aesthetic/content/listening review or production performance
claim. Synthetic regression tests cover decoded full/cold/warm equivalence,
original/voice alternation, a single changed shot, reorder, cross-generation
reuse, identical-key parallel VO, corruption, invalid manifests/symlinks,
independent copies, interrupted publication and concurrent immutable publication.
Real-film, human listening, broad rational-FPS/VFR and platform coverage remain
NOT_RUN; the feature stays default-off pending that evidence.
