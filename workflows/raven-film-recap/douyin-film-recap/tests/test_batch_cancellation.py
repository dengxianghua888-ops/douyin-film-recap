"""Cancellation regressions use local fake transports only."""
import asyncio
from threading import Event

import pytest

from douyin_film_recap import send_guard as guard
from douyin_film_recap import parallel
from douyin_film_recap.analysis import analyze_scenes
from douyin_film_recap.models import SceneIndex, SceneUnit
from douyin_film_recap.workspace import read


SCOPE = {"stage": "synthetic-cancellation"}


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
def test_scene_failure_stops_queued_batches(tmp_path, app_config, failure):
    calls = []
    app_config.scene.contact_sheet_units = 1
    app_config.scene.max_scene_analysis_workers = 1
    scenes = SceneIndex(units=[SceneUnit(unit_id=f"u{i}", source_id="s", start=i, end=i+1)
                              for i in range(25)], source_fingerprints={"s": "synthetic"}, detector="test")

    class Client:
        def chat_json(self, **kwargs):
            def send():
                calls.append(kwargs["intent_key"])
                raise failure("first batch failed")
            guard.guarded_send("chat", {"test": True}, send, intent_key=kwargs["intent_key"])

    with guard.send_session(tmp_path, SCOPE, authorized=True) as session:
        with pytest.raises(failure, match="first batch"):
            analyze_scenes(scenes, app_config, Client())
        with pytest.raises(guard.SendCancelled):
            guard.guarded_send("chat", {}, lambda: pytest.fail("new send"), intent_key="after")
    assert calls == ["scene-analysis:batch:0000"]
    receipts = list((tmp_path / ".remote-intents").glob("*.json"))
    assert len(receipts) == session.sent == 1
    assert read(receipts[0])["status"] == "UNKNOWN"


def test_running_request_can_finish_after_other_worker_fails(tmp_path):
    entered = Event()
    release = Event()
    calls = []

    def worker(job):
        if job == 0:
            def send():
                calls.append(job)
                entered.set()
                assert release.wait(5)
                return {"observed": "complete"}
            return guard.guarded_send("chat", {}, send, intent_key="in-flight")
        assert entered.wait(5)
        if job == 1:
            guard.cancel_active_sends()
            release.set()
            raise RuntimeError("other batch failed")
        pytest.fail("queued job was started")

    with guard.send_session(tmp_path, SCOPE, authorized=True):
        with pytest.raises(RuntimeError, match="other batch"):
            parallel.run_parallel(range(30), worker, max_workers=2)
    assert calls == [0]
    receipt = read(next((tmp_path / ".remote-intents").glob("*.json")))
    assert receipt["status"] == "SUCCEEDED" and receipt["result"] == {"observed": "complete"}


@pytest.mark.parametrize("asynchronous", [False, True])
def test_cancel_after_reservation_before_transport_is_known_unsent(tmp_path, monkeypatch, asynchronous):
    with guard.send_session(tmp_path, SCOPE, authorized=True) as session:
        reserve = session._reserve
        def cancel_after_reserve(*args, **kwargs):
            result = reserve(*args, **kwargs)
            session.cancel()
            return result
        monkeypatch.setattr(session, "_reserve", cancel_after_reserve)
        with pytest.raises(guard.SendCancelled):
            if asynchronous:
                asyncio.run(session.perform_async("chat", {}, lambda: pytest.fail("transport called"), "reserved"))
            else:
                session.perform("chat", {}, lambda: pytest.fail("transport called"), "reserved")
    receipt = read(next((tmp_path / ".remote-intents").glob("*.json")))
    assert receipt["status"] == "NOT_SUBMITTED_CONFIRMED"
    assert receipt["cancellation"]["reason"] == "cancelled_before_transport"


def test_coordinator_interrupt_cancels_session_and_queue(tmp_path, monkeypatch):
    entered = Event()
    release = Event()
    calls = []
    def worker(job):
        calls.append(job)
        entered.set()
        assert release.wait(5)
    def interrupt(_):
        assert entered.wait(5)
        raise KeyboardInterrupt("operator cancelled")
    monkeypatch.setattr(parallel, "as_completed", interrupt)
    def cancel_and_release():
        guard.cancel_active_sends()
        release.set()
    monkeypatch.setattr(parallel, "cancel_active_sends", cancel_and_release)
    with guard.send_session(tmp_path, SCOPE, authorized=True) as session:
        with pytest.raises(KeyboardInterrupt, match="operator cancelled"):
            parallel.run_parallel(range(25), worker, max_workers=1)
        with pytest.raises(guard.SendCancelled):
            session.check_cancelled()
    assert calls == [0]
