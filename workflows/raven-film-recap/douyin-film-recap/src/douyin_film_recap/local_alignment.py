"""Explicit, CPU-only local Wav2Vec2 CTC execution. Never imported by normal runs.

Model-derived boundaries are observations, not recognition accuracy. No downloads,
custom model code, pickle weights, interpolation, or automatic pipeline adoption.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np

from .alignment import AlignmentCue, AlignmentResult, AlignmentToken, import_alignment
from .asr import _TOKEN_RE, parse_subtitle
from .models import SourceInfo
from .utils import SourceChangedDuringRead, content_identity

REQUIRED_FILES = {"config.json", "preprocessor_config.json", "vocab.json", "model.safetensors"}
ALLOWED_FILES = REQUIRED_FILES | {"README.md", "LICENSE", "LICENSE.txt", "NOTICE"}
SELF_CONTAINED_DEMUXERS = "wav,flac,mp3,ogg,mov,matroska,webm,avi,aac,mpeg,mpegts"
MAX_WINDOW_SECONDS = 30.0
MAX_CTC_CELLS = 5_000_000


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def model_identity(directory: Path) -> str:
    """Content pin for a deliberately small, unsharded safe local model layout."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("A real local model directory is required")
    members = list(directory.iterdir())
    if {p.name for p in members} - ALLOWED_FILES or not REQUIRED_FILES <= {p.name for p in members}:
        raise ValueError("Model requires config/preprocessor/vocab and unsharded model.safetensors; "
                         "extra executable, pickle, tokenizer, shard or adapter files are unsupported")
    if any(p.is_symlink() or not p.is_file() for p in members):
        raise ValueError("Model members must be regular files, not symlinks")
    return digest({p.name: content_identity(p) for p in sorted(members)})


def ctc_spans(log_probs: np.ndarray, labels: list[int], blank: int) -> list[tuple[int, int, float]]:
    """Exact constrained CTC Viterbi path, including blank between repeated labels.

    Returns half-open frame spans and mean emission posterior, without interpolation.
    An impossible path raises; callers retain estimated whole-cue boundaries.
    """
    values = np.asarray(log_probs, dtype=np.float64)
    if (values.ndim != 2 or not np.isfinite(values).all() or not labels
            or not 0 <= blank < values.shape[1]
            or any(type(x) is not int or not 0 <= x < values.shape[1] or x == blank for x in labels)):
        raise ValueError("Invalid finite CTC emissions or labels")
    frames = len(values)
    states = [blank]
    for label in labels:
        states.extend([label, blank])
    if frames * len(states) > MAX_CTC_CELLS:
        raise ValueError("CTC window exceeds bounded trellis size")
    if frames < len(labels) + sum(a == b for a, b in zip(labels, labels[1:])):
        raise ValueError("Insufficient CTC frames")
    previous = np.full(len(states), -np.inf)
    previous[0], previous[1] = values[0, blank], values[0, labels[0]]
    back = np.zeros((frames, len(states)), dtype=np.uint8)
    for t in range(1, frames):
        current = previous.copy()
        steps = np.zeros(len(states), dtype=np.uint8)
        better = previous[:-1] > current[1:]
        current[1:] = np.maximum(current[1:], previous[:-1])
        steps[1:][better] = 1
        allowed = np.array([s != blank and s != states[i - 2]
                            for i, s in enumerate(states)][2:])
        better = allowed & (previous[:-2] > current[2:])
        current[2:][better] = previous[:-2][better]
        steps[2:][better] = 2
        previous = current + values[t, states]
        back[t] = steps
    state = len(states) - (1 if previous[-1] >= previous[-2] else 2)
    if not np.isfinite(previous[state]):
        raise ValueError("No complete CTC path")
    path = np.empty(frames, dtype=np.int32)
    for t in range(frames - 1, -1, -1):
        path[t] = state
        state -= int(back[t, state])
    result = []
    for i, label in enumerate(labels):
        indices = np.flatnonzero(path == 2 * i + 1)
        if not len(indices):
            raise ValueError("Missing native CTC label")
        result.append((int(indices[0]), int(indices[-1]) + 1,
                       float(np.exp(values[indices, label]).mean())))
    return result


