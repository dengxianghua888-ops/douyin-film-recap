from __future__ import annotations

from pathlib import Path

import shutil
import pytest

from douyin_film_recap.asr import build_transcript
from douyin_film_recap.media import build_manifest, build_scene_index
from douyin_film_recap.utils import run_command

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg is required",
)


def test_ingest_subtitle_and_scene_index(tmp_path: Path, app_config) -> None:
    source = tmp_path / "episode01.mp4"
    subtitle = tmp_path / "episode01.srt"
    run_command(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=24:duration=4",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=4",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            source,
        ]
    )
    subtitle.write_text(
        "1\n00:00:00,500 --> 00:00:02,100\n你到底想干什么？\n\n"
        "2\n00:00:02,300 --> 00:00:03,700\n真正的危险才刚开始。\n",
        encoding="utf-8",
    )
    work = tmp_path / "work"
    manifest = build_manifest(source, app_config, work)
    assert manifest.sources[0].subtitle_path == str(subtitle.resolve())
    transcript = build_transcript(manifest, app_config)
    assert transcript.provider == "subtitle"
    assert len(transcript.segments) == 2
    assert transcript.segments[0].words

    scene_index = build_scene_index(manifest, transcript, app_config, work)
    assert scene_index.units
    assert all(Path(unit.contact_sheet_path or "").exists() for unit in scene_index.units)
    assert all(unit.frame_paths for unit in scene_index.units)
