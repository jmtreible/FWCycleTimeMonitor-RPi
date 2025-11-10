"""Configuration utilities for the FW Cycle Time Monitor."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict

LOGGER = logging.getLogger(__name__)


def _sanitize_machine_id(machine_id: str) -> str:
    """Return a canonical machine identifier."""

    return machine_id.strip().upper()


def _determine_config_dir() -> Path:
    """Return the directory used for configuration and state files.

    When ``FW_CYCLE_MONITOR_CONFIG_DIR`` is defined the application stores
    configuration and runtime state in that directory.  This keeps the GUI and
    background service aligned even if they execute under different user
    accounts (for example, when systemd launches the service at boot).  The
    installer sets the variable automatically, but the code falls back to the
    traditional per-user location for manual deployments.
    """

    override = os.environ.get("FW_CYCLE_MONITOR_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "fw_cycle_monitor"


CONFIG_DIR = _determine_config_dir()
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass
class AppConfig:
    """User editable configuration."""

    machine_id: str = "M201"
    gpio_pin: int = 17
    csv_directory: Path = Path.home() / "fw_cycle_monitor_data"
    reset_hour: int = 3

    def __post_init__(self) -> None:
        self.machine_id = _sanitize_machine_id(self.machine_id)
        if not isinstance(self.csv_directory, Path):
            self.csv_directory = Path(self.csv_directory)

    def csv_path(self) -> Path:
        """Return the CSV path derived from the machine id."""

        sanitized_machine = _sanitize_machine_id(self.machine_id)
        return Path(self.csv_directory).expanduser() / f"CM_{sanitized_machine}.csv"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        defaults = cls()
        csv_directory = Path(data.get("csv_directory", defaults.csv_directory))
        try:
            reset_hour = int(data.get("reset_hour", defaults.reset_hour))
        except (TypeError, ValueError):
            reset_hour = defaults.reset_hour
        if not 0 <= reset_hour <= 23:
            reset_hour = defaults.reset_hour

        return cls(
            machine_id=_sanitize_machine_id(str(data.get("machine_id", defaults.machine_id))),
            gpio_pin=int(data.get("gpio_pin", defaults.gpio_pin)),
            csv_directory=csv_directory,
            reset_hour=reset_hour,
        )


def ensure_config_dir() -> None:
    """Ensure the configuration directory exists."""

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> AppConfig:
    """Load configuration from disk, returning defaults when missing."""

    ensure_config_dir()
    if not CONFIG_PATH.exists():
        LOGGER.debug("Config file %s not found; using defaults", CONFIG_PATH)
        return AppConfig()

    try:
        data = json.loads(CONFIG_PATH.read_text())
        LOGGER.debug("Loaded config: %s", data)
        return AppConfig.from_dict(data)
    except (json.JSONDecodeError, OSError) as exc:
        LOGGER.warning("Failed to load config %s: %s", CONFIG_PATH, exc)
        return AppConfig()


def save_config(config: AppConfig) -> None:
    """Persist configuration to disk."""

    ensure_config_dir()

    previous_config: AppConfig | None = None
    if CONFIG_PATH.exists():
        try:
            existing = json.loads(CONFIG_PATH.read_text())
            previous_config = AppConfig.from_dict(existing)
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            LOGGER.debug("Existing configuration could not be loaded for comparison", exc_info=True)

    serializable = asdict(config)
    serializable["csv_directory"] = str(config.csv_directory)
    CONFIG_PATH.write_text(json.dumps(serializable, indent=2))
    LOGGER.debug("Saved config to %s", CONFIG_PATH)

    if previous_config:
        _handle_machine_change(previous_config, config)


def _handle_machine_change(previous: AppConfig, current: AppConfig) -> None:
    """Clean up state tied to a prior machine configuration."""

    prev_machine = _sanitize_machine_id(previous.machine_id)
    curr_machine = _sanitize_machine_id(current.machine_id)
    prev_directory = Path(previous.csv_directory).expanduser()
    curr_directory = Path(current.csv_directory).expanduser()

    if prev_machine == curr_machine and prev_directory == curr_directory:
        return

    if prev_machine:
        try:
            from .state import clear_cycle_state

            clear_cycle_state(prev_machine)
        except Exception:  # pragma: no cover - defensive cleanup
            LOGGER.debug("Unable to clear stored state for %s", prev_machine, exc_info=True)

        try:
            from .metrics import clear_cycle_metrics

            clear_cycle_metrics(prev_machine)
        except Exception:  # pragma: no cover - defensive cleanup
            LOGGER.debug("Unable to clear stored metrics for %s", prev_machine, exc_info=True)

        _remove_machine_sidecars(prev_machine, prev_directory)


def _remove_machine_sidecars(machine_id: str, csv_directory: Path) -> None:
    """Delete stale pending/state files associated with ``machine_id``."""

    sanitized = _sanitize_machine_id(machine_id)
    if not sanitized:
        return

    csv_dir = csv_directory.expanduser()
    base = csv_dir / f"CM_{sanitized}.csv"
    targets = [
        base.with_name(base.name + ".pending"),
        base.with_name(base.name + ".state.json"),
    ]

    for path in targets:
        try:
            if path.exists():
                path.unlink()
                LOGGER.info("Removed stale file %s for retired machine %s", path, sanitized)
        except OSError:
            LOGGER.warning("Failed to remove stale file %s", path, exc_info=True)
