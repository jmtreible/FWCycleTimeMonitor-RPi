"""Configuration utilities for the FW Cycle Time Monitor."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict

LOGGER = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".config" / "fw_cycle_monitor"
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass
class AppConfig:
    """User editable configuration."""

    machine_id: str = "M201"
    gpio_pin: int = 17
    csv_directory: Path = Path.home() / "fw_cycle_monitor_data"
    reset_hour: int = 3

    def csv_path(self) -> Path:
        """Return the CSV path derived from the machine id."""

        sanitized_machine = self.machine_id.strip().upper()
        return Path(self.csv_directory) / f"CM_{sanitized_machine}.csv"

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
            machine_id=data.get("machine_id", defaults.machine_id),
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
    serializable = asdict(config)
    serializable["csv_directory"] = str(config.csv_directory)
    CONFIG_PATH.write_text(json.dumps(serializable, indent=2))
    LOGGER.debug("Saved config to %s", CONFIG_PATH)
