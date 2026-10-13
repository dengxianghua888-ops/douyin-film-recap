# Restricted OTIO exchange (X1)

This opt-in exporter derives a **cut skeleton** from the current film Storyboard.
`09_storyboard.json` remains the sole film render authority. There is no new
project ledger, writable OTIO head, host integration, or implicit Work migration.

## Entry

```bash
python -m douyin_film_recap.otio_exchange \
  --work-dir ./work/project --output-dir ./exports/cuts-001 \
  --fps 30 --width 160 --height 90 --captions-json ./captions.json
```

The output path must not exist. Captions are an explicit list of
`caption_id`, `start`, `end`, `text`; times may be decimal seconds, `"num/den"`,
or `{ "numerator": 1, "denominator": 30 }`. They may cross cuts. Without this
list the package reports absent caption mapping and writes an empty SRT; it
does not invent subtitle timings from narration text. Existing `build_cues`
output can be supplied by a caller with independently allocated caption IDs.

Python integration:

- `export_otio_package(work_dir, destination, *, profile, media_facts=None,
  captions=(), identity_map=None, reference_render=None)` holds the existing
  workspace lock, freezes current generation + exact Storyboard bytes + source
  manifest binding, then creates an independent package.
- With no `media_facts`, installed ffprobe reads every frame timestamp and audio
  sample count. Matching header frame rates alone do not establish CFR. The
  source SHA is checked before and after this scan and during verified copying.
- `compile_cut_projection(...)` is a pure function for already frozen inputs.
  It uses the existing film `resolved_visual_spans` and duration resolver,
  preserves exact supplied rational/decimal times, and refuses new quantization.
  Its hand-supplied media facts are explicitly reported as unprobed.
- `export_frozen_storyboard(...)` writes a supplied frozen snapshot into a new
  package. The caller must establish the authority binding; it does not adopt it.
- `verify_package(path)` verifies every declared member SHA/size and rejects
  added members, missing members, symlinks, and unsafe paths.

## Supported subset and limitations

The fixed native JSON subset uses Timeline.1, Stack.1, Track.1, Clip.1,
ExternalReference.1, Gap.1, TimeRange.1 and RationalTime.1. Source references are
relative paths to independent SHA-verified copies, never network URLs or links.
One video track and separate original/narration audio tracks contain exact 1×
ranges and gaps. Audio gaps/ranges retain sample clocks, not rounded video ticks.

Requirements: CFR; common frame rate and source/output dimensions; zero media
start time; first/only video and audio stream; mono or stereo audio; exact frame
and sample alignment. VFR, retiming, mixed frame rates, nonzero starts, effects,
transitions, overlays, nonzero gain and layout changes are rejected. This is
intentionally narrower than the local renderer. Render processing such as its
fades and normalization is listed as unrepresented. Baked-segment compatibility
export is deferred, not silently substituted.

Video track audio routing is host-specific. The package explicitly requests
separate audio tracks, but **no actual host has yet verified that importing video
clips does not also duplicate their source audio**. The loss/capability reports
make this unknown visible. Likewise sidecar dimensions are not proof that a host
sets a vertical project profile. No render-equivalence claim is made.

A source ID colliding with the reserved `narration:<segment_id>` resource
namespace is rejected. Each video occurrence has a distinct stable ID, including
repeated identical source windows. Its paired original-audio occurrence uses
`original:<video-instance-id>`; all generated and explicit IDs are checked for
collisions. Explicit `clip_instance_id` and `audio_instance_id` extensions are
honored. Legacy IDs are allocated once into the identity map. Reuse that map for
subsequent exports in the same branch. Legacy visual edits without explicit IDs
cannot be guessed by file name, current order, text, or timecode; they are
rejected as ambiguous. Segment reorder with unchanged visuals retains IDs.

## Package and evidence

The new directory contains timeline.otio, captions.srt, caption-map.json,
media-manifest.json, identity-map.json, export-binding.json, projection.json,
opaque.json, original storyboard.snapshot.json, capability-report.json,
loss-report.json, and checksums.json. Reference render copying is optional and
reported as copied, not validated. Unknown fields survive in original bytes and
opaque sidecars; preservation does not mean they execute or remain time-correct.

`checksums.json` is written last with COMPLETE. Failed exports leave diagnostic
bytes without a COMPLETE marker. Package checksums are content-integrity checks,
not a cryptographic trust signature or hostile-process isolation. Source media,
Storyboard, state and active host projects are never overwritten. No host write
API exists, because no real host CAS has been established.

Five evidence levels remain separate: serialization, actual host import, saved
reopen, rendered equivalence, reversible readback. The last four remain NOT_RUN;
the runtime exporter still reports per-export official parser evidence as NOT_RUN
because it does not invoke the parser. A separate pinned development/CI suite
checks representative packages with the official parser and its native JSON
roundtrip; see [parser acceptance](otio-parser-acceptance.md). Those tests do not
change host, rendered-equivalence or per-export evidence flags.

## Format/permission provenance

The serializer was independently implemented against the pinned upstream native
sample format, not copied from Kdenlive/MLT code:

- [OTIO v0.17.0 native example](https://github.com/AcademySoftwareFoundation/OpenTimelineIO/blob/v0.17.0/tests/sample_data/clip_example.otio)
- [OTIO v0.17.0 Apache-2.0 license](https://github.com/AcademySoftwareFoundation/OpenTimelineIO/blob/v0.17.0/LICENSE.txt)

No third-party OTIO implementation or fixture is vendored. The runtime exporter
keeps no OTIO dependency. The optional dev extra pins the official OTIO 0.18.1
distribution for isolated parser acceptance tests, with license and package
provenance documented separately. No local install was attempted in the restricted
cloud workspace; existing CI performs its normal dev installation. User media,
paid APIs and the user's Mac remain outside these synthetic tests.

Local test command (no pytest installation required):

```bash
PYTHONPATH=src python -m unittest discover -s tests -p test_otio_exchange_contract.py -v
```
