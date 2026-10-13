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
