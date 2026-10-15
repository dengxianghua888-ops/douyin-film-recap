from __future__ import annotations

from pathlib import Path

import pytest

from douyin_film_recap import asr, media
from douyin_film_recap.utils import SourceChangedDuringRead, content_identity


def _probe(_):
    return {
        "streams": [
            {"codec_type": "video", "width": 16, "height": 16, "avg_frame_rate": "24/1"},
            {"codec_type": "subtitle", "codec_name": "subrip", "index": 2},
        ],
        "format": {"duration": "5"},
    }


def _extract_fixture(command, **_):
    assert "-n" in command and "-y" not in command
    video = Path(command[command.index("-i") + 1])
    output = Path(command[-1])
    # Exclusive creation also ensures the implementation never requests a clobber.
    with output.open("x", encoding="utf-8") as handle:
        handle.write("1\n00:00:01,000 --> 00:00:03,000\n" + video.read_text() + "\n")


@pytest.mark.parametrize("relative_paths", [
    ("season1/episode.mp4", "season2/episode.mp4"),
    ("episode!.mp4", "episode?.mp4"),
])
def test_embedded_subtitles_are_isolated_and_transcribe_correct_source(
    tmp_path, monkeypatch, app_config, relative_paths
):
    source_root = tmp_path / "sources"
    for relative, text in zip(relative_paths, ["第一集对白", "第二集对白"]):
        video = source_root / relative
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_text(text, encoding="utf-8")
    monkeypatch.setattr(media, "ffprobe_json", _probe)
    monkeypatch.setattr(media, "run_command", _extract_fixture)
    manifest = media.build_manifest(source_root, app_config, tmp_path / "work")
    subtitle_paths = [Path(source.subtitle_path) for source in manifest.sources]
    assert len(set(subtitle_paths)) == 2
    for source, subtitle in zip(manifest.sources, subtitle_paths):
        identity = content_identity(subtitle)
        assert source.fingerprint in subtitle.parts
        assert source.source_id in subtitle.parts
        assert source.subtitle_fingerprint == identity["sha256"]
        assert source.subtitle_size_bytes == identity["bytes"]
    transcript = asr.build_transcript(manifest, app_config)
    source_map = {source.source_id: source for source in manifest.sources}
    assert len(transcript.segments) == 2
    for segment in transcript.segments:
        assert segment.text == Path(source_map[segment.source_id].path).read_text()


def test_repeated_extraction_preserves_old_subtitle_artifact(tmp_path, monkeypatch):
    video = tmp_path / "episode.mp4"
    video.write_text("原版对白", encoding="utf-8")
    monkeypatch.setattr(media, "ffprobe_json", _probe)
    monkeypatch.setattr(media, "run_command", _extract_fixture)
    first = media.extract_embedded_subtitle(video, tmp_path / "cache")
    assert first is not None
    original_bytes = first.read_bytes()
    video.write_text("更新对白", encoding="utf-8")
    second = media.extract_embedded_subtitle(video, tmp_path / "cache")
    assert second is not None and first != second
    assert first.read_bytes() == original_bytes
    assert "更新对白" in second.read_text()


@pytest.mark.parametrize("change_during_read", [False, True])
def test_transcript_rejects_changed_subtitle_identity(
    tmp_path, monkeypatch, app_config, change_during_read
):
    video = tmp_path / "source.mp4"
    video.write_bytes(b"synthetic video")
    subtitle = video.with_suffix(".srt")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:03,000\n原版对白\n", encoding="utf-8")
    monkeypatch.setattr(media, "ffprobe_json", _probe)
    manifest = media.build_manifest(video, app_config, tmp_path / "work")
    if change_during_read:
        parse = asr.parse_subtitle

        def mutate_after_parse(path, source_id):
            result = parse(path, source_id)
            Path(path).write_text("unexpected replacement", encoding="utf-8")
            return result

        monkeypatch.setattr(asr, "parse_subtitle", mutate_after_parse)
    else:
        subtitle.write_text("unexpected replacement", encoding="utf-8")
    with pytest.raises(SourceChangedDuringRead, match="Subtitle"):
        asr.build_transcript(manifest, app_config)


def test_same_basename_embedded_subtitles_with_real_ffmpeg(tmp_path, app_config):
    import shutil

    from douyin_film_recap.utils import run_command

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and ffprobe are required")
    source_root = tmp_path / "sources"
    for index, text in enumerate(["第一集对白", "第二集对白"], start=1):
        subtitle = tmp_path / f"input_{index}.srt"
        subtitle.write_text(f"1\n00:00:00,500 --> 00:00:01,500\n{text}\n", encoding="utf-8")
        video = source_root / f"season{index}" / "episode.mp4"
        video.parent.mkdir(parents=True)
        run_command([
            "ffmpeg", "-n", "-v", "error", "-f", "lavfi", "-i",
            "color=c=black:s=32x32:r=5:d=2", "-i", subtitle,
            "-map", "0:v", "-map", "1:s", "-c:v", "libx264", "-c:s", "mov_text", video,
        ])
    manifest = media.build_manifest(source_root, app_config, tmp_path / "work")
    transcript = asr.build_transcript(manifest, app_config)
    assert [(segment.source_id, segment.text) for segment in transcript.segments] == [
        ("src_001", "第一集对白"), ("src_002", "第二集对白"),
    ]
    assert len({source.subtitle_path for source in manifest.sources}) == 2
