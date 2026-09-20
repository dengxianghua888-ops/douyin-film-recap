from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from PIL import ImageFont

from .config import AppConfig
from .media import media_duration
from .models import SourceInfo, Storyboard, StoryboardSegment, VisualReference
from .subtitles import build_cues, output_timeline, resolved_visual_spans, segment_output_duration, write_srt
from .utils import content_fingerprint, run_command, safe_slug, write_json


def _layout_filter(config: AppConfig) -> str:
    width, height, fps = config.render.width, config.render.height, config.render.fps
    if config.render.layout == "center_crop":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,fps={fps},format=yuv420p"
        )
    if config.render.layout == "fit_black":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps={fps},format=yuv420p"
        )
    return (
        f"split=2[bg][fg];"
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},gblur=sigma={config.render.blur_sigma}[bg2];"
        f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[fg2];"
        f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2,setsar=1,fps={fps},format=yuv420p"
    )


def _video_encode_args(config: AppConfig) -> list[str]:
    return [
        "-c:v",
        config.render.video_codec,
        "-preset",
        config.render.preset,
        "-crf",
        str(config.render.crf),
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(config.render.fps),
        "-movflags",
        "+faststart",
    ]


def _audio_encode_args(config: AppConfig) -> list[str]:
    return [
        "-c:a",
        config.render.audio_codec,
        "-b:a",
        config.render.audio_bitrate,
        "-ar",
        "48000",
        "-ac",
        "2",
    ]


def _source_map(storyboard: Storyboard) -> dict[str, SourceInfo]:
    return {source.source_id: source for source in storyboard.sources}


def _render_visual_piece(
    visual: VisualReference,
    source: SourceInfo,
    duration: float,
    output: Path,
    config: AppConfig,
    *,
    include_audio: bool = False,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    args: list[str | Path] = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-ss",
        f"{visual.start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        source.path,
    ]
    audio_input = "0:a:0"
    if include_audio and not source.has_audio:
        args.extend(
            [
                "-f",
                "lavfi",
                "-t",
                f"{duration:.3f}",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
            ]
        )
        audio_input = "1:a:0"
    args.extend(["-map", "0:v:0", "-vf", _layout_filter(config)])
    if include_audio:
        fade = min(0.03, duration / 4)
        args.extend(
            [
                "-map",
                audio_input,
                "-af",
                (
                    "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                    f"afade=t=in:st=0:d={fade:.3f},"
                    f"afade=t=out:st={max(0.0, duration - fade):.3f}:d={fade:.3f}"
                ),
                *_video_encode_args(config),
                *_audio_encode_args(config),
                "-shortest",
                output,
            ]
        )
    else:
        args.extend(["-an", *_video_encode_args(config), output])
    run_command(args, timeout=config.runtime.stage_timeout_sec)


def _write_concat_list(paths: list[Path], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for path in paths:
        escaped = str(path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _concat_copy(paths: list[Path], output: Path, config: AppConfig) -> None:
    concat_list = _write_concat_list(paths, output.with_suffix(".concat.txt"))
    try:
        run_command(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_list,
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                output,
            ],
            timeout=config.runtime.stage_timeout_sec,
        )
    except Exception:
        # Fallback re-encodes but remains deterministic when container timebases differ.
        run_command(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_list,
                *_video_encode_args(config),
                *_audio_encode_args(config),
                output,
            ],
            timeout=config.runtime.stage_timeout_sec,
        )


