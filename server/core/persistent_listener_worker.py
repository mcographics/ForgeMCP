"""Supervise one private Windows listener-query process for an isolated host."""
from __future__ import annotations

import ctypes
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

MAX_RESPONSE = 65536
log = logging.getLogger("majestic_forge.identity_worker")


class ListenerWorkerError(RuntimeError):
    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


class PersistentListenerWorker:
    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.creation_ticks: int | None = None
        self._responses: queue.Queue[bytes] = queue.Queue(maxsize=2)
        self._reader: threading.Thread | None = None
        self._failed = False
        self._query_lock = threading.Lock()

    def _read(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        try:
            while True:
                line = self.process.stdout.readline(MAX_RESPONSE + 1)
                self._responses.put_nowait(line)
                if not line or len(line) > MAX_RESPONSE:
                    return
        except (OSError, queue.Full):
            self._failed = True

    def _receive(self, deadline: float) -> dict:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ListenerWorkerError("listener_timeout")
        try:
            line = self._responses.get(timeout=remaining)
        except queue.Empty:
            raise ListenerWorkerError("listener_timeout") from None
        if not line or len(line) > MAX_RESPONSE or not line.endswith(b"\n"):
            raise ListenerWorkerError("listener_protocol_failed")
        try:
            value = json.loads(line)
        except (UnicodeError, ValueError):
            raise ListenerWorkerError("listener_protocol_failed") from None
        if not isinstance(value, dict):
            raise ListenerWorkerError("listener_protocol_failed")
        return value

    def start(self, deadline: float | None = None) -> None:
        if self.process is not None or self._failed:
            raise ListenerWorkerError("listener_worker_unavailable")
        base = Path(getattr(sys, "_base_executable", ""))
        worker = Path(__file__).with_name("windows_tcp_worker.py")
        listener = Path(__file__).with_name("windows_tcp_listener.py")
        if not base.is_absolute() or not base.is_file() or not worker.is_file() or not listener.is_file():
            self._failed = True
            raise ListenerWorkerError("listener_launch_failed")
        try:
            environment = os.environ.copy()
            for key in ("FORGE_IDENTITY_CHILD_LOG", "FORGE_IDENTITY_DIAGNOSTIC_LOG",
                        "FORGE_IDENTITY_CORRELATION", "FORGE_IDENTITY_ORIGIN"):
                environment.pop(key, None)
            self.process = subprocess.Popen(
                [str(base), "-I", "-S", str(worker), str(listener)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                env=environment,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            # QueryFullProcessImageNameW/GetProcessTimes use the owned process handle.
            from server.core.process_identity import _child_creation_ticks
            self.creation_ticks = _child_creation_ticks(self.process)
            if self.creation_ticks is None or not self._image_matches(base):
                raise ListenerWorkerError("listener_launch_failed")
            self._reader = threading.Thread(target=self._read, daemon=True, name="forge-listener-reader")
            self._reader.start()
            ready = self._receive(min(deadline or time.monotonic() + 10, time.monotonic() + 10))
            if ready != {"ready": True, "pid": self.process.pid} or self.process.poll() is not None:
                raise ListenerWorkerError("listener_protocol_failed")
            log.info("Listener worker ready pid=%s creation_ticks=%s", self.process.pid, self.creation_ticks)
        except (OSError, ListenerWorkerError):
            self.invalidate()
            raise

    def _image_matches(self, expected: Path) -> bool:
        try:
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.QueryFullProcessImageNameW.argtypes = [
                wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                ctypes.POINTER(wintypes.DWORD),
            ]
            kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            if not kernel32.QueryFullProcessImageNameW(
                int(self.process._handle), 0, buffer, ctypes.byref(size)
            ):
                return False
            return os.path.normcase(os.path.normpath(buffer.value)) == os.path.normcase(
                os.path.normpath(str(expected))
            )
        except (AttributeError, OSError, TypeError, ValueError):
            return False

    def query(self, port: int, deadline: float) -> dict:
        if not self._query_lock.acquire(timeout=max(0, deadline - time.monotonic())):
            self.invalidate()
            raise ListenerWorkerError("listener_timeout")
        try:
            process = self.process
            if self._failed or process is None or process.poll() is not None or process.stdin is None:
                self.invalidate()
                raise ListenerWorkerError("listener_worker_unavailable")
            request_id = uuid.uuid4().hex
            try:
                if deadline - time.monotonic() <= 0:
                    raise ListenerWorkerError("listener_timeout")
                encoded = json.dumps({"id": request_id, "port": port}, separators=(",", ":")).encode() + b"\n"
                process.stdin.write(encoded)
                process.stdin.flush()
                response = self._receive(deadline)
                if set(response) != {"id", "result"} or response["id"] != request_id:
                    raise ListenerWorkerError("listener_protocol_failed")
                if process.poll() is not None or self._failed:
                    raise ListenerWorkerError("listener_worker_unavailable")
                return response["result"]
            except (OSError, ListenerWorkerError):
                self.invalidate()
                raise
        finally:
            self._query_lock.release()

    def invalidate(self) -> None:
        self._failed = True
        process = self.process
        if process is None:
            return
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            raise ListenerWorkerError("listener_cleanup_failed") from None
        if self._reader is not None:
            self._reader.join(timeout=2)
        log.info("Listener worker stopped pid=%s exit=%s", process.pid, process.poll())

    def close(self) -> None:
        self.invalidate()