def frame_edges(samples: int, kernels: list[int], strides: list[int], frames: int) -> np.ndarray:
    """Cells split at convolution-frame center midpoints, bounded by actual samples."""
    length, step, receptive = samples, 1, 1
    for kernel, stride in zip(kernels, strides, strict=True):
        length = (length - kernel) // stride + 1
        receptive += (kernel - 1) * step
        step *= stride
    if length != frames or frames < 1:
        raise ValueError("Acoustic frame/sample geometry mismatch")
    return np.array([0.0] + [receptive / 2 + (i - .5) * step for i in range(1, frames)]
                    + [float(samples)])


def _load_model(directory: Path):
    # Deliberately concrete classes; no Auto*, remote code, processor plugins or pickle.
    try:
        import torch
        from transformers import Wav2Vec2Config, Wav2Vec2FeatureExtractor, Wav2Vec2ForCTC
    except ImportError as exc:
        raise RuntimeError("Install the explicit local-alignment extra before execution") from exc
    config = Wav2Vec2Config.from_json_file(str(directory / "config.json"))
    if config.model_type != "wav2vec2" or config.add_adapter or getattr(config, "auto_map", None):
        raise ValueError("Only standard Wav2Vec2 CTC without adapters/custom code is supported")
    model, loading = Wav2Vec2ForCTC.from_pretrained(str(directory), config=config,
        local_files_only=True, use_safetensors=True, trust_remote_code=False,
        output_loading_info=True)
    if any(loading.get(key) for key in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")):
        raise ValueError("Incomplete or mismatched acoustic weights")
    model.cpu().eval()
    extractor = Wav2Vec2FeatureExtractor.from_pretrained(str(directory), local_files_only=True)
    if extractor.sampling_rate != 16000:
        raise ValueError("Only explicit 16000 Hz models are supported")
    vocab = json.loads((directory / "vocab.json").read_text(encoding="utf-8"))
    if (not isinstance(vocab, dict) or len(vocab) != config.vocab_size
            or set(vocab.values()) != set(range(config.vocab_size))
            or any(type(v) is not int for v in vocab.values())
            or type(config.pad_token_id) is not int or not 0 <= config.pad_token_id < len(vocab)):
        raise ValueError("Model vocabulary/CTC blank mismatch")
    return torch, model, extractor, vocab


def _audio_window(ffmpeg: str, source: Path, start: float, duration: float) -> np.ndarray:
    # Whitelist the actual demuxer, not the filename. Local-file protocols alone
    # still permit concat/HLS playlists whose referenced bytes are not source-bound.
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("Local FFprobe required")
    probe = subprocess.run([ffprobe, "-v", "error", "-protocol_whitelist", "file",
        "-format_whitelist", SELF_CONTAINED_DEMUXERS, "-show_entries", "format=format_name",
        "-of", "json", "-i", str(source)], capture_output=True, timeout=30, check=True)
    formats = json.loads(probe.stdout)["format"]["format_name"].split(",")
    # These are MOV-private options; passing them to WAV fails in FFmpeg.
    demux_options = ["-enable_drefs", "0", "-use_absolute_path", "0"] if "mov" in formats else []
    # Only selected audio is decoded into memory. Repeat allowlist at decode time.
    result = subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-protocol_whitelist", "file",
        "-format_whitelist", SELF_CONTAINED_DEMUXERS, *demux_options, "-ss", str(start), "-i", str(source), "-t", str(duration), "-map", "0:a:0",
        "-vn", "-sn", "-dn", "-ac", "1", "-ar", "16000", "-f", "f32le", "pipe:1"],
        capture_output=True, timeout=90, check=True)
    waveform = np.frombuffer(result.stdout, dtype="<f4").copy()
    expected = round(duration * 16000)
    if not len(waveform) or abs(len(waveform) - expected) > 1 or not np.isfinite(waveform).all():
        raise ValueError("Selected audio window is truncated, nonfinite or has unexpected length")
    return waveform


