"""The public planner command must remain read-only and reject stale authority."""
from __future__ import annotations

import json

from typer.testing import CliRunner

from douyin_film_recap.cli import app
from douyin_film_recap.models import SourceInfo, Storyboard, StoryboardSegment, VisualReference


def _workspace(tmp_path):
    source = SourceInfo(source_id="s", path="/not-consumed/source.mp4", fingerprint="a" * 64,
                        size_bytes=100, filename="source.mp4", duration=10,
                        width=320, height=240, fps=30)
    board = Storyboard(project_name="fixture", plan_fingerprint="p", target_duration_sec=1,
        sources=[source], segments=[StoryboardSegment(segment_id="c", beat_id="b",
            mode="original", title="fixture", text="", audio_owner="action_sound",
            planned_duration_sec=1, notes="", visuals=[VisualReference(source_id="s", start=0, end=1)])])
    work = tmp_path / "work"
    work.mkdir()
    (work / "09_storyboard.json").write_text(board.model_dump_json(), encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text("models:\n  llm_model: unused\n  vlm_model: unused\n", encoding="utf-8")
    return work, config


def test_render_plan_cli_does_not_write_or_render(tmp_path, monkeypatch):
    work, config = _workspace(tmp_path)
    before = {p.name: p.read_bytes() for p in work.iterdir()}
    import douyin_film_recap.render_plan as planner
    monkeypatch.setattr(planner, "collect_render_inputs", lambda board: {
        "source_identities": {"s": {"sha256": "a" * 64, "size": 100}},
        "toolchain": {"verified": False},
    })
    result = CliRunner().invoke(app, ["render-plan", str(work), "--config", str(config), "--dry-run"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["schema"] == "film-render-plan/1"
    assert data["timeline"]["placement_state"] == "expected"
    assert before == {p.name: p.read_bytes() for p in work.iterdir()}


def test_render_plan_cli_rejects_midread_storyboard_change(tmp_path, monkeypatch):
    work, config = _workspace(tmp_path)
    import douyin_film_recap.render_plan as planner
    def changed(board):
        (work / "09_storyboard.json").write_text('{}', encoding="utf-8")
        return {"source_identities": {"s": {"sha256": "a" * 64, "size": 100}}}
    monkeypatch.setattr(planner, "collect_render_inputs", changed)
    result = CliRunner().invoke(app, ["render-plan", str(work), "--config", str(config)])
    assert result.exit_code == 2
    assert "STALE_AUTHORITY" in result.output
