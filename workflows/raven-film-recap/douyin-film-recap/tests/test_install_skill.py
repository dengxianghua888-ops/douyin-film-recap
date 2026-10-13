"""Installer regressions use only disposable source and destination fixtures."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "scripts" / "install_skill.py"


def snapshot(root: Path) -> dict:
    contents = {}
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            contents[name] = ("symlink", str(path.readlink()))
        elif path.is_dir():
            contents[name] = ("directory",)
        else:
            contents[name] = ("file", path.read_bytes())
    return contents


class InstallSkillTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name).resolve()
        self.source = self.base / "source parent" / "影视 source"
        (self.source / "scripts").mkdir(parents=True)
        self.script = self.source / "scripts" / "install_skill.py"
        shutil.copyfile(INSTALLER, self.script)
        (self.source / "SKILL.md").write_text("Source must survive reinstall.\n", encoding="utf-8")
        (self.source / "uncommitted.bin").write_bytes(b"\x00user edits\xff\n")
        (self.source / "empty directory").mkdir()
        self.original = snapshot(self.source)
        self.target = self.base / "installed" / "douyin-film-recap"

    def run_installer(self, target=None, *options, check=True):
        result = subprocess.run(
            [sys.executable, str(self.script), "--target", str(target or self.target), *options],
            text=True, capture_output=True, timeout=10, cwd=self.base,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def assert_source_unchanged(self):
        self.assertFalse(self.source.is_symlink())
        self.assertTrue(self.source.is_dir())
        self.assertEqual(snapshot(self.source), self.original)

    def test_force_reinstall_link_preserves_source_for_both_modes(self):
        for copy in (False, True):
            with self.subTest(copy=copy):
                target = self.target.with_name("copy" if copy else "link")
                self.run_installer(target)
                self.assertTrue(target.is_symlink())
                self.run_installer(target, "--force", *(["--copy"] if copy else []))
                self.assertEqual(target.is_symlink(), not copy)
                self.assertEqual(snapshot(target), self.original)
                self.assert_source_unchanged()

    def test_existing_link_requires_force(self):
        self.run_installer()
        result = self.run_installer(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Target exists", result.stderr)
        self.assertTrue(self.target.is_symlink())
        self.assert_source_unchanged()

    def test_force_replaces_dangling_links_for_both_modes(self):
        self.target.parent.mkdir()
        for copy in (False, True):
            with self.subTest(copy=copy):
                target = self.target.with_name("copy" if copy else "link")
                target.symlink_to(self.base / "missing source", target_is_directory=True)
                self.run_installer(target, "--force", *(["--copy"] if copy else []))
                self.assertEqual(target.is_symlink(), not copy)
                self.assertEqual(snapshot(target), self.original)
                self.assert_source_unchanged()

    def test_force_only_unlinks_external_directory_or_file_targets(self):
        self.target.parent.mkdir()
        external = self.base / "unrelated"
        external.mkdir()
        marker = external / "keep.bin"
        marker.write_bytes(b"unrelated user data")
        original = snapshot(external)
        for index, link_source in enumerate((external, marker)):
            for copy in (False, True):
                with self.subTest(link_source=link_source, copy=copy):
                    target = self.target.with_name(f"target-{index}-{copy}")
                    target.symlink_to(link_source, target_is_directory=link_source.is_dir())
                    self.run_installer(target, "--force", *(["--copy"] if copy else []))
                    self.assertEqual(snapshot(external), original)
                    self.assert_source_unchanged()

    def test_force_replaces_independent_existing_directory(self):
        self.target.mkdir(parents=True)
        (self.target / "stale.txt").write_text("old installation", encoding="utf-8")
        self.run_installer(self.target, "--force", "--copy")
        self.assertFalse((self.target / "stale.txt").exists())
        self.assertEqual(snapshot(self.target), self.original)
        self.assert_source_unchanged()

    def test_rejects_source_ancestor_and_descendants_before_mutation(self):
        targets = (
            self.source,
            self.source.parent,
            self.source / "scripts",
            self.source / "new parent" / "new install",
        )
        for target in targets:
            for copy in (False, True):
                with self.subTest(target=target, copy=copy):
                    result = self.run_installer(
                        target, "--force", *(["--copy"] if copy else []), check=False,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("must not overlap", result.stderr)
                    self.assert_source_unchanged()

    def test_rejects_parent_symlink_aliases_into_source(self):
        alias = self.base / "source alias"
        alias.symlink_to(self.source, target_is_directory=True)
        parent_alias = self.base / "parent alias"
        parent_alias.symlink_to(self.source.parent, target_is_directory=True)
        targets = (alias / "new install", alias / "scripts", parent_alias / self.source.name)
        for target in targets:
            with self.subTest(target=target):
                result = self.run_installer(target, "--force", "--copy", check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("must not overlap", result.stderr)
                self.assert_source_unchanged()

    def test_safe_parent_alias_keeps_final_link_lexical(self):
        actual_parent = self.base / "actual installation parent"
        actual_parent.mkdir()
        parent_alias = self.base / "installation parent alias"
        parent_alias.symlink_to(actual_parent, target_is_directory=True)
        target = parent_alias / "skill"
        self.run_installer(target)
        self.run_installer(target, "--force", "--copy")
        self.assertFalse(target.is_symlink())
        self.assertEqual(snapshot(target), self.original)
        self.assert_source_unchanged()

    def test_rejects_final_parent_directory_component(self):
        result = self.run_installer(self.source / "scripts" / "..", "--force", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unsafe target", result.stderr)
        self.assert_source_unchanged()


if __name__ == "__main__":
    unittest.main()
