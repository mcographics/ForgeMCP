# SPDX-License-Identifier: MIT
"""Passive Windows process and listener identity checks for isolated hosts."""

from __future__ import annotations

import contextvars
import ctypes
import ipaddress
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from server.core.host_config import IsolatedHostConfig
from server.core.persistent_listener_worker import ListenerWorkerError, PersistentListenerWorker

IDENTITY_PROBE_TIMEOUT_SECONDS = 30
IDENTITY_ORIGIN = contextvars.ContextVar("forge_identity_origin", default="other")
IDENTITY_DEADLINE = contextvars.ContextVar("forge_identity_deadline", default=None)


def _diagnostic_marker(phase: str, started: float, **fields: object) -> None:
    """Append bounded, opt-in phase data without process paths or credentials."""
    destination = os.environ.get("FORGE_IDENTITY_DIAGNOSTIC_LOG")
    if not destination:
        return
    correlation = fields.get("correlation_id")
    if isinstance(correlation, str) and len(correlation) == 32:
        destination = str(Path(destination).with_name(
            f"identity-parent-{correlation}.jsonl"))
    record = {"component": "parent", "phase": phase, "parent_pid": os.getpid(),
              "monotonic_ns": time.monotonic_ns(),
              "elapsed_ms": round((time.monotonic() - started) * 1000, 3), **fields}
    try:
        with open(destination, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError:
        raise ProcessIdentityError(
            "Identity diagnostic marker could not be written.",
            category="identity_diagnostic_failed",
        ) from None


def _child_creation_ticks(process: subprocess.Popen) -> int | None:
    """Read the direct Windows process handle's creation FILETIME."""
    try:
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                             ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        values = (wintypes.FILETIME * 4)()
        if not kernel32.GetProcessTimes(int(process._handle), *[ctypes.byref(v) for v in values]):
            return None
        return (values[0].dwHighDateTime << 32) | values[0].dwLowDateTime
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _direct_child_exited(process: subprocess.Popen) -> bool:
    """Check the owned handle, which remains tied to one process despite PID reuse."""
    if process.poll() is None:
        return False
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        return kernel32.WaitForSingleObject(int(process._handle), 0) == 0
    except (AttributeError, OSError, TypeError, ValueError):
        return False


class ProcessIdentityError(RuntimeError):
    """The pinned process or its loopback listener could not be verified."""

    def __init__(self, message: str, *, category: str = "identity_verification_failed") -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class ProcessSnapshot:
    pid: int
    executable_path: str
    command_line: str
    creation_utc: str
    listener_pids: tuple[int, ...]
    listener_addresses: tuple[str, ...]


def _windows_argv(command_line: str) -> list[str]:
    """Parse a Windows command line with the same API used by process launchers."""
    if os.name != "nt":
        raise ProcessIdentityError(
            "Isolated process identity checks require Windows.", category="platform_unsupported"
        )

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    argc = ctypes.c_int()
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    shell32.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    parsed = shell32.CommandLineToArgvW(command_line, ctypes.byref(argc))
    if not parsed:
        raise ProcessIdentityError(
            "The Editor command line could not be parsed.", category="command_line_parse_failed"
        )
    try:
        return [parsed[index] for index in range(argc.value)]
    finally:
        kernel32.LocalFree(ctypes.cast(parsed, ctypes.c_void_p))


def _windows_path_key(value: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(value)))


