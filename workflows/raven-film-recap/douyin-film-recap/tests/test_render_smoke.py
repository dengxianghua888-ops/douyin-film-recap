from __future__ import annotations

import shutil
import json
from fractions import Fraction
from pathlib import Path

import pytest

from douyin_film_recap.models import (
    SourceInfo,
    Storyboard,
    StoryboardSegment,
    VisualReference,
)
from douyin_film_recap.render import render_storyboard
from douyin_film_recap.utils import run_command

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg is required",
)


def test_render_two_segment_smoke(tmp_path: Path, app_config) -> None:
    source = tmp_path / "source.mp4"
    narration = tmp_path / "narration.m4a"
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
    run_command(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=660:sample_rate=48000:duration=1",
            "-c:a",
            "aac",
            narration,
        ]
    )
    source_info = SourceInfo(
        source_id="src_001",
        path=str(source),
        fingerprint="fixture",
        filename=source.name,
        duration=4,
        width=640,
        height=360,
        fps=24,
        has_audio=True,
    )
    storyboard = Storyboard(
        project_name="smoke",
        sources=[source_info],
        plan_fingerprint="p",
        target_duration_sec=2,
        segments=[
            StoryboardSegment(
                segment_id="s1",
                beat_id="b1",
                mode="original",
                title="原声",
                text="原声",
                text_raw="原声",
                visuals=[VisualReference(source_id="src_001", start=0, end=1)],
                audio_owner="original_dialogue",
                planned_duration_sec=1,
                notes="保留原声",
            ),
            StoryboardSegment(
                segment_id="s2",
                beat_id="b2",
                mode="voiceover",
                title="解说",
                text="危险刚刚开始",
                visuals=[VisualReference(source_id="src_001", start=1, end=2)],
                audio_owner="narration",
                narration_job="foreshadow",
                mute_original=True,
                planned_duration_sec=1,
                audio_file=str(narration),
                audio_duration_sec=1,
                notes="用动作画面承接解说",
            ),
        ],
    )
    result = render_storyboard(storyboard, app_config, tmp_path / "work")
    final = Path(result.output["final_video"])
    assert final.exists()
    assert final.stat().st_size > 0


def test_render_voiceover_with_ducked_original_bed(tmp_path: Path, app_config) -> None:
    source = tmp_path / "source_bed.mp4"
    narration = tmp_path / "narration_bed.m4a"
    run_command(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", source,
        ]
    )
    run_command(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", "sine=frequency=770:sample_rate=48000:duration=1",
            "-c:a", "aac", narration,
        ]
    )
    source_info = SourceInfo(
        source_id="src_001", path=str(source), fingerprint="fixture",
        filename=source.name, duration=2, width=640, height=360, fps=24, has_audio=True,
    )
    storyboard = Storyboard(
        project_name="bed", sources=[source_info], plan_fingerprint="p",
        target_duration_sec=1,
        segments=[
            StoryboardSegment(
                segment_id="s1", beat_id="b1", mode="voiceover", title="解说",
                text="危险正在逼近",
                visuals=[VisualReference(source_id="src_001", start=0, end=1)],
                audio_owner="narration", narration_job="foreshadow",
                mute_original=False, planned_duration_sec=1,
                audio_file=str(narration), audio_duration_sec=1,
                notes="保留低电平环境声",
            )
        ],
    )
    result = render_storyboard(storyboard, app_config, tmp_path / "work_bed")
    final = Path(result.output["final_video"])
    assert final.exists() and final.stat().st_size > 0


def test_mixed_pcm_narration_concat_keeps_configured_final_frame_rate(tmp_path: Path, app_config) -> None:
    """AAC container offsets must not survive the final video as irregular PTS."""
    config = app_config.model_copy(deep=True)
    config.render.width = config.render.height = 64
    config.render.fps = 25
    source = tmp_path / 'source.mp4'
    narration = tmp_path / 'narration.wav'
    run_command(['ffmpeg', '-n', '-v', 'error', '-f', 'lavfi', '-i',
                 'color=c=red:s=64x64:r=25:d=12', '-f', 'lavfi', '-i',
                 'sine=frequency=440:sample_rate=48000:duration=12',
                 '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', source])
    run_command(['ffmpeg', '-n', '-v', 'error', '-f', 'lavfi', '-i',
                 'sine=frequency=660:sample_rate=48000:duration=4', '-c:a', 'pcm_s16le', narration])
    info = SourceInfo(source_id='src', path=str(source), fingerprint='fixture', filename=source.name,
                      duration=12, width=64, height=64, fps=25, has_audio=True)
    segments = []
    for index in range(3):
        original = index == 0
        segments.append(StoryboardSegment(segment_id=f's{index}', beat_id=f'b{index}',
            mode='original' if original else 'voiceover', title='synthetic', text='test',
            text_raw='test' if original else '', visuals=[VisualReference(source_id='src', start=index*4, end=(index+1)*4)],
            audio_owner='original_dialogue' if original else 'narration', planned_duration_sec=4,
            audio_file=None if original else str(narration), audio_duration_sec=None if original else 4,
            mute_original=not original, notes=''))
    result = render_storyboard(Storyboard(project_name='CFR regression', sources=[info],
        plan_fingerprint='fixture', target_duration_sec=12, segments=segments), config, tmp_path/'task')
    final = Path(result.output['final_video'])
    probe = json.loads(run_command(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', final]).stdout)
    video = next(stream for stream in probe['streams'] if stream['codec_type']=='video')
    assert float(Fraction(video['avg_frame_rate'])) == pytest.approx(config.render.fps, abs=0.001)
    frames = json.loads(run_command(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', final]).stdout)['frames']
    times = [float(frame['best_effort_timestamp_time']) for frame in frames]
    assert all(b-a == pytest.approx(1/config.render.fps, abs=0.0001) for a,b in zip(times,times[1:]))
