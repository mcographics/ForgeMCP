# SPDX-License-Identifier: MIT
"""Passive Windows process and listener identity checks for isolated hosts."""

from __future__ import annotations

import ctypes
import ipaddress
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from server.core.host_config import IsolatedHostConfig

IDENTITY_PROBE_TIMEOUT_SECONDS = 30


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
    $targetPort = [int]$env:FORGE_IDENTITY_TARGET_PORT
    $processes = @(Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $targetPid")
    if ($processes.Count -ne 1) { throw 'process-count' }
    $process = $processes[0]
    # Filter in the OS query so identity checks inspect only the pinned bridge
    # port instead of materializing every listening socket on the machine.
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $targetPort)
    $result = [ordered]@{
        pid = [int]$process.ProcessId
        executable_path = [string]$process.ExecutablePath
        command_line = [string]$process.CommandLine
        creation_utc = $process.CreationDate.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ')
        listener_pids = @($listeners | ForEach-Object { [int]$_.OwningProcess })
        listener_addresses = @($listeners | ForEach-Object { [string]$_.LocalAddress })
    }
    $result | ConvertTo-Json -Compress -Depth 4
} catch {
    [Console]::Error.WriteLine('Isolated process identity inspection failed.')
    exit 2
}
"""


class WindowsProcessIdentityProbe:
    """Read process and TCP listener metadata without opening the application socket."""

    def __call__(self, pid: int, port: int) -> ProcessSnapshot:
        if os.name != "nt":
            raise ProcessIdentityError(
                "Isolated process identity checks require Windows.", category="platform_unsupported"
            )
        environment = os.environ.copy()
        environment["FORGE_IDENTITY_TARGET_PID"] = str(pid)
        environment["FORGE_IDENTITY_TARGET_PORT"] = str(port)
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _POWERSHELL_SNAPSHOT],
                capture_output=True,
                check=False,
                encoding="utf-8",
                errors="strict",
                # CIM plus listener inspection can exceed ten seconds on a busy
                # Windows host; keep the probe bounded without turning a slow
                # metadata query into an identity bypass.
                timeout=IDENTITY_PROBE_TIMEOUT_SECONDS,
                env=environment,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired:
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
        try:
            payload = json.loads(result.stdout)
            if not isinstance(payload, dict):
                raise ValueError("snapshot is not an object")
            listeners = payload["listener_pids"]
            addresses = payload["listener_addresses"]
            if (
                not isinstance(listeners, list)
                or any(type(owner) is not int for owner in listeners)
                or not isinstance(addresses, list)
                or any(not isinstance(address, str) for address in addresses)
            ):
                raise ValueError("listener ownership is invalid")
            snapshot = ProcessSnapshot(
                pid=payload["pid"],
                executable_path=payload["executable_path"],
                command_line=payload["command_line"],
                creation_utc=payload["creation_utc"],
                listener_pids=tuple(listeners),
                listener_addresses=tuple(addresses),
            )
            if (
                type(snapshot.pid) is not int
                or not isinstance(snapshot.executable_path, str)
                or not snapshot.executable_path
                or not isinstance(snapshot.command_line, str)
                or not snapshot.command_line
                or not isinstance(snapshot.creation_utc, str)
            ):
                raise ValueError("process metadata is invalid")
            return snapshot
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise ProcessIdentityError(
                "Passive Windows process identity data is invalid.", category="metadata_parse_failed"
            ) from None


ProcessIdentityProbe = Callable[[int, int], ProcessSnapshot]
