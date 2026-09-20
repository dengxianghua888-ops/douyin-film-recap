from pathlib import Path
from types import SimpleNamespace

import pytest

from douyin_film_recap import render


def test_explicit_font_requires_matching_family(tmp_path, app_config, monkeypatch):
    font_file = tmp_path / "font.ttf"
    font_file.write_bytes(b"fixture")
    app_config.render.subtitle_font_file = str(font_file)
    app_config.render.subtitle_font = "Requested Family"
    monkeypatch.setattr(render.ImageFont, "truetype", lambda *args: SimpleNamespace(getname=lambda: ("Different Family", "Regular")))
    with pytest.raises(ValueError, match="does not match"):
        with render._subtitle_font_source(app_config):
            pass


def test_missing_explicit_font_does_not_fallback(tmp_path, app_config):
    app_config.render.subtitle_font_file = str(tmp_path / "absent.ttf")
    with pytest.raises(ValueError, match="does not exist"):
        with render._subtitle_font_source(app_config):
            pass


def test_file_and_directory_are_mutually_exclusive(app_config):
    app_config.render.subtitle_font_file = "a.ttf"
    app_config.render.subtitle_fonts_dir = "fonts"
    with pytest.raises(ValueError, match="not both"):
        with render._subtitle_font_source(app_config):
            pass


def test_ffmpeg_success_with_missing_glyphs_is_not_applied(tmp_path, app_config, monkeypatch):
    app_config.render.subtitle_burn_in = True
    subtitle = tmp_path / "caption.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\n中文\n", encoding="utf-8")
    final = tmp_path / "final.mp4"
    def fake_render(args, **kwargs):
        Path(args[-1]).write_bytes(b"unacceptable tofu render")
        return SimpleNamespace(stdout="", stderr="fontselect: failed to find any fallback with glyph 0x4E2D for font: (Missing, 700, 0)", returncode=0)
    monkeypatch.setattr(render, "run_command", fake_render)
    with pytest.raises(ValueError, match="tofu-caption"):
        render._finalize(tmp_path / "base.mp4", subtitle, final, app_config)
    assert not final.exists()
    assert final.with_suffix(".fonts.json").exists()
