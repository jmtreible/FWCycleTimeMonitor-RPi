"""systemd integration helpers for the remote supervisor."""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict, Optional

from .settings import get_settings

LOGGER = logging.getLogger(__name__)

STATUS_PROPERTIES = (
    "Id",
    "Names",
    "ActiveState",
    "SubState",
    "Result",
    "MainPID",
    "ExecMainStartTimestamp",
    "UnitFileState",
)


class ServiceCommandError(RuntimeError):
    """Raised when ``systemctl`` returns a non-zero exit code."""

    def __init__(self, message: str, stderr: str | None = None):
        super().__init__(message)
        self.stderr = stderr


class ServiceStatus(dict):
    """Dictionary-like representation of service metadata."""

    @property
    def active(self) -> bool:
        return self.get("ActiveState") == "active"

    @property
    def pid(self) -> Optional[int]:
        try:
            value = self.get("MainPID")
            return int(value) if value else None
        except (TypeError, ValueError):
            return None

    @property
    def started_at(self) -> Optional[datetime]:
        timestamp = self.get("ExecMainStartTimestamp")
        if not timestamp:
            return None
        try:
            return datetime.strptime(timestamp, "%a %Y-%m-%d %H:%M:%S %Z")
        except ValueError:
            return None


def _run_systemctl(*args: str) -> subprocess.CompletedProcess[str]:
    command = ["sudo", "systemctl", *args]
    LOGGER.debug("Executing %%s", " ".join(command))
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise ServiceCommandError(
            f"systemctl {' '.join(args)} failed with code {result.returncode}",
            stderr=result.stderr,
        )
    return result


def get_service_status(unit_name: str | None = None) -> ServiceStatus:
    """Return ``systemctl show`` metadata for ``unit_name``."""

    unit = unit_name or get_settings().unit_name
    result = _run_systemctl(
        "show",
        unit,
        f"--property={','.join(STATUS_PROPERTIES)}",
        "--no-page",
    )
    data: Dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key] = value
    return ServiceStatus(data)


def _mutate_service(action: str, unit_name: str | None = None) -> ServiceStatus:
    unit = unit_name or get_settings().unit_name
    _run_systemctl(action, unit)
    return get_service_status(unit)


def start_service(unit_name: str | None = None) -> ServiceStatus:
    return _mutate_service("start", unit_name)


def stop_service(unit_name: str | None = None) -> ServiceStatus:
    return _mutate_service("stop", unit_name)


def restart_service(unit_name: str | None = None) -> ServiceStatus:
    return _mutate_service("restart", unit_name)


def status_summary(unit_name: str | None = None) -> Dict[str, object]:
    status = get_service_status(unit_name)
    response: Dict[str, object] = {
        "unit": unit_name or get_settings().unit_name,
        "active_state": status.get("ActiveState"),
        "sub_state": status.get("SubState"),
        "result": status.get("Result"),
        "pid": status.pid,
        "unit_file_state": status.get("UnitFileState"),
    }
    started = status.started_at
    if started is not None:
        response["started_at"] = started.isoformat()
        now = datetime.now(timezone.utc)
        started_utc = started
        if started_utc.tzinfo is None:
            started_utc = started_utc.replace(tzinfo=timezone.utc)
        response["uptime_seconds"] = max((now - started_utc).total_seconds(), 0.0)
    return response


def daemon_reload() -> None:
    _run_systemctl("daemon-reload")
