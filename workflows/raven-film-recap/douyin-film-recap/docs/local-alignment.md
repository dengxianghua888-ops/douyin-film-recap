# M2: explicit local CTC producer (experimental, disabled by default)

`run-local-alignment` is an actual CPU Wav2Vec2 forward pass followed by an
independently implemented constrained CTC Viterbi alignment. It creates the existing
`film-alignment/1` import artifact; normal pipeline runs do not invoke it, import
PyTorch/Transformers, download anything, or adopt its output automatically. Existing
`asr.alignment.enabled` remains false by default. The offline WhisperX converter is
still supported separately and is not invoked by this producer.

## Preconditions and exact local identity

Provide your own approved, licensed **trained character-vocabulary Wav2Vec2 CTC**
model and authorized audio. The repository distributes neither. A model directory
must contain exactly these runtime files (optionally README.md, LICENSE, LICENSE.txt,
NOTICE):

- config.json: standard `wav2vec2`, no adapters or custom `auto_map`
- preprocessor_config.json: 16000 Hz feature extractor
- vocab.json: one-to-one complete token-to-ID mapping, characters matched exactly
- model.safetensors: complete, unsharded weights

Pickle/bin weights, shards, remote IDs/URLs, symlinks, tokenizer code and extra files
are rejected. The loader uses concrete classes, `local_files_only=True`,
`use_safetensors=True`, `trust_remote_code=False`, CPU and evaluation/inference mode.
Missing/unexpected/mismatched weights reject execution instead of silently using
randomly initialized parameters. No authentication or persistent grants are created.
This restricts the loading path; it is not an OS sandbox. Run third-party libraries
inside your usual network-denied execution environment for defense in depth.

Install the optional libraries separately from the normal workflow. `all` deliberately
does not include `local-alignment` because it is a heavyweight, explicit opt-in:

```sh
python -m pip install '.[local-alignment]'
```

The tested optional versions are torch 2.8.0 (CPU distribution used in engineering
checks), transformers 4.57.1 and safetensors 0.6.2. Use the official PyTorch CPU wheel
index if you require a CPU-only torch installation. Installation installs code, not
acoustic models. Review the model's license and expected language before running it.

Compute the immutable content revision of your reviewed directory, then retain it
with the request. All allowed files are fully hashed, not just names/mtimes:

```sh
python -c 'from pathlib import Path; from douyin_film_recap.local_alignment import model_identity; print(model_identity(Path("/absolute/model")))'
python -m douyin_film_recap run-local-alignment \
  --manifest work/00_source_manifest.json --source-id src_001 \
  --cue-index 3 --cue-index 7 \
  --model-dir /absolute/model --model-sha256 YOUR_REVIEWED_64_HEX_DIGEST \
  --output alignment/src_001.json --cache-dir work/alignment-cache
```

Use the actual active generation manifest. Cue indices are zero-based. Select only
whole original-subtitle cues that will be used as original sound. Each selected cue
must be at most 30 seconds and inside the media duration. There is no full-film
inference or implicit expansion to neighboring cues. FFmpeg extracts/resamples only
those windows to mono 16 kHz; full media bytes are read separately for input identity.
Decode-time format allowlisting limits inputs to WAV/FLAC/MP3/OGG/MOV-family,
Matroska/WebM/AVI/AAC/MPEG/MPEG-TS self-contained media. Concat/HLS/SDP
playlists are rejected even when renamed with a video extension; MOV external
data references and absolute aliases are disabled. Local-file protocols alone would
not bind referenced audio to the source hash.
Output creation is exclusive; source media, subtitles and existing outputs are never
written. Run `validate-alignment`, review the boundaries, and explicitly configure
normal alignment import as described in [alignment-import.md](alignment-import.md).

## Native timing and conservative fallback

Convolution kernel/stride geometry determines frame-cell edges in actual decoded
samples; the original cue start is then added. The producer checks output frame
count and audio-window sample length. It does not map cropped times onto a zero-based
source clock. Repeated labels require an intervening CTC blank. Token spans comprise
only their native character cells; there is no nearest/linear interpolation.

Exact original characters must exist in the model vocabulary. Unknown characters,
punctuation, numbers or case variations are not normalized or invented. Any unknown
character keeps the whole cue estimated. Whitespace is unscored (CTC blanks can span
it); this initial implementation is primarily for exact character vocabularies and
is not a multilingual tokenizer. Overlapping subtitle cues and digital silence
(RMS <= 1e-5) produce missing tokens and retain whole-cue estimated timing. An
impossible complete CTC path also falls back. Invalid geometry, nonfinite emissions,
truncated audio, excessive trellis size or stale bindings reject the artifact.

This cannot detect all silence, incorrect transcript text or overlapping speakers.
CTC can force an incorrect transcript onto unrelated audio. An `observed` token and
`aligned` timing source mean model-derived timing only, not that a word was correctly
recognized or that a cut sounds good. Scores are emission posteriors, not recognition
accuracy, calibrated confidence or proof of human validation. Existing whole-cue
fallback and downstream QC remain in force.

## Cache and reproducibility

Optional cache keys bind media/subtitle bytes, selected cues, source ID/duration,
model-directory content revision, producer/parser/import implementation bytes,
Torch/Transformers/NumPy/safetensors versions and the FFmpeg/FFprobe executable hashes. Changing
any of these makes a different entry. Input/model identities are rechecked after
execution, and every cached result is validated against the current source and cue
contract. Corrupt entries reject rather than trigger hidden inference. Cache files
contain an embedded digest, not a signature; keep them in a trusted private directory.
Ordinary importer result-file fingerprints still bind downstream workspace reuse.
CPU and fixed seeds do not promise bit-identical inference on different hardware.

## Validation and outstanding acceptance

Engineering tests create tiny random safetensors weights locally and generate their
own sine-wave/silence WAVs. They execute real feature extraction, CPU forward passes,
FFmpeg resampling and CLI/import/cache paths with Python network connects denied.
Deterministic emission tests also check frame geometry, repeated-character blanks
and Viterbi paths against exhaustive enumeration. These are not trained models or
speech, and must never be reported as Chinese acoustic-quality evidence.

Real trained-model execution, authorized Chinese speech, human gold boundaries,
cutoff improvement, fallback/error rates, overlapping-speech behavior and listening
quality remain **NOT_RUN**. Before production, obtain an approved licensed model and
short self-owned/authorized clips covering Chinese, numbers, mixed script, omitted
words, silence and overlap; compare human boundary deviations and falsely trusted
words, and listen to accepted cuts. The unrelated baked-media OTIO package remains
conditional on an actual editor handoff need and a supported pilot; it is not part
of this change.

API references: [Transformers model loading](https://huggingface.co/docs/transformers/v4.57.1/main_classes/model)
and [PyTorch CTC alignment tutorial](https://docs.pytorch.org/audio/stable/tutorials/ctc_forced_alignment_api_tutorial.html).
The trellis implementation here is independent; no upstream source or model is copied.
