"""Persistence helpers for cycle monitor runtime state."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from .config import CONFIG_DIR, ensure_config_dir

LOGGER = logging.getLogger(__name__)

STATE_PATH = CONFIG_DIR / "state.json"
_STATE_TMP_SUFFIX = ".tmp"

__all__ = ["MachineState", "load_cycle_state", "save_cycle_state", "clear_cycle_state"]


@dataclass
class MachineState:
    """State persisted for a specific machine."""

    machine_id: str
    last_cycle: int
    last_timestamp: datetime


def _load_state_blob() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        LOGGER.warning("Failed to load state file %s: %s", STATE_PATH, exc)
        return {}


def _save_state_blob(data: Dict[str, Any]) -> None:
    ensure_config_dir()
    tmp_path = STATE_PATH.with_suffix(STATE_PATH.suffix + _STATE_TMP_SUFFIX)
    try:
        tmp_path.write_text(json.dumps(data, indent=2))
        tmp_path.replace(STATE_PATH)
    except OSError:
        LOGGER.exception("Unable to persist cycle state to %s", STATE_PATH)
        try:
            tmp_path.unlink(missing_ok=True)  # type: ignore[arg-type]
        except OSError:
            LOGGER.debug("Failed to remove temporary state file %s", tmp_path, exc_info=True)


def load_cycle_state(machine_id: str) -> Optional[MachineState]:
    """Load the stored state for ``machine_id`` if it exists."""

    data = _load_state_blob()
    machines = data.get("machines")
    if not isinstance(machines, dict):
        LOGGER.debug("State file %s does not contain machine mapping", STATE_PATH)
        return None

    raw_state = machines.get(machine_id)
    if not isinstance(raw_state, dict):
        LOGGER.debug("No stored state found for machine %s", machine_id)
        return None

    try:
        last_cycle = int(raw_state.get("last_cycle", 0))
        timestamp_str = raw_state["last_timestamp"]
        last_timestamp = datetime.fromisoformat(timestamp_str)
    except (KeyError, ValueError, TypeError):
        LOGGER.warning("State for %s is invalid; ignoring", machine_id)
        return None

    LOGGER.info(
        "Restored cycle state for %s: last_cycle=%s at %s",
        machine_id,
        last_cycle,
        last_timestamp.isoformat(),
    )
    return MachineState(machine_id=machine_id, last_cycle=last_cycle, last_timestamp=last_timestamp)


def save_cycle_state(machine_id: str, *, last_cycle: int, last_timestamp: datetime) -> None:
    """Persist the latest cycle details for ``machine_id``."""

    data = _load_state_blob()
    machines = data.setdefault("machines", {})
    if not isinstance(machines, dict):
        machines = {}
        data["machines"] = machines

    machines[machine_id] = {
        "last_cycle": int(last_cycle),
        "last_timestamp": last_timestamp.isoformat(),
    }

    _save_state_blob(data)
    LOGGER.debug(
        "Persisted cycle state for %s to %s (cycle=%s, timestamp=%s)",
        machine_id,
        STATE_PATH,
        last_cycle,
        last_timestamp.isoformat(),
    )


def clear_cycle_state(machine_id: str) -> None:
    """Remove stored state for ``machine_id``."""

    data = _load_state_blob()
    machines = data.get("machines")
    if not isinstance(machines, dict) or machine_id not in machines:
        return
    machines.pop(machine_id, None)
    _save_state_blob(data)
