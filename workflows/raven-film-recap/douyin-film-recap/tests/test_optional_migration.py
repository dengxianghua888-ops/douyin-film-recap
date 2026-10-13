"""Optional references stay auditable without blocking safe generation changes."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from douyin_film_recap import workspace as w


class OptionalMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "task"
        self.root.mkdir()
        self.final = self.root / "output/final.mp4"
        self.final.parent.mkdir()
        self.final.write_bytes(b"synthetic final bytes")
        self.review = self.root / "output/review_evidence.json"
        self.board = self.root / "09_storyboard.json"
        w.atomic(self.board, {"output": {"final_video": str(self.final), "review_file": str(self.review)}})
        self.state = {"schema_version": 2, "input_fingerprint": "same-source",
                      "config_fingerprint": "old", "stages": {
                          "render": {"status": "passed", "artifacts": {str(self.final): w.sha(self.final)}}}}
        self.binding = {"input_paths": ["/synthetic/source.mp4"], "input_fingerprint": "same-source",
                        "config_fingerprint": "new"}
        self.save()

    def save(self):
        w.atomic(self.root / "state.json", self.state)

    def migrate(self, **kwargs):
        return w.prepare(self.root, self.binding, **kwargs)

    def add_missing_debug(self, *, delivered):
        self.frame = self.root / "frames/s/unit.jpg"
        self.sheet = self.root / "contact_sheets/unit.jpg"
        index = self.root / "02_scene_index.json"
        w.atomic(index, {"units": [{"frame_paths": [str(self.frame)], "contact_sheet_path": str(self.sheet)}]})
        self.state["stages"].update({
            "scenes": {"status": "passed", "artifacts": {str(index): w.sha(index), str(self.frame): "a"*64, str(self.sheet): "b"*64}},
            "scene_analysis": {"status": "passed"}, "highlights": {"status": "passed"},
            "delivery": {"status": "passed" if delivered else "running"}})
        self.save()

    def test_absent_review_is_recorded_and_does_not_fabricate_evidence(self):
        original = self.board.read_bytes()
        _, active, manifest = self.migrate()
        self.assertNotEqual(active, self.root)
        self.assertEqual(manifest["unavailable_optional_references"], [{
            "original_path": str(self.review), "reason": "optional_review_not_present"}])
        self.assertEqual(self.board.read_bytes(), original)
        self.assertFalse(self.review.exists())
        self.assertNotIn("output/review_evidence.json", {row["path"] for row in manifest["files"]})

    def test_present_review_is_preserved(self):
        self.review.write_bytes(b'{"human_review":"preserve exact bytes"}')
        _, _, manifest = self.migrate()
        self.assertEqual(manifest["unavailable_optional_references"], [])
        self.assertIn("output/review_evidence.json", {row["path"] for row in manifest["files"]})

    def test_required_final_missing_still_blocks(self):
        self.final.unlink()
        with self.assertRaisesRegex(w.WorkspaceError, "REQUIRED_ARCHIVE_MEMBER_MISSING"):
            self.migrate()
        self.assertFalse((self.root / w.POINTER).exists())

    def test_recorded_review_missing_still_blocks(self):
        self.state["stages"]["post_qc"] = {"artifacts": {str(self.review): "recorded-existing-review"}}
        self.save()
        with self.assertRaisesRegex(w.WorkspaceError, "REQUIRED_ARCHIVE_MEMBER_MISSING"):
            self.migrate()

    def test_legacy_delivery_cleaned_debug_can_migrate(self):
        self.add_missing_debug(delivered=True)
        _, _, manifest = self.migrate()
        absent = {row["original_path"]: row["reason"] for row in manifest["unavailable_optional_references"]}
        self.assertEqual(absent[str(self.frame)], "missing_regenerable_debug_after_delivery")
        self.assertEqual(absent[str(self.sheet)], "missing_regenerable_debug_after_delivery")

    def test_undelivered_debug_loss_without_receipt_blocks(self):
        self.add_missing_debug(delivered=False)
        with self.assertRaisesRegex(w.WorkspaceError, "REQUIRED_ARCHIVE_MEMBER_MISSING"):
            self.migrate()

    def test_cleanup_intent_handles_interrupted_delivery(self):
        self.add_missing_debug(delivered=False)
        w.atomic(self.root / ".receipts/debug-cleanup.json", {"schema": "film-debug-cleanup/1", "files": [
            {"path": str(self.frame), "sha256": "a"*64}, {"path": str(self.sheet), "sha256": "b"*64}]})
        _, _, manifest = self.migrate()
        absent = {row["original_path"]: row["reason"] for row in manifest["unavailable_optional_references"]}
        self.assertEqual(absent[str(self.frame)], "recorded_regenerable_debug_cleanup")
        self.assertEqual(absent[str(self.sheet)], "recorded_regenerable_debug_cleanup")

    def test_cleanup_cannot_exempt_unrelated_missing_artifact(self):
        self.final.unlink()
        w.atomic(self.root / ".receipts/debug-cleanup.json", {"schema": "film-debug-cleanup/1", "files": [
            {"path": str(self.final), "sha256": self.state["stages"]["render"]["artifacts"][str(self.final)]}]})
        with self.assertRaisesRegex(w.WorkspaceError, "REQUIRED_ARCHIVE_MEMBER_MISSING"):
            self.migrate()

    def test_optional_evidence_appearing_during_copy_rejects_switch(self):
        def interrupt(point):
            if point == "copied":
                self.review.write_text('{"new_review":true}')
        with self.assertRaisesRegex(w.WorkspaceError, "MIGRATION_INPUT_CHANGED"):
            self.migrate(interrupt=interrupt)
        self.assertFalse((self.root / w.POINTER).exists())


if __name__ == "__main__":
    unittest.main()
