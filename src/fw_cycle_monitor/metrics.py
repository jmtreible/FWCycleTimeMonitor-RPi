"""Cycle metrics persistence and calculations."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .config import CONFIG_DIR, ensure_config_dir

LOGGER = logging.getLogger(__name__)

METRICS_PATH = CONFIG_DIR / "metrics.json"
RETENTION_PERIOD = timedelta(hours=2)
AVERAGE_WINDOWS: tuple[int, ...] = (5, 15, 30, 60)


@dataclass
class CycleMetrics:
    """Timestamp history for a machine's cycle events."""

    machine_id: str
    timestamps: List[datetime]


@dataclass
class CycleStatistics:
    """Computed statistics for cycle times."""

    last_cycle_seconds: Optional[float]
    window_averages: Dict[int, Optional[float]]


def _load_metrics_blob() -> Dict[str, Any]:
    if not METRICS_PATH.exists():
        return {}
    try:
        return json.loads(METRICS_PATH.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        LOGGER.warning("Failed to read metrics file %s: %s", METRICS_PATH, exc)
        return {}


def _save_metrics_blob(data: Dict[str, Any]) -> None:
    ensure_config_dir()
    tmp_path = METRICS_PATH.with_suffix(METRICS_PATH.suffix + ".tmp")
    try:
        tmp_path.write_text(json.dumps(data, indent=2))
        tmp_path.replace(METRICS_PATH)
    except OSError:
        LOGGER.exception("Unable to persist metrics to %s", METRICS_PATH)
        try:
            tmp_path.unlink(missing_ok=True)  # type: ignore[arg-type]
        except OSError:
            LOGGER.debug("Failed to remove temporary metrics file %s", tmp_path, exc_info=True)


def _canonical_machine_id(machine_id: str) -> str:
    return machine_id.strip().upper()


def load_cycle_metrics(machine_id: str) -> CycleMetrics:
    """Load stored timestamps for ``machine_id``."""

    canonical_id = _canonical_machine_id(machine_id)
    data = _load_metrics_blob()
    machines = data.get("machines")
    if not isinstance(machines, dict):
        machines = {}
    raw_timestamps = machines.get(canonical_id, [])
    timestamps: List[datetime] = []
    if isinstance(raw_timestamps, list):
        for value in raw_timestamps:
            if not isinstance(value, str):
                continue
            try:
                timestamp = datetime.fromisoformat(value)
            except ValueError:
                continue
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            timestamps.append(timestamp)
    timestamps.sort()
    return CycleMetrics(machine_id=canonical_id, timestamps=timestamps)


def save_cycle_metrics(metrics: CycleMetrics) -> None:
    """Persist ``metrics`` to disk."""

    canonical_id = _canonical_machine_id(metrics.machine_id)
    data = _load_metrics_blob()
    machines = data.setdefault("machines", {})
    if not isinstance(machines, dict):
        machines = {}
        data["machines"] = machines
    machines[canonical_id] = [ts.isoformat() for ts in sorted(metrics.timestamps)]
    _save_metrics_blob(data)


def record_cycle_event(machine_id: str, timestamp: datetime) -> None:
    """Record a cycle event for ``machine_id`` at ``timestamp``."""

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    metrics = load_cycle_metrics(machine_id)
    metrics.timestamps.append(timestamp)
    metrics.timestamps.sort()

    cutoff = timestamp - RETENTION_PERIOD
    filtered = [ts for ts in metrics.timestamps if ts >= cutoff]
    if len(filtered) < 2 and metrics.timestamps:
        filtered = metrics.timestamps[-2:]
    metrics.timestamps = filtered

    save_cycle_metrics(metrics)


def clear_cycle_metrics(machine_id: str) -> None:
    """Remove stored metrics for ``machine_id``."""

    canonical_id = _canonical_machine_id(machine_id)
    data = _load_metrics_blob()
    machines = data.get("machines")
    if not isinstance(machines, dict) or canonical_id not in machines:
        return
    machines.pop(canonical_id, None)
    _save_metrics_blob(data)


def calculate_cycle_statistics(machine_id: str, now: Optional[datetime] = None) -> CycleStatistics:
    """Calculate statistics for ``machine_id``."""

    metrics = load_cycle_metrics(machine_id)
    timestamps = metrics.timestamps
    if now is None:
        now = datetime.now(timezone.utc).astimezone()

    last_cycle: Optional[float] = None
    if len(timestamps) >= 2:
        last_cycle = (timestamps[-1] - timestamps[-2]).total_seconds()

    averages: Dict[int, Optional[float]] = {}
    for window in AVERAGE_WINDOWS:
        cutoff = now - timedelta(minutes=window)
        durations = [
            (end - start).total_seconds()
            for start, end in zip(timestamps, timestamps[1:])
            if end >= cutoff
        ]
        if durations:
            averages[window] = sum(durations) / len(durations)
        else:
            averages[window] = None

    return CycleStatistics(last_cycle_seconds=last_cycle, window_averages=averages)

