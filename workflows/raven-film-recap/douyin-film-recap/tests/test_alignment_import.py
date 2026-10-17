"""Synthetic contract fixtures; these tests do not measure acoustic accuracy."""
import copy
import json
import socket

import pytest
from typer.testing import CliRunner

from douyin_film_recap.alignment import WHISPERX_REVISION, convert_whisperx, import_alignment
from douyin_film_recap.asr import build_transcript, parse_subtitle
from douyin_film_recap.cli import app
from douyin_film_recap.config import AlignmentConfig
from douyin_film_recap.models import SourceInfo, SourceManifest
from douyin_film_recap.utils import content_identity, fingerprint_json


@pytest.fixture
def sample(tmp_path):
    media = tmp_path / "clip.wav"
    media.write_bytes(b"synthetic identity fixture, not audio inference")
    subtitle = tmp_path / "clip.srt"
    subtitle.write_text("1\n00:00:01,000 --> 00:00:05,000\n你好 hello 43！\n", encoding="utf-8")
    source = SourceInfo(source_id="src_001", path=str(media), filename=media.name,
                        fingerprint=content_identity(media)["sha256"], duration=10,
                        width=16, height=16, fps=25, subtitle_path=str(subtitle),
                        subtitle_fingerprint=content_identity(subtitle)["sha256"])
    segments = parse_subtitle(subtitle, source.source_id)
    tokens = [dict(text=w.text, status="observed", start=1 + i * .5,
                   end=1.4 + i * .5, score=.7) for i, w in enumerate(segments[0].words)]
    result = dict(schema_version="film-alignment/1", source_id=source.source_id,
                  media_sha256=source.fingerprint, subtitle_sha256=source.subtitle_fingerprint,
                  producer="test-fixture", producer_revision="fixture-v1", model="no-real-model",
                  model_revision="fixture-v1", method="synthetic-contract-test",
                  score_semantics="test scalar, not accuracy probability", provenance="producer_declared",
                  cues=[dict(cue_index=0, text=segments[0].text, start=1, end=5, tokens=tokens)])
    path = tmp_path / "alignment.json"
    def write():
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return path
    write()
    return source, segments, result, write


def test_import_preserves_text_bounds_and_input(sample):
    source, segments, result, write = sample
    before = copy.deepcopy(segments)
    output = import_alignment(write(), source, segments)
    assert segments == before
    assert output[0].text == "你好 hello 43！"
    assert (output[0].start, output[0].end) == (1, 5)
    assert [w.text for w in output[0].words] == [w.text for w in segments[0].words]
    assert all(w.timing_source == "aligned" and w.probability is None for w in output[0].words)
    assert output[0].alignment["provenance"] == "producer_declared"
    assert output[0].alignment["result_sha256"] == content_identity(write())["sha256"]


@pytest.mark.parametrize("status", ["missing", "interpolated", "unknown"])
def test_inferred_whole_cue_fallback(sample, status):
    source, segments, result, write = sample
    token = result["cues"][0]["tokens"][1]
    token.update(status=status, start=None, end=None, score=None)
    output = import_alignment(write(), source, segments)
    assert output[0].words == segments[0].words
    assert all(w.timing_source == "estimated" for w in output[0].words)
    assert output[0].alignment["unobserved_token_indices"] == [1]
    assert output[0].alignment["fallback_reason"] == "incomplete_or_inferred_tokens"


@pytest.mark.parametrize("field,value", [
    ("start", -1), ("start", float("nan")), ("end", float("inf")),
    ("end", 1), ("end", 20), ("start", 0), ("score", float("nan")),
    ("start", None), ("score", None),
])
def test_bad_native_evidence_rejected(sample, field, value):
    source, segments, result, write = sample
    result["cues"][0]["tokens"][0][field] = value
    with pytest.raises(ValueError):
        import_alignment(write(), source, segments)


@pytest.mark.parametrize("mutation", ["text", "omit", "overlap", "cue_text", "cue_time", "duplicate",
                                     "bad_index", "media_hash", "subtitle_hash", "extra"])
