from __future__ import annotations

import hashlib
import os

import pytest
from pydantic import ValidationError

from douyin_film_recap import media, utils
from douyin_film_recap.models import PipelineState, SourceInfo, SourceManifest


def test_middle_change_with_restored_mtime_invalidates_complete_identity(tmp_path):
    source = tmp_path / "source.avi"
    source.write_bytes(b"a" * (4 * 1024 * 1024))
    original_stat = source.stat()
    before = utils.content_identity(source)
    hint = utils.sampled_fingerprint_hint(source)
    with source.open("r+b") as handle:
        handle.seek(1500000)
        handle.write(b"changed")
    os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    assert utils.sampled_fingerprint_hint(source) == hint
    assert utils.file_fingerprint(source) != before["sha256"]
    assert utils.content_identity(source) == {
        "schema": "sha256-full/2", "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "bytes": 4 * 1024 * 1024,
    }


def test_timestamp_alone_does_not_invalidate_content(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"same bytes")
    before = utils.content_identity(source)
    stamp = source.stat()
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1000000))
    assert utils.content_identity(source) == before


@pytest.mark.parametrize("mutation", ["modify", "replace", "delete"])
def test_hashing_rejects_observed_source_changes(tmp_path, monkeypatch, mutation):
    source = tmp_path / "source.bin"
    source.write_bytes(b"a" * 4096)
    original_stat = source.stat()
    original_digest = hashlib.sha256

    class ChangingDigest:
        def __init__(self):
            self.digest = original_digest()
            self.changed = False

        def update(self, value):
            self.digest.update(value)
            if self.changed:
                return
            self.changed = True
            if mutation == "delete":
                source.unlink()
            elif mutation == "replace":
                replacement = tmp_path / "replacement.bin"
                replacement.write_bytes(b"a" * 4096)
                replacement.replace(source)
            else:
                with source.open("r+b") as handle:
                    handle.seek(2048)
                    handle.write(b"changed")
                os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

        def hexdigest(self):
            return self.digest.hexdigest()

    monkeypatch.setattr(utils.hashlib, "sha256", ChangingDigest)
    with pytest.raises(utils.SourceChangedDuringRead):
        utils.content_identity(source, chunk_size=1024)


@pytest.mark.parametrize("version", [0, 1, 3, 999, "2"])
def test_production_state_and_manifest_reject_unsupported_versions(version):
    with pytest.raises(ValidationError):
        PipelineState(schema_version=version, project_name="p", input_paths=[],
                      config_fingerprint="c", stages={})
    with pytest.raises(ValidationError):
        SourceManifest(schema_version=version, sources=[], config_fingerprint="c")


def test_new_records_declare_content_identity_version():
    assert PipelineState(project_name="p", input_paths=[], config_fingerprint="c", stages={}).schema_version == 2
    assert SourceManifest(sources=[], config_fingerprint="c").schema_version == 2
    source = SourceInfo(source_id="s", path="movie.mp4", fingerprint="f", filename="movie.mp4",
                        duration=1, width=16, height=16, fps=24)
    assert source.identity_schema == "sha256-full/2"
    with pytest.raises(ValidationError):
        SourceInfo.model_validate({**source.model_dump(), "identity_schema": "sampled/1"})


@pytest.mark.parametrize("change_during_probe", [False, True])
def test_manifest_binds_full_content_and_refuses_probe_drift(tmp_path, app_config, monkeypatch, change_during_probe):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"original source fixture")
    app_config.asr.prefer_sidecar_subtitle = False
    app_config.asr.prefer_embedded_subtitle = False

    def probe(_):
        if change_during_probe:
            source.write_bytes(b"different source fixture")
        return {"streams": [{"codec_type": "video", "width": 16, "height": 16,
                             "avg_frame_rate": "24/1"}], "format": {"duration": "1"}}

    monkeypatch.setattr(media, "ffprobe_json", probe)
    if change_during_probe:
        with pytest.raises(utils.SourceChangedDuringRead):
            media.build_manifest(source, app_config, tmp_path / "work")
    else:
        result = media.build_manifest(source, app_config, tmp_path / "work")
        assert result.sources[0].fingerprint == hashlib.sha256(source.read_bytes()).hexdigest()
        assert result.sources[0].size_bytes == source.stat().st_size
        assert result.sources[0].identity_schema == "sha256-full/2"
