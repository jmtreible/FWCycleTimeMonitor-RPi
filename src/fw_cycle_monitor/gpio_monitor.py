"""GPIO monitoring logic for the FW Cycle Time Monitor."""

from __future__ import annotations

import csv
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from .config import AppConfig

LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover - hardware-specific import
    import RPi.GPIO as GPIO  # type: ignore

    GPIO.setmode(GPIO.BCM)
    _GPIO_AVAILABLE = True
except Exception:  # pragma: no cover - executed on non-RPi systems
    GPIO = None  # type: ignore
    _GPIO_AVAILABLE = False


class GPIOUnavailableError(RuntimeError):
    """Raised when RPi.GPIO is not available on the current system."""


@dataclass
class MonitorStats:
    """Statistics about monitoring events."""

    last_event_time: Optional[datetime] = None
    events_logged: int = 0


class CycleMonitor:
    """Monitor a GPIO pin for rising edges and log cycle times."""

    def __init__(self, config: AppConfig, callback: Optional[Callable[[datetime], None]] = None):
        self.config = config
        self._callback = callback
        self._lock = threading.Lock()
        self._stats = MonitorStats()
        self._running = False

    @property
    def stats(self) -> MonitorStats:
        return self._stats

    def start(self) -> None:
        if not _GPIO_AVAILABLE:
            raise GPIOUnavailableError(
                "RPi.GPIO is not available. Run on a Raspberry Pi with the library installed."
            )

        with self._lock:
            if self._running:
                LOGGER.debug("CycleMonitor already running")
                return
            LOGGER.info("Starting monitor on pin %s for machine %s", self.config.gpio_pin, self.config.machine_id)
            self._setup_gpio()
            self._running = True

    def stop(self) -> None:
        if not _GPIO_AVAILABLE:
            return

        with self._lock:
            if not self._running:
                return
            LOGGER.info("Stopping monitor on pin %s", self.config.gpio_pin)
            try:
                GPIO.remove_event_detect(self.config.gpio_pin)  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - best effort cleanup
                LOGGER.debug("Event detect removal failed", exc_info=True)
            GPIO.cleanup(self.config.gpio_pin)  # type: ignore[attr-defined]
            self._running = False

    def _setup_gpio(self) -> None:
        Path(self.config.csv_directory).mkdir(parents=True, exist_ok=True)
        GPIO.setup(self.config.gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # type: ignore[attr-defined]
        GPIO.add_event_detect(  # type: ignore[attr-defined]
            self.config.gpio_pin,
            GPIO.RISING,
            callback=self._handle_event,
            bouncetime=200,
        )

    def _handle_event(self, channel: int) -> None:  # pragma: no cover - triggered by GPIO
        timestamp = datetime.now(timezone.utc).astimezone()
        csv_path = self.config.csv_path()
        try:
            is_new_file = not csv_path.exists()
            with csv_path.open("a", newline="") as csv_file:
                writer = csv.writer(csv_file)
                if is_new_file:
                    writer.writerow(["machine_id", "timestamp"])
                writer.writerow([self.config.machine_id, timestamp.isoformat()])
            LOGGER.debug("Logged cycle at %s to %s", timestamp.isoformat(), csv_path)
        except OSError:
            LOGGER.exception("Failed to write cycle event to %s", csv_path)
            return

        with self._lock:
            self._stats.last_event_time = timestamp
            self._stats.events_logged += 1

        if self._callback:
            try:
                self._callback(timestamp)
            except Exception:  # pragma: no cover - UI callback errors
                LOGGER.exception("Cycle event callback failed")

    def simulate_event(self) -> datetime:
        """Simulate an event for testing environments without GPIO.

        Returns the timestamp that was logged.
        """

        timestamp = datetime.now(timezone.utc).astimezone()
        csv_path = self.config.csv_path()
        is_new_file = not csv_path.exists()
        with csv_path.open("a", newline="") as csv_file:
            writer = csv.writer(csv_file)
            if is_new_file:
                writer.writerow(["machine_id", "timestamp"])
            writer.writerow([self.config.machine_id, timestamp.isoformat()])
        with self._lock:
            self._stats.last_event_time = timestamp
            self._stats.events_logged += 1
        if self._callback:
            self._callback(timestamp)
        return timestamp
