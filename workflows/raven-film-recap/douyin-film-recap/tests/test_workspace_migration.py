from pathlib import Path
import json
import os
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from douyin_film_recap import workspace as w
from douyin_film_recap.cli import app
from douyin_film_recap.pipeline import FilmRecapPipeline

REPO = Path(__file__).resolve().parents[4]
BINDING = {"input_paths": ["/synthetic/source.mp4"], "input_fingerprint": "full-source-v2",
           "config_fingerprint": "runtime-v2"}


@pytest.fixture
def recovery_bundle(tmp_path):
    out = tmp_path / "只读 B package"
    result = subprocess.run([sys.executable, str(REPO / "scripts/build_film_recovery_bundle.py"),
                             "--out", str(out)], text=True, capture_output=True, check=True)
    return out, json.loads(result.stdout)["package_sha256"]


def legacy(tmp_path):
    root = tmp_path / "old"
    root.mkdir()
    hand = root / "09_storyboard.json"
    hand.write_bytes(b'{"manual":"keep these exact bytes"}\n')
    w.atomic(root / "state.json", {"schema_version": 1, "project_name": "fixture",
        "input_fingerprint": "sampled-old", "config_fingerprint": "old-config",
        "stages": {"storyboard": {"status": "passed", "artifacts": {str(hand): "old-recorded-sha"}}}})
    return root, hand


def migrate(root, bundle, **kwargs):
    return w.prepare(root, BINDING, allow_legacy=True, recovery_bundle=bundle[0],
                     recovery_bundle_sha256=bundle[1], **kwargs)


def test_hand_bytes_original_receipt_and_external_final_preserved(tmp_path, recovery_bundle):
    root, hand = legacy(tmp_path)
    final = tmp_path / "outside-last-valid.mp4"
    final.write_bytes(b"generated-final-media-fixture")
    raw = w.read(root / "state.json")
    raw["stages"]["render"] = {"status": "passed", "artifacts": {str(final): w.sha(final)}}
    w.atomic(root / "state.json", raw)
    original = hand.read_bytes()
    _, active, manifest = migrate(root, recovery_bundle)
    assert active != root and hand.read_bytes() == original
    assert all(r["status"] == "pending" for r in w.read(active / "state.json")["stages"].values())
    row = next(r for r in manifest["files"] if r["path"] == hand.name)
    assert row["recorded_sha256"] == "old-recorded-sha"
    assert row["observed_sha256"] == w.sha(hand)
    archive = Path(w.read(active / "state.json")["recovery_manifest"]).parent
    external = next(r for r in manifest["files"] if r["original_path"] == str(final))
    assert (archive / "files" / external["path"]).read_bytes() == final.read_bytes()
    restored = tmp_path / "independent recovered"
    assert w.recover(archive, restored)["production_authorized"] is False
    assert (restored / hand.name).read_bytes() == original
    assert w.read(restored / "state.json")["schema_version"] == 1


@pytest.mark.parametrize("point", ["copied", "archived", "prepared", "switched"])
def test_interruption_and_repeat_are_idempotent(tmp_path, recovery_bundle, point):
    root, hand = legacy(tmp_path)
    original = hand.read_bytes()
    def interrupt(name):
        if name == point:
            raise RuntimeError("controlled interruption")
    with pytest.raises(RuntimeError, match="controlled"):
        migrate(root, recovery_bundle, interrupt=interrupt)
    _, active, _ = migrate(root, recovery_bundle)
    _, again, _ = migrate(root, recovery_bundle)
    assert active == again and hand.read_bytes() == original
    complete = [p for p in (root / ".migrations").iterdir() if not p.name.startswith(".")]
    assert len(complete) == 1
    assert w.read(complete[0] / "migration-status.json")["status"] == "SWITCHED"


@pytest.mark.parametrize("mutation,error", [("manual", "MIGRATION_INPUT_CHANGED"),
    ("pointer", "MIGRATION_POINTER_CHANGED"), ("candidate", "PREPARED_GENERATION_CHANGED")])
def test_compare_all_members_before_switch(tmp_path, recovery_bundle, mutation, error):
    root, hand = legacy(tmp_path)
    def change(name):
        if name != "prepared":
            return
        if mutation == "manual":
            hand.write_bytes(b"hand edit after archival copy")
        elif mutation == "pointer":
            w.atomic(root / w.POINTER, {"schema": "future/999"})
        else:
            path = next((root / ".generations").glob("*/state.json"))
            data = w.read(path); data["schema_version"] = 999; w.atomic(path, data)
    with pytest.raises(w.WorkspaceError, match=error):
        migrate(root, recovery_bundle, interrupt=change)
    if mutation != "pointer":
        assert not (root / w.POINTER).exists()
    else:
        assert w.read(root / w.POINTER)["schema"] == "future/999"