def run_local_alignment(*, source: SourceInfo, cue_indices: list[int], model_dir: Path,
                        model_sha256: str, output: Path, cache_dir: Path | None = None) -> dict:
    """Explicit one-shot producer; outputs must still pass normal import/adoption gates."""
    output, model_dir = Path(output), Path(model_dir)
    if model_dir.is_symlink():
        raise ValueError("Model directory symlinks are unsupported")
    model_dir = model_dir.resolve()
    if output.exists():
        raise FileExistsError("Alignment output already exists")
    if not source.has_audio or not source.subtitle_path:
        raise ValueError("Existing audio and subtitles required")
    if (not cue_indices or any(type(i) is not int or i < 0 for i in cue_indices)
            or len(set(cue_indices)) != len(cue_indices)):
        raise ValueError("Select unique nonnegative subtitle cue indices explicitly")
    selected = sorted(cue_indices)
    media = content_identity(source.path)
    subtitle = content_identity(source.subtitle_path)
    if source.fingerprint != media["sha256"] or (source.subtitle_fingerprint is not None
            and source.subtitle_fingerprint != subtitle["sha256"]):
        raise ValueError("Manifest input identity mismatch")
    identity = model_identity(model_dir)
    if identity != model_sha256:
        raise ValueError("Local model content pin mismatch")
    segments = parse_subtitle(source.subtitle_path, source.source_id)
    if any(i >= len(segments) for i in selected):
        raise ValueError("Selected cue outside subtitle")
    for i in selected:
        cue = segments[i]
        if not 0 < cue.end - cue.start <= MAX_WINDOW_SECONDS or cue.end > source.duration:
            raise ValueError("Selected whole cue must fit media and maximum 30-second window")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("Local FFmpeg and FFprobe required")
    versions = {name: importlib.metadata.version(name) for name in
                ("torch", "transformers", "numpy", "safetensors")}
    implementation = digest({name: content_identity(Path(__file__).with_name(name)) for name in
                             ("local_alignment.py", "alignment.py", "asr.py", "models.py", "utils.py")})
    key = digest({"schema": "film-local-ctc-cache/1", "media": media, "subtitle": subtitle,
                  "source_id": source.source_id, "duration": source.duration,
                  "model": identity, "selected": selected, "implementation": implementation,
                  "versions": versions, "ffmpeg": content_identity(ffmpeg),
                  "ffprobe": content_identity(ffprobe), "device": "cpu"})
    cache_file = Path(cache_dir) / f"{key}.json" if cache_dir is not None else None
    cache_hit = bool(cache_file and cache_file.exists())
    if cache_hit:
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        if cached.get("key") != key or digest(cached.get("result")) != cached.get("result_sha256"):
            raise ValueError("Corrupt alignment cache; no automatic inference fallback")
        result = AlignmentResult.model_validate(cached["result"])
    else:
        torch, model, extractor, vocab = _load_model(model_dir)
        cues = []
        for i in selected:
            cue = segments[i]
            matches = list(_TOKEN_RE.finditer(cue.text))
            tokens = [AlignmentToken(text=m.group(), status="missing") for m in matches]
            chars = [(j, c) for j, c in enumerate(cue.text) if not c.isspace()]
            overlap = any(j != i and s.start < cue.end and cue.start < s.end
                          for j, s in enumerate(segments))
            known = bool(chars) and all(c in vocab and vocab[c] != model.config.pad_token_id
                                        for _, c in chars)
            if known and not overlap:
                waveform = _audio_window(ffmpeg, Path(source.path), cue.start, cue.end - cue.start)
                # Exact/near digital silence cannot supply acoustic boundary evidence.
                if float(np.sqrt(np.mean(waveform.astype(np.float64) ** 2))) > 1e-5:
                    expected_frames = len(waveform)
                    for kernel, stride in zip(model.config.conv_kernel, model.config.conv_stride, strict=True):
                        expected_frames = (expected_frames - kernel) // stride + 1
                    if (expected_frames < 1 or expected_frames > 4000
                            or expected_frames * (2 * len(chars) + 1) > MAX_CTC_CELLS):
                        raise ValueError("Selected window exceeds bounded acoustic/CTC frame budget")
                    inputs = extractor(waveform, sampling_rate=16000, return_tensors="pt")
                    with torch.inference_mode():
                        logits = model(**inputs).logits[0]
                        log_probs = torch.log_softmax(logits, dim=-1).cpu().numpy()
                    edges = frame_edges(len(waveform), model.config.conv_kernel,
                                        model.config.conv_stride, len(log_probs)) / 16000 + cue.start
                    edges = np.minimum(edges, cue.end)
                    try:
                        spans = ctc_spans(log_probs, [vocab[c] for _, c in chars],
                                          model.config.pad_token_id)
                    except ValueError as exc:
                        if str(exc) not in {"Insufficient CTC frames", "No complete CTC path"}:
                            raise
                    else:
                        positions = {pos: span for (pos, _), span in zip(chars, spans, strict=True)}
                        tokens = []
                        for match in matches:
                            covered = [positions[j] for j in range(match.start(), match.end())]
                            tokens.append(AlignmentToken(text=match.group(), status="observed",
                                start=float(edges[covered[0][0]]), end=float(edges[covered[-1][1]]),
                                score=sum(s[2] for s in covered) / len(covered)))
            cues.append(AlignmentCue(cue_index=i, text=cue.text, start=cue.start, end=cue.end,
                                     tokens=tokens))
        result = AlignmentResult(source_id=source.source_id, media_sha256=media["sha256"],
            subtitle_sha256=subtitle["sha256"], producer="local-wav2vec2-ctc",
            producer_revision=f"sha256:{implementation}", model="local-wav2vec2-ctc",
            model_revision=f"sha256:{identity}", method="ctc-viterbi-native-frame-cells/1",
            score_semantics="mean native label emission posterior; not recognition accuracy",
            cues=cues)
    # Validate current bindings and full contract before publishing either artifact.
    if (content_identity(source.path) != media or content_identity(source.subtitle_path) != subtitle
            or model_identity(model_dir) != identity):
        raise SourceChangedDuringRead("Local alignment inputs changed during execution")
    if ([cue.cue_index for cue in result.cues] != selected
            or result.model_revision != f"sha256:{identity}"
            or result.producer_revision != f"sha256:{implementation}"):
        raise ValueError("Alignment cache producer/model/selection mismatch")
    with tempfile.TemporaryDirectory(prefix="film-ctc-validate-") as directory:
        candidate = Path(directory) / "result.json"
        candidate.write_text(result.model_dump_json(), encoding="utf-8")
        adopted = import_alignment(candidate, source, segments)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(result.model_dump_json(indent=2) + "\n")
    if cache_file and not cache_hit:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = result.model_dump()
        with cache_file.open("x", encoding="utf-8") as handle:
            json.dump({"key": key, "result_sha256": digest(payload), "result": payload}, handle,
                      ensure_ascii=False, allow_nan=False)
    return {"output": str(output), "cache_hit": cache_hit, "cache_key": key,
            "selected_cues": selected, "versions": versions,
            "aligned_cues": sum(bool(s.alignment and s.alignment["status"] == "aligned")
                                for s in adopted), "recognition_accuracy": "NOT_VERIFIED",
            "chinese_speech_quality": "NOT_VERIFIED"}
