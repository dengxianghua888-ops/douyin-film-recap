"""Verified, immutable whole-AV cache; no editorial adoption or QC shortcuts.

A COMPLETE manifest is the single atomic publication point. Objects and manifests
are private copies, never writable hardlinks to sources or render outputs. No GC
is implemented: readers cannot race eviction. Corrupt records are retained and
skipped, never overwritten or silently repaired in place.
"""
from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import threading
from typing import Any
from uuid import uuid4

from .render_contracts import (CACHE_SCHEMA, CHECKER_REVISION, RENDERER_REVISION,
    RenderContractError, canonical_bytes, content_binding, digest, ratio, rational, validate_sha)
from .utils import content_identity, run_command


class CachePathError(RenderContractError):
    pass


def safe_directory(path: Path) -> Path:
    path = path.absolute()
    chain = list(reversed([path, *path.parents]))
    for part in chain:
        try:
            mode = part.lstat().st_mode
        except FileNotFoundError:
            try:
                part.mkdir(mode=0o700)
            except FileExistsError:
                pass
            mode = part.lstat().st_mode
        if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
            raise CachePathError(f"CACHE_DIRECTORY_UNSAFE: {part}")
    return path


def _regular(path: Path) -> None:
    for part in [path, *path.parents]:
        mode = part.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise CachePathError(f"CACHE_SYMLINK: {part}")
    mode = path.lstat()
    if not stat.S_ISREG(mode.st_mode):
        raise CachePathError("CACHE_NOT_REGULAR")
    if mode.st_nlink != 1:
        raise CachePathError("CACHE_HARDLINK")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def copy_new(source: Path, destination: Path, expected: dict | None = None) -> dict:
    """Exclusive independent copy, full-byte verification, no linked parents."""
    source, destination = Path(source).absolute(), Path(destination).absolute()
    for part in [source, *source.parents]:
        if part.is_symlink():
            raise CachePathError("INPUT_SYMLINK")
    safe_directory(destination.parent)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    source_fd = os.open(source, flags)
    output_fd = None
    created = False
    try:
        before = os.fstat(source_fd)
        if not stat.S_ISREG(before.st_mode):
            raise CachePathError("INPUT_NOT_REGULAR")
        output_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                            getattr(os, "O_NOFOLLOW", 0), 0o600)
        created = True
        checksum = hashlib.sha256()
        size = 0
        with os.fdopen(source_fd, "rb", closefd=False) as src, os.fdopen(output_fd, "wb", closefd=False) as dst:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                dst.write(chunk)
                checksum.update(chunk)
                size += len(chunk)
            dst.flush()
            os.fsync(output_fd)
        after = os.fstat(source_fd)
        current = source.stat()
        identity = {"sha256": checksum.hexdigest(), "size": size}
        observations = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if observations(before) != observations(after) or observations(before) != observations(current):
            raise RenderContractError("SOURCE_CHANGED_DURING_COPY")
        if expected and identity != content_binding(expected):
            raise RenderContractError("DEPENDENCY_BYTES_CHANGED")
        return identity
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise
    finally:
        os.close(source_fd)
        if output_fd is not None:
            os.close(output_fd)


class VerificationStats:
    def __init__(self):
        self.lock = threading.Lock()
        self.decode_calls = 0
        self.probe_calls = 0

    def add(self, field):
        with self.lock:
            setattr(self, field, getattr(self, field) + 1)


def _probe(path: Path, args: list[str], timeout: int, stats: VerificationStats | None = None) -> dict:
    if stats:
        stats.add("probe_calls")
    return json.loads(run_command(["ffprobe", "-v", "error", *args, "-of", "json", path], timeout=timeout).stdout)