def test_reentry_rejects_self_consistent_archive_tamper(tmp_path, recovery_bundle):
    root, _ = legacy(tmp_path)
    def interrupt(name):
        if name == "archived":
            raise RuntimeError("stop")
    with pytest.raises(RuntimeError):
        migrate(root, recovery_bundle, interrupt=interrupt)
    archive = next((root / ".migrations").iterdir())
    path = archive / "files/09_storyboard.json"
    path.write_bytes(b"wrong bytes")
    manifest = w.read(archive / "recovery-manifest.json")
    row = next(r for r in manifest["files"] if r["path"] == "09_storyboard.json")
    row.update(bytes=path.stat().st_size, sha256=w.sha(path))
    w.atomic(archive / "recovery-manifest.json", manifest)
    with pytest.raises(w.WorkspaceError, match="MIGRATION_INTENT_MISMATCH"):
        migrate(root, recovery_bundle)
    assert not (root / w.POINTER).exists()


def test_recovery_cannot_pollute_original_or_overwrite_member(tmp_path, recovery_bundle):
    root, _ = legacy(tmp_path)
    (root / "output").mkdir()
    (root / "output/recovery-result.json").write_bytes(b"user bytes")
    _, active, _ = migrate(root, recovery_bundle)
    archive = Path(w.read(active / "state.json")["recovery_manifest"]).parent
    before = w.verify_archive(archive)
    for target in (archive / "files/restore", root / "restored"):
        with pytest.raises(w.WorkspaceError, match="OUTSIDE_ORIGINAL_TASK"):
            w.recover(archive, target)
        assert not target.exists()
    assert w.verify_archive(archive) == before
    restored = tmp_path / "good-target"
    w.recover(archive, restored)
    assert (restored / "output/recovery-result.json").read_bytes() == b"user bytes"
    with pytest.raises(w.WorkspaceError, match="TARGET_EXISTS"):
        w.recover(archive, restored)


def test_fixed_b_entry_schema_and_production_matrix(tmp_path, recovery_bundle):
    root, _ = legacy(tmp_path)
    entry = recovery_bundle[0] / "recover.py"
    env = dict(os.environ); env.pop("PYTHONPATH", None)
    def run(*args):
        return subprocess.run([sys.executable, "-B", str(entry), *args], env=env,
            cwd=tmp_path, capture_output=True, text=True)
    assert json.loads(run("inspect", "--work-dir", str(root)).stdout)["status"] == "READ_ONLY"
    migrate(root, recovery_bundle)
    assert json.loads(run("inspect", "--work-dir", str(root)).stdout)["status"] == "READ_ONLY"
    for operation in ("run", "resume", "render", "tts", "delivery"):
        result = run(operation, "--work-dir", str(root))
        assert result.returncode == 2 and "PRODUCTION_DISABLED" in result.stdout
    pointer = root / w.POINTER
    raw = pointer.read_bytes(); pointer.write_text('{"schema":"future/999"}')
    before = pointer.read_bytes()
    result = run("inspect", "--work-dir", str(root))
    assert result.returncode == 2 and "UNSUPPORTED" in result.stdout
    assert pointer.read_bytes() == before
    pointer.write_bytes(raw)
    archive = Path(w.read(w.preflight(root)[1] / "state.json")["recovery_manifest"]).parent
    target = tmp_path / "via-real-B-cli"
    result = run("recover", "--archive", str(archive), "--out", str(target))
    assert result.returncode == 0 and json.loads(result.stdout)["status"] == "RECOVERED_BYTES_ONLY"


def test_unknown_rejected_by_real_cli_and_direct_constructor_before_writes(tmp_path, app_config, monkeypatch):
    root = tmp_path / "future"; root.mkdir()
    (root / "state.json").write_text('{"schema_version":999}')
    before = (root / "state.json").read_bytes()
    monkeypatch.setattr("douyin_film_recap.pipeline.OpenAICompatibleClient", lambda _: pytest.fail("provider init"))
    with pytest.raises(w.WorkspaceError, match="UNSUPPORTED"):
        FilmRecapPipeline(input_path=tmp_path / "missing.mp4", work_dir=root, config=app_config)
    result = CliRunner().invoke(app, ["run", "missing.mp4", "-w", str(root), "-c", "missing.yaml"])
    assert result.exit_code != 0 and "UNSUPPORTED_STATE_SCHEMA" in result.stdout
    assert (root / "state.json").read_bytes() == before
    assert list(root.iterdir()) == [root / "state.json"]