def _render_voiceover_segment(
    segment: StoryboardSegment,
    source_map: dict[str, SourceInfo],
    output: Path,
    work_dir: Path,
    config: AppConfig,
) -> None:
    if not segment.audio_file or not Path(segment.audio_file).exists():
        raise FileNotFoundError(f"Missing voiceover audio: {segment.segment_id}")
    target_duration = float(segment.audio_duration_sec or segment.planned_duration_sec)
    remaining = target_duration
    pieces: list[Path] = []
    for index, visual in enumerate(resolved_visual_spans(segment), start=1):
        source = source_map[visual.source_id]
        available = visual.end - visual.start
        duration = min(available, remaining)
        piece = work_dir / "clips" / "visuals" / segment.segment_id / f"v{index:03d}.mp4"
        _render_visual_piece(
            visual,
            source,
            duration,
            piece,
            config,
            include_audio=not segment.mute_original,
        )
        pieces.append(piece)
        remaining -= duration
    if remaining > 0.001:
        raise ValueError(
            f"Voiceover visuals are {remaining:.2f}s shorter than audio: {segment.segment_id}"
        )
    visual_base = work_dir / "clips" / "visuals" / segment.segment_id / "visual_base.mp4"
    _concat_copy(pieces, visual_base, config)
    fade = min(0.03, target_duration / 4)
    output.parent.mkdir(parents=True, exist_ok=True)
    args: list[str | Path] = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        visual_base,
        "-i",
        segment.audio_file,
        "-map",
        "0:v:0",
    ]
    if segment.mute_original:
        speed_filter = (f"atempo={segment.audio_speed:.6f}," if abs(segment.audio_speed - 1.0) > 1e-4 else "")
        audio_filter = (
            speed_filter
            + "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"afade=t=in:st=0:d={fade:.3f},"
            f"afade=t=out:st={max(0.0, target_duration - fade):.3f}:d={fade:.3f}"
        )
        args.extend(["-map", "1:a:0", "-af", audio_filter])
    else:
        filter_complex = (
            f"[0:a]volume={config.render.original_bed_db}dB,"
            f"atrim=0:{target_duration:.3f},asetpts=PTS-STARTPTS[bed];"
            f"[1:a]{('atempo=' + format(segment.audio_speed, '.6f') + ',') if abs(segment.audio_speed - 1.0) > 1e-4 else ''}"
            f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"atrim=0:{target_duration:.3f},asetpts=PTS-STARTPTS[vo];"
            f"[bed][vo]amix=inputs=2:duration=longest:dropout_transition=0,"
            f"afade=t=in:st=0:d={fade:.3f},"
            f"afade=t=out:st={max(0.0, target_duration - fade):.3f}:d={fade:.3f}[mix]"
        )
        args.extend(["-filter_complex", filter_complex, "-map", "[mix]"])
    args.extend(
        [
            "-t",
            f"{target_duration:.3f}",
            "-c:v",
            "copy",
            *_audio_encode_args(config),
            "-movflags",
            "+faststart",
            output,
        ]
    )
    run_command(args, timeout=config.runtime.stage_timeout_sec)


