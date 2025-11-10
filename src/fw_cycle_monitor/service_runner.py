"""Headless service entry point for the FW Cycle Time Monitor."""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import AppConfig, load_config
from .gpio_monitor import CycleMonitor, GPIOUnavailableError
from .updater import determine_repo_path, sync_environment, update_repository

LOGGER = logging.getLogger(__name__)
_STOP_EVENT = threading.Event()


def _handle_signal(signum: int, _frame: Optional[object]) -> None:
    LOGGER.info("Received signal %s; stopping monitor", signum)
    _STOP_EVENT.set()


def _log_cycle_event(timestamp: datetime) -> None:
    LOGGER.info("Cycle logged at %s", timestamp.isoformat())


def _install_signal_handlers() -> None:
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(sig, _handle_signal)
        except ValueError:
            # Signal handling is only permitted in the main thread; if this is
            # not the main thread we simply skip installing handlers.
            LOGGER.debug("Unable to install handler for signal %s", sig, exc_info=True)


def _summarize_config(config: AppConfig) -> str:
    return (
        f"machine_id={config.machine_id}, pin={config.gpio_pin}, "
        f"csv={config.csv_path()}, reset_hour={config.reset_hour}"
    )


def _refresh_code() -> None:
    repo_path = determine_repo_path(Path(__file__).resolve().parents[2])
    extras = os.environ.get("FW_CYCLE_MONITOR_INSTALL_EXTRAS")

    LOGGER.info("Ensuring repository at %s is up to date", repo_path)
    if update_repository(repo_path):
        LOGGER.info("Repository updated; refreshing Python package")
        if not sync_environment(repo_path, extras):
            LOGGER.warning(
                "Failed to refresh installed package; the service may run with stale dependencies"
            )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    _refresh_code()

    config = load_config()
    LOGGER.info("Loaded configuration: %s", _summarize_config(config))

    monitor = CycleMonitor(config, callback=_log_cycle_event)
    try:
        monitor.start()
    except GPIOUnavailableError as exc:
        LOGGER.error("GPIO is unavailable: %s", exc)
        return 1
    except Exception as exc:  # pragma: no cover - hardware-specific failure
        LOGGER.exception("Failed to start cycle monitor")
        return 1

    _install_signal_handlers()
    LOGGER.info("Cycle monitor started; waiting for events")

    try:
        while not _STOP_EVENT.wait(timeout=1):
            continue
    except KeyboardInterrupt:
        LOGGER.info("Keyboard interrupt received; stopping monitor")
    finally:
        LOGGER.info("Stopping cycle monitor")
        try:
            monitor.stop()
        except Exception:  # pragma: no cover - best effort cleanup
            LOGGER.exception("Error while stopping cycle monitor")

    pending = monitor.stats.events_logged
    LOGGER.info("Monitor stopped. Total events logged this session: %s", pending)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