def test_malformed_or_stale_contract_rejected(sample, mutation):
    source, segments, result, write = sample
    cue = result["cues"][0]
    if mutation == "text": cue["tokens"][0]["text"] = "错"
    if mutation == "omit": cue["tokens"].pop()
    if mutation == "overlap": cue["tokens"][1]["start"] = 1.1
    if mutation == "cue_text": cue["text"] += "改"
    if mutation == "cue_time": cue["start"] = 0
    if mutation == "duplicate": result["cues"].append(copy.deepcopy(cue))
    if mutation == "bad_index": cue["cue_index"] = 8
    if mutation == "media_hash": result["media_sha256"] = "0" * 64
    if mutation == "subtitle_hash": result["subtitle_sha256"] = "0" * 64
    if mutation == "extra": result["assume_aligned"] = True
    with pytest.raises(ValueError):
        import_alignment(write(), source, segments)


def test_overlapping_cues_fallback_and_unselected_unchanged(sample):
    source, segments, _, write = sample
    segments.append(segments[0].model_copy(deep=True, update={"start": 4, "end": 6}))
    output = import_alignment(write(), source, segments)
    assert output[0].alignment["fallback_reason"] == "overlapping_subtitle_cues"
    assert output[1] == segments[1]


def test_missing_model_default_no_network_and_fingerprint(sample, app_config, monkeypatch):
    source, segments, result, write = sample
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("network attempted"))
    monkeypatch.setattr("douyin_film_recap.asr._load_whisper_model",
                        lambda *a: pytest.fail("model loading attempted"))
    manifest = SourceManifest(sources=[source], config_fingerprint="test")
    assert not app_config.asr.alignment.enabled
    output = build_transcript(manifest, app_config)
    assert output.segments == segments
    # Disabled option preserves previous identity, including ignored missing paths.
    data = app_config.model_dump(mode="json")
    data["asr"].pop("alignment")
    data["render"].pop("incremental_cache", None)
    for key in ("visual_retrieval", "visual_pool_text_budget", "visual_exploration_fraction"):
        data["format"].pop(key, None)
    expected = fingerprint_json({"config": data, "explicit_format_fields": sorted(app_config.format.model_fields_set)})
    assert app_config.fingerprint() == expected
    app_config.asr.alignment = AlignmentConfig(enabled=True, result_files={source.source_id: str(write())})
    first = app_config.fingerprint()
    aligned = build_transcript(manifest, app_config)
    assert aligned.segments[0].words[0].timing_source == "aligned"
    result["model_revision"] = "new-revision"
    write()
    assert app_config.fingerprint() != first


def test_enabled_missing_result_fails_without_model_fallback(sample, app_config, monkeypatch):
    source, _, _, write = sample
    path = write(); path.unlink()
    app_config.asr.alignment = AlignmentConfig(enabled=True, result_files={source.source_id: str(path)})
    monkeypatch.setattr("douyin_film_recap.asr._load_whisper_model", lambda *a: pytest.fail("model fallback"))
    with pytest.raises(FileNotFoundError):
        build_transcript(SourceManifest(sources=[source], config_fingerprint="test"), app_config)


def whisper_receipt(sample):
    _, _, result, _ = sample
    receipt = {k: v for k, v in result.items() if k != "cues"}
    receipt.update(producer="whisperx", producer_revision=WHISPERX_REVISION,
                   interpolate_method="ignore", dictionary=list("你好helo43！"))
    cue = result["cues"][0]
    chars = [dict(char=c, start=1 + i*.2, end=1.15+i*.2, score=.75)
             for i, c in enumerate(cue["text"])]
    receipt["whisperx_cues"] = [{**{k: v for k, v in cue.items() if k != "tokens"},
                                "result": {"segments": [{"text": cue["text"], "chars": chars}]}}]
    return receipt


def test_convert_native_chars_and_validate_cli(sample, tmp_path):
    source, _, _, _ = sample
    receipt = whisper_receipt(sample)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt))
    output = tmp_path / "converted.json"
    runner = CliRunner()
    response = runner.invoke(app, ["convert-whisperx-alignment", "--receipt", str(path), "--output", str(output)])
    assert response.exit_code == 0, response.output
    manifest = tmp_path / "manifest.json"
    manifest.write_text(SourceManifest(sources=[source], config_fingerprint="test").model_dump_json())
    response = runner.invoke(app, ["validate-alignment", "--manifest", str(manifest), "--source-id", source.source_id,
                                   "--result", str(output)])
    assert response.exit_code == 0, response.output
    assert "1 aligned cues" in response.output
    assert runner.invoke(app, ["convert-whisperx-alignment", "--receipt", str(path), "--output", str(output)]).exit_code == 2


