# SPDX-License-Identifier: MIT
"""Fail-closed configuration for a dedicated, isolated ForgeMCP host."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class HostConfigurationError(ValueError):
    """The host environment is incomplete or crosses an isolation boundary."""


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SESSION_ID = _IDENTIFIER
_CREDENTIAL_SOURCE = "private_session_registration"


def _required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise HostConfigurationError(f"{key} is required in isolated-host mode")
    return value


def _path(env: Mapping[str, str], key: str) -> Path:
    value = _required(env, key)
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        raise HostConfigurationError(f"{key} must be an absolute path")
    resolved = candidate.resolve(strict=False)
    if resolved.exists() and not resolved.is_dir():
        raise HostConfigurationError(f"{key} must name a directory")
    return resolved


def _absolute_file_path(env: Mapping[str, str], key: str) -> Path:
    value = _required(env, key)
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        raise HostConfigurationError(f"{key} must be an absolute file path")
    return candidate.resolve(strict=False)


def _key(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=False)))


def _contains(parent: Path, child: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def _overlaps(left: Path, right: Path) -> bool:
    return _contains(left, right) or _contains(right, left)


def _id_list(env: Mapping[str, str], key: str) -> frozenset[str]:
    raw = _required(env, key)
    values = [part.strip() for part in raw.split(",")]
    if not values or any(not item or not _SESSION_ID.fullmatch(item) for item in values):
        raise HostConfigurationError(f"{key} must contain valid comma-separated session IDs")
    if len(set(values)) != len(values):
        raise HostConfigurationError(f"{key} must not contain duplicate session IDs")
    return frozenset(values)


@dataclass(frozen=True)
class IsolatedHostConfig:
    """An isolated host is pinned to one Editor and private process state."""

    host_id: str
    auth_context_id: str
    private_root: Path
    registry_root: Path
    unreal_registry_root: Path
    blender_registry_root: Path
    state_root: Path
    temp_root: Path
    log_root: Path
    allowed_session_id: str
    denied_session_ids: frozenset[str]
    expected_pid: int
    expected_port: int
    expected_process_start_utc: str
    expected_executable_path: Path
    expected_project_file: Path
    expected_level: str
    expected_engine_version_prefix: str
    tool_profile: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> IsolatedHostConfig:
        env = os.environ if env is None else env
        host_id = _required(env, "FORGE_HOST_ID")
        auth_context_id = _required(env, "FORGE_AUTH_CONTEXT_ID")
        if not _IDENTIFIER.fullmatch(host_id) or not _IDENTIFIER.fullmatch(auth_context_id):
            raise HostConfigurationError("Host and authentication context IDs must be simple identifiers")
        if _required(env, "FORGE_ISOLATED_CREDENTIAL_SOURCE") != _CREDENTIAL_SOURCE:
            raise HostConfigurationError(
                "Isolated credentials must come only from the private session registration"
            )

        private_root = _path(env, "FORGE_PRIVATE_ROOT")
        registry_root = _path(env, "FORGE_SESSION_DIR")
        unreal_root = _path(env, "FORGE_UNREAL_SESSION_DIR")
        blender_root = _path(env, "FORGE_BLENDER_SESSION_DIR")
        state_root = _path(env, "FORGE_STATE_DIR")
        project_root = _path(env, "FORGE_PROJECT_ROOT")
        temp_root = _path(env, "FORGE_TEMP_DIR")
        log_root = _path(env, "FORGE_LOG_DIR")
        expected_project_file = _absolute_file_path(env, "FORGE_ISOLATED_EXPECTED_PROJECT_FILE")
        expected_executable_path = _absolute_file_path(env, "FORGE_ISOLATED_EXPECTED_EXECUTABLE")
        expected_process_start_utc = _required(env, "FORGE_ISOLATED_EXPECTED_START_UTC")
        if not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{7}Z",
            expected_process_start_utc,
        ):
            raise HostConfigurationError(
                "Expected isolated process start must be a UTC timestamp with seven fractional digits"
            )
        expected_level = _required(env, "FORGE_ISOLATED_EXPECTED_LEVEL")
        expected_engine_version = _required(env, "FORGE_ISOLATED_EXPECTED_ENGINE_VERSION")
        tool_profile = env.get("FORGE_ISOLATED_TOOL_PROFILE", "readonly").strip().lower()
        if tool_profile not in {"readonly", "landscape_smoke"}:
            raise HostConfigurationError(
                "FORGE_ISOLATED_TOOL_PROFILE must be readonly or landscape_smoke"
            )
        approved_engine_entry = "/Engine/Maps/Entry.Entry"
        if len(expected_level) > 512 or not (
            expected_level.startswith("/Game/") or expected_level == approved_engine_entry
        ):
            raise HostConfigurationError(
                "Expected isolated map must be a /Game package or the approved /Engine/Maps/Entry source"
            )
        if not re.fullmatch(r"\d+\.\d+\.\d+", expected_engine_version):
            raise HostConfigurationError("Expected engine version must use major.minor.patch form")

        private_paths = (registry_root, unreal_root, blender_root, state_root, temp_root, log_root)
        if any(not _contains(private_root, path) or _key(private_root) == _key(path)
               for path in private_paths):
            raise HostConfigurationError("All isolated storage paths must be children of FORGE_PRIVATE_ROOT")
        if _key(project_root) != _key(state_root):
            raise HostConfigurationError("FORGE_PROJECT_ROOT must equal the isolated FORGE_STATE_DIR")
        if not _contains(registry_root, unreal_root) or not _contains(registry_root, blender_root):
            raise HostConfigurationError("Application registries must be inside the private registry root")
        separated_paths = (unreal_root, blender_root, state_root, temp_root, log_root)
        for index, left in enumerate(separated_paths):
            for right in separated_paths[index + 1:]:
                if _overlaps(left, right):
                    raise HostConfigurationError("Registry, state, temporary, and log paths must be separate")

        # This is a deny-only reference to the existing shared registry. It is
        # required explicitly so a custom production root cannot be mistaken
        # for the dedicated private registry.
        shared_root = _path(env, "FORGE_SHARED_SESSION_DIR")
        if _overlaps(private_root, shared_root) or any(
            _overlaps(path, shared_root) for path in (registry_root, unreal_root, blender_root)
        ):
            raise HostConfigurationError("Isolated storage must not overlap shared session storage")

        temp_value = _key(temp_root)
        for key in ("TEMP", "TMP"):
            if _key(_path(env, key)) != temp_value:
                raise HostConfigurationError(f"{key} must point to the private FORGE_TEMP_DIR")

        allowed = _id_list(env, "FORGE_ISOLATED_ALLOWED_SESSION_IDS")
        denied = _id_list(env, "FORGE_ISOLATED_DENIED_SESSION_IDS")
        if len(allowed) != 1:
            raise HostConfigurationError("Exactly one isolated Editor session must be allowlisted")
        if allowed & denied:
            raise HostConfigurationError("A session cannot be both allowed and denied")

        try:
            expected_pid = int(_required(env, "FORGE_ISOLATED_EXPECTED_PID"))
            expected_port = int(_required(env, "FORGE_ISOLATED_EXPECTED_PORT"))
        except ValueError as exc:
            raise HostConfigurationError("Expected Editor PID and port must be decimal integers") from exc
        if expected_pid <= 0 or not 1 <= expected_port <= 65535:
            raise HostConfigurationError("Expected Editor PID or port is outside valid bounds")

        return cls(
            host_id=host_id,
            auth_context_id=auth_context_id,
            private_root=private_root,
            registry_root=registry_root,
            unreal_registry_root=unreal_root,
            blender_registry_root=blender_root,
            state_root=state_root,
            temp_root=temp_root,
            log_root=log_root,
            allowed_session_id=next(iter(allowed)),
            denied_session_ids=denied,
            expected_pid=expected_pid,
            expected_port=expected_port,
            expected_process_start_utc=expected_process_start_utc,
            expected_executable_path=expected_executable_path,
            expected_project_file=expected_project_file,
            expected_level=expected_level,
            expected_engine_version_prefix=expected_engine_version,
            tool_profile=tool_profile,
        )

    def validate_session_id(self, session_id: object) -> str:
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("An explicit session_id is required for isolated-host commands")
        if not _SESSION_ID.fullmatch(session_id):
            raise ValueError("Malformed isolated-host session_id")
        if session_id in self.denied_session_ids:
            raise ValueError("Session is explicitly denied by isolated-host policy")
        if session_id != self.allowed_session_id:
            raise ValueError("Session is not in the isolated-host allowlist")
        return session_id

    def validate_registration(self, session_id: str, kind: str, pid: int, port: int) -> None:
        self.validate_session_id(session_id)
        if kind != "unreal" or pid != self.expected_pid or port != self.expected_port:
            raise ValueError("Registration does not match the isolated Editor identity")

    def validate_project_info(self, data: object) -> None:
        if not isinstance(data, dict):
            raise ValueError("Editor identity data is invalid")
        project_file = data.get("project_file")
        level = data.get("level")
        engine_version = data.get("engine_version")
        if (
            not isinstance(project_file, str)
            or not Path(project_file).is_absolute()
            or _key(Path(project_file)) != _key(self.expected_project_file)
            or level != self.expected_level
            or not isinstance(engine_version, str)
            or not engine_version.startswith(self.expected_engine_version_prefix)
            or data.get("play_in_editor") is not False
        ):
            raise ValueError("Editor identity does not match isolated-host expectations")

    def prepare_private_directories(self) -> None:
        """Create only configured private directories; never migrate registrations or credentials."""
        for path in (
            self.private_root,
            self.registry_root,
            self.unreal_registry_root,
            self.blender_registry_root,
            self.state_root,
            self.temp_root,
            self.log_root,
        ):
            path.mkdir(parents=True, exist_ok=True)
            if not path.is_dir():
                raise HostConfigurationError("An isolated private storage path is not a directory")
