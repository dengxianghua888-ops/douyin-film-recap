from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .utils import fingerprint_json


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class EditorialBrief(FlexibleModel):
    narrative_question: str = ""
    audience_knowledge: list[str] = Field(default_factory=list)
    stance: str = ""
    preserve: list[str] = Field(default_factory=list)
    avoid_phrases: list[str] = Field(default_factory=list)
    ending_payoff: str = ""
    spoiler_policy: Literal["preserve", "allow"] = "preserve"
    spoiler_reason: str = ""


class ProjectConfig(FlexibleModel):
    language: str = "zh-CN"
    platform: str = "douyin"
    rights_confirmed: bool = False
    publish_mode: str = "draft"
    context_file: str | None = None
    editorial_brief: EditorialBrief = Field(default_factory=EditorialBrief)


class ModelConfig(FlexibleModel):
    provider: str = "openai_compatible"
    base_url_env: str = "FILM_RECAP_BASE_URL"
    api_key_env: str = "FILM_RECAP_API_KEY"
    llm_model: str
    vlm_model: str
    timeout_sec: float = 180
    max_retries: int = 3
    temperature: dict[str, float] = Field(
        default_factory=lambda: {"analysis": 0.1, "creative": 0.45, "qc": 0.0}
    )

    def base_url(self) -> str:
        value = os.getenv(self.base_url_env, "").strip()
        if not value:
            raise ValueError(f"Missing environment variable: {self.base_url_env}")
        return value.rstrip("/")

    def api_key(self) -> str:
        value = os.getenv(self.api_key_env, "").strip()
        if not value:
            raise ValueError(f"Missing environment variable: {self.api_key_env}")
        return value


class ASRConfig(FlexibleModel):
    provider: str = "faster_whisper"
    model: str = "large-v3"
    device: str = "auto"
    compute_type: str = "auto"
    language: str = "zh"
    prefer_sidecar_subtitle: bool = True
    prefer_embedded_subtitle: bool = True
    word_timestamps: bool = True
    beam_size: int = 5


class SceneConfig(FlexibleModel):
    detector: str = "scenedetect"
    content_threshold: float = 27.0
    min_shot_sec: float = 0.45
    min_unit_sec: float = 4.0
    max_unit_sec: float = 16.0
    sample_frames_per_unit: int = 3
    contact_sheet_units: int = 8
    max_scene_analysis_workers: int = 2


class StoryConfig(FlexibleModel):
    chunk_units: int = 32
    character_confidence_threshold: float = 0.68
    story_confidence_threshold: float = 0.72
    allow_external_context: bool = False


class HighlightConfig(FlexibleModel):
    candidate_pool_size: int = 80
    rerank_top_k: int = 36
    final_pool_size: int = 24
    min_confidence: float = 0.62
    max_same_type_ratio: float = 0.45
    max_same_character_ratio: float = 0.65
    max_redundancy: float = 0.35
    allow_hook_reuse: bool = True
    genre_profile: str = "auto"


class FormatConfig(FlexibleModel):
    duration_mode: Literal["auto", "highlight", "short", "standard", "deep", "series"] = "auto"
    content_unit: Literal["auto", "scene", "relationship", "episode", "film", "series"] = "auto"
    highlight_range_sec: tuple[int, int] = (30, 90)
    # Preserve v0.1 short/standard/deep meanings for existing configurations.
    short_range_sec: tuple[int, int] = (180, 360)
    standard_range_sec: tuple[int, int] = (360, 600)
    deep_range_sec: tuple[int, int] = (600, 1200)
    first_highlight_deadline_sec: float = 6
    original_ratio_range: tuple[float, float] = (0.25, 0.45)
    original_clip_range_sec: tuple[float, float] = (4.0, 12.0)
    max_original_over_15s: int = 2
    micro_cycle_sec: tuple[float, float] = (12, 25)
    reset_interval_sec: tuple[float, float] = (45, 75)
    vo_chars_per_sec: tuple[float, float] = (4.2, 5.2)
    default_ending: str = "payoff"
    allow_cta: bool = False
    visual_pool_size: int = Field(default=160, ge=12)


class TTSConfig(FlexibleModel):
    provider: str = "edge_tts"
    voice: str = "zh-CN-YunxiNeural"
    rate: str = "+10%"
    pitch: str = "+0Hz"
    volume: str = "+0%"
    max_speedup: float = 1.08
    min_speedup: float = 0.95


class RenderConfig(FlexibleModel):
    width: int = 1080
    height: int = 1920
    fps: int = 30
    video_codec: str = "libx264"
    crf: int = 19
    preset: str = "medium"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    layout: str = "safe_fit_blur"
    blur_sigma: int = 28
    original_bed_db: float = -26
    target_lufs: float = -14
    true_peak_db: float = -1.5
    subtitle_burn_in: bool = True
    subtitle_font: str = "Noto Sans CJK SC"
    # An explicit file bypasses discovery; subtitle_font must match its family.
    subtitle_font_file: str | None = None
    # Additional libass font discovery directory (mutually exclusive with file).
    subtitle_fonts_dir: str | None = None
    subtitle_font_size: int = 62
    subtitle_margin_v: int = 250
    subtitle_max_chars_per_line: int = 16
    subtitle_max_lines: int = 2
    subtitle_outline: int = 3


class QCConfig(FlexibleModel):
    self_repair_rounds: int = 2
    fail_on_sentence_cut: bool = True
    fail_on_tts_truncation: bool = True
    fail_on_missing_audio: bool = True
    allow_semantic_qc_failure: bool = True
    max_black_ratio: float = 0.02
    max_silence_ratio: float = 0.18
    duration_tolerance_sec: float = 1.2


class RuntimeConfig(FlexibleModel):
    cache: bool = True
    keep_debug_frames: bool = True
    max_parallel_ffmpeg: int = 2
    stage_timeout_sec: int = 1800


class AppConfig(FlexibleModel):
    version: int = 1
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    models: ModelConfig
    asr: ASRConfig = Field(default_factory=ASRConfig)
    scene: SceneConfig = Field(default_factory=SceneConfig)
    story: StoryConfig = Field(default_factory=StoryConfig)
    highlight: HighlightConfig = Field(default_factory=HighlightConfig)
    format: FormatConfig = Field(default_factory=FormatConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    render: RenderConfig = Field(default_factory=RenderConfig)
    qc: QCConfig = Field(default_factory=QCConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

    def fingerprint(self) -> str:
        return fingerprint_json(
            {
                "config": self.model_dump(mode="json"),
                "explicit_format_fields": sorted(self.format.model_fields_set),
            }
        )


def load_dotenv_near(config_path: Path) -> None:
    env_path = config_path.parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    load_dotenv_near(config_path)
    data: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(data)
