"""Fail-fast local batches; already running work is allowed to settle honestly."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from threading import Event, Lock

from .send_guard import SendCancelled, cancel_active_sends


def run_parallel(jobs, worker, *, max_workers):
    """Cancel queued jobs on the first failure, including KeyboardInterrupt.

    Workers signal failure before returning to the executor, so the same worker
    cannot start another queued job while the coordinator observes its Future.
    In-flight transports are not forcibly stopped or represented as unsent.
    """
    stopped = Event()
    failure_lock = Lock()
    first_failure = []

    def run(job):
        if stopped.is_set():
            raise SendCancelled("BATCH_CANCELLED: no new work will start")
        try:
            return worker(job)
        except BaseException as exc:
            with failure_lock:
                if not first_failure:
                    first_failure.append(exc)
                stopped.set()
                cancel_active_sends()
            raise

    executor = ThreadPoolExecutor(max_workers=max_workers)
    futures = []
    try:
        for job in jobs:
            if stopped.is_set():
                break
            futures.append(executor.submit(copy_context().run, run, job))
        results = [future.result() for future in as_completed(futures)]
        if first_failure:
            raise first_failure[0]
        return results
    except BaseException as exc:
        stopped.set()
        cancel_active_sends()
        for future in futures:
            future.cancel()
        # Preserve the original worker error over cancellation from a queued job.
        if isinstance(exc, SendCancelled) and first_failure:
            raise first_failure[0]
        raise
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
