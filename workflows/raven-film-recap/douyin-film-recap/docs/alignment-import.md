# M1: offline alignment-result import (experimental)

This release **imports existing alignment evidence**. It does not implement or run
an acoustic forced aligner, install WhisperX/PyTorch, download models, or contact a
service. Tests use synthetic contracts, not real speech. Chinese boundary accuracy,
cutoff improvement, real model execution and downstream listening quality are
**NOT_RUN**. There is no diarization.

## Enable only for selected existing subtitle cues

Normal subtitle parsing is unchanged. Alignment never rewrites the parsed subtitle
text or cue bounds (the parser's existing markup/whitespace normalization still
applies). Original source/subtitle files are never written.

```yaml
asr:
  alignment:
    enabled: true                     # default false
    result_files:
      src_001: ./alignment/src_001.json # use actual source_id from the manifest
```

Paths in YAML resolve relative to the config file. Each result lists zero-based
`cue_index` values in that source's parsed subtitle order. Only listed cues are
selected; all other cues retain their existing estimated words. Full cue boundaries
are the selected windows; partial-cue and cropped-audio offsets are unsupported.
Use the source-media clock in seconds, not the final film clock.

Run the existing pipeline normally, or validate without ASR/inference:

```sh
python -m douyin_film_recap validate-alignment \
  --manifest work/00_source_manifest.json --source-id src_001 \
  --result alignment/src_001.json
```

Use the actual active generation manifest path in schema-2 workspaces. Validation
is read-only. It reports adopted/fallback cue counts. Pipeline failures leave the
existing state/error handling in control; invalid imports never trigger model or
network fallback. An enabled import needs nonempty subtitles and audio.

## Contract: film-alignment/1

An import JSON has these required fields:

- `schema_version`: `film-alignment/1`
- `source_id`, `media_sha256`, `subtitle_sha256`: full source media and raw subtitle
  bytes SHA-256 at producer execution time, checked against current files/manifest.
  `media_sha256` binds the original container file, including its audio; a hash of a
  separately extracted WAV is **not** interchangeable. The producer must retain the
  original container binding and use its unshifted source clock.
- `producer`, `producer_revision`, `model`, `model_revision`: exact producer build
  and immutable model revision or local model-directory content digest. Do not use
  moving aliases such as `latest` or `main`.
- `method`, `score_semantics`: explicit interpretation of alignment and scores.
  A CTC score is not recognition correctness or calibrated confidence.
- `provenance`: `producer_declared`. These are declarations, not a signature or
  independent proof of model execution, licensing, or acoustic accuracy.
- `cues`: nonempty array of `{cue_index, text, start, end, tokens}`.
- Each token has `text`, `status` (`observed`, `missing`, `interpolated`, `unknown`),
  optional `start`, `end`, `score`. Observed tokens require both finite timestamps
  and a finite score. Tokenization must exactly match the existing subtitle parser:
  individual Chinese characters, Latin/number words, and punctuation tokens.

Exact token coverage, exact cue text/bounds, unique indices, finite ordered times,
media/cue bounds and nonoverlap are checked. Omitted/reordered/mismatched tokens,
wrong hashes or malformed timings reject the artifact. Represent a missing token
explicitly with `status: missing`, null timestamps and null score. Any nonobserved
token or overlapping subtitle cue keeps the **whole original cue** as `estimated`.
No interpolation is promoted to `aligned`. In particular, punctuation/unknown
numbers may cause conservative whole-cue fallback. Silence cannot be detected
from this import contract; it requires independent acoustic evaluation.

The transcript stores per-cue provenance, input/result hashes, missing indices,
fallback reason and original imported token evidence. Adopted word scores are in
`alignment_score`, never `probability`. Existing QC timing-source checks stay intact.

The enabled configuration fingerprint includes **result file content identities**,
not just paths, plus an implementation digest of the alignment/parser/model/config
source files. Changing result bytes, selected cues, model revision or config
invalidates the existing workspace binding through the normal state machine; an
in-flight file change is rejected. Resume requires the normal new-generation flow.
Disabled alignment adds no model imports, file reads or network access and preserves
the pre-feature configuration fingerprint. There is no separate alignment cache.

## WhisperX conversion: native characters only

The standalone conversion command consumes a producer receipt. It does not launch
WhisperX. Supported upstream format is pinned to
[`771b4a14a9486f8fd5aef18ef49e35d639523dd3`](https://github.com/m-bain/whisperX/blob/771b4a14a9486f8fd5aef18ef49e35d639523dd3/whisperx/alignment.py).

The producer must already have the licensed local model/processor/vocabulary,
WhisperX dependencies and NLTK sentence resources. Upstream code can otherwise
attempt model or NLTK downloads; our importer never calls it. Do not treat an
upstream cache-only flag as a complete offline guarantee. Run the producer under
your own offline setup/network restriction and record the actual execution inputs.

For each selected cue, an already configured producer should capture the return
value of `whisperx.align([original_cue], model, metadata, full_source_audio, device,
interpolate_method="ignore", return_char_alignments=True)`. Capture hashes before
and verify them after inference; save the actual model/build revision and
`list(metadata["dictionary"])`. This is guidance for an external producer, not an
inference command supplied/executed by this project.

A conversion receipt uses all the contract header fields above, except `cues`, plus:

```json
{
  "producer": "whisperx",
  "producer_revision": "771b4a14a9486f8fd5aef18ef49e35d639523dd3",
  "interpolate_method": "ignore",
  "dictionary": ["你", "好"],
  "whisperx_cues": [{
    "cue_index": 0, "text": "你好", "start": 1.0, "end": 2.0,
    "result": {
      "segments": [{"text": "你好", "chars": [
        {"char": "你", "start": 1.1, "end": 1.4, "score": 0.7},
        {"char": "好", "start": 1.5, "end": 1.8, "score": 0.8}
      ]}]
    }
  }]
}
```

This illustrative fragment deliberately omits real input hashes/model identity;
add them from the real producer receipt. These sample times are synthetic and must
not be used as speech evidence. `dictionary` must be the actual complete model
vocabulary, not a list fabricated from subtitle text.

```sh
python -m douyin_film_recap convert-whisperx-alignment \
  --receipt actual-producer-receipt.json --output alignment/src_001.json
```

Output creation is exclusive (existing files are not overwritten). Then run
`validate-alignment` with the actual manifest, before enabling pipeline adoption.

Only one exact-text result segment per original cue is supported. Multi-sentence
regrouping, duplicated/missing characters and word-only exports are rejected;
there is no guessing of offsets or reconstruction of missing text. Native character
coverage plus model-vocabulary membership is required for every character in a
token. Wildcard/unknown characters or absent timestamps remain missing even if a
word timestamp exists. This avoids treating partial-word/nearest interpolation as
evidence. Token score is the arithmetic mean of its native character scores.
The conversion supplies its own method/score semantics; producer/model identities
remain declared. Neither hashes nor an `ignore` declaration prove the producer ran
honestly. Use trusted, reviewed producer receipts only.

## Validation scope

`tests/test_alignment_import.py` covers Chinese/English/numbers/punctuation,
missing and inferred tokens, native-character conversion, malformed/NaN/infinite
or overlapping/out-of-bounds timing, stale input identity, unchanged text/default
behavior, unknown sources, CLI use and cache identity. It does not establish real
Chinese speech benefits. Before production, use authorized short audio with human
boundary gold labels, measure cutoff errors/fallback rate and listen to accepted
cuts, including overlapping speech and silence.
