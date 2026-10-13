from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from douyin_film_recap import media
from douyin_film_recap.models import (
    SceneAnalysisDocument, SceneAnalysisItem, SceneDetectionMetadata, SceneIndex,
    SourceInfo, SourceManifest, TranscriptDocument,
)
from douyin_film_recap.analysis import _scene_payload
from douyin_film_recap.planning import _build_visual_pool
from douyin_film_recap.prompts import scene_batch_prompt
from test_qc import _base_artifacts


def _source(source_id="src_001"):
    return SourceInfo(source_id=source_id, path="/fixture.mp4", fingerprint=source_id,
                      filename="fixture.mp4", duration=40, width=16, height=16, fps=25)


def _fake_detector(monkeypatch, *, error=None, empty=False):
    class Manager:
        def add_detector(self, detector):
            pass

        def detect_scenes(self, **kwargs):
            if error:
                raise error

        def get_scene_list(self, **kwargs):
            return [] if empty else [(SimpleNamespace(get_seconds=lambda: 0),
                                     SimpleNamespace(get_seconds=lambda: 40))]

    monkeypatch.setitem(sys.modules, "scenedetect", SimpleNamespace(
        ContentDetector=lambda **kwargs: object(), SceneManager=Manager,
        open_video=lambda path: object(),
    ))


@pytest.mark.parametrize("failure", ["missing", "decode", "empty"])
def test_detector_failures_record_reason_and_unknown_boundaries(monkeypatch, app_config, failure):
    if failure == "missing":
        monkeypatch.setitem(sys.modules, "scenedetect", None)
    else:
        _fake_detector(monkeypatch, error=RuntimeError("fixture decode failure") if failure == "decode" else None,
                       empty=failure == "empty")
    with pytest.warns(RuntimeWarning, match="Shot boundaries and continuity are unknown"):
        shots, metadata = media.detect_shots_with_metadata(_source(), app_config)
    assert shots == [(0, 16), (16, 32), (32, 40)]
    assert metadata.detector_requested == "scenedetect"
    assert metadata.detector_used == "fixed_interval"
    assert metadata.boundary_confidence == "unknown"
    expected = {"missing": "missing_dependency", "decode": "detection_error", "empty": "no_usable_scenes"}
    assert metadata.fallback_reason.startswith(expected[failure])


def test_real_detector_result_is_distinct_from_fallback(monkeypatch, app_config):
    _fake_detector(monkeypatch)
    shots, metadata = media.detect_shots_with_metadata(_source(), app_config)
    assert shots == [(0, 40)]
    assert metadata.detector_used == "scenedetect"
    assert metadata.boundary_confidence == "detector_estimated"
    assert metadata.fallback_reason is None
    assert media.detect_shots(_source(), app_config) == shots


@pytest.mark.parametrize("mixed", [False, True])
def test_index_and_prompt_never_claim_fixed_windows_are_shots(tmp_path, monkeypatch, app_config, mixed):
    sources = [_source()]
    if mixed:
        sources.append(_source("src_002"))
    manifest = SourceManifest(sources=sources, config_fingerprint="fixture")
    transcript = TranscriptDocument(provider="fixture", segments=[], source_fingerprints={})

    def detect(source, config):
        fallback = source.source_id == "src_001"
        return ([(0, 16), (16, 32), (32, 40)] if fallback else [(0, 40)]), SceneDetectionMetadata(
            detector_requested="scenedetect", detector_used="fixed_interval" if fallback else "scenedetect",
            fallback_reason="no_usable_scenes" if fallback else None,
            boundary_confidence="unknown" if fallback else "detector_estimated",
        )

    monkeypatch.setattr(media, "detect_shots_with_metadata", detect)
    monkeypatch.setattr(media, "extract_frames_batch", lambda *args: None)
    monkeypatch.setattr(media, "make_contact_sheet", lambda *args: None)
    monkeypatch.setattr(media, "motion_score", lambda *args: 0)
    index = media.build_scene_index(manifest, transcript, app_config, tmp_path)
    assert index.detector == ("mixed" if mixed else "fixed_interval")
    assert index.detection_status == ("mixed" if mixed else "fallback")
    assert index.source_detection["src_001"].fallback_reason == "no_usable_scenes"
    fallback_units = [unit for unit in index.units if unit.source_id == "src_001"]
    assert all(unit.analysis_window_only for unit in fallback_units)
    assert all(unit.original_shot_spans == [] and unit.continuity_shot_ids == [] for unit in fallback_units)
    assert all(unit.signals.shot_density == 0 and not unit.signals.shot_density_available for unit in fallback_units)
    roundtrip = SceneIndex.model_validate_json(index.model_dump_json())
    assert roundtrip.source_detection == index.source_detection
    payload = json.loads(scene_batch_prompt(fallback_units).split("\n\n", 1)[1])
    assert all(unit["scene_detection"]["detector_used"] == "fixed_interval" for unit in payload)
    assert all(unit["original_shot_spans"] == [] and unit["continuity_shot_ids"] == [] for unit in payload)
    analysis = SceneAnalysisDocument(provider="fixture", model="fixture", unit_fingerprint="fixture",
                                     items=[SceneAnalysisItem(unit_id=unit.unit_id) for unit in index.units])
    story_payload = _scene_payload(index, analysis)
    assert story_payload[0]["scene_detection"]["detector_used"] == "fixed_interval"
    _, _, story, highlights, plan, _ = _base_artifacts(app_config, unsafe=False)
    pool = _build_visual_pool(manifest, story, highlights, plan, app_config, index, analysis)
    fallback_pool = [unit for unit in pool if unit["unit_id"] in {unit.unit_id for unit in fallback_units}]
    assert fallback_pool
    assert all(unit["scene_detection"]["boundary_confidence"] == "unknown" for unit in fallback_pool)
    if mixed:
        detected_units = [unit for unit in index.units if unit.source_id == "src_002"]
        assert all(unit.original_shot_spans == [(0, 40)] for unit in detected_units)
        assert len({tuple(unit.continuity_shot_ids) for unit in detected_units}) == 1


def test_unsupported_detector_does_not_silently_substitute(app_config):
    app_config.scene.detector = "unconfigured-detector"
    with pytest.raises(ValueError, match="Unsupported scene detector"):
        media.detect_shots_with_metadata(_source(), app_config)
