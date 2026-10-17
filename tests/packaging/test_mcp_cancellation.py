"""Exercise live input while a tool is running, with atomic progress output."""
import importlib.util
import io
import json
from pathlib import Path
import queue
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'runtime'))
import editing_runtime as runtime


def test_owned_process_cooperatively_cancels_its_child():
    event = threading.Event()
    token = runtime.RUN_CANCELLATION.set(event)
    timer = threading.Timer(0.15, event.set)
    timer.start()
    try:
        started = time.monotonic()
        result = runtime.owned_process([sys.executable, '-c', 'import time; time.sleep(30)'])
        assert result.termination_reason == 'cancelled'
        assert result.returncode != 0
        assert time.monotonic() - started < 3
    finally:
        timer.cancel()
        timer.join()
        runtime.RUN_CANCELLATION.reset(token)


def test_live_ping_progress_and_cancel(monkeypatch):
    spec = importlib.util.spec_from_file_location('mcp_cancellation_test_server', ROOT / 'scripts/mcp_server.py')
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    incoming, outgoing = queue.Queue(), queue.Queue()
    started = threading.Event()
    class Input:
        def __iter__(self):
            while True:
                line = incoming.get(timeout=5)
                if line is None:
                    return
                yield line
    def fake_tool(name, arguments, *, cancel_event, progress):
        started.set()
        assert cancel_event.wait(3), 'server did not process cancellation during tool call'
        progress('Cancellation observed')
        return {'status': 'FAILED', 'cancelled': True}
    monkeypatch.setattr(server.sys, 'stdin', Input())
    monkeypatch.setattr(server, '_emit', outgoing.put)
    monkeypatch.setattr(server, 'call_tool', fake_tool)
    thread = threading.Thread(target=server.serve)
    thread.start()
    def send(value):
        incoming.put(json.dumps(value) + '\n')
    try:
        send({'id': 1, 'method': 'tools/call', 'params': {
            'name': 'run_operation', 'arguments': {}, '_meta': {'progressToken': 'p'}}})
        assert started.wait(2)
        send({'id': 2, 'method': 'ping'})
        progress = outgoing.get(timeout=2)
        assert progress['method'] == 'notifications/progress'
        assert outgoing.get(timeout=2) == {'jsonrpc': '2.0', 'id': 2, 'result': {}}
        send({'method': 'notifications/cancelled', 'params': {'requestId': 1}})
        outputs = [outgoing.get(timeout=3) for _ in range(3)]
        assert outputs[-1]['id'] == 1
        assert outputs[-1]['result']['isError']
        assert [item['params']['progress'] for item in [progress] + outputs[:-1]] == [1, 2, 3]
    finally:
        incoming.put(None)
        thread.join(timeout=5)
    assert not thread.is_alive()
