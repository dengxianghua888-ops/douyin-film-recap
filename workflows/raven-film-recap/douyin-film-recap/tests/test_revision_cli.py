from __future__ import annotations
import json
from typer.testing import CliRunner
from douyin_film_recap.cli import app


def test_revision_snapshot_cli_is_read_only(tmp_path, monkeypatch):
    import douyin_film_recap.revision as revision
    seen = []
    monkeypatch.setattr(revision, "freeze_revision", lambda path: seen.append(path) or {"schema": "film-revision-base/1"})
    result = CliRunner().invoke(app, ["revision-snapshot", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["schema"] == "film-revision-base/1"
    assert seen == [tmp_path]
    assert list(tmp_path.iterdir()) == []


def test_revise_cli_rejects_domain_bypass(tmp_path, monkeypatch):
    import douyin_film_recap.revision as revision
    called = []
    monkeypatch.setattr(revision, "adopt_revision", lambda *args, **kwargs: called.append(kwargs))
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps({"base": {}, "artifacts": {}, "scope": {}, "kind": "boundary"}))
    result = CliRunner().invoke(app, ["revise", str(tmp_path), "--proposal", str(proposal)])
    assert result.exit_code == 2
    assert "DOMAIN_PROPOSAL_REQUIRES_DEDICATED_VALIDATOR" in result.output
    assert not called


def test_revise_cli_preserves_exact_base_and_scope(tmp_path, monkeypatch):
    import douyin_film_recap.revision as revision
    request = {"base": {"generation": "g"}, "artifacts": {"09_storyboard.json": {}},
               "scope": {"segment_ids": ["s"], "fields": ["notes"]}, "reason": "fix note"}
    called = []
    monkeypatch.setattr(revision, "adopt_revision", lambda *args, **kwargs: called.append(kwargs) or {"status": "ADOPTED"})
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps(request))
    result = CliRunner().invoke(app, ["revise", str(tmp_path), "--proposal", str(proposal)])
    assert result.exit_code == 0, result.output
    assert called == [{**request, "kind": "local"}]


def test_render_current_cli_never_starts_constructor_or_tts(tmp_path, monkeypatch, app_config):
    import douyin_film_recap.cli as cli
    calls = []
    class Current:
        def render_only(self):
            calls.append("render_only")
            return tmp_path / "report.md"
    def from_current(*, work_dir, config, on_update):
        assert work_dir == tmp_path and config is app_config
        calls.append("from_current")
        return Current()
    monkeypatch.setattr(cli, "load_config", lambda path: app_config)
    monkeypatch.setattr(cli.FilmRecapPipeline, "from_current", staticmethod(from_current))
    result = CliRunner().invoke(app, ["render-current", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert calls == ["from_current", "render_only"]