def validate_process_snapshot(snapshot: ProcessSnapshot, config: IsolatedHostConfig) -> None:
    """Fail closed unless process, project argument, start time and listener all match."""
    if snapshot.pid != config.expected_pid:
        raise ProcessIdentityError(
            "The registered Editor PID does not match the pinned process.", category="pid_mismatch"
        )
    if _windows_path_key(snapshot.executable_path) != _windows_path_key(
        config.expected_executable_path
    ):
        raise ProcessIdentityError(
            "The Editor executable does not match the pinned path.", category="executable_mismatch"
        )
    if snapshot.creation_utc != config.expected_process_start_utc:
        raise ProcessIdentityError(
            "The Editor process start time does not match the pinned UTC value.",
            category="process_start_mismatch",
        )

    argv = _windows_argv(snapshot.command_line)
    if not argv or _windows_path_key(argv[0]) != _windows_path_key(config.expected_executable_path):
        raise ProcessIdentityError(
            "The Editor command line does not begin with the pinned executable.",
            category="command_line_executable_mismatch",
        )
    project_args = [
        argument for argument in argv[1:]
        if argument.lower().endswith(".uproject")
    ]
    if (
        len(project_args) != 1
        or _windows_path_key(project_args[0]) != _windows_path_key(config.expected_project_file)
    ):
        raise ProcessIdentityError(
            "The Editor command line does not contain the exact isolated project argument.",
            category="project_argument_mismatch",
        )

    owners = set(snapshot.listener_pids)
    if not owners or owners != {config.expected_pid} or not snapshot.listener_addresses:
        raise ProcessIdentityError(
            "The configured loopback listener is not uniquely owned by the pinned Editor.",
            category="listener_owner_mismatch",
        )
    try:
        if any(not ipaddress.ip_address(address).is_loopback for address in snapshot.listener_addresses):
            raise ProcessIdentityError(
                "The Editor bridge listener is not bound only to loopback addresses.",
                category="listener_not_loopback",
            )
    except ValueError:
        raise ProcessIdentityError(
            "The Editor bridge listener address could not be verified.",
            category="listener_address_invalid",
        ) from None


_POWERSHELL_SNAPSHOT = r"""
$ErrorActionPreference = 'Stop'
try {
    $targetPid = [int]$env:FORGE_IDENTITY_TARGET_PID
    $processes = @(Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $targetPid")
    if ($processes.Count -ne 1) { throw 'process-count' }
    $process = $processes[0]
    $result = [ordered]@{
        pid = [int]$process.ProcessId
        executable_path = [string]$process.ExecutablePath
        command_line = [string]$process.CommandLine
        creation_utc = $process.CreationDate.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ')
    }
    $result | ConvertTo-Json -Compress -Depth 4
} catch {
    [Console]::Error.WriteLine('Isolated process identity inspection failed.')
    exit 2
}
"""


