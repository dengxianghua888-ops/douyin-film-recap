# Changelog

## 0.2.0 · 2026-09-20

- Fixed sidecar episode matching, subtitle input invalidation, downstream cache receipts and nested work/source paths.
- Split long shots into bounded analysis windows; preserved original shot provenance.
- Added hook eligibility, evidence-backed visual selection, editorial brief and resolved genre constraints.
- Verified hook use and timing against actually consumed source spans, rejecting unsupported highlight labels.
- Added the distinct 30–90s highlight mode without changing existing duration aliases.
- Added original-cue source timing, word-timing provenance, exact consumed-span EDL and segment TTS caching.
- Bound source identities and final QC evidence; added FPS, codec, subtitle and burn-in validation.
- Added explicit subtitle font loading and blocking checks for missing glyphs reported by libass.
- Separated automated media checks from independent rendered-picture/listening evidence.
- Reorganized both Skill entrypoints around shared creative rules, scoped delivery and editable handoff.
- Added regression tests and explicit benchmark readiness; no claim of a completed real-film quality benchmark.


## 0.1.0 · 2026-08-23

Initial runnable release.

- Added an Agent Skill contract for automatic Douyin-style film and TV recaps.
- Added subtitle-first ingest with local ASR fallback.
- Added scene detection, batched representative-frame extraction and contact sheets.
- Added hierarchical story understanding with character, event and knowledge timelines.
- Added genre-adaptive multi-type high-light recall and VLM reranking.
- Added recap planning, executable Storyboard generation and narration compression.
- Added Edge TTS word boundaries, bounded playback-rate fitting and output-timeline subtitles.
- Added original-audio segments, optional ducked source beds under narration and parallel FFmpeg rendering.
- Added 9:16 safe-fit rendering, EDL output, stage caching, resume and deterministic quality gates.
- Added semantic QC as advisory only, with `PASSED`, `DEGRADED`, and `BLOCKED` delivery states.
- Added schemas, evaluation rubric, installation helper and automated tests.
