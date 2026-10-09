from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

import pytest
from pydantic import ValidationError

from douyin_film_recap import render
from douyin_film_recap.models import SourceInfo, Storyboard, StoryboardSegment, VisualReference
from douyin_film_recap.utils import content_fingerprint, run_command


def segment(identifier="中文分镜"):
    return StoryboardSegment(segment_id=identifier, beat_id="b1", mode="original", title="原声",
                            text="", visuals=[VisualReference(source_id="s", start=0, end=0.5)],
                            audio_owner="action_sound", planned_duration_sec=0.5, notes="fixture")


def storyboard(source: Path):
    info = SourceInfo(source_id="s", path=str(source), fingerprint=content_fingerprint(source),
                      filename=source.name, duration=1, width=64, height=64, fps=24, has_audio=False)
    return Storyboard(project_name="test", sources=[info], plan_fingerprint="p",
                      target_duration_sec=0.5, segments=[segment()])


@pytest.mark.parametrize("identifier", ["", " ", ".", "..", "../source", "/tmp/source", "a/b",
                                        "a\\b", "C:movie", "nul\x00", "line\n", "x" * 129])
def test_semantic_ids_reject_paths_and_controls(identifier):
    with pytest.raises(ValidationError, match="segment_id"):
        segment(identifier)


def test_duplicate_ids_are_rejected_without_silent_rebinding(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fixture")
    board = storyboard(source)
    with pytest.raises(ValidationError, match="unique"):
        Storyboard.model_validate({**board.model_dump(), "segments": [segment().model_dump()] * 2})
    assert segment("中文 合法分镜").segment_id == "中文 合法分镜"


def test_mutated_absolute_id_is_rejected_at_render_boundary(tmp_path, app_config):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"user source sentinel")
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "v001.mp4"
    sentinel.write_bytes(b"must survive")
    board = storyboard(source)
    board.segments[0].segment_id = str(outside)
    work = tmp_path / "work"
    with pytest.raises(ValidationError, match="segment_id"):
        render.render_storyboard(board, app_config, work)
    assert sentinel.read_bytes() == b"must survive"
    assert source.read_bytes() == b"user source sentinel"
    assert not work.exists()


def test_symlink_attempt_parent_is_rejected_without_touching_target(tmp_path, app_config):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fixture")
    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (work / "render_attempts").symlink_to(outside, target_is_directory=True)
    with pytest.raises(render.ArtifactPathError, match="SYMLINK"):
        render.render_storyboard(storyboard(source), app_config, work)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("kind", ["existing", "hardlink", "symlink", "source"])
def test_private_write_boundary_refuses_existing_files_and_source_aliases(tmp_path, app_config, kind):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"original user media")
    board = storyboard(source)
    target = tmp_path / "target.mp4"
    if kind == "existing":
        target.write_bytes(b"user output")
    elif kind == "hardlink":
        os.link(source, target)
    elif kind == "symlink":
        target.symlink_to(source)
    else:
        target = source
    before = target.read_bytes()
    with pytest.raises(render.ArtifactPathError):
        render._render_visual_piece(board.segments[0].visuals[0], board.sources[0], 0.5, target, app_config)
    assert source.read_bytes() == b"original user media"
    assert target.read_bytes() == before


def test_attempt_rejects_linked_ancestor_and_replaced_root(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"original user media")
    attempt = render._RenderAttempt(tmp_path / "work", [source])
    outside = tmp_path / "outside"
    outside.mkdir()
    (attempt.root / "clips").symlink_to(outside, target_is_directory=True)
    with pytest.raises(render.ArtifactPathError, match="SYMLINK"):
        attempt.prepare(attempt.root / "clips" / "result.mp4")
    original_root = attempt.root.with_name("preserved-original")
    attempt.root.rename(original_root)
    attempt.root.mkdir()
    with pytest.raises(render.ArtifactPathError, match="CHANGED"):
        attempt.prepare(attempt.root / "result.mp4")
    assert list(outside.iterdir()) == []


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg is required")
def test_real_render_uses_new_attempts_and_preserves_manual_outputs(tmp_path, app_config):
    source = tmp_path / "source.mp4"
    run_command(["ffmpeg", "-n", "-v", "error", "-f", "lavfi", "-i",
                 "color=c=blue:size=64x64:rate=24:duration=1", "-f", "lavfi", "-i",
                 "sine=frequency=440:sample_rate=48000:duration=1", "-c:v", "libx264",
                 "-c:a", "aac", "-shortest", source])
    board = storyboard(source)
    board.sources[0].has_audio = True
    work = tmp_path / "work"
    legacy = work / "output" / "final.mp4"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"manual legacy final")
    source_hash = content_fingerprint(source)
    app_config.render.width = 64
    app_config.render.height = 64
    first = render.render_storyboard(board, app_config, work)
    first_final = Path(first.output["final_video"])
    assert first_final.is_relative_to(work / "render_attempts")
    assert first_final.stat().st_size > 0
    first_final.write_bytes(b"user modified last final")
    board.segments[0].segment_id = "修改后的中文分镜"
    second = render.render_storyboard(board, app_config, work)
    assert second.output["render_attempt_id"] != first.output["render_attempt_id"]
    assert Path(second.output["final_video"]).stat().st_size > 0
    assert first_final.read_bytes() == b"user modified last final"
    assert legacy.read_bytes() == b"manual legacy final"
    assert content_fingerprint(source) == source_hash
    edl = json.loads(Path(second.output["edl"]).read_text())
    assert edl[0]["segment_id"] == "修改后的中文分镜"
    assert board.output == {}  # A caller's previous record is not changed mid-attempt.