class WindowsProcessIdentityProbe:
    """Read process and TCP listener metadata without opening the application socket."""

    def __init__(self, worker: PersistentListenerWorker | None = None) -> None:
        self.worker = worker

    def __call__(self, pid: int, port: int) -> ProcessSnapshot:
        if os.name != "nt":
            raise ProcessIdentityError(
                "Isolated process identity checks require Windows.", category="platform_unsupported"
            )
        started = time.monotonic()
        inherited_deadline = IDENTITY_DEADLINE.get()
        deadline = min(started + IDENTITY_PROBE_TIMEOUT_SECONDS, inherited_deadline) if inherited_deadline is not None else started + IDENTITY_PROBE_TIMEOUT_SECONDS
        correlation = uuid.uuid4().hex
        origin = IDENTITY_ORIGIN.get()
        if origin not in {"health", "project_info"}:
            origin = "other"
        fields = {"correlation_id": correlation, "origin": origin}
        _diagnostic_marker("identity_start", started, **fields,
                           budget_seconds=IDENTITY_PROBE_TIMEOUT_SECONDS)
        environment = os.environ.copy()
        environment["FORGE_IDENTITY_TARGET_PID"] = str(pid)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProcessIdentityError(
                "Passive Windows identity budget expired.", category="powershell_timeout"
            )
        try:
            _diagnostic_marker("powershell_launch", started, **fields,
                               remaining_ms=round(remaining * 1000, 3))
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _POWERSHELL_SNAPSHOT],
                capture_output=True,
                check=False,
                encoding="utf-8",
                errors="strict",
                timeout=remaining,
                env=environment,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired:
            _diagnostic_marker("powershell_timeout", started, **fields)
            _diagnostic_marker("powershell_child_reaped", started, **fields)
            raise ProcessIdentityError(
                "Passive Windows process identity inspection timed out.", category="powershell_timeout"
            ) from None
        except UnicodeError:
            raise ProcessIdentityError(
                "Passive Windows process metadata could not be decoded.", category="metadata_decode_failed"
            ) from None
        except OSError:
            raise ProcessIdentityError(
                "PowerShell process inspection could not be launched.", category="powershell_launch_failed"
            ) from None
        except subprocess.SubprocessError:
            raise ProcessIdentityError(
                "PowerShell process inspection failed.", category="powershell_subprocess_failed"
            ) from None
        if result.returncode != 0:
            raise ProcessIdentityError(
                "PowerShell returned an unsuccessful process identity result.",
                category="powershell_execution_failed",
            )
        _diagnostic_marker("powershell_complete", started, **fields,
                           exit_code=result.returncode)
        try:
            payload = json.loads(result.stdout)
            if not isinstance(payload, dict):
                raise ValueError("snapshot is not an object")
            if (
                type(payload["pid"]) is not int
                or not isinstance(payload["executable_path"], str)
                or not payload["executable_path"]
                or not isinstance(payload["command_line"], str)
                or not payload["command_line"]
                or not isinstance(payload["creation_utc"], str)
            ):
                raise ValueError("process metadata is invalid")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise ProcessIdentityError(
                "Passive Windows process identity data is invalid.", category="metadata_parse_failed"
            ) from None

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProcessIdentityError(
                "Passive Windows identity budget expired.", category="listener_timeout"
            )
        if self.worker is not None:
            try:
                listeners = self.worker.query(port, deadline)
                owners = listeners["listener_pids"]
                addresses = listeners["listener_addresses"]
                if (
                    not isinstance(owners, list)
                    or any(type(owner) is not int for owner in owners)
                    or not isinstance(addresses, list)
                    or any(not isinstance(address, str) for address in addresses)
                    or len(owners) != len(addresses)
                ):
                    raise ValueError("invalid listener rows")
            except ListenerWorkerError as error:
                raise ProcessIdentityError(
                    "Persistent listener worker failed.", category=error.category
                ) from None
            except (KeyError, TypeError, ValueError):
                self.worker.invalidate()
                raise ProcessIdentityError(
                    "Persistent listener worker returned invalid rows.",
                    category="listener_parse_failed",
                ) from None
            return ProcessSnapshot(
                pid=payload["pid"], executable_path=payload["executable_path"],
                command_line=payload["command_line"], creation_utc=payload["creation_utc"],
                listener_pids=tuple(owners), listener_addresses=tuple(addresses),
            )
        base_interpreter = Path(getattr(sys, "_base_executable", ""))
        listener_script = Path(__file__).with_name("windows_tcp_listener.py")
        bootstrap_script = Path(__file__).with_name("windows_tcp_bootstrap.py")
        if (
            not base_interpreter.is_absolute()
            or not base_interpreter.is_file()
            or not listener_script.is_file()
            or not bootstrap_script.is_file()
        ):
            raise ProcessIdentityError(
                "The direct listener helper launch path is unavailable.",
                category="listener_launch_failed",
            )
        diagnostic_root = os.environ.get("FORGE_IDENTITY_DIAGNOSTIC_LOG")
        if diagnostic_root:
            diagnostic_path = Path(diagnostic_root)
            if not diagnostic_path.parent.is_dir():
                raise ProcessIdentityError("Identity diagnostic directory is unavailable.",
                                           category="listener_launch_failed")
            environment["FORGE_IDENTITY_CHILD_LOG"] = str(
                diagnostic_path.with_name(f"identity-child-{correlation}.jsonl")
            )
            environment["FORGE_IDENTITY_CORRELATION"] = correlation
            environment["FORGE_IDENTITY_ORIGIN"] = origin
        else:
            environment.pop("FORGE_IDENTITY_CHILD_LOG", None)
        process = None
        try:
            _diagnostic_marker("listener_launch", started, **fields,
                               remaining_ms=round((deadline-time.monotonic())*1000, 3))
            _diagnostic_marker("popen_enter", started, **fields)
            process = subprocess.Popen(
                [str(base_interpreter), "-I", "-S", str(bootstrap_script),
                 str(listener_script), str(port)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=environment,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            popen_return_ns = time.monotonic_ns()
            child_ticks = _child_creation_ticks(process)
            _diagnostic_marker("popen_return", started, **fields,
                               child_pid=process.pid, handle=int(process._handle),
                               popen_return_ns=popen_return_ns,
                               creation_ticks=child_ticks,
                               creation_time_available=child_ticks is not None)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, 0)
            output, errors = process.communicate(timeout=remaining)
            listener_result = subprocess.CompletedProcess(
                process.args, process.returncode,
                output.decode("utf-8", "strict"), errors.decode("utf-8", "strict")
            )
            _diagnostic_marker("listener_child_exit", started, **fields,
                               child_pid=process.pid, exit_code=process.returncode)
            if child_ticks is None or not _direct_child_exited(process):
                raise ProcessIdentityError(
                    "Direct listener child identity or exit could not be verified.",
                    category="listener_launch_failed",
                )
        except subprocess.TimeoutExpired:
            _diagnostic_marker("listener_timeout", started, **fields,
                               child_pid=process.pid if process else None)
            if process is not None:
                if process.poll() is None:
                    try:
                        process.kill()
                    except OSError:
                        _diagnostic_marker("listener_cleanup_failed", started, **fields,
                                           child_pid=process.pid)
                        raise ProcessIdentityError(
                            "Passive Windows listener child termination failed.",
                            category="listener_timeout") from None
                try:
                    process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    _diagnostic_marker("listener_cleanup_failed", started, **fields,
                                       child_pid=process.pid)
                    raise ProcessIdentityError(
                        "Passive Windows listener child cleanup could not be verified.",
                        category="listener_timeout") from None
                exited = _direct_child_exited(process)
                _diagnostic_marker("listener_child_reaped", started, **fields,
                                   child_pid=process.pid, exited_on_handle=exited)
                if not exited:
                    raise ProcessIdentityError(
                        "Passive Windows listener child exit could not be verified.",
                        category="listener_timeout") from None
            raise ProcessIdentityError(
                "Passive Windows listener inspection timed out.", category="listener_timeout"
            ) from None
        except UnicodeError:
            raise ProcessIdentityError(
                "Passive Windows listener metadata could not be decoded.", category="listener_decode_failed"
            ) from None
        except ProcessIdentityError:
            if process is not None and process.poll() is None:
                process.kill()
                try:
                    process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
            raise
        except (OSError, subprocess.SubprocessError):
            _diagnostic_marker("listener_launch_failed", started, **fields)
            raise ProcessIdentityError(
                "Passive Windows listener inspection failed.", category="listener_launch_failed"
            ) from None
        if listener_result.returncode != 0:
            # stderr contains a bounded category from the dedicated helper; it is
            # intentionally not copied into the public bridge response.
            safe_categories = {
                "listener_api_failed", "listener_table_size_failed",
                "listener_table_size_invalid", "listener_table_unstable",
                "listener_table_malformed", "listener_state_invalid",
                "listener_port_malformed", "listener_owner_invalid",
                "listener_family_invalid", "listener_port_invalid",
                "identity_diagnostic_write_failed", "listener_launch_failed",
            }
            category = listener_result.stderr.strip()
            raise ProcessIdentityError(
                "Passive Windows listener inspection failed.",
                category=category if category in safe_categories else "listener_api_failed",
            )
        _diagnostic_marker("listener_complete", started, **fields,
                           exit_code=listener_result.returncode)
        try:
            listeners = json.loads(listener_result.stdout)
            owners = listeners["listener_pids"]
            addresses = listeners["listener_addresses"]
            if (
                not isinstance(owners, list)
                or any(type(owner) is not int for owner in owners)
                or not isinstance(addresses, list)
                or any(not isinstance(address, str) for address in addresses)
                or len(owners) != len(addresses)
            ):
                raise ValueError("listener ownership is invalid")
            return ProcessSnapshot(
                pid=payload["pid"],
                executable_path=payload["executable_path"],
                command_line=payload["command_line"],
                creation_utc=payload["creation_utc"],
                listener_pids=tuple(owners),
                listener_addresses=tuple(addresses),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise ProcessIdentityError(
                "Passive Windows listener data is invalid.", category="listener_parse_failed"
            ) from None


ProcessIdentityProbe = Callable[[int, int], ProcessSnapshot]
