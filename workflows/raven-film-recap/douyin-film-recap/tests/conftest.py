from __future__ import annotations

import pytest

from douyin_film_recap.config import AppConfig


@pytest.fixture
def app_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "models": {
                "llm_model": "test-llm",
                "vlm_model": "test-vlm",
            },
            "render": {
                "width": 360,
                "height": 640,
                "fps": 24,
                "crf": 28,
                "preset": "ultrafast",
                "subtitle_burn_in": False,
                "subtitle_font_size": 24,
                "subtitle_margin_v": 60,
            },
            "format": {
                "short_range_sec": [10, 30],
                "standard_range_sec": [30, 60],
                "deep_range_sec": [60, 120],
                "original_ratio_range": [0.2, 0.8],
            },
        }
    )