@pytest.mark.parametrize("mutation", ["word_only", "nearest", "revision", "text", "duplicate_char", "split"])
def test_ambiguous_whisperx_output_refused(sample, mutation):
    receipt = whisper_receipt(sample)
    part = receipt["whisperx_cues"][0]["result"]["segments"][0]
    if mutation == "word_only": part.pop("chars")
    if mutation == "nearest": receipt["interpolate_method"] = "nearest"
    if mutation == "revision": receipt["producer_revision"] = "unknown"
    if mutation == "text": part["text"] += "changed"
    if mutation == "duplicate_char": part["chars"].append(part["chars"][0])
    if mutation == "split": receipt["whisperx_cues"][0]["result"]["segments"].append(part)
    with pytest.raises(ValueError):
        convert_whisperx(receipt)


@pytest.mark.parametrize("unknown", ["4", "！", "你"])
def test_wildcard_or_missing_char_never_aligned(sample, unknown):
    receipt = whisper_receipt(sample)
    receipt["dictionary"].remove(unknown)
    result = convert_whisperx(receipt)
    assert any(token.status == "missing" for token in result.cues[0].tokens)


def test_partial_english_token_not_promoted(sample):
    receipt = whisper_receipt(sample)
    chars = receipt["whisperx_cues"][0]["result"]["segments"][0]["chars"]
    next(c for c in chars if c["char"] == "e").pop("start")
    result = convert_whisperx(receipt)
    assert next(t for t in result.cues[0].tokens if t.text == "hello").status == "missing"


@pytest.mark.parametrize("mode", ["unknown_source", "no_subtitle", "no_audio"])
def test_explicit_unusable_source_fails(sample, app_config, monkeypatch, mode):
    source, _, _, write = sample
    key = "unknown" if mode == "unknown_source" else source.source_id
    if mode == "no_subtitle": source.subtitle_path = None
    if mode == "no_audio": source.has_audio = False
    app_config.asr.alignment = AlignmentConfig(enabled=True, result_files={key: str(write())})
    monkeypatch.setattr("douyin_film_recap.asr._load_whisper_model", lambda *a: pytest.fail("model loaded"))
    with pytest.raises(ValueError):
        build_transcript(SourceManifest(sources=[source], config_fingerprint="test"), app_config)


def test_disabled_ignores_nonexistent_alignment_file(app_config):
    old = app_config.fingerprint()
    app_config.asr.alignment.result_files = {"source": "/does/not/exist.json"}
    assert app_config.fingerprint() == old


def test_alignment_result_change_hits_existing_runtime_binding(sample, app_config):
    from douyin_film_recap.pipeline import FilmRecapPipeline
    from douyin_film_recap.workspace import WorkspaceError
    source, _, result, write = sample
    app_config.asr.alignment = AlignmentConfig(enabled=True, result_files={source.source_id: str(write())})
    pipeline = FilmRecapPipeline.__new__(FilmRecapPipeline)
    pipeline.config = app_config
    pipeline._config_fingerprint = app_config.fingerprint()
    result["cues"][0]["tokens"][0]["score"] = .9
    write()
    with pytest.raises(WorkspaceError, match="CONFIG_OR_ENDPOINT_BINDING_CHANGED"):
        pipeline._assert_bound_sources()


def test_yaml_alignment_paths_relative_to_config(sample, app_config, tmp_path):
    import yaml
    from douyin_film_recap.config import load_config
    source, _, _, write = sample
    data = app_config.model_dump()
    data["asr"]["alignment"] = {"enabled": True, "result_files": {source.source_id: write().name}}
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump(data))
    assert load_config(config).asr.alignment.result_files[source.source_id] == str(write())


def test_boolean_time_rejected(sample):
    source, segments, result, write = sample
    result["cues"][0]["tokens"][0]["start"] = True
    with pytest.raises(ValueError):
        import_alignment(write(), source, segments)