def test_source_drift_preserves_old_generation_and_requires_new_binding(tmp_path, app_config, monkeypatch):
    source = tmp_path / "source.mp4"; source.write_bytes(b"AAA")
    p = FilmRecapPipeline(input_path=source, work_dir=tmp_path / "run", config=app_config)
    def ingest():
        p.paths["manifest"].write_text('{"generated":"keep"}')
        source.write_bytes(b"BBB")
        return p.paths["manifest"]
    monkeypatch.setattr(p, "_stage_ingest", ingest)
    with pytest.raises(w.WorkspaceError, match="SOURCE_BINDING_CHANGED"):
        p.run(until="ingest")
    assert p.state.stages["ingest"].status == "failed"
    next_run = FilmRecapPipeline(input_path=source, work_dir=p.task_root, config=app_config)
    assert next_run.work_dir != p.work_dir
    assert p.paths["manifest"].read_text() == '{"generated":"keep"}'
    assert next_run.state.stages["ingest"].status == "pending"
    with pytest.raises(w.WorkspaceError, match="STALE"):
        p.run(until="ingest")


def test_other_process_cannot_write_during_migration(tmp_path, recovery_bundle):
    root, _ = legacy(tmp_path)
    source_dir = REPO / "workflows/raven-film-recap/douyin-film-recap/src"
    with w.work_lock(root):
        code = "from douyin_film_recap.workspace import work_lock\nfrom pathlib import Path\nwith work_lock(Path(__import__('sys').argv[1])): pass"
        env = dict(os.environ, PYTHONPATH=str(source_dir))
        result = subprocess.run([sys.executable, "-c", code, str(root)], env=env, capture_output=True, text=True)
        assert result.returncode != 0 and "WORKSPACE_BUSY" in result.stderr


def test_b_pin_and_source_tamper_rejected(tmp_path, recovery_bundle):
    root, _ = legacy(tmp_path)
    with pytest.raises(w.WorkspaceError, match="PINNED"):
        w.prepare(root, BINDING, allow_legacy=True, recovery_bundle=recovery_bundle[0])
    (recovery_bundle[0] / "recover.py").write_text("raise RuntimeError('fake B')\n")
    with pytest.raises(w.WorkspaceError, match="DRIFTED"):
        migrate(root, recovery_bundle)
    assert not (root / w.POINTER).exists()


def test_original_u_cli_is_not_a_supported_rollback(tmp_path):
    # Exact original CLI bytes from baseline 5296227, only the read-only status entry.
    # Imports use this test environment; no original production operation is invoked.
    # A pinned fixture keeps shallow CI checkouts/source archives reproducible.
    prefix = "workflows/raven-film-recap/douyin-film-recap/src"
    fixture = Path(__file__).parent / "fixtures/original_u_cli.py"
    assert w.sha(fixture) == "ac1cc9f028ccf2c0a3b2a3116219cf3e6ef7d123c390d5abc60b09d24098a35f"
    synthetic = tmp_path / "v2-copy"; synthetic.mkdir()
    w.atomic(synthetic / "state.json", {"schema_version": 2, "project_name": "synthetic only",
                                         "stages": {"ingest": {"status": "pending"}}})
    env = dict(os.environ, PYTHONPATH=str(REPO / prefix), PYTHONDONTWRITEBYTECODE="1")
    code = "import importlib.util,sys; spec=importlib.util.spec_from_file_location('douyin_film_recap.original_u_cli',sys.argv.pop(1)); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); module.app()"
    result = subprocess.run([sys.executable, "-c", code, str(fixture), "status", str(synthetic)],
                            env=env, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0 and "UNSUPPORTED" not in result.stdout
    # U accepts the synthetic v2 header; it is explicitly not certified for rollback.
    assert not (synthetic / ".film-write.lock").exists()


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "traversal", "symlink", "extra"])
def test_invalid_recovery_members_rejected_before_destination_creation(tmp_path, recovery_bundle, mutation):
    root, _ = legacy(tmp_path)
    _, active, _ = migrate(root, recovery_bundle)
    archive = Path(w.read(active / "state.json")["recovery_manifest"]).parent
    manifest = w.read(archive / "recovery-manifest.json")
    row = manifest["files"][0]
    path = archive / "files" / row["path"]
    if mutation == "missing":
        path.unlink()
    elif mutation == "duplicate":
        manifest["files"].append(dict(row))
        w.atomic(archive / "recovery-manifest.json", manifest)
    elif mutation == "traversal":
        row["path"] = "../outside.json"
        w.atomic(archive / "recovery-manifest.json", manifest)
    elif mutation == "symlink":
        outside = tmp_path / "outside.json"; outside.write_bytes(path.read_bytes())
        path.unlink(); path.symlink_to(outside)
    else:
        (archive / "files/extra").write_text("undeclared")
    destination = tmp_path / "must-not-exist"
    with pytest.raises(w.WorkspaceError):
        w.recover(archive, destination)
    assert not destination.exists()