def _render_original_segment(
    segment: StoryboardSegment,
    source_map: dict[str, SourceInfo],
    output: Path,
    config: AppConfig,
) -> None:
    visuals = resolved_visual_spans(segment)
    if len(visuals) != 1:
        raise ValueError(f"Original segment must have one continuous visual: {segment.segment_id}")
    visual = visuals[0]
    source = source_map[visual.source_id]
    duration = visual.end - visual.start
    fade = min(0.03, duration / 4)
    args: list[str | Path] = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-ss",
        f"{visual.start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        source.path,
    ]
    if not source.has_audio:
        args.extend(
            [
                "-f",
                "lavfi",
                "-t",
                f"{duration:.3f}",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
            ]
        )
        audio_input = "1:a:0"
    else:
        audio_input = "0:a:0"
    audio_filter = (
        f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
        f"afade=t=in:st=0:d={fade:.3f},"
        f"afade=t=out:st={max(0.0, duration - fade):.3f}:d={fade:.3f}"
    )
    args.extend(
        [
            "-map",
            "0:v:0",
            "-map",
            audio_input,
            "-vf",
            _layout_filter(config),
            "-af",
            audio_filter,
            *_video_encode_args(config),
            *_audio_encode_args(config),
            output,
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    run_command(args, timeout=config.runtime.stage_timeout_sec)


def _escape_subtitle_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    value = value.replace(":", "\\:").replace("'", "\\'")
    return value


def _subtitle_style(config: AppConfig, font_name: str | None = None) -> str:
    return (
        f"FontName={font_name or config.render.subtitle_font},"
        f"FontSize={config.render.subtitle_font_size},"
        "Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00101010,"
        "BackColour=&H66000000,BorderStyle=1,Shadow=0,Alignment=2,"
        f"Outline={config.render.subtitle_outline},"
        f"MarginV={config.render.subtitle_margin_v}"
    )


@contextmanager
def _subtitle_font_source(config: AppConfig):
    """Explicit files bypass unreliable system font discovery, including CoreText.

    libass accepts a directory, not a fontfile option. Give it a temporary
    directory containing only the selected file and use the file's real family.
    No font is installed, downloaded, or silently replaced.
    """
    font_file = config.render.subtitle_font_file
    fonts_dir = config.render.subtitle_fonts_dir
    if font_file and fonts_dir:
        raise ValueError("Set only subtitle_font_file or subtitle_fonts_dir, not both")
    if font_file:
        source = Path(font_file).expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"Subtitle font file does not exist: {source}")
        try:
            family = ImageFont.truetype(str(source), 24).getname()[0]
        except OSError as exc:
            raise ValueError(f"Cannot read subtitle font file: {source}") from exc
        normalize = lambda value: re.sub(r"[\s_-]+", "", value).casefold()
        if normalize(family) != normalize(config.render.subtitle_font):
            raise ValueError(
                f"subtitle_font={config.render.subtitle_font!r} does not match the font file's "
                f"family {family!r}; set both explicitly or use subtitle_fonts_dir for a font collection"
            )
        with tempfile.TemporaryDirectory(prefix="film-recap-fonts-") as temporary:
            linked = Path(temporary) / source.name
            try:
                linked.symlink_to(source)
            except OSError:
                shutil.copy2(source, linked)
            yield family, Path(temporary), str(source)
    elif fonts_dir:
        directory = Path(fonts_dir).expanduser().resolve()
        if not directory.is_dir():
            raise ValueError(f"Subtitle fonts directory does not exist: {directory}")
        yield config.render.subtitle_font, directory, None
    else:
        yield config.render.subtitle_font, None, None


def _finalize(
    base_video: Path,
    subtitle_path: Path,
    final_path: Path,
    config: AppConfig,
    *,
    subtitles_expected: bool = True,
) -> str:
    audio_filter = (
        f"loudnorm=I={config.render.target_lufs}:"
        f"TP={config.render.true_peak_db}:LRA=11"
    )
    args: list[str | Path] = ["ffmpeg", "-y", "-v", "info", "-i", base_video]
    has_subtitles = subtitle_path.exists() and subtitle_path.stat().st_size > 0
    if subtitles_expected and not has_subtitles:
        raise ValueError("Expected captions are missing or empty; refusing silent subtitle loss")
    burn_status = "not_requested" if not config.render.subtitle_burn_in else "not_applicable"
    if config.render.subtitle_burn_in and has_subtitles:
        with _subtitle_font_source(config) as (family, fonts_dir, font_file):
            if any(character in family for character in "\n\r,[]'"):
                raise ValueError("Subtitle font family contains unsupported filter/style characters")
            subtitle_filter = f"subtitles='{_escape_subtitle_path(subtitle_path)}':"
            if fonts_dir:
                subtitle_filter += f"fontsdir='{_escape_subtitle_path(fonts_dir)}':"
            subtitle_filter += f"force_style='{_subtitle_style(config, family)}'"
            args.extend(["-vf", subtitle_filter, "-af", audio_filter, *_video_encode_args(config)])
            args.extend([*_audio_encode_args(config), "-movflags", "+faststart", final_path])
            final_path.parent.mkdir(parents=True, exist_ok=True)
            result = run_command(args, timeout=config.runtime.stage_timeout_sec)
            log = (result.stderr or "") + "\n" + (result.stdout or "")
            font_lines = [line for line in log.splitlines() if any(marker in line.lower() for marker in (
                "fontselect:", "glyph", "loading font file", "using font provider", "error opening font",
            ))]
            missing = [line for line in font_lines if re.search(r"failed to find.*glyph|fontselect:.*failed|no usable font", line, re.I)]
            report_path = final_path.with_suffix(".fonts.json")
            write_json(report_path, {"requested_family": config.render.subtitle_font,
                       "resolved_family": family, "font_file": font_file,
                       "fonts_dir": config.render.subtitle_fonts_dir,
                       "font_file_sha256": content_fingerprint(font_file) if font_file else None,
                       "status": "failed" if missing else "applied",
                       "font_selection_log": font_lines, "missing_glyph_errors": missing})
            if missing:
                final_path.unlink(missing_ok=True)
                raise ValueError(
                    "Subtitle font cannot render required glyphs; refusing a tofu-caption final. "
                    "Set render.subtitle_font_file to a readable CJK font, or subtitle_fonts_dir "
                    f"and the correct family. Diagnostics: {report_path}"
                )
        return "applied"
    else:
        args.extend(["-af", audio_filter, "-c:v", "copy"])
    args.extend([*_audio_encode_args(config), "-movflags", "+faststart", final_path])
    final_path.parent.mkdir(parents=True, exist_ok=True)
    run_command(args, timeout=config.runtime.stage_timeout_sec)
    return burn_status


def _make_preview(final_path: Path, preview_path: Path, config: AppConfig) -> None:
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            final_path,
            "-vf",
            "scale=720:1280:force_original_aspect_ratio=decrease,"
            "pad=720:1280:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v",
            config.render.video_codec,
            "-preset",
            "veryfast",
            "-crf",
            "27",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            preview_path,
        ],
        timeout=config.runtime.stage_timeout_sec,
    )