def verify_media(path: Path, params: dict, *, timeout: int = 1800, stats: VerificationStats | None = None) -> dict:
    """Hash, fully decode and measure every selected audio/video frame/packet."""
    started = time.monotonic()
    _regular(path)
    identity = content_identity(path)
    probe = _probe(path, ["-show_streams"], timeout, stats)
    streams = probe.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    if len(videos) != 1 or len(audios) != 1 or len(streams) != 2:
        raise RenderContractError("MEDIA_STREAM_COUNT_MISMATCH")
    video, audio = videos[0], audios[0]
    fps = rational(params["fps"])
    video_tb, audio_tb = rational(video["time_base"]), rational(audio["time_base"])
    codec_names = {"libx264": "h264", "libx265": "hevc", "libaom-av1": "av1", "libvpx-vp9": "vp9"}
    if (video.get("codec_name") != codec_names.get(params["video_codec"], params["video_codec"])
            or audio.get("codec_name") != params["audio_codec"]
            or video.get("width") != params["width"] or video.get("height") != params["height"]
            or video.get("pix_fmt") != "yuv420p" or video.get("sample_aspect_ratio") not in {"1:1", "1/1"}
            or int(audio.get("sample_rate", 0)) != 48000 or audio.get("channels") != 2
            or audio.get("channel_layout") != "stereo" or rational(video["avg_frame_rate"]) != fps):
        raise RenderContractError("MEDIA_CONTRACT_MISMATCH")
    if stats:
        stats.add("decode_calls")
    run_command(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-err_detect", "explode",
                 "-i", path, "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"], timeout=timeout)
    frames = _probe(path, ["-show_frames", "-show_entries", "frame=media_type,best_effort_timestamp,pts,nb_samples"], timeout, stats).get("frames", [])
    vf = [f for f in frames if f.get("media_type") == "video"]
    af = [f for f in frames if f.get("media_type") == "audio"]
    if not vf or not af:
        raise RenderContractError("DECODED_STREAM_EMPTY")
    vtimes = [int(f["best_effort_timestamp"]) * video_tb for f in vf]
    if abs(vtimes[0]) > video_tb or any(abs(t - Fraction(i, 1) / fps) > video_tb for i, t in enumerate(vtimes)):
        raise RenderContractError("VIDEO_PTS_NOT_LOCAL_CFR")
    atimes = [int(f["pts"]) * audio_tb for f in af]
    samples = [int(f["nb_samples"]) for f in af]
    if abs(atimes[0]) > Fraction(1, 48000) or any(n <= 0 for n in samples):
        raise RenderContractError("AUDIO_START_OR_SAMPLES_INVALID")
    if any(abs(atimes[i + 1] - atimes[i] - Fraction(samples[i], 48000)) > Fraction(1, 48000)
           for i in range(len(af) - 1)):
        raise RenderContractError("AUDIO_PTS_DISCONTINUOUS")
    packets = _probe(path, ["-select_streams", "a:0", "-show_packets", "-show_entries",
                           "packet=pts,duration,side_data_list"], timeout, stats).get("packets", [])
    if not packets or any("pts" not in p or "duration" not in p for p in packets):
        raise RenderContractError("AUDIO_PACKET_TIMING_MISSING")
    packet_end = max((int(p["pts"]) + int(p["duration"])) * audio_tb for p in packets)
    presented = packet_end * 48000
    if presented.denominator != 1 or presented <= 0:
        raise RenderContractError("AUDIO_PRESENTATION_NOT_SAMPLE_EXACT")
    decoded_samples = sum(samples)
    padding = decoded_samples - int(presented)
    delay = sum(int(side.get("skip_samples", 0)) for p in packets for side in p.get("side_data_list", []))
    if padding < 0 or padding > max(samples) or delay > 8192:
        raise RenderContractError("AUDIO_PADDING_UNEXPLAINED")
    duration = Fraction(len(vf), 1) / fps
    # One output frame is the documented shadow tolerance; never trim/pad media.
    if abs(Fraction(int(presented), 48000) - duration) > 1 / fps:
        raise RenderContractError("AUDIO_VIDEO_DURATION_DRIFT")
    if abs(duration - rational(params["duration"])) > 1 / fps:
        raise RenderContractError("REALIZED_DURATION_DRIFT")
    contract = {"video_codec": video["codec_name"], "video_profile": video.get("profile"),
        "audio_codec": audio["codec_name"], "audio_profile": audio.get("profile"),
        "width": video["width"], "height": video["height"], "pix_fmt": video["pix_fmt"],
        "sar": video["sample_aspect_ratio"], "fps": ratio(fps), "video_time_base": ratio(video_tb),
        "audio_time_base": ratio(audio_tb), "video_start_pts": int(vf[0]["best_effort_timestamp"]),
        "audio_start_pts": int(af[0]["pts"]), "frame_count": len(vf), "sample_rate": 48000,
        "channel_layout": "stereo", "sample_count": int(presented), "decoded_sample_count": decoded_samples,
        "encoder_delay": delay, "padding": padding, "padding_policy": "decoded-minus-packet-end/1",
        **{name: video.get(name) for name in ("color_primaries", "color_transfer", "color_space", "color_range")}}
    after = content_identity(path)
    if after != identity:
        raise RenderContractError("ARTIFACT_CHANGED_DURING_VERIFICATION")
    return {"sha256": identity["sha256"], "size": identity["bytes"], "media_contract": contract,
        "verification": {"hash_checked": True, "probe_checked": True, "decode_checked": True,
                         "checker_revision": CHECKER_REVISION},
        "verification_seconds": time.monotonic() - started}


