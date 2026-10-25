import asyncio
import os
import socket
import time

import pytest

from server.core.persistent_listener_worker import ListenerWorkerError, PersistentListenerWorker


@pytest.fixture
def worker():
    instance = PersistentListenerWorker()
    instance.start()
    try:
        yield instance
    finally:
        instance.close()
        assert instance.process.poll() is not None


@pytest.mark.skipif(os.name != "nt", reason="Windows IP Helper worker")
def test_repeated_queries_are_fresh(worker):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        before = worker.query(port, time.monotonic() + 5)
        assert before["listener_pids"] == []
        listener.listen()
        during = worker.query(port, time.monotonic() + 5)
        assert during == {"listener_pids": [os.getpid()], "listener_addresses": ["127.0.0.1"]}
    after = worker.query(port, time.monotonic() + 5)
    assert after["listener_pids"] == []


@pytest.mark.skipif(os.name != "nt", reason="Windows IP Helper worker")
def test_worker_exit_invalidates_without_restart(worker):
    worker.process.kill()
    worker.process.wait(timeout=2)
    with pytest.raises(ListenerWorkerError, match="listener_worker_unavailable"):
        worker.query(59863, time.monotonic() + 2)
    assert worker._failed
    with pytest.raises(ListenerWorkerError):
        worker.start()


@pytest.mark.skipif(os.name != "nt", reason="Windows IP Helper worker")
def test_stale_response_invalidates_worker(worker, monkeypatch):
    monkeypatch.setattr(worker, "_receive", lambda _deadline: {"id": "0" * 32, "result": {}})
    with pytest.raises(ListenerWorkerError, match="listener_protocol_failed"):
        worker.query(59863, time.monotonic() + 2)
    assert worker.process.poll() is not None


@pytest.mark.skipif(os.name != "nt", reason="Windows IP Helper worker")
def test_worker_timeout_invalidates_and_reaps(worker, monkeypatch):
    def timeout(_deadline):
        raise ListenerWorkerError("listener_timeout")

    monkeypatch.setattr(worker, "_receive", timeout)
    with pytest.raises(ListenerWorkerError, match="listener_timeout"):
        worker.query(59863, time.monotonic() + 2)
    assert worker.process.poll() is not None


@pytest.mark.asyncio
async def test_worker_queries_cannot_overlap(worker):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        results = await asyncio.gather(*(
            asyncio.to_thread(worker.query, port, time.monotonic() + 5) for _ in range(2)
        ))
    assert all(result["listener_pids"] == [os.getpid()] for result in results)