def build_edl(storyboard: Storyboard) -> list[dict[str, Any]]:
    timeline = output_timeline(storyboard)
    timeline_map = {item["segment_id"]: item for item in timeline}
    entries: list[dict[str, Any]] = []
    for segment in storyboard.segments:
        output = timeline_map[segment.segment_id]
        source_spans = []
        cursor = float(output["start"])
        for visual in resolved_visual_spans(segment):
            duration = visual.end - visual.start
            source_spans.append({
                "source_id": visual.source_id, "start": visual.start, "end": visual.end,
                "output_start": cursor, "output_end": cursor + duration,
                "purpose": visual.purpose, "highlight_id": visual.highlight_id,
                "unit_id": getattr(visual, "unit_id", None),
            })
            cursor += duration
        entries.append(
            {
                "segment_id": segment.segment_id,
                "beat_id": segment.beat_id,
                "mode": segment.mode,
                "output_start": output["start"],
                "output_end": output["end"],
                "source_spans": source_spans,
                "text": segment.text,
                "text_raw": segment.text_raw,
                "audio_owner": segment.audio_owner,
                "narration_job": segment.narration_job,
                "reason": segment.notes,
            }
        )
    return entries


def render_storyboard(
    storyboard: Storyboard,
    config: AppConfig,
    work_dir: Path,
) -> Storyboard:
    source_map = _source_map(storyboard)
    segment_dir = work_dir / "clips" / "rendered"
    render_jobs: list[tuple[int, StoryboardSegment, Path]] = []
    for index, segment in enumerate(storyboard.segments, start=1):
        output = segment_dir / f"{index:04d}_{safe_slug(segment.segment_id)}.mp4"
        render_jobs.append((index, segment, output))

    def render_one(job: tuple[int, StoryboardSegment, Path]) -> tuple[int, Path]:
        index, segment, output = job
        if segment.mode == "voiceover":
            _render_voiceover_segment(segment, source_map, output, work_dir, config)
        else:
            _render_original_segment(segment, source_map, output, config)
        segment.status = "rendered"
        segment.rendered_file = str(output)
        segment.rendered_duration_sec = media_duration(output)
        return index, output

    rendered: dict[int, Path] = {}
    workers = max(1, min(config.runtime.max_parallel_ffmpeg, len(render_jobs) or 1))
    if workers == 1:
        for job in render_jobs:
            index, output = render_one(job)
            rendered[index] = output
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(render_one, job): job[0] for job in render_jobs}
            for future in as_completed(futures):
                index, output = future.result()
                rendered[index] = output
    segment_paths = [rendered[index] for index in sorted(rendered)]

    base_video = work_dir / "output" / "base_no_subtitles.mp4"
    _concat_copy(segment_paths, base_video, config)
    cues = build_cues(storyboard, config)
    srt_path = write_srt(cues, work_dir / "subtitles" / "master.srt")
    final_path = work_dir / "output" / "final.mp4"
    burn_status = _finalize(base_video, srt_path, final_path, config, subtitles_expected=bool(cues))
    preview_path = work_dir / "output" / "preview.mp4"
    _make_preview(final_path, preview_path, config)
    edl_path = work_dir / "output" / "edit_decision_list.json"
    write_json(edl_path, build_edl(storyboard))
    review_file = storyboard.output.get("review_file", str(work_dir / "output" / "review_evidence.json"))
    storyboard.output = {
        "base_video": str(base_video),
        "final_video": str(final_path),
        "preview_video": str(preview_path),
        "subtitle": str(srt_path),
        "edl": str(edl_path),
        "duration_sec": media_duration(final_path),
        "final_fingerprint": content_fingerprint(final_path),
        "subtitle_fingerprint": content_fingerprint(srt_path),
        "subtitle_burn_status": burn_status,
        "subtitle_cue_count": len(cues),
        "subtitle_font_report": str(final_path.with_suffix(".fonts.json")) if burn_status == "applied" else None,
        "review_file": review_file,
    }
    return storyboard
