# V1 raw-source verification and advisory semantics

`raw_evidence.py` provides executable `RawEvidenceCard`, `DerivedClaim` and
`ClaimVerification` contracts. They are separate strict schemas: story graphs,
model scores, generated summaries and unsupported extra fields cannot be passed
as raw cards. Ordinary subtitle text is still an observation with possible errors.

## Native evidence and identity

`create_raw_evidence_card` extracts a local lossless video clip, PCM audio and/or
sampled PNGs from a bound source. It creates a new directory and never overwrites
sources. Initial extraction is limited to 30 source seconds and 24 frame requests.
Actual frame index and demux PTS are stored; no n/fps VFR approximation is used.

`verify_raw_evidence` independently checks full source/asset SHA, current PTS
mapping and decoder version. It re-decodes the exact source frames/video/PCM and
compares decoded pixels, timing and samples. Re-labeling an unrelated image with
a valid SHA fails. Native frame/sample counts must be nonzero. Continuous
video/audio coverage is derived from actual demux PTS/durations and decoded PCM
sample counts, then unioned; a tiny subclip cannot certify a wider requested card
window simply by declaring no gaps. Point samples are not continuous action
coverage. Unsafe paths, symlinks, missing bytes and assets over 64 MiB reject.

Current extraction supports the first video/audio streams and saved subtitle
sidecars whose full bytes match the manifest. Unsupported stream IDs, embedded
subtitles/ASR artifacts, decoder changes and missing clocks require explicit
re-extraction/adaptation; they are not silently promoted to supported inputs.
A clock mapping or decoded-byte match is not a semantic or final-render review.

## Two genuinely separate reviewer inputs

`verify_claim(..., observer=..., judge=...)` first invokes an observation callback
with independently re-decoded, metadata-stripped native content and a fixed neutral target taxonomy.
Caller asset metadata never reaches the observer: PNGs are rebuilt from decoded
RGB pixels, WAVs from PCM samples, FFV1 clips are decoded with all metadata/chapter
copy disabled, and subtitle inputs contain only in-range source cue text/times.
Original full asset hashes remain audit-only; separate consumed-asset hashes bind
the actual bytes delivered to the observer. It receives
neither the claim answer, story graph, event/character claims, generator scores
nor generator reasoning. Evidence/source/asset labels are replaced by opaque
IDs so caller-written names cannot leak the answer. The output is then mapped
back to the original audit IDs and must cite an existing asset, modality and
actual sampled/source time.

Only the second callback receives the exact frozen claim and located raw
observations. Independent input and output hashes bind both stages. Callbacks
must be explicitly provided by an authorized provider adapter; this module never
starts a paid or remote model. Default CLI/API operation has no reviewer and
returns UNKNOWN after deterministic checks. Tests demonstrate that observer
callbacks receive and hash real media bytes, not merely path labels.

Missing modalities, coverage gaps, absent temporal footage, unsupported motives,
missing required nodes, malformed/unlocated observations, exhausted budgets and
unavailable callbacks remain UNKNOWN. Audio is required for tone, dialogue,
speaker, sound and silence questions; subtitles alone cannot certify sarcasm.
Speaker checks also require video. These checks restrict admissible evidence;
they do not automatically establish who spoke or caused a sound.

Model accept AND reject remain ADVISORY. `claim_verification_finding` emits
nonblocking, nondeterministic QC findings for them. Only deterministic source,
range, content or identity failures can produce a blocking binding finding.
There is no route from semantic acceptance to hard QC PASS, and final rendered
visual/audio review is never inherited.

## Boundary integration and CLI

An approved BoundaryProposal may opt into `raw_evidence_card_hashes`. All declared
cards and their exact hashes become part of its approval hash; B2 rechecks raw
content and required continuous coverage under the existing I2 lock before
publication. Its sidecar distinguishes `verified_source_bindings` from
`not_verified`. Shape-only old evidence IDs are explicitly caller-supplied;
neither branch proves historical model consumption or upgrades semantic/QC state.

The standalone command is:

    python -m douyin_film_recap.raw_evidence verify-claim --request request.json

The request contains `claim`, `cards`, `manifest` and `evidence_root`. It prints a
verification record. No configured observer/judge means UNKNOWN, not completed
model review. Exit 2 means deterministic binding failure; exit 0 is not PASS.

21 synthetic tests use locally generated red 32×32 FFV1 video and a sine PCM
track. They test source/asset spoofing, actual byte consumption, separate stages,
opaque labels, partial/empty coverage, missing modalities, container-metadata answer leakage, model verdicts and
approval-bound B2 raw-card integration. They establish software contracts only,
not real-film factuality, performance, aesthetics or release readiness.