class SegmentCache:
    def __init__(self, root: Path, *, timeout: int = 1800):
        self.root = safe_directory(root)
        self.timeout = timeout
        self.stats = VerificationStats()
        info = self.root.stat()
        self.directory_identity = (info.st_dev, info.st_ino)

    def _key_dir(self, key: str) -> Path:
        validate_sha(key)
        safe_directory(self.root)
        info = self.root.stat()
        if (info.st_dev, info.st_ino) != self.directory_identity:
            raise CachePathError("CACHE_ROOT_CHANGED")
        return safe_directory(self.root / key[:2] / key)

    def materialize(self, node: dict, destination: Path) -> tuple[dict | None, list[str]]:
        key = node.get("semantic_key")
        if not key:
            return None, ["PROVISIONAL_KEY"]
        directory = self._key_dir(key)
        reasons = []
        for manifest in sorted(directory.glob("*.json")):
            copied = False
            try:
                _regular(manifest)
                if manifest.stat().st_size > 1024 * 1024:
                    raise RenderContractError("MANIFEST_TOO_LARGE")
                record = json.loads(manifest.read_text(encoding="utf-8"))
                if record.get("schema") != CACHE_SCHEMA or record.get("kind") != "segment_av":
                    raise RenderContractError("SCHEMA_UNSUPPORTED")
                if record.get("nondeterministic_output_digest") != record.get("artifact", {}).get("sha256"):
                    raise RenderContractError("ARTIFACT_DIGEST_CONFLICT")
                if (record.get("semantic_key") != key or record.get("completion_state") != "COMPLETE"
                        or record.get("renderer_revision") != RENDERER_REVISION
                        or record.get("params_digest") != digest(node["params"])
                        or record.get("input_artifacts") != node["inputs"]
                        or record.get("source_bindings") != node["params"]["sources"]
                        or record.get("toolchain_digest") != node["toolchain_digest"]):
                    raise RenderContractError("DEPENDENCY_BYTES_CHANGED")
                relative = record.get("artifact", {}).get("relative_path", "")
                if not re.fullmatch(r"[0-9a-f]{32}\.mp4", relative):
                    raise CachePathError("CACHE_PATH_TRAVERSAL")
                artifact = directory / relative
                _regular(artifact)
                copy_new(artifact, destination, record["artifact"])
                copied = True
                actual = verify_media(destination, node["params"], timeout=self.timeout, stats=self.stats)
                if actual["media_contract"] != record.get("media_contract"):
                    raise RenderContractError("MEDIA_CONTRACT_MISMATCH")
                actual["semantic_key"] = key
                actual["cache_manifest"] = str(manifest)
                return actual, reasons
            except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
                if copied:
                    destination.unlink(missing_ok=True)
                if isinstance(exc, FileExistsError):
                    raise  # Never delete or overwrite an existing caller output.
                reasons.append(str(exc).split(":", 1)[0] or type(exc).__name__)
        return None, reasons or ["MISSING"]

    def publish(self, node: dict, artifact: Path, verified: dict, *, attempt_id: str) -> Path:
        key = validate_sha(node.get("semantic_key"))
        if not all(verified.get("verification", {}).get(k) is True for k in ("hash_checked", "probe_checked", "decode_checked")):
            raise RenderContractError("CANNOT_PUBLISH_UNVERIFIED")
        directory = self._key_dir(key)
        nonce = uuid4().hex
        object_path = directory / f"{nonce}.mp4"
        copy_new(artifact, object_path, verified)
        record = {"schema": CACHE_SCHEMA, "kind": "segment_av", "semantic_key": key,
            "renderer_revision": RENDERER_REVISION, "input_artifacts": node["inputs"],
            "params_digest": digest(node["params"]), "source_bindings": node["params"]["sources"],
            "toolchain_digest": node["toolchain_digest"], "nondeterministic_output_digest": verified["sha256"], "artifact": {"relative_path": object_path.name,
                **content_binding(verified), "media_type": "video/mp4"},
            "media_contract": verified["media_contract"], "verification": verified["verification"],
            "completion_state": "COMPLETE", "completed_at": datetime.now(timezone.utc).isoformat(),
            "origin_attempt": attempt_id}
        staging, published = directory / f".{nonce}.pending", directory / f"{nonce}.json"
        try:
            with staging.open("xb") as handle:
                handle.write(canonical_bytes(record))
                handle.flush()
                os.fsync(handle.fileno())
            _fsync_directory(directory)
            # Atomic no-clobber publication. A unique immutable manifest is the commit.
            os.link(staging, published, follow_symlinks=False)
            staging.unlink()
            _fsync_directory(directory)
        finally:
            staging.unlink(missing_ok=True)
        return published


def verify_assembly_placement(path: Path, timeline: list[dict], fps_value: Any, *, timeout: int = 1800) -> None:
    """Reject concat clocks that cannot justify frame-grid subtitle placement.

    Existing concat/AAC behavior is preserved, never silently repaired here.
    The bounded shadow tolerance is one output frame over the entire assembly.
    Final CFR normalization and the existing post-QC remain mandatory.
    """
    fps = rational(fps_value)
    frames = _probe(path, ["-select_streams", "v:0", "-show_frames", "-show_entries",
                          "frame=best_effort_timestamp_time"], timeout).get("frames", [])
    count = timeline[-1]["end_frame"]
    if len(frames) != count:
        raise RenderContractError("ASSEMBLY_FRAME_COUNT_CHANGED")
    times = [rational(f["best_effort_timestamp_time"]) for f in frames]
    if any(b <= a for a, b in zip(times, times[1:])) or any(
            abs(t - Fraction(i, 1) / fps) > 1 / fps for i, t in enumerate(times)):
        raise RenderContractError("ASSEMBLY_PLACEMENT_DRIFT")
