"""Interruptions persist resumable stage errors without claiming remote outcomes."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from douyin_film_recap.config import AppConfig
from douyin_film_recap.pipeline import FilmRecapPipeline
from douyin_film_recap import send_guard as guard
from douyin_film_recap.workspace import read


class PipelineInterruptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / "source.mp4"
        source.write_bytes(b"synthetic source; never decoded")
        config = AppConfig.model_validate({"models": {"llm_model": "test", "vlm_model": "test"}})
        self.pipeline = FilmRecapPipeline(input_path=source, work_dir=self.root / "work", config=config)

    @staticmethod
    def interrupt(*args):
        raise KeyboardInterrupt("operator interrupted")

    def assert_recorded(self):
        state = read(self.pipeline.work_dir / "state.json")
        self.assertEqual(state["stages"]["ingest"]["status"], "failed")
        self.assertEqual(state["last_error"]["code"], "KeyboardInterrupt")
        self.assertEqual(state["last_error"]["stage"], "ingest")
        receipts = list((self.pipeline.work_dir / ".receipts/failures").glob("ingest-*.json"))
        self.assertEqual(len(receipts), 1)
        self.assertEqual(read(receipts[0])["error"]["code"], "KeyboardInterrupt")

    def test_handler_interruption_is_persisted(self):
        self.pipeline._stage_ingest = self.interrupt
        with self.assertRaisesRegex(KeyboardInterrupt, "operator interrupted"):
            self.pipeline.run(until="ingest")
        self.assert_recorded()

    def test_preparation_interruption_is_persisted(self):
        self.pipeline._prepare_stage = self.interrupt
        with self.assertRaisesRegex(KeyboardInterrupt, "operator interrupted"):
            self.pipeline.run(until="ingest")
        self.assert_recorded()

    def test_remote_interruption_remains_unknown_and_cancels_session(self):
        sessions = []
        def handler():
            sessions.append(guard._session.get())
            guard.guarded_send("edge_tts", self.pipeline.remote_policy["edge_tts"], self.interrupt,
                               intent_key="synthetic interrupted request")
        self.pipeline._stage_ingest = handler
        with self.assertRaisesRegex(KeyboardInterrupt, "operator interrupted"):
            self.pipeline.run(until="ingest", allow_remote=True, max_remote_requests=1)
        self.assert_recorded()
        receipt = read(next((self.pipeline.task_root / ".remote-intents").glob("*.json")))
        self.assertEqual(receipt["status"], "UNKNOWN")
        self.assertEqual(receipt["local_error"]["type"], "KeyboardInterrupt")
        with self.assertRaises(guard.SendCancelled):
            sessions[0].check_cancelled()

    def test_receipt_write_failure_does_not_mask_interruption(self):
        self.pipeline._stage_ingest = self.interrupt
        with patch.object(self.pipeline.store, "fail", side_effect=OSError("synthetic disk failure")):
            with self.assertRaisesRegex(KeyboardInterrupt, "operator interrupted") as raised:
                self.pipeline.run(until="ingest")
        self.assertTrue(any("Could not persist ingest failure" in note
                            for note in raised.exception.__notes__))


if __name__ == "__main__":
    unittest.main()
